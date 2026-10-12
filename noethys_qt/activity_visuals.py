"""Grammaire visuelle minimale du POC Qt Activités.

Ce module reste volontairement petit : il ne constitue pas un moteur de thème
Noethys. Il applique au premier écran réel des rôles sémantiques éprouvables,
une densité desktop et des états interactifs cohérents avec la direction
PMSL-Arch. Si le POC est validé, ces rôles pourront ensuite être extraits vers
des composants communs au rythme des écrans réellement migrés.
"""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QKeySequence, QPalette
from PySide6.QtWidgets import QApplication, QMainWindow, QStyle, QToolBar


LIGHT_TOKENS: dict[str, str] = {
    "surface": "#F5F6F7",
    "surface_container_lowest": "#FFFFFF",
    "surface_container_low": "#F7F8F9",
    "surface_container": "#EEF0F2",
    "surface_container_high": "#E8EAED",
    "surface_container_highest": "#DEE2E6",
    "on_surface": "#1D2329",
    "on_surface_variant": "#56616B",
    "primary": "#0F6CBD",
    "on_primary": "#FFFFFF",
    "outline": "#8A949E",
    "outline_variant": "#D4D9DE",
    "selection": "#CFE8FC",
    "selection_text": "#102A43",
    "disabled": "#8A949E",
    "focus": "#0F6CBD",
}

DARK_TOKENS: dict[str, str] = {
    "surface": "#1B1C1E",
    "surface_container_lowest": "#202224",
    "surface_container_low": "#252729",
    "surface_container": "#2B2D30",
    "surface_container_high": "#313438",
    "surface_container_highest": "#393C40",
    "on_surface": "#E7E9EB",
    "on_surface_variant": "#BDC3C9",
    "primary": "#78B3ED",
    "on_primary": "#0D2438",
    "outline": "#68717A",
    "outline_variant": "#41464B",
    "selection": "#315E7E",
    "selection_text": "#F5F9FC",
    "disabled": "#7C848C",
    "focus": "#78B3ED",
}


def _resolved_theme(requested: str) -> str:
    if requested in {"light", "dark"}:
        return requested

    app = QApplication.instance()
    if app is None:
        return "light"

    hints = app.styleHints()
    getter = getattr(hints, "colorScheme", None)
    if callable(getter):
        scheme = getter()
        if scheme == Qt.ColorScheme.Dark:
            return "dark"
        if scheme == Qt.ColorScheme.Light:
            return "light"

    window_color = app.palette().color(QPalette.ColorRole.Window)
    return "dark" if window_color.lightness() < 128 else "light"


def _tokens(requested: str) -> Mapping[str, str]:
    return DARK_TOKENS if _resolved_theme(requested) == "dark" else LIGHT_TOKENS


def _palette(tokens: Mapping[str, str]) -> QPalette:
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: "surface",
        QPalette.ColorRole.WindowText: "on_surface",
        QPalette.ColorRole.Base: "surface_container_lowest",
        QPalette.ColorRole.AlternateBase: "surface_container_low",
        QPalette.ColorRole.ToolTipBase: "surface_container_highest",
        QPalette.ColorRole.ToolTipText: "on_surface",
        QPalette.ColorRole.Text: "on_surface",
        QPalette.ColorRole.Button: "surface_container",
        QPalette.ColorRole.ButtonText: "on_surface",
        QPalette.ColorRole.Highlight: "selection",
        QPalette.ColorRole.HighlightedText: "selection_text",
        QPalette.ColorRole.PlaceholderText: "on_surface_variant",
        QPalette.ColorRole.Link: "primary",
        QPalette.ColorRole.LinkVisited: "primary",
    }
    for role, token in roles.items():
        palette.setColor(role, QColor(tokens[token]))

    disabled = QColor(tokens["disabled"])
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.PlaceholderText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    return palette


