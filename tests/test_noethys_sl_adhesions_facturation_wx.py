# -*- coding: utf-8 -*-
"""P1 #426 : tests wx du choix explicite des cotisations, sans base reelle."""
import datetime
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
import wx
from Dlg import DLG_Factures_generation as UI
from Utils import UTILS_Adhesions as A
from Utils import UTILS_Adhesions_echeances as E
from Utils import UTILS_Identification


def params(prestations=None):
    return dict(date_debut="2026-09-01", date_fin="2026-09-30",
                date_anterieure=None, listeActivites=[1, 2],
                IDcompte_payeur=None,
                prestations=["consommation", "cotisation"] if prestations is None else prestations)


def proposition():
    return {
        "date_debut": datetime.date(2026, 9, 1),
        "date_fin": datetime.date(2026, 9, 30),
        "date_reference": datetime.date(2026, 10, 19),
        "propositions": [{"IDtitulaire": 100, "IDindividu": 100,
                          "IDcompte_payeur": 11, "montant": 7.5,
                          "date_debut": datetime.date(2026, 9, 5)}],
        "a_verifier": [],
    }


class ChoixFactice:
    def __init__(self, selections=(0,), code=wx.ID_OK):
        self.selections = list(selections)
        self.code = code
        self.selection_initiale = None
        self.ferme = False

    def SetSelections(self, indices):
        self.selection_initiale = list(indices)

    def ShowModal(self):
        return self.code

    def GetSelections(self):
        return self.selections

    def Destroy(self):
        self.ferme = True


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
        prop = proposition()
        choix = ChoixFactice(selections=[0])
        appels = []
        def proposer(**kwargs):
            appels.append("proposer")
            return prop
        def executer(*args, **kwargs):
            appels.append("executer")
            return [{"statut": "cree"}]
        with patch.object(E, "Proposer", side_effect=proposer), \
                patch.object(E, "Executer", side_effect=executer) as ecrire, \
                patch.object(A, "_lire", return_value=[(100, "TEST", "Lou")]), \
                patch.object(UTILS_Identification, "GetIDutilisateur", return_value=91), \
                patch.object(wx, "MultiChoiceDialog", return_value=choix):
            self.assertTrue(UI.Dialog.PreparerCotisationsPourApercu(self.fake()))
        self.assertEqual(appels, ["proposer", "executer", "proposer"])
        self.assertEqual(choix.selection_initiale, [0])
        self.assertTrue(choix.ferme)
        self.assertEqual(ecrire.call_args.kwargs["confirmation"], True)
        self.assertEqual(ecrire.call_args.kwargs["selection_titulaires"], {100})
        self.assertEqual(ecrire.call_args.kwargs["IDutilisateur"], 91)

    def test_non_explicite_ne_cree_jamais(self):
        prop = proposition()
        with patch.object(E, "Proposer", return_value=prop), \
                patch.object(E, "Executer") as executer, \
                patch.object(A, "_lire", return_value=[(100, "TEST", "Lou")]), \
                patch.object(wx, "MultiChoiceDialog", return_value=ChoixFactice(selections=[])):
            self.assertTrue(UI.Dialog.PreparerCotisationsPourApercu(self.fake()))
            executer.assert_not_called()
        with patch.object(E, "Proposer", return_value=prop), \
                patch.object(E, "Executer") as executer, \
                patch.object(A, "_lire", return_value=[(100, "TEST", "Lou")]), \
                patch.object(wx, "MultiChoiceDialog", return_value=ChoixFactice(code=wx.ID_CANCEL)):
            self.assertFalse(UI.Dialog.PreparerCotisationsPourApercu(self.fake()))
            executer.assert_not_called()

    def test_anomalie_bloque_les_ecritures_si_non_acquittee(self):
        prop = proposition()
        prop["a_verifier"] = [{"motif": "premiere_participation_anterieure"}]
        with patch.object(E, "Proposer", return_value=prop), \
                patch.object(E, "Executer") as executer, \
                patch.object(wx, "MessageBox", return_value=wx.NO):
            self.assertFalse(UI.Dialog.PreparerCotisationsPourApercu(self.fake()))
            executer.assert_not_called()

    def test_creations_partielles_bloquent_apercu(self):
        prop = proposition()
        with patch.object(E, "Proposer", return_value=prop), \
                patch.object(E, "Executer", return_value=[{"statut": "a_verifier"}]) as executer, \
                patch.object(A, "_lire", return_value=[(100, "TEST", "Lou")]), \
                patch.object(UTILS_Identification, "GetIDutilisateur", return_value=91), \
                patch.object(wx, "MultiChoiceDialog", return_value=ChoixFactice()), \
                patch.object(wx, "MessageBox", return_value=wx.OK):
            self.assertFalse(UI.Dialog.PreparerCotisationsPourApercu(self.fake()))
            executer.assert_called_once()


if __name__ == "__main__":
    unittest.main()
