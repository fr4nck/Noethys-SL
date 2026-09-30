# -*- coding: utf-8 -*-
"""Caractérisation de UTILS_Ouvertures.GetDatesOuverture / GetNombreJoursOuverture.

Contexte : `ouvertures` contient une ligne par (IDactivite, IDunite,
IDgroupe, date) -- plusieurs unités ouvertes le même jour pour le même
périmètre produisent plusieurs lignes ce jour-là (démontré sur la base
PMSL réelle : ratio lignes/jours de x2,5 à x6 selon l'accueil). Le nombre
de jours ouverts d'un périmètre (IDactivite, IDgroupe) n'est donc jamais
un COUNT(*), mais un COUNT(DISTINCT date).

Ces tests utilisent une fixture DB générique (IDs arbitraires) -- aucun ID
PMSL réel n'est codé en dur ici ni dans le module testé.
"""
from __future__ import annotations

import datetime
import sys
import unittest
from pathlib import Path

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

from _fixtures_noethys_db import BaseTest, RedirectionGestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402

from Utils import UTILS_Ouvertures  # noqa: E402


class GetDatesOuvertureTests(unittest.TestCase):
    def setUp(self):
        self.base = BaseTest()
        self.base.db.CreationTable("ouvertures", dicoDB=Tables.DB_DATA)
        self.base.db.Commit()
        self.addCleanup(self.base.fermer)

        self._redirection = RedirectionGestionDB(self.base.chemin)
        self._redirection.__enter__()
        self.addCleanup(self._redirection.__exit__)

    def _inserer_ouvertures(self, lignes):
        """ lignes : liste de (IDactivite, IDunite, IDgroupe, date). """
        self.base.inserer(
            "ouvertures",
            ["IDactivite", "IDunite", "IDgroupe", "date"],
            lignes,
        )
        self.base.db.Commit()

    def test_1_une_date_avec_cinq_unites_ouvertes_ne_donne_quune_seule_date(self):
        self._inserer_ouvertures([
            (10, 1, 1, "2026-03-10"),
            (10, 2, 1, "2026-03-10"),
            (10, 3, 1, "2026-03-10"),
            (10, 4, 1, "2026-03-10"),
            (10, 5, 1, "2026-03-10"),
        ])
        dates = UTILS_Ouvertures.GetDatesOuverture(10, 1, "2026-03-01", "2026-03-31")
        self.assertEqual(dates, [datetime.date(2026, 3, 10)])

    def test_2_deux_dates_distinctes_donnent_deux_dates(self):
        self._inserer_ouvertures([
            (10, 1, 1, "2026-03-10"),
            (10, 1, 1, "2026-03-11"),
        ])
        dates = UTILS_Ouvertures.GetDatesOuverture(10, 1, "2026-03-01", "2026-03-31")
        self.assertEqual(dates, [datetime.date(2026, 3, 10), datetime.date(2026, 3, 11)])

    def test_3_deux_groupes_de_la_meme_activite_le_meme_jour_restent_separes(self):
        self._inserer_ouvertures([
            (10, 1, 1, "2026-03-10"),   # groupe 1
            (10, 1, 2, "2026-03-10"),   # groupe 2, même activité, même jour
            (10, 1, 2, "2026-03-11"),   # groupe 2 uniquement
        ])
        dates_groupe1 = UTILS_Ouvertures.GetDatesOuverture(10, 1, "2026-03-01", "2026-03-31")
        dates_groupe2 = UTILS_Ouvertures.GetDatesOuverture(10, 2, "2026-03-01", "2026-03-31")
        self.assertEqual(dates_groupe1, [datetime.date(2026, 3, 10)])
        self.assertEqual(dates_groupe2, [datetime.date(2026, 3, 10), datetime.date(2026, 3, 11)])

    def test_4_deux_activites_le_meme_jour_restent_separees(self):
        self._inserer_ouvertures([
            (10, 1, 1, "2026-03-10"),   # activité 10
            (20, 1, 1, "2026-03-10"),   # activité 20, même groupe, même jour
            (20, 1, 1, "2026-03-11"),   # activité 20 uniquement
        ])
        dates_act10 = UTILS_Ouvertures.GetDatesOuverture(10, 1, "2026-03-01", "2026-03-31")
        dates_act20 = UTILS_Ouvertures.GetDatesOuverture(20, 1, "2026-03-01", "2026-03-31")
        self.assertEqual(dates_act10, [datetime.date(2026, 3, 10)])
        self.assertEqual(dates_act20, [datetime.date(2026, 3, 10), datetime.date(2026, 3, 11)])

    def test_5_bornes_date_debut_date_fin_respectees(self):
        self._inserer_ouvertures([
            (10, 1, 1, "2026-02-28"),   # avant la période
            (10, 1, 1, "2026-03-01"),   # borne basse incluse
            (10, 1, 1, "2026-03-15"),   # dans la période
            (10, 1, 1, "2026-03-31"),   # borne haute incluse
            (10, 1, 1, "2026-04-01"),   # après la période
        ])
        dates = UTILS_Ouvertures.GetDatesOuverture(10, 1, "2026-03-01", "2026-03-31")
        self.assertEqual(dates, [datetime.date(2026, 3, 1), datetime.date(2026, 3, 15), datetime.date(2026, 3, 31)])

    def test_6_periode_sans_ouverture_donne_une_liste_vide(self):
        self._inserer_ouvertures([
            (10, 1, 1, "2026-03-10"),
        ])
        dates = UTILS_Ouvertures.GetDatesOuverture(10, 1, "2026-06-01", "2026-06-30")
        self.assertEqual(dates, [])

    def test_7_resultats_tries_et_sans_doublon(self):
        # Insertion volontairement désordonnée, avec plusieurs unités par date
        # (doublons de date à éliminer) et une unité de plus sur le 11.
        self._inserer_ouvertures([
            (10, 3, 1, "2026-03-15"),
            (10, 1, 1, "2026-03-10"),
            (10, 2, 1, "2026-03-10"),
            (10, 1, 1, "2026-03-11"),
            (10, 2, 1, "2026-03-11"),
            (10, 3, 1, "2026-03-11"),
        ])
        dates = UTILS_Ouvertures.GetDatesOuverture(10, 1, "2026-03-01", "2026-03-31")
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(len(dates), len(set(dates)))
        self.assertEqual(dates, [datetime.date(2026, 3, 10), datetime.date(2026, 3, 11), datetime.date(2026, 3, 15)])

    def test_ne_filtre_jamais_par_idunite(self):
        """ Une seule unité ouverte suffit -- pas de condition implicite sur IDunite. """
        self._inserer_ouvertures([
            (10, 99, 1, "2026-03-10"),
        ])
        dates = UTILS_Ouvertures.GetDatesOuverture(10, 1, "2026-03-01", "2026-03-31")
        self.assertEqual(dates, [datetime.date(2026, 3, 10)])


