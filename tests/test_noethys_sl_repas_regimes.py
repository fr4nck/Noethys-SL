# -*- coding: utf-8 -*-
"""Lot 1 #430 : repartition exclusive des regimes, donnees fictives uniquement."""
import copy
import sqlite3
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
from Utils import UTILS_Repas_regimes as R  # noqa: E402
from Utils import UTILS_Repas_source  # noqa: E402
from Utils import UTILS_Repas_alimentaires, UTILS_Repas_validation  # noqa: E402

JOUR = date(2026, 11, 4)
ENFANT = date(2018, 1, 1)     # 8 ans
PETIT = date(2022, 1, 1)      # 4 ans
ADULTE = date(1990, 1, 1)
CHOIX = {"standard": 11, "sans_porc": 12, "vegetarien": 13}
SERVICES = {(1, 10): ("Site A", "midi"), (2, 10): ("Site A", "midi"),
            (1, 20): ("Site A", "gouter"), (3, 30): ("Site B", "midi")}


def conso(individu, groupe=1, unite=10, etat="reservation", jour=JOUR):
    return {"date": jour, "IDindividu": individu, "IDgroupe": groupe, "IDunite": unite, "etat": etat}


def repartir(consos, reponses, naissances=None, services=SERVICES):
    if naissances is None:
        naissances = dict((c["IDindividu"], ENFANT) for c in consos)
    return R.RepartitionRegimes(consos, reponses, CHOIX, services, naissances)


