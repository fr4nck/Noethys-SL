"""Réception d'une attestation et saisie unique, sur données fictives."""
import datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'noethys'))
import wx
APP = wx.GetApp() or wx.App(False)
from _fixtures_noethys_db import BaseTest, RedirectionGestionDB
from Data import DATA_Tables as Tables
from Dlg import DLG_Saisie_piece


class ReceptionTests(unittest.TestCase):
    def setUp(self):
        self.base = BaseTest()
        self.addCleanup(self.base.fermer)
        for table in ['quotients', 'types_quotients', 'types_pieces', 'pieces',
                      'pieces_activites', 'inscriptions']:
            self.base.db.CreationTable(table, dicoDB=Tables.DB_DATA)
        self.base.inserer('types_quotients', ['IDtype_quotient', 'nom'], [(1, 'CAF fictive')])
        self.base.inserer('types_pieces', ['IDtype_piece', 'nom', 'public', 'duree_validite'],
                         [(1, 'Attestation QF fictive', 'famille', '2027-08-31')])
        self.context = RedirectionGestionDB(self.base.chemin)
        self.context.__enter__()
        self.addCleanup(self.context.__exit__)
        self.dialog = DLG_Saisie_piece.Dialog(None, IDfamille=42)
        self.addCleanup(self.dialog.Destroy)
        self.dialog.SetValeurs(IDfamille=42, IDtype_piece=1)
        self.dialog.ctrl_date_debut.SetDate(datetime.date(2026, 10, 2))

    def completer(self):
        self.dialog.check_saisir_quotient.SetValue(True)
        self.dialog.OnActiverQuotient()
        self.dialog.ctrl_quotient.SetValue('790')
        self.dialog.ctrl_type_quotient.SetID(1)
        self.dialog.OnEcheanceQF()

    def test_echeance_et_champs_optionnels(self):
        self.assertFalse(self.dialog.check_saisir_quotient.GetValue())
        self.assertFalse(self.dialog.ctrl_quotient.IsEnabled())
        self.completer()
        self.assertTrue(self.dialog.ctrl_quotient.IsEnabled())
        self.assertEqual(self.dialog.ctrl_date_fin.GetDate(), datetime.date(2027, 1, 9))

    def test_montant_obligatoire_avant_sauvegarde(self):
        self.completer()
        self.dialog.ctrl_quotient.SetValue('')
        with patch.object(wx, 'MessageBox'), patch.object(self.dialog, 'Sauvegarde') as save:
            self.dialog.OnBoutonOk(None)
        save.assert_not_called()

    def test_montant_et_dates_reportes_dans_quotients(self):
        self.completer()
        with patch.object(self.dialog, 'Sauvegarde', return_value=True), patch.object(self.dialog, 'EndModal') as close:
            self.dialog.OnBoutonOk(None)
        close.assert_called_once_with(wx.ID_OK)
        self.base.db.ExecuterReq('SELECT IDfamille, date_debut, date_fin, quotient, IDtype_quotient FROM quotients')
        self.assertEqual(self.base.db.ResultatReq(), [(42, '2026-10-02', '2027-01-09', 790.0, 1)])

    def test_echec_piece_ne_cree_pas_quotient(self):
        self.completer()
        with patch.object(self.dialog, 'Sauvegarde', return_value=False), patch.object(self.dialog, 'SaisirQuotient') as save:
            self.dialog.OnBoutonOk(None)
        save.assert_not_called()

    def test_renouvellement_depuis_reception(self):
        self.completer()
        self.base.inserer('quotients',
                         ['IDquotient', 'IDfamille', 'IDtype_quotient', 'date_debut', 'date_fin', 'quotient'],
                         [(1, 42, 1, '2026-09-01', '2027-08-31', 900)])
        question = Mock()
        question.ShowModal.return_value = wx.ID_YES
        with patch.object(wx, 'MessageDialog', return_value=question):
            self.assertTrue(self.dialog.SaisirQuotient())
        self.base.db.ExecuterReq('SELECT date_debut, date_fin, quotient FROM quotients ORDER BY IDquotient')
        self.assertEqual(self.base.db.ResultatReq(),
                         [('2026-09-01', '2026-10-01', 900.0), ('2026-10-02', '2027-01-09', 790.0)])

    def test_echec_quotient_garde_fenetre_ouverte(self):
        self.completer()
        with patch.object(self.dialog, 'Sauvegarde', return_value=True), patch.object(self.dialog, 'SaisirQuotient', return_value=False), patch.object(self.dialog, 'EndModal') as close:
            self.dialog.OnBoutonOk(None)
        close.assert_not_called()


if __name__ == '__main__':
    unittest.main()
