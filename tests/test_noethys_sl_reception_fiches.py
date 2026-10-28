# -*- coding: utf-8 -*-
"""#436 : revue de documents parents sur donnees entierement fictives."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
from Utils import UTILS_Reception_fiches as F  # noqa: E402


class ReceptionAEEH(unittest.TestCase):
    def test_case_vide_ne_modifie_jamais_oui_ou_non(self):
        for courant in (None, 0, 1):
            with self.subTest(courant=courant):
                r = F.EvaluerDeclarationAEEH(42, courant, "absent", True)
                self.assertEqual(r["action"], "non_renseigne_sur_piece")
                self.assertIsNone(r["valeur_proposee"])
                self.assertFalse(r["ecriture_autorisee"])

    def test_oui_et_non_proposes_seulement_apres_relecture(self):
        for choix, statut in (("oui", 1), ("non", 0)):
            with self.subTest(choix=choix):
                r = F.EvaluerDeclarationAEEH(42, None, choix, True)
                self.assertEqual(r["action"], "a_reporter")
                self.assertEqual(r["valeur_proposee"], statut)
                self.assertFalse(r["ecriture_autorisee"])

    def test_dans_le_doute_une_relecture_est_requise(self):
        r = F.EvaluerDeclarationAEEH(42, None, "oui", False)
        self.assertEqual(r["action"], "relecture_requise")
        self.assertIsNone(r["valeur_proposee"])

    def test_declaration_identique_ne_change_rien(self):
        r = F.EvaluerDeclarationAEEH(42, 1, "oui", True)
        self.assertEqual(r["action"], "identique")
        self.assertEqual(r["valeur_proposee"], 1)

    def test_contradiction_a_arbitrer_par_un_agent(self):
        r = F.EvaluerDeclarationAEEH(42, 1, "non", True)
        self.assertEqual(r["action"], "a_reporter")
        self.assertEqual(r["valeur_proposee"], 0)
        self.assertFalse(r["ecriture_autorisee"])

    def test_jamais_de_duo_oui_et_non_ambigu(self):
        for choix in ("", "Oui", "oui/non", None, 1, True, "non renseigne"):
            with self.subTest(choix=choix), self.assertRaises(F.ReceptionFicheInvalide):
                F.EvaluerDeclarationAEEH(42, None, choix, True)

    def test_identifiant_invalide_ou_valeur_invalide(self):
        for identifiant in (None, 0, -1, True, "42"):
            with self.subTest(identifiant=identifiant), self.assertRaises(F.ReceptionFicheInvalide):
                F.EvaluerDeclarationAEEH(identifiant, None, "oui", True)
        for courant in (True, False, 2, "1"):
            with self.subTest(courant=courant), self.assertRaises(F.ReceptionFicheInvalide):
                F.EvaluerDeclarationAEEH(42, courant, "oui", True)

    def test_relecture_booleen_strict(self):
        for flag in (1, "oui", None):
            with self.subTest(flag=flag), self.assertRaises(F.ReceptionFicheInvalide):
                F.EvaluerDeclarationAEEH(42, None, "oui", flag)


class Periodes(unittest.TestCase):
    base = [{"date_debut": "2026-01-01", "date_fin": "2026-12-31"}]

    def test_non_renseignee_ne_genere_aucune_periode(self):
        r = F.ComparerPeriodeAEEH(periodes_existantes=self.base)
        self.assertEqual(r["action"], "dates_non_communiquees")
        self.assertFalse(r["ecriture_autorisee"])

    def test_une_periode_existante_est_detectee(self):
        r = F.ComparerPeriodeAEEH("2026-01-01", "2026-12-31", self.base)
        self.assertEqual(r["action"], "periode_deja_connue")
        self.assertFalse(r["ecriture_autorisee"])

    def test_nouvelle_periode_disjointe_a_verifier(self):
        r = F.ComparerPeriodeAEEH("2027-01-01", "2027-06-30", self.base)
        self.assertEqual(r["action"], "periode_a_verifier")
        self.assertEqual(r["date_fin"], "2027-06-30")

    def test_chevauchement_et_fin_ouverte_exigent_arbitrage(self):
        r = F.ComparerPeriodeAEEH("2026-06-01", "2027-06-30", self.base)
        self.assertEqual(r["action"], "periode_a_arbitrer")
        ancien = [{"date_debut": "2026-01-01", "date_fin": None}]
        r = F.ComparerPeriodeAEEH("2027-02-01", "2027-08-31", ancien)
        self.assertEqual(r["action"], "periode_a_arbitrer")

    def test_bornes_inclusives_et_separation(self):
        r = F.ComparerPeriodeAEEH("2026-12-31", "2027-01-01", self.base)
        self.assertEqual(r["action"], "periode_a_arbitrer")
        r = F.ComparerPeriodeAEEH("2027-01-01", None, self.base)
        self.assertEqual(r["action"], "periode_a_verifier")

    def test_dates_incorrectes_refusees(self):
        for debut, fin in ((None, "2026-12-31"), ("2026-12-31", "2026-01-01"),
                           ("2026-02-30", None), ("02/01/2026", None)):
            with self.subTest(debut=debut, fin=fin), self.assertRaises(F.ReceptionFicheInvalide):
                F.ComparerPeriodeAEEH(debut, fin, self.base)

    def test_historique_invalide_refuse(self):
        for historique in (None, "2026", [None], [{"date_debut": "2026-12-31", "date_fin": "2026-01-01"}]):
            with self.subTest(historique=historique), self.assertRaises(F.ReceptionFicheInvalide):
                F.ComparerPeriodeAEEH(None, None, historique)


class Sante(unittest.TestCase):
    def test_toutes_les_verifications_restent_a_effectuer(self):
        for relu in (False, True):
            self.assertEqual(set(F.PreparerControlesMedicaux(relu)), set(F.RUBRIQUES_MEDICALES))
            self.assertEqual(set(F.PreparerControlesMedicaux(relu).values()), {"a_verifier"})

    def test_qualif_donnees_de_sante_ne_sort_pas_du_moteur(self):
        self.assertNotIn("diagnostic", str(F.PreparerControlesMedicaux(True)))

    def test_indicateur_relecture_malforme_refuse(self):
        for v in (None, "oui", 1):
            with self.subTest(v=v), self.assertRaises(F.ReceptionFicheInvalide):
                F.PreparerControlesMedicaux(v)


if __name__ == "__main__":
    unittest.main()
