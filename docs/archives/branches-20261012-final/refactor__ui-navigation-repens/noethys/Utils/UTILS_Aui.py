# -*- coding: utf-8 -*-
"""Helpers explicites pour wxAUI et les composants du shell Noethys.

Repens peut styliser le shell, ses toolbars, notebooks et grilles, mais il ne
pilote pas la géométrie des panes. Le docking, les sash, le flottement et les
perspectives restent sous la responsabilité native de wxAUI. Cette séparation
évite qu'un recalcul responsive ne lutte contre un déplacement utilisateur.
"""

PERSPECTIVE_LAYOUT_VERSION = 7
PARAMETRE_PERSPECTIVE_VERSION = "aui_perspective_layout_version"

# Registre documentaire des modules susceptibles de partager la zone de travail.
# Il ne sert volontairement plus à réécrire leur position ou leur taille.
WORKSPACE_PANES = (
    {"nom": "recherche", "caption": u"Individus / Familles", "poids": 1.00, "minimum": 300},
    {"nom": "messagerie", "caption": u"Messagerie", "poids": 0.72, "minimum": 300},
    {"nom": "semaine_equipe", "caption": u"Semaine équipe", "poids": 0.62, "minimum": 300},
    {"nom": "sms", "caption": u"SMS", "poids": 0.48, "minimum": 280},
)


def VerifierVersionPerspective(manager):
    """Invalide proprement une ancienne génération de disposition AUI."""
    if manager is None:
        return False
    try:
        from Utils import UTILS_Config
        version = int(UTILS_Config.GetParametre(PARAMETRE_PERSPECTIVE_VERSION, 0) or 0)
    except Exception:
        version = 0

    if version == PERSPECTIVE_LAYOUT_VERSION:
        return True

    try:
        fenetre = manager.GetManagedWindow()
    except Exception:
        fenetre = None

    if fenetre is not None:
        try:
            fenetre.perspectives = []
            fenetre.perspective_active = None
        except Exception:
            pass

    try:
        UTILS_Config.SetParametre(PARAMETRE_PERSPECTIVE_VERSION, PERSPECTIVE_LAYOUT_VERSION)
    except Exception:
        pass
    return False


def ChargerBitmapToolBar(image, taille_base=24):
    """Charge un pictogramme à la taille réellement utilisée par une toolbar."""
    try:
        import wx
        import Chemins
        from Utils import UTILS_Responsive

        taille = UTILS_Responsive.GetTailleIcone(taille_base)
        chemin = Chemins.GetStaticIconPath(image, taille=taille)
        bitmap = wx.Bitmap(chemin, wx.BITMAP_TYPE_ANY)
        if bitmap.IsOk() and (bitmap.GetWidth() != taille or bitmap.GetHeight() != taille):
            source = bitmap.ConvertToImage()
            source = source.Scale(taille, taille, wx.IMAGE_QUALITY_HIGH)
            bitmap = wx.Bitmap(source)
        return bitmap
    except Exception:
        try:
            return wx.NullBitmap
        except Exception:
            return None


def _TailleBitmapExistante(toolbar, defaut=16):
    try:
        taille = toolbar.GetToolBitmapSize()
        largeur = int(taille.GetWidth()) if hasattr(taille, "GetWidth") else int(taille[0])
        if largeur > 0:
            return largeur
    except Exception:
        pass
    return defaut


def _ToolbarAvecLibelle(toolbar):
    try:
        import wx
        import wx.lib.agw.aui as aui
        if isinstance(toolbar, aui.AuiToolBar):
            return bool(toolbar.GetAGWWindowStyleFlag() & aui.AUI_TB_TEXT)
        return bool(toolbar.GetWindowStyleFlag() & wx.TB_TEXT)
    except Exception:
        return True


def _ItererDescendants(window):
    if window is None:
        return
    yield window
    try:
        enfants = window.GetChildren()
    except Exception:
        enfants = []
    for enfant in enfants:
        for descendant in _ItererDescendants(enfant):
            yield descendant


