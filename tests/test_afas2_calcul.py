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
from test_afas2_calendrier import SAMEDIS_FICTIFS, VACANCES_FICTIVES  # noqa: E402

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
    211: {"nom": "Repas extra", "type": "Unitaire", "heure_debut": "12:00", "heure_fin": "13:30", "categorie": "repas"},
}
# Plages réellement organisées déclarées dans le preset (identiques aux horaires Noethys).
for _unite in UNITES.values():
    if _unite["categorie"] in M.CATEGORIES_A_PLAGE:
        _unite["plage_declaree"] = "%s-%s" % (_unite["heure_debut"], _unite["heure_fin"])

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
        "options": {}, "calendrier": K.Calendrier(VACANCES_FICTIVES), "samedis_avec_ecole": SAMEDIS_FICTIFS,
        "ouvertures": ouvertures if ouvertures is not None else set(),
        "aeeh": {}, "sejours": [], "date_reference": D(2027, 1, 15),
    }
    ctx.update(kw)
    return ctx


_ID = [0]


def conso(date, IDunite, couple=BAIS_PLUS, etat="present", individu=1, hd=None, hf=None, IDprestation=None,
          IDfacture=None, facture_etat=None, **prestation):
    _ID[0] += 1
    unite = UNITES[IDunite]
    resultat = {"IDconso": _ID[0], "IDindividu": individu, "date": date, "IDunite": IDunite,
                "IDactivite": couple[0], "IDgroupe": couple[1], "etat": etat,
                "heure_debut": unite["heure_debut"] if hd is None else hd,
                "heure_fin": unite["heure_fin"] if hf is None else hf, "quantite": None,
                "IDprestation": IDprestation, "IDfacture": IDfacture, "facture_etat": facture_etat,
                "IDfamille": 1000 + individu, "prestation_montant": 12.5 if IDprestation else None,
                "prestation_forfait": None, "prestation_forfait_debut": None,
                "prestation_IDindividu": individu if IDprestation else None}
    resultat.update(prestation)
    return resultat


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
        # Ouverture continue grâce au temps de repas organisé entre les deux demi-journées.
        r = calculer(M.EXTRA, consos, ouvertures=ouvert(consos, [(BAIS_PLUS, 211, LUNDI_VACANCES)]))
        self.assertEqual(r["indicateurs"]["heures_facturees"], 8 * H)
        self.assertFalse(r["bloquant"])
        # Sans plage intermédiaire organisée : ouverture discontinue, jamais combinée.
        self.assertTrue(calculer(M.EXTRA, consos)["bloquant"])

    def test_journee_et_demi_journee_bloquant(self):
        consos = [self.facturee(LUNDI_VACANCES, 201), self.facturee(LUNDI_VACANCES, 203)]
        r = calculer(M.EXTRA, consos)
        self.assertTrue(r["bloquant"])
        self.assertTrue(any("Facturation supérieure à une journée" in n for n in natures(r)))

    def test_prestation_couvrant_deux_demi_journees_indeterminable(self):
        # Une seule prestation pour matin + après-midi : une journée ou une demi ? Jamais supposé.
        consos = [self.facturee(LUNDI_VACANCES, 202, prestation=500), self.facturee(LUNDI_VACANCES, 203, prestation=500)]
        r = calculer(M.EXTRA, consos, ouvertures=ouvert(consos, [(BAIS_PLUS, 201, LUNDI_VACANCES)]))
        self.assertEqual(r["indicateurs"]["heures_facturees"], 0)
        self.assertTrue(r["bloquant"])
        self.assertTrue(any("nature facturée indéterminable" in n for n in natures(r)))

    def test_prestation_journee_avec_repas_combines(self):
        # Combinaison tarifaire journée + repas : une seule unité journée/demi, la prestation reste justifiable.
        consos = [self.facturee(LUNDI_VACANCES, 201, prestation=501), self.facturee(LUNDI_VACANCES, 211, prestation=501)]
        r = calculer(M.EXTRA, consos)
        self.assertEqual((r["indicateurs"]["heures_facturees"], r["bloquant"]), (8 * H, False))

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
        # Intégrées aux actes ouvrant droit (réalisés et facturés), sans entrer dans la présence physique.
        self.assertEqual((r["indicateurs"]["heures_realisees"], r["indicateurs"]["heures_facturees"],
                          r["indicateurs"]["heures_physiques"]), (30 * H, 30 * H, 0))

    def test_sejour_et_accueil_meme_jour_sans_double_comptage(self):
        jour = D(2026, 10, 22)
        consos = [conso(jour, 205, couple=MINICAMP), conso(jour, 201, couple=MINICAMP, IDprestation=880, IDfacture=1)]
        r = calculer(M.EXTRA, consos, sejours=[self.SEJOUR])
        self.assertIn("Séjour et accueil le même jour pour un enfant", natures(r))
        self.assertTrue(r["bloquant"])

    def test_sejour_et_journee_d_autres_enfants_additionnes(self):
        jour = D(2026, 10, 22)
        consos = [conso(jour, 205, couple=MINICAMP, individu=1), conso(jour, 201, individu=2, IDprestation=881, IDfacture=1)]
        r = calculer(M.EXTRA, consos, sejours=[self.SEJOUR])
        self.assertEqual(r["indicateurs"]["heures_facturees"], 10 * H + 8 * H)
        self.assertEqual(r["indicateurs"]["heures_realisees"], 10 * H + 9 * H)

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
        self.assertIn("Calendrier des vacances incomplet pour l'année scolaire "
                      "(manque : Toussaint, Noël, Hiver, Printemps, Été)", natures(r))
        self.assertEqual(r["indicateurs"]["heures_realisees"], 0)

    def test_26b_periode_de_vacances_manquante_bloquante(self):
        cal = K.Calendrier([p for p in VACANCES_FICTIVES if p[1] != "2027-02-13"])
        r = calculer(M.EXTRA, [conso(D(2027, 2, 17), 201)], debut=D(2027, 1, 1), fin=D(2027, 12, 31), calendrier=cal)
        self.assertIn("Calendrier des vacances incomplet pour l'année scolaire (manque : Hiver)", natures(r))
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

    def test_unite_de_l_autre_mode_non_bloquante_hors_de_son_mode(self):
        # Même activité, mêmes groupes : les unités de vacances non classées dans le preset
        # périscolaire n'y bloquent rien les jours de vacances (et inversement).
        unites = {ID: u for ID, u in UNITES.items() if ID < 200}
        consos = [conso(LUNDI_SCOLAIRE, 101), conso(LUNDI_VACANCES, 201)]
        consos[1]["IDunite"] = 999
        r = calculer(M.PERI, consos, unites=unites)
        self.assertEqual((r["indicateurs"]["heures_realisees"], r["bloquant"]), (H + 15 * 60, False))
        r = calculer(M.EXTRA, [conso(LUNDI_SCOLAIRE, 101, etat="xyz")], unites={ID: u for ID, u in UNITES.items() if ID > 200})
        self.assertFalse(r["bloquant"])
        # Le même défaut un jour du mode déclaré reste bloquant.
        consos = [conso(LUNDI_SCOLAIRE, 101)]
        consos[0]["IDunite"] = 999
        self.assertTrue(calculer(M.PERI, consos)["bloquant"])

    def test_hors_couple_ignore(self):
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 101, couple=(1, 99)), conso(LUNDI_SCOLAIRE, 101, couple=(2, 11))])
        self.assertEqual((r["indicateurs"]["heures_realisees"], r["lignes"]), (0, []))

    def test_rapport_anomalie_complet(self):
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 101, etat="xyz")])
        anomalie = r["anomalies"][0]
        for champ in ("date", "IDindividu", "IDconso", "IDactivite", "IDgroupe", "IDunite", "unite", "site", "nature", "consequence"):
            self.assertIn(champ, anomalie)


