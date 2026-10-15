# -*- coding: utf-8 -*-
"""Issue #428 : la cle de repertoire PDF doit survivre a wx.PropertyGrid.

Reproduction du défaut sur wxPython Phoenix : DirProperty(name=<texte UI>,
label="repertoire_copie") provoquait un KeyError dans les deux handlers
de factures. Test sur vrai PropertyGrid wx, sans connexion ni envoi d'email.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
NOETHYS = ROOT / "noethys"
for p in (TESTS, NOETHYS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import _garde_reseau  # noqa: F401,E402 -- interdit toute connexion reseau
import wx  # noqa: E402

_APP = wx.App(False)

from Ctrl import CTRL_Factures_options  # noqa: E402
from Dlg import DLG_Factures_email, DLG_Factures_impression  # noqa: E402
from Utils import UTILS_Facturation  # noqa: E402


class ExportOptionsFacturesTests(unittest.TestCase):
    def setUp(self):
        self.frame = wx.Frame(None)
        # Le modele, les preferences de la base et les destinataires ne
        # sont pas necessaires pour controler le contrat du PropertyGrid.
        with patch.object(CTRL_Factures_options.CTRL_Parametres, "MAJ_modeles"), \
                patch.object(CTRL_Factures_options.CTRL_Parametres, "Importation"):
            self.ctrl = CTRL_Factures_options.CTRL_Parametres(self.frame)

    def tearDown(self):
        self.frame.Destroy()

    def test_nom_stable_et_libelle_traduit(self):
        valeurs = self.ctrl.GetValeurs()
        self.assertIn("repertoire_copie", valeurs)
        self.assertEqual(valeurs["repertoire_copie"], "")
        propriete = self.ctrl.GetPropertyByName("repertoire_copie")
        self.assertIsNotNone(propriete)
        self.assertEqual(propriete.GetLabel(), "Répertoire pour copie unique")
        self.assertNotIn("Répertoire pour copie unique", valeurs)

    def test_apercu_passe_le_repertoire_sans_keyerror(self):
        options = self.ctrl.GetValeurs()
        selection = SimpleNamespace(IDfacture=1, etat="emission")
        dialogue = SimpleNamespace(
            ctrl_liste_factures=SimpleNamespace(GetTracksCoches=lambda: [selection]),
            ctrl_options=SimpleNamespace(GetOptions=lambda: options),
        )
        with patch.object(UTILS_Facturation, "Facturation") as classe:
            classe.return_value.Impression.return_value = False
            DLG_Factures_impression.Dialog.OnBoutonApercu(dialogue, None)
            kwargs = classe.return_value.Impression.call_args.kwargs
            self.assertEqual(kwargs["listeFactures"], [1])
            self.assertEqual(kwargs["repertoire"], "")

    def test_transfert_email_prepare_le_pdf_sans_envoi(self):
        options = self.ctrl.GetValeurs()
        selection = SimpleNamespace(IDfacture=1, etat="emission")
        dialogue = SimpleNamespace(
            ctrl_liste_factures=SimpleNamespace(GetTracksCoches=lambda: [selection]),
            ctrl_options=SimpleNamespace(GetOptions=lambda: options),
        )
        # Impression retourne False avant toute resolution d'adresse ou
        # ouverture du mailer. Aucun email ni PDF n'est emis par ce test.
        with patch.object(UTILS_Facturation, "Facturation") as classe:
            classe.return_value.Impression.return_value = False
            DLG_Factures_email.Dialog.OnBoutonOk(dialogue, None)
            kwargs = classe.return_value.Impression.call_args.kwargs
            self.assertEqual(kwargs["listeFactures"], [1])
            self.assertEqual(kwargs["repertoire"], "")
            self.assertIs(kwargs["repertoireTemp"], True)


if __name__ == "__main__":
    unittest.main()
