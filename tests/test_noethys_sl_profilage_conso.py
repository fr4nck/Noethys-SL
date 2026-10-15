# -*- coding: utf-8 -*-
"""Issue #427 : aucun journal par defaut ; opt-in local sans donnee familiale."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"
if str(NOETHYS) not in sys.path:
    sys.path.insert(0, str(NOETHYS))

from Utils import UTILS_Profilage_consos as profiler  # noqa: E402


class ProfilageConsommationsTests(unittest.TestCase):
    def test_desactive_aucune_ecriture(self):
        with tempfile.TemporaryDirectory() as racine:
            with patch.dict(os.environ, {"LOCALAPPDATA": racine,
                                          "NOETHYS_SL_PROFILE_CONSOS": "0"}):
                with profiler.SuiviValidation() as suivi:
                    with suivi.etape("consommations"):
                        pass
                self.assertFalse(profiler.CheminJournal().exists())

    def test_optin_journalise_les_phases_sans_donnees_privees(self):
        with tempfile.TemporaryDirectory() as racine:
            with patch.dict(os.environ, {"LOCALAPPDATA": racine,
                                          "NOETHYS_SL_PROFILE_CONSOS": "1"}):
                with profiler.SuiviValidation() as suivi:
                    with suivi.etape("consommations"):
                        sum(range(500))
                    with suivi.etape("transports"):
                        pass
                chemin = profiler.CheminJournal()
                self.assertTrue(chemin.is_file())
                texte = chemin.read_text(encoding="utf-8")
                ligne = json.loads(texte.strip())
                self.assertTrue(ligne["termine_sans_exception"])
                self.assertGreaterEqual(ligne["duree_ms"], 0)
                self.assertEqual([phase["phase"] for phase in ligne["etapes"]],
                                 ["consommations", "transports"])
                self.assertTrue(ligne["fonctions"])
                self.assertNotIn(str(racine), texte, "Chemin complet utilisateur interdit")
                self.assertNotIn("IDfamille", texte)
                self.assertNotIn("requete_sql", texte)

    def test_exception_journalisee_sans_message_ni_masquage(self):
        with tempfile.TemporaryDirectory() as racine:
            with patch.dict(os.environ, {"LOCALAPPDATA": racine,
                                          "NOETHYS_SL_PROFILE_CONSOS": "1"}):
                with self.assertRaisesRegex(RuntimeError, "SECRET_DU_TEST"):
                    with profiler.SuiviValidation() as suivi:
                        with suivi.etape("consommations"):
                            raise RuntimeError("SECRET_DU_TEST")
                texte = profiler.CheminJournal().read_text(encoding="utf-8")
                self.assertFalse(json.loads(texte.strip())["termine_sans_exception"])
                self.assertNotIn("SECRET_DU_TEST", texte)

    def test_handlers_couvrent_toutes_les_phases(self):
        for module in ("DLG_Grille.py", "DLG_Gestionnaire_conso.py"):
            source = (NOETHYS / "Dlg" / module).read_text(encoding="utf-8")
            corps = source.split("    def OnBoutonOk(self, event):", 1)[1].split(
                "    def OnBouton", 1)[0]
            self.assertIn("UTILS_Profilage_consos.SuiviValidation()", corps)
            for phase in ("consommations", "transports", "parametres", "fermeture"):
                self.assertIn('mesure.etape("%s")' % phase, corps)


if __name__ == "__main__":
    unittest.main()
