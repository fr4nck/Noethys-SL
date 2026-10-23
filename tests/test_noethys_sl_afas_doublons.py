# -*- coding: utf-8 -*-
"""AFAS -- doublons et chevauchements bloquants.

Non-régression de l'anomalie P0-2 de l'audit AFAS du 23/10/2026 : journée +
demi-journée, plages chevauchantes et consommations en double étaient
additionnées (14 h ou 18 h pour 9 h). Aucune règle de déduplication n'est
inventée : le calcul AFAS est bloqué et les consommations en cause sont
listées. L'état global sans contrôle garde son comportement historique.
Bases SQLite fictives uniquement.
"""
import datetime
import unittest

import _garde_reseau  # noqa: F401  aucune connexion à une base réseau

from test_noethys_sl_afas_donnees import _BaseAFASDonneesTests
from Dlg import DLG_Etat_global
from Utils import UTILS_AFAS_Donnees
from Utils import UTILS_AFAS_Perimetre


class _BaseDoublons(_BaseAFASDonneesTests):
    def setUp(self):
        super().setUp()
        self.base.inserer("groupes", ["IDgroupe", "IDactivite", "nom"], [(1, 10, "Groupe 1"), (2, 10, "Groupe 2")])
        self._commit()

    def _conso(self, IDconso, debut, fin, IDunite=51, IDindividu=1, IDgroupe=1, date="2026-03-04"):
        self.base.inserer(
            "consommations",
            ["IDconso", "IDindividu", "IDunite", "date", "heure_debut", "heure_fin", "etat", "quantite",
             "IDactivite", "IDprestation", "IDcompte_payeur", "IDgroupe"],
            [(IDconso, IDindividu, IDunite, date, debut, fin, "present", None, 10, None, IDindividu, IDgroupe)],
        )

    def _unites(self, coeff=None):
        unites = {51: self._unite_reel(51, 10), 52: self._unite_reel(52, 10)}
        if coeff:
            for IDunite, valeur in coeff.items():
                unites[IDunite].update(typeCalcul=0, coeff=valeur)
        return unites

    def _periode(self, unites=None):
        self._commit()
        unites = unites or self._unites()
        facture = {cle: self._unite_facture(cle, 10) for cle in unites}
        return UTILS_AFAS_Donnees.GetDonneesPeriodeAFAS(
            [(10, 1), (10, 2)], datetime.date(2026, 1, 1), datetime.date(2026, 12, 31),
            datetime.date(2026, 12, 31), unites, facture, self._options())


class DoublonsBloquantsTests(_BaseDoublons):
    def test_journee_et_demi_journee_bloque(self):
        self._conso(1, "08:30", "17:30", IDunite=51)
        self._conso(2, "08:30", "12:00", IDunite=52)
        with self.assertRaisesRegex(UTILS_AFAS_Donnees.AnomalieAFAS, "consommations 1 et 2"):
            self._periode(self._unites(coeff={51: 9, 52: 5}))

    def test_plages_chevauchantes_bloque(self):
        self._conso(1, "08:30", "17:30")
        self._conso(2, "08:30", "12:00", IDunite=52)
        with self.assertRaises(UTILS_AFAS_Donnees.AnomalieAFAS):
            self._periode()

    def test_doublon_deux_idconso_meme_creneau_bloque(self):
        self._conso(1, "08:30", "17:30")
        self._conso(2, "08:30", "17:30")
        with self.assertRaises(UTILS_AFAS_Donnees.AnomalieAFAS):
            self._periode()

    def test_meme_enfant_deux_sites_meme_creneau_bloque(self):
        self._conso(1, "08:30", "17:30", IDgroupe=1)
        self._conso(2, "08:30", "17:30", IDgroupe=2)
        with self.assertRaises(UTILS_AFAS_Donnees.AnomalieAFAS):
            self._periode()

    def test_meme_unite_sans_horaires_bloque(self):
        self._conso(1, None, None, IDunite=51)
        self._conso(2, None, None, IDunite=51)
        with self.assertRaises(UTILS_AFAS_Donnees.AnomalieAFAS):
            self._periode(self._unites(coeff={51: 9}))

    def test_historique_perimetre_bloque_aussi(self):
        self._conso(1, "08:30", "17:30")
        self._conso(2, "09:00", "10:00", IDunite=52)
        self._commit()
        with self.assertRaises(UTILS_AFAS_Donnees.AnomalieAFAS):
            UTILS_AFAS_Perimetre.GetDonneesPerimetre(
                10, 1, datetime.date(2026, 1, 1), datetime.date(2026, 12, 31), self._unites(), self._options())


