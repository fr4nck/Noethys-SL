# -*- coding: utf-8 -*-
"""#435 : priorités entre réservations successives, sans DB réelle."""
import unittest
from Utils.UTILS_Portail_reservations import (planifier_priorites, planifier_sur_grille,
                                               ArbitrageManuelRequis, decision_quantite,
                                               preparer_confirmation_attentes)

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



class RepriseQuantitePartielleTests(unittest.TestCase):
    def test_une_unite_deja_enregistree_et_une_absente_rejouables(self):
        from types import SimpleNamespace as NS
        DATE = "2026-11-04"
        def conso(etat):
            if etat is None:
                return NS(etat=None, quantite=None, IDfacture=None,
                          verrouillage=0, GetListeConso=lambda: [])
            ligne = NS(etat=etat, IDinscription=10, IDfacture=None,
                       verrouillage=0)
            return NS(etat=etat, quantite=1, IDfacture=None, verrouillage=0,
                      GetListeConso=lambda: [ligne])
        cas = {101: conso('reservation'), 102: conso(None)}
        classe = NS(
            dictUnites={101: {'type': 'Quantite'}, 102: {'type': 'Quantite'}})
        grille = NS(grille=classe,
                    GetCase=lambda identifiant, date: cas[identifiant],
                    IsOuvert=lambda **kw: True,
                    HasPlacesDisponibles=lambda **kw: True)
        unites = {1: {'nom': 'Option Quantite', 'IDactivite': 7,
                      'unites_principales': [101, 102],
                      'unites_secondaires': [], 'role_portail': 'normal'}}
        demandes = [{'IDreservation': 2, 'IDunite': 1, 'IDinscription': 10,
                     'date': DATE, 'etat': 1}]
        retenues, decisions = planifier_sur_grille(demandes, unites, grille, 7)
        self.assertEqual(retenues, demandes)
        self.assertEqual(decisions, [])
        self.assertEqual(decision_quantite(cas[101], 10, 'reservation'), 'existant')
        self.assertEqual(decision_quantite(cas[102], 10, 'reservation'), 'creer')

    def test_reprise_quantite_autre_inscription_reste_protegee(self):
        with self.assertRaises(ArbitrageManuelRequis):
            # La provenance etrangere ne doit jamais etre ecrasee.
            decision_quantite(QuantityDecisionTests.case(
                etat='reservation', inscription=11), 10, 'reservation')


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



class DirectionCapaciteTests(unittest.TestCase):
    """L'autorite humaine peut reserver meme avec zero place informatique."""

    class Case:
        etat = None
        def GetListeConso(self):
            return []

    class Grille:
        def GetCase(self, IDunite, date):
            return DirectionCapaciteTests.Case()
        def IsOuvert(self, IDunite, date):
            return True
        def HasPlacesDisponibles(self, IDunite, date):
            return False

    def unites(self):
        return {
            numero: dict(valeurs, IDactivite=50,
                         unites_principales=[100 + numero],
                         unites_secondaires=[])
            for numero, valeurs in UNITS.items()
        }

    def test_derogation_capacite_priorise_la_journee_meme_a_zero_place(self):
        resultat, decisions = planifier_sur_grille(
            demands([1, 2, 3]), self.unites(), self.Grille(), 50,
            forcer_capacite=True)
        self.assertEqual([item['IDunite'] for item in resultat], [1])
        self.assertIn('journee_prioritaire', [motif for motif, _ in decisions])

    def test_sans_derogation_les_regles_automatiques_restant_actives(self):
        with self.assertRaises(ArbitrageManuelRequis):
            planifier_sur_grille(demands([1, 2, 3]), self.unites(), self.Grille(), 50)



class ValidationDirecteConnecthysTests(unittest.TestCase):
    """Validation en un clic : ne jamais imposer un detour par la grille."""

    def construire(self, etat='attente', inscription=10, facture=None,
                   verrouillage=0, quantite=1, ouvert=True, type_unite='Unitaire'):
        from types import SimpleNamespace as NS
        conso = NS(etat=etat, IDinscription=inscription,
                   IDfacture=facture, verrouillage=verrouillage)
        case = NS(
            etat=etat, IDfacture=None, verrouillage=0, quantite=quantite,
            GetListeConso=lambda: [conso])
        grille = NS(grille=NS(dictUnites={101: {'type': type_unite}}),
                    GetCase=lambda IDunite, date: case,
                    IsOuvert=lambda **kw: ouvert,
                    HasPlacesDisponibles=lambda **kw: False)
        unites = {1: {'role_portail': 'normal', 'nom': 'Accueil',
                      'IDactivite': 50, 'unites_principales': [101],
                      'unites_secondaires': []}}
        demande = {'IDreservation': 1, 'IDunite': 1,
                   'IDinscription': 10, 'date': '2026-11-04', 'etat': 1}
        return conso, case, grille, unites, demande

    def tester(self, **options):
        conso, case, grille, unites, demande = self.construire(**options)
        resultat = preparer_confirmation_attentes(
            [demande], unites, grille, 50)
        return conso, case, resultat

    def test_zero_place_reste_confirmable_sans_ouvrir_la_grille(self):
        conso, case, resultat = self.tester()
        self.assertEqual(len(resultat), 1)
        self.assertIs(resultat[0][0], case)
        self.assertIs(resultat[0][1], conso)
        self.assertEqual(conso.etat, 'attente')  # prevol strictement lecture seule

    def test_reservation_deja_confirmee_pas_de_rejeu(self):
        _, _, resultat = self.tester(etat='reservation')
        self.assertEqual(resultat, [])

    def test_pointage_ne_devient_pas_confirmation(self):
        _, _, resultat = self.tester(etat='present')
        self.assertEqual(resultat, [])

    def test_autre_inscription_ne_peut_etre_modifiee(self):
        with self.assertRaises(ArbitrageManuelRequis):
            self.tester(inscription=11)

    def test_facturation_et_verrouillage_restent_proteges(self):
        for options in ({'facture': 40}, {'verrouillage': 1}):
            with self.subTest(**options):
                with self.assertRaises(ArbitrageManuelRequis):
                    self.tester(**options)

    def test_une_unite_fermee_ne_peut_pas_etre_forcee(self):
        with self.assertRaises(ArbitrageManuelRequis):
            self.tester(ouvert=False)

    def test_quantite_deux_ne_peut_pas_etre_ecrasee(self):
        with self.assertRaises(ArbitrageManuelRequis):
            self.tester(type_unite='Quantite', quantite=2)

    def test_une_demande_repetee_ne_confirme_quune_fois(self):
        conso, case, grille, unites, demande = self.construire()
        seconde = dict(demande, IDreservation=2)
        resultat = preparer_confirmation_attentes(
            [demande, seconde], unites, grille, 50)
        self.assertEqual(len(resultat), 1)



if __name__ == "__main__":
    unittest.main()
