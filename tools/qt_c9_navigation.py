"""C10 : listes et fiches métier sur base C8 entièrement fictive.

Navigation contextuelle Familles / Individus / Activités / Inscriptions,
sans enregistrement, sans import wx et sans interprétation des
constantes de catégories familiales historiques.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from tools.qt_c8_fixture import MARKER


class C9BusinessPage(QWidget):
    """Consultation C9 enrichie au C10, détail sans nouvelle fenêtre."""

    DOMAINS = (
        ("familles", "Familles", ("Famille", "Membres rattachés", "Indicateurs titulaires")),
        ("individus", "Individus", ("Individu", "Nom", "Prénom", "Famille(s)")),
        ("activites", "Activités", ("Activité", "Nom", "Inscrits")),
        ("inscriptions", "Inscriptions", ("Inscription", "Individu", "Activité", "Statut")),
    )
    LABELS = dict((key, label) for key, label, _columns in DOMAINS)

    def __init__(self, fictive_db, parent=None):
        super().__init__(parent)
        self._db = fictive_db
        self._domain = None
        self._filters = {}
        self._history = []
        self._all_rows = ()
        self._rendering = False
        self.on_domain_requested = None

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 7, 8, 7)
        root.setSpacing(7)
        info = QLabel("Gestion quotidienne — démonstration fictive / lecture seule", self)
        info.setObjectName("sectionTitle")
        root.addWidget(info)

        nav = QHBoxLayout()
        self.buttons = {}
        for key, label, _columns in self.DOMAINS:
            button = QPushButton(label, self)
            button.setAccessibleName("Afficher " + label.lower())
            button.clicked.connect(
                lambda _checked=False, domain=key: self.show_domain(domain)
            )
            self.buttons[key] = button
            nav.addWidget(button)
        nav.addStretch(1)
        root.addLayout(nav)

        self.title = QLabel(self)
        self.title.setWordWrap(True)
        root.addWidget(self.title)
        self.search = QLineEdit(self)
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText("Rechercher dans la liste affichée…")
        self.search.setAccessibleName("Rechercher dans le domaine sélectionné")
        root.addWidget(self.search)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.table = QTableWidget(splitter)
        self.table.setAccessibleName("Liste métier fictive")
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setVisible(False)

        detail = QWidget(splitter)
        detail.setMinimumWidth(255)
        details_layout = QVBoxLayout(detail)
        details_layout.setContentsMargins(8, 5, 5, 5)
        details_layout.setSpacing(10)
        self.detail_title = QLabel("Sélectionnez un élément", detail)
        self.detail_title.setObjectName("sectionTitle")
        self.detail_title.setWordWrap(True)
        details_layout.addWidget(self.detail_title)
        self.detail_body = QLabel("La fiche apparaîtra ici.", detail)
        self.detail_body.setAccessibleName("Fiche de l'élément sélectionné")
        self.detail_body.setTextFormat(Qt.TextFormat.PlainText)
        self.detail_body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.detail_body.setWordWrap(True)
        self.detail_body.setAlignment(Qt.AlignmentFlag.AlignTop)
        details_layout.addWidget(self.detail_body, 1)
        self.related_button = QPushButton("Voir les liens", detail)
        self.related_button.setEnabled(False)
        details_layout.addWidget(self.related_button)
        self.individual_consumptions_button = QPushButton(
            "Voir les consommations de cet individu", detail
        )
        self.individual_consumptions_button.hide()
        details_layout.addWidget(self.individual_consumptions_button)
        self.back_button = QPushButton("Retour", detail)
        self.back_button.setEnabled(False)
        details_layout.addWidget(self.back_button)
        splitter.addWidget(self.table)
        splitter.addWidget(detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

        self.hint = QLabel(
            "Un clic affiche la fiche ; double-clic ou « Voir les liens » pour "
            "suivre le dossier choisi. Les catégories familiales ne sont pas "
            "interprétées à partir de leurs identifiants.",
            self,
        )
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)

        self.table.itemSelectionChanged.connect(self._show_selection)
        self.table.cellDoubleClicked.connect(self._open_related)
        self.table.itemActivated.connect(
            lambda item: self._open_related(item.row(), item.column())
        )
        self.related_button.clicked.connect(lambda: self._open_related(self.table.currentRow(), 0))
        self.individual_consumptions_button.clicked.connect(
            self._open_individual_consumptions
        )
        self.back_button.clicked.connect(self.go_back)
        self.search.textChanged.connect(self._render_rows)
        self.show_domain("familles", remember=False)

    def _read(self, statement, values=()):
        """SELECT uniquement sur la base temporaire construite par C8."""
        file = self._db.path
        expected = self._db._root / "C8_DEMONSTRATION_FICTIVE.sqlite"
        if (
            file != expected or file.is_symlink() or not file.is_file()
            or file.resolve() != expected or file.parent.resolve() != self._db._root
        ):
            raise RuntimeError("Source C10 extérieure à la fixture fictive refusée.")
        with closing(sqlite3.connect(
            "file:" + file.as_posix() + "?mode=ro", uri=True
        )) as db:
            db.execute("PRAGMA query_only=ON")
            dbs = db.execute("PRAGMA database_list").fetchall()
            if len(dbs) != 1 or dbs[0][1] != "main":
                raise RuntimeError("Base attachée interdite dans la recette C10.")
            if db.execute("SELECT token FROM c8_marker").fetchone() != (MARKER,):
                raise RuntimeError("Marqueur C8 fictif absent.")
            return tuple(db.execute(statement, values).fetchall())

    def _rows(self, domain, filters):
        if domain == "familles":
            where = "WHERE f.IDfamille=?" if filters.get("family_id") is not None else ""
            args = (filters["family_id"],) if where else ()
            return self._read("""
                SELECT f.IDfamille,
                  COALESCE((SELECT GROUP_CONCAT(i.prenom || ' ' || i.nom, ', ')
                    FROM rattachements r JOIN individus i ON i.IDindividu=r.IDindividu
                    WHERE r.IDfamille=f.IDfamille), ''),
                  COALESCE((SELECT SUM(CASE WHEN r.titulaire=1 THEN 1 ELSE 0 END)
                    FROM rattachements r WHERE r.IDfamille=f.IDfamille), 0)
                FROM familles f """ + where + " ORDER BY f.IDfamille", args)
        if domain == "individus":
            where = (
                "WHERE EXISTS (SELECT 1 FROM rattachements r "
                "WHERE r.IDindividu=i.IDindividu AND r.IDfamille=?)"
                if filters.get("family_id") is not None else ""
            )
            args = (filters["family_id"],) if where else ()
            return self._read("""
                SELECT i.IDindividu, i.nom, i.prenom,
                  COALESCE((SELECT GROUP_CONCAT(DISTINCT r.IDfamille)
                    FROM rattachements r WHERE r.IDindividu=i.IDindividu), '')
                FROM individus i """ + where + " ORDER BY i.nom, i.prenom", args)
        if domain == "activites":
            return self._read("""
                SELECT a.IDactivite, a.nom, COUNT(ins.IDinscription)
                FROM activites a LEFT JOIN inscriptions ins
                  ON ins.IDactivite=a.IDactivite
                GROUP BY a.IDactivite, a.nom ORDER BY a.nom
            """)
        if domain == "inscriptions":
            if "individual_id" in filters:
                clause, args = "WHERE ins.IDindividu=?", (filters["individual_id"],)
            elif "activity_id" in filters:
                clause, args = "WHERE ins.IDactivite=?", (filters["activity_id"],)
            else:
                clause, args = "", ()
            return self._read("""
                SELECT ins.IDinscription, i.prenom || ' ' || i.nom,
                  a.nom, ins.statut
                FROM inscriptions ins JOIN individus i
                  ON i.IDindividu=ins.IDindividu
                JOIN activites a ON a.IDactivite=ins.IDactivite
                """ + clause + " ORDER BY ins.IDinscription", args)
        raise ValueError("Domaine métier inconnu.")

    @property
    def domain(self):
        return self._domain

    def _selected_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def show_domain(self, domain, *, remember=True, restore_id=None, **filters):
        if domain not in self.LABELS:
            raise ValueError("Domaine inconnu")
        # Aucun effet de navigation en cas d'erreur SQL ; préparer d'abord.
        rows = self._rows(domain, filters)
        if remember and self._domain is not None:
            self._history.append((self._domain, dict(self._filters), self._selected_id()))
        self._domain = domain
        self._filters = dict(filters)
        self._all_rows = rows
        self.search.blockSignals(True)
        try:
            self.search.clear()
        finally:
            self.search.blockSignals(False)
        self._render_rows(restore_id=restore_id)
        for key, button in self.buttons.items():
            button.setEnabled(key != domain)
        self.back_button.setEnabled(bool(self._history))

    def _render_rows(self, *_args, restore_id=None):
        if self._domain is None:
            return
        term = self.search.text().strip().casefold()
        rows = (
            [r for r in self._all_rows if any(term in str(v).casefold() for v in r)]
            if term else list(self._all_rows)
        )
        columns = next(cols for key, _label, cols in self.DOMAINS if key == self._domain)
        self._rendering = True
        try:
            self.table.setRowCount(0)
            self.table.setColumnCount(len(columns))
            self.table.setHorizontalHeaderLabels(columns)
            self.table.setRowCount(len(rows))
            desired = 0
            for index, values in enumerate(rows):
                if restore_id is not None and values[0] == restore_id:
                    desired = index
                for column, value in enumerate(values):
                    item = QTableWidgetItem("" if value is None else str(value))
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if column == 0:
                        item.setData(Qt.ItemDataRole.UserRole, int(values[0]))
                    self.table.setItem(index, column, item)
            self.table.resizeColumnsToContents()
            if rows:
                self.table.selectRow(desired)
            else:
                self.table.clearSelection()
        finally:
            self._rendering = False
        title = self.LABELS[self._domain]
        context = ""
        if "family_id" in self._filters:
            context = f" · famille #{self._filters['family_id']}"
        elif "individual_id" in self._filters:
            context = f" · individu #{self._filters['individual_id']}"
        elif "activity_id" in self._filters:
            context = f" · activité #{self._filters['activity_id']}"
        self.title.setText(f"{title}{context} — {len(rows)} élément(s) affiché(s)")
        self._show_selection()

    def _detail(self, domain, ident):
        if domain == "familles":
            members = self._read("""
                SELECT i.prenom || ' ' || i.nom, r.titulaire, r.IDcategorie
                FROM rattachements r JOIN individus i ON i.IDindividu=r.IDindividu
                WHERE r.IDfamille=? ORDER BY i.nom, i.prenom
            """, (ident,))
            count = self._read(
                "SELECT COUNT(*) FROM inscriptions WHERE IDfamille=?", (ident,)
            )[0][0]
            roster = "\n".join(
                f"• {name} · indicateur titulaire={flag} · catégorie brute={cat}"
                for name, flag, cat in members
            ) or "Aucun rattachement"
            return (
                f"Famille #{ident}",
                f"Membres rattachés ({len(members)})\n{roster}\n\n"
                f"Inscriptions liées : {count}\n\n"
                "Les identifiants de catégorie sont affichés sans interpréter "
                "un rôle « représentant » ou « enfant ».",
                "Voir les individus rattachés",
            )
        if domain == "individus":
            person = self._read("""
                SELECT prenom, nom, date_naiss, adresse_auto, ville_resid, mail
                FROM individus WHERE IDindividu=?
            """, (ident,))
            if not person:
                return ("Individu introuvable", "", "Aucun lien")
            first, last, born, address_link, city, email = person[0]
            families = self._read(
                "SELECT IDfamille, titulaire FROM rattachements "
                "WHERE IDindividu=? ORDER BY IDfamille", (ident,),
            )
            enrollments = self._read(
                "SELECT COUNT(*) FROM inscriptions WHERE IDindividu=?", (ident,)
            )[0][0]
            family_label = ", ".join(
                f"#{family} (titulaire brut={flag})" for family, flag in families
            ) or "Aucune"
            address_label = (
                f"Adresse référencée via l'individu #{address_link} (non résolue)"
                if address_link is not None else (city or "Non renseignée")
            )
            return (
                f"{first} {last}",
                f"Individu #{ident}\nNaissance : {born or 'Non renseignée'}\n"
                f"Famille(s) : {family_label}\n"
                f"Adresse : {address_label}\nCourriel fictif : {email or '—'}\n\n"
                f"Inscriptions : {enrollments}",
                "Voir les inscriptions de cet individu",
            )
        if domain == "activites":
            rows = self._read("""
                SELECT nom, abrege, date_debut, date_fin FROM activites
                WHERE IDactivite=?
            """, (ident,))
            if not rows:
                return ("Activité introuvable", "", "Aucun lien")
            name, code, start, end = rows[0]
            count = self._read(
                "SELECT COUNT(*) FROM inscriptions WHERE IDactivite=?", (ident,)
            )[0][0]
            return (
                name,
                f"Activité #{ident}\nCode : {code or '—'}\n"
                f"Période : {start or '—'} → {end or '—'}\n"
                f"Inscriptions : {count}",
                "Voir les inscriptions à cette activité",
            )
        rows = self._read("""
            SELECT ins.IDindividu, i.prenom || ' ' || i.nom,
              ins.IDfamille, a.nom, ins.statut, ins.date_inscription
            FROM inscriptions ins JOIN individus i ON i.IDindividu=ins.IDindividu
            JOIN activites a ON a.IDactivite=ins.IDactivite
            WHERE ins.IDinscription=?
        """, (ident,))
        if not rows:
            return ("Inscription introuvable", "", "Aucun lien")
        person_id, name, family, activity, state, date = rows[0]
        return (
            f"Inscription #{ident}",
            f"Individu : {name} (#{person_id})\n"
            f"Famille référencée : #{family}\n"
            f"Activité : {activity}\n"
            f"Statut brut : {state or '—'}\nDate : {date or '—'}\n\n"
            "Le calendrier sera filtré précisément par les identifiants "
            "de cet individu et de cette inscription (lecture seule).",
            "Voir les consommations de cette inscription",
        )

    def _show_selection(self):
        if self._rendering:
            return
        ident = self._selected_id()
        if ident is None:
            self.detail_title.setText("Sélectionnez un élément")
            self.detail_body.setText("Aucune fiche à afficher.")
            self.related_button.setEnabled(False)
            self.individual_consumptions_button.hide()
            return
        title, body, action = self._detail(self._domain, int(ident))
        self.detail_title.setText(title)
        self.detail_body.setText(body)
        self.related_button.setText(action)
        self.related_button.setEnabled(True)
        self.individual_consumptions_button.setVisible(
            self._domain == "individus"
        )

    def _open_individual_consumptions(self):
        if self._domain != "individus":
            return
        ident = self._selected_id()
        if ident is not None and callable(self.on_domain_requested):
            self.on_domain_requested("consommations", individual_id=int(ident))

    def _open_related(self, row, _column):
        if row < 0 or row >= self.table.rowCount():
            return
        item = self.table.item(row, 0)
        if item is None:
            return
        ident = int(item.data(Qt.ItemDataRole.UserRole))
        if self._domain == "familles":
            self.show_domain("individus", family_id=ident)
        elif self._domain == "individus":
            self.show_domain("inscriptions", individual_id=ident)
        elif self._domain == "activites":
            self.show_domain("inscriptions", activity_id=ident)
        elif self._domain == "inscriptions" and callable(self.on_domain_requested):
            linked = self._read(
                "SELECT IDindividu FROM inscriptions WHERE IDinscription=?",
                (ident,),
            )
            if len(linked) != 1 or linked[0][0] is None:
                self.detail_body.setText(
                    "Inscription sans individu vérifié : navigation bloquée."
                )
                return
            self.on_domain_requested(
                "consommations",
                individual_id=int(linked[0][0]),
                inscription_id=ident,
            )

    def go_back(self):
        if not self._history:
            return
        domain, filters, selected = self._history.pop()
        self.show_domain(domain, remember=False, restore_id=selected, **filters)