class RepartitionTests(unittest.TestCase):
    def test_exemple_42_8_5_egal_55(self):
        consos, reponses = [], {}
        for i in range(50):
            consos.append(conso(i))
            reponses[i] = "11" if i < 40 else ("12" if i < 47 else "13")
        entree = repartir(consos, reponses)[(JOUR, "Site A", "midi")]
        self.assertEqual((entree["standard"], entree["sans_porc"], entree["vegetarien"],
                          entree["non_renseignes"], entree["total_repas"]), (40, 7, 3, 0, 50))
        total = R.IntegrerAdultes(entree, 5, {"standard": 2, "sans_porc": 1, "vegetarien": 2})
        self.assertEqual((total["standard"], total["sans_porc"], total["vegetarien"],
                          total["non_renseignes"], total["total_repas"], total["dont_adultes"]),
                         (42, 8, 5, 0, 55, 5))
        self.assertEqual(sum(total[c] for c in R.CHAMPS), total["total_repas"])

    def test_absence_jamais_standard(self):
        entree = repartir([conso(1), conso(2), conso(3)], {1: None, 2: "", 3: " ; "})[(JOUR, "Site A", "midi")]
        self.assertEqual((entree["standard"], entree["non_renseignes"], entree["total_repas"]), (0, 3, 3))

    def test_choix_inconnu_ou_contradictoire_refuses(self):
        for reponse in ("99", "11;12", "abc", "12.0"):
            with self.subTest(reponse=reponse), self.assertRaises(R.RegimeInvalide):
                repartir([conso(1)], {1: reponse})
        self.assertEqual(repartir([conso(1)], {1: "12;12"})[(JOUR, "Site A", "midi")]["sans_porc"], 1)

    def test_message_non_nominatif(self):
        with self.assertRaises(R.RegimeInvalide) as ctx:
            repartir([conso(1234), conso(5678)], {1234: "99", 5678: "11;13"})
        self.assertIn("1 inconnue(s), 1 contradictoire(s)", str(ctx.exception))
        self.assertNotIn("1234", str(ctx.exception))

    def test_doublons_groupes_unites_etats(self):
        consos = [conso(1), conso(1, etat="present"), conso(1, groupe=2), conso(2, groupe=2)]
        entree = repartir(consos, {1: "12", 2: "11"})[(JOUR, "Site A", "midi")]
        self.assertEqual((entree["total_repas"], entree["sans_porc"], entree["standard"]), (2, 1, 1))

    def test_annulation_absence_attente_exclues(self):
        consos = [conso(1), conso(2, etat="absenti"), conso(3, etat="absentj"),
                  conso(4, etat="attente"), conso(5, etat="refus")]
        resultat = repartir(consos, {i: "11" for i in range(1, 6)})
        self.assertEqual(resultat[(JOUR, "Site A", "midi")]["total_repas"], 1)
        # Consommation supprimee : rien a compter.
        self.assertEqual(repartir([], {1: "11"}), {})

    def test_unite_non_parametree_ignoree(self):
        self.assertEqual(repartir([conso(1, groupe=9)], {1: "11"}), {})

    def test_sites_et_services_distincts(self):
        consos = [conso(1), conso(1, unite=20), conso(2, groupe=3, unite=30), conso(3), conso(3, groupe=3, unite=30)]
        resultat = repartir(consos, {1: "13", 2: "12", 3: "11"})
        self.assertEqual(sorted(resultat), [(JOUR, "Site A", "gouter"), (JOUR, "Site A", "midi"),
                                            (JOUR, "Site B", "midi")])
        self.assertEqual(resultat[(JOUR, "Site A", "gouter")]["vegetarien"], 1)
        self.assertEqual(resultat[(JOUR, "Site A", "midi")]["total_repas"], 2)
        # Personne 3 sur deux sites au meme service : signalee de chaque cote.
        self.assertEqual(resultat[(JOUR, "Site A", "midi")]["multisites"], 1)
        self.assertEqual(resultat[(JOUR, "Site B", "midi")]["multisites"], 1)
        self.assertEqual(resultat[(JOUR, "Site A", "gouter")]["multisites"], 0)

    def test_dates_distinctes(self):
        consos = [conso(1), conso(1, jour=date(2026, 11, 5))]
        self.assertEqual(len(repartir(consos, {1: "11"})), 2)

    def test_adulte_avec_consommation_signale_hors_total(self):
        naissances = {1: ENFANT, 2: ADULTE, 3: PETIT}
        entree = repartir([conso(1), conso(2), conso(3)], {1: "11", 2: "13", 3: "12"},
                          naissances)[(JOUR, "Site A", "midi")]
        self.assertEqual((entree["total_repas"], entree["vegetarien"], entree["adultes_avec_conso"]), (2, 0, 1))
        self.assertTrue(entree["complet"])
        # Anniversaire des 18 ans le jour du repas : adulte.
        majeur = repartir([conso(4)], {4: "11"}, {4: date(2008, 11, 4)})[(JOUR, "Site A", "midi")]
        self.assertEqual((majeur["adultes_avec_conso"], majeur["total_repas"]), (1, 0))

    def test_age_inconnu_rend_la_suggestion_incomplete(self):
        entree = repartir([conso(1), conso(2)], {1: "11", 2: "11"}, {1: ENFANT, 2: None})[(JOUR, "Site A", "midi")]
        self.assertFalse(entree["complet"])
        self.assertEqual((entree["ages_inconnus"], entree["total_repas"]), (1, 1))

    def test_consommation_invalide(self):
        with self.assertRaises(ValueError):
            repartir([conso(None)], {})
        with self.assertRaises(ValueError):
            repartir([conso(1, jour="2026-11-04")], {1: "11"})


