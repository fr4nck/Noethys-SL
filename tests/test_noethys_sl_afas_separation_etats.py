# -*- coding: utf-8 -*-
"""AFAS : états distincts, aucun comptage implicite de réservations et d'absences."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "noethys"))

from test_noethys_sl_afas_donnees import _BaseAFASDonneesTests
from Utils import UTILS_AFAS, UTILS_AFAS_Donnees, UTILS_AFAS_Actualisation as AFAS


class SelectionEtatsAFAS(_BaseAFASDonneesTests):
    def alimenter(self):
        """Un présent, une réservation et deux absences sur quatre dates."""
        for i, etat, heures in (
                (1, "present", "02:00"),
                (2, "reservation", "04:00"),
                (3, "absenti", "05:00"),
                (4, "absentj", "06:00")):
            date = "2026-03-%02d" % (i + 9)
            self._inserer_prestation(500 + i, heures)
            self._inserer_conso(i, 1, 1, date, "08:00", "%02d:00" % (8 + int(heures[:2])),
                                IDprestation=500 + i)
            self._inserer_ouverture(date)
            if etat != "present":
                self.base.db.ExecuterReq(
                    "UPDATE consommations SET etat='%s' WHERE IDconso=%d" % (etat, i))
        self._commit()

    def calculer(self, options):
        return UTILS_AFAS_Donnees.GetDonneesAFAS(
            10, 1, 2026, UTILS_AFAS.PHASE_REEL,
            {51: self._unite_reel(51, 10)},
            {51: self._unite_facture(51, 10)},
            options)

    def test_ancien_profil_ne_comptabilise_pas_absences_ou_reservations(self):
        self.alimenter()
        options = self._options()
        initial = list(options["etat_consommations"])
        resultat = self.calculer(options)
        self.assertEqual(resultat["heures_reelles"], 2.0)
        self.assertEqual(resultat["heures_facturees"], 2.0)
        self.assertEqual(options["etat_consommations"], initial)

    def test_absence_facturee_explicitement_ne_modifie_pas_reel(self):
        self.alimenter()
        options = self._options(afas_etats_reels=["present"],
                                afas_etats_factures=["present", "absenti"])
        resultat = self.calculer(options)
        self.assertEqual(resultat["heures_reelles"], 2.0)
        self.assertEqual(resultat["heures_facturees"], 7.0)
        self.assertEqual(options["afas_etats_factures"], ["present", "absenti"])

    def test_absence_injustifiee_reelle_si_choisie_explicitement(self):
        self.alimenter()
        resultat = self.calculer(self._options(afas_etats_reels=["present", "absenti"]))
        self.assertEqual(resultat["heures_reelles"], 7.0)
        self.assertEqual(resultat["heures_facturees"], 2.0)

    def test_rejet_etats_non_qualifies_et_reservation_reelle(self):
        for selection in ([], ["xxx"], ["present", "present"], "present", [0]):
            with self.subTest(selection=selection):
                with self.assertRaises(ValueError):
                    UTILS_AFAS_Donnees.SelectionEtatsAFAS(
                        {"afas_etats_factures": selection}, "afas_etats_factures")
        with self.assertRaisesRegex(ValueError, "réservations"):
            UTILS_AFAS_Donnees.SelectionEtatsAFAS(
                {"afas_etats_reels": ["present", "reservation"]}, "afas_etats_reels")

    def test_rapport_csv_explicite_les_deux_filtrages(self):
        self.alimenter()
        opts = self._options(afas_etats_factures=["present", "absenti"])
        rapport = AFAS.PreparerActualisation(
            2026, [(10, 1)], {51: self._unite_reel(51, 10)}, opts,
            methode=UTILS_AFAS.METHODE_MANUEL,
            valeurs_manuelles={code: 0 for code, _ in AFAS.METRIQUES},
            phase=UTILS_AFAS.PHASE_ACTUALISATION_SEPTEMBRE)
        self.assertEqual(rapport["options"]["afas_etats_reels"], ["present"])
        self.assertEqual(rapport["options"]["afas_etats_factures"], ["present", "absenti"])
        with tempfile.TemporaryDirectory() as dossier:
            path = Path(dossier) / "declaration.csv"
            AFAS.ExporterCSV(path, rapport, "ALSH fictif")
            with path.open(encoding="utf-8-sig", newline="") as fichier:
                rows = list(csv.reader(fichier, delimiter=";"))
            self.assertIn(["États heures réalisées", "present"], rows)
            self.assertIn(["États heures facturées", "present, absenti"], rows)


if __name__ == "__main__":
    unittest.main()
