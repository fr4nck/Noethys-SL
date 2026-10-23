# -*- coding: utf-8 -*-
"""AFAS V2 -- moteur de calcul ALSH (sans wx, sans base).

Données fictives : un calendrier de vacances construit pour les tests, des
unités, ouvertures et consommations inventées. Les durées sont en secondes.
"""
import datetime
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
for chemin in (RACINE / "noethys", RACINE / "tests"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))

from Utils import UTILS_AFAS2_Calcul as M  # noqa: E402
from Utils import UTILS_AFAS2_Calendrier as K  # noqa: E402
from test_afas2_calendrier import VACANCES_FICTIVES  # noqa: E402

H = 3600
D = datetime.date
BAIS_PLUS, BAIS_MOINS, GUERCHE, MINICAMP = (1, 11), (1, 12), (1, 14), (1, 15)

UNITES = {
    # périscolaire
    101: {"nom": "Matin", "type": "Unitaire", "heure_debut": "07:30", "heure_fin": "08:45", "categorie": "accueil"},
    102: {"nom": "Midi", "type": "Unitaire", "heure_debut": "11:45", "heure_fin": "13:45", "categorie": "accueil"},
    103: {"nom": "Soir", "type": "Unitaire", "heure_debut": "16:30", "heure_fin": "18:30", "categorie": "accueil"},
    104: {"nom": "Repas", "type": "Unitaire", "heure_debut": "12:00", "heure_fin": "13:00", "categorie": "repas"},
    105: {"nom": "Garderie matin", "type": "Horaire", "heure_debut": "07:00", "heure_fin": "07:30", "categorie": "garderie_matin"},
    106: {"nom": "Garderie soir", "type": "Horaire", "heure_debut": "18:30", "heure_fin": "19:00", "categorie": "garderie_soir"},
    107: {"nom": "Mercredi journée", "type": "Unitaire", "heure_debut": "07:00", "heure_fin": "19:00", "categorie": "accueil"},
    # extrascolaire
    201: {"nom": "Journée", "type": "Unitaire", "heure_debut": "08:30", "heure_fin": "17:30", "categorie": "journee"},
    202: {"nom": "Matinée", "type": "Unitaire", "heure_debut": "08:30", "heure_fin": "12:00", "categorie": "demi_journee"},
    203: {"nom": "Après-midi", "type": "Unitaire", "heure_debut": "13:30", "heure_fin": "17:30", "categorie": "demi_journee"},
    204: {"nom": "Sortie", "type": "Unitaire", "heure_debut": None, "heure_fin": None, "categorie": "annexe"},
    205: {"nom": "Minicamp", "type": "Unitaire", "heure_debut": "08:00", "heure_fin": "20:00", "categorie": "sejour"},
    206: {"nom": "Journée courte", "type": "Unitaire", "heure_debut": "10:00", "heure_fin": "16:00", "categorie": "journee"},
    207: {"nom": "Demi courte", "type": "Unitaire", "heure_debut": "10:00", "heure_fin": "13:00", "categorie": "demi_journee"},
    208: {"nom": "Accueil horaire", "type": "Horaire", "heure_debut": "08:00", "heure_fin": "18:00", "categorie": "accueil"},
    209: {"nom": "Inconnue", "type": "Unitaire", "heure_debut": "08:00", "heure_fin": "09:00", "categorie": "a_qualifier"},
    210: {"nom": "Ultra courte", "type": "Unitaire", "heure_debut": "10:00", "heure_fin": "11:30", "categorie": "journee"},
}

MERCREDI_SCOLAIRE = D(2026, 10, 14)
LUNDI_SCOLAIRE = D(2026, 10, 12)
MERCREDI_VACANCES = D(2026, 10, 21)
LUNDI_VACANCES = D(2026, 10, 19)
SAMEDI_SANS_ECOLE = D(2026, 10, 10)
DIMANCHE_SEJOUR = D(2026, 10, 25)


