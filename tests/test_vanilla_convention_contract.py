# -*- coding: utf-8 -*-
"""Contrat de source pour le point d'entree Convention de la fiche
Famille, apres refactor : le moteur redevient generique (DLG_Noedoc),
plus un moteur ReportLab dedie ni pilote par un questionnaire
obligatoire. Voir aussi test_vanilla_convention_rendering.py pour la
verification d'execution reelle (pas seulement de source).
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLG_FAMILLE = ROOT / "noethys" / "Dlg" / "DLG_Famille.py"
DLG_GENERATION = ROOT / "noethys" / "Dlg" / "DLG_Generation_convention.py"
UTIL_CONVENTION = ROOT / "noethys" / "Utils" / "UTILS_Impression_convention.py"
UTIL_CHAMPS = ROOT / "noethys" / "Utils" / "UTILS_Convention_champs.py"


class ConventionContractTests(unittest.TestCase):
    def test_family_tools_exposes_convention_generation(self):
        source = DLG_FAMILLE.read_text(encoding="utf-8")
        self.assertIn("Générer une convention", source)
        self.assertIn("def MenuGenererConvention", source)
        self.assertIn("DLG_Generation_convention", source)
        self.assertIn("UTILS_Impression_convention.Impression(", source)
        self.assertIn("IDmodele=IDmodele", source)
        self.assertIn("UTILS_Convention_docx.Impression(", source)
        self.assertIn("modele=modele_docx", source)

    def test_generation_dialog_lets_user_choose_model_and_period(self):
        source = DLG_GENERATION.read_text(encoding="utf-8")
        self.assertIn('categorie="convention"', source)
        self.assertIn("CTRL_Choice", source)
        self.assertIn("MyDatePickerCtrl", source)
        self.assertIn("wx.FilePickerCtrl", source)
        self.assertIn("Word modifiable (.docx)", source)

    def test_generation_dialog_exposes_manual_fields_and_planning_button(self):
        """ Dernier jalon : ce qui est annoncé comme "manuel" dans le
        rapport (fonction, date/lieu de signature, tarif ambigu) doit
        être réellement saisissable depuis ce dialogue, pas seulement
        documenté. Le bouton Planning doit réutiliser le moteur
        Réservations existant, jamais un second moteur PDF. """
        source = DLG_GENERATION.read_text(encoding="utf-8")
        self.assertIn("ctrl_representant_fonction", source)
        self.assertIn("ctrl_date_signature", source)
        self.assertIn("ctrl_lieu_signature", source)
        self.assertIn("ctrl_tarif_horaire", source)
        self.assertIn("def GetOverrides", source)
        self.assertIn("def OnSelection", source)
        self.assertIn("def OnBoutonPlanning", source)
        self.assertIn("UTILS_Impression_reservations", source)
        self.assertNotIn("SimpleDocTemplate", source)
        self.assertNotIn("BaseDocTemplate", source)

    def test_overrides_are_applied_without_touching_noethys_data(self):
        source = UTIL_CHAMPS.read_text(encoding="utf-8")
        self.assertIn("def GetChampsConvention(", source)
        self.assertIn("overrides", source)
        for table_interdite in ("prestations", "consommations", "tarifs", "individus", "familles"):
            self.assertNotIn('ReqMAJ("%s"' % table_interdite, source)
            self.assertNotIn('ReqInsert("%s"' % table_interdite, source)

    def test_convention_engine_reuses_noedoc_instead_of_a_dedicated_engine(self):
        source = UTIL_CONVENTION.read_text(encoding="utf-8")
        self.assertIn("DLG_Noedoc", source)
        self.assertIn("ModeleDoc", source)
        self.assertIn("cadre_principal", source)
        # Le pilotage obligatoire par questionnaire ("Saison de la
        # convention", "Type de structure") de la première version a
        # disparu : la saison est un paramètre optionnel de Impression(),
        # plus une précondition.
        self.assertNotIn("QUESTION_SAISON", source)
        self.assertNotIn("QUESTION_TYPE", source)
        self.assertNotIn("UTILS_Questionnaires", source)
        # Non-régression du refactor : plus de mise en page ReportLab
        # construite à la main pour cette catégorie.
        self.assertNotIn("SimpleDocTemplate", source)
        self.assertNotIn("_pdf_association", source)

    def test_champs_provider_does_not_duplicate_reservations_query(self):
        """ Guardrail 4 : le fournisseur de champs ne doit pas
        réimplémenter une requête concurrente de
        UTILS_Impression_reservations. """
        source = UTIL_CHAMPS.read_text(encoding="utf-8")
        self.assertIn("UTILS_Impression_reservations", source)
        self.assertIn("GetDonnees", source)


if __name__ == "__main__":
    unittest.main()
