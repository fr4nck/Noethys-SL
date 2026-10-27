"""Calendrier et navigation par activité des consommations Qt (lot C2).

Compose la table bornée du lot C1 et une synthèse mensuelle SQL exacte.
Les événements liés sont affichés comme références, pas comme preuve qu'une
plage sans événement constitue une séance canonique.
"""
from __future__ import annotations

import calendar
import datetime as dt

from PySide6.QtCore import QDate, QObject, QRunnable, QSignalBlocker, QThreadPool, Qt, Signal
from PySide6.QtGui import QFont, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget, QCheckBox, QComboBox, QGroupBox, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget,
)

from .consumptions_calendar_core import (
    ConsumptionCalendarRepository, DayCount,
)
from .consumptions_core import format_date, state_label
from .consumptions_ui import ConsumptionPage
from .consumptions_preparation_ui import ConsumptionPreparationPanel


class _BackgroundSignals(QObject):
    completed = Signal(int, object, str)


class _CalendarWorker(QRunnable):
    """Travail SQL déporté, sans manipulation de widget depuis le thread."""

    def __init__(self, repository, token, method, filters):
        super().__init__()
        self.setAutoDelete(False)
        self.repository = repository
        self.token = token
        self.method = method
        self.filters = filters
        self.signals = _BackgroundSignals()

    def run(self):
        try:
            result = getattr(self.repository, self.method)(**self.filters)
        except Exception as exc:
            self.signals.completed.emit(self.token, None, str(exc))
        else:
            self.signals.completed.emit(self.token, result, "")