def contexte(mode, couples=None, ouvertures=None, **kw):
    ctx = {
        "mode": mode, "equipement": "BAIS",
        "couples": couples or {BAIS_PLUS: "Bais +6 ans", BAIS_MOINS: "Bais -6 ans", MINICAMP: "Minicamps 6/8"},
        "unites": UNITES, "etats_realise": ["present"], "etats_facture": ["present", "absentj", "absenti"],
        "options": {}, "calendrier": K.Calendrier(VACANCES_FICTIVES),
        "ouvertures": ouvertures if ouvertures is not None else set(),
        "aeeh": {}, "sejours": [], "date_reference": D(2027, 1, 15),
    }
    ctx.update(kw)
    return ctx


_ID = [0]


def conso(date, IDunite, couple=BAIS_PLUS, etat="present", individu=1, hd=None, hf=None, IDprestation=None,
          IDfacture=None, facture_etat=None):
    _ID[0] += 1
    unite = UNITES[IDunite]
    return {"IDconso": _ID[0], "IDindividu": individu, "date": date, "IDunite": IDunite,
            "IDactivite": couple[0], "IDgroupe": couple[1], "etat": etat,
            "heure_debut": unite["heure_debut"] if hd is None else hd,
            "heure_fin": unite["heure_fin"] if hf is None else hf,
            "IDprestation": IDprestation, "IDfacture": IDfacture, "facture_etat": facture_etat}


def ouvert(consos, extra_unites=()):
    """Ouvertures correspondant exactement aux consommations (+ unités supplémentaires)."""
    ouv = {(c["IDactivite"], c["IDunite"], c["IDgroupe"], c["date"]) for c in consos}
    for couple, IDunite, date in extra_unites:
        ouv.add((couple[0], IDunite, couple[1], date))
    return ouv


def calculer(mode, consos, debut=D(2026, 1, 1), fin=D(2026, 12, 31), ouvertures=None, **kw):
    ctx = contexte(mode, ouvertures=ouvertures if ouvertures is not None else ouvert(consos), **kw)
    return M.Calculateur(ctx).Calculer(consos, debut, fin)


def natures(resultat):
    return [a["nature"] for a in resultat["anomalies"]]


class PeriscolaireTests(unittest.TestCase):
    def test_01_bais_plage_1h15(self):
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 101, hd="08:05", hf="08:40")])
        self.assertEqual(r["indicateurs"]["heures_realisees"], H + 15 * 60)
        self.assertEqual(r["indicateurs"]["heures_physiques"], 35 * 60)  # deux grandeurs distinctes
        self.assertFalse(r["bloquant"])

    def test_02_plusieurs_plages_plafond_9h(self):
        consos = [conso(MERCREDI_SCOLAIRE, 107), conso(MERCREDI_SCOLAIRE, 101)]
        r = calculer(M.PERI, consos)
        self.assertEqual(r["indicateurs"]["heures_realisees"], 9 * H)

    def test_02b_trois_plages_additionnees(self):
        consos = [conso(LUNDI_SCOLAIRE, u) for u in (101, 102, 103)]
        self.assertEqual(calculer(M.PERI, consos)["indicateurs"]["heures_realisees"], 5 * H + 15 * 60)

    def test_03_la_guerche_meme_regle(self):
        couples = {GUERCHE: "La Guerche-de-Bretagne"}
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 101, couple=GUERCHE)], couples=couples, equipement="LA_GUERCHE_MOUTIERS")
        self.assertEqual(r["indicateurs"]["heures_realisees"], H + 15 * 60)

    def test_09_reservation_non_pointee_passee_bloquante(self):
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 101, etat="reservation")])
        self.assertEqual(r["indicateurs"]["heures_realisees"], 0)
        self.assertIn("Pointage en attente sur une date passée", natures(r))
        self.assertTrue(r["bloquant"])

    def test_09b_reservation_future_non_comptee_sans_anomalie(self):
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 101, etat="reservation")], date_reference=D(2026, 1, 1))
        self.assertEqual((r["indicateurs"]["heures_realisees"], r["bloquant"]), (0, False))

    def test_absence_non_comptee_en_realise(self):
        for etat in ("absentj", "absenti"):
            with self.subTest(etat=etat):
                r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 101, etat=etat)])
                self.assertEqual(r["indicateurs"]["heures_realisees"], 0)

    def test_10_mercredi_scolaire_retenu(self):
        self.assertEqual(calculer(M.PERI, [conso(MERCREDI_SCOLAIRE, 107)])["indicateurs"]["heures_realisees"], 9 * H)

    def test_11_mercredi_de_vacances_exclu_du_periscolaire(self):
        r = calculer(M.PERI, [conso(MERCREDI_VACANCES, 107)])
        self.assertEqual(r["indicateurs"]["heures_realisees"], 0)
        self.assertEqual(r["lignes"][0]["statut"], "exclue")

    def test_16_garderies_separees_sans_double_comptage(self):
        consos = [conso(LUNDI_SCOLAIRE, u) for u in (105, 101, 103, 106)]
        r = calculer(M.PERI, consos)
        self.assertEqual(r["indicateurs"]["garderie_matin"], 30 * 60)
        self.assertEqual(r["indicateurs"]["garderie_soir"], 30 * 60)
        self.assertEqual(r["indicateurs"]["garderie_total"], H)
        self.assertEqual(r["indicateurs"]["heures_realisees"], 3 * H + 15 * 60)  # garderies non ajoutées

    def test_16b_garderie_incluse_si_choix_explicite(self):
        consos = [conso(LUNDI_SCOLAIRE, u) for u in (105, 101)]
        r = calculer(M.PERI, consos, options={"inclure_garderie_caf": True})
        self.assertEqual(r["indicateurs"]["heures_realisees"], H + 45 * 60)

    def test_17_repas_dans_une_plage_deja_retenue(self):
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 102), conso(LUNDI_SCOLAIRE, 104)])
        self.assertEqual(r["indicateurs"]["heures_realisees"], 2 * H)

    def test_17b_repas_seul_compte_si_temps_repas_inclus(self):
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 104)])
        self.assertEqual(r["indicateurs"]["heures_realisees"], H)
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 104)], options={"inclure_repas_meridien": False})
        self.assertEqual(r["indicateurs"]["heures_realisees"], 0)

    def test_facture_non_applicable_en_periscolaire(self):
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 101)])
        self.assertIsNone(r["indicateurs"]["heures_facturees"])
        self.assertIsNone(r["indicateurs"]["heures_sejours"])


