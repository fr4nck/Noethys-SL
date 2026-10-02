import datetime
from decimal import Decimal
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'noethys'))
import wx
APP = wx.GetApp() or wx.App(False)
from _fixtures_noethys_db import BaseTest, RedirectionGestionDB
from Data import DATA_Tables as Tables
from Dlg import DLG_Attestations_repas
from Ol import OL_Attestations_fiscales_prestations
from Ol import OL_Attestations_fiscales_selection
from Utils import UTILS_Attestations_repas as repas


class DialogTests(unittest.TestCase):
    def setUp(self):
        self.base = BaseTest()
        self.addCleanup(self.base.fermer)
        for table in ('ventilation', 'reglements'):
            self.base.db.CreationTable(table, dicoDB=Tables.DB_DATA)
        self.base.inserer('activites', ['IDactivite', 'nom'], [(1, 'Accueil fictif')])
        self.base.inserer('unites', ['IDunite', 'IDactivite', 'nom'], [(2, 1, 'Repas'), (3, 1, 'Journée')])
        self.context = RedirectionGestionDB(self.base.chemin)
        self.context.__enter__()
        self.addCleanup(self.context.__exit__)

    def dialog(self):
        dlg = DLG_Attestations_repas.Dialog(None)
        self.addCleanup(dlg.Destroy)
        return dlg

    def test_saisie_enregistre_et_recharge(self):
        dlg = self.dialog()
        dlg.AjouterLigne('Accueil fictif / Repas')
        for col, value in ((1, '01/01/2026'), (2, '31/08/2026'), (3, '3,50')):
            dlg.grille.SetCellValue(0, col, value)
        with patch.object(dlg, 'EndModal') as close:
            dlg.OnValider(None)
        close.assert_called_once_with(wx.ID_OK)
        nouveau = self.dialog()
        self.assertEqual(nouveau.LireRegles(),
                         [dict(IDunite=2, date_debut='2026-01-01', date_fin='2026-08-31', montant='3.50')])

    def test_selection_reservation_obligatoire(self):
        dlg = self.dialog()
        dlg.AjouterLigne()
        dlg.grille.SetCellValue(0, 3, '4')
        with self.assertRaises(ValueError):
            dlg.LireRegles()

    def test_liste_reelle_associe_deduction_a_prestation(self):
        self.base.inserer('individus', ['IDindividu', 'nom', 'prenom', 'date_naiss'], [(100, 'FICTIF', 'Enfant', '2024-01-01')])
        self.base.inserer('prestations', ['IDprestation', 'IDactivite', 'IDindividu', 'IDfamille', 'IDcompte_payeur', 'date', 'label', 'montant'],
                         [(10, 1, 100, 42, 42, '2026-08-31', 'Journée', 20), (11, 1, 100, 42, 42, '2026-09-01', 'Journée', 20)])
        self.base.inserer('consommations', ['IDconso', 'IDprestation', 'IDunite', 'date', 'quantite'],
                         [(1, 10, 2, '2026-08-31', 1), (2, 11, 2, '2026-09-01', 1)])
        repas.Sauver(self.base.db, [dict(IDunite=2, date_debut='2026-01-01', date_fin='2026-08-31', montant='3.50'),
                                  dict(IDunite=2, date_debut='2026-09-01', date_fin='2026-12-31', montant='4')])
        proxy = SimpleNamespace(date_debut=datetime.date(2026, 1, 1), date_fin=datetime.date(2026, 12, 31),
                                dateNaiss=datetime.date(2020, 1, 1), listeActivites=[1], listeModes=[1],
                                methode='prestations', deduire_repas=True)
        tracks = OL_Attestations_fiscales_prestations.ListView.GetTracks(proxy)
        self.assertEqual(len(tracks), 1)
        self.assertEqual([p['deduction_repas'] for p in tracks[0].listePrestations], [Decimal('3.50'), Decimal('4')])
        self.assertEqual(tracks[0].montant_total, Decimal('40'))
        famille = dict(adresse=dict(rue='', cp='', ville=''),
                       titulairesAvecCivilite='Famille fictive', titulairesSansCivilite='Famille fictive')
        selection = SimpleNamespace(listePrestations=tracks, dictTitulaires={42: famille})
        attestations = OL_Attestations_fiscales_selection.ListView.GetTracks(selection)
        self.assertEqual(len(attestations), 1)
        self.assertEqual(attestations[0].montant_total, Decimal('32.50'))
        self.base.db.ExecuterReq('SELECT montant FROM prestations ORDER BY IDprestation')
        self.assertEqual(self.base.db.ResultatReq(), [(20.0,), (20.0,)])


if __name__ == '__main__':
    unittest.main()
