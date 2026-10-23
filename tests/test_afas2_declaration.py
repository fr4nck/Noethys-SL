# -*- coding: utf-8 -*-
"""AFAS V2 -- phases déclaratives, indépendance du preset, historique et exports.

Source de données factice (aucune base) pour les phases ; base SQLite
fictive pour l'historique. Aucune donnée réelle.
"""
import copy
import csv
import datetime
import json
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
for chemin in (RACINE / "noethys", RACINE / "tests"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))

from Utils import UTILS_AFAS as AFAS  # noqa: E402
from Utils import UTILS_AFAS2_Calendrier as K  # noqa: E402
from Utils import UTILS_AFAS2_Declaration as DECL  # noqa: E402
from Utils import UTILS_AFAS2_Presets as P  # noqa: E402

H = 3600
D = datetime.date
VACANCES = []
for annee in range(2023, 2029):  # calendrier fictif régulier et complet, construit pour les tests
    VACANCES += [("Hiver", "%d-02-10" % annee, "%d-02-24" % annee), ("Printemps", "%d-04-14" % annee, "%d-04-28" % annee),
                 ("Eté", "%d-07-05" % annee, "%d-08-31" % annee), ("Toussaint", "%d-10-19" % annee, "%d-11-03" % annee),
                 ("Noël", "%d-12-21" % annee, "%d-01-04" % (annee + 1))]

GROUPES = {11: (1, "Bais +6 ans"), 12: (1, "Bais -6 ans"), 13: (1, "Moutiers"), 14: (1, "La Guerche"), 15: (1, "Minicamps 6/8")}
UNITES = {101: {"IDactivite": 1, "nom": "Matin", "type": "Unitaire", "heure_debut": "07:30", "heure_fin": "08:45"},
          201: {"IDactivite": 1, "nom": "Journée", "type": "Unitaire", "heure_debut": "08:30", "heure_fin": "17:30"}}


def referentiel(**kw):
    def lien(g, e):
        return {"IDactivite": 1, "IDgroupe": g, "nom_groupe": GROUPES[g][1], "equipement": e}
    ref = {"format": 2, "moutiers_rattachement_confirme": False, "sejours": [], "justificatifs": {}, "regularisations": {},
           "samedis_avec_ecole": {str(a): [] for a in range(2023, 2029)}, "sites": {
        "Bais +6 ans": lien(11, "BAIS"), "Bais -6 ans": lien(12, "BAIS"), "Moutiers": lien(13, "LA_GUERCHE_MOUTIERS"),
        "La Guerche-de-Bretagne": lien(14, "LA_GUERCHE_MOUTIERS"), "Minicamps 6/8": lien(15, None)}}
    ref.update(kw)
    return ref


def preset(mode="periscolaire", sites=("Bais +6 ans",), equipement="BAIS"):
    p = P.NouveauPreset("Bais accueil", mode, equipement, sites=list(sites), unites={"101": "accueil", "201": "journee"},
                        plages={"101": "07:30-08:45", "201": "08:30-17:30"})
    return P.ValiderPreset(p)


class SourceFactice(object):
    def __init__(self, consos=(), ouvertures=(), aeeh=None, regularisations=()):
        self.consos = list(consos)
        self.ouvertures = set(ouvertures)
        self.aeeh = aeeh or {}
        self.regularisations = list(regularisations)
        self.fenetre_regularisations = None

    def Regularisations(self, IDactivites, IDindividus, IDfamilles, debut, fin):
        self.fenetre_regularisations = (debut, fin)
        return [dict(r) for r in self.regularisations if debut <= r["date"] <= fin]

    def Groupes(self):
        return dict(GROUPES)

    def Unites(self, IDactivites):
        return copy.deepcopy(UNITES)

    def Consommations(self, couples, debut, fin):
        return [dict(c) for c in self.consos if debut <= c["date"] <= fin and (c["IDactivite"], c["IDgroupe"]) in couples]

    def Ouvertures(self, couples, debut, fin):
        return {o for o in self.ouvertures if debut <= o[3] <= fin and (o[0], o[2]) in couples}

    def AEEH(self, IDindividus):
        return {i: v for i, v in self.aeeh.items() if i in IDindividus}

    def Calendrier(self, debut, fin):
        return K.Calendrier(VACANCES)


_ID = [0]


