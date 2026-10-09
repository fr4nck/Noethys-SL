# -*- coding: utf-8 -*-
"""Noe-032 : garde de sauvegarde reseau sans connexion, sans base ni GUI.

La fonction Sauvegarde est extraite par AST : aucun import wx/GestionDB,
aucun profil de production, aucune creation de fichier.
"""
import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Sauvegarde.py"


def _charger_sauvegarde_isolee(dependances=None):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    fonction = next(n for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == "Sauvegarde")
    module = ast.Module(body=[fonction], type_ignores=[])
    namespace = {} if dependances is None else dict(dependances)
    exec(compile(ast.fix_missing_locations(module), str(SOURCE), "exec"), namespace)
    return namespace["Sauvegarde"]


class BackupNetworkConfigTests(unittest.TestCase):
    def test_reseau_seul_sans_connexion_refuse_avant_toute_action(self):
        sauvegarde = _charger_sauvegarde_isolee()
        self.assertIs(sauvegarde(listeFichiersReseau=["base_fictive"],
                                 dictConnexion=None), False)

    def test_mixte_sans_connexion_refuse_archive_partielle(self):
        sauvegarde = _charger_sauvegarde_isolee()
        self.assertIs(sauvegarde(listeFichiersLocaux=["fichier_fictif.dat"],
                                 listeFichiersReseau=["base_fictive"],
                                 dictConnexion=None), False)

    def test_local_seul_conserve_le_parcours_de_sauvegarde(self):
        class ProgressionAtteinte(Exception):
            pass

        class FauxWx:
            PD_SMOOTH = 0
            PD_AUTO_HIDE = 0
            PD_APP_MODAL = 0

            @staticmethod
            def ProgressDialog(*args, **kwargs):
                raise ProgressionAtteinte()

        sauvegarde = _charger_sauvegarde_isolee({
            "wx": FauxWx,
            "_": lambda valeur: valeur,
            "EXTENSIONS": {"decrypte": "nod", "crypte": "noc"},
        })
        # Le parcours local atteint l'ouverture du dialogue, sans ecrire de ZIP.
        with self.assertRaises(ProgressionAtteinte):
            sauvegarde(listeFichiersLocaux=["fichier_fictif.dat"],
                       listeFichiersReseau=[], dictConnexion=None)


if __name__ == "__main__":
    unittest.main()
