"""Parcours du vrai dialogue wx sur une base temporaire, sans données réelles."""
import datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'noethys'))
import wx
APP = wx.GetApp() or wx.App(False)
from _fixtures_noethys_db import BaseTest, RedirectionGestionDB
from Data import DATA_Tables as Tables
from Dlg import DLG_Saisie_quotient


class DialogTests(unittest.TestCase):
    def setUp(self):
        self.base = BaseTest()
        self.addCleanup(self.base.fermer)
        for table in ['quotients', 'types_quotients']:
            self.base.db.CreationTable(table, dicoDB=Tables.DB_DATA)
        self.base.inserer('types_quotients', ['IDtype_quotient', 'nom'], [(1, 'CAF fictive')])
        self.context = RedirectionGestionDB(self.base.chemin)
        self.context.__enter__()
        self.addCleanup(self.context.__exit__)

    def construire(self, IDquotient=None):
        dialog = DLG_Saisie_quotient.Dialog(None, IDfamille=1, IDquotient=IDquotient)
        self.addCleanup(dialog.Destroy)
        dialog.SetTypeQuotient(1)
        dialog.SetQuotient(900)
        return dialog

    def ancien(self):
        self.base.inserer('quotients',
                         ['IDquotient', 'IDfamille', 'IDtype_quotient', 'date_debut', 'date_fin', 'quotient', 'revenu'],
                         [(1, 1, 1, '2026-09-10', '2027-01-09', 700, 0)])

    def dates_test(self, dialog):
        dialog.SetDateDebut(datetime.date(2026, 10, 2))
        dialog.SetDateFin(datetime.date(2027, 1, 9))

    def test_nouveau_propose_aujourdhui_et_echeance(self):
        self.ancien()
        dialog = self.construire()
        today = datetime.date.today()
        self.assertEqual(dialog.GetDateDebut(), today)
        from Utils import UTILS_Quotients_validite
        self.assertEqual(dialog.GetDateFin(), UTILS_Quotients_validite.DateFinProposee(today))

    def test_modification_conserve_les_dates_existantes(self):
        self.ancien()
        dialog = self.construire(1)
        self.assertEqual(dialog.GetDateDebut(), datetime.date(2026, 9, 10))
        self.assertEqual(dialog.GetDateFin(), datetime.date(2027, 1, 9))

    def test_date_personnalisee_conservee_et_bouton_recalcule(self):
        dialog = self.construire()
        self.dates_test(dialog)
        dialog.SetDateFin(datetime.date(2027, 6, 30))
        dialog.OnChoixDate()
        self.assertEqual(dialog.GetDateFin(), datetime.date(2027, 6, 30))
        dialog.OnProchaineEcheance()
        self.assertEqual(dialog.GetDateFin(), datetime.date(2027, 1, 9))

    def test_confirmation_annulee_ne_modifie_rien(self):
        self.ancien()
        dialog = self.construire()
        self.dates_test(dialog)
        question = Mock()
        question.ShowModal.return_value = wx.ID_NO
        with patch.object(wx, 'MessageDialog', return_value=question):
            self.assertFalse(dialog.OnBoutonOk(None))
        self.base.db.ExecuterReq('SELECT date_fin FROM quotients')
        self.assertEqual(self.base.db.ResultatReq(), [('2027-01-09',)])

    def test_confirmation_validee_ajuste_et_enregistre(self):
        self.ancien()
        dialog = self.construire()
        self.dates_test(dialog)
        question = Mock()
        question.ShowModal.return_value = wx.ID_YES
        with patch.object(wx, 'MessageDialog', return_value=question), patch.object(dialog, 'EndModal') as fermer:
            dialog.OnBoutonOk(None)
        fermer.assert_called_once_with(wx.ID_OK)
        self.base.db.ExecuterReq('SELECT date_fin, quotient FROM quotients ORDER BY IDquotient')
        self.assertEqual(self.base.db.ResultatReq(), [('2026-10-01', 700), ('2027-01-09', 900)])

    def test_meme_debut_bloque_sans_proposition_dangereuse(self):
        self.ancien()
        dialog = self.construire()
        dialog.SetDateDebut(datetime.date(2026, 9, 10))
        with patch.object(wx, 'MessageBox'), patch.object(wx, 'MessageDialog') as question:
            self.assertFalse(dialog.OnBoutonOk(None))
        question.assert_not_called()


if __name__ == '__main__':
    unittest.main()