def _stylesheet(tokens: Mapping[str, str]) -> str:
    return f"""
QMainWindow {{
    background: {tokens['surface']};
    color: {tokens['on_surface']};
}}
QToolBar {{
    background: {tokens['surface_container_high']};
    border: none;
    border-bottom: 1px solid {tokens['outline_variant']};
    spacing: 4px;
    padding: 4px 6px;
}}
QToolBar::separator {{
    background: {tokens['outline_variant']};
    width: 1px;
    margin: 5px 6px;
}}
QToolButton {{
    color: {tokens['on_surface']};
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 7px;
}}
QToolButton:hover {{
    background: {tokens['surface_container_highest']};
}}
QToolButton:pressed {{
    background: {tokens['surface_container']};
    border-color: {tokens['outline']};
}}
QToolButton:focus {{
    border-color: {tokens['focus']};
}}
QToolButton:disabled {{
    color: {tokens['disabled']};
}}
QComboBox {{
    color: {tokens['on_surface']};
    background: {tokens['surface_container']};
    border: 1px solid {tokens['outline_variant']};
    border-radius: 4px;
    padding: 3px 8px;
}}
QComboBox:hover {{
    border-color: {tokens['outline']};
}}
QComboBox:focus {{
    border-color: {tokens['focus']};
}}
QComboBox QAbstractItemView {{
    color: {tokens['on_surface']};
    background: {tokens['surface_container_high']};
    border: 1px solid {tokens['outline_variant']};
    selection-background-color: {tokens['selection']};
    selection-color: {tokens['selection_text']};
}}
QCheckBox {{
    color: {tokens['on_surface']};
    spacing: 6px;
}}
QCheckBox:focus {{
    color: {tokens['on_surface']};
}}
QTableView {{
    color: {tokens['on_surface']};
    background: {tokens['surface_container_lowest']};
    alternate-background-color: {tokens['surface_container_low']};
    border: none;
    selection-background-color: {tokens['selection']};
    selection-color: {tokens['selection_text']};
    outline: 0;
}}
QTableView::item {{
    border: none;
    padding: 3px 6px;
}}
QTableView::item:hover:!selected {{
    background: {tokens['surface_container']};
}}
QTableView::item:selected {{
    background: {tokens['selection']};
    color: {tokens['selection_text']};
}}
QTableView::item:focus {{
    border: 1px solid {tokens['focus']};
}}
QHeaderView {{
    background: {tokens['surface_container_high']};
}}
QHeaderView::section {{
    color: {tokens['on_surface']};
    background: {tokens['surface_container_high']};
    border: none;
    border-right: 1px solid {tokens['outline_variant']};
    border-bottom: 1px solid {tokens['outline_variant']};
    padding: 5px 6px;
    font-weight: 600;
}}
QHeaderView::section:hover {{
    background: {tokens['surface_container_highest']};
}}
QStatusBar {{
    color: {tokens['on_surface_variant']};
    background: {tokens['surface_container_high']};
    border-top: 1px solid {tokens['outline_variant']};
}}
QMenu {{
    color: {tokens['on_surface']};
    background: {tokens['surface_container_high']};
    border: 1px solid {tokens['outline_variant']};
    padding: 4px;
}}
QMenu::item {{
    border-radius: 3px;
    padding: 5px 22px 5px 8px;
}}
QMenu::item:selected {{
    color: {tokens['selection_text']};
    background: {tokens['selection']};
}}
QMenu::item:disabled {{
    color: {tokens['disabled']};
}}
QToolTip {{
    color: {tokens['on_surface']};
    background: {tokens['surface_container_highest']};
    border: 1px solid {tokens['outline']};
    padding: 3px 5px;
}}
"""


def apply_semantic_theme(window: QMainWindow) -> None:
    """Applique la palette au thème actuellement sélectionné par la fenêtre."""
    app = QApplication.instance()
    if app is None:
        return
    theme_combo = getattr(window, "theme_combo", None)
    requested = str(theme_combo.currentData()) if theme_combo is not None else "system"
    tokens = _tokens(requested)
    app.setPalette(_palette(tokens))
    app.setStyleSheet(_stylesheet(tokens))


def apply_activity_visuals(window: QMainWindow) -> None:
    """Modernise seulement la présentation du POC, sans toucher au métier."""
    table = getattr(window, "table")
    table.setShowGrid(False)
    table.setTextElideMode(Qt.TextElideMode.ElideRight)
    table.setTabKeyNavigation(True)
    table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    header = table.horizontalHeader()
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    header.setSectionsClickable(True)

    metrics = table.fontMetrics()
    table.verticalHeader().setDefaultSectionSize(metrics.height() + 12)

    toolbar = window.findChild(QToolBar)
    if toolbar is not None:
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)

    style = window.style()
    refresh_action = getattr(window, "refresh_action")
    export_text_action = getattr(window, "export_text_action")
    export_excel_action = getattr(window, "export_excel_action")

    refresh_action.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
    refresh_action.setShortcut(QKeySequence.Refresh)
    refresh_action.setToolTip("Actualiser la liste (F5)")

    export_text_action.setText("Exporter texte")
    export_text_action.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileIcon))
    export_text_action.setShortcut(QKeySequence("Ctrl+Shift+T"))
    export_text_action.setToolTip("Exporter la liste visible au format texte")

    export_excel_action.setText("Exporter Excel")
    export_excel_action.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
    export_excel_action.setShortcut(QKeySequence("Ctrl+Shift+E"))
    export_excel_action.setToolTip("Exporter la liste visible au format Excel")

    theme_combo = getattr(window, "theme_combo", None)
    if theme_combo is not None:
        labels = ("Système", "Clair", "Sombre")
        for index, label in enumerate(labels):
            if index < theme_combo.count():
                theme_combo.setItemText(index, label)
        theme_combo.setAccessibleName("Thème de l'interface")
        theme_combo.setToolTip("Utiliser le thème système, clair ou sombre")

        if not bool(window.property("pmslVisualThemeConnected")):
            theme_combo.currentIndexChanged.connect(lambda _index: apply_semantic_theme(window))
            window.setProperty("pmslVisualThemeConnected", True)

    open_only = getattr(window, "open_only", None)
    if open_only is not None:
        open_only.setToolTip("Limiter la liste aux activités dont la date de fin n'est pas passée")

    apply_semantic_theme(window)