class ExtrascolaireTests(unittest.TestCase):
    def facturee(self, date, IDunite, etat="present", individu=1, prestation=None, **kw):
        prestation = prestation or (900 + _ID[0])
        return conso(date, IDunite, etat=etat, individu=individu, IDprestation=prestation, IDfacture=1, **kw)

    def test_04_amplitude_9h_journee_8h(self):
        r = calculer(M.EXTRA, [self.facturee(LUNDI_VACANCES, 201)])
        self.assertEqual(r["indicateurs"]["heures_facturees"], 8 * H)
        self.assertEqual(r["indicateurs"]["heures_realisees"], 9 * H)  # présence effective, grandeur distincte

    def test_05_amplitude_9h_demi_journee_4h(self):
        consos = [self.facturee(LUNDI_VACANCES, 202)]
        r = calculer(M.EXTRA, consos, ouvertures=ouvert(consos, [(BAIS_PLUS, 201, LUNDI_VACANCES)]))
        self.assertEqual(r["indicateurs"]["heures_facturees"], 4 * H)

    def test_06_amplitude_6h_journee_6h(self):
        couples = {GUERCHE: "La Guerche-de-Bretagne"}
        r = calculer(M.EXTRA, [self.facturee(LUNDI_VACANCES, 206, couple=GUERCHE)], couples=couples)
        self.assertEqual(r["indicateurs"]["heures_facturees"], 6 * H)

    def test_07_amplitude_6h_demi_journee_3h(self):
        consos = [self.facturee(LUNDI_VACANCES, 207)]
        r = calculer(M.EXTRA, consos, ouvertures=ouvert(consos, [(BAIS_PLUS, 206, LUNDI_VACANCES)]))
        self.assertEqual(r["indicateurs"]["heures_facturees"], 3 * H)

    def test_08_absence_facturee_sans_presence(self):
        r = calculer(M.EXTRA, [self.facturee(LUNDI_VACANCES, 201, etat="absenti")])
        self.assertEqual(r["indicateurs"]["heures_facturees"], 8 * H)
        self.assertEqual(r["indicateurs"]["heures_realisees"], 0)

    def test_absence_justifiee_non_facturee(self):
        r = calculer(M.EXTRA, [conso(LUNDI_VACANCES, 201, etat="absentj")])
        self.assertEqual((r["indicateurs"]["heures_facturees"], r["indicateurs"]["heures_realisees"]), (0, 0))

    def test_absence_exclue_du_facture_si_statut_non_retenu(self):
        r = calculer(M.EXTRA, [self.facturee(LUNDI_VACANCES, 201, etat="absentj")], etats_facture=["present"])
        self.assertEqual(r["indicateurs"]["heures_facturees"], 0)

    def test_facture_annulee_non_comptee(self):
        r = calculer(M.EXTRA, [self.facturee(LUNDI_VACANCES, 201, facture_etat="annulation")])
        self.assertEqual(r["indicateurs"]["heures_facturees"], 0)

    def test_non_facturee_non_comptee(self):
        r = calculer(M.EXTRA, [conso(LUNDI_VACANCES, 201)])
        self.assertEqual((r["indicateurs"]["heures_facturees"], r["indicateurs"]["heures_realisees"]), (0, 9 * H))

    def test_deux_demi_journees_equivalent_journee(self):
        consos = [self.facturee(LUNDI_VACANCES, 202), self.facturee(LUNDI_VACANCES, 203)]
        r = calculer(M.EXTRA, consos)
        self.assertEqual(r["indicateurs"]["heures_facturees"], 8 * H)
        self.assertFalse(r["bloquant"])

    def test_journee_et_demi_journee_bloquant(self):
        consos = [self.facturee(LUNDI_VACANCES, 201), self.facturee(LUNDI_VACANCES, 203)]
        r = calculer(M.EXTRA, consos)
        self.assertTrue(r["bloquant"])
        self.assertTrue(any("Facturation supérieure à une journée" in n for n in natures(r)))

    def test_prestation_partagee_comptee_une_fois(self):
        consos = [self.facturee(LUNDI_VACANCES, 202, prestation=500), self.facturee(LUNDI_VACANCES, 203, prestation=500)]
        r = calculer(M.EXTRA, consos)
        self.assertEqual(r["indicateurs"]["heures_facturees"], 4 * H)

    def test_12_samedi_sans_ecole(self):
        r = calculer(M.EXTRA, [self.facturee(SAMEDI_SANS_ECOLE, 201)])
        self.assertEqual(r["indicateurs"]["heures_facturees"], 8 * H)
        self.assertEqual(calculer(M.PERI, [conso(SAMEDI_SANS_ECOLE, 101)])["indicateurs"]["heures_realisees"], 0)

    def test_11b_mercredi_scolaire_exclu_de_l_extrascolaire(self):
        r = calculer(M.EXTRA, [self.facturee(MERCREDI_SCOLAIRE, 201)])
        self.assertEqual(r["indicateurs"]["heures_facturees"], 0)

    def test_dimanche_hors_sejour_non_eligible(self):
        r = calculer(M.EXTRA, [self.facturee(DIMANCHE_SEJOUR, 201)])
        self.assertEqual(r["indicateurs"]["heures_facturees"], 0)
        self.assertIn("Dimanche hors séjour", natures(r))

    def test_18_sortie_supplement_sans_heures_ni_suppression(self):
        consos = [self.facturee(LUNDI_VACANCES, 201), self.facturee(LUNDI_VACANCES, 204)]
        r = calculer(M.EXTRA, consos)
        self.assertEqual((r["indicateurs"]["heures_facturees"], r["indicateurs"]["heures_realisees"]), (8 * H, 9 * H))

    def test_amplitude_inferieure_a_2h_bloquante(self):
        r = calculer(M.EXTRA, [self.facturee(LUNDI_VACANCES, 210)])
        self.assertIn("Amplitude d'ouverture inférieure à 2 h", natures(r))

    def test_unite_horaire_facturee_bloquante(self):
        r = calculer(M.EXTRA, [self.facturee(LUNDI_VACANCES, 208)])
        self.assertIn("Unité horaire facturée en extrascolaire", natures(r))

    def test_presence_sans_horaires_bloquante(self):
        r = calculer(M.EXTRA, [conso(LUNDI_VACANCES, 201, hd="", hf="")])
        self.assertIn("Présence effective sans horaires valides", natures(r))