class PlagesDeclareesTests(unittest.TestCase):
    """Décision 1 : plages Noethys utilisées seulement si elles correspondent aux plages réellement organisées."""

    def unites(self, IDunite, **modif):
        unites = {ID: dict(u) for ID, u in UNITES.items()}
        unites[IDunite].update(modif)
        return unites

    def test_plage_non_declaree_bloquante(self):
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 101)], unites=self.unites(101, plage_declaree=None))
        self.assertTrue(any("plage réellement organisée non déclarée" in n for n in natures(r)))
        self.assertEqual(r["indicateurs"]["heures_realisees"], 0)

    def test_horaires_noethys_modifies_bloquants(self):
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 101)], unites=self.unites(101, heure_fin="09:15"))
        self.assertTrue(any("différents de la plage déclarée 07:30-08:45" in n for n in natures(r)))
        self.assertEqual(r["indicateurs"]["heures_realisees"], 0)

    def test_horaires_absents_ou_incoherents_bloquants(self):
        for modif in (dict(heure_debut=None), dict(heure_debut="09:00", heure_fin="08:00"), dict(heure_fin="8h45")):
            with self.subTest(modif=modif):
                r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 101)], unites=self.unites(101, **modif))
                self.assertTrue(r["bloquant"])
                self.assertEqual(r["indicateurs"]["heures_realisees"], 0)

    def test_duree_de_pointage_jamais_substituee_a_la_plage(self):
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 103, hd="16:30", hf="22:00")])
        self.assertEqual(r["indicateurs"]["heures_realisees"], 2 * H)

    def test_unite_ouverte_sans_plage_declaree_bloque_l_amplitude(self):
        consos = [conso(LUNDI_VACANCES, 201, IDprestation=700, IDfacture=1)]
        unites = self.unites(211, plage_declaree=None)
        r = calculer(M.EXTRA, consos, unites=unites, ouvertures=ouvert(consos, [(BAIS_PLUS, 211, LUNDI_VACANCES)]))
        self.assertTrue(any(n.startswith("Amplitude d'ouverture indéterminable") for n in natures(r)))