def ConfigurerGrille(grille):
    """Applique la grammaire visuelle commune à une wx.Grid existante."""
    if grille is None:
        return False
    try:
        import wx.grid as gridlib
        from Utils import UTILS_Interface
        from Utils import UTILS_UIMetrics
        if not isinstance(grille, gridlib.Grid):
            return False
    except Exception:
        return False

    try:
        grille.EnableGridLines(True)
        grille.SetGridLineColour(UTILS_Interface.GetCouleurRole("outline_variant"))
    except Exception:
        pass
    try:
        grille.SetLabelBackgroundColour(UTILS_Interface.GetCouleurRole("surface_container_high"))
        grille.SetLabelTextColour(UTILS_Interface.GetCouleurRole("on_surface"))
    except Exception:
        pass
    try:
        grille.SetDefaultCellBackgroundColour(UTILS_Interface.GetCouleurRole("surface_container_lowest"))
        grille.SetDefaultCellTextColour(UTILS_Interface.GetCouleurRole("on_surface"))
    except Exception:
        pass

    try:
        if not hasattr(grille, "_noethys_default_row_base"):
            grille._noethys_default_row_base = grille.GetDefaultRowSize()
        grille.SetDefaultRowSize(
            max(UTILS_UIMetrics.row_height("table"), UTILS_UIMetrics.px(grille._noethys_default_row_base)),
            True,
        )
    except Exception:
        pass

    for getter, setter, attribut in (
        ("GetRowLabelSize", "SetRowLabelSize", "_noethys_row_label_base"),
        ("GetColLabelSize", "SetColLabelSize", "_noethys_col_label_base"),
    ):
        try:
            if not hasattr(grille, attribut):
                setattr(grille, attribut, getattr(grille, getter)())
            getattr(grille, setter)(UTILS_UIMetrics.px(getattr(grille, attribut)))
        except Exception:
            pass

    try:
        grille.ForceRefresh()
    except Exception:
        try:
            grille.Refresh()
        except Exception:
            pass
    return True


def _TypesNavigationStandard(wx):
    """Retourne les contrôles book disponibles dans la version courante de wxPython."""
    types_navigation = []
    for nom in ("Notebook", "Choicebook", "Listbook", "Treebook", "Simplebook"):
        classe = getattr(wx, nom, None)
        if isinstance(classe, type):
            types_navigation.append(classe)
    return tuple(types_navigation)


def _StyliserControleNavigation(controle, UTILS_Interface):
    """Style un sélecteur interne de book sans modifier sa géométrie native."""
    if controle is None:
        return
    try:
        controle.SetBackgroundColour(UTILS_Interface.GetCouleurRole("surface_container_low"))
        controle.SetForegroundColour(UTILS_Interface.GetCouleurRole("on_surface"))
        controle.Refresh()
    except Exception:
        pass


def ConfigurerNavigation(book):
    """Applique Repens aux notebooks/listbooks/choicebooks sans redessiner leurs onglets."""
    if book is None:
        return False
    try:
        import wx
        import wx.lib.agw.aui as aui
        from Utils import UTILS_UIMetrics
        from Utils import UTILS_Interface
    except Exception:
        return False

    types_standard = _TypesNavigationStandard(wx)
    est_aui = isinstance(book, aui.AuiNotebook)
    if not est_aui and (not types_standard or not isinstance(book, types_standard)):
        return False

    try:
        book.SetBackgroundColour(UTILS_Interface.GetCouleurRole("surface"))
        book.SetForegroundColour(UTILS_Interface.GetCouleurRole("on_surface"))
    except Exception:
        pass

    # AUI expose explicitement la hauteur de sa barre d'onglets. Les books
    # natifs conservent volontairement leur métrique plateforme et leur focus.
    if est_aui:
        try:
            book.SetTabCtrlHeight(UTILS_UIMetrics.px(32))
        except Exception:
            pass

    # Listbook/Choicebook/Treebook fournissent selon la version de wxPython un
    # contrôle de navigation interne. On le thématise sans remplacer son rendu.
    for getter in ("GetListView", "GetChoiceCtrl", "GetTreeCtrl"):
        try:
            controle = getattr(book, getter)()
        except Exception:
            controle = None
        _StyliserControleNavigation(controle, UTILS_Interface)

    # Les pages reçoivent uniquement les rôles de surface/texte. Leur layout,
    # leurs tailles et leur logique métier restent intégralement inchangés.
    try:
        nombre_pages = book.GetPageCount()
    except Exception:
        nombre_pages = 0
    for index in range(nombre_pages):
        try:
            page = book.GetPage(index)
            page.SetBackgroundColour(UTILS_Interface.GetCouleurRole("surface"))
            page.SetForegroundColour(UTILS_Interface.GetCouleurRole("on_surface"))
        except Exception:
            pass

    try:
        book.Refresh()
    except Exception:
        pass
    return True


def ConfigurerNotebook(notebook):
    """Compatibilité historique : configure désormais toute navigation de type book."""
    return ConfigurerNavigation(notebook)


