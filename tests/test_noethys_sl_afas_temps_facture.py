# -*- coding: utf-8 -*-
"""AFAS -- contrôle des temps facturés (prestations.temps_facture).

Non-régression de l'anomalie P1 de l'audit AFAS du 23/10/2026 : un temps
facturé négatif était compté (-1 h) et un format invalide provoquait une
ValueError brute. Le calcul AFAS est désormais bloqué et la prestation en
cause listée. Aucun plafond n'est appliqué (un forfait peut couvrir
plusieurs journées). L'état global sans contrôle garde son comportement
historique. Bases SQLite fictives uniquement.
"""
import datetime
import unittest

import _garde_reseau  # noqa: F401  aucune connexion à une base réseau

from test_noethys_sl_afas_donnees import _BaseAFASDonneesTests
from Dlg import DLG_Etat_global
from Utils import UTILS_AFAS_Donnees


class _BaseTempsFacture(_BaseAFASDonneesTests):
    def setUp(self):
        super().setUp()
        self.base.inserer("groupes", ["IDgroupe", "IDactivite", "nom"], [(1, 10, "Groupe 1")])
        self._commit()

    def _conso_facturee(self, temps_facture, IDconso=1, IDprestation=501):
        self._inserer_prestation(IDprestation, temps_facture)
        self._inserer_conso(IDconso, 1, 1, "2026-03-04", "08:30", "17:30", IDprestation=IDprestation)
        self._commit()

    def _periode(self):
        return UTILS_AFAS_Donnees.GetDonneesPeriodeAFAS(
            [(10, 1)], datetime.date(2026, 1, 1), datetime.date(2026, 12, 31), datetime.date(2026, 12, 31),
            {51: self._unite_reel(51, 10)}, {51: self._unite_facture(51, 10)}, self._options())


class TempsFactureAFASTests(_BaseTempsFacture):
    def test_temps_negatif_bloque(self):
        self._conso_facturee("-01:00")
        with self.assertRaisesRegex(UTILS_AFAS_Donnees.AnomalieAFAS, "Temps facturé invalide"):
            self._periode()

    def test_formats_invalides_bloques(self):
        for i, temps in enumerate(("9h", "09:60", "abc", "09", "9:5", " 09:00"), 1):
            with self.subTest(temps=temps):
                self.base.db.ExecuterReq("DELETE FROM consommations;")
                self.base.db.ExecuterReq("DELETE FROM prestations;")
                self._conso_facturee(temps, IDconso=i, IDprestation=500 + i)
                with self.assertRaises(UTILS_AFAS_Donnees.AnomalieAFAS):
                    self._periode()

    def test_temps_valides_comptes(self):
        self._conso_facturee("09:00")
        self.assertEqual(self._periode()["heures_facturees"], 9)

    def test_temps_nul_accepte(self):
        self._conso_facturee("00:00")
        self.assertEqual(self._periode()["heures_facturees"], 0)

    def test_forfait_superieur_a_24h_non_plafonne(self):
        # Aucun plafond inventé : la décision métier reste à prendre.
        self._conso_facturee("36:00")
        self.assertEqual(self._periode()["heures_facturees"], 36)

    def test_prestation_sans_temps_ignoree(self):
        self._conso_facturee(None)
        self.assertEqual(self._periode()["heures_facturees"], 0)


class TempsFactureValideTests(unittest.TestCase):
    def test_formats(self):
        for valeur, attendu in (("09:00", True), ("00:00", True), ("120:30", True), ("-01:00", False),
                                ("9h", False), ("09:60", False), ("", False), (None, False), (9, False)):
            with self.subTest(valeur=valeur):
                self.assertEqual(DLG_Etat_global.TempsFactureValide(valeur), attendu)


class EtatGlobalHistoriqueTests(_BaseTempsFacture):
    def test_etat_global_sans_controle_inchange(self):
        # Comportement historique conservé hors AFAS : -1 h compté, aucune anomalie signalée.
        self._conso_facturee("-01:00")
        resultat = DLG_Etat_global.CalculateurEtatGlobal().CalculerEtatGlobal(
            date_debut=datetime.date(2026, 1, 1), date_fin=datetime.date(2026, 12, 31), listeActivites=[10],
            dictUnites={51: self._unite_facture(51, 10)}, dict_options=self._options(),
            dictInfosIndividus={}, dictInfosFamilles={})
        total = sum((v for t in resultat["dict_resultats"].values() for p in t.values()
                     for r in p.values() for v in r.values()), datetime.timedelta(0))
        self.assertEqual(total, datetime.timedelta(hours=-1))
        self.assertEqual(resultat["listeTempsFactures"], [])


if __name__ == "__main__":
    unittest.main()
