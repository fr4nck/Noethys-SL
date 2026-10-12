# -*- coding: utf-8 -*-
"""Noe-032 : controles avant toute ecriture, marqueur terminal et postconditions.

Restauration et ses aides sont isolees par AST ; MySQL est simule par un faux
client a etats qui execute (ou non) le marqueur ajoute a la copie extraite.
Aucun reseau, profil, base reelle ni wx.
"""
import ast
import importlib.util
import os
import re
import shutil
import tempfile
import types
import unittest
import zipfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Sauvegarde.py"
HELPER = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_SQL_Integrite.py"
FONCTIONS_RESTAURATION = (
    "Restauration", "_NomFichierReseau",
    "_VerifierPostconditionRestaurationMySQL", "_SupprimerMarqueurRestaurationMySQL",
)
FIN = b"\n-- Dump completed on 2026-10-12 12:00:00\n"


def _charger_manifeste():
    spec = importlib.util.spec_from_file_location("sql_manifest_integrite", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Dialogue:
    messages = []

    def __init__(self, parent=None, message="", *args, **kwargs):
        _Dialogue.messages.append(message)

    def ShowModal(self):
        return 5103

    def Update(self, *args, **kwargs):
        return True

    def Destroy(self):
        return None


class _Progression(_Dialogue):
    def __init__(self, *args, **kwargs):
        pass


class _FauxMySQL:
    """Client mysql et connexions GestionDB simules sur un etat partage."""

    def __init__(self, mode="complet", code_retour=0):
        self.mode = mode
        self.code_retour = code_retour
        self.imports = []
        self.bases_creees = []
        self.tables = set()
        self.marqueur = None
        self.suppressions_marqueur = 0
        self.connexions_ouvertes = 0

    # --- client mysql (subprocess.Popen) ---
    def popen(self, commande, **kwargs):
        chemin = re.search(r'<\s*"([^"]+)"', commande).group(1)
        sql = Path(chemin).read_text(encoding="utf-8", errors="ignore")
        self.imports.append(sql)
        marqueur = re.search(r"-- NOETHYS-RESTORE-END-V1 ([0-9a-f]{32})", sql)
        tables = set(t.lower() for t in re.findall(r"CREATE TABLE `?([A-Za-z0-9_]+)`?", sql))
        tables = set(t for t in tables if not t.startswith("__noethys_restore_"))
        if self.mode == "objet_manquant":
            tables = set(sorted(tables)[1:])
        self.tables = tables
        if marqueur and self.mode != "marqueur_non_execute" and self.code_retour == 0:
            self.marqueur = marqueur.group(1)
        etat = self

        class Processus:
            returncode = etat.code_retour

            def communicate(self):
                return b"", None

        return Processus()

    # --- GestionDB.DB ---
    def db(self, suffixe=None, nomFichier="", modeCreation=False):
        etat = self
        if modeCreation:
            self.bases_creees.append(nomFichier)
        self.connexions_ouvertes += 1

        class Connexion:
            echec = 0
            derniere = None

            def ExecuterReq(self, requete):
                self.derniere = requete
                if requete.startswith("DROP TABLE IF EXISTS `__noethys_restore_"):
                    etat.suppressions_marqueur += 1
                    etat.marqueur = None
                return 1

            def ResultatReq(self):
                if self.derniere.startswith("SELECT `jeton`"):
                    return [(etat.marqueur,)] if etat.marqueur else []
                if self.derniere.startswith("SHOW FULL TABLES"):
                    lignes = [(t, "BASE TABLE") for t in sorted(etat.tables)]
                    if etat.marqueur:
                        lignes.append(("__noethys_restore_" + etat.marqueur, "BASE TABLE"))
                    return lignes
                return []

            def Close(self):
                etat.connexions_ouvertes -= 1

        return Connexion()


class RestaurationManifesteTests(unittest.TestCase):
    def setUp(self):
        _Dialogue.messages = []

    def _executer(self, archive, rep, processus_interdit=False, base_interdite=False,
                  faux=None, locaux=(), reseau=("base_fictive.sql",)):
        faux = faux or _FauxMySQL()
        wx = types.SimpleNamespace(
            MessageDialog=_Dialogue, ProgressDialog=_Progression,
            ID_YES=5103, YES_NO=0, CANCEL=0, NO_DEFAULT=0,
            ICON_EXCLAMATION=0, ICON_ERROR=0, OK=0,
            PD_SMOOTH=0, PD_AUTO_HIDE=0, PD_APP_MODAL=0,
        )

        def popen(*args, **kwargs):
            if processus_interdit:
                raise AssertionError("mysql execute avant verification SQL")
            return faux.popen(*args, **kwargs)

        def db(*args, **kwargs):
            if base_interdite and kwargs.get("modeCreation"):
                raise AssertionError("base creee avant verification SQL")
            return faux.db(*args, **kwargs)

        rep_data = rep / "data"
        rep_data.mkdir(exist_ok=True)
        deps = {
            "zipfile": zipfile, "os": os, "shutil": shutil,
            "wx": wx, "_": lambda texte: texte,
            "six": types.SimpleNamespace(PY2=False),
            "subprocess": types.SimpleNamespace(Popen=popen, PIPE=-1, STDOUT=-2),
            "GestionDB": types.SimpleNamespace(DB=db),
            "UTILS_SQL_Integrite": _charger_manifeste(),
            "UTILS_Fichiers": types.SimpleNamespace(
                GetRepTemp=lambda fichier: str(rep / fichier),
                GetRepData=lambda fichier="": str(rep_data / fichier) if fichier else str(rep_data),
            ),
            "GetListeFichiersReseau": lambda _connection: ([] if base_interdite else ["base_fictive"]),
            "GetRepertoireMySQL": lambda _connection: str(rep) + os.sep,
            "CreationFichierLoginTemp": lambda **kwargs: None,
        }
        arbre = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
        fonctions = [noeud for noeud in arbre.body
                     if isinstance(noeud, ast.FunctionDef) and noeud.name in FONCTIONS_RESTAURATION]
        self.assertEqual(len(fonctions), len(FONCTIONS_RESTAURATION))
        exec(compile(ast.fix_missing_locations(ast.Module(body=fonctions, type_ignores=[])),
                     str(SOURCE), "exec"), deps)
        self.faux = faux
        self.rep_data = rep_data
        return deps["Restauration"](
            fichier=str(archive), listeFichiersLocaux=list(locaux), listeFichiersReseau=list(reseau),
            dictConnexion={"port": "3308", "host": "127.0.0.1", "user": "faux", "password": "faux"},
        )

    @staticmethod
    def _archive(rep, sql, nom="temoin.nod", locaux=None):
        archive = rep / nom
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("base_fictive.sql", sql)
            for nom_local, contenu in (locaux or {}).items():
                z.writestr(nom_local, contenu)
        return archive

    def test_manifeste_invalide_refuse_avant_sql(self):
        with tempfile.TemporaryDirectory(prefix="noe032-manifest-invalide-") as dossier:
            rep = Path(dossier)
            archive = self._archive(rep, b"-- NOETHYS-SQL-MANIFEST-V1 " + b"a" * 32 + b"\nCREATE TABLE faux (id INT);\n")
            resultat = self._executer(archive, rep, processus_interdit=True, base_interdite=True)
            self.assertIs(resultat, False)
            self.assertTrue(archive.exists())
            self.assertFalse((rep / "restoretemp").exists())

    def test_ancien_dump_tronque_refuse_avant_sql(self):
        with tempfile.TemporaryDirectory(prefix="noe032-analyse-tronque-") as dossier:
            rep = Path(dossier)
            archive = self._archive(rep, b"CREATE TABLE fictive (id INT);\nINSERT INTO fictive VALUES (1),(")
            resultat = self._executer(archive, rep, processus_interdit=True, base_interdite=True)
            self.assertIs(resultat, False)
            self.assertTrue(archive.exists())
            self.assertFalse((rep / "restoretemp").exists())

    def test_ancien_dump_coupe_entre_deux_instructions_refuse_avant_sql(self):
        # Coupure en frontiere : syntaxe valide, mais ligne finale mysqldump absente.
        with tempfile.TemporaryDirectory(prefix="noe032-fin-absente-") as dossier:
            rep = Path(dossier)
            archive = self._archive(rep, b"CREATE TABLE fictive (id INT);\nINSERT INTO fictive VALUES (1);\n")
            resultat = self._executer(archive, rep, processus_interdit=True, base_interdite=True)
            self.assertIs(resultat, False)
            self.assertIn("Dump completed", "\n".join(_Dialogue.messages))
            self.assertFalse((rep / "restoretemp").exists())

    def test_dump_sans_objet_restaurable_refuse_avant_sql(self):
        with tempfile.TemporaryDirectory(prefix="noe032-analyse-noop-") as dossier:
            rep = Path(dossier)
            archive = self._archive(rep, b"-- vide\nSELECT 1;\n" + FIN)
            resultat = self._executer(archive, rep, processus_interdit=True, base_interdite=True)
            self.assertIs(resultat, False)
            self.assertFalse((rep / "restoretemp").exists())

    def test_ancien_dump_sans_manifeste_reste_lisible(self):
        with tempfile.TemporaryDirectory(prefix="noe032-manifest-ancien-") as dossier:
            rep = Path(dossier)
            archive = self._archive(rep, b"CREATE TABLE fictive (id INT);\n" + FIN, nom="ancien.nod")
            resultat = self._executer(archive, rep)
            self.assertEqual(resultat, ["base_fictive"])
            self.assertFalse((rep / "restoretemp").exists())
            self.assertIn("-- NOETHYS-RESTORE-END-V1", self.faux.imports[0])
            self.assertIsNone(self.faux.marqueur, "Marqueur terminal laisse en base")
            self.assertEqual(self.faux.connexions_ouvertes, 0)

    def test_dump_avec_manifeste_sans_ligne_finale_accepte(self):
        # --compact (option Customize) : le manifeste SHA-256 suffit a prouver la completude.
        with tempfile.TemporaryDirectory(prefix="noe032-manifest-compact-") as dossier:
            rep = Path(dossier)
            dump = rep / "source.sql"
            dump.write_bytes(b"CREATE TABLE fictive (id INT);\nINSERT INTO fictive VALUES (1);\n")
            _charger_manifeste().AjouterManifesteIntegriteSQL(str(dump))
            archive = self._archive(rep, dump.read_bytes())
            self.assertEqual(self._executer(archive, rep), ["base_fictive"])

    def test_marqueur_non_execute_refuse_et_nettoye(self):
        with tempfile.TemporaryDirectory(prefix="noe032-marqueur-") as dossier:
            rep = Path(dossier)
            archive = self._archive(rep, b"CREATE TABLE fictive (id INT);\n" + FIN)
            faux = _FauxMySQL(mode="marqueur_non_execute")
            resultat = self._executer(archive, rep, faux=faux)
            self.assertIs(resultat, False)
            self.assertIn("marqueur terminal", "\n".join(_Dialogue.messages))
            self.assertGreaterEqual(faux.suppressions_marqueur, 1)
            self.assertFalse((rep / "restoretemp").exists())

    def test_objet_attendu_absent_refuse_et_nettoye(self):
        with tempfile.TemporaryDirectory(prefix="noe032-objet-") as dossier:
            rep = Path(dossier)
            archive = self._archive(
                rep, b"CREATE TABLE alpha (id INT);\nCREATE TABLE beta (id INT);\n" + FIN)
            faux = _FauxMySQL(mode="objet_manquant")
            resultat = self._executer(archive, rep, faux=faux)
            self.assertIs(resultat, False)
            self.assertIn("alpha", "\n".join(_Dialogue.messages))
            self.assertIsNone(faux.marqueur, "Marqueur terminal laisse en base")

    def test_echec_mysql_nettoie_aussi_le_marqueur(self):
        with tempfile.TemporaryDirectory(prefix="noe032-echec-mysql-") as dossier:
            rep = Path(dossier)
            archive = self._archive(rep, b"CREATE TABLE fictive (id INT);\n" + FIN)
            faux = _FauxMySQL(code_retour=1)
            resultat = self._executer(archive, rep, faux=faux)
            self.assertIs(resultat, False)
            self.assertGreaterEqual(faux.suppressions_marqueur, 1)
            self.assertEqual(faux.connexions_ouvertes, 0)

    def test_restauration_mixte_dump_invalide_ne_touche_pas_sqlite(self):
        with tempfile.TemporaryDirectory(prefix="noe032-mixte-") as dossier:
            rep = Path(dossier)
            archive = self._archive(rep, b"CREATE TABLE fictive (id INT);\nINSERT INTO",
                                    locaux={"local_DATA.dat": b"SQLite format 3\x00fictif"})
            resultat = self._executer(archive, rep, processus_interdit=True, base_interdite=True,
                                      locaux=["local_DATA.dat"])
            self.assertIs(resultat, False)
            self.assertFalse((self.rep_data / "local_DATA.dat").exists(),
                             "Fichier Sqlite remplace avant le controle du dump MySQL")
            self.assertIn("aucune donnée n'a été modifiée", "\n".join(_Dialogue.messages))

    def test_restauration_mixte_membre_local_corrompu_ne_touche_rien(self):
        with tempfile.TemporaryDirectory(prefix="noe032-mixte-crc-") as dossier:
            rep = Path(dossier)
            archive = self._archive(rep, b"CREATE TABLE fictive (id INT);\n" + FIN,
                                    locaux={"local_DATA.dat": b"A" * 4096})
            # Corruption d'un octet des donnees compressees -> CRC invalide.
            brut = bytearray(archive.read_bytes())
            position = brut.index(b"A" * 64)
            brut[position] = ord("B")
            archive.write_bytes(bytes(brut))
            resultat = self._executer(archive, rep, processus_interdit=True, base_interdite=True,
                                      locaux=["local_DATA.dat"])
            self.assertIs(resultat, False)
            self.assertFalse((self.rep_data / "local_DATA.dat").exists())
            self.assertFalse((rep / "restoretemp").exists())

    def test_restauration_mixte_valide_restaure_les_deux(self):
        with tempfile.TemporaryDirectory(prefix="noe032-mixte-ok-") as dossier:
            rep = Path(dossier)
            archive = self._archive(rep, b"CREATE TABLE fictive (id INT);\n" + FIN,
                                    locaux={"local_DATA.dat": b"SQLite format 3\x00fictif"})
            resultat = self._executer(archive, rep, locaux=["local_DATA.dat"])
            self.assertEqual(resultat, ["local_DATA", "base_fictive"])
            self.assertTrue((self.rep_data / "local_DATA.dat").exists())

    def test_sauvegarde_reseau_produit_un_manifeste_valide(self):
        with tempfile.TemporaryDirectory(prefix="noe032-save-manifest-") as dossier:
            rep = Path(dossier)
            sortie = rep / "sortie"
            sortie.mkdir()

            class Processus:
                returncode = 0

                def communicate(self):
                    return b"", None

            def popen(commande, **kwargs):
                chemin = re.search(r'>\s*"([^"]+)"', commande).group(1)
                Path(chemin).write_bytes(b"CREATE TABLE test_synth (id INT);\n")
                return Processus()

            wx = types.SimpleNamespace(
                MessageDialog=_Dialogue, ProgressDialog=_Progression,
                OK=0, ICON_ERROR=0, PD_SMOOTH=0, PD_AUTO_HIDE=0, PD_APP_MODAL=0,
            )
            deps = {
                "zipfile": zipfile, "os": os, "shutil": shutil,
                "wx": wx, "_": lambda texte: texte,
                "six": types.SimpleNamespace(PY2=False, PY3=True),
                "subprocess": types.SimpleNamespace(Popen=popen, PIPE=-1, STDOUT=-2),
                "UTILS_SQL_Integrite": _charger_manifeste(),
                "UTILS_Customize": types.SimpleNamespace(GetValeur=lambda *args, **kwargs: ""),
                "UTILS_Envoi_email": types.SimpleNamespace(Message=lambda **kwargs: kwargs),
                "UTILS_Fichiers": types.SimpleNamespace(GetRepTemp=lambda fichier: str(rep / fichier)),
                "GetRepertoireMySQL": lambda _connection: str(rep) + os.sep,
                "CreationFichierLoginTemp": lambda **kwargs: None,
                "EXTENSIONS": {"decrypte": "nod", "crypte": "noc"},
            }
            arbre = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
            fonction = next(noeud for noeud in arbre.body
                            if isinstance(noeud, ast.FunctionDef) and noeud.name == "Sauvegarde")
            exec(compile(ast.fix_missing_locations(ast.Module(body=[fonction], type_ignores=[])),
                         str(SOURCE), "exec"), deps)
            resultat = deps["Sauvegarde"](
                listeFichiersReseau=["base_fictive"], nom="essai", repertoire=str(sortie),
                dictConnexion={"port": "3308", "host": "127.0.0.1", "user": "faux", "password": "faux"},
            )
            self.assertTrue(resultat)
            archive = sortie / "essai.nod"
            self.assertTrue(archive.exists())
            with zipfile.ZipFile(archive, "r") as z:
                sql = z.read("base_fictive.sql")
            self.assertTrue(sql.startswith(b"-- NOETHYS-SQL-MANIFEST-V1 "))
            fichier_sql = rep / "resultat.sql"
            fichier_sql.write_bytes(sql)
            self.assertEqual(_charger_manifeste().VerifierIntegriteSQL(fichier_sql), (True, None))
            self.assertFalse((rep / "savetemp").exists())


if __name__ == "__main__":
    unittest.main()