def _ConfigurerComposantsDuManager(manager):
    """Configure les composants communs sans modifier la géométrie des panes."""
    try:
        import wx
        import wx.grid as gridlib
        import wx.lib.agw.aui as aui
        panes = manager.GetAllPanes()
    except Exception:
        return

    types_navigation = _TypesNavigationStandard(wx)
    deja_vues = set()
    for pane in panes:
        racine = getattr(pane, "window", None)
        for fenetre in _ItererDescendants(racine):
            if id(fenetre) in deja_vues:
                continue
            deja_vues.add(id(fenetre))

            if isinstance(fenetre, (wx.ToolBar, aui.AuiToolBar)):
                taille_base = getattr(fenetre, "_noethys_toolbar_icon_base", None)
                if taille_base is None:
                    taille_base = _TailleBitmapExistante(fenetre, defaut=16)
                ConfigurerToolBar(fenetre, taille_base=taille_base, fond_uni=True)
                continue
            if isinstance(fenetre, aui.AuiNotebook) or (types_navigation and isinstance(fenetre, types_navigation)):
                ConfigurerNavigation(fenetre)
                continue
            if isinstance(fenetre, gridlib.Grid):
                ConfigurerGrille(fenetre)


def _ConfigurerPoliceCaptions(art):
    try:
        import wx
        import wx.lib.agw.aui as aui
        from Utils import UTILS_Interface

        police = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        base = max(7, police.GetPointSize())
        facteur = (UTILS_Interface.GetEchelle() / 100.0) * (UTILS_Interface.GetTailleTexte() / 100.0)
        police.SetPointSize(max(7, int(round(base * facteur))))
        try:
            police.SetWeight(wx.FONTWEIGHT_SEMIBOLD)
        except Exception:
            police.SetWeight(wx.FONTWEIGHT_BOLD)
        art.SetFont(aui.AUI_DOCKART_CAPTION_FONT, police)
    except Exception:
        pass


def _SetArtColour(art, aui, constante, role):
    identifiant = getattr(aui, constante, None)
    if identifiant is None:
        return
    try:
        from Utils import UTILS_Interface
        couleur = UTILS_Interface.GetCouleurRole(role)
    except Exception:
        return
    try:
        art.SetColour(identifiant, couleur)
    except Exception:
        try:
            art.SetColor(identifiant, couleur)
        except Exception:
            pass


def _SetArtMetric(art, aui, constante, valeur):
    identifiant = getattr(aui, constante, None)
    if identifiant is None:
        return
    try:
        art.SetMetric(identifiant, int(valeur))
    except Exception:
        pass


def _ConfigurerArtShell(art, aui):
    """Palette AUI plate et dense, sans intervenir sur la géométrie."""
    try:
        from Utils import UTILS_UIMetrics
        caption = UTILS_UIMetrics.px(30)
    except Exception:
        caption = 30

    _SetArtMetric(art, aui, "AUI_DOCKART_CAPTION_SIZE", caption)
    _SetArtMetric(art, aui, "AUI_DOCKART_PANE_BORDER_SIZE", 1)
    try:
        from Utils import UTILS_Responsive
        sash = max(5, min(10, int(round(5 * max(1.0, UTILS_Responsive.GetFacteurEcran())))))
        _SetArtMetric(art, aui, "AUI_DOCKART_SASH_SIZE", sash)
    except Exception:
        pass

    for constante, role in (
        ("AUI_DOCKART_BACKGROUND_COLOUR", "surface"),
        ("AUI_DOCKART_SASH_COLOUR", "outline_variant"),
        ("AUI_DOCKART_BORDER_COLOUR", "outline_variant"),
        ("AUI_DOCKART_GRIPPER_COLOUR", "outline_variant"),
        ("AUI_DOCKART_INACTIVE_CAPTION_COLOUR", "surface_container"),
        ("AUI_DOCKART_INACTIVE_CAPTION_GRADIENT_COLOUR", "surface_container"),
        ("AUI_DOCKART_INACTIVE_CAPTION_TEXT_COLOUR", "on_surface_variant"),
        ("AUI_DOCKART_ACTIVE_CAPTION_COLOUR", "surface_container_high"),
        ("AUI_DOCKART_ACTIVE_CAPTION_GRADIENT_COLOUR", "surface_container_high"),
        ("AUI_DOCKART_ACTIVE_CAPTION_TEXT_COLOUR", "on_surface"),
    ):
        _SetArtColour(art, aui, constante, role)


def _GetPane(manager, nom):
    try:
        pane = manager.GetPane(nom)
        if pane is not None and pane.IsOk():
            return pane
    except Exception:
        pass
    return None


def _AppelerPane(pane, nom, *args):
    if pane is None:
        return
    try:
        getattr(pane, nom)(*args)
    except Exception:
        pass


def _ConfigurerBarresSysteme(manager):
    """Fige uniquement les deux barres structurelles du shell."""
    for nom, position in (("barre_raccourcis", 0), ("barre_utilisateur", 1)):
        pane = _GetPane(manager, nom)
        if pane is None:
            continue
        for methode, args in (
            ("Top", ()),
            ("Layer", (0,)),
            ("Row", (0,)),
            ("Position", (position,)),
            ("ToolbarPane", ()),
            ("Gripper", (False,)),
            ("Floatable", (False,)),
            ("DockFixed", (True,)),
            ("CloseButton", (False,)),
            ("MaximizeButton", (False,)),
            ("MinimizeButton", (False,)),
        ):
            _AppelerPane(pane, methode, *args)


