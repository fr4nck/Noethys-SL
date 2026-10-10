# -*- coding: utf-8 -*-
"""Noe-032 : restauration reseau sans connexion refusee avant extraction.

Fonction isolee par AST ; archive de test simulee ; aucun profil wx ni acces DB.
"""
import ast
import os
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Sauvegarde.py"


class ArchiveTemoin:
    derniere = None

    def __init__(self, *args, **kwargs):
        self.fermee = False
        self.extractions = []
        ArchiveTemoin.derniere = self

    def close(self):
        self.fermee = True

    def extract(self, *args, **kwargs):
        self.extractions.append(args)
        raise OSError("Echec de lecture simule")


class FauxZip:
    ZipFile = ArchiveTemoin


def _charger_restauration_isolee(dependances=None):
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    fonction = next(n for n in arbre.body
                    if isinstance(n, ast.FunctionDef) and n.name == "Restauration")
    module = ast.Module(body=[fonction], type_ignores=[])
    namespace = {"zipfile": FauxZip, "os": os}
    namespace.update(dependances or {})
    exec(compile(ast.fix_missing_locations(module), str(SOURCE), "exec"), namespace)
    return namespace["Restauration"]


class RestaurationReseauSansConnexionTests(unittest.TestCase):
    def setUp(self):
        ArchiveTemoin.derniere = None

    def _verifier_refus(self, locaux):
        restauration = _charger_restauration_isolee()
        self.assertIs(restauration(
            fichier="archive-fictive.nod", listeFichiersLocaux=locaux,
            listeFichiersReseau=["base-fictive"], dictConnexion=None), False)
        self.assertIsNotNone(ArchiveTemoin.derniere)
        self.assertTrue(ArchiveTemoin.derniere.fermee, "Archive non fermee")
        self.assertEqual(ArchiveTemoin.derniere.extractions, [])

    def test_reseau_seul_refuse_sans_connexion_et_ferme_archive(self):
        self._verifier_refus([])

    def test_mixte_refuse_avant_extraction_locale(self):
        self._verifier_refus(["local-fictif.dat"])

    def test_local_seul_conserve_son_parcours(self):
        class ParcoursLocalAtteint(Exception):
            pass

        class FichiersFictifs:
            @staticmethod
            def GetRepData(*args, **kwargs):
                raise ParcoursLocalAtteint()

        restauration = _charger_restauration_isolee({
            "UTILS_Fichiers": FichiersFictifs,
        })
        with self.assertRaises(ParcoursLocalAtteint):
            restauration(fichier="archive-fictive.nod",
                         listeFichiersLocaux=["local-fictif.dat"],
                         listeFichiersReseau=[], dictConnexion=None)


