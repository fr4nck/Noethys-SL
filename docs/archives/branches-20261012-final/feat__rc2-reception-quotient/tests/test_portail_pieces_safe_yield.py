"""Regression tests for the parent passed to SafeYield during piece downloads."""
import ast
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


SOURCE = Path(__file__).resolve().parents[1] / "noethys/Dlg/DLG_Saisie_portail_demande.py"


class DownloadReached(Exception):
    pass


class Window:
    pass


class TraitementPiecesYieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        traitement = next(node for node in tree.body
                          if isinstance(node, ast.ClassDef) and node.name == "Traitement")
        method = next(node for node in traitement.body
                      if isinstance(node, ast.FunctionDef) and node.name == "Traitement_pieces")
        cls.code = compile(ast.Module(body=[method], type_ignores=[]), str(SOURCE), "exec")

    def run_download(self, parent, phoenix=True):
        wx = SimpleNamespace(
            Window=Window, PlatformInfo=("phoenix",) if phoenix else (),
            BusyInfo=Mock(), SafeYield=Mock(), Yield=Mock(),
        )
        utils = ModuleType("Utils")
        synchro = Mock(side_effect=DownloadReached)
        utils.UTILS_Portail_synchro = SimpleNamespace(Synchro=synchro)
        namespace = {"wx": wx, "_": lambda text: text}
        exec(self.code, namespace)
        traitement = SimpleNamespace(
            parent=parent, dict_parametres={},
            track=SimpleNamespace(description="Envoi de la pièce test"),
        )
        with patch.dict(sys.modules, {"Utils": utils}):
            with self.assertRaises(DownloadReached):
                namespace["Traitement_pieces"](traitement)
        synchro.assert_called_once_with(log=traitement.track)
        return wx

    def test_window_parent_is_forwarded(self):
        parent = Window()
        wx = self.run_download(parent)
        wx.SafeYield.assert_called_once_with(parent, True)
        wx.Yield.assert_not_called()

    def test_missing_parent_uses_none(self):
        self.run_download(None).SafeYield.assert_called_once_with(None, True)

    def test_non_window_parent_uses_none(self):
        self.run_download(object()).SafeYield.assert_called_once_with(None, True)

    def test_classic_wx_still_uses_yield(self):
        wx = self.run_download(object(), phoenix=False)
        wx.Yield.assert_called_once_with()
        wx.SafeYield.assert_not_called()


if __name__ == "__main__":
    unittest.main()

