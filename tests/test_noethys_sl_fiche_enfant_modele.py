# -*- coding: utf-8 -*-
"""#436 : concordance source Fiche Enfant PMSL, aucune base et aucun PAI bis."""
import unittest
from Utils import UTILS_Fiche_enfant_modele as M


class FormulaireEnfantTests(unittest.TestCase):
    def test_sept_rubriques_papier_dans_le_bon_ordre(self):
        self.assertEqual([x["code"] for x in M.PlanDeFiche()["sections"]],
                         ["identite", "responsables", "accompagnants",
                          "vaccinations", "medecin", "sante", "autorisations",
                          "declaration"])

    def test_liberes_source_papier(self):
        self.assertEqual([x["libelle"] for x in M.PlanDeFiche()["autorisations_papier"]],
                         ["Photos (site internet : pelemele.org)", "Maquillage",
                          "Baignade", "Activités physiques"])

    def test_onglet_medical_reutilise(self):
        plan = M.PlanDeFiche()
        for code in ("vaccinations", "medecin", "sante"):
            self.assertEqual(next(x["onglet"] for x in plan["sections"]
                                  if x["code"] == code), "medical")
        self.assertFalse(plan["nouveau_dossier_medical"])

    def test_anciens_champs_restent_leur_source(self):
        plan = M.PlanDeFiche()
        self.assertEqual(plan["donnees_existantes"]["aeeh"], "identite")
        self.assertEqual(plan["donnees_existantes"]["repas"], "questionnaire")
        self.assertFalse(plan["portail_parents"])

    def test_absence_autorisations_ne_devient_pas_consentement(self):
        plan = M.PlanDeFiche()
        self.assertEqual({x["etat"] for x in plan["autorisations_papier"]},
                         {"non_renseigne"})

    def test_quatre_etats_explicites(self):
        codes = [c for c, _ in M.AUTORISATIONS_PAPIER]
        for etat in ("oui", "non", "non_renseigne", "expire", "a_verifier"):
            self.assertTrue(M.ValiderConcordance(dict.fromkeys(codes, etat)))

    def test_absence_et_inconnue_refusees(self):
        codes = [c for c, _ in M.AUTORISATIONS_PAPIER]
        with self.assertRaises(ValueError):
            M.ValiderConcordance(dict.fromkeys(codes[:-1], "non"))
        with self.assertRaises(ValueError):
            M.ValiderConcordance(dict.fromkeys(codes, "peut-etre"))


if __name__ == "__main__":
    unittest.main()