class RestaurationArchiveCleanupTests(unittest.TestCase):
    """Branches de sortie avant import SQL, sur archives et dependances fictives."""

    class Dialogue:
        def __init__(self, *args, **kwargs):
            pass

        def ShowModal(self):
            return 5104  # annulation, jamais confirmation

        def Destroy(self):
            pass

    class Progression:
        def __init__(self, *args, **kwargs):
            pass

        def Update(self, *args, **kwargs):
            return True

        def Destroy(self):
            pass

    class Wx:
        ID_YES = 5103
        YES_NO = CANCEL = NO_DEFAULT = ICON_EXCLAMATION = 0
        OK = ICON_ERROR = PD_SMOOTH = PD_AUTO_HIDE = PD_APP_MODAL = 0
        MessageDialog = None
        ProgressDialog = None

    class Fichiers:
        @staticmethod
        def GetRepData(nom=None):
            return "chemin-fictif/" + (nom or "")

    class CheminExiste:
        @staticmethod
        def isfile(chemin):
            return True

    class CheminAbsent:
        @staticmethod
        def isfile(chemin):
            return False

    class OsExiste:
        path = None

    class OsAbsent:
        path = None

    def setUp(self):
        ArchiveTemoin.derniere = None
        self.Wx.MessageDialog = self.Dialogue
        self.Wx.ProgressDialog = self.Progression
        self.OsExiste.path = self.CheminExiste
        self.OsAbsent.path = self.CheminAbsent

    def _restauration(self, os_fictif, **dependances):
        environnement = {
            "wx": self.Wx,
            "_": lambda texte: texte,
            "os": os_fictif,
            "UTILS_Fichiers": self.Fichiers,
        }
        environnement.update(dependances)
        return _charger_restauration_isolee(environnement)

    def _controle_zip_ferme(self):
        self.assertIsNotNone(ArchiveTemoin.derniere)
        self.assertTrue(ArchiveTemoin.derniere.fermee, "ZIP laisse ouvert")

    def test_annulation_remplacement_local_ferme_zip(self):
        restauration = self._restauration(self.OsExiste)
        resultat = restauration(fichier="archive-fictive.nod",
                               listeFichiersLocaux=["fichier-fictif.dat"])
        self.assertIs(resultat, False)
        self._controle_zip_ferme()
        self.assertEqual(ArchiveTemoin.derniere.extractions, [])

    def test_erreur_extraction_locale_ferme_zip(self):
        restauration = self._restauration(self.OsAbsent)
        resultat = restauration(fichier="archive-fictive.nod",
                               listeFichiersLocaux=["fichier-fictif.dat"])
        self.assertIs(resultat, False)
        self._controle_zip_ferme()
        self.assertEqual(len(ArchiveTemoin.derniere.extractions), 1)

    def test_client_mysql_introuvable_ferme_zip(self):
        restauration = self._restauration(
            self.OsAbsent,
            GetListeFichiersReseau=lambda _connexion: [],
            GetRepertoireMySQL=lambda _connexion: None,
        )
        resultat = restauration(
            fichier="archive-fictive.nod",
            listeFichiersReseau=["base-fictive"],
            dictConnexion={"hote": "fictif.invalid"},
        )
        self.assertIs(resultat, False)
        self._controle_zip_ferme()
        self.assertEqual(ArchiveTemoin.derniere.extractions, [])

    def test_annulation_remplacement_reseau_ferme_zip(self):
        restauration = self._restauration(
            self.OsAbsent,
            GetListeFichiersReseau=lambda _connexion: ["base-fictive"],
            GetRepertoireMySQL=lambda _connexion: "/mysql-fictif/",
        )
        resultat = restauration(
            fichier="archive-fictive.nod",
            listeFichiersReseau=["base-fictive.sql"],
            dictConnexion={"hote": "fictif.invalid"},
        )
        self.assertIs(resultat, False)
        self._controle_zip_ferme()
        self.assertEqual(ArchiveTemoin.derniere.extractions, [])

    def test_tous_les_refus_explicitent_la_fermeture_du_zip(self):
        arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
        fonction = next(n for n in arbre.body
                        if isinstance(n, ast.FunctionDef)
                        and n.name == "Restauration")
        gardes = []
        for noeud in ast.walk(fonction):
            for _champ, valeur in ast.iter_fields(noeud):
                if not isinstance(valeur, list):
                    continue
                for i, instruction in enumerate(valeur):
                    if (isinstance(instruction, ast.Return)
                            and isinstance(instruction.value, ast.Constant)
                            and instruction.value.value is False):
                        gardes.append((instruction.lineno,
                                       valeur[i - 1] if i else None))
        self.assertEqual(len(gardes), 6, "Verifier les nouvelles sorties anticipées")
        for ligne, precedente in gardes:
            self.assertIsInstance(precedente, ast.Expr, "Retour ligne %s" % ligne)
            self.assertEqual(ast.unparse(precedente), "fichierZip.close()",
                             "Fuite potentielle du ZIP ligne %s" % ligne)


if __name__ == "__main__":
    unittest.main()
