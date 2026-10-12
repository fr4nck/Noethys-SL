"""Composition finale de la fiche Activité Qt actuellement migrée."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from .activity_agreements import ActivityEditorDialog as AgreementsActivityEditorDialog
from .activity_editor import NativeActivityEditorRepository
from .activity_labels import ActivityLabelsPage


class ActivityEditorDialog(AgreementsActivityEditorDialog):
    """Éditeur Activité avec la page Étiquettes raccordée au rail complet."""

    def __init__(
        self,
        repository: NativeActivityEditorRepository,
        activity_id: int,
        parent: QWidget | None = None,
    ):
        super().__init__(repository, activity_id, parent)
        old_page = self.tabs.widget(4)
        self.tabs.removeTab(4)
        if old_page is not None:
            old_page.deleteLater()
        self.labels_page = ActivityLabelsPage(repository, activity_id, self)
        self.tabs.insertTab(4, self.labels_page, "Étiquettes")