class SejoursTests(unittest.TestCase):
    SEJOUR = {"id": "camp-2026-10", "libelle": "Minicamp Toussaint", "site": "Minicamps 6/8",
              "date_debut": "2026-10-22", "date_fin": "2026-10-25", "nuits": 3,
              "prevu_declaration_annuelle": True, "integre_projet_educatif": True, "declare_sejour_vacances": False}

    def test_14_sejour_qualifie_10h_par_journee(self):
        consos = [conso(D(2026, 10, j), 205, couple=MINICAMP) for j in (22, 23, 24)]
        r = calculer(M.EXTRA, consos, sejours=[self.SEJOUR])
        self.assertEqual(r["indicateurs"]["heures_sejours"], 30 * H)
        self.assertEqual(r["indicateurs"]["heures_facturees"], 0)  # jamais cumulé avec l'option 2

    def test_13_dimanche_de_sejour_eligible(self):
        r = calculer(M.EXTRA, [conso(DIMANCHE_SEJOUR, 205, couple=MINICAMP)], sejours=[self.SEJOUR])
        self.assertEqual(r["indicateurs"]["heures_sejours"], 10 * H)
        self.assertFalse(r["bloquant"])

    def test_15_sejour_non_qualifie_refuse(self):
        r = calculer(M.EXTRA, [conso(D(2026, 10, 22), 205, couple=MINICAMP)])
        self.assertEqual(r["indicateurs"]["heures_sejours"], 0)
        self.assertIn("Consommation de séjour hors séjour qualifié", natures(r))

    def test_sejour_absent_non_compte(self):
        r = calculer(M.EXTRA, [conso(D(2026, 10, 22), 205, couple=MINICAMP, etat="absenti")], sejours=[self.SEJOUR])
        self.assertEqual(r["indicateurs"]["heures_sejours"], 0)

    def test_sejour_en_periscolaire_bloquant(self):
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 205, couple=MINICAMP)])
        self.assertIn("Unité de séjour en périscolaire", natures(r))


