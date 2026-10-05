# -*- coding: utf-8 -*-
"""Fondus des dialogues : la modalité et le code de retour restent ceux de wx."""
from pathlib import Path
import sys
import unittest
import unittest.mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "noethys"))

import wx  # noqa: E402

from Utils.UTILS_Transitions import DialogFondu  # noqa: E402


class DialogFonduTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.GetApp() or wx.App(False)

    def test_showmodal_renvoie_le_code_de_endmodal(self):
        dlg = DialogFondu(None, -1, u"Essai")
        wx.CallLater(50, dlg.EndModal, wx.ID_OK)
        self.assertEqual(dlg.ShowModal(), wx.ID_OK)
        dlg.Destroy()

    def test_alpha_sur_dialogue_detruit_ne_leve_pas(self):
        # wxPython 4 lève RuntimeError sur un objet C++ détruit ;
        # wx.PyDeadObjectError n'existe plus.
        dlg = DialogFondu(None, -1, u"Essai")
        with unittest.mock.patch.object(DialogFondu, "SetTransparent",
                                        side_effect=RuntimeError("objet détruit")):
            self.assertFalse(dlg._Alpha(200))
        dlg.Destroy()

    def test_dialogues_convention_noedoc_et_identification_utilisent_le_fondu(self):
        from Dlg import DLG_Generation_convention, DLG_Noedoc
        from Ctrl import CTRL_Identification
        self.assertTrue(issubclass(DLG_Generation_convention.Dialog, DialogFondu))
        self.assertTrue(issubclass(DLG_Noedoc.Dialog, DialogFondu))
        self.assertTrue(issubclass(CTRL_Identification.Dialog, DialogFondu))


if __name__ == "__main__":
    unittest.main()
