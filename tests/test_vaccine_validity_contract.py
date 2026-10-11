import ast
import types
import unittest
from pathlib import Path

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "noethys/Dlg/DLG_Saisie_typesVaccins.py"
)

class Control:
    def __init__(self, value=None):
        self.value = value

    def GetValue(self):
        return self.value

    def SetValue(self, value):
        self.value = value

    def SetFocus(self):
        pass

class FakeDialog:
    count = 0

    def __init__(self, *args, **kwargs):
        type(self).count += 1

    def ShowModal(self):
        return 1

    def Destroy(self):
        pass

WX = types.SimpleNamespace(
    MessageDialog=FakeDialog,
    OK=1,
    ICON_EXCLAMATION=2,
    ID_OK=5100,
)

def load_method(name):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    dialog = next(
        n for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == "Dialog"
    )
    method = next(
        n for n in dialog.body
        if isinstance(n, ast.FunctionDef) and n.name == name
    )
    module = ast.Module(body=[method], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"wx": WX, "_": lambda value: value}
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace[name]

class ValidationPage:
    def __init__(self, diseases):
        self.ctrl_nom = Control("Vaccin test")
        self.spin_jours = Control(0)
        self.spin_mois = Control(0)
        self.spin_annees = Control(0)
        self.radio_duree_2 = Control(False)
        self.ctrl_maladies = types.SimpleNamespace(
            GetIDcoches=lambda: diseases
        )
        self.ended = []

    def EndModal(self, code):
        self.ended.append(code)

class DurationPage:
    def __init__(self):
        self.radio_duree_1 = Control(False)
        self.radio_duree_2 = Control(False)
        self.spin_jours = Control(0)
        self.spin_mois = Control(0)
        self.spin_annees = Control(0)
        self.refreshes = 0

    def OnRadioDuree(self, event):
        self.refreshes += 1

class VaccineValidityTests(unittest.TestCase):
    def setUp(self):
        FakeDialog.count = 0

    def test_empty_disease_selection_rejected(self):
        page = ValidationPage([])
        load_method("OnBoutonOk")(page, None)
        self.assertEqual(page.ended, [])
        self.assertEqual(FakeDialog.count, 1)

    def test_selected_disease_accepted(self):
        page = ValidationPage([7])
        load_method("OnBoutonOk")(page, None)
        self.assertEqual(page.ended, [WX.ID_OK])
        self.assertEqual(FakeDialog.count, 0)

    def test_none_validity_is_unlimited(self):
        page = DurationPage()
        load_method("SetValidite")(page, None)
        self.assertTrue(page.radio_duree_1.value)
        self.assertFalse(page.radio_duree_2.value)
        self.assertEqual(page.refreshes, 1)

    def test_zero_validity_is_unlimited(self):
        page = DurationPage()
        load_method("SetValidite")(page, "j0-m0-a0")
        self.assertTrue(page.radio_duree_1.value)
        self.assertFalse(page.radio_duree_2.value)

    def test_limited_validity_preserved(self):
        page = DurationPage()
        load_method("SetValidite")(page, "j5-m2-a1")
        self.assertFalse(page.radio_duree_1.value)
        self.assertTrue(page.radio_duree_2.value)
        self.assertEqual(
            (
                page.spin_jours.value,
                page.spin_mois.value,
                page.spin_annees.value,
            ),
            (5, 2, 1),
        )