def peri(date, individu=1, groupe=11, etat="present"):
    _ID[0] += 1
    return {"IDconso": _ID[0], "IDindividu": individu, "individu": "FICTIF", "date": date, "IDunite": 101, "IDactivite": 1,
            "IDgroupe": groupe, "heure_debut": "07:30", "heure_fin": "08:45", "etat": etat,
            "IDprestation": None, "IDfacture": None, "facture_etat": None}


def source_peri(dates, groupe=11, ouvertures_supp=()):
    consos = [peri(d, groupe=groupe) for d in dates]
    ouvertures = {(1, 101, groupe, d) for d in list(dates) + list(ouvertures_supp)}
    return SourceFactice(consos, ouvertures)


def executer(p, annee, phase, source, **kw):
    kw.setdefault("date_reference", D(2030, 1, 1))
    kw.setdefault("maintenant", datetime.datetime(2026, 10, 23, 12, 0, 0))
    return DECL.Executer(p, kw.pop("ref", referentiel()), annee, phase, source=source, **kw)


def ligne(rapport, cle):
    return next(l for l in rapport["indicateurs"] if l["cle"] == cle)


class PhasesTests(unittest.TestCase):
    def test_periodes_des_quatre_phases(self):
        self.assertEqual(DECL.Periodes(2026, AFAS.PHASE_PREVISIONNEL), (None, None, D(2026, 1, 1), D(2026, 12, 31)))
        self.assertEqual(DECL.Periodes(2026, AFAS.PHASE_ACTUALISATION_JUIN), (D(2026, 1, 1), D(2026, 6, 30), D(2026, 7, 1), D(2026, 12, 31)))
        self.assertEqual(DECL.Periodes(2026, AFAS.PHASE_ACTUALISATION_SEPTEMBRE), (D(2026, 1, 1), D(2026, 9, 30), D(2026, 10, 1), D(2026, 12, 31)))
        self.assertEqual(DECL.Periodes(2026, AFAS.PHASE_REEL), (D(2026, 1, 1), D(2026, 12, 31), None, None))
        for annee, phase in ((2026, "octobre"), ("2026", AFAS.PHASE_REEL), (1999, AFAS.PHASE_REEL)):
            with self.subTest(annee=annee, phase=phase), self.assertRaises(DECL.DeclarationImpossible):
                DECL.Periodes(annee, phase)

    def test_22_meme_preset_pour_les_quatre_phases(self):
        p = preset()
        avant = copy.deepcopy(p)
        dates = [D(2026, 6, 30), D(2026, 7, 1), D(2026, 9, 30), D(2026, 10, 1), D(2025, 7, 1), D(2025, 10, 1)]
        source = source_peri(dates)
        attendus = {AFAS.PHASE_ACTUALISATION_JUIN: 1, AFAS.PHASE_ACTUALISATION_SEPTEMBRE: 3, AFAS.PHASE_REEL: 4}
        for phase, nombre in attendus.items():
            with self.subTest(phase=phase):
                r = executer(p, 2026, phase, source)
                self.assertEqual(ligne(r, "heures_realisees")["realise"], nombre * (H + 15 * 60))
        r = executer(p, 2026, AFAS.PHASE_PREVISIONNEL, source)
        self.assertIsNone(r["periode_realise"])
        self.assertEqual(p, avant)  # le preset n'est jamais modifié

    def test_21_meme_preset_de_2025_a_2027(self):
        p = preset()
        source = source_peri([D(2025, 3, 3), D(2026, 3, 3), D(2027, 3, 3)])
        for annee in (2025, 2026, 2027):
            with self.subTest(annee=annee):
                r = executer(p, annee, AFAS.PHASE_REEL, source)
                self.assertEqual((r["convention"], r["validable"]), ("PERI_BAIS_2025_2027", True))
                self.assertEqual(ligne(r, "heures_realisees")["realise"], H + 15 * 60)
                self.assertEqual(r["preset"], p)

    def test_periode_realisee_non_terminee_non_validable(self):
        source = source_peri([D(2026, 3, 3)])
        r = executer(preset(), 2026, AFAS.PHASE_REEL, source, date_reference=D(2026, 10, 23))
        self.assertFalse(r["validable"])
        self.assertTrue(any("non terminée" in m for m in r["motifs_non_validable"]))
        r = executer(preset(), 2026, AFAS.PHASE_ACTUALISATION_JUIN, source_peri(
            [D(2026, 3, 3)], ouvertures_supp=[D(2025, 7, 7), D(2026, 7, 7)]), date_reference=D(2026, 10, 23))
        self.assertTrue(r["validable"])

    def test_convention_jamais_etendue_hors_2025_2027(self):
        r = executer(preset(), 2028, AFAS.PHASE_REEL, source_peri([D(2028, 3, 6)]))
        self.assertIsNone(r["convention"])
        self.assertFalse(r["validable"])

    def test_prevision_n1_ajustee_aux_jours_ouverts(self):
        # N-1 : 2 jours ouverts, 2 présences ; N : 4 jours ouverts programmés.
        source = source_peri([D(2025, 10, 6), D(2025, 10, 7)],
                             ouvertures_supp=[D(2026, 10, 5), D(2026, 10, 6), D(2026, 10, 7), D(2026, 10, 8)])
        r = executer(preset(), 2026, AFAS.PHASE_ACTUALISATION_SEPTEMBRE, source)
        self.assertEqual(ligne(r, "heures_realisees")["prevision"], 4 * (H + 15 * 60))
        self.assertEqual((r["jours_ouverts_n1"], r["jours_ouverts_prevision"]), (2, 4))

    def test_prevision_n1_impossible_sans_historique(self):
        source = source_peri([], ouvertures_supp=[D(2026, 10, 5)])
        with self.assertRaisesRegex(DECL.DeclarationImpossible, "N-1"):
            executer(preset(), 2026, AFAS.PHASE_ACTUALISATION_SEPTEMBRE, source)
        with self.assertRaisesRegex(DECL.DeclarationImpossible, "Aucun jour d'ouverture programmé"):
            executer(preset(), 2026, AFAS.PHASE_ACTUALISATION_SEPTEMBRE, source_peri([]))

    def test_prevision_n1_bloquee_par_anomalies(self):
        source = source_peri([D(2025, 10, 6)], ouvertures_supp=[D(2026, 10, 5)])
        source.consos[0]["etat"] = "xyz"
        with self.assertRaisesRegex(DECL.DeclarationImpossible, "anomalies bloquantes"):
            executer(preset(), 2026, AFAS.PHASE_ACTUALISATION_SEPTEMBRE, source)

    def test_prevision_manuelle_controlee(self):
        valeurs = {"heures_realisees": "10,5", "heures_facturees": 0, "heures_realisees_aeeh": 1, "heures_facturees_aeeh": 0}
        r = executer(preset(), 2026, AFAS.PHASE_PREVISIONNEL, source_peri([]), methode=DECL.METHODE_MANUELLE,
                     valeurs_manuelles=valeurs)
        self.assertEqual(ligne(r, "heures_realisees")["total"], int(10.5 * H))
        self.assertEqual(ligne(r, "heures_physiques")["prevision"], "non_qualifie")  # jamais un zéro trompeur
        self.assertIsNone(ligne(r, "heures_facturees")["total"])  # non applicable en périscolaire
        for mauvais in ({}, dict(valeurs, heures_realisees="-1"), dict(valeurs, heures_realisees="nan"),
                        dict(valeurs, heures_realisees_aeeh=20)):
            with self.subTest(mauvais=mauvais), self.assertRaises(DECL.DeclarationImpossible):
                executer(preset(), 2026, AFAS.PHASE_PREVISIONNEL, source_peri([]), methode=DECL.METHODE_MANUELLE,
                         valeurs_manuelles=mauvais)


