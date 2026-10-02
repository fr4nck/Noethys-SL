# -*- coding: utf-8 -*-
"""Caractérisation de UTILS_AFAS_Donnees.GetDonneesAFAS.

Vérifie que l'orchestrateur combine, pour un même périmètre
(IDactivite, IDgroupe) et une phase AFAS donnée, les heures réelles
(État global, typeCalcul réel) et facturées (État global, typeCalcul=2 /
prestations.temps_facture, déduplication par IDprestation déjà gérée par
le moteur), chacune avec son sous-total "dont AEEH" déterminé par
`aeeh_periodes` à la date de situation de la phase -- jamais ajouté au
total, jamais de donnée recalculée ou dupliquée, aucun arrondi AFAS
supplémentaire, aucun ID PMSL réel.
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

from Utils import UTILS_AEEH_Periodes  # noqa: E402
from Utils import UTILS_AFAS  # noqa: E402
from Utils import UTILS_AFAS_Donnees  # noqa: E402


TABLES_SUPPLEMENTAIRES = ("vacances", "evenements", "etiquettes", "comptes_payeurs", "categories_tarifs",
                           "ouvertures", "aeeh_periodes")


class _BaseAFASDonneesTests(unittest.TestCase):
    def setUp(self):
        self.base = BaseTest()
        for nom_table in TABLES_SUPPLEMENTAIRES:
            self.base.db.CreationTable(nom_table, dicoDB=Tables.DB_DATA)

        self.base.inserer("regimes", ["IDregime", "nom"], [(1, "Régime Général")])
        self.base.inserer("caisses", ["IDcaisse", "nom", "IDregime"], [(1, "CAF Test", 1)])
        self.base.inserer("familles", ["IDfamille", "IDcaisse"], [(1, 1), (2, 1), (3, 1)])
        self.base.inserer("comptes_payeurs", ["IDcompte_payeur", "IDfamille"], [(1, 1), (2, 2), (3, 3)])
        date_naiss = str(datetime.date.today().replace(year=datetime.date.today().year - 10))
        self.base.inserer(
            "individus",
            ["IDindividu", "nom", "prenom", "IDcivilite", "date_naiss"],
            [
                (1, "DUPONT", "Enfant A", 1, date_naiss),
                (2, "MARTIN", "Enfant B", 1, date_naiss),
                (3, "DURAND", "Enfant C", 1, date_naiss),
            ],
        )
        self.base.inserer("activites", ["IDactivite", "nom"], [(10, "Activite A")])
        self.base.inserer(
            "vacances",
            ["IDvacance", "nom", "annee", "date_debut", "date_fin"],
            [(1, "Annee 2026", 2026, "2026-01-01", "2026-12-31")],
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

    def _unite_reel(self, IDunite, IDactivite):
        return {
            "IDunite": IDunite, "IDactivite": IDactivite, "nomUnite": "Unite", "nomActivite": "Activite",
            "typeCalcul": 1, "coeff": None, "arrondi": None,
            "duree_plafond": None, "duree_seuil": None,
            "heure_plafond": None, "heure_seuil": None, "formule": None,
        }

    def _unite_facture(self, IDunite, IDactivite):
        return {
            "IDunite": IDunite, "IDactivite": IDactivite, "nomUnite": "Unite", "nomActivite": "Activite",
            "typeCalcul": 2, "coeff": None, "arrondi": None,
            "duree_plafond": None, "duree_seuil": None,
            "heure_plafond": None, "heure_seuil": None, "formule": None,
        }

    def _inserer_conso(self, IDconso, IDindividu, IDcompte_payeur, date, heure_debut, heure_fin,
                        IDunite=51, IDprestation=None):
        self.base.inserer(
            "consommations",
            ["IDconso", "IDindividu", "IDunite", "date", "heure_debut", "heure_fin", "etat", "quantite",
             "IDactivite", "IDprestation", "IDcompte_payeur", "IDgroupe"],
            [(IDconso, IDindividu, IDunite, date, heure_debut, heure_fin, "present", None, 10, IDprestation,
              IDcompte_payeur, 1)],
        )

    def _inserer_prestation(self, IDprestation, temps_facture):
        self.base.inserer(
            "prestations",
            ["IDprestation", "temps_facture"],
            [(IDprestation, temps_facture)],
        )

    def _inserer_ouverture(self, date, IDunite=51):
        self.base.inserer("ouvertures", ["IDactivite", "IDunite", "IDgroupe", "date"], [(10, IDunite, 1, date)])

    def _inserer_aeeh(self, IDperiode, IDindividu, date_debut, date_fin):
        self.base.inserer("aeeh_periodes", ["IDperiode", "IDindividu", "date_debut", "date_fin"],
                           [(IDperiode, IDindividu, date_debut, date_fin)])

    def _commit(self):
        self.base.db.Commit()


# ---------------------------------------------------------------------------
# GetIndividusActifsADate -- bornes AEEH par date de situation
# ---------------------------------------------------------------------------

class IndividusActifsADateTests(_BaseAFASDonneesTests):
    def test_aucune_periode_liste_vide(self):
        self.assertEqual(UTILS_AEEH_Periodes.GetIndividusActifsADate("2026-12-31"), [])

    def test_debut_exactement_a_date_situation_inclus(self):
        self._inserer_aeeh(1, 1, "2026-12-31", "2027-06-30")
        self._commit()
        self.assertEqual(UTILS_AEEH_Periodes.GetIndividusActifsADate("2026-12-31"), [1])

    def test_fin_exactement_a_date_situation_inclus(self):
        self._inserer_aeeh(1, 1, "2026-01-01", "2026-12-31")
        self._commit()
        self.assertEqual(UTILS_AEEH_Periodes.GetIndividusActifsADate("2026-12-31"), [1])

    def test_periode_expiree_avant_date_situation_exclue(self):
        self._inserer_aeeh(1, 1, "2026-01-01", "2026-12-30")
        self._commit()
        self.assertEqual(UTILS_AEEH_Periodes.GetIndividusActifsADate("2026-12-31"), [])

    def test_periode_future_exclue(self):
        self._inserer_aeeh(1, 1, "2027-01-01", "2027-06-30")
        self._commit()
        self.assertEqual(UTILS_AEEH_Periodes.GetIndividusActifsADate("2026-12-31"), [])

    def test_date_fin_null_incluse(self):
        self._inserer_aeeh(1, 1, "2026-01-01", None)
        self._commit()
        self.assertEqual(UTILS_AEEH_Periodes.GetIndividusActifsADate("2026-12-31"), [1])
        self.assertEqual(UTILS_AEEH_Periodes.GetIndividusActifsADate("2099-01-01"), [1])

    def test_plusieurs_individus_seuls_certains_actifs(self):
        self._inserer_aeeh(1, 1, "2026-01-01", "2026-12-31")   # actif
        self._inserer_aeeh(2, 2, "2025-01-01", "2025-12-31")   # expiré
        self._inserer_aeeh(3, 3, "2027-01-01", None)           # futur
        self._commit()
        self.assertEqual(UTILS_AEEH_Periodes.GetIndividusActifsADate("2026-12-31"), [1])


# ---------------------------------------------------------------------------
# GetDonneesAFAS -- réel / facturé / sous-totaux AEEH
# ---------------------------------------------------------------------------

class GetDonneesAFASTests(_BaseAFASDonneesTests):
    def _calculer(self, annee=2026, phase=UTILS_AFAS.PHASE_REEL, dictUnites_reel=None, dictUnites_facture=None):
        dictUnites_reel = dictUnites_reel if dictUnites_reel is not None else {51: self._unite_reel(51, 10)}
        dictUnites_facture = dictUnites_facture if dictUnites_facture is not None else {51: self._unite_facture(51, 10)}
        return UTILS_AFAS_Donnees.GetDonneesAFAS(
            IDactivite=10, IDgroupe=1, annee=annee, phase=phase,
            dictUnites_reel=dictUnites_reel, dictUnites_facture=dictUnites_facture,
            dict_options=self._options(),
        )

    def test_reel_sans_aeeh(self):
        self._inserer_conso(1, 1, 1, "2026-03-10", "08:00", "10:00")  # 2h
        self._inserer_ouverture("2026-03-10")
        self._commit()

        resultat = self._calculer()
        self.assertEqual(resultat["heures_reelles"], 2.0)
        self.assertEqual(resultat["heures_reelles_aeeh"], 0.0)

    def test_reel_avec_aeeh(self):
        self._inserer_conso(1, 1, 1, "2026-03-10", "08:00", "10:00")  # individu 1 (AEEH) : 2h
        self._inserer_conso(2, 2, 2, "2026-03-11", "08:00", "11:00")  # individu 2 (non AEEH) : 3h
        self._inserer_ouverture("2026-03-10")
        self._inserer_ouverture("2026-03-11")
        self._inserer_aeeh(1, 1, "2026-01-01", "2026-12-31")
        self._commit()

        resultat = self._calculer()
        self.assertEqual(resultat["heures_reelles"], 5.0)
        self.assertEqual(resultat["heures_reelles_aeeh"], 2.0)
        self.assertLessEqual(resultat["heures_reelles_aeeh"], resultat["heures_reelles"])

    def test_facture_sans_aeeh(self):
        self._inserer_prestation(501, "01:30")
        self._inserer_conso(1, 1, 1, "2026-03-10", "08:00", "10:00", IDprestation=501)
        self._inserer_ouverture("2026-03-10")
        self._commit()

        resultat = self._calculer()
        self.assertEqual(resultat["heures_facturees"], 1.5)
        self.assertEqual(resultat["heures_facturees_aeeh"], 0.0)

    def test_facture_avec_aeeh(self):
        self._inserer_prestation(501, "01:30")
        self._inserer_prestation(502, "02:30")
        self._inserer_conso(1, 1, 1, "2026-03-10", "08:00", "10:00", IDprestation=501)  # AEEH
        self._inserer_conso(2, 2, 2, "2026-03-11", "08:00", "11:00", IDprestation=502)  # non AEEH
        self._inserer_ouverture("2026-03-10")
        self._inserer_ouverture("2026-03-11")
        self._inserer_aeeh(1, 1, "2026-01-01", "2026-12-31")
        self._commit()

        resultat = self._calculer()
        self.assertEqual(resultat["heures_facturees"], 4.0)
        self.assertEqual(resultat["heures_facturees_aeeh"], 1.5)
        self.assertLessEqual(resultat["heures_facturees_aeeh"], resultat["heures_facturees"])

    def test_sous_total_aeeh_jamais_double_dans_le_total(self):
        """ Même nombre d'heures, qu'un individu soit AEEH ou non : le total
        est la somme simple des deux individus, jamais total + sous-total. """
        self._inserer_conso(1, 1, 1, "2026-03-10", "08:00", "10:00")  # 2h, AEEH
        self._inserer_conso(2, 2, 2, "2026-03-11", "08:00", "10:00")  # 2h, non AEEH
        self._inserer_ouverture("2026-03-10")
        self._inserer_ouverture("2026-03-11")
        self._inserer_aeeh(1, 1, "2026-01-01", "2026-12-31")
        self._commit()

        resultat = self._calculer()
        self.assertEqual(resultat["heures_reelles"], 4.0)
        self.assertEqual(resultat["heures_reelles_aeeh"], 2.0)

    def test_individu_hors_periode_aeeh_absent_du_dont_aeeh(self):
        # Individu 1 a une période AEEH mais EXPIRÉE avant date_situation (2026-12-31).
        self._inserer_conso(1, 1, 1, "2026-03-10", "08:00", "10:00")  # 2h
        self._inserer_ouverture("2026-03-10")
        self._inserer_aeeh(1, 1, "2025-01-01", "2025-12-31")
        self._commit()

        resultat = self._calculer()
        self.assertEqual(resultat["heures_reelles"], 2.0)
        self.assertEqual(resultat["heures_reelles_aeeh"], 0.0)

    def test_plusieurs_individus_dont_seulement_certains_aeeh(self):
        self._inserer_conso(1, 1, 1, "2026-03-10", "08:00", "10:00")  # 2h, AEEH
        self._inserer_conso(2, 2, 2, "2026-03-11", "08:00", "10:00")  # 2h, non AEEH
        self._inserer_conso(3, 3, 3, "2026-03-12", "08:00", "10:00")  # 2h, non AEEH
        self._inserer_ouverture("2026-03-10")
        self._inserer_ouverture("2026-03-11")
        self._inserer_ouverture("2026-03-12")
        self._inserer_aeeh(1, 1, "2026-01-01", "2026-12-31")
        self._commit()

        resultat = self._calculer()
        self.assertEqual(resultat["heures_reelles"], 6.0)
        self.assertEqual(resultat["heures_reelles_aeeh"], 2.0)
        self.assertLessEqual(resultat["heures_reelles_aeeh"], resultat["heures_reelles"])

    def test_deduplication_idprestation_conservee_pour_le_facture(self):
        # Deux consommations distinctes référençant LA MÊME prestation :
        # le moteur ne doit la compter qu'une seule fois (comportement
        # déjà existant de CalculerEtatGlobal, pas recréé ici).
        self._inserer_prestation(501, "01:30")
        self._inserer_conso(1, 1, 1, "2026-03-10", "08:00", "10:00", IDprestation=501)
        self._inserer_conso(2, 1, 1, "2026-03-11", "08:00", "10:00", IDprestation=501)
        self._inserer_ouverture("2026-03-10")
        self._inserer_ouverture("2026-03-11")
        self._commit()

        resultat = self._calculer()
        self.assertEqual(resultat["heures_facturees"], 1.5)

    def test_midi_applique_au_reel_jamais_au_facture(self):
        """ Verdict verrouillé sur données réelles PMSL (IDactivite=1) :
        prestations.temps_facture est déjà la durée réellement bookée
        (incluant le midi quand la plage le couvre) -- le forfait de
        présence méridienne ne doit donc jamais s'y ajouter, alors qu'il
        s'applique bien côté réel. Même consommation (08:00-16:00,
        chevauche 12:30-13:30) utilisée pour les deux calculs. """
        self._inserer_prestation(501, "08:00")  # déjà la durée brute, midi inclus dans ce vécu réel
        self._inserer_conso(1, 1, 1, "2026-03-10", "08:00", "16:00", IDprestation=501)  # 8h, chevauche le midi
        self._inserer_ouverture("2026-03-10")
        self._commit()

        resultat = UTILS_AFAS_Donnees.GetDonneesAFAS(
            IDactivite=10, IDgroupe=1, annee=2026, phase=UTILS_AFAS.PHASE_REEL,
            dictUnites_reel={51: self._unite_reel(51, 10)},
            dictUnites_facture={51: self._unite_facture(51, 10)},
            dict_options=self._options(forfait_presence_midi=60),
        )

        self.assertEqual(resultat["heures_reelles"], 9.0)       # 8h + 1h de forfait midi
        self.assertEqual(resultat["heures_facturees"], 8.0)     # temps_facture exact, jamais +1h

    def test_dict_options_appelant_jamais_mute(self):
        dict_options = self._options(forfait_presence_midi=60)
        copie_avant = dict(dict_options)

        self._inserer_prestation(501, "08:00")
        self._inserer_conso(1, 1, 1, "2026-03-10", "08:00", "16:00", IDprestation=501)
        self._inserer_ouverture("2026-03-10")
        self._commit()

        UTILS_AFAS_Donnees.GetDonneesAFAS(
            IDactivite=10, IDgroupe=1, annee=2026, phase=UTILS_AFAS.PHASE_REEL,
            dictUnites_reel={51: self._unite_reel(51, 10)},
            dictUnites_facture={51: self._unite_facture(51, 10)},
            dict_options=dict_options,
        )

        self.assertEqual(dict_options, copie_avant)
        self.assertEqual(dict_options["forfait_presence_midi"], 60)

    def test_jours_ouverts_identiques_quel_que_soit_aeeh(self):
        self._inserer_conso(1, 1, 1, "2026-03-10", "08:00", "10:00")
        self._inserer_ouverture("2026-03-10")
        self._commit()

        resultat_sans_aeeh = self._calculer()
        self._inserer_aeeh(1, 1, "2026-01-01", "2026-12-31")
        self._commit()
        resultat_avec_aeeh = self._calculer()

        self.assertEqual(resultat_sans_aeeh["jours_ouverts"], resultat_avec_aeeh["jours_ouverts"])
        self.assertEqual(resultat_avec_aeeh["jours_ouverts"], 1)


if __name__ == "__main__":
    unittest.main()
