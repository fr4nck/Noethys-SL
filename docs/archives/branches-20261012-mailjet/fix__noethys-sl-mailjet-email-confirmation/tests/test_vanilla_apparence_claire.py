# -*- coding: utf-8 -*-
"""Non-regression : Noethys SL 0.1.0 reste en apparence claire.

AuiDefaultDockArt (wx.lib.agw.aui) derive ses fonds, separations et
bordures des couleurs systeme Windows, et AuiManager les redemande a
chaque wx.EVT_SYS_COLOUR_CHANGED. Pendant la stabilisation de Noethys SL,
l'application utilise donc des art providers dedies (Utils.UTILS_AUI_
Apparence.NoethysSLDockArt / NoethysSLToolBarArt) dont la palette claire
resiste a toute reinitialisation ulterieure, et neutralise les anciens
profils ayant memorise l'accent Noir.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

import wx  # noqa: E402
import wx.lib.agw.aui as aui  # noqa: E402

_APP = wx.App(False)

import Noethys  # noqa: E402
from Utils import UTILS_AUI_Apparence  # noqa: E402
from Utils import UTILS_Interface  # noqa: E402

NOETHYS_SOURCE_PATH = Path(NOETHYS_DIR) / "Noethys.py"


def _est_clair(couleur):
    return couleur.Red() > 200 and couleur.Green() > 200 and couleur.Blue() > 200


def _est_lisible_sur_fond_clair(couleur):
    return couleur.Red() < 100 and couleur.Green() < 100 and couleur.Blue() < 100


class NoethysSLDockArtTests(unittest.TestCase):
    """Art provider dédié au AuiManager principal : dérive de la classe
    publique AuiDefaultDockArt, jamais de ModernDockArt."""

    def setUp(self):
        self.frame = wx.Frame(None)
        self.addCleanup(self.frame.Destroy)

    def test_derive_de_auidefaultdockart_et_jamais_de_moderndockart(self):
        art = UTILS_AUI_Apparence.NoethysSLDockArt()
        self.assertIsInstance(art, aui.AuiDefaultDockArt)
        self.assertNotIsInstance(art, aui.ModernDockArt)

    def test_aucun_chemin_winxptheme_residuel(self):
        """ModernDockArt.DrawCaptionBackground() peut dessiner la légende
        via winxptheme.DrawThemeBackground() si l'attribut usingTheme est
        vrai. En dérivant de AuiDefaultDockArt (qui ne connaît pas cet
        attribut ni cette méthode), ce chemin est éliminé structurellement,
        pas neutralisé après coup."""
        art = UTILS_AUI_Apparence.NoethysSLDockArt()
        self.assertFalse(hasattr(art, "usingTheme"))
        # Le rendu de légende utilisé est bien celui, non thématisé, de la
        # classe de base — jamais celui, potentiellement piloté par
        # winxptheme, de ModernDockArt.
        self.assertIs(type(art).DrawCaptionBackground, aui.AuiDefaultDockArt.DrawCaptionBackground)

    def test_dessin_legende_utilise_des_coordonnees_entieres(self):
        """ModernDockArt.DrawCaption() calcule ses coordonnées de texte en
        division réelle (`rect.height/2 - h/2 - diff`, wx/lib/agw/aui/
        dockart.py ~1038-1040) : sous wxPython 4.2.5, dc.DrawText() lève
        TypeError("argument 3 has unexpected type 'float'") — cause
        probable des bandes noires en thème Windows sombre (l'exception
        interrompt framemanager.OnRender avant la fin du rendu).
        AuiDefaultDockArt.DrawCaption() calcule les mêmes coordonnées en
        division entière (`//`) : en dérivant de cette classe et jamais de
        ModernDockArt, ce chemin d'erreur est éliminé structurellement.
        Ce test échouerait si Noethys revenait un jour à ModernDockArt."""
        art = UTILS_AUI_Apparence.NoethysSLDockArt()
        self.assertIs(type(art).DrawCaption, aui.AuiDefaultDockArt.DrawCaption)
        self.assertIsNot(type(art).DrawCaption, aui.ModernDockArt.DrawCaption)

    def test_palette_claire_des_la_construction(self):
        art = UTILS_AUI_Apparence.NoethysSLDockArt()
        for id_couleur in (
            aui.AUI_DOCKART_BACKGROUND_COLOUR,
            aui.AUI_DOCKART_ACTIVE_CAPTION_COLOUR,
            aui.AUI_DOCKART_ACTIVE_CAPTION_GRADIENT_COLOUR,
            aui.AUI_DOCKART_INACTIVE_CAPTION_COLOUR,
        ):
            couleur = art.GetColor(id_couleur)
            self.assertTrue(_est_clair(couleur), "id=%s couleur=%s" % (id_couleur, couleur))
        for id_couleur in (
            aui.AUI_DOCKART_ACTIVE_CAPTION_TEXT_COLOUR,
            aui.AUI_DOCKART_INACTIVE_CAPTION_TEXT_COLOUR,
        ):
            couleur = art.GetColor(id_couleur)
            self.assertTrue(_est_lisible_sur_fond_clair(couleur), "id=%s couleur=%s" % (id_couleur, couleur))

    def test_rappel_direct_de_init_conserve_la_palette_claire(self):
        """Un rappel direct de Init() (ce que fait AuiManager.
        OnSysColourChanged()) doit reconverger vers la palette claire, pas
        seulement le premier appel effectué à la construction."""
        art = UTILS_AUI_Apparence.NoethysSLDockArt()
        art.Init()
        for id_couleur in (
            aui.AUI_DOCKART_BACKGROUND_COLOUR,
            aui.AUI_DOCKART_ACTIVE_CAPTION_COLOUR,
            aui.AUI_DOCKART_ACTIVE_CAPTION_GRADIENT_COLOUR,
        ):
            couleur = art.GetColor(id_couleur)
            self.assertTrue(_est_clair(couleur), "id=%s couleur=%s" % (id_couleur, couleur))

    def test_changement_systeme_reel_via_onsyscolourchanged_ne_reintroduit_pas_de_sombre(self):
        """Reproduit le mécanisme réel identifié dans wx.lib.agw.aui.
        framemanager.AuiManager : OnSysColourChanged() est lié à
        wx.EVT_SYS_COLOUR_CHANGED et rappelle art.Init() sans jamais
        repasser par le code applicatif. On déclenche ici le vrai
        gestionnaire d'événement de l'AuiManager, pas une simulation."""
        mgr = aui.AuiManager()
        mgr.SetArtProvider(UTILS_AUI_Apparence.NoethysSLDockArt())
        mgr.SetManagedWindow(self.frame)
        self.addCleanup(mgr.UnInit)

        mgr.OnSysColourChanged(wx.SysColourChangedEvent())

        art = mgr.GetArtProvider()
        for id_couleur in (
            aui.AUI_DOCKART_BACKGROUND_COLOUR,
            aui.AUI_DOCKART_ACTIVE_CAPTION_COLOUR,
            aui.AUI_DOCKART_ACTIVE_CAPTION_GRADIENT_COLOUR,
        ):
            couleur = art.GetColor(id_couleur)
            self.assertTrue(_est_clair(couleur), "id=%s couleur=%s" % (id_couleur, couleur))


class NoethysSLToolBarArtTests(unittest.TestCase):
    """Art provider dédié aux AuiToolBar, distinct de celui du AuiManager."""

    def setUp(self):
        self.frame = wx.Frame(None)
        self.addCleanup(self.frame.Destroy)

    def test_derive_de_auidefaulttoolbarart(self):
        art = UTILS_AUI_Apparence.NoethysSLToolBarArt()
        self.assertIsInstance(art, aui.AuiDefaultToolBarArt)

    def test_palette_claire_des_la_construction(self):
        art = UTILS_AUI_Apparence.NoethysSLToolBarArt()
        self.assertTrue(_est_clair(art._base_colour))

    def test_reappel_setdefaultcolours_sans_argument_reste_clair(self):
        """Le point d'entrée public SetDefaultColours() doit rester
        verrouillé sur la palette claire même si du code le rappelle plus
        tard sans préciser de couleur (comportement par défaut de
        AuiDefaultToolBarArt : base_colour=None -> couleur système)."""
        art = UTILS_AUI_Apparence.NoethysSLToolBarArt()
        art.SetDefaultColours()
        self.assertTrue(_est_clair(art._base_colour))
        art.SetDefaultColours(base_colour=wx.Colour(10, 10, 10))
        self.assertTrue(_est_clair(art._base_colour))

    def test_toolbar_reelle_utilise_lart_provider_noethys_sl(self):
        tb = aui.AuiToolBar(self.frame, -1)
        self.addCleanup(tb.Destroy)

        tb.SetArtProvider(UTILS_AUI_Apparence.NoethysSLToolBarArt())

        self.assertIsInstance(tb.GetArtProvider(), UTILS_AUI_Apparence.NoethysSLToolBarArt)
        self.assertTrue(_est_clair(tb.GetArtProvider()._base_colour))


class NoethysCablageAUITests(unittest.TestCase):
    """Vérifie, au niveau du code source de Noethys.py, que le câblage
    utilise bien les art providers Noethys SL et plus aucun mécanisme de
    contournement (monkey-patch, attribut privé usingTheme). Déterministe,
    sans dépendre d'une session graphique réelle ni d'un vrai poste Linux."""

    def setUp(self):
        self.source = NOETHYS_SOURCE_PATH.read_text(encoding="utf-8")

    def test_aucune_trace_de_moderndockart_ni_du_hack_precedent(self):
        for motif_interdit in ("ModernDockArt", "ForceApparenceClaireAUI", "usingTheme", ".Init ="):
            self.assertNotIn(motif_interdit, self.source, "motif résiduel interdit : %s" % motif_interdit)

    def test_le_aui_manager_principal_utilise_noethysSLDockArt(self):
        self.assertIn("self._mgr.SetArtProvider(UTILS_AUI_Apparence.NoethysSLDockArt())", self.source)

    def test_les_trois_barres_outils_utilisent_noethysSLToolBarArt_hors_linux(self):
        motif = "tb.SetArtProvider(UTILS_AUI_Apparence.NoethysSLToolBarArt())"
        occurrences = []
        depart = 0
        while True:
            position = self.source.find(motif, depart)
            if position == -1:
                break
            occurrences.append(position)
            depart = position + 1

        self.assertEqual(len(occurrences), 3, "les 3 sites de création d'AuiToolBar doivent utiliser NoethysSLToolBarArt")
        for position in occurrences:
            bloc_precedent = self.source[max(0, position - 200):position]
            self.assertIn('"linux" not in sys.platform', bloc_precedent)

    def test_le_module_apparence_est_importe(self):
        self.assertIn("from Utils import UTILS_AUI_Apparence", self.source)


class ThemeNoethysSLTests(unittest.TestCase):
    def test_ancien_theme_noir_est_normalise_vers_vert(self):
        with mock.patch.object(
            UTILS_Interface.UTILS_Customize,
            "GetValeur",
            return_value="Noir",
        ):
            self.assertEqual(UTILS_Interface.GetTheme(), "Vert")

    def test_les_accents_clairs_restent_disponibles(self):
        self.assertEqual(UTILS_Interface._NormaliseThemeNoethysSL("Vert"), "Vert")
        self.assertEqual(UTILS_Interface._NormaliseThemeNoethysSL("Bleu"), "Bleu")


if __name__ == "__main__":
    unittest.main()
