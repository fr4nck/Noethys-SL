#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Produit :        Noethys SL wx
# Licence:         Licence GNU GPL
#------------------------------------------------------------------------
"""Verrouillage de l'apparence claire de wxAUI pour Noethys SL wx.

Noethys SL 0.1.0 reste volontairement en apparence claire, y compris sous
Windows en thème sombre. Deux comportements de wx.lib.agw.aui (wxPython
4.2.5) empêchent d'obtenir ce résultat avec un simple appel ponctuel à
art.SetDefaultColours(base_colour=...) :

- wx.lib.agw.aui.dockart.AuiDefaultDockArt.SetDefaultColours() ne recalcule
  pas la légende de pane active (couleur de fond ni couleur de texte) : ces
  couleurs ne sont fixées que dans Init(), depuis wx.SystemSettings ;
- wx.lib.agw.aui.framemanager.AuiManager.OnSysColourChanged() (appelé sur
  wx.EVT_SYS_COLOUR_CHANGED, notamment lors d'un maximiser/redimensionner
  sous Windows) rappelle art.Init(), qui recalcule alors toute la palette
  depuis wx.SystemSettings et écrase silencieusement toute couleur fixée
  auparavant.

Ce module fournit deux art providers dédiés à Noethys SL wx qui héritent
proprement des classes publiques de wx.lib.agw.aui et surchargent leur
point d'entrée public (Init() pour le dock art, SetDefaultColours() pour
l'art des barres d'outils) afin que toute réinitialisation ultérieure,
quel que soit son déclencheur, reconverge vers la palette claire.

NoethysSLDockArt dérive de AuiDefaultDockArt plutôt que de ModernDockArt :
cela élimine structurellement le rendu de légende par thème natif Windows
(winxptheme.DrawThemeBackground), propre à ModernDockArt et qui ignorerait
de toute façon la palette de l'art provider.

Aucune logique métier ici : uniquement de la présentation wxAUI, centralisée
pour l'ensemble de la couche Noethys SL wx.
"""

import wx
import wx.lib.agw.aui as aui


COULEUR_FOND_CLAIRE = wx.Colour(240, 240, 240)
COULEUR_TEXTE_LEGENDE = wx.Colour(30, 30, 30)


class NoethysSLDockArt(aui.AuiDefaultDockArt):
    """Art provider wxAUI du AuiManager principal de Noethys SL wx.

    Conserve le rendu fonctionnel standard de AuiDefaultDockArt (fonds,
    séparateurs, bordures, boutons de légende) et verrouille uniquement sa
    palette de couleurs sur l'apparence claire Noethys SL.
    """

    def Init(self):
        # Initialisation standard de la classe parente (dimensions, police,
        # couleurs par défaut...).
        aui.AuiDefaultDockArt.Init(self)
        # Puis verrouillage de la palette Noethys SL par-dessus, via l'API
        # publique uniquement. Rejoué à l'identique à chaque appel de
        # Init(), y compris depuis AuiManager.OnSysColourChanged().
        self.SetDefaultColours(base_colour=COULEUR_FOND_CLAIRE)
        # SetDefaultColours() ne recalcule pas les couleurs de texte de
        # légende : on les fixe explicitement pour rester lisibles sur un
        # fond clair.
        self.SetColor(aui.AUI_DOCKART_ACTIVE_CAPTION_TEXT_COLOUR, COULEUR_TEXTE_LEGENDE)
        self.SetColor(aui.AUI_DOCKART_INACTIVE_CAPTION_TEXT_COLOUR, COULEUR_TEXTE_LEGENDE)
        # AuiDefaultDockArt.SetColor(AUI_DOCKART_ACTIVE_CAPTION_COLOUR, ...)
        # lit en interne l'attribut _custom_pane_bitmaps, que
        # AuiDefaultDockArt.__init__() ne crée qu'en appelant
        # SetDefaultPaneBitmaps() APRÈS Init() : au tout premier Init()
        # (celui de la construction), cet attribut n'existe donc pas
        # encore et SetColor() lève une AttributeError (vérifié à
        # l'exécution). Impossible de fixer cette couleur avec la seule
        # API publique SetColor()/SetDefaultColours() sans d'abord
        # provoquer nous-mêmes la création de cet attribut : on appelle
        # donc SetDefaultPaneBitmaps(), elle aussi publique, en avance —
        # avec nos couleurs de texte déjà posées ci-dessus, les bitmaps de
        # boutons de légende sont correctes dès ce premier appel.
        self.SetDefaultPaneBitmaps(wx.Platform == "__WXMAC__")
        self.SetColor(aui.AUI_DOCKART_ACTIVE_CAPTION_COLOUR, COULEUR_FOND_CLAIRE)
        self.SetColor(aui.AUI_DOCKART_ACTIVE_CAPTION_GRADIENT_COLOUR, COULEUR_FOND_CLAIRE)


class NoethysSLToolBarArt(aui.AuiDefaultToolBarArt):
    """Art provider wxAUI des AuiToolBar de Noethys SL wx.

    AuiDefaultToolBarArt calcule sa couleur de base depuis wx.SystemSettings
    dès sa construction (__init__ appelle SetDefaultColours() sans
    argument) et rien, dans wx.lib.agw.aui, ne la recalcule ensuite : il
    suffit donc de verrouiller ce point d'entrée public pour que la barre
    reste claire, y compris si du code appelant rappelait un jour
    SetDefaultColours() sans préciser de couleur.
    """

    def SetDefaultColours(self, base_colour=None):
        aui.AuiDefaultToolBarArt.SetDefaultColours(self, base_colour=COULEUR_FOND_CLAIRE)
