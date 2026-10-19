# -*- coding: utf-8 -*-
"""#430 : prevalidation sans effet de bord, totaux issus des valeurs confirmees."""
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
from Utils.UTILS_Repas_validation import ConstruireControle, AppliquerControle
from Utils.UTILS_Repas_totaux import TotauxRepas


class CasFictif:
    def __init__(self, valeur):
        self.valeur = valeur
        self.saisies = []
    def GetValeur(self):
        return self.valeur
    def SetValeur(self, val):
        self.valeur = val
        self.saisies.append(val)


class ControleRepasTests(unittest.TestCase):
    def setUp(self):
        self.cases = [CasFictif(v) for v in (18, 32, 3, 1, 1, 7)]
        roles = ("moins_6", "six_plus", "animateurs", "direction", "autres_adultes", "sans_porc")
        self.donnees = {"liste_dates": [date(2026, 10, 19), "Total"],
                        "erreurs_sans_porc": {},
                        "liste_colonnes": [
                          {"nom_colonne": role, "categorie": "numerique_avec_suggestion",
                           "parametres": {"role_repas": role, "site_directeur": "Site A",
                                          "service_directeur": "midi"}}
                          for role in roles],
                        "cases": {(0, i): c for i, c in enumerate(self.cases)}}

    def test_retient_tous_les_adultes_et_sans_porc_est_sous_total(self):
        rows = ConstruireControle(self.donnees)
        self.assertEqual(len(rows), 1)
        x = rows[0]["totaux"]
        self.assertEqual((x["total_adultes"], x["repas_6_et_plus"], x["total_repas"], x["sans_porc"]),
                         (5, 37, 55, 7))
        self.assertTrue(all(not c.saisies for c in self.cases))

    def test_edition_ne_change_rien_avant_application(self):
        rows = ConstruireControle(self.donnees)
        rows[0]["valeurs"]["animateurs_repas"] = 5
        self.assertTrue(all(not c.saisies for c in self.cases))
        AppliquerControle(rows)
        self.assertEqual(self.cases[2].valeur, 5)
        self.assertEqual(TotauxRepas(**rows[0]["valeurs"])["total_repas"], 57)

    def test_doublon_meme_site_role_interdit(self):
        self.donnees["liste_colonnes"].append(dict(self.donnees["liste_colonnes"][0]))
        self.donnees["cases"][(0, 6)] = CasFictif(8)
        with self.assertRaises(ValueError):
            ConstruireControle(self.donnees)

    def test_source_sans_porc_invalide_interdit(self):
        self.donnees["erreurs_sans_porc"] = {12: "Choix manquant"}
        with self.assertRaises(ValueError):
            ConstruireControle(self.donnees)

    def test_sans_roles_nouveaux_refuse(self):
        self.donnees["liste_colonnes"][0]["parametres"]["role_repas"] = "aucun"
        self.assertEqual(len(ConstruireControle(self.donnees)[0]["colonnes_non_classees"]), 1)
        for c in self.donnees["liste_colonnes"]:
            c["parametres"]["role_repas"] = "aucun"
        with self.assertRaises(ValueError):
            ConstruireControle(self.donnees)

    def test_pas_decriture_si_validation_refusee(self):
        rows = ConstruireControle(self.donnees)
        rows[0]["valeurs"]["sans_porc"] = 100
        with self.assertRaises(ValueError):
            AppliquerControle(rows)
        self.assertTrue(all(not c.saisies for c in self.cases))


if __name__ == "__main__":
    unittest.main()