class ValidabiliteTests(unittest.TestCase):
    def test_28_moutiers_sans_rattachement_confirme(self):
        p = preset(sites=("Moutiers",), equipement="LA_GUERCHE_MOUTIERS")
        r = executer(p, 2026, AFAS.PHASE_REEL, source_peri([D(2026, 3, 3)], groupe=13))
        self.assertFalse(r["validable"])
        self.assertTrue(any("Moutiers" in m for m in r["motifs_non_validable"]))
        # Confirmation sans formulaire d'implantation référencé : toujours non validable.
        r = executer(p, 2026, AFAS.PHASE_REEL, source_peri([D(2026, 3, 3)], groupe=13),
                     ref=referentiel(moutiers_rattachement_confirme=True))
        self.assertFalse(r["validable"])
        r = executer(p, 2026, AFAS.PHASE_REEL, source_peri([D(2026, 3, 3)], groupe=13),
                     ref=referentiel(moutiers_rattachement_confirme=True,
                                     justificatifs={"Moutiers": "Formulaire d'implantation fictif"}))
        self.assertTrue(r["validable"])
        self.assertEqual(r["justificatifs"], {"Moutiers": "Formulaire d'implantation fictif"})

    def test_minicamp_sans_equipement_non_validable(self):
        p = preset(mode="extrascolaire", sites=("Bais +6 ans", "Minicamps 6/8"))
        r = executer(p, 2026, AFAS.PHASE_REEL, SourceFactice())
        self.assertFalse(r["validable"])

    def test_site_non_relie_ou_autre_equipement(self):
        ref = referentiel()
        del ref["sites"]["Bais -6 ans"]
        with self.assertRaisesRegex(DECL.DeclarationImpossible, "relié"):
            executer(preset(sites=("Bais -6 ans",)), 2026, AFAS.PHASE_REEL, SourceFactice(), ref=ref)
        ref = referentiel()
        ref["sites"]["Minicamps 6/8"]["equipement"] = "LA_GUERCHE_MOUTIERS"
        with self.assertRaisesRegex(DECL.DeclarationImpossible, "mélangés"):
            executer(preset(mode="extrascolaire", sites=("Bais +6 ans", "Minicamps 6/8")), 2026, AFAS.PHASE_REEL,
                     SourceFactice(), ref=ref)

    def test_unite_du_preset_supprimee_de_noethys(self):
        p = preset()
        p["unites"]["999"] = "accueil"
        p["plages_declarees"]["999"] = "07:30-08:45"
        with self.assertRaisesRegex(DECL.DeclarationImpossible, "n'existe plus"):
            executer(p, 2026, AFAS.PHASE_REEL, SourceFactice())

    def test_anomalie_bloquante_interdit_l_export_declaratif(self):
        source = source_peri([D(2026, 3, 3)])
        source.consos[0]["etat"] = "xyz"
        r = executer(preset(), 2026, AFAS.PHASE_REEL, source)
        self.assertFalse(r["validable"])
        with tempfile.TemporaryDirectory() as dossier:
            with self.assertRaises(DECL.DeclarationImpossible):
                DECL.ExporterDeclaration(dossier, r, "afas")
            chemins = DECL.ExporterControle(dossier, r, "afas")
            with open(chemins["anomalies"], encoding="utf-8-sig") as f:
                lignes = list(csv.reader(f, delimiter=";"))
            self.assertEqual(lignes[1][9], "Statut de consommation inconnu ou absent : 'xyz'")


