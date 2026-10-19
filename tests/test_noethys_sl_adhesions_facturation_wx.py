# -*- coding: utf-8 -*-
"""P1 #426: recette wx de la preparation avant apercu, sans base ni email."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
import wx

from Dlg import DLG_Factures_generation as UI
from Utils import UTILS_Adhesions_echeances as E
from Utils import UTILS_Identification


def params(prestations=None):
    return dict(date_debut="2026-09-01", date_fin="2026-09-30",
                date_anterieure=None, listeActivites=[1, 2],
                IDcompte_payeur=None,
                prestations=["consommation", "cotisation"] if prestations is None else prestations)


class FacturationP1WxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.GetApp() or wx.App(False)

    def fake(self, prestations=None):
        return SimpleNamespace(dictParametres=params(prestations))

    def test_prestations_hors_cotisation_ne_declenchent_rien(self):
        with patch.object(E, "Proposer") as proposer:
            self.assertTrue(UI.Dialog.PreparerCotisationsPourApercu(
                self.fake(["consommation"])))
            proposer.assert_not_called()

    def test_creation_uniquement_apres_confirmation_et_avant_apercu(self):
        prop = {"date_debut": "2026-09-01", "date_fin": "2026-09-30",
                "date_reference": "2026-10-19",
                "propositions": [{"montant": 7.5}], "a_verifier": []}
        with patch.object(E, "Proposer", return_value=prop) as proposer, \
                patch.object(E, "Executer", return_value=[{"statut": "cree"}]) as executer, \
                patch.object(UTILS_Identification, "GetIDutilisateur", return_value=91), \
                patch.object(wx, "MessageBox", return_value=wx.YES):
            self.assertTrue(UI.Dialog.PreparerCotisationsPourApercu(self.fake()))
            proposer.assert_called_once()
            self.assertEqual(executer.call_args.kwargs["confirmation"], True)
            self.assertEqual(executer.call_args.kwargs["IDutilisateur"], 91)

    def test_non_explicite_ne_cree_jamais(self):
        prop = {"propositions": [{"montant": 7.5}], "a_verifier": []}
        with patch.object(E, "Proposer", return_value=prop), \
                patch.object(E, "Executer") as executer, \
                patch.object(wx, "MessageBox", return_value=wx.NO):
            self.assertTrue(UI.Dialog.PreparerCotisationsPourApercu(self.fake()))
            executer.assert_not_called()

    def test_anomalie_bloque_les_ecritures_si_non_acquittee(self):
        prop = {"propositions": [{"montant": 7.5}],
                "a_verifier": [{"motif": "premiere_participation_anterieure"}]}
        with patch.object(E, "Proposer", return_value=prop), \
                patch.object(E, "Executer") as executer, \
                patch.object(wx, "MessageBox", return_value=wx.NO):
            self.assertFalse(UI.Dialog.PreparerCotisationsPourApercu(self.fake()))
            executer.assert_not_called()

    def test_creations_partielles_bloquent_aperçu(self):
        prop = {"propositions": [{"montant": 7.5}], "a_verifier": []}
        with patch.object(E, "Proposer", return_value=prop), \
                patch.object(E, "Executer",
                             return_value=[{"statut": "a_verifier"}]), \
                patch.object(UTILS_Identification, "GetIDutilisateur", return_value=91), \
                patch.object(wx, "MessageBox", return_value=wx.YES):
            self.assertFalse(UI.Dialog.PreparerCotisationsPourApercu(self.fake()))


if __name__ == "__main__":
    unittest.main()
