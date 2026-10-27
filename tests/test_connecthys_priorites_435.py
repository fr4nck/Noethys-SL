# -*- coding: utf-8 -*-
"""#435 : priorités entre réservations successives, sans DB réelle."""
import unittest
from Utils.UTILS_Portail_reservations import planifier_priorites, ArbitrageManuelRequis, decision_quantite

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

    def test_cumul_journee_et_matin_deja_persistes_a_arbitrer(self):
        with self.assertRaises(ArbitrageManuelRequis):
            plan([2], states={'journee': 'reservation', 'matin': 'reservation'})

    def test_doublon_meme_demi_journee_pas_deux_saisies(self):
        result, reasons = plan([2, 2])
        self.assertEqual([r['IDunite'] for r in result], [2])
        self.assertIn('doublon_demande', [reason[0] for reason in reasons])

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


class QuantityDecisionTests(unittest.TestCase):
    @staticmethod
    def case(etat=None, inscription=10, quantite=1, facture=None, verrouillage=0):
        from types import SimpleNamespace as NS
        conso = NS(etat=etat, IDinscription=inscription,
                   IDfacture=facture, verrouillage=verrouillage)
        return NS(etat=etat, quantite=quantite if etat is not None else None,
                  IDfacture=facture, verrouillage=verrouillage,
                  GetListeConso=lambda: [conso])

    def test_absente_creation_unique(self):
        self.assertEqual(decision_quantite(self.case(), 10, 'reservation'), 'creer')

    def test_presente_ne_pas_appeler_saisie(self):
        self.assertEqual(decision_quantite(
            self.case(etat='reservation'), 10, 'reservation'), 'existant')

    def test_attente_requalification_sans_increment(self):
        self.assertEqual(decision_quantite(
            self.case(etat='attente'), 10, 'reservation'), 'requalifier')

    def test_deux_unites_legitimes_ne_sont_pas_ecrasees(self):
        with self.assertRaises(ArbitrageManuelRequis):
            decision_quantite(self.case(etat='reservation', quantite=2),
                              10, 'reservation')

    def test_autre_inscription_interdite(self):
        with self.assertRaises(ArbitrageManuelRequis):
            decision_quantite(self.case(etat='reservation', inscription=11),
                              10, 'reservation')

    def test_facturee_protegee(self):
        with self.assertRaises(ArbitrageManuelRequis):
            decision_quantite(self.case(etat='reservation', facture=5),
                              10, 'reservation')

    def test_pointee_protegee(self):
        with self.assertRaises(ArbitrageManuelRequis):
            decision_quantite(self.case(etat='present'), 10, 'reservation')

    def test_attente_ne_degrade_pas_reservation(self):
        with self.assertRaises(ArbitrageManuelRequis):
            decision_quantite(self.case(etat='reservation'), 10, 'attente')


if __name__ == "__main__":
    unittest.main()
