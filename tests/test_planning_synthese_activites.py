"""Synthèse du planning : montants enregistrés et durées sans doublons."""
from decimal import Decimal
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1]/'noethys')]
from Utils import UTILS_Convention_champs as CC


def donnees(conso):
    return {1: {'nom': 'Structure témoin', 'prenom': '', 'activites': {
        10: {'nom': 'Activité témoin', 'dates': {'2026-09-01': {'unites': {1: conso}}}}}}}


def seance(ID, debut='09:00', fin='10:00', montant='20'):
    return dict(IDprestation=ID, heure_debut=debut, heure_fin=fin,
                prestation={'montant': montant})


class SyntheseTests(unittest.TestCase):
    def test_tarifs_changeants_utilisent_les_montants_enregistres(self):
        r = CC.ConstruireSyntheseActivites(donnees([seance(1), seance(2, '10:00', '12:00', '44')]))
        self.assertEqual(r['minutes'], 180)
        self.assertEqual(r['montant'], Decimal('64'))
        self.assertFalse(r['montant_incomplet'])

    def test_unites_partagees_ne_doublent_pas_heures_ni_prestation(self):
        d = donnees([seance(1), seance(1, '09:30', '10:00')])
        r = CC.ConstruireSyntheseActivites(d)
        self.assertEqual(r['minutes'], 60)
        self.assertEqual(r['montant'], Decimal('20'))
        self.assertEqual(len(d[1]['activites'][10]['dates']['2026-09-01']['unites'][1]), 2)

    def test_prestation_partagee_entre_activites_refuse_repartition_arbitraire(self):
        d = donnees([seance(1)])
        d[1]['activites'][11] = {'nom': 'Autre', 'dates': {'2026-09-01': {'unites': {1: [seance(1)]}}}}
        with self.assertRaises(ValueError):
            CC.ConstruireSyntheseActivites(d)

    def test_champs_manquants_signalent_totaux_incomplets(self):
        r = CC.ConstruireSyntheseActivites(donnees([seance(1, None, None, None)]))
        self.assertTrue(r['heures_incompletes'])
        self.assertTrue(r['montant_incomplet'])

    def test_plusieurs_activites_et_total_general(self):
        d = donnees([seance(1)])
        d[1]['activites'][11] = {'nom': 'Autre', 'dates': {'2026-09-01': {'unites': {1: [seance(2, '14:00', '16:00', '45')]}}}}
        r = CC.ConstruireSyntheseActivites(d)
        self.assertEqual(len(r['activites']), 2)
        self.assertEqual(r['minutes'], 180)
        self.assertEqual(r['montant'], Decimal('65'))

    def test_choix_detail_synthese_et_annulation(self):
        import wx
        from Dlg import DLG_Generation_convention as DGC
        p = Mock(IDfamille=1)
        p.ctrl_date_debut.GetDate.return_value = '2026-09-01'
        p.ctrl_date_fin.GetDate.return_value = '2026-09-30'
        for selection in (0, 1, None):
            with self.subTest(selection=selection), patch.object(CC, 'GetIndividusRattaches', return_value=[1]), \
                 patch('Utils.UTILS_Impression_reservations.GetDonnees', return_value=donnees([seance(1)])) as get, \
                 patch('Utils.UTILS_Impression_reservations.Impression') as impression, \
                 patch('wx.SingleChoiceDialog') as choix:
                choix.return_value.ShowModal.return_value = wx.ID_CANCEL if selection is None else wx.ID_OK
                choix.return_value.GetSelection.return_value = selection
                DGC.Dialog.OnBoutonPlanning(p, None)
                if selection is None:
                    impression.assert_not_called()
                elif selection == 0:
                    impression.assert_called_once_with(get.return_value)
                else:
                    impression.assert_called_once_with(get.return_value, synthese=True)
                choix.return_value.Destroy.assert_called_once()

if __name__ == '__main__':
    unittest.main()