class GetNombreJoursOuvertureTests(unittest.TestCase):
    def setUp(self):
        self.base = BaseTest()
        self.base.db.CreationTable("ouvertures", dicoDB=Tables.DB_DATA)
        self.base.db.Commit()
        self.addCleanup(self.base.fermer)

        self._redirection = RedirectionGestionDB(self.base.chemin)
        self._redirection.__enter__()
        self.addCleanup(self._redirection.__exit__)

    def test_nombre_jours_ouverture_egale_longueur_de_la_liste_des_dates(self):
        self.base.inserer(
            "ouvertures",
            ["IDactivite", "IDunite", "IDgroupe", "date"],
            [
                (10, 1, 1, "2026-03-10"),
                (10, 2, 1, "2026-03-10"),
                (10, 3, 1, "2026-03-10"),
                (10, 1, 1, "2026-03-11"),
                (10, 1, 1, "2026-03-12"),
            ],
        )
        self.base.db.Commit()

        dates = UTILS_Ouvertures.GetDatesOuverture(10, 1, "2026-03-01", "2026-03-31")
        nombre = UTILS_Ouvertures.GetNombreJoursOuverture(10, 1, "2026-03-01", "2026-03-31")

        self.assertEqual(nombre, len(dates))
        self.assertEqual(nombre, 3)  # 5 lignes brutes, 3 jours distincts -- jamais 5


if __name__ == "__main__":
    unittest.main()
