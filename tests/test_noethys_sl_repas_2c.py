# -*- coding: utf-8 -*-
"""Tests purs du contrat opt-in repas #433 : aucune connexion ni ecriture."""
import unittest
from datetime import date

from Utils import UTILS_Repas_2c as R

JOUR = date(2026, 10, 28)
CHOIX = {"standard": 11, "sans_porc": 12, "vegetarien": 13, "sans_repas_pmsl": 14}


def accueil(individu, debut="08:30", fin="17:30", etat="reservation",
            repas=True, jour=JOUR, site="Bais", service="midi", **kw):
    return dict(IDindividu=individu, date=jour, site=site, service=service,
                heure_debut=debut, heure_fin=fin, etat=etat,
                midi_debut="12:00", midi_fin="13:00", repas_pmsl_prevu=repas, **kw)


def repartir(lignes, reponses=None, exceptions=None, mode="prevision"):
    return R.RepartirAccueils(lignes, reponses or {}, CHOIX, exceptions, mode)


def exception(type_repas):
    return {"type_repas": type_repas, "auteur": "operateur-test",
            "horodatage": "2026-10-26T16:00:00+01:00"}


class CouvertureMidi(unittest.TestCase):
    def test_journee_et_demi_avec_midi(self):
        self.assertTrue(R.CouvreMidi([("08:30", "17:30")], "12:00", "13:00"))
        self.assertTrue(R.CouvreMidi([("08:30", "13:00")], "12:00", "13:00"))
        self.assertTrue(R.CouvreMidi([("12:00", "17:00")], "12:00", "13:00"))

    def test_demi_sans_midi(self):
        self.assertFalse(R.CouvreMidi([("08:30", "12:00")], "12:00", "13:00"))
        self.assertFalse(R.CouvreMidi([("13:00", "17:00")], "12:00", "13:00"))

    def test_plages_jointives_sans_double_compte(self):
        self.assertTrue(R.CouvreMidi([("08:30", "12:30"), ("12:30", "17:00")], "12:00", "13:00"))

    def test_midi_partiel_ambigu(self):
        for plages in ([('08:30', '12:30')], [('12:30', '17:30')],
                       [('08:30', '12:20'), ('12:40', '17:30')]):
            with self.subTest(plages=plages), self.assertRaises(R.Repas2CInvalide):
                R.CouvreMidi(plages, "12:00", "13:00")

    def test_horaires_invalides(self):
        for debut, fin in [('', '17:00'), ('13:00', '12:00'), ('24:00', '00:30')]:
            with self.subTest(debut=debut), self.assertRaises(R.Repas2CInvalide):
                R.CouvreMidi([(debut, fin)], "12:00", "13:00")


