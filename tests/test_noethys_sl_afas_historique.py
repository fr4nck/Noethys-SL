# -*- coding: utf-8 -*-
"""Caractérisation de UTILS_AFAS_Historique.ConstruireHistoriquePerimetre.

Vérifie uniquement que l'adaptateur assemble, pour un même périmètre
(IDactivite, IDgroupe), la liste d'historique multi-années attendue par
UTILS_AFAS.EstimerPeriode/ConstruireComparaison à partir de
UTILS_AFAS_Perimetre.GetDonneesPerimetre -- aucune règle d'estimation
CAF/AFAS n'est testée ici (déjà couverte par test_noethys_sl_afas.py),
aucun ID PMSL réel n'est utilisé.
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

from Utils import UTILS_AFAS  # noqa: E402
from Utils import UTILS_AFAS_Historique  # noqa: E402


TABLES_SUPPLEMENTAIRES = ("vacances", "evenements", "etiquettes", "comptes_payeurs", "categories_tarifs", "ouvertures")


class ConstruireHistoriquePerimetreTests(unittest.TestCase):
    def setUp(self):
        self.base = BaseTest()
        for nom_table in TABLES_SUPPLEMENTAIRES:
            self.base.db.CreationTable(nom_table, dicoDB=Tables.DB_DATA)

        self.base.inserer("regimes", ["IDregime", "nom"], [(1, "Régime Général")])
        self.base.inserer("caisses", ["IDcaisse", "nom", "IDregime"], [(1, "CAF Test", 1)])
        self.base.inserer("familles", ["IDfamille", "IDcaisse"], [(1, 1)])
        self.base.inserer("comptes_payeurs", ["IDcompte_payeur", "IDfamille"], [(1, 1)])
        date_naiss = str(datetime.date.today().replace(year=datetime.date.today().year - 10))
        self.base.inserer(
            "individus",
            ["IDindividu", "nom", "prenom", "IDcivilite", "date_naiss"],
            [(1, "DUPONT", "Enfant A", 1, date_naiss), (2, "MARTIN", "Enfant B", 1, date_naiss)],
        )
        self.base.inserer("activites", ["IDactivite", "nom"], [(10, "Activite A"), (20, "Activite B")])
        self.base.inserer(
            "vacances",
            ["IDvacance", "nom", "annee", "date_debut", "date_fin"],
            [
                (1, "Annee 2023", 2023, "2023-01-01", "2023-12-31"),
                (2, "Annee 2024", 2024, "2024-01-01", "2024-12-31"),
                (3, "Annee 2025", 2025, "2025-01-01", "2025-12-31"),
            ],
        )
        self.base.db.Commit()

        self._redirection = RedirectionGestionDB(self.base.chemin)
        self._redirection.__enter__()
        self.addCleanup(self._redirection.__exit__)
        self.addCleanup(self.base.fermer)

    def _options(self, **overrides):
        options = {
            "regroupement_principal": "aucun",
            "regroupement_age": [],
            "periodes_detaillees": False,
            "jours_hors_vacances": [0, 1, 2, 3, 4, 5, 6],
            "jours_vacances": [0, 1, 2, 3, 4, 5, 6],
            "etat_consommations": ["reservation", "present", "absentj", "absenti"],
            "plafond_journalier_individu": 0,
            "associer_regime_inconnu": "non",
            "tranches_qf_perso": [],
        }
        options.update(overrides)
        return options

    def _unite(self, IDunite, IDactivite):
        return {
            "IDunite": IDunite, "IDactivite": IDactivite, "nomUnite": "Unite", "nomActivite": "Activite",
            "typeCalcul": 1, "coeff": None, "arrondi": None,
            "duree_plafond": None, "duree_seuil": None,
            "heure_plafond": None, "heure_seuil": None, "formule": None,
        }

    def test_une_annee_historique(self):
        # Une seule conso en 2025 (année N-1 par rapport à annee_reference=2026).
        self.base.inserer(
            "consommations",
            ["IDconso", "IDindividu", "IDunite", "date", "heure_debut", "heure_fin", "etat", "quantite", "IDactivite", "IDprestation", "IDcompte_payeur", "IDgroupe"],
            [(1, 1, 51, "2025-03-10", "08:00", "10:00", "present", None, 10, None, 1, 1)],  # 2h
        )
        self.base.db.Commit()
        self.base.inserer(
            "ouvertures",
            ["IDactivite", "IDunite", "IDgroupe", "date"],
            [(10, 51, 1, "2025-03-10")],
        )
        self.base.db.Commit()

        dictUnites = {51: self._unite(51, IDactivite=10)}
        historique = UTILS_AFAS_Historique.ConstruireHistoriquePerimetre(
            IDactivite=10, IDgroupe=1, annee_reference=2026, nombre_annees=1,
            dictUnites=dictUnites, dict_options=self._options(),
        )

        self.assertEqual(historique, [{"heures": 2.0, "jours_ouverts": 1}])

    def test_plusieurs_annees_ordre_plus_recent_au_plus_ancien(self):
        # 2025 (N-1) : 2h/1j -- 2024 (N-2) : 3h/1j -- 2023 (N-3) : 4h/1j.
        self.base.inserer(
            "consommations",
            ["IDconso", "IDindividu", "IDunite", "date", "heure_debut", "heure_fin", "etat", "quantite", "IDactivite", "IDprestation", "IDcompte_payeur", "IDgroupe"],
            [
                (1, 1, 51, "2025-03-10", "08:00", "10:00", "present", None, 10, None, 1, 1),  # 2h
                (2, 1, 51, "2024-03-10", "08:00", "11:00", "present", None, 10, None, 1, 1),  # 3h
                (3, 1, 51, "2023-03-10", "08:00", "12:00", "present", None, 10, None, 1, 1),  # 4h
            ],
        )
        self.base.db.Commit()
        self.base.inserer(
            "ouvertures",
            ["IDactivite", "IDunite", "IDgroupe", "date"],
            [
                (10, 51, 1, "2025-03-10"),
                (10, 51, 1, "2024-03-10"),
                (10, 51, 1, "2023-03-10"),
            ],
        )
        self.base.db.Commit()

        dictUnites = {51: self._unite(51, IDactivite=10)}
        historique = UTILS_AFAS_Historique.ConstruireHistoriquePerimetre(
            IDactivite=10, IDgroupe=1, annee_reference=2026, nombre_annees=3,
            dictUnites=dictUnites, dict_options=self._options(),
        )

        self.assertEqual(historique, [
            {"heures": 2.0, "jours_ouverts": 1},  # 2025 = N-1
            {"heures": 3.0, "jours_ouverts": 1},  # 2024 = N-2
            {"heures": 4.0, "jours_ouverts": 1},  # 2023 = N-3
        ])

    def test_periode_vide(self):
        dictUnites = {51: self._unite(51, IDactivite=10)}
        historique = UTILS_AFAS_Historique.ConstruireHistoriquePerimetre(
            IDactivite=10, IDgroupe=1, annee_reference=2026, nombre_annees=2,
            dictUnites=dictUnites, dict_options=self._options(),
        )

        self.assertEqual(historique, [
            {"heures": 0.0, "jours_ouverts": 0},
            {"heures": 0.0, "jours_ouverts": 0},
        ])

    def test_isolation_activite_et_groupe(self):
        # Même année (2025), même IDunite, mais activité/groupe différents : ne doit pas se mélanger.
        self.base.inserer(
            "consommations",
            ["IDconso", "IDindividu", "IDunite", "date", "heure_debut", "heure_fin", "etat", "quantite", "IDactivite", "IDprestation", "IDcompte_payeur", "IDgroupe"],
            [
                (1, 1, 51, "2025-03-10", "08:00", "10:00", "present", None, 10, None, 1, 1),  # activite 10, groupe 1 : 2h
                (2, 2, 51, "2025-03-10", "08:00", "17:00", "present", None, 10, None, 1, 2),  # activite 10, groupe 2 : 9h
                (3, 1, 61, "2025-03-10", "08:00", "14:00", "present", None, 20, None, 1, 1),  # activite 20, groupe 1 : 6h
            ],
        )
        self.base.db.Commit()
        self.base.inserer(
            "ouvertures",
            ["IDactivite", "IDunite", "IDgroupe", "date"],
            [
                (10, 51, 1, "2025-03-10"),
                (10, 51, 2, "2025-03-10"),
                (20, 61, 1, "2025-03-10"),
            ],
        )
        self.base.db.Commit()

        dictUnites_10 = {51: self._unite(51, IDactivite=10)}
        dictUnites_20 = {61: self._unite(61, IDactivite=20)}

        historique_groupe1 = UTILS_AFAS_Historique.ConstruireHistoriquePerimetre(
            IDactivite=10, IDgroupe=1, annee_reference=2026, nombre_annees=1,
            dictUnites=dictUnites_10, dict_options=self._options(),
        )
        historique_groupe2 = UTILS_AFAS_Historique.ConstruireHistoriquePerimetre(
            IDactivite=10, IDgroupe=2, annee_reference=2026, nombre_annees=1,
            dictUnites=dictUnites_10, dict_options=self._options(),
        )
        historique_autre_activite = UTILS_AFAS_Historique.ConstruireHistoriquePerimetre(
            IDactivite=20, IDgroupe=1, annee_reference=2026, nombre_annees=1,
            dictUnites=dictUnites_20, dict_options=self._options(),
        )

        self.assertEqual(historique_groupe1, [{"heures": 2.0, "jours_ouverts": 1}])
        self.assertEqual(historique_groupe2, [{"heures": 9.0, "jours_ouverts": 1}])
        self.assertEqual(historique_autre_activite, [{"heures": 6.0, "jours_ouverts": 1}])

    def test_propagation_coherente_heures_et_jours_ouverts(self):
        # 2 jours d'ouverture distincts en 2025, consos réparties dessus.
        self.base.inserer(
            "consommations",
            ["IDconso", "IDindividu", "IDunite", "date", "heure_debut", "heure_fin", "etat", "quantite", "IDactivite", "IDprestation", "IDcompte_payeur", "IDgroupe"],
            [
                (1, 1, 51, "2025-03-10", "08:00", "10:00", "present", None, 10, None, 1, 1),  # 2h
                (2, 2, 51, "2025-03-11", "08:00", "11:00", "present", None, 10, None, 1, 1),  # 3h
            ],
        )
        self.base.db.Commit()
        self.base.inserer(
            "ouvertures",
            ["IDactivite", "IDunite", "IDgroupe", "date"],
            [
                (10, 51, 1, "2025-03-10"),
                (10, 51, 1, "2025-03-11"),
            ],
        )
        self.base.db.Commit()

        dictUnites = {51: self._unite(51, IDactivite=10)}
        historique = UTILS_AFAS_Historique.ConstruireHistoriquePerimetre(
            IDactivite=10, IDgroupe=1, annee_reference=2026, nombre_annees=1,
            dictUnites=dictUnites, dict_options=self._options(),
        )

        self.assertEqual(historique, [{"heures": 5.0, "jours_ouverts": 2}])

    def test_compatibilite_avec_estimer_periode(self):
        self.base.inserer(
            "consommations",
            ["IDconso", "IDindividu", "IDunite", "date", "heure_debut", "heure_fin", "etat", "quantite", "IDactivite", "IDprestation", "IDcompte_payeur", "IDgroupe"],
            [
                (1, 1, 51, "2025-03-10", "08:00", "10:00", "present", None, 10, None, 1, 1),  # 2025 (N-1) : 2h
                (2, 1, 51, "2024-03-10", "08:00", "10:00", "present", None, 10, None, 1, 1),  # 2024 (N-2) : 2h
            ],
        )
        self.base.db.Commit()
        self.base.inserer(
            "ouvertures",
            ["IDactivite", "IDunite", "IDgroupe", "date"],
            [
                (10, 51, 1, "2025-03-10"),
                (10, 51, 1, "2024-03-10"),
            ],
        )
        self.base.db.Commit()

        dictUnites = {51: self._unite(51, IDactivite=10)}
        historique = UTILS_AFAS_Historique.ConstruireHistoriquePerimetre(
            IDactivite=10, IDgroupe=1, annee_reference=2026, nombre_annees=2,
            dictUnites=dictUnites, dict_options=self._options(),
        )

        estimation_n1 = UTILS_AFAS.EstimerPeriode(
            methode=UTILS_AFAS.METHODE_N1_AJUSTE, historique=historique, jours_ouverts_cible=10,
        )
        self.assertEqual(estimation_n1, 20.0)  # 2h/1j * 10j

        comparaison = UTILS_AFAS.ConstruireComparaison(historique=historique, jours_ouverts_cible=10)
        self.assertEqual(comparaison[UTILS_AFAS.METHODE_MOYENNE_2_ANS], 20.0)
        self.assertEqual(comparaison[UTILS_AFAS.METHODE_MOYENNE_3_ANS], 20.0)

    def test_nombre_annees_invalide_leve_erreur(self):
        dictUnites = {51: self._unite(51, IDactivite=10)}
        with self.assertRaises(ValueError):
            UTILS_AFAS_Historique.ConstruireHistoriquePerimetre(
                IDactivite=10, IDgroupe=1, annee_reference=2026, nombre_annees=0,
                dictUnites=dictUnites, dict_options=self._options(),
            )


if __name__ == "__main__":
    unittest.main()
