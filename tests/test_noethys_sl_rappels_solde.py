# -*- coding: utf-8 -*-
"""Rappels : pas de fausse dette de 0,00 EUR due aux SUM flottants."""
import datetime
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _garde_reseau
from _fixtures_noethys_db import BaseTest, RedirectionGestionDB
from Data import DATA_Tables
from Utils import UTILS_Rappels


class RappelsSoldeTests(unittest.TestCase):
    def setUp(self):
        self.base = BaseTest()
        self.addCleanup(self.base.fermer)
        self.base.db.CreationTable('ventilation', dicoDB=DATA_Tables.DB_DATA)
        self.base.db.Commit()
        self.redirection = RedirectionGestionDB(self.base.chemin)
        self.redirection.__enter__()
        self.addCleanup(self.redirection.__exit__, None, None, None)
        self.f = UTILS_Rappels.Facturation.__new__(UTILS_Rappels.Facturation)
        self.f.dictTitulaires = {1: dict(titulairesAvecCivilite='Famille fictive', titulairesSansCivilite='Fictive',
                                       adresse=dict(rue='Rue fictive', cp='00000', ville='Test'))}
        self.f.dictOrganisme = dict.fromkeys(('nom', 'rue', 'cp', 'ville', 'tel', 'fax', 'mail', 'site',
                                             'num_agrement', 'num_siret', 'code_ape'), 'Fictif')
        self.f.infosIndividus = SimpleNamespace(GetDictValeurs=lambda **k: {})
        self.f.Questionnaires = SimpleNamespace(GetDonnees=lambda _: [])

    def donnees(self, montants, ventilation):
        for identifiant, montant in enumerate(montants, 1):
            self.base.inserer('prestations', ['IDprestation', 'IDcompte_payeur', 'IDfamille', 'IDactivite', 'date', 'categorie', 'montant'],
                              [(identifiant, 11, 1, 1, '2026-09-01', 'consommation', montant)])
        if ventilation is not None:
            self.base.inserer('ventilation', ['IDventilation', 'IDcompte_payeur', 'IDprestation', 'IDreglement', 'montant'],
                              [(1, 11, 1, 1, ventilation)])
        avant = [list(self.base.db.connexion.execute('SELECT * FROM ' + table))
                 for table in ('prestations', 'ventilation')]
        resultat = self.f.GetDonnees(liste_activites=[1], listeExceptionsComptes=[999999],
                                    date_reference=datetime.date(2026, 9, 30), date_edition=datetime.date(2026, 10, 15))
        self.assertEqual([list(self.base.db.connexion.execute('SELECT * FROM ' + table))
                          for table in ('prestations', 'ventilation')], avant)
        return resultat

    def test_backend_decimal_sql_montants_au_centime(self):
        for total, regle, attendu in ((Decimal('0.30'), Decimal('0.30'), None),
                                      (Decimal('0.300000000001'), Decimal('0.30'), None),
                                      (Decimal('0.30'), Decimal('0.29'), Decimal('0.01'))):
            db = Mock()
            db.ResultatReq.side_effect = [[(11, 1, '2026-09-01', '2026-09-01', total)], [(11, regle)]]
            with patch.object(UTILS_Rappels.GestionDB, 'DB', return_value=db):
                resultat = self.f.GetDonnees(liste_activites=[1], listeExceptionsComptes=[999999],
                                            date_reference=datetime.date(2026, 9, 30), date_edition=datetime.date(2026, 10, 15))
            self.assertEqual(resultat[11]['solde_num'] if resultat else None, attendu)
            self.assertTrue(all(appel.args[0].lstrip().startswith('SELECT') for appel in db.ExecuterReq.call_args_list))
            db.Close.assert_called_once()

    def test_reproduction_sum_flottant_compte_solde_exclu(self):
        self.assertGreater(sum([.1, .2]), .3)  # ecart reel de l'addition binaire
        self.assertEqual(self.donnees([.1, .2], .3), {})

    def test_compte_exactement_solde_exclu(self):
        self.assertEqual(self.donnees([7.50], 7.50), {})

    def test_compte_crediteur_exclu(self):
        self.assertEqual(self.donnees([10], 12), {})

    def test_un_centime_du_reste_propose(self):
        resultat = self.donnees([.1, .2], .29)
        self.assertEqual(resultat[11]['solde_num'], Decimal('0.01'))
        self.assertIn('0.01', resultat[11]['solde'])
        self.assertTrue(resultat[11]['select'])

    def test_dette_usuelle_montants_dates_et_compte_conserves(self):
        r = self.donnees([100, 7.5], 40.45)[11]
        self.assertEqual(r['solde_num'], Decimal('67.05'))
        self.assertEqual(r['IDfamille'], 1)
        self.assertEqual(r['date_min'], datetime.date(2026, 9, 1))
        self.assertEqual(r['date_max'], datetime.date(2026, 9, 1))

    def test_sans_ventilation_dette_conservee(self):
        self.assertEqual(self.donnees([7.5], None)[11]['solde_num'], Decimal('7.50'))


if __name__ == '__main__':
    unittest.main()
