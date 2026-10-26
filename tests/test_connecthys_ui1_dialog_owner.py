# -*- coding: utf-8 -*-
"""UI-1: dialog owner and hidden Mailer regressions, with no real users or network."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAILER = ROOT / "noethys" / "Dlg" / "DLG_Mailer.py"
CONNECT = ROOT / "noethys" / "Dlg" / "DLG_Saisie_portail_demande.py"
EMAIL = ROOT / "noethys" / "Utils" / "UTILS_Envoi_email.py"


def method(path, cls, name):
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    fun = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(text, fun)


class ModalOwnerContracts(unittest.TestCase):
    def test_hidden_mailer_not_reopened_on_validation_error(self):
        src = method(MAILER, "Dialog", "Envoyer")
        self.assertNotIn("self.ShowModal()", src)
        self.assertIn("parent_dialogue = self._ParentVisiblePourDialogue()", src)
        self.assertIn("wx.MessageDialog(parent_dialogue,", src)

    def test_visible_parent_resolution(self):
        src = method(MAILER, "Dialog", "_ParentVisiblePourDialogue")
        self.assertIn("IsShownOnScreen()", src)
        self.assertIn("fenetre.GetParent()", src)

    def test_progress_and_report_owned(self):
        src = method(MAILER, "Dialog", "Envoyer")
        self.assertIn("parent_progress = parent_dialogue", src)
        lot = method(MAILER, "Dialog", "_EnvoyerLotMailjetHorsUI")
        self.assertIn("parent=parent_progress", lot)

    def test_reservation_warning_owned_by_connecthys(self):
        src = method(CONNECT, "Traitement", "Appliquer_reservations")
        self.assertIn("DLG_Messagebox.Dialog(self.parent,", src)
        self.assertNotIn("DLG_Messagebox.Dialog(None,", src)

    def test_report_accepts_optional_parent_without_changing_acceptance(self):
        src = EMAIL.read_text(encoding="utf-8")
        tree = ast.parse(src)
        method_node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_AfficherCompteRendu")
        sig = [arg.arg for arg in method_node.args.args]
        self.assertEqual(sig[-1], "parent")
        self.assertIn("dlg = wx.MessageDialog(parent, texte,", ast.get_source_segment(src, method_node))
        self.assertIn("dlg = DLG_Messagebox.Dialog(parent,", ast.get_source_segment(src, method_node))


if __name__ == "__main__":
    unittest.main()