class CasLegitimesTests(_BaseDoublons):
    def test_plages_contigues_acceptees(self):
        self._conso(1, "07:30", "08:30", IDunite=52)
        self._conso(2, "08:30", "17:30", IDunite=51)
        self.assertEqual(self._periode()["heures_reelles"], 10)

    def test_unite_multi_horaires_sans_chevauchement_acceptee(self):
        self._conso(1, "07:30", "08:30")
        self._conso(2, "16:30", "18:00")
        self.assertEqual(self._periode()["heures_reelles"], 2.5)

    def test_plusieurs_enfants_meme_creneau(self):
        for IDindividu in (1, 2, 3):
            self._conso(IDindividu, "08:30", "17:30", IDindividu=IDindividu)
        self.assertEqual(self._periode()["heures_reelles"], 27)

    def test_meme_enfant_jours_differents(self):
        self._conso(1, "08:30", "17:30", date="2026-03-04")
        self._conso(2, "08:30", "17:30", date="2026-03-11")
        self.assertEqual(self._periode()["heures_reelles"], 18)

    def test_anomalie_hors_etats_retenus_ignoree(self):
        # Une conso exclue par son statut ne participe ni au calcul ni au contrôle.
        self._conso(1, "08:30", "17:30")
        self.base.inserer(
            "consommations",
            ["IDconso", "IDindividu", "IDunite", "date", "heure_debut", "heure_fin", "etat", "quantite",
             "IDactivite", "IDprestation", "IDcompte_payeur", "IDgroupe"],
            [(2, 1, 52, "2026-03-04", "08:30", "12:00", "absenti", None, 10, None, 1, 1)])
        self._commit()
        unites = self._unites()
        resultat = UTILS_AFAS_Donnees.GetDonneesPeriodeAFAS(
            [(10, 1)], datetime.date(2026, 1, 1), datetime.date(2026, 12, 31), datetime.date(2026, 12, 31),
            unites, {cle: self._unite_facture(cle, 10) for cle in unites},
            self._options(etat_consommations=["present"]))
        self.assertEqual(resultat["heures_reelles"], 9)


class AnomaliesPeriodeTests(_BaseDoublons):
    def test_periode_inconnue_bloque_afas(self):
        # Périodes détaillées sans période couvrant la date : le moteur produit une anomalie, AFAS la remonte.
        self.base.db.ExecuterReq("DELETE FROM vacances;")
        self.base.inserer("vacances", ["IDvacance", "nom", "annee", "date_debut", "date_fin"],
                          [(9, "Toussaint", 2026, "2026-10-17", "2026-11-01")])
        self._conso(1, "08:30", "17:30", date="2026-03-04")
        self._commit()
        unites = self._unites()
        with self.assertRaisesRegex(UTILS_AFAS_Donnees.AnomalieAFAS, "Période inconnue"):
            UTILS_AFAS_Donnees.GetDonneesPeriodeAFAS(
                [(10, 1)], datetime.date(2026, 1, 1), datetime.date(2026, 12, 31), datetime.date(2026, 12, 31),
                unites, {cle: self._unite_facture(cle, 10) for cle in unites},
                self._options(periodes_detaillees=True))


class EtatGlobalHistoriqueTests(_BaseDoublons):
    def test_etat_global_sans_controle_inchange(self):
        self._conso(1, "08:30", "17:30")
        self._conso(2, "08:30", "12:00", IDunite=52)
        self._commit()
        resultat = DLG_Etat_global.CalculateurEtatGlobal().CalculerEtatGlobal(
            date_debut=datetime.date(2026, 1, 1), date_fin=datetime.date(2026, 12, 31), listeActivites=[10],
            dictUnites=self._unites(), dict_options=self._options(), dictInfosIndividus={}, dictInfosFamilles={})
        total = sum((v for t in resultat["dict_resultats"].values() for p in t.values()
                     for r in p.values() for v in r.values()), datetime.timedelta(0))
        self.assertEqual(total, datetime.timedelta(hours=12, minutes=30))
        self.assertEqual(resultat["listeDoublons"], [])


if __name__ == "__main__":
    unittest.main()
