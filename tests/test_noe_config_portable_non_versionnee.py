# -*- coding: utf-8 -*-
"""Garde : aucun Config.json de profil Portable ne doit être versionné.

Ce fichier contient les paramètres de connexion (identifiants MySQL compris).
Voir docs/incidents/2026-10-14-identifiants-mysql-portable.md.
Le test ne lit jamais le contenu des fichiers : seulement l'index Git.
"""
import os
import shutil
import subprocess
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(*args):
    return subprocess.run(["git", "-C", RACINE] + list(args),
                          capture_output=True, text=True, check=False)


@unittest.skipUnless(shutil.which("git") and os.path.isdir(os.path.join(RACINE, ".git")),
                     "dépôt Git indisponible")
class ConfigPortableNonVersionneeTests(unittest.TestCase):

    def test_aucun_config_json_portable_suivi(self):
        suivis = _git("ls-files").stdout.splitlines()
        fautifs = [f for f in suivis
                   if "/Portable/" in "/" + f and os.path.basename(f).startswith("Config.json")]
        self.assertEqual(fautifs, [])

    def test_gitignore_exclut_config_portable(self):
        for chemin in ("noethys/Portable/Config.json", "noethys/Portable/Config.json.bak"):
            self.assertEqual(_git("check-ignore", "-q", "--no-index", chemin).returncode, 0, chemin)


if __name__ == "__main__":
    unittest.main()