class ChoixTypeRepas(unittest.TestCase):
    def test_configuration_quatre_choix(self):
        self.assertEqual(R.ConfigurationTypeRepas(5, CHOIX)[1], CHOIX)
        for mauvais in [{"standard": 11, "sans_porc": 12, "vegetarien": 13},
                        dict(CHOIX, sans_repas_pmsl=11), dict(CHOIX, standard=True),
                        dict(CHOIX, standard=11.7)]:
            with self.subTest(mauvais=mauvais), self.assertRaises(R.Repas2CInvalide):
                R.ConfigurationTypeRepas(5, mauvais)

    def test_exemple_30_avec_panier(self):
        lignes = [accueil(i) for i in range(1, 31)]
        reponses = {i: 11 for i in range(1, 25)}
        reponses.update({i: 12 for i in range(25, 28)})
        reponses.update({28: 13, 29: 13, 30: 14})
        r = repartir(lignes, reponses)[(JOUR, "Bais", "midi")]
        self.assertEqual((r["presents_midi"], r["standard"], r["sans_porc"],
                          r["vegetarien"], r["repas_apportes"], r["repas_fournisseur"]),
                         (30, 24, 3, 2, 1, 29))
        self.assertTrue(r["complet"])

    def test_panier_meme_si_formule_ne_fournit_pas_le_repas(self):
        r = repartir([accueil(1, repas=False)], {1: 14})[JOUR, "Bais", "midi"]
        self.assertEqual((r["repas_apportes"], r["repas_fournisseur"]), (1, 0))

    def test_pas_de_reservation_repas_distincte(self):
        r = repartir([accueil(1, debut="08:30", fin="13:00")],
                     {1: 14})[(JOUR, "Bais", "midi")]
        self.assertEqual((r["presents_midi"], r["repas_apportes"], r["repas_fournisseur"]), (1, 1, 0))

    def test_demi_sans_midi_ni_repas(self):
        self.assertEqual(repartir([accueil(1, debut="13:00", fin="17:00")]), {})

    def test_absence_de_reponse_standard_avec_formule_repas(self):
        r = repartir([accueil(1)])[JOUR, "Bais", "midi"]
        self.assertEqual((r["standard"], r["provenances"]["defaut_standard"]), (1, 1))

    def test_sans_offre_de_repas_et_reponse_absente_a_qualifier(self):
        r = repartir([accueil(1, repas=False)])[JOUR, "Bais", "midi"]
        self.assertEqual((r["a_qualifier"], r["repas_fournisseur"], r["complet"]), (1, 0, False))

    def test_sans_offre_non_precisee_refusee(self):
        entree = accueil(1)
        del entree["repas_pmsl_prevu"]
        with self.assertRaises(R.Repas2CInvalide):
            repartir([entree])

    def test_sans_offre_et_demande_standard_refusee(self):
        with self.assertRaises(R.Repas2CInvalide):
            repartir([accueil(1, repas=False)], {1: 11})

    def test_exception_datee_prioritaire_et_tracee(self):
        autre = date(2026, 11, 4)
        lignes = [accueil(1, jour=JOUR), accueil(1, jour=autre)]
        e = {(1, JOUR, "Bais", "midi"): exception("sans_repas_pmsl")}
        r = repartir(lignes, {1: 11}, e)
        self.assertEqual((r[JOUR, "Bais", "midi"]["repas_apportes"],
                          r[autre, "Bais", "midi"]["standard"]), (1, 1))
        self.assertEqual(r[JOUR, "Bais", "midi"]["provenances"]["exception_datee"], 1)

    def test_exception_non_tracee_refusee(self):
        with self.assertRaises(R.Repas2CInvalide):
            repartir([accueil(1)], {}, {(1, JOUR, "Bais", "midi"): {"type_repas": "sans_repas_pmsl"}})

    def test_reservation_pour_prevision_present_pour_realise(self):
        lignes = [accueil(1), accueil(2, etat="present"), accueil(3, etat="absenti")]
        self.assertEqual(repartir(lignes)[JOUR, "Bais", "midi"]["presents_midi"], 2)
        self.assertEqual(repartir(lignes, mode="realise")[JOUR, "Bais", "midi"]["presents_midi"], 1)

    def test_plusieurs_unites_ne_doublent_pas_enfant(self):
        lignes = [accueil(1, debut="08:30", fin="12:30"),
                  accueil(1, debut="12:30", fin="17:30")]
        r = repartir(lignes)[JOUR, "Bais", "midi"]
        self.assertEqual((r["presents_midi"], r["repas_fournisseur"]), (1, 1))

    def test_offres_midi_contradictoires_refusees(self):
        lignes = [accueil(1, debut="08:30", fin="12:30", repas=True),
                  accueil(1, debut="12:30", fin="17:00", repas=False)]
        with self.assertRaises(R.Repas2CInvalide):
            repartir(lignes)

    def test_midi_sur_deux_sites_refuse(self):
        with self.assertRaises(R.Repas2CInvalide):
            repartir([accueil(1), accueil(1, site="La Guerche")])

    def test_total_anonymise_et_entrees_non_modifiees(self):
        entree = accueil(7)
        originale = dict(entree)
        r = repartir([entree], {7: 14})[JOUR, "Bais", "midi"]
        self.assertEqual(entree, originale)
        self.assertNotIn("IDindividu", r)
        self.assertNotIn("auteur", r)

    def test_reponses_contradictoires_ou_inconnues_refusees(self):
        for reponse in ("11;12", "99", True):
            with self.subTest(reponse=reponse), self.assertRaises(R.Repas2CInvalide):
                repartir([accueil(1)], {1: reponse})


if __name__ == "__main__":
    unittest.main()