class AnomaliesTests(unittest.TestCase):
    def test_19_deux_consommations_simultanees_meme_unite(self):
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 101), conso(LUNDI_SCOLAIRE, 101)])
        self.assertTrue(r["bloquant"])
        self.assertTrue(any(n.startswith("Même unité saisie deux fois") for n in natures(r)))

    def test_19b_meme_enfant_deux_sites_memes_horaires(self):
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 101), conso(LUNDI_SCOLAIRE, 101, couple=BAIS_MOINS)])
        self.assertTrue(any(n.startswith("Même enfant sur deux sites") for n in natures(r)))

    def test_plusieurs_enfants_memes_creneaux(self):
        consos = [conso(LUNDI_SCOLAIRE, 101, individu=i) for i in (1, 2, 3)]
        r = calculer(M.PERI, consos)
        self.assertEqual((r["indicateurs"]["heures_realisees"], r["bloquant"]), (3 * (H + 15 * 60), False))

    def test_unite_multihoraire_sans_chevauchement_admise(self):
        consos = [conso(LUNDI_SCOLAIRE, 105, hd="07:00", hf="07:15"), conso(LUNDI_SCOLAIRE, 105, hd="07:20", hf="07:30")]
        self.assertFalse(calculer(M.PERI, consos)["bloquant"])

    def test_26_calendrier_absent_bloquant(self):
        r = calculer(M.PERI, [conso(D(2027, 10, 13), 107)], debut=D(2027, 1, 1), fin=D(2027, 12, 31))
        self.assertIn("Calendrier des vacances absent pour l'année scolaire", natures(r))
        self.assertEqual(r["indicateurs"]["heures_realisees"], 0)

    def test_sans_ouverture_bloquant(self):
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 101)], ouvertures=set())
        self.assertIn("Consommation un jour sans ouverture de l'unité pour ce groupe", natures(r))

    def test_statut_inconnu_ou_null_bloquant(self):
        for etat in (None, "", "xyz"):
            with self.subTest(etat=etat):
                r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 101, etat=etat)])
                self.assertTrue(r["bloquant"])

    def test_etats_techniques_exclus(self):
        for etat in ("attente", "refus"):
            with self.subTest(etat=etat):
                r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 101, etat=etat)])
                self.assertEqual((r["indicateurs"]["heures_realisees"], r["bloquant"]), (0, False))

    def test_unite_non_classee_ou_a_qualifier_bloquante(self):
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 209)])
        self.assertIn("Unité à qualifier", natures(r))
        inconnue = conso(LUNDI_SCOLAIRE, 101)
        inconnue["IDunite"] = 999
        r = calculer(M.PERI, [inconnue])
        self.assertIn("Unité non classée dans le preset", natures(r))

    def test_hors_couple_ignore(self):
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 101, couple=(1, 99)), conso(LUNDI_SCOLAIRE, 101, couple=(2, 11))])
        self.assertEqual((r["indicateurs"]["heures_realisees"], r["lignes"]), (0, []))

    def test_rapport_anomalie_complet(self):
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 101, etat="xyz")])
        anomalie = r["anomalies"][0]
        for champ in ("date", "IDindividu", "IDconso", "IDactivite", "IDgroupe", "IDunite", "unite", "site", "nature", "consequence"):
            self.assertIn(champ, anomalie)


