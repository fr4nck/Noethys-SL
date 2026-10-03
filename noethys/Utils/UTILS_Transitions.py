# -*- coding: utf-8 -*-
"""Fondus courts des dialogues, avec repli immédiat sans transparence."""
import wx


class DialogFondu(wx.Dialog):
    def _Alpha(self, value):
        try:
            return bool(self.SetTransparent(value))
        except RuntimeError:
            return False

    def _Animer(self, valeurs, termine):
        self._fondu_generation = getattr(self, "_fondu_generation", 0) + 1
        generation = self._fondu_generation
        def pas(index=0):
            if not self or generation != self._fondu_generation:
                return
            if index == len(valeurs) or not self._Alpha(valeurs[index]):
                termine()
                return
            wx.CallLater(20, pas, index + 1)
        pas()

    def ShowModal(self):
        self._fondu_fermeture = False
        if self._Alpha(190):
            wx.CallAfter(self._Animer, (205, 220, 235, 245, 255), lambda: None)
        try:
            return wx.Dialog.ShowModal(self)
        finally:
            self._fondu_generation = getattr(self, "_fondu_generation", 0) + 1
            if self:
                self._Alpha(255)

    def _FermerFondu(self, termine):
        if getattr(self, "_fondu_fermeture", False):
            return
        self._fondu_fermeture = True
        if self.IsShown() and self.IsModal():
            self._Animer((245, 230, 215, 200, 190), termine)
        else:
            termine()

    def EndModal(self, code):
        self._FermerFondu(lambda: wx.Dialog.EndModal(self, code))

    def Destroy(self):
        if self.IsShown() and self.IsModal():
            self._FermerFondu(lambda: wx.Dialog.Destroy(self))
            return True
        self._fondu_generation = getattr(self, "_fondu_generation", 0) + 1
        return wx.Dialog.Destroy(self)