def extra(date, individu=1, groupe=11, unite=201, etat="present", **kw):
    _ID[0] += 1
    c = {"IDconso": _ID[0], "IDindividu": individu, "individu": "FICTIF", "date": date, "IDunite": unite, "IDactivite": 1,
         "IDgroupe": groupe, "heure_debut": "08:30", "heure_fin": "17:30", "etat": etat, "quantite": None,
         "IDprestation": 5000 + _ID[0], "prestation_montant": 15.0, "prestation_forfait": None,
         "prestation_forfait_debut": None, "prestation_IDindividu": individu, "IDfamille": 100 + individu,
         "IDfacture": 70, "facture_etat": None}
    c.update(kw)
    return c


class ExtrascolaireDeclarationTests(unittest.TestCase):
    JOUR = D(2026, 10, 21)  # mercredi de vacances (calendrier fictif)

    def source(self, consos, **kw):
        return SourceFactice(consos, {(1, c["IDunite"], c["IDgroupe"], c["date"]) for c in consos}, **kw)

    def test_extrascolaire_validable_avec_justification(self):
        r = executer(preset(mode="extrascolaire"), 2026, AFAS.PHASE_REEL, self.source([extra(self.JOUR)]))
        self.assertTrue(r["validable"], r["motifs_non_validable"])
        self.assertEqual(ligne(r, "heures_facturees")["realise"], 8 * H)
        self.assertTrue(r["jours"][0]["justification_facture"].startswith("journée P"))

    def test_regularisations_recherchees_apres_la_periode(self):
        source = self.source([extra(self.JOUR)], regularisations=[
            {"IDprestation": 9100, "IDindividu": 1, "IDfamille": 101, "IDactivite": 1, "date": D(2027, 1, 20),
             "montant": -15.0, "label": "Avoir", "IDfacture": None, "facture_etat": None}])
        r = executer(preset(mode="extrascolaire"), 2026, AFAS.PHASE_REEL, source)
        self.assertEqual(source.fenetre_regularisations, (D(2026, 1, 1), D(2027, 4, 2)))
        self.assertFalse(r["validable"])
        qualifiee = referentiel(regularisations={"9100": {"consommations_annulees": [source.consos[0]["IDconso"]],
                                                          "justification": "Avoir pour absence maladie (fictif)"}})
        r = executer(preset(mode="extrascolaire"), 2026, AFAS.PHASE_REEL, source, ref=qualifiee)
        self.assertTrue(r["validable"], r["motifs_non_validable"])
        self.assertEqual(ligne(r, "heures_facturees")["realise"], 0)
        self.assertIn("9100", r["regularisations_qualifiees"])

    def test_sejours_integres_mais_rubrique_non_confirmee(self):
        p = P.NouveauPreset("Bais extrascolaire", "extrascolaire", "BAIS", sites=["Bais +6 ans"],
                            unites={"201": "journee", "205": "sejour"}, plages={"201": "08:30-17:30"})
        sejour = {"id": "s1", "libelle": "Minicamp fictif", "site": "Bais +6 ans", "date_debut": "2026-10-21",
                  "date_fin": "2026-10-23", "nuits": 2, "prevu_declaration_annuelle": True,
                  "integre_projet_educatif": True, "declare_sejour_vacances": False}
        unites = dict(UNITES)
        unites[205] = {"IDactivite": 1, "nom": "Minicamp", "type": "Unitaire", "heure_debut": None, "heure_fin": None}
        source = self.source([extra(self.JOUR, unite=205)])
        source.Unites = lambda IDactivites: copy.deepcopy(unites)
        r = executer(P.ValiderPreset(p), 2026, AFAS.PHASE_REEL, source, ref=referentiel(sejours=[sejour]))
        self.assertEqual((ligne(r, "heures_sejours")["realise"], ligne(r, "heures_realisees")["realise"],
                          ligne(r, "heures_facturees")["realise"]), (10 * H, 10 * H, 10 * H))
        self.assertFalse(r["validable"])
        self.assertTrue(any("rubrique AFAS des séjours" in m for m in r["motifs_non_validable"]))
        with tempfile.TemporaryDirectory() as dossier:
            DECL.ExporterControle(dossier, r, "afas")  # le contrôle reste exportable
            with self.assertRaises(DECL.DeclarationImpossible):
                DECL.ExporterDeclaration(dossier, r, "afas")

    def test_samedi_sans_calendrier_date_bloquant(self):
        ref = referentiel(samedis_avec_ecole={})
        r = executer(preset(mode="extrascolaire"), 2026, AFAS.PHASE_REEL, self.source([extra(D(2026, 10, 10))]), ref=ref)
        self.assertFalse(r["validable"])
        self.assertTrue(r["bloquant"])

    def test_nature_des_indicateurs_dans_la_synthese(self):
        r = executer(preset(mode="extrascolaire"), 2026, AFAS.PHASE_REEL, self.source([extra(self.JOUR)]))
        self.assertEqual(ligne(r, "complement_inclusif_arrondi")["nature"], "hypothèse")
        with tempfile.TemporaryDirectory() as dossier:
            chemins = DECL.ExporterDeclaration(dossier, r, "afas")
            with open(chemins["synthese"], encoding="utf-8-sig") as f:
                textes = {l[0]: l[1:] for l in csv.reader(f, delimiter=";") if l}
            self.assertEqual(textes["Heures facturées CAF"], ["déclaratif", "8,00", "0,00", "8,00"])
            self.assertEqual(textes["Complément inclusif : arrondi à l'heure supérieure par jour (hypothèse)"][0], "hypothèse")
            with open(chemins["jours"], encoding="utf-8-sig") as f:
                jours = list(csv.reader(f, delimiter=";"))
            self.assertEqual(jours[1][4], "08:30-17:30")


