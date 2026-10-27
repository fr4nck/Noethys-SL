"""C9 : navigation métier FICTIVE Familles -> Individus -> Inscriptions.

Aucun service d'écriture, aucune configuration Noethys. Les données lues
proviennent uniquement de la fixture temporaire du démonstrateur C8.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from tools.qt_c8_fixture import MARKER


class C9BusinessPage(QWidget):
    """Liste de domaines familiers, à lecture seule et navigation directe."""

    DOMAINS = (
        ("familles", "Familles", ("Famille", "Représentants", "Enfants")),
        ("individus", "Individus", ("Individu", "Nom", "Prénom", "Famille")),
        ("activites", "Activités", ("Activité", "Nom", "Inscrits")),
        ("inscriptions", "Inscriptions", ("Inscription", "Individu", "Activité", "Statut")),
    )

    def __init__(self, fictive_db, parent=None):
        super().__init__(parent)
        self._db = fictive_db
        self._domain = "familles"
        self.on_domain_requested = None
        root = QVBoxLayout(self)
        root.addWidget(QLabel("Parcours métier — consultation fictive (aucune saisie)", self))
        navigation = QHBoxLayout()
        self.buttons = {}
        for key, label, _columns in self.DOMAINS:
            button = QPushButton(label, self)
            button.clicked.connect(lambda _checked=False, domain=key: self.show_domain(domain))
            self.buttons[key] = button
            navigation.addWidget(button)
        root.addLayout(navigation)
        self.title = QLabel(self)
        self.title.setObjectName("sectionTitle")
        root.addWidget(self.title)
        self.table = QTableWidget(self)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(False)
        root.addWidget(self.table, 1)
        self.hint = QLabel(
            "Sélectionnez une ligne puis double-cliquez pour parcourir ses liens métier.",
            self,
        )
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)
        self.table.cellDoubleClicked.connect(self._open_related)
        self.show_domain("familles")

    def _read(self, statement, values=()):
        with closing(sqlite3.connect(
            "file:" + self._db.path.as_posix() + "?mode=ro", uri=True
        )) as db:
            db.execute("PRAGMA query_only=ON")
            if db.execute("SELECT token FROM c8_marker").fetchone() != (MARKER,):
                raise RuntimeError("Source C9 non fictive refusée.")
            return tuple(db.execute(statement, values).fetchall())

    def _rows(self, domain):
        if domain == "familles":
            return self._read("""
                SELECT f.IDfamille,
                  COALESCE((SELECT GROUP_CONCAT(i.prenom || ' ' || i.nom)
                    FROM rattachements r JOIN individus i ON i.IDindividu=r.IDindividu
                    WHERE r.IDfamille=f.IDfamille AND r.titulaire=1), ''),
                  COALESCE((SELECT GROUP_CONCAT(i.prenom || ' ' || i.nom)
                    FROM rattachements r JOIN individus i ON i.IDindividu=r.IDindividu
                    WHERE r.IDfamille=f.IDfamille AND r.titulaire=0), '')
                FROM familles f ORDER BY f.IDfamille
            """)
        if domain == "individus":
            return self._read("""
                SELECT i.IDindividu, i.nom, i.prenom,
                  COALESCE((SELECT MIN(r.IDfamille) FROM rattachements r
                    WHERE r.IDindividu=i.IDindividu), '')
                FROM individus i ORDER BY i.nom, i.prenom
            """)
        if domain == "activites":
            return self._read("""
                SELECT a.IDactivite, a.nom, COUNT(ins.IDinscription)
                FROM activites a LEFT JOIN inscriptions ins
                  ON ins.IDactivite=a.IDactivite
                GROUP BY a.IDactivite, a.nom ORDER BY a.nom
            """)
        if domain == "inscriptions":
            return self._read("""
                SELECT ins.IDinscription, i.prenom || ' ' || i.nom,
                  a.nom, ins.statut
                FROM inscriptions ins JOIN individus i
                  ON i.IDindividu=ins.IDindividu
                JOIN activites a ON a.IDactivite=ins.IDactivite
                ORDER BY ins.IDinscription
            """)
        raise ValueError("Domaine métier inconnu")

    def show_domain(self, domain):
        definitions = {key: (label, columns) for key, label, columns in self.DOMAINS}
        if domain not in definitions:
            raise ValueError("Domaine inconnu")
        label, columns = definitions[domain]
        rows = self._rows(domain)
        self._domain = domain
        self.title.setText(f"{label} — {len(rows)} élément(s) fictif(s)")
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setRowCount(len(rows))
        for row_number, values in enumerate(rows):
            for col_number, value in enumerate(values):
                item = QTableWidgetItem(str(value) if value is not None else "")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_number, col_number, item)
        self.table.resizeColumnsToContents()
        self.buttons[domain].setEnabled(False)
        for key, button in self.buttons.items():
            button.setEnabled(key != domain)

    @property
    def domain(self):
        return self._domain

    def _open_related(self, row, _column):
        if row < 0 or row >= self.table.rowCount():
            return
        if self._domain == "familles":
            self.show_domain("individus")
        elif self._domain == "individus":
            self.show_domain("inscriptions")
        elif self._domain == "activites":
            self.show_domain("inscriptions")
        else:
            if callable(self.on_domain_requested):
                self.on_domain_requested("consommations")
