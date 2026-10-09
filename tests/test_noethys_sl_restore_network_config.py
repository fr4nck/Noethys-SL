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
        raise AssertionError("Aucune extraction ne doit etre realisee")


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


if __name__ == "__main__":
    unittest.main()
