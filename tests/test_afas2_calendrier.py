# -*- coding: utf-8 -*-
"""AFAS V2 -- périodes d'accueil (conventions art. 1.1) et statuts.

Calendrier de vacances fictif construit pour les tests (aucun calendrier
officiel n'est supposé). Le cœur est testé sans wx ni base ; le chargement
depuis Noethys est testé sur une base SQLite fictive.
"""
import datetime
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
for chemin in (RACINE / "noethys", RACINE / "tests"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))

from Utils import UTILS_AFAS2_Calendrier as K  # noqa: E402

D = datetime.date
VACANCES_FICTIVES = [
    ("Eté", "2025-07-05", "2025-08-31"),
    ("Toussaint", "2025-10-18", "2025-11-02"),
    ("Noël", "2025-12-20", "2026-01-04"),
    ("Hiver", "2026-02-14", "2026-03-01"),
    ("Printemps", "2026-04-11", "2026-04-26"),
    ("Eté", "2026-07-04", "2026-08-31"),
    ("Toussaint", "2026-10-17", "2026-11-01"),
    ("Noël", "2026-12-19", "2027-01-03"),
    ("Hiver", "2027-02-13", "2027-02-28"),
    ("Printemps", "2027-04-10", "2027-04-25"),
    ("Eté", "2027-07-03", "2027-08-31"),
]


def calendrier():
    return K.Calendrier(VACANCES_FICTIVES)


class ModeDateTests(unittest.TestCase):
    def test_mercredi_scolaire(self):
        self.assertEqual(K.ModeDate(D(2026, 10, 14), calendrier()), K.PERISCOLAIRE)

    def test_mercredi_de_vacances(self):
        self.assertEqual(K.ModeDate(D(2026, 10, 21), calendrier()), K.EXTRASCOLAIRE)

    def test_lundi_scolaire_et_lundi_de_vacances(self):
        self.assertEqual(K.ModeDate(D(2026, 10, 12), calendrier()), K.PERISCOLAIRE)
        self.assertEqual(K.ModeDate(D(2026, 10, 19), calendrier()), K.EXTRASCOLAIRE)

    def test_samedi_sans_ecole_extrascolaire(self):
        self.assertEqual(K.ModeDate(D(2026, 10, 10), calendrier()), K.EXTRASCOLAIRE)

    def test_samedi_avec_ecole_si_declare(self):
        self.assertEqual(K.ModeDate(D(2026, 10, 10), calendrier(), samedis_avec_ecole=True), K.PERISCOLAIRE)

    def test_dimanche_jamais_periscolaire(self):
        for jour in (D(2026, 10, 11), D(2026, 10, 25)):
            with self.subTest(jour=jour):
                self.assertEqual(K.ModeDate(jour, calendrier()), K.DIMANCHE)

    def test_limites_exactes_des_vacances(self):
        cal = calendrier()
        self.assertEqual(K.ModeDate(D(2026, 10, 16), cal), K.PERISCOLAIRE)   # vendredi veille
        self.assertEqual(K.ModeDate(D(2026, 10, 17), cal), K.EXTRASCOLAIRE)  # 1er jour (samedi)
        self.assertEqual(K.ModeDate(D(2026, 10, 30), cal), K.EXTRASCOLAIRE)  # dernier vendredi
        self.assertEqual(K.ModeDate(D(2026, 11, 2), cal), K.PERISCOLAIRE)    # lundi de rentrée

    def test_frontieres_juin_juillet_septembre_octobre(self):
        cal = calendrier()
        self.assertEqual(K.ModeDate(D(2026, 6, 30), cal), K.PERISCOLAIRE)
        self.assertEqual(K.ModeDate(D(2026, 7, 6), cal), K.EXTRASCOLAIRE)
        self.assertEqual(K.ModeDate(D(2026, 9, 30), cal), K.PERISCOLAIRE)
        self.assertEqual(K.ModeDate(D(2026, 10, 1), cal), K.PERISCOLAIRE)

    def test_passage_31_decembre_1er_janvier(self):
        cal = calendrier()
        self.assertEqual(K.ModeDate(D(2026, 12, 31), cal), K.EXTRASCOLAIRE)
        self.assertEqual(K.ModeDate(D(2027, 1, 1), cal), K.EXTRASCOLAIRE)
        self.assertEqual(K.ModeDate(D(2027, 1, 4), cal), K.PERISCOLAIRE)

    def test_calendrier_absent_jamais_scolaire_par_defaut(self):
        # Année scolaire 2027-2028 sans vacances saisies : inconnu, pas périscolaire.
        self.assertEqual(K.ModeDate(D(2027, 10, 13), calendrier()), K.INCONNU)
        self.assertEqual(K.ModeDate(D(2028, 7, 12), calendrier()), K.INCONNU)

    def test_calendrier_partiel_sans_ete(self):
        cal = K.Calendrier([p for p in VACANCES_FICTIVES if p[1] != "2027-07-03"])
        self.assertEqual(K.ModeDate(D(2026, 10, 14), cal), K.INCONNU)

    def test_ete_rattache_a_l_annee_qui_s_acheve(self):
        self.assertEqual(K.AnneeScolaire(D(2026, 7, 15)), 2025)
        self.assertEqual(K.AnneeScolaire(D(2026, 9, 1)), 2026)

    def test_detail_des_periodes(self):
        segments = K.DetailPeriodes(D(2026, 10, 15), D(2026, 10, 19), calendrier())
        self.assertEqual([s[2] for s in segments], [K.PERISCOLAIRE, K.EXTRASCOLAIRE, K.DIMANCHE, K.EXTRASCOLAIRE])
        self.assertEqual(segments[1][:2], (D(2026, 10, 17), D(2026, 10, 17)))

    def test_periode_incoherente_refusee(self):
        with self.assertRaises(ValueError):
            K.Calendrier([("Erreur", "2026-10-20", "2026-10-10")])


