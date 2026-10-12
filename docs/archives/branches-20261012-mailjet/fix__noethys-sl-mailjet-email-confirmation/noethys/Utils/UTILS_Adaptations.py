#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Auteur:          Ivan LUCAS
# Copyright:       (c) 2010-17 Ivan LUCAS
# Licence:         Licence GNU GPL
#------------------------------------------------------------------------

import wx
import sys
import types
import threading
from importlib import import_module


# Compatibilité des API retirées sous Python 3 / wxPython Phoenix.
# Ces alias conservent le comportement attendu par le code historique sans
# modifier les parcours wxClassic/Python 2.
if not hasattr(types, "StringTypes"):
    types.StringTypes = (str,)

if not hasattr(threading.Thread, "isAlive") and hasattr(threading.Thread, "is_alive"):
    threading.Thread.isAlive = threading.Thread.is_alive

if 'phoenix' in wx.PlatformInfo:
    if not hasattr(wx.PrintPreview, "Ok") and hasattr(wx.PrintPreview, "IsOk"):
        wx.PrintPreview.Ok = wx.PrintPreview.IsOk

    if not hasattr(wx.PreviewFrame, "MakeModal"):
        def _PreviewFrameMakeModal(self, modal=True):
            return None
        wx.PreviewFrame.MakeModal = _PreviewFrameMakeModal

    # wxClassic acceptait dans plusieurs parcours historiques des dimensions
    # calculées en flottants. Phoenix exige des entiers pour Scale/Rescale.
    _ImageScale = wx.Image.Scale
    _ImageRescale = wx.Image.Rescale

    def _ImageScaleEntier(self, width, height, *args, **kwargs):
        return _ImageScale(self, int(width), int(height), *args, **kwargs)

    def _ImageRescaleEntier(self, width, height, *args, **kwargs):
        return _ImageRescale(self, int(width), int(height), *args, **kwargs)

    wx.Image.Scale = _ImageScaleEntier
    wx.Image.Rescale = _ImageRescaleEntier

    # wx.lib.agw.supertooltip.ToolTipWindowBase.CalculateBestSize() fait
    # `largeur, hauteur = self.OnPaint(None); self.SetSize((largeur, hauteur))`.
    # OnPaint() mélange division entière (//) et division réelle (/) selon
    # les options du tooltip : dès qu'un bitmap de pied de page est défini
    # (SetFooterBitmap), le calcul de la hauteur totale passe par une
    # division réelle et devient un flottant. SetSize() reçoit alors une
    # hauteur flottante, ce qui tronque visuellement le tooltip sous
    # wxPython 4.2.5 (ex. hauteur ~20px au lieu de la hauteur réelle du
    # message sur 8-10 lignes) au lieu de lever une erreur.
    # On rejoue exactement le même calcul (OnPaint(None) est inchangé,
    # public, et documenté pour être appelable avec event=None) en forçant
    # des coordonnées entières, sans modifier wx.lib.agw.supertooltip.
    import wx.lib.agw.supertooltip as _STT

    def _ToolTipCalculateBestSizeEntier(self):
        largeur, hauteur = self.OnPaint(None)
        self.SetSize((int(largeur), int(hauteur)))

    _STT.ToolTipWindowBase.CalculateBestSize = _ToolTipCalculateBestSizeEntier


def Import(nom_module=""):
    # Essaye d'importer
    try :
        module = import_module(nom_module)
        return module
    except ImportError:
        pass

    # Recherche si le module est déjà chargé
    if nom_module in sys.modules:
        module = sys.modules[nom_module]
        return module

    # Essaye d'importer sans le module_path
    module_path, class_name = nom_module.rsplit('.', 1)
    try :
        module = import_module(class_name)
        return module
    except ImportError:
        pass

    return None



class Menu(wx.Menu):
    def __init__(self, *args, **kwds):
        wx.Menu.__init__(self, *args, **kwds)

    def AppendItem(self, item):
        if 'phoenix' in wx.PlatformInfo:
            super(Menu, self).Append(item)
        else :
            super(Menu, self).AppendItem(item)

    def AppendMenu(self, *args, **kwds):
        if 'phoenix' in wx.PlatformInfo:
            super(Menu, self).Append(*args, **kwds)
        else :
            super(Menu, self).AppendMenu(*args, **kwds)


class ToolBar(wx.ToolBar):
    def __init__(self, *args, **kwds):
        wx.ToolBar.__init__(self, *args, **kwds)

    def AddLabelTool(self, *args, **kw):
        if 'phoenix' in wx.PlatformInfo:
            if "longHelp" in kw:
                kw.pop("longHelp")
            super(ToolBar, self).AddTool(*args, **kw)
        else :
            super(ToolBar, self).AddLabelTool(*args, **kw)

    def AddSimpleTool(self, *args, **kw):
        if 'phoenix' in wx.PlatformInfo:
            if "longHelp" in kw:
                kw.pop("longHelp")
            super(ToolBar, self).AddTool(*args, **kw)
        else :
            super(ToolBar, self).AddSimpleTool(*args, **kw)


if __name__ == "__main__":
    pass