class ExportsEtHistoriqueTests(unittest.TestCase):
    def test_29_export_avec_empreinte_et_instantane(self):
        r = executer(preset(), 2026, AFAS.PHASE_REEL, source_peri([D(2026, 3, 3)]))
        self.assertTrue(r["validable"])
        with tempfile.TemporaryDirectory() as dossier:
            chemins = DECL.ExporterDeclaration(dossier, r, "afas")
            with open(chemins["synthese"], encoding="utf-8-sig") as f:
                synthese = list(csv.reader(f, delimiter=";"))
            textes = {ligne[0]: ligne[1:] for ligne in synthese if ligne}
            self.assertEqual(textes["Empreinte de la déclaration"], [r["empreinte"]])
            self.assertEqual(textes["Empreinte du preset"], [r["empreinte_preset"]])
            self.assertEqual(textes["Convention"], ["PERI_BAIS_2025_2027"])
            self.assertEqual(textes["Heures de présence conventionnelles CAF"], ["déclaratif", "1,25", "0,00", "1,25"])
            self.assertEqual(textes["Heures facturées CAF"], ["déclaratif"] + ["non applicable"] * 3)
            with open(chemins["instantane"], encoding="utf-8") as f:
                instantane = json.load(f)
            self.assertEqual(instantane["preset"]["preset_id"], r["preset"]["preset_id"])
            self.assertNotIn("annee", instantane["preset"])
            with open(chemins["detail"], encoding="utf-8-sig") as f:
                self.assertEqual(len(list(csv.reader(f, delimiter=";"))), 2)

    def test_empreinte_reproductible(self):
        source = source_peri([D(2026, 3, 3)])
        p = preset()
        premiere = executer(p, 2026, AFAS.PHASE_REEL, source)["empreinte"]
        self.assertEqual(premiere, executer(p, 2026, AFAS.PHASE_REEL, source)["empreinte"])
        self.assertNotEqual(premiere, executer(p, 2026, AFAS.PHASE_ACTUALISATION_JUIN, source_peri(
            [D(2026, 3, 3)], ouvertures_supp=[D(2025, 7, 7), D(2026, 7, 7)]))["empreinte"])

    def test_resume_historique_borne(self):
        source = source_peri([D(2026, 3, 2) + datetime.timedelta(days=i) for i in range(0, 300) if
                              (D(2026, 3, 2) + datetime.timedelta(days=i)).weekday() < 5])
        for c in source.consos:
            c["etat"] = "xyz"
        r = executer(preset(), 2026, AFAS.PHASE_REEL, source)
        resume = DECL.ResumeHistorique(r)
        self.assertLessEqual(len(json.dumps(resume, ensure_ascii=False)), 30000)
        self.assertTrue(resume.get("anomalies_tronquees"))


