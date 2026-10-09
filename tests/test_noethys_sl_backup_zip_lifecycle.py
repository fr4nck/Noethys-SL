# -*- coding: utf-8 -*-
"""Régression : l'énumération d'un fichier NOD ne laisse pas de ZIP ouvert.

Fonction historique chargée isolément via AST : pas de profil Noethys, wx ni DB.
"""
import ast
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Sauvegarde.py"


def _charger_enumeration():
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    fonction = next(noeud for noeud in arbre.body
                    if isinstance(noeud, ast.FunctionDef)
                    and noeud.name == "GetListeFichiersZIP")
    isolat = ast.Module(body=[fonction], type_ignores=[])
    namespace = {"zipfile": zipfile}
    exec(compile(ast.fix_missing_locations(isolat), str(SOURCE), "exec"), namespace)
    return namespace["GetListeFichiersZIP"]


class ListeFichiersZipLifecycleTests(unittest.TestCase):
    def test_archive_est_fermee_apres_enumeration(self):
        class ZipControle(zipfile.ZipFile):
            ouvertes = []

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.ouvertes.append(self)

        with tempfile.TemporaryDirectory(prefix="noethys-test-zip-") as dossier:
            archive = Path(dossier) / "temoin.nod"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("fichier1.dat", "fictif")
                z.writestr("fichier2.sql", "donnees fictives")
            with mock.patch.object(zipfile, "ZipFile", ZipControle):
                noms = _charger_enumeration()(str(archive))
            self.assertEqual(noms, ["fichier1.dat", "fichier2.sql"])
            self.assertEqual(len(ZipControle.ouvertes), 1)
            self.assertIsNone(ZipControle.ouvertes[0].fp, "ZIP non ferme")


if __name__ == "__main__":
    unittest.main()