class ConsumptionCalendarPage(QWidget):
    """Filtres synchronisés, lecture seule et accès direct au jour choisi."""

    def __init__(self, repository, parent=None, *, background=True):
        super().__init__(parent)
        self.repository = repository
        self.calendar_repository = ConsumptionCalendarRepository(repository)
        self.background = background
        self._loaded = False
        self._calendar_sync = False
        self._month_token = 0
        self._month_queued = None
        self._month_worker = None
        self._activity_worker = None
        self._activity_loaded = False
        self._record_individual_id: int | None = None
        self._record_inscription_id: int | None = None
        self._date_counts: tuple[DayCount, ...] = ()
        self._marked_dates: set[QDate] = set()

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        left = QWidget(self)
        left.setMinimumWidth(225)
        left.setMaximumWidth(295)
        controls = QVBoxLayout(left)
        controls.setContentsMargins(8, 8, 6, 8)
        controls.setSpacing(6)

        heading = QLabel("Calendrier et activité", left)
        heading.setObjectName("sectionTitle")
        controls.addWidget(heading)

        self.activity_combo = QComboBox(left)
        self.activity_combo.setAccessibleName("Filtrer les consommations par activité")
        self.activity_combo.addItem("Toutes les activités", None)
        controls.addWidget(self.activity_combo)

        self.record_filter_label = QLabel("", left)
        self.record_filter_label.setObjectName("recordFilterLabel")
        self.record_filter_label.setWordWrap(True)
        self.record_filter_label.hide()
        controls.addWidget(self.record_filter_label)
        self.clear_record_button = QPushButton("Retirer le filtre de fiche", left)
        self.clear_record_button.hide()
        controls.addWidget(self.clear_record_button)

        self.calendar = QCalendarWidget(left)
        self.calendar.setObjectName("consumptionsCalendar")
        self.calendar.setGridVisible(True)
        self.calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        self.calendar.setNavigationBarVisible(True)
        controls.addWidget(self.calendar)

        self.only_day = QCheckBox("Limiter au jour sélectionné", left)
        self.only_day.setChecked(False)  # Préserver la liste annuelle du lot C1.
        controls.addWidget(self.only_day)
        self.year_button = QPushButton("Afficher toute l'année", left)
        controls.addWidget(self.year_button)

        self.month_summary = QLabel("Le calendrier affichera les journées avec consommations.", left)
        self.month_summary.setWordWrap(True)
        controls.addWidget(self.month_summary)

        self.day_list = QListWidget(left)
        self.day_list.setAccessibleName("Journées du mois ayant des consommations")
        self.day_list.setAlternatingRowColors(True)
        controls.addWidget(self.day_list, 1)

        caution = QLabel(
            "Comptages mensuels exacts selon les filtres. "
            "La liste de droite reste limitée à 300 lignes.",
            left,
        )
        caution.setWordWrap(True)
        controls.addWidget(caution)
        root.addWidget(left)

        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 6, 0)
        right_layout.setSpacing(4)
        self.list_page = ConsumptionPage(repository, right, background=background)
        self.list_page.filter_context = self._extra_filters
        right_layout.addWidget(self.list_page, 1)

        details = QGroupBox("Détail de la consommation / événement lié", right)
        details_layout = QVBoxLayout(details)
        self.details_label = QLabel("Sélectionnez une consommation pour afficher son détail.", details)
        self.details_label.setTextFormat(Qt.TextFormat.PlainText)
        self.details_label.setWordWrap(True)
        details_layout.addWidget(self.details_label)
        right_layout.addWidget(details)
        self.preparation_panel = ConsumptionPreparationPanel(
            repository, right, background=background,
        )
        right_layout.addWidget(self.preparation_panel)
        root.addWidget(right, 1)

        self.clear_record_button.clicked.connect(self.clear_record_context)
        self.activity_combo.currentIndexChanged.connect(self.refresh)
        self.calendar.selectionChanged.connect(self._day_changed)
        self.calendar.currentPageChanged.connect(self._page_changed)
        self.only_day.toggled.connect(self._filter_day_changed)
        self.year_button.clicked.connect(lambda: self.only_day.setChecked(False))
        self.day_list.itemActivated.connect(self._choose_day)
        self.day_list.itemClicked.connect(self._choose_day)
        self.list_page.year_spin.valueChanged.connect(self._year_changed)
        self.list_page.refresh_button.clicked.connect(self.refresh_month)
        self.list_page._debounce.timeout.connect(self.refresh_month)
        # Écouter la modification logique complète des filtres, et non les
        # 7 signaux de cases émis pendant « Tout sélectionner ».
        self.list_page.state_selection_changed.connect(self.refresh_month)
        self.list_page.table.selectionModel().selectionChanged.connect(self._selection_changed)
        self.list_page.model.modelReset.connect(self._clear_detail)

    @property
    def selected_activity_id(self) -> int | None:
        return self.activity_combo.currentData()

    @property
    def selected_day(self) -> dt.date | None:
        if not self.only_day.isChecked():
            return None
        date = self.calendar.selectedDate().toPython()
        if date.year != self.list_page.year_spin.value():
            return None  # Éviter un filtre de jour incohérent pendant la synchronisation.
        return date

    def _extra_filters(self) -> dict:
        return {
            "activity_id": self.selected_activity_id,
            "individual_id": self._record_individual_id,
            "inscription_id": self._record_inscription_id,
            "day": self.selected_day,
        }

    def focus_record(self, *, individual_id: int | None = None,
                     inscription_id: int | None = None,
                     year: int | None = None) -> None:
        """C11 : ID exact, état de filtres cohérent, une seule actualisation."""
        for label, ident in (("individu", individual_id), ("inscription", inscription_id)):
            if ident is not None and (
                not isinstance(ident, int) or isinstance(ident, bool) or ident <= 0
            ):
                raise ValueError(f"Identifiant {label} de fiche invalide")
        if year is not None and (
            not isinstance(year, int) or isinstance(year, bool)
            or not 1900 <= year <= 2098
        ):
            raise ValueError("Année de fiche invalide")

        controls = (
            self.only_day, self.list_page.year_spin, self.calendar,
            self.activity_combo, self.list_page.search_edit,
            *self.list_page.state_checks.values(),
        )
        blockers = [QSignalBlocker(widget) for widget in controls]
        try:
            self.only_day.setChecked(False)
            self.activity_combo.setCurrentIndex(0)
            self.list_page.search_edit.clear()
            self.list_page._debounce.stop()
            for check in self.list_page.state_checks.values():
                check.setChecked(True)
            if year is not None:
                old = self.calendar.selectedDate()
                day = min(old.day(), calendar.monthrange(year, old.month())[1])
                new_date = QDate(year, old.month(), day)
                self.calendar.setSelectedDate(new_date)
                self.calendar.setCurrentPage(year, old.month())
                self.list_page.year_spin.setValue(year)
        finally:
            for blocker in blockers:
                blocker.unblock()

        self._record_individual_id = individual_id
        self._record_inscription_id = inscription_id
        parts = []
        if individual_id is not None:
            parts.append(f"Individu #{individual_id}")
        if inscription_id is not None:
            parts.append(f"Inscription #{inscription_id}")
        self.record_filter_label.setText(
            "Filtre exact : " + " · ".join(parts) if parts else ""
        )
        self.record_filter_label.setVisible(bool(parts))
        self.clear_record_button.setVisible(bool(parts))
        if self._loaded:
            self.refresh()

    def clear_record_context(self) -> None:
        self.focus_record()

    def activate(self) -> None:
        if not self._loaded:
            self._loaded = True
            self.list_page.activate()
            self.refresh_month()
            self._load_activities()

    def refresh(self, *_args) -> None:
        if not self._loaded:
            return
        self.list_page.refresh()
        self.refresh_month()

    def _year_changed(self, year: int) -> None:
        if self._calendar_sync or not self._loaded:
            return
        date = self.calendar.selectedDate()
        selected = QDate(year, date.month(), min(date.day(), calendar.monthrange(year, date.month())[1]))
        self._calendar_sync = True
        self.calendar.setSelectedDate(selected)
        self.calendar.setCurrentPage(year, selected.month())
        self._calendar_sync = False
        self.refresh()  # Corrige l'éventuelle requête C1 déclenchée avant le calendrier.

    def _day_changed(self) -> None:
        if self._calendar_sync or not self._loaded:
            return
        date = self.calendar.selectedDate()
        if self.list_page.year_spin.value() != date.year():
            self._calendar_sync = True
            self.list_page.year_spin.setValue(date.year())
            self._calendar_sync = False
        if not self.only_day.isChecked():
            self.only_day.setChecked(True)
        else:
            self.list_page.refresh()

    def _page_changed(self, year: int, month: int) -> None:
        if self._calendar_sync or not self._loaded:
            return
        selected = self.calendar.selectedDate()
        if selected.year() != year or selected.month() != month:
            self._calendar_sync = True
            self.calendar.setSelectedDate(QDate(year, month, 1))
            self._calendar_sync = False
            if self.only_day.isChecked():
                self.list_page.refresh()
        if self.list_page.year_spin.value() != year:
            self._calendar_sync = True
            self.list_page.year_spin.setValue(year)
            self._calendar_sync = False
            self.list_page.refresh()
        self.refresh_month()

    def _filter_day_changed(self, _checked: bool) -> None:
        if self._loaded:
            self.list_page.refresh()

    def _choose_day(self, item: QListWidgetItem) -> None:
        if not self._loaded:
            return
        chosen = QDate.fromString(str(item.data(Qt.ItemDataRole.UserRole)), Qt.DateFormat.ISODate)
        if chosen.isValid():
            self.calendar.setSelectedDate(chosen)
            if not self.only_day.isChecked():
                self.only_day.setChecked(True)
            else:
                self.list_page.refresh()

    def _load_activities(self) -> None:
        if self._activity_loaded or self._activity_worker is not None:
            return
        if not self.background:
            try:
                result = self.calendar_repository.list_activities()
            except Exception as exc:
                self.month_summary.setText(f"Activités indisponibles : {exc}")
            else:
                self._apply_activities(result)
            return
        worker = _CalendarWorker(self.calendar_repository, 0, "list_activities", {})
        self._activity_worker = worker
        worker.signals.completed.connect(self._activities_completed)
        QThreadPool.globalInstance().start(worker)

    def _activities_completed(self, _token, result, error) -> None:
        self._activity_worker = None
        if error:
            self.month_summary.setText(f"Activités indisponibles : {error}")
        else:
            self._apply_activities(result)

    def _apply_activities(self, result) -> None:
        if not isinstance(result, tuple):
            self.month_summary.setText("Liste d'activités inattendue.")
            return
        selected = self.selected_activity_id
        self.activity_combo.blockSignals(True)
        try:
            self.activity_combo.clear()
            self.activity_combo.addItem("Toutes les activités", None)
            for ident, name in result:
                self.activity_combo.addItem(f"{name} (#{ident})", ident)
            index = self.activity_combo.findData(selected) if selected is not None else 0
            self.activity_combo.setCurrentIndex(max(0, index))
        finally:
            self.activity_combo.blockSignals(False)
        self._activity_loaded = True

    def refresh_month(self, *_args) -> None:
        if not self._loaded:
            return
        self._month_token += 1
        self._month_queued = None
        states = self.list_page.selected_states
        if not states:
            self._apply_month(())
            return
        filters = {
            "year": self.calendar.yearShown(),
            "month": self.calendar.monthShown(),
            "states": states,
            "activity_id": self.selected_activity_id,
            "individual_id": self._record_individual_id,
            "inscription_id": self._record_inscription_id,
            "text": self.list_page.search_edit.text().strip(),
        }
        self.month_summary.setText("Calcul du mois…")
        if not self.background:
            try:
                result = self.calendar_repository.month_counts(**filters)
            except Exception as exc:
                self._month_error(str(exc))
            else:
                self._apply_month(result)
            return
        self._month_queued = (self._month_token, filters)
        self._launch_month()

    def _launch_month(self) -> None:
        if self._month_worker is not None or self._month_queued is None:
            return
        token, filters = self._month_queued
        self._month_queued = None
        worker = _CalendarWorker(self.calendar_repository, token, "month_counts", filters)
        self._month_worker = worker
        worker.signals.completed.connect(self._month_completed)
        QThreadPool.globalInstance().start(worker)

    def _month_completed(self, token: int, result: object, error: str) -> None:
        self._month_worker = None
        self._launch_month()  # Seule la plus récente demande en attente est exécutée.
        if token != self._month_token:
            return
        if error:
            self._month_error(error)
        elif isinstance(result, tuple):
            self._apply_month(result)
        else:
            self._month_error("Réponse mensuelle inattendue.")

    def _month_error(self, error: str) -> None:
        self._clear_marks()
        self.day_list.clear()
        self._date_counts = ()
        self.month_summary.setText(f"Calendrier indisponible : {error}")

    def _clear_marks(self) -> None:
        for date in self._marked_dates:
            self.calendar.setDateTextFormat(date, QTextCharFormat())
        self._marked_dates.clear()

    def _apply_month(self, rows: tuple[DayCount, ...]) -> None:
        # Un rafraîchissement sans données nouvelles ne doit ni vider la
        # liste des jours, ni effacer les formats du calendrier.
        if rows != self._date_counts:
            self._date_counts = rows
            self._clear_marks()
            self.day_list.clear()
            for entry in rows:
                qdate = QDate(entry.date.year, entry.date.month, entry.date.day)
                fmt = QTextCharFormat()
                fmt.setFontWeight(int(QFont.Weight.Bold))
                fmt.setToolTip(f"{entry.count} consommation(s) suivant les filtres")
                self.calendar.setDateTextFormat(qdate, fmt)
                self._marked_dates.add(qdate)
                item = QListWidgetItem(
                    f"{entry.date.strftime('%d/%m')} · {entry.count} consommation(s)"
                )
                item.setData(Qt.ItemDataRole.UserRole, entry.date.isoformat())
                self.day_list.addItem(item)
        total = sum(row.count for row in rows)
        self.month_summary.setText(
            f"{total} consommation(s) sur {len(rows)} jour(s) du mois affiché "
            "(selon les filtres, sans plafonnement)."
        )

    def _selection_changed(self, *_args) -> None:
        selected = self.list_page.table.selectionModel().selectedRows()
        if not selected:
            self._clear_detail()
            return
        row = self.list_page.model.rows[selected[0].row()]
        self.preparation_panel.set_row(row)
        event_label = (
            f"Événement #{row.event_id} : {row.event_name or 'sans libellé'}"
            if row.event_id is not None else
            "Aucun événement lié ; séance canonique non déterminée"
        )
        self.details_label.setText(
            f"Consommation #{row.consumption_id} — {format_date(row.date)} "
            f"— {state_label(row.state)}\n"
            f"{row.last_name} {row.first_name} · {row.activity}\n"
            f"Unité : {row.unit or '—'} · Groupe : {row.group or '—'} "
            f"· Horaires : {row.hours_label or 'non précisés'}\n"
            f"{event_label}\n"
            f"Prestation #{row.prestation_id if row.prestation_id is not None else 'aucune'} "
            f"· Montant associé : {row.amount_label or 'non renseigné'}"
        )

    def _clear_detail(self) -> None:
        self.preparation_panel.set_row(None)
        self.details_label.setText("Sélectionnez une consommation pour afficher son détail.")