def ReequilibrerWorkspace(manager):
    """Rafraîchit AUI sans déplacer ni redimensionner les panes utilisateur."""
    if manager is None:
        return False
    try:
        manager.Update()
        fenetre = manager.GetManagedWindow()
        if fenetre is not None:
            fenetre.Layout()
        return True
    except Exception:
        return False


def ConfigurerManager(manager):
    """Applique le langage visuel Repens au manager, sans piloter son layout."""
    if manager is None:
        return False
    try:
        import wx.lib.agw.aui as aui
        art = manager.GetArtProvider()
    except Exception:
        return False

    _ConfigurerPoliceCaptions(art)
    _ConfigurerArtShell(art, aui)
    _ConfigurerComposantsDuManager(manager)
    _ConfigurerBarresSysteme(manager)

    try:
        manager.Update()
        fenetre = manager.GetManagedWindow()
        if fenetre is not None:
            from Utils import UTILS_Interface
            fenetre.SetBackgroundColour(UTILS_Interface.GetCouleurRole("surface"))
            fenetre.Layout()
    except Exception:
        pass
    return True


def ConfigurerToolBar(toolbar, taille_base=16, fond_uni=True):
    """Configure une toolbar selon icônes, texte, DPI et échelle utilisateur."""
    if toolbar is None:
        return False
    try:
        import wx
        import wx.lib.agw.aui as aui
        from Utils import UTILS_Interface
        from Utils import UTILS_Responsive
        from Utils import UTILS_UIMetrics
    except Exception:
        return False

    try:
        taille_base = int(taille_base)
    except Exception:
        taille_base = 16
    toolbar._noethys_toolbar_icon_base = taille_base
    taille = UTILS_Responsive.GetTailleIcone(taille_base)

    try:
        toolbar.SetToolBitmapSize(wx.Size(taille, taille))
    except Exception:
        try:
            toolbar.SetToolBitmapSize((taille, taille))
        except Exception:
            pass

    if fond_uni and isinstance(toolbar, aui.AuiToolBar):
        try:
            style = toolbar.GetAGWWindowStyleFlag()
            style |= getattr(aui, "AUI_TB_PLAIN_BACKGROUND", 0)
            toolbar.SetAGWWindowStyleFlag(style)
        except Exception:
            pass

    try:
        toolbar.SetBackgroundColour(UTILS_Interface.GetCouleurRole("surface_container_low"))
        toolbar.SetForegroundColour(UTILS_Interface.GetCouleurRole("on_surface"))
    except Exception:
        pass

    marge = UTILS_UIMetrics.spacing(1)
    for nom, args in (
        ("SetToolPacking", (marge,)),
        ("SetToolSeparation", (marge,)),
    ):
        try:
            getattr(toolbar, nom)(*args)
        except Exception:
            pass
    try:
        toolbar.SetMargins(marge, marge)
    except Exception:
        try:
            toolbar.SetMargins(marge, marge, marge, marge)
        except Exception:
            pass

    try:
        toolbar.Realize()
    except Exception:
        pass

    avec_libelle = _ToolbarAvecLibelle(toolbar)
    hauteur = UTILS_UIMetrics.toolbar_height(avec_libelle=avec_libelle, icon_px=taille)
    try:
        hauteur = max(hauteur, int(toolbar.GetBestSize().GetHeight()))
    except Exception:
        pass
    try:
        hauteur = max(hauteur, int(toolbar.GetMinSize().GetHeight()))
    except Exception:
        pass

    try:
        toolbar.SetMinSize((-1, hauteur))
        toolbar._noethys_toolbar_min_height = hauteur
        toolbar.InvalidateBestSize()
    except Exception:
        pass

    try:
        parent = toolbar.GetParent()
        if parent is not None:
            parent.Layout()
    except Exception:
        pass
    return True


def ChargerPerspective(manager, perspective, fallback=None):
    """Charge une perspective AUI sans la réécrire après son chargement."""
    if manager is None:
        return False

    version_valide = VerifierVersionPerspective(manager)
    sources = (perspective, fallback) if version_valide else (fallback,)

    candidates = []
    for candidate in sources:
        if isinstance(candidate, str) and candidate.strip() and candidate not in candidates:
            candidates.append(candidate)

    for candidate in candidates:
        try:
            result = manager.LoadPerspective(candidate)
        except (AssertionError, TypeError, ValueError, RuntimeError):
            result = False
        if result is not False:
            ConfigurerManager(manager)
            return result

    ConfigurerManager(manager)
    return False