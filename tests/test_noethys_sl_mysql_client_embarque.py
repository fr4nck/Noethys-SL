# -*- coding: utf-8 -*-
"""RC6 lot A : sauvegarde/restauration réseau avec les clients MySQL livrés.

Toujours exécutés (sans base, sans wx affiché) :
- résolution du répertoire mysql-client/ embarqué, prioritaire sur un client installé ;
- fichier d'identifiants temporaire : valeurs quotées, UTF-8, jamais réécrit sur place.

Aller-retour réel (Windows uniquement), seulement si sont déclarés :
- NOETHYS_TEST_MYSQL_HOST/_PORT/_USER/_PASSWORD : serveur MySQL LOCAL et jetable
  (garde _garde_reseau : 127.0.0.1/localhost seulement) ;
- NOETHYS_TEST_MYSQL_APP_DIR : racine d'un paquet contenant mysql-client/bin.
Le vrai Sauvegarde() produit un .nod via mysqldump, puis le vrai Restauration()
le réimporte via mysql ; les données sont comparées octet par octet.
"""
import os
import sys
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402  (profil temporaire, réseau interdit)

try:
    import wx  # noqa: F401
    from Utils import UTILS_Sauvegarde
except ImportError:  # wx absent : seuls les tests de source restent pertinents
    UTILS_Sauvegarde = None

import GestionDB  # noqa: E402

MOT_DE_PASSE_PIEGE = u'P#w;d "x\\y\'z é '
BASE = "noethys_rc6_recette_data"


def _analyse_option_mysql(valeur):
    """ Lecture d'une valeur quotée selon my_default.cc (MySQL 5.7). """
    if len(valeur) > 1 and valeur[0] in "\"'" and valeur[-1] == valeur[0]:
        valeur = valeur[1:-1]
    sortie, i = [], 0
    echappements = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "s": " ", '"': '"', "'": "'", "\\": "\\"}
    while i < len(valeur):
        if valeur[i] == "\\" and i != len(valeur) - 1:
            i += 1
            sortie.append(echappements.get(valeur[i], "\\" + valeur[i]))
        else:
            sortie.append(valeur[i])
        i += 1
    return "".join(sortie)


class _FauxWx(object):
    ID_YES = 5103
    ID_OK = 5100
    messages = []

    def __getattr__(self, nom):
        return 0

    class _Dialogue(object):
        def __init__(self, *args, **kwargs):
            # MessageDialog(parent, message, ...) ; ProgressDialog(titre, message, ...)
            _FauxWx.messages.append(u" | ".join(a for a in args if isinstance(a, str)))

        def ShowModal(self):
            return _FauxWx.ID_YES

        def Update(self, *args, **kwargs):
            return True

        def Destroy(self):
            return None

    MessageDialog = _Dialogue
    ProgressDialog = _Dialogue

    @staticmethod
    def DirDialog(*args, **kwargs):
        raise AssertionError("Le client embarqué aurait dû être trouvé sans demander de répertoire.")


@unittest.skipIf(UTILS_Sauvegarde is None, "wxPython requis pour importer UTILS_Sauvegarde")
class ClientEmbarqueTests(unittest.TestCase):
    def setUp(self):
        self.racine = tempfile.mkdtemp(prefix="noethys-rc6-app-")
        self.addCleanup(shutil.rmtree, self.racine, True)

    def _chemin_principal(self, fichier=""):
        return os.path.join(self.racine, fichier)

    def test_client_embarque_complet_prioritaire(self):
        bin_ = os.path.join(self.racine, "mysql-client", "bin")
        os.makedirs(bin_)
        for nom in ("mysql.exe", "mysqldump.exe"):
            open(os.path.join(bin_, nom), "wb").close()
        with mock.patch.object(UTILS_Sauvegarde.Chemins, "GetMainPath", self._chemin_principal):
            chemin = UTILS_Sauvegarde.GetRepertoireMySQLEmbarque()
            self.assertEqual(chemin, self.racine.replace("\\", "/") + "/mysql-client/")
            if sys.platform == "win32":
                with mock.patch.object(UTILS_Sauvegarde.os, "listdir", side_effect=AssertionError("recherche Program Files")):
                    self.assertEqual(UTILS_Sauvegarde.GetRepertoireMySQL({}), chemin)

    def test_client_embarque_incomplet_ignore(self):
        bin_ = os.path.join(self.racine, "mysql-client", "bin")
        os.makedirs(bin_)
        open(os.path.join(bin_, "mysql.exe"), "wb").close()
        with mock.patch.object(UTILS_Sauvegarde.Chemins, "GetMainPath", self._chemin_principal):
            self.assertIsNone(UTILS_Sauvegarde.GetRepertoireMySQLEmbarque())

    def test_identifiants_quotes_utf8_et_relus_a_l_identique(self):
        fichier = os.path.join(self.racine, "logintemp.cnf")
        UTILS_Sauvegarde.CreationFichierLoginTemp(
            host="127.0.0.1", user="recette", port=3399,
            password=GestionDB.EncodeMdpReseau(MOT_DE_PASSE_PIEGE), nomFichier=fichier)
        with open(fichier, "rb") as f:
            lignes = f.read().decode("utf-8").splitlines()
        self.assertEqual(lignes[0], "[client]")
        valeurs = dict(ligne.split("=", 1) for ligne in lignes[1:])
        self.assertEqual({cle: _analyse_option_mysql(v) for cle, v in valeurs.items()},
                         {"host": "127.0.0.1", "user": "recette", "port": "3399",
                          "password": MOT_DE_PASSE_PIEGE})
        # Recréation : l'ancien fichier est remplacé, jamais complété.
        UTILS_Sauvegarde.CreationFichierLoginTemp(host="h", user="u", port=1, password="p", nomFichier=fichier)
        with open(fichier, "rb") as f:
            self.assertEqual(f.read().decode("utf-8").count("[client]"), 1)


