# -*- coding: utf-8 -*-
"""Caractérisation de UTILS_AFAS_Perimetre.GetDonneesPerimetre.

Vérifie uniquement que l'orchestrateur assemble correctement deux
résultats déjà qualifiés (CalculateurEtatGlobal pour les heures,
UTILS_Ouvertures pour les jours ouverts) pour un même périmètre
(IDactivite, IDgroupe) -- aucune règle CAF/AFAS n'est testée ici, aucun ID
PMSL réel n'est utilisé.
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

from Utils import UTILS_AFAS_Perimetre  # noqa: E402


TABLES_SUPPLEMENTAIRES = ("vacances", "evenements", "etiquettes", "comptes_payeurs", "categories_tarifs", "ouvertures")


class GetDonneesPerimetreTests(unittest.TestCase):
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
            [(1, "Toussaint", 2026, "2026-01-01", "2026-12-31")],
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

    def test_heures_et_jours_ouverts_portent_sur_le_meme_perimetre(self):
        # Consommations : 2h + 3h pour (activite=10, groupe=1) sur 2 jours distincts.
        self.base.inserer(
            "consommations",
            ["IDconso", "IDindividu", "IDunite", "date", "heure_debut", "heure_fin", "etat", "quantite", "IDactivite", "IDprestation", "IDcompte_payeur", "IDgroupe"],
            [
                (1, 1, 51, "2026-03-10", "08:00", "10:00", "present", None, 10, None, 1, 1),  # 2h
                (2, 2, 51, "2026-03-11", "08:00", "11:00", "present", None, 10, None, 1, 1),  # 3h
            ],
        )
        self.base.db.Commit()
        # Ouvertures : 3 unités ouvertes le 10/03 (même jour), 1 seule le 11/03 -> 2 jours distincts.
        self.base.inserer(
            "ouvertures",
            ["IDactivite", "IDunite", "IDgroupe", "date"],
            [
                (10, 51, 1, "2026-03-10"),
                (10, 52, 1, "2026-03-10"),
                (10, 53, 1, "2026-03-10"),
                (10, 51, 1, "2026-03-11"),
            ],
        )
        self.base.db.Commit()

        dictUnites = {51: self._unite(51, IDactivite=10)}
        resultat = UTILS_AFAS_Perimetre.GetDonneesPerimetre(
            IDactivite=10, IDgroupe=1, date_debut="2026-03-01", date_fin="2026-03-31",
            dictUnites=dictUnites, dict_options=self._options(),
        )

        self.assertEqual(resultat, {"heures": 5.0, "jours_ouverts": 2})

    def test_contrat_cles_et_types_exacts(self):
        dictUnites = {51: self._unite(51, IDactivite=10)}
        resultat = UTILS_AFAS_Perimetre.GetDonneesPerimetre(
            IDactivite=10, IDgroupe=1, date_debut="2026-03-01", date_fin="2026-03-31",
            dictUnites=dictUnites, dict_options=self._options(),
        )
        self.assertEqual(set(resultat.keys()), {"heures", "jours_ouverts"})
        self.assertIsInstance(resultat["heures"], float)
        self.assertIsInstance(resultat["jours_ouverts"], int)
        self.assertEqual(resultat, {"heures": 0.0, "jours_ouverts": 0})

    def test_ne_melange_pas_un_autre_groupe_de_la_meme_activite(self):
        # Consommations pour groupe 1 (2h) et groupe 2 (9h) de la même activité 10.
        self.base.inserer(
            "consommations",
            ["IDconso", "IDindividu", "IDunite", "date", "heure_debut", "heure_fin", "etat", "quantite", "IDactivite", "IDprestation", "IDcompte_payeur", "IDgroupe"],
            [
                (1, 1, 51, "2026-03-10", "08:00", "10:00", "present", None, 10, None, 1, 1),  # groupe 1 : 2h
                (2, 2, 51, "2026-03-10", "08:00", "17:00", "present", None, 10, None, 1, 2),  # groupe 2 : 9h
            ],
        )
        self.base.db.Commit()
        self.base.inserer(
            "ouvertures",
            ["IDactivite", "IDunite", "IDgroupe", "date"],
            [
                (10, 51, 1, "2026-03-10"),
                (10, 51, 2, "2026-03-10"),
                (10, 51, 2, "2026-03-11"),
            ],
        )
        self.base.db.Commit()

        dictUnites = {51: self._unite(51, IDactivite=10)}
        resultat_groupe1 = UTILS_AFAS_Perimetre.GetDonneesPerimetre(
            IDactivite=10, IDgroupe=1, date_debut="2026-03-01", date_fin="2026-03-31",
            dictUnites=dictUnites, dict_options=self._options(),
        )
        resultat_groupe2 = UTILS_AFAS_Perimetre.GetDonneesPerimetre(
            IDactivite=10, IDgroupe=2, date_debut="2026-03-01", date_fin="2026-03-31",
            dictUnites=dictUnites, dict_options=self._options(),
        )
        self.assertEqual(resultat_groupe1, {"heures": 2.0, "jours_ouverts": 1})
        self.assertEqual(resultat_groupe2, {"heures": 9.0, "jours_ouverts": 2})

    def test_ne_melange_pas_une_autre_activite(self):
        self.base.inserer(
            "consommations",
            ["IDconso", "IDindividu", "IDunite", "date", "heure_debut", "heure_fin", "etat", "quantite", "IDactivite", "IDprestation", "IDcompte_payeur", "IDgroupe"],
            [
                (1, 1, 51, "2026-03-10", "08:00", "10:00", "present", None, 10, None, 1, 1),   # activité 10 : 2h
                (2, 2, 61, "2026-03-10", "08:00", "14:00", "present", None, 20, None, 1, 1),   # activité 20, même groupe : 6h
            ],
        )
        self.base.db.Commit()
        self.base.inserer(
            "ouvertures",
            ["IDactivite", "IDunite", "IDgroupe", "date"],
            [
                (10, 51, 1, "2026-03-10"),
                (20, 61, 1, "2026-03-10"),
                (20, 61, 1, "2026-03-11"),
            ],
        )
        self.base.db.Commit()

        dictUnites = {51: self._unite(51, IDactivite=10)}
        resultat = UTILS_AFAS_Perimetre.GetDonneesPerimetre(
            IDactivite=10, IDgroupe=1, date_debut="2026-03-01", date_fin="2026-03-31",
            dictUnites=dictUnites, dict_options=self._options(),
        )
        # Seule l'activité 10 doit contribuer, malgré le même IDgroupe=1 utilisé ailleurs.
        self.assertEqual(resultat, {"heures": 2.0, "jours_ouverts": 1})


if __name__ == "__main__":
    unittest.main()
