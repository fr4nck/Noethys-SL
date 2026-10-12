"""Premier écran Qt de Noethys : liste des activités.

Objectif : remplacer uniquement la couche graphique du tableau historique
``Ol/OL_Activites.py`` sans modifier le schéma ni les règles métier.

Le mode par défaut réutilise ``GestionDB.DB`` afin de lire la base configurée
par Noethys. Il n'instancie aucune boucle événementielle wx : Qt reste l'unique
moteur graphique du prototype.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSettings, QSortFilterProxyModel, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHeaderView,
    QMainWindow,
    QMenu,
    QMessageBox,
    QTableView,
    QToolBar,
)


ROOT = Path(__file__).resolve().parents[1]
NOETHYS_PACKAGE = ROOT / "noethys"


def _as_date(value: object) -> dt.date | None:
    if value in (None, ""):
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _format_period(start: dt.date | None, end: dt.date | None) -> str:
    if start == dt.date(1977, 1, 1) and end == dt.date(2999, 1, 1):
        return "Illimitée"
    if start is None or end is None:
        return "Pas de période"
    return f"Du {start:%d/%m/%Y} au {end:%d/%m/%Y}"


@dataclass(frozen=True, slots=True)
class ActivityRow:
    activity_id: int
    name: str
    short_name: str
    start_date: dt.date | None
    end_date: dt.date | None

    @classmethod
    def from_db_row(cls, row: Sequence[object]) -> "ActivityRow":
        return cls(
            activity_id=int(row[0]),
            name=str(row[1] or ""),
            short_name=str(row[2] or ""),
            start_date=_as_date(row[3]),
            end_date=_as_date(row[4]),
        )

    @property
    def period(self) -> str:
        return _format_period(self.start_date, self.end_date)


# Garde Noethys-SL : sans --sqlite, le prototype ouvrirait la base configurée
# dans Noethys, c'est-à-dire possiblement la base de production. Ce n'est permis
# que sur autorisation explicite (variable d'environnement valant « 1 »).
AUTORISATION_BASE_CONFIGUREE = "NOETHYS_QT_BASE_CONFIGUREE"


def VerifierAccesBaseConfiguree() -> None:
    if os.environ.get(AUTORISATION_BASE_CONFIGUREE, "") != "1":
        raise RuntimeError(
            "Prototype Qt : la base configurée dans Noethys (peut-être la production) "
            "n'est pas ouverte par défaut. Lancez le prototype avec --sqlite "
            "<copie fictive>, ou définissez %s=1 en connaissance de cause."
            % AUTORISATION_BASE_CONFIGUREE
        )


class ActivityRepository:
    def fetch(self, only_open: bool = False) -> list[ActivityRow]:
        raise NotImplementedError


class LegacyNoethysActivityRepository(ActivityRepository):
    """Lecture seule via le mécanisme de connexion déjà utilisé par Noethys."""

    def fetch(self, only_open: bool = False) -> list[ActivityRow]:
        VerifierAccesBaseConfiguree()
        noethys_path = str(NOETHYS_PACKAGE)
        if noethys_path not in sys.path:
            sys.path.insert(0, noethys_path)

        try:
            import GestionDB  # type: ignore
        except Exception as exc:  # pragma: no cover - dépend de l'environnement Noethys
            raise RuntimeError(
                "Impossible de charger GestionDB. Lancez le prototype depuis une "
                "installation Noethys Upgrade complète."
            ) from exc

        condition = ""
        if only_open:
            condition = f"WHERE date_fin >= '{dt.date.today().isoformat()}'"

        query = f"""
            SELECT IDactivite, nom, abrege, date_debut, date_fin
            FROM activites
            {condition}
            ORDER BY date_fin, nom;
        """

        db = GestionDB.DB()
        try:
            if getattr(db, "echec", 0):
                detail = getattr(db, "erreur", "connexion indisponible")
                raise RuntimeError(f"Impossible d'ouvrir la base Noethys : {detail}")
            db.ExecuterReq(query)
            rows = db.ResultatReq()
        finally:
            try:
                db.Close()
            except Exception:
                pass

        return [ActivityRow.from_db_row(row) for row in rows]


class SqliteActivityRepository(ActivityRepository):
    """Mode de recette autonome, sans import wx, sur une copie SQLite Noethys."""

    def __init__(self, database: Path):
        self.database = database

    def fetch(self, only_open: bool = False) -> list[ActivityRow]:
        if not self.database.is_file():
            raise RuntimeError(f"Base SQLite introuvable : {self.database}")

        query = """
            SELECT IDactivite, nom, abrege, date_debut, date_fin
            FROM activites
        """
        params: tuple[object, ...] = ()
        if only_open:
            query += " WHERE date_fin >= ?"
            params = (dt.date.today().isoformat(),)
        query += " ORDER BY date_fin, nom"

        with sqlite3.connect(self.database) as connection:
            rows = connection.execute(query, params).fetchall()
        return [ActivityRow.from_db_row(row) for row in rows]


class ActivityTableModel(QAbstractTableModel):
    HEADERS = ("ID", "Nom de l'activité", "Abrégé", "Période de validité")
    SORT_ROLE = int(Qt.ItemDataRole.UserRole)

    def __init__(self, rows: Iterable[ActivityRow] = ()):  # noqa: D107
        super().__init__()
        self._rows = list(rows)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        column = index.column()

        if role == int(Qt.ItemDataRole.DisplayRole):
            return (row.activity_id, row.name, row.short_name, row.period)[column]

        if role == self.SORT_ROLE:
            if column == 0:
                return row.activity_id
            if column == 1:
                return row.name.casefold()
            if column == 2:
                return row.short_name.casefold()
            return row.end_date.isoformat() if row.end_date else "0000-00-00"

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = int(Qt.ItemDataRole.DisplayRole)):  # noqa: N802,E501
        if role == int(Qt.ItemDataRole.DisplayRole) and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def row_at(self, row: int) -> ActivityRow:
        return self._rows[row]

    def replace_rows(self, rows: Iterable[ActivityRow]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()


class ActivitiesWindow(QMainWindow):
    def __init__(
        self,
        repository: ActivityRepository,
        *,
        initial_open_only: bool = False,
        requested_theme: str | None = None,
    ):
        super().__init__()
        self.repository = repository
        self.settings = QSettings("Noethys", "QtActivitiesPrototype")
        self.setWindowTitle("Noethys Qt — Gestion des activités")

        self.model = ActivityTableModel()
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(ActivityTableModel.SORT_ROLE)
        self.proxy.setDynamicSortFilter(True)

        self.table = QTableView(self)
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.setCentralWidget(self.table)

        self._configure_columns()
        self._create_actions()
        self._create_toolbar(initial_open_only, requested_theme)
        self._restore_geometry()
        self.reload()

    def _configure_columns(self) -> None:
        header = self.table.horizontalHeader()
        self.table.setColumnHidden(0, True)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        state = self.settings.value("activities/header_state")
        if state is not None:
            header.restoreState(state)
            self.table.setColumnHidden(0, True)

    def _create_actions(self) -> None:
        self.refresh_action = QAction("Actualiser", self)
        self.refresh_action.triggered.connect(self.reload)

        self.export_text_action = QAction("Exporter au format Texte", self)
        self.export_text_action.triggered.connect(self.export_text)

        self.export_excel_action = QAction("Exporter au format Excel", self)
        self.export_excel_action.triggered.connect(self.export_excel)

        self.deferred_actions: list[QAction] = []
        for label in (
            "Ajouter",
            "Modifier",
            "Supprimer",
            "Dupliquer",
            "Importer",
            "Exporter une activité",
            "Aperçu avant impression",
            "Imprimer",
        ):
            action = QAction(label, self)
            action.setEnabled(False)
            action.setToolTip("Hors périmètre du prototype Qt n°1")
            self.deferred_actions.append(action)

    def _create_toolbar(self, initial_open_only: bool, requested_theme: str | None) -> None:
        toolbar = QToolBar("Commandes", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        toolbar.addAction(self.refresh_action)
        toolbar.addSeparator()

        self.open_only = QCheckBox("Activités ouvertes", toolbar)
        self.open_only.setChecked(initial_open_only)
        self.open_only.toggled.connect(self.reload)
        toolbar.addWidget(self.open_only)
        toolbar.addSeparator()

        toolbar.addAction(self.export_text_action)
        toolbar.addAction(self.export_excel_action)
        toolbar.addSeparator()

        self.theme_combo = QComboBox(toolbar)
        self.theme_combo.addItem("Thème système", "system")
        self.theme_combo.addItem("Clair", "light")
        self.theme_combo.addItem("Sombre", "dark")
        saved_theme = requested_theme or str(self.settings.value("appearance/theme", "system"))
        index = max(0, self.theme_combo.findData(saved_theme))
        self.theme_combo.setCurrentIndex(index)
        self.theme_combo.currentIndexChanged.connect(self._theme_changed)
        toolbar.addWidget(self.theme_combo)
        self._set_theme(saved_theme)

    def _theme_changed(self) -> None:
        self._set_theme(str(self.theme_combo.currentData()))

    def _set_theme(self, theme: str) -> None:
        hints = QApplication.styleHints()
        scheme = {
            "system": Qt.ColorScheme.Unknown,
            "light": Qt.ColorScheme.Light,
            "dark": Qt.ColorScheme.Dark,
        }.get(theme, Qt.ColorScheme.Unknown)

        setter = getattr(hints, "setColorScheme", None)
        if callable(setter):
            setter(scheme)
            self.settings.setValue("appearance/theme", theme)
        elif theme != "system":
            self.statusBar().showMessage(
                "Cette version de Qt ne permet pas de forcer le thème ; thème système conservé.",
                5000,
            )

    def _restore_geometry(self) -> None:
        geometry = self.settings.value("window/geometry")
        if geometry is not None and self.restoreGeometry(geometry):
            return
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(int(available.width() * 0.72), int(available.height() * 0.72))

    def reload(self, *_args) -> None:
        try:
            rows = self.repository.fetch(self.open_only.isChecked())
        except Exception as exc:
            QMessageBox.critical(self, "Noethys Qt", str(exc))
            return

        self.model.replace_rows(rows)
        self.table.sortByColumn(3, Qt.SortOrder.DescendingOrder)
        self.statusBar().showMessage(f"{len(rows)} activité(s)")

    def _show_context_menu(self, position) -> None:
        menu = QMenu(self)
        for action in self.deferred_actions[:4]:
            menu.addAction(action)
        menu.addSeparator()
        for action in self.deferred_actions[4:6]:
            menu.addAction(action)
        menu.addSeparator()
        for action in self.deferred_actions[6:]:
            menu.addAction(action)
        menu.addSeparator()
        menu.addAction(self.export_text_action)
        menu.addAction(self.export_excel_action)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def _visible_rows(self) -> list[ActivityRow]:
        rows: list[ActivityRow] = []
        for proxy_row in range(self.proxy.rowCount()):
            source_index = self.proxy.mapToSource(self.proxy.index(proxy_row, 0))
            rows.append(self.model.row_at(source_index.row()))
        return rows

    def export_text(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter la liste des activités",
            "activites.csv",
            "Fichier CSV (*.csv);;Fichier texte (*.txt)",
        )
        if not filename:
            return

        try:
            with open(filename, "w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream, delimiter=";")
                writer.writerow(ActivityTableModel.HEADERS)
                for row in self._visible_rows():
                    writer.writerow((row.activity_id, row.name, row.short_name, row.period))
        except OSError as exc:
            QMessageBox.critical(self, "Export texte", str(exc))
            return
        self.statusBar().showMessage(f"Export texte créé : {filename}", 5000)

    def export_excel(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter la liste des activités",
            "activites.xlsx",
            "Classeur Excel (*.xlsx)",
        )
        if not filename:
            return
        if not filename.lower().endswith(".xlsx"):
            filename += ".xlsx"

        try:
            import xlsxwriter
        except ImportError:
            QMessageBox.critical(
                self,
                "Export Excel",
                "XlsxWriter n'est pas installé dans cet environnement.",
            )
            return

        rows = self._visible_rows()
        workbook = None
        try:
            workbook = xlsxwriter.Workbook(filename)
            worksheet = workbook.add_worksheet("Activités")
            header_format = workbook.add_format({"bold": True})
            for column, title in enumerate(ActivityTableModel.HEADERS):
                worksheet.write(0, column, title, header_format)
            for line, row in enumerate(rows, start=1):
                values = (row.activity_id, row.name, row.short_name, row.period)
                for column, value in enumerate(values):
                    worksheet.write(line, column, value)
            worksheet.freeze_panes(1, 0)
            if rows:
                worksheet.autofilter(0, 0, len(rows), len(ActivityTableModel.HEADERS) - 1)
            worksheet.set_column(0, 0, None, None, {"hidden": True})
            worksheet.set_column(1, 1, 32)
            worksheet.set_column(2, 2, 16)
            worksheet.set_column(3, 3, 28)
            workbook.close()
            workbook = None
        except Exception as exc:
            if workbook is not None:
                try:
                    workbook.close()
                except Exception:
                    pass
            QMessageBox.critical(self, "Export Excel", str(exc))
            return

        self.statusBar().showMessage(f"Export Excel créé : {filename}", 5000)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue("activities/header_state", self.table.horizontalHeader().saveState())
        super().closeEvent(event)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prototype Qt — liste des activités Noethys")
    parser.add_argument(
        "--sqlite",
        type=Path,
        help="Copie SQLite Noethys à utiliser à la place de la configuration courante.",
    )
    parser.add_argument(
        "--open-only",
        action="store_true",
        help="N'afficher au démarrage que les activités dont la date de fin n'est pas passée.",
    )
    parser.add_argument("--theme", choices=("system", "light", "dark"))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Noethys Qt — Activités")
    app.setOrganizationName("Noethys")

    repository: ActivityRepository
    if args.sqlite:
        repository = SqliteActivityRepository(args.sqlite)
    else:
        repository = LegacyNoethysActivityRepository()

    window = ActivitiesWindow(
        repository,
        initial_open_only=args.open_only,
        requested_theme=args.theme,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