class ConfigurationTests(unittest.TestCase):
    def test_liste_deroulante_seule(self):
        self.assertEqual(R.ConfigurationRegimes("5", {"standard": "11", "sans_porc": 12, "vegetarien": 13},
                                                "liste_deroulante"), (5, CHOIX))
        for controle in ("liste_coches", "case_coche", "ligne_texte", None):
            with self.subTest(controle=controle), self.assertRaises(ValueError):
                R.ConfigurationRegimes(5, CHOIX, controle)

    def test_correspondance_complete_distincte_et_positive(self):
        invalides = [{"standard": 11, "sans_porc": 12},
                     {"standard": 11, "sans_porc": 11, "vegetarien": 13},
                     {"standard": 11, "sans_porc": 12, "vegetarien": 0},
                     {"standard": 11, "sans_porc": True, "vegetarien": 13},
                     dict(CHOIX, halal=14), None]
        for correspondance in invalides:
            with self.subTest(correspondance=correspondance), self.assertRaises(ValueError):
                R.ConfigurationRegimes(5, correspondance, "liste_deroulante")
        for question in (0, -1, None, "x", True):
            with self.subTest(question=question), self.assertRaises(ValueError):
                R.ConfigurationRegimes(question, CHOIX, "liste_deroulante")

    def test_cle_site_service_non_ambigue(self):
        with self.assertRaises(ValueError):
            R.NormaliserServices({(1, 10): ("Site A", "midi"), (2, 10): ("site a", "midi")})
        with self.assertRaises(ValueError):
            R.NormaliserServices({(1, 10): ("Site A", " ")})
        self.assertEqual(R.NormaliserServices({("1", "10"): (" Site A ", "midi")}), {(1, 10): ("Site A", "midi")})


class AdultesEtInvariantTests(unittest.TestCase):
    ENTREE = {"standard": 3, "sans_porc": 1, "vegetarien": 0, "non_renseignes": 1, "total_repas": 5}

    def test_adultes_non_classes_non_renseignes(self):
        total = R.IntegrerAdultes(self.ENTREE, 4)
        self.assertEqual((total["standard"], total["non_renseignes"], total["total_repas"]), (3, 5, 9))
        partiel = R.IntegrerAdultes(self.ENTREE, 4, {"vegetarien": 1})
        self.assertEqual((partiel["vegetarien"], partiel["non_renseignes"]), (1, 4))

    def test_adultes_refus(self):
        for adultes, classes in ((1, {"standard": 2}), (2, {"halal": 1}), (-1, {}), ("2.5", {}), (2, {"standard": -1})):
            with self.subTest(adultes=adultes, classes=classes), self.assertRaises(ValueError):
                R.IntegrerAdultes(self.ENTREE, adultes, classes)

    def test_invariant_detecte_une_incoherence(self):
        with self.assertRaises(ValueError):
            R.VerifierInvariant(dict(self.ENTREE, total_repas=6))
        with self.assertRaises(ValueError):
            R.IntegrerAdultes(dict(self.ENTREE, total_repas=4), 0)

    def test_changement_de_preference_apres_validation_non_applique(self):
        validee = {(JOUR, "Site A", "midi"): R.IntegrerAdultes(
            repartir([conso(1), conso(2)], {1: "11", 2: "11"})[(JOUR, "Site A", "midi")], 0)}
        copie = copy.deepcopy(validee)
        actuelle = repartir([conso(1), conso(2)], {1: "11", 2: "13"})
        ecarts = R.EcartsAvecCommande(validee, actuelle)
        self.assertEqual(validee, copie)
        self.assertIn(((JOUR, "Site A", "midi"), "standard", 2, 1), ecarts)
        self.assertIn(((JOUR, "Site A", "midi"), "vegetarien", 0, 1), ecarts)
        self.assertEqual(R.EcartsAvecCommande(validee, validee), [])


class CompatibiliteTests(unittest.TestCase):
    def test_anciens_modeles_sans_porc_inchanges(self):
        self.assertEqual(UTILS_Repas_validation.ROLES,
                         ("moins_6", "six_plus", "animateurs", "direction", "autres_adultes", "sans_porc"))
        resultat = UTILS_Repas_alimentaires.CompterSansPorc(
            [conso(1), conso(2), conso(3)], {1: "12", 2: "11"}, [(1, 10)], 12, "liste_deroulante")
        self.assertEqual(resultat[JOUR], {"sans_porc": 1, "repas": 3, "non_renseignes": 1})