class HistoriqueBaseTests(unittest.TestCase):
    def setUp(self):
        import _garde_reseau  # noqa: F401
        from _fixtures_noethys_db import BaseTest, RedirectionGestionDB
        from Data import DATA_Tables as Tables
        self.base = BaseTest()
        for table in ("profils", "profils_parametres"):
            self.base.db.CreationTable(table, dicoDB=Tables.DB_DATA)
        self.base.db.Commit()
        self.redirection = RedirectionGestionDB(self.base.chemin)
        self.redirection.__enter__()
        self.addCleanup(self.redirection.__exit__)
        self.addCleanup(self.base.fermer)

    def test_historique_independant_du_preset_et_integre(self):
        p = preset()
        IDpreset, p = P.EnregistrerPreset(p)
        r = executer(p, 2026, AFAS.PHASE_REEL, source_peri([D(2026, 3, 3)]))
        IDhisto = DECL.EnregistrerHistorique(r)
        p["sites"] = ["Bais -6 ans"]
        P.EnregistrerPreset(p, IDpreset)  # le preset évolue ensuite
        archive = DECL.ChargerHistorique(IDhisto)
        self.assertTrue(archive["integrite"])
        self.assertEqual(archive["preset"]["sites"], ["Bais +6 ans"])
        self.assertEqual(archive["empreinte"], r["empreinte"])
        self.base.db.ExecuterReq("UPDATE profils_parametres SET parametre=replace(parametre, '\"annee\": 2026', '\"annee\": 2025') "
                                 "WHERE IDprofil=%d;" % IDhisto)
        self.base.db.Commit()
        self.assertFalse(DECL.ChargerHistorique(IDhisto)["integrite"])
        self.assertEqual(len(DECL.ListerHistorique()), 1)


if __name__ == "__main__":
    unittest.main()
