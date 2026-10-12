import ast
import unittest
from dataclasses import dataclass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from audit_ui_execution import execute_handler
from audit_ui_second_pass import (
    MetaVisitor,
    menu_append_is_real,
    find_handler,
    binding_candidates,
    better_id_for_command,
)


@dataclass
class FakeCommand:
    path: str
    class_name: str
    function_name: str
    line: int
    kind: str = "menu"
    source: str = ""
    command_id: str = ""
    label: str = ""
    event: str = ""
    handler: str = ""
    status: str = "BLOCKED"
    defect_type: str = "STATIC_BIND_UNRESOLVED"
    severity: str = ""
    result_obtained: str = ""
    trace: str = ""


class ExecutionProofTests(unittest.TestCase):
    def _fn(self, source, name="OnAjouter"):
        tree = ast.parse(source)
        return next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name)

    def test_simple_delegation_is_really_executed(self):
        node = self._fn("def OnAjouter(self, event):\n    self.ctrl.Ajouter()\n")
        proof = execute_handler(node, "Ajouter", "self.bouton_ajouter", "self.OnAjouter")
        self.assertTrue(proof.ok)
        self.assertEqual(proof.action, "self.ctrl.Ajouter")
        self.assertEqual(proof.calls[0].path, "self.ctrl.Ajouter")

    def test_branch_is_refused(self):
        node = self._fn("def OnAjouter(self, event):\n    if self.ok:\n        self.ctrl.Ajouter()\n")
        self.assertFalse(execute_handler(node, "Ajouter", "", "self.OnAjouter").ok)

    def test_close_modal_is_executed(self):
        node = self._fn("def OnFermer(self, event):\n    self.EndModal(wx.ID_CANCEL)\n", "OnFermer")
        proof = execute_handler(node, "Fermer", "", "self.OnFermer")
        self.assertTrue(proof.ok)
        self.assertEqual(proof.action, "self.EndModal")

    def test_event_skip_can_accompany_action(self):
        node = self._fn("def OnModifier(self, event):\n    self.Modifier()\n    event.Skip()\n", "OnModifier")
        proof = execute_handler(node, "Modifier", "", "self.OnModifier")
        self.assertTrue(proof.ok)
        self.assertEqual([call.path for call in proof.calls], ["self.Modifier", "event.Skip"])

    def test_nested_context_menu_handler_executes_captured_action(self):
        tree = ast.parse("""
def OnContext(self, event):
    date = event.date
    def Ajouter(evt):
        self.Ajouter(date)
""")
        node = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "Ajouter")
        proof = execute_handler(node, "Ajouter", "item", "Ajouter")
        self.assertTrue(proof.ok)
        self.assertEqual(proof.action, "self.Ajouter")


class CorrelationTests(unittest.TestCase):
    def _meta(self, source):
        visitor = MetaVisitor("noethys/Fake.py")
        visitor.meta.tree = ast.parse(source)
        visitor.visit(visitor.meta.tree)
        return visitor.meta

    def test_propertygrid_append_is_not_menu(self):
        meta = self._meta("""
class CTRL:
    def f(self):
        self.Append(wxpg.BoolProperty(label='x'))
""")
        cmd = FakeCommand("noethys/Fake.py", "CTRL", "f", 4, source="self#menu@4")
        self.assertFalse(menu_append_is_real(meta, cmd))

    def test_known_menu_append_is_real(self):
        meta = self._meta("""
class CTRL:
    def f(self):
        menuPop = UTILS_Adaptations.Menu()
        menuPop.Append(10, 'Ajouter')
""")
        cmd = FakeCommand("noethys/Fake.py", "CTRL", "f", 5, source="menuPop#menu@5")
        self.assertTrue(menu_append_is_real(meta, cmd))

    def test_menuitem_uses_second_positional_argument_as_id(self):
        meta = self._meta("""
class CTRL:
    def f(self):
        item = wx.MenuItem(menuPop, 20, 'Imprimer')
""")
        cmd = FakeCommand("noethys/Fake.py", "CTRL", "f", 4, source="item", command_id="menuPop")
        self.assertEqual(better_id_for_command(meta, cmd), "20")

    def test_third_bind_argument_is_source_even_when_owner_is_self(self):
        meta = self._meta("""
class CTRL:
    def f(self):
        self.Bind(wx.EVT_BUTTON, self.OnAjouter, self.bouton_ajouter)
    def OnAjouter(self, event):
        self.Ajouter()
""")
        self.assertEqual(meta.bindings[0].source, "self.bouton_ajouter")
        cmd = FakeCommand("noethys/Fake.py", "CTRL", "f", 4, source="self.bouton_ajouter", label="Ajouter")
        self.assertEqual(binding_candidates(meta, cmd)[0].handler, "self.OnAjouter")

    def test_menuitem_matches_bind_by_corrected_id(self):
        meta = self._meta("""
class CTRL:
    def f(self):
        item = wx.MenuItem(menuPop, 20, 'Imprimer')
        self.Bind(wx.EVT_MENU, self.Imprimer, id=20)
    def Imprimer(self, event):
        self.ctrl.Imprimer()
""")
        cmd = FakeCommand("noethys/Fake.py", "CTRL", "f", 4, source="item", command_id="menuPop", label="Imprimer")
        matches = binding_candidates(meta, cmd)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].handler, "self.Imprimer")

    def test_same_file_inherited_handler_is_resolved(self):
        meta = self._meta("""
class Base:
    def OnFermer(self, event):
        self.Destroy()
class Child(Base):
    def f(self):
        self.Bind(wx.EVT_BUTTON, self.OnFermer, self.button)
""")
        node, inherited = find_handler(meta, "Child", "self.OnFermer", 7)
        self.assertIsNotNone(node)
        self.assertTrue(inherited)

    def test_getattr_literal_handler_is_resolved_textually(self):
        meta = self._meta("""
class CTRL:
    def f(self):
        self.Bind(wx.EVT_BUTTON, getattr(self, 'OnAjouter'), self.button)
""")
        self.assertEqual(meta.bindings[0].handler, "self.OnAjouter")


class RepositoryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        if not (cls.root / "noethys").is_dir():
            raise unittest.SkipTest("repository tree only available in CI checkout")

    def test_business_tree_is_available_in_ci(self):
        self.assertTrue((self.root / "noethys").is_dir())

    def test_updater_cancel_is_disabled_before_calllater(self):
        path = self.root / "noethys" / "Dlg" / "DLG_Updater.py"
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        page = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Page_installation")
        installation = next(node for node in page.body if isinstance(node, ast.FunctionDef) and node.name == "Installation")
        calls = [node for node in ast.walk(installation) if isinstance(node, ast.Call)]
        rendered = [ast.unparse(call) for call in calls]
        disable_pos = next(i for i, text in enumerate(rendered) if "bouton_annuler.Enable(False)" in text)
        later_pos = next(i for i, text in enumerate(rendered) if "wx.CallLater" in text)
        self.assertLess(disable_pos, later_pos)

    def test_badgeage_empty_handler_only_contains_pass_and_commented_behavior(self):
        path = self.root / "noethys" / "Dlg" / "DLG_Badgeage_saisie_procedure.py"
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "CTRL_Interface")
        handler = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "OnChoixIdentification")
        body = [stmt for stmt in handler.body if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str))]
        self.assertEqual(len(body), 1)
        self.assertIsInstance(body[0], ast.Pass)
        self.assertIn("self.check_activites.Enable(self.radio_liste.GetValue())", source)


if __name__ == "__main__":
    unittest.main()
