# -*- coding: utf-8 -*-
"""#435 : priorités entre réservations successives, sans DB réelle."""
import unittest
from Utils.UTILS_Portail_reservations import planifier_priorites, ArbitrageManuelRequis

UNITS = {1: {'role_portail': 'journee'}, 2: {'role_portail': 'matin'},
         3: {'role_portail': 'apres_midi'}, 4: {'role_portail': 'repas'}}


def demands(roles):
    return [{'IDreservation': i + 1, 'IDunite': unit, 'IDinscription': 10,
             'date': '2026-11-04', 'etat': 1} for i, unit in enumerate(roles)]


def plan(roles, states=None, available=None):
    states, available = states or {}, available or {}
    return planifier_priorites(demands(roles), UNITS,
        lambda request, role: states.get(role),
        lambda request: available.get(request['IDunite'], True))


class PriorityTests(unittest.TestCase):
    def test_day_prioritaire_meme_demande(self):
        result, reasons = plan([1, 2, 3])
        self.assertEqual([r['IDunite'] for r in result], [1])
        self.assertEqual(reasons[0][0], 'journee_prioritaire')

    def test_day_full_repli_deux_demis(self):
        result, reasons = plan([1, 2, 3], available={1: False})
        self.assertEqual([r['IDunite'] for r in result], [2, 3])
        self.assertEqual(reasons[0][0], 'journee_complete_repli_demi')

    def test_day_full_repli_demi_disponible(self):
        result, _ = plan([1, 2, 3], available={1: False, 2: False})
        self.assertEqual([r['IDunite'] for r in result], [3])

    def test_aucune_alternative_ne_valide_silencieusement(self):
        with self.assertRaises(ArbitrageManuelRequis):
            plan([1, 2, 3], available={1: False, 2: False, 3: False})

    def test_day_full_sans_alternative_attend(self):
        result, _ = plan([1], available={1: False})
        self.assertEqual([r['IDunite'] for r in result], [1])

    def test_day_deja_present_demande_suivante(self):
        result, reasons = plan([2, 3], states={'journee': 'reservation'})
        self.assertEqual(result, [])
        self.assertEqual(reasons[0][0], 'journee_deja_presente')

    def test_deja_present_same_half_noop(self):
        result, _ = plan([2], states={'matin': 'reservation'})
        self.assertEqual(result, [])

    def test_ancienne_demi_ne_disparait_pas_silencieusement(self):
        with self.assertRaises(ArbitrageManuelRequis):
            plan([1, 2, 3], states={'matin': 'reservation'})

    def test_attente_peut_etre_requalifiee(self):
        result, _ = plan([2], states={'matin': 'attente'})
        self.assertEqual([r['IDunite'] for r in result], [2])

    def test_pointage_arbitrage(self):
        with self.assertRaises(ArbitrageManuelRequis):
            plan([2], states={'matin': 'absenti'})

    def test_repas_independant(self):
        result, _ = plan([1, 2, 3, 4])
        self.assertEqual([r['IDunite'] for r in result], [1, 4])

    def test_entrees_inalterees(self):
        source = demands([1, 2, 3])
        planifier_priorites(source, UNITS, lambda r, name: None, lambda r: True)
        self.assertEqual(source, demands([1, 2, 3]))

    def test_annulation_conservee(self):
        source = demands([1, 2, 3])
        source[1]['etat'] = 0
        result, _ = planifier_priorites(source, UNITS,
                                          lambda r, name: None, lambda r: True)
        self.assertIn(source[1], result)

    def test_disponibilite_inconnue_arbitrage(self):
        with self.assertRaises(ArbitrageManuelRequis):
            plan([1, 2, 3], available={1: None})

    def test_inscriptions_distinctes(self):
        source = demands([1, 2, 3])
        source[1]['IDinscription'] = 20
        source[2]['IDinscription'] = 20
        result, _ = planifier_priorites(source, UNITS,
                                          lambda r, name: None, lambda r: True)
        self.assertEqual(len(result), 3)


if __name__ == "__main__":
    unittest.main()
