# -*- coding: utf-8 -*-
"""Saisie d'adresse : une commune homonyme ne voit jamais son code postal
remplacé silencieusement (repris de master 79680bda, porté sur l'interface
de main). Méthodes appelées sur des doublures : aucune fenêtre créée.
"""
import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import unittest  # noqa: E402
from unittest import mock  # noqa: E402

import wx  # noqa: E402

_APP = wx.GetApp() or wx.App(False)

from Ctrl import CTRL_Saisie_adresse  # noqa: E402

VILLES = [("VITRÉ", "35500"), ("VITRÉ", "79370"), ("CHASSELAY", "69380"), ("RENNES", "35000")]


class _Evenement(object):
    def __init__(self, texte=""):
        self.texte = texte
        self.skip = 0

    def GetString(self):
        return self.texte

    def Skip(self):
        self.skip += 1


class _Champ(object):
    def __init__(self, valeur=""):
        self.valeur = valeur

    def GetValue(self):
        return self.valeur

    def SetValue(self, valeur):
        self.valeur = valeur


class _Ville(_Champ):
    def __init__(self, valeur, cp):
        _Champ.__init__(self, valeur)
        self.ctrlCp = _Champ(cp)
        self.listeVilles = VILLES
        self.listeNomsVilles = [v for v, c in VILLES]
        self.autoComplete = True
        self.ignoreEvtText = False
        self.ChoixCodes = mock.Mock(return_value="")

    def SetInsertionPoint(self, position):
        pass

    def SetSelection(self, debut, fin):
        pass


Ville = CTRL_Saisie_adresse.TextCtrlVille


class HomonymesTests(unittest.TestCase):
    def test_perte_de_focus_conserve_le_couple_homonyme_choisi(self):
        ctrl = _Ville("VITRÉ", "79370")
        Ville.OnKillFocus(ctrl, _Evenement())
        self.assertEqual(ctrl.ctrlCp.GetValue(), "79370")
        ctrl.ChoixCodes.assert_not_called()

    def test_perte_de_focus_propose_le_choix_si_couple_incomplet(self):
        ctrl = _Ville("VITRÉ", "")
        ctrl.ChoixCodes.return_value = "35500"
        Ville.OnKillFocus(ctrl, _Evenement())
        ctrl.ChoixCodes.assert_called_once_with("VITRÉ", ["35500", "79370"])
        self.assertEqual(ctrl.ctrlCp.GetValue(), "35500")

    def test_perte_de_focus_complete_un_code_unique(self):
        ctrl = _Ville("RENNES", "")
        Ville.OnKillFocus(ctrl, _Evenement())
        self.assertEqual(ctrl.ctrlCp.GetValue(), "35000")

    def test_frappe_ne_reecrit_pas_le_code_d_une_ville_homonyme(self):
        ctrl = _Ville("VITRÉ", "79370")
        Ville.OnText(ctrl, _Evenement("VITRÉ"))
        self.assertEqual(ctrl.ctrlCp.GetValue(), "79370")

    def test_frappe_ambigue_ne_choisit_pas_au_hasard(self):
        ctrl = _Ville("VIT", "")
        Ville.OnText(ctrl, _Evenement("VIT"))
        self.assertEqual(ctrl.ctrlCp.GetValue(), "")
        self.assertEqual(ctrl.GetValue(), "VIT")

    def test_frappe_unique_complete_ville_et_code(self):
        ctrl = _Ville("chass", "")
        Ville.OnText(ctrl, _Evenement("chass"))
        self.assertEqual((ctrl.GetValue(), ctrl.ctrlCp.GetValue()), ("CHASSELAY", "69380"))


if __name__ == "__main__":
    unittest.main()