class AEEHTests(unittest.TestCase):
    def test_20_droit_ouvert_en_cours_d_annee(self):
        consos = [conso(D(2026, 3, 9), 101), conso(LUNDI_SCOLAIRE, 101)]
        r = calculer(M.PERI, consos, aeeh={1: [(D(2026, 6, 1), None)]})
        self.assertEqual(r["indicateurs"]["heures_realisees"], 2 * (H + 15 * 60))
        self.assertEqual(r["indicateurs"]["heures_realisees_aeeh"], H + 15 * 60)

    def test_20b_droit_ferme_en_cours_d_annee(self):
        consos = [conso(D(2026, 3, 9), 101), conso(LUNDI_SCOLAIRE, 101)]
        r = calculer(M.PERI, consos, aeeh={1: [(D(2026, 1, 1), D(2026, 5, 31))]})
        self.assertEqual(r["indicateurs"]["heures_realisees_aeeh"], H + 15 * 60)

    def test_complement_inclusif_presence_effective_et_arrondi(self):
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 101, hd="07:40", hf="08:20")], aeeh={1: [(D(2026, 1, 1), None)]})
        self.assertEqual(r["indicateurs"]["complement_inclusif_brut"], 40 * 60)
        self.assertEqual(r["indicateurs"]["complement_inclusif_arrondi"], H)

    def test_absence_facturee_aeeh(self):
        c = conso(LUNDI_VACANCES, 201, etat="absenti", IDprestation=77, IDfacture=1)
        r = calculer(M.EXTRA, [c], aeeh={1: [(D(2026, 1, 1), None)]})
        self.assertEqual((r["indicateurs"]["heures_facturees_aeeh"], r["indicateurs"]["heures_realisees_aeeh"],
                          r["indicateurs"]["complement_inclusif_brut"]), (8 * H, 0, 0))

    def test_sous_totaux_jamais_superieurs(self):
        consos = [conso(LUNDI_VACANCES, 201, individu=i, IDprestation=600 + i, IDfacture=1) for i in (1, 2)]
        r = calculer(M.EXTRA, consos, aeeh={1: [(D(2026, 1, 1), None)]})
        self.assertLessEqual(r["indicateurs"]["heures_realisees_aeeh"], r["indicateurs"]["heures_realisees"])
        self.assertLessEqual(r["indicateurs"]["heures_facturees_aeeh"], r["indicateurs"]["heures_facturees"])


class ContexteTests(unittest.TestCase):
    def test_statuts_et_categories_valides(self):
        with self.assertRaises(ValueError):
            M.Calculateur(contexte(M.PERI, etats_realise=[]))
        unites = dict(UNITES)
        unites[301] = {"nom": "X", "heure_debut": "08:00", "heure_fin": "09:00", "categorie": "garderie"}
        with self.assertRaises(M.ContexteInvalide):
            M.Calculateur(contexte(M.PERI, unites=unites))
        with self.assertRaises(M.ContexteInvalide):
            M.Calculateur(contexte("ados"))


if __name__ == "__main__":
    unittest.main()
