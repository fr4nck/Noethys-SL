# -*- coding: utf-8 -*-
"""Questionnaires : statut visible, action explicite, aucune mutation implicite."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "noethys"))
try:
    import wx
except ImportError:
    wx = None


@unittest.skipIf(wx is None, "wxPython absent")
class QuestionnaireDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from Dlg import DLG_Questionnaires
        cls.module = DLG_Questionnaires

    def faux_dialogue(self, etat):
        # Appelle les methodes du vrai Dialogue avec des contrôles simulés.
        dlg = SimpleNamespace(type="individu", label_repas=Mock(),
                              ctrl_questionnaire=Mock())
        dlg.ActualiserEtatRepas = lambda: etat
        return dlg

    def test_statut_pret_affiche_sans_edition(self):
        dlg = self.faux_dialogue(None)
        with patch.object(self.module.UTILS_Repas_questionnaire,
                          "ExaminerQuestionnaire",
                          return_value={"etat": "pret"}):
            resultat = self.module.Dialog.ActualiserEtatRepas(dlg)
        self.assertEqual(resultat["etat"], "pret")
        self.assertIn("PRÊT", dlg.label_repas.SetLabel.call_args.args[0])

    def test_statut_absent_et_conflit_distincts(self):
        dlg = self.faux_dialogue(None)
        with patch.object(self.module.UTILS_Repas_questionnaire,
                          "ExaminerQuestionnaire",
                          return_value={"etat": "absent"}):
            self.module.Dialog.ActualiserEtatRepas(dlg)
        self.assertIn("ABSENT", dlg.label_repas.SetLabel.call_args.args[0])
        with patch.object(self.module.UTILS_Repas_questionnaire,
                          "ExaminerQuestionnaire",
                          return_value={"etat": "conflit", "detail": "Incomplet"}):
            self.module.Dialog.ActualiserEtatRepas(dlg)
        self.assertIn("CORRIGER", dlg.label_repas.SetLabel.call_args.args[0])

    def test_creation_uniquement_apres_accord(self):
        dlg = self.faux_dialogue({"etat": "absent"})
        with patch.object(self.module.UTILS_Repas_questionnaire,
                          "PreparerQuestionnaire",
                          return_value={"etat": "pret"}) as preparer, \
             patch.object(self.module.wx, "MessageBox",
                          return_value=self.module.wx.YES):
            self.assertTrue(self.module.Dialog.OnPreparerQuestionnaireRepas(dlg))
        preparer.assert_called_once_with()
        dlg.ctrl_questionnaire.MAJ.assert_called_once()

    def test_refus_aucune_creation_ni_rafraichissement(self):
        dlg = self.faux_dialogue({"etat": "absent"})
        with patch.object(self.module.UTILS_Repas_questionnaire,
                          "PreparerQuestionnaire") as preparer, \
             patch.object(self.module.wx, "MessageBox",
                          return_value=self.module.wx.NO):
            self.assertFalse(self.module.Dialog.OnPreparerQuestionnaireRepas(dlg))
        preparer.assert_not_called()
        dlg.ctrl_questionnaire.MAJ.assert_not_called()

    def test_question_pret_aucun_prompt_ni_reecriture(self):
        dlg = self.faux_dialogue({"etat": "pret"})
        with patch.object(self.module.UTILS_Repas_questionnaire,
                          "PreparerQuestionnaire") as preparer, \
             patch.object(self.module.wx, "MessageBox") as popup:
            self.assertTrue(self.module.Dialog.OnPreparerQuestionnaireRepas(dlg))
        preparer.assert_not_called()
        popup.assert_not_called()

    def test_question_ambigue_stop_sans_edition(self):
        dlg = self.faux_dialogue({"etat": "conflit", "detail": "Doublon"})
        with patch.object(self.module.UTILS_Repas_questionnaire,
                          "PreparerQuestionnaire") as preparer, \
             patch.object(self.module.wx, "MessageBox") as popup:
            self.assertFalse(self.module.Dialog.OnPreparerQuestionnaireRepas(dlg))
        preparer.assert_not_called()
        popup.assert_called_once()

    def test_type_famille_ne_peut_pas_creer_question_individuelle(self):
        dlg = self.faux_dialogue({"etat": "absent"})
        dlg.type = "famille"
        with patch.object(self.module.UTILS_Repas_questionnaire,
                          "PreparerQuestionnaire") as preparer:
            self.assertFalse(self.module.Dialog.OnPreparerQuestionnaireRepas(dlg))
        preparer.assert_not_called()

    def test_indisponibilite_base_stop(self):
        dlg = self.faux_dialogue(None)
        with patch.object(self.module.UTILS_Repas_questionnaire,
                          "PreparerQuestionnaire") as preparer, \
             patch.object(self.module.wx, "MessageBox"):
            self.assertFalse(self.module.Dialog.OnPreparerQuestionnaireRepas(dlg))
        preparer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
