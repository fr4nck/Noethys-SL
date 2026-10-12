# -*- coding: utf-8 -*-
"""Config.json illisible : recuperation du .bak et quarantaine, jamais d'ecrasement silencieux.

Repris de agent/windows11-pyinstaller (cb646889). Fichiers temporaires
uniquement ; profil isole par la garde reseau.
"""
import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import json  # noqa: E402
import os  # noqa: E402
import tempfile  # noqa: E402
import unittest  # noqa: E402
from pathlib import Path  # noqa: E402

from Utils import UTILS_Config  # noqa: E402


class QuarantaineConfigTests(unittest.TestCase):
    def setUp(self):
        self._dossier = tempfile.TemporaryDirectory(prefix="noethys-config-")
        self.rep = Path(self._dossier.name)
        self.config = UTILS_Config.FichierConfig()
        self.config.nomFichier = str(self.rep / "Config.json")

    def tearDown(self):
        self._dossier.cleanup()

    def _quarantaines(self):
        return sorted(p for p in self.rep.iterdir() if ".corrupt-" in p.name)

    def test_config_valide_lue_sans_quarantaine(self):
        Path(self.config.nomFichier).write_text(json.dumps({"nomFichier": "Fictif"}), encoding="utf-8")
        self.assertEqual(self.config.GetDictConfig(), {"nomFichier": "Fictif"})
        self.assertEqual(self._quarantaines(), [])

    def test_premier_demarrage_sans_fichier(self):
        self.assertEqual(self.config.GetDictConfig(), {})
        self.assertEqual(self._quarantaines(), [])

    def test_config_corrompue_sans_bak_mise_en_quarantaine(self):
        Path(self.config.nomFichier).write_text("{ illisible", encoding="utf-8")
        self.assertEqual(self.config.GetDictConfig(), {})
        quarantaines = self._quarantaines()
        self.assertEqual(len(quarantaines), 1)
        self.assertEqual(quarantaines[0].read_text(encoding="utf-8"), "{ illisible")
        self.assertFalse(os.path.exists(self.config.nomFichier))

    def test_config_corrompue_restauree_depuis_bak_valide(self):
        Path(self.config.nomFichier).write_text("{ illisible", encoding="utf-8")
        Path(self.config.nomFichier + ".bak").write_text(json.dumps({"nomFichier": "Sauvegarde"}), encoding="utf-8")
        self.assertEqual(self.config.GetDictConfig(), {"nomFichier": "Sauvegarde"})
        self.assertEqual(len(self._quarantaines()), 1)
        self.assertEqual(json.loads(Path(self.config.nomFichier).read_text(encoding="utf-8")),
                         {"nomFichier": "Sauvegarde"})

    def test_json_qui_n_est_pas_un_dictionnaire_traite_comme_corrompu(self):
        Path(self.config.nomFichier).write_text(json.dumps(["liste"]), encoding="utf-8")
        self.assertEqual(self.config.GetDictConfig(), {})
        self.assertEqual(len(self._quarantaines()), 1)


if __name__ == "__main__":
    unittest.main()