class AmplitudeTests(unittest.TestCase):
    """Décision 2 : amplitude = ouverture effective continue du site de l'enfant."""

    def facturee(self, IDunite, couple=BAIS_PLUS, individu=1):
        return conso(LUNDI_VACANCES, IDunite, couple=couple, individu=individu, IDprestation=7000 + _ID[0], IDfacture=1)

    def test_ouverture_continue_avec_repas(self):
        consos = [self.facturee(202)]
        ouv = ouvert(consos, [(BAIS_PLUS, 211, LUNDI_VACANCES), (BAIS_PLUS, 203, LUNDI_VACANCES)])
        r = calculer(M.EXTRA, consos, ouvertures=ouv)
        self.assertEqual(r["indicateurs"]["heures_facturees"], 4 * H)  # 08:30-17:30 = 9 h -> 4 h
        self.assertEqual(r["jours"][0]["plages_ouverture"], "08:30-17:30")
        self.assertFalse(r["bloquant"])

    def test_ouverture_discontinue_bloquante(self):
        # Matin 08:30-12:00 et après-midi 13:30-17:30 sans plage intermédiaire : pas d'amplitude 08:30-17:30.
        consos = [self.facturee(202)]
        r = calculer(M.EXTRA, consos, ouvertures=ouvert(consos, [(BAIS_PLUS, 203, LUNDI_VACANCES)]))
        self.assertEqual(r["indicateurs"]["heures_facturees"], 0)
        self.assertTrue(any("ouverture discontinue (08:30-12:00, 13:30-17:30)" in n for n in natures(r)))
        self.assertEqual(r["jours"][0]["plages_ouverture"], "08:30-12:00 + 13:30-17:30")

    def test_implantations_jamais_combinees(self):
        # Bais +6 ouvert le matin seulement, Bais -6 l'après-midi seulement : 3 h 30 pour Bais +6, pas 9 h.
        consos = [self.facturee(202)]
        r = calculer(M.EXTRA, consos, ouvertures=ouvert(consos, [(BAIS_MOINS, 203, LUNDI_VACANCES)]))
        self.assertEqual(r["indicateurs"]["heures_facturees"], 3 * H // 2 + 15 * 60)  # demi = amplitude 3 h 30 / 2
        self.assertTrue(any(n.startswith("Amplitudes d'ouverture différentes selon les sites") for n in natures(r)))
        self.assertFalse(r["bloquant"])

    def test_amplitudes_differentes_par_site(self):
        consos = [self.facturee(201), self.facturee(206, couple=BAIS_MOINS, individu=2)]
        r = calculer(M.EXTRA, consos)
        self.assertEqual(r["indicateurs"]["heures_facturees"], 8 * H + 6 * H)
        anomalies = [a for a in r["anomalies"] if a["nature"].startswith("Amplitudes d'ouverture différentes")]
        self.assertEqual(len(anomalies), 1)  # une seule fois par jour
        self.assertIn("Bais +6 ans 08:30-17:30", anomalies[0]["nature"])
        self.assertIn("Bais -6 ans 10:00-16:00", anomalies[0]["nature"])

    def test_equivalences_option_2_strictes(self):
        for IDunite, attendu in ((201, 8 * H), (206, 6 * H)):
            with self.subTest(unite=IDunite):
                r = calculer(M.EXTRA, [self.facturee(IDunite)])
                self.assertEqual(r["indicateurs"]["heures_facturees"], attendu)


class FacturationTests(unittest.TestCase):
    """Décision 3 : chaque journée ou demi-journée retenue est justifiée par la facturation."""

    def facturee(self, IDunite=201, date=LUNDI_VACANCES, individu=1, **kw):
        kw.setdefault("IDprestation", 8000 + _ID[0])
        kw.setdefault("IDfacture", 31)
        return conso(date, IDunite, individu=individu, **kw)

    def regul(self, **kw):
        regul = {"IDprestation": 9001, "IDindividu": 1, "IDfamille": 1001, "IDactivite": 1, "date": D(2026, 11, 5),
                 "montant": -15.0, "label": "Avoir absence", "IDfacture": 40, "facture_etat": None}
        regul.update(kw)
        return regul

    def test_justification_par_prestation_et_facture(self):
        c = self.facturee(IDprestation=8500, IDfacture=31)
        r = calculer(M.EXTRA, [c])
        self.assertEqual(r["jours"][0]["justification_facture"], "journée P8500 F31")
        self.assertEqual((r["lignes"][0]["IDprestation"], r["lignes"][0]["IDfacture"]), (8500, 31))

    def test_montant_jamais_converti_en_heures(self):
        for montant in (0.0, 1.0, 48.0):
            with self.subTest(montant=montant):
                r = calculer(M.EXTRA, [self.facturee(prestation_montant=montant)])
                self.assertEqual((r["indicateurs"]["heures_facturees"], r["bloquant"]), (8 * H, False))

    def test_remise_ne_retire_pas_l_unite(self):
        # Une déduction (remise, aide) réduit le montant, pas l'unité facturée.
        r = calculer(M.EXTRA, [self.facturee(prestation_montant=2.5)])
        self.assertEqual(r["indicateurs"]["heures_facturees"], 8 * H)

    def test_regularisation_non_qualifiee_bloquante(self):
        r = calculer(M.EXTRA, [self.facturee()], regularisations=[self.regul()])
        self.assertTrue(r["bloquant"])
        self.assertTrue(any(n.startswith("Régularisation négative non rattachée") for n in natures(r)))

    def test_avoir_familial_bloquant(self):
        r = calculer(M.EXTRA, [self.facturee()], regularisations=[self.regul(IDindividu=None)])
        self.assertTrue(r["bloquant"])

    def test_regularisation_d_une_autre_famille_ignoree(self):
        r = calculer(M.EXTRA, [self.facturee()], regularisations=[self.regul(IDindividu=None, IDfamille=5555),
                                                                  self.regul(IDindividu=77, IDfamille=5555)])
        self.assertFalse(r["bloquant"])

    def test_regularisation_qualifiee_annulant_la_journee(self):
        c = self.facturee()
        qualifiees = {"9001": {"consommations_annulees": [c["IDconso"]], "justification": "Avoir maladie"}}
        r = calculer(M.EXTRA, [c], regularisations=[self.regul()], regularisations_qualifiees=qualifiees)
        self.assertEqual((r["indicateurs"]["heures_facturees"], r["bloquant"]), (0, False))
        self.assertEqual(r["indicateurs"]["heures_realisees"], 9 * H)  # la présence reste

    def test_regularisation_qualifiee_sans_annulation(self):
        qualifiees = {"9001": {"consommations_annulees": [], "justification": "Remboursement de trop-perçu"}}
        r = calculer(M.EXTRA, [self.facturee()], regularisations=[self.regul()], regularisations_qualifiees=qualifiees)
        self.assertEqual((r["indicateurs"]["heures_facturees"], r["bloquant"]), (8 * H, False))

    def test_regularisation_sans_effet_en_periscolaire(self):
        r = calculer(M.PERI, [conso(LUNDI_SCOLAIRE, 101)], regularisations=[self.regul()])
        self.assertFalse(r["bloquant"])

    def test_annulation_partielle_facture_annulee_puis_refacturee(self):
        annulee = self.facturee(facture_etat="annulation")
        refacturee = self.facturee(individu=2, IDfacture=32)
        r = calculer(M.EXTRA, [annulee, refacturee])
        self.assertEqual(r["indicateurs"]["heures_facturees"], 8 * H)

    def test_quantite_indeterminable_bloquante(self):
        cas = {"prestation de montant négatif": dict(prestation_montant=-12.0),
               "prestation forfaitaire": dict(prestation_forfait=2),
               "forfait daté": dict(prestation_forfait_debut="2026-10-19"),
               "quantité facturée": dict(quantite=2),
               "autre enfant": dict(prestation_IDindividu=99)}
        for motif, modif in cas.items():
            with self.subTest(motif=motif):
                r = calculer(M.EXTRA, [self.facturee(**modif)])
                self.assertEqual(r["indicateurs"]["heures_facturees"], 0)
                self.assertTrue(any(n.startswith("Facturation indéterminable") for n in natures(r)))

    def test_prestation_partagee_entre_deux_jours_bloquante(self):
        consos = [self.facturee(IDprestation=8888), self.facturee(date=D(2026, 10, 20), IDprestation=8888)]
        r = calculer(M.EXTRA, consos)
        self.assertEqual(r["indicateurs"]["heures_facturees"], 0)
        self.assertTrue(any("partagée entre plusieurs jours" in n for n in natures(r)))

    def test_absence_facturee_jamais_presence(self):
        r = calculer(M.EXTRA, [self.facturee(etat="absenti")])
        self.assertEqual((r["indicateurs"]["heures_facturees"], r["indicateurs"]["heures_realisees"],
                          r["indicateurs"]["heures_physiques"]), (8 * H, 0, 0))


class SamedisTests(unittest.TestCase):
    """Décision 4 : samedis avec école identifiés par un calendrier daté."""

    def test_samedi_sans_calendrier_date_bloquant(self):
        r = calculer(M.EXTRA, [conso(SAMEDI_SANS_ECOLE, 201)], samedis_avec_ecole={})
        self.assertTrue(any(n.startswith("Samedi hors vacances : calendrier daté") for n in natures(r)))
        self.assertEqual(r["indicateurs"]["heures_realisees"], 0)

    def test_samedi_avec_ecole_date_periscolaire(self):
        samedi = D(2026, 11, 28)
        self.assertEqual(calculer(M.EXTRA, [conso(samedi, 201)])["indicateurs"]["heures_realisees"], 0)
        self.assertEqual(calculer(M.PERI, [conso(samedi, 101)])["indicateurs"]["heures_realisees"], H + 15 * 60)

    def test_ancienne_option_booleenne_ignoree(self):
        r = calculer(M.PERI, [conso(SAMEDI_SANS_ECOLE, 101)], options={"samedis_avec_ecole": True})
        self.assertEqual(r["indicateurs"]["heures_realisees"], 0)


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


class PerformanceTests(unittest.TestCase):
    def test_annee_complete_volumineuse(self):
        # 120 enfants x 40 jours de vacances, 6 unités ouvertes par jour : calcul en temps borné.
        import time
        jours = [D(2026, 7, 6) + datetime.timedelta(days=i) for i in range(56) if (D(2026, 7, 6) + datetime.timedelta(days=i)).weekday() < 5]
        consos = [conso(j, 201, individu=i, IDprestation=10000 * i + n, IDfacture=1) for i in range(120) for n, j in enumerate(jours)]
        ouvertures = {(1, u, g, j) for j in jours for u in (201, 202, 203) for g in (11, 12)}
        debut = time.time()
        r = calculer(M.EXTRA, consos, ouvertures=ouvertures)
        self.assertEqual(r["indicateurs"]["heures_facturees"], len(consos) * 8 * H)
        self.assertLess(time.time() - debut, 20)


class ContexteTests(unittest.TestCase):
    def test_statuts_et_categories_valides(self):
        with self.assertRaises(ValueError):
            M.Calculateur(contexte(M.PERI, etats_realise=[]))
        for champ, etats in (("etats_realise", ["present", "reservation"]), ("etats_realise", ["present", "absenti"]),
                             ("etats_facture", ["present", "reservation"])):
            with self.subTest(champ=champ, etats=etats), self.assertRaises(ValueError):
                M.Calculateur(contexte(M.PERI, **{champ: etats}))
        unites = dict(UNITES)
        unites[301] = {"nom": "X", "heure_debut": "08:00", "heure_fin": "09:00", "categorie": "garderie"}
        with self.assertRaises(M.ContexteInvalide):
            M.Calculateur(contexte(M.PERI, unites=unites))
        with self.assertRaises(M.ContexteInvalide):
            M.Calculateur(contexte("ados"))


if __name__ == "__main__":
    unittest.main()