class BaseFictive:
    def __init__(self, controle="liste_deroulante", type_categorie="Individu"):
        self.db = sqlite3.connect(":memory:")
        self.requetes, self.results, self.closed = [], [], False
        self.db.executescript("""
            CREATE TABLE questionnaire_categories (IDcategorie INTEGER PRIMARY KEY, type TEXT);
            CREATE TABLE questionnaire_questions (IDquestion INTEGER PRIMARY KEY, IDcategorie INTEGER, controle TEXT);
            CREATE TABLE questionnaire_choix (IDchoix INTEGER PRIMARY KEY, IDquestion INTEGER);
            CREATE TABLE questionnaire_reponses (IDreponse INTEGER PRIMARY KEY, IDquestion INTEGER,
                                                 IDindividu INTEGER, reponse TEXT);
            CREATE TABLE individus (IDindividu INTEGER PRIMARY KEY, date_naiss TEXT);
            CREATE TABLE consommations (date TEXT, IDgroupe INTEGER, IDunite INTEGER, IDindividu INTEGER, etat TEXT);
            INSERT INTO questionnaire_choix VALUES (11, 5), (12, 5), (13, 5), (21, 6);
            INSERT INTO individus VALUES (1, '2018-01-01'), (2, '2018-01-01'), (3, '1990-01-01'), (4, '2018-01-01');
            INSERT INTO questionnaire_reponses VALUES (1, 5, 1, '12'), (2, 5, 2, '13'), (3, 5, 3, '13');
            INSERT INTO consommations VALUES ('2026-11-04', 1, 10, 1, 'reservation'),
                ('2026-11-04', 1, 10, 1, 'present'), ('2026-11-04', 2, 10, 2, 'present'),
                ('2026-11-04', 1, 10, 3, 'present'), ('2026-11-04', 1, 10, 4, 'reservation'),
                ('2026-11-04', 1, 10, 5, 'absenti'), ('2026-11-04', 9, 10, 6, 'present');
        """)
        self.db.execute("INSERT INTO questionnaire_categories VALUES (7, ?)", (type_categorie,))
        self.db.execute("INSERT INTO questionnaire_questions VALUES (5, 7, ?)", (controle,))

    def ExecuterReq(self, req):
        self.requetes.append(req)
        self.results = self.db.execute(req).fetchall()
        return True

    def ResultatReq(self):
        return self.results

    def Close(self):
        self.closed = True


class SourceSQLiteTests(unittest.TestCase):
    def charger(self, base, choix=CHOIX):
        self.addCleanup(base.db.close)
        with patch.object(UTILS_Repas_source.GestionDB, "DB", return_value=base):
            return UTILS_Repas_source.ChargerRepartitionRegimes(
                5, choix, {(1, 10): ("Site A", "midi"), (2, 10): ("Site A", "midi")}, JOUR, JOUR)

    def test_lecture_groupee_reelle(self):
        base = BaseFictive()
        entree = self.charger(base)[(JOUR, "Site A", "midi")]
        self.assertEqual((entree["sans_porc"], entree["vegetarien"], entree["non_renseignes"],
                          entree["standard"], entree["total_repas"], entree["adultes_avec_conso"]),
                         (1, 1, 1, 0, 3, 1))
        self.assertTrue(base.closed)
        self.assertEqual(len(base.requetes), 4)
        self.assertTrue(all(q.lstrip().startswith("SELECT") for q in base.requetes))

    def test_refus_question_non_conforme(self):
        for base in (BaseFictive(controle="liste_coches"), BaseFictive(type_categorie="Famille")):
            with self.subTest(), self.assertRaises(ValueError):
                self.charger(base)

    def test_refus_choix_d_une_autre_question(self):
        with self.assertRaises(ValueError):
            self.charger(BaseFictive(), dict(CHOIX, vegetarien=21))

    def test_reponses_en_double_refusees(self):
        base = BaseFictive()
        base.db.execute("INSERT INTO questionnaire_reponses VALUES (9, 5, 1, '11')")
        with self.assertRaises(R.RegimeInvalide):
            self.charger(base)
        self.assertTrue(base.closed)

    def test_aucune_unite(self):
        with patch.object(UTILS_Repas_source.GestionDB, "DB") as db:
            self.assertEqual(UTILS_Repas_source.ChargerRepartitionRegimes(5, CHOIX, {}, JOUR, JOUR), {})
        db.assert_not_called()


if __name__ == "__main__":
    unittest.main()
