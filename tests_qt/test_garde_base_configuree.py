"""Garde Noethys-SL du prototype Qt : la base configurée dans Noethys (peut-être
la production) n'est jamais ouverte sans autorisation explicite.

Aucune QApplication n'est créée : aucun widget, aucune fenêtre.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from noethys_qt import activities_native, activities_prototype
from noethys_qt.activity_editor import NativeActivityEditorRepository

VARIABLE = activities_prototype.AUTORISATION_BASE_CONFIGUREE


def _sans_autorisation():
    environ = {k: v for k, v in os.environ.items() if k != VARIABLE}
    return mock.patch.dict(os.environ, environ, clear=True)


class GardeBaseConfigureeTests(unittest.TestCase):
    def test_configuration_jamais_lue_sans_autorisation(self):
        with _sans_autorisation(), mock.patch.object(
            activities_native, "_user_config_dir", side_effect=AssertionError("Config.json lu")
        ):
            with self.assertRaises(RuntimeError) as ctx:
                activities_native._load_config()
        self.assertIn("--sqlite", str(ctx.exception))

    def test_autorisation_differente_de_1_refusee(self):
        with mock.patch.dict(os.environ, {VARIABLE: "oui"}):
            with self.assertRaises(RuntimeError):
                activities_prototype.VerifierAccesBaseConfiguree()

    def test_lecture_historique_gestiondb_refusee_avant_tout_import(self):
        with _sans_autorisation(), mock.patch.object(activities_prototype.sys, "path", []) as chemin:
            with self.assertRaises(RuntimeError):
                activities_prototype.LegacyNoethysActivityRepository().fetch()
        self.assertEqual(chemin, [])  # noethys/ jamais ajouté au chemin d'import

    def test_editeur_sans_copie_sqlite_refuse(self):
        with _sans_autorisation():
            with self.assertRaises(RuntimeError):
                NativeActivityEditorRepository(None)._connect()

    def test_copie_sqlite_explicite_toujours_permise(self):
        with tempfile.TemporaryDirectory() as dossier, _sans_autorisation():
            chemin = Path(dossier) / "copie_DATA.dat"
            sqlite3.connect(chemin).close()
            connexion, marque = NativeActivityEditorRepository(chemin)._connect()
            connexion.close()
        self.assertEqual(marque, "?")

    def test_autorisation_explicite_lit_la_configuration(self):
        with tempfile.TemporaryDirectory() as dossier:
            Path(dossier, "Config.json").write_text(json.dumps({"nomFichier": "Fictif"}), encoding="utf-8")
            with mock.patch.dict(os.environ, {VARIABLE: "1"}), mock.patch.object(
                activities_native, "_user_config_dir", return_value=Path(dossier)
            ):
                self.assertEqual(activities_native._load_config(), {"nomFichier": "Fictif"})


if __name__ == "__main__":
    unittest.main()