def _parametres_recette():
    if sys.platform != "win32" or UTILS_Sauvegarde is None:
        return None
    app = os.environ.get("NOETHYS_TEST_MYSQL_APP_DIR", "")
    if not app or _garde_reseau.ParametresMySQLDeTest() is None:
        return None
    return app


@unittest.skipIf(_parametres_recette() is None,
                 "Recette réelle : serveur MySQL local jetable et paquet mysql-client non déclarés")
class AllerRetourReelTests(unittest.TestCase):
    """ Ne s'exécute que contre le serveur MySQL local de test (garde réseau). """

    @classmethod
    def setUpClass(cls):
        import MySQLdb
        cls.app = _parametres_recette()
        cls.contexte = _garde_reseau.ServeurMySQLDeTest()
        cls.p = cls.contexte.__enter__()
        cls.MySQLdb = MySQLdb
        cls.mdp = cls.p["motdepasse"]
        cls.dictConnexion = {
            "port": cls.p["port"], "hote": cls.p["hote"], "host": cls.p["hote"],
            "user": cls.p["utilisateur"], "utilisateur": cls.p["utilisateur"],
            "mdp": GestionDB.EncodeMdpReseau(cls.mdp), "password": GestionDB.EncodeMdpReseau(cls.mdp),
            "fichier": BASE}
        cls.patch_wx = mock.patch.object(UTILS_Sauvegarde, "wx", _FauxWx())
        cls.patch_wx.start()
        cls.patch_app = mock.patch.object(UTILS_Sauvegarde.Chemins, "GetMainPath",
                                          lambda fichier="": os.path.join(cls.app, fichier))
        cls.patch_app.start()

    @classmethod
    def tearDownClass(cls):
        try:
            cx = cls._connexion()
            cx.cursor().execute("DROP DATABASE IF EXISTS `%s`" % BASE)
            cx.close()
        finally:
            cls.patch_app.stop()
            cls.patch_wx.stop()
            cls.contexte.__exit__(None, None, None)

    @classmethod
    def _connexion(cls, base=None):
        options = dict(host=cls.p["hote"], port=cls.p["port"], user=cls.p["utilisateur"],
                       passwd=cls.mdp, charset="utf8")
        if base:
            options["db"] = base
        return cls.MySQLdb.connect(**options)

    def _creer_base_fictive(self):
        cx = self._connexion()
        cur = cx.cursor()
        cur.execute("DROP DATABASE IF EXISTS `%s`" % BASE)
        cur.execute("CREATE DATABASE `%s` CHARACTER SET utf8" % BASE)
        cur.execute("USE `%s`" % BASE)
        cur.execute("""CREATE TABLE familles (IDfamille INTEGER PRIMARY KEY AUTO_INCREMENT,
            nom VARCHAR(200), memo TEXT, solde DECIMAL(10,2), naissance DATE, maj DATETIME, doc LONGBLOB)""")
        lignes = [
            (u"Famille Éloïse d'Arc", u"ligne1\nligne2; \"guillemets\" \\ fin", "12.50", "2015-03-01", "2026-10-14 10:00:00", bytes(range(256))),
            (u"Famille NULL", None, None, None, None, None),
            (u"Famille ; -- pas un commentaire /* ni ceci */", u"#dièse", "-3.00", "2001-12-31", "2026-01-01 00:00:00", b"\x00\x1a\\'\""),
        ]
        cur.executemany("INSERT INTO familles (nom, memo, solde, naissance, maj, doc) VALUES (%s,%s,%s,%s,%s,%s)", lignes)
        cur.execute("CREATE TABLE reglements (IDreglement INTEGER PRIMARY KEY, IDfamille INTEGER, montant DECIMAL(10,2))")
        cur.executemany("INSERT INTO reglements VALUES (%s,%s,%s)", [(i, 1 + i % 3, "%d.25" % i) for i in range(1, 2001)])
        cx.commit()
        cx.close()

    def _contenu(self):
        cx = self._connexion(BASE)
        cur = cx.cursor()
        contenu = {}
        for table in ("familles", "reglements"):
            cur.execute("SELECT * FROM %s ORDER BY 1" % table)
            contenu[table] = cur.fetchall()
        cx.close()
        return contenu

    def _fichiers_identifiants_restants(self):
        restants = []
        for racine, _, fichiers in os.walk(_garde_reseau.PROFIL_TEST):
            restants += [os.path.join(racine, f) for f in fichiers if f.endswith(".cnf")]
        return restants

    def test_sauvegarde_puis_restauration_identiques(self):
        self._creer_base_fictive()
        attendu = self._contenu()
        dossier = tempfile.mkdtemp(prefix="noethys-rc6-nod-")
        self.addCleanup(shutil.rmtree, dossier, True)

        self.assertIs(UTILS_Sauvegarde.Sauvegarde(listeFichiersReseau=[BASE], nom="recette_rc6", repertoire=dossier,
                                                  dictConnexion=self.dictConnexion), True, _FauxWx.messages[-3:])
        nod = os.path.join(dossier, "recette_rc6.nod")
        self.assertTrue(zipfile.is_zipfile(nod))
        with zipfile.ZipFile(nod) as z:
            self.assertEqual(z.namelist(), [BASE + ".sql"])
            dump = z.read(BASE + ".sql")
        self.assertTrue(dump.startswith(b"-- NOETHYS-SQL-MANIFEST-V1 "))
        self.assertIn(b"-- Dump completed", dump)
        self.assertEqual(self._fichiers_identifiants_restants(), [])

        # Base supprimée : la restauration doit la recréer à l'identique.
        cx = self._connexion()
        cx.cursor().execute("DROP DATABASE `%s`" % BASE)
        cx.close()
        self.assertEqual(UTILS_Sauvegarde.Restauration(fichier=nod, listeFichiersReseau=[BASE + ".sql"],
                                                       dictConnexion=self.dictConnexion), [BASE], _FauxWx.messages[-3:])
        self.assertEqual(self._contenu(), attendu)

        # Base existante modifiée : remplacée par le contenu sauvegardé.
        cx = self._connexion(BASE)
        cx.cursor().execute("DELETE FROM reglements WHERE IDreglement > 10")
        cx.commit()
        cx.close()
        self.assertEqual(UTILS_Sauvegarde.Restauration(fichier=nod, listeFichiersReseau=[BASE + ".sql"],
                                                       dictConnexion=self.dictConnexion), [BASE])
        self.assertEqual(self._contenu(), attendu)
        self.assertEqual(self._fichiers_identifiants_restants(), [])

    def test_identifiants_refuses_aucune_archive(self):
        self._creer_base_fictive()
        dossier = tempfile.mkdtemp(prefix="noethys-rc6-nod-")
        self.addCleanup(shutil.rmtree, dossier, True)
        faux = dict(self.dictConnexion, password=GestionDB.EncodeMdpReseau(self.mdp + "x"))
        self.assertIs(UTILS_Sauvegarde.Sauvegarde(listeFichiersReseau=[BASE], nom="refus_rc6", repertoire=dossier,
                                                  dictConnexion=faux), False)
        self.assertEqual(os.listdir(dossier), [])
        self.assertIn("1045", _FauxWx.messages[-1])
        self.assertEqual(self._fichiers_identifiants_restants(), [])

    def test_archive_alteree_refusee_sans_modifier_la_base(self):
        self._creer_base_fictive()
        attendu = self._contenu()
        dossier = tempfile.mkdtemp(prefix="noethys-rc6-nod-")
        self.addCleanup(shutil.rmtree, dossier, True)
        self.assertIs(UTILS_Sauvegarde.Sauvegarde(listeFichiersReseau=[BASE], nom="alteree", repertoire=dossier,
                                                  dictConnexion=self.dictConnexion), True)
        nod = os.path.join(dossier, "alteree.nod")
        with zipfile.ZipFile(nod) as z:
            dump = z.read(BASE + ".sql")
        alteree = os.path.join(dossier, "alteree2.nod")
        with zipfile.ZipFile(alteree, "w") as z:
            z.writestr(BASE + ".sql", dump.replace(b"Famille NULL", b"Famille XXXX"))
        self.assertIs(UTILS_Sauvegarde.Restauration(fichier=alteree, listeFichiersReseau=[BASE + ".sql"],
                                                    dictConnexion=self.dictConnexion), False)
        self.assertIn(u"aucune donnée n'a été modifiée", _FauxWx.messages[-1])
        self.assertEqual(self._contenu(), attendu)


if __name__ == "__main__":
    unittest.main()