class StatutsTests(unittest.TestCase):
    def test_codes_et_libelles(self):
        self.assertEqual(K.CODES_STATUTS, ("reservation", "present", "absentj", "absenti"))
        self.assertEqual(K.LIBELLES_STATUTS["reservation"], "Pointage en attente")

    def test_defauts_independants(self):
        self.assertEqual(K.ETATS_REALISE_DEFAUT, ("present",))
        self.assertNotIn("reservation", K.ETATS_FACTURE_DEFAUT)

    def test_classement(self):
        self.assertEqual(K.ClasserStatut("present"), "admis")
        self.assertEqual(K.ClasserStatut("refus"), "technique")
        self.assertEqual(K.ClasserStatut("attente"), "technique")
        for etat in (None, "", "xyz", "PRESENT"):
            with self.subTest(etat=etat):
                self.assertEqual(K.ClasserStatut(etat), "inconnu")

    def test_validation_des_selections(self):
        self.assertEqual(K.ValiderEtats(["present", "absenti"], "Facturé"), ["present", "absenti"])
        for etats in ([], None, ["present", "present"], ["refus"], ["xyz"], "present"):
            with self.subTest(etats=etats), self.assertRaises(ValueError):
                K.ValiderEtats(etats, "Réalisé")


class ChargementNoethysTests(unittest.TestCase):
    def setUp(self):
        import _garde_reseau  # noqa: F401
        from _fixtures_noethys_db import BaseTest, RedirectionGestionDB
        from Data import DATA_Tables as Tables
        self.base = BaseTest()
        self.base.db.CreationTable("vacances", dicoDB=Tables.DB_DATA)
        self.base.inserer("vacances", ["IDvacance", "nom", "annee", "date_debut", "date_fin"],
                          [(i, nom, int(debut[:4]), debut, fin) for i, (nom, debut, fin) in enumerate(VACANCES_FICTIVES, 1)])
        self.base.db.Commit()
        self.redirection = RedirectionGestionDB(self.base.chemin)
        self.redirection.__enter__()
        self.addCleanup(self.redirection.__exit__)
        self.addCleanup(self.base.fermer)

    def test_lecture_de_la_table_vacances(self):
        cal = K.ChargerCalendrier(D(2026, 1, 1), D(2026, 12, 31))
        self.assertEqual(K.ModeDate(D(2026, 10, 21), cal), K.EXTRASCOLAIRE)
        self.assertEqual(K.ModeDate(D(2026, 10, 14), cal), K.PERISCOLAIRE)
        self.assertEqual(K.ModeDate(D(2027, 10, 13), cal), K.INCONNU)


if __name__ == "__main__":
    unittest.main()
