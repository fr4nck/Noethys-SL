import os
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from noethys_qt.activity_editor import NativeActivityEditorRepository, UNLIMITED_END, UNLIMITED_START
from noethys_qt.activity_units import (
    ActivityEditorDialog,
    ActivityUnitsPage,
    ActivityUnitsRepository,
    ConsumptionUnit,
)


class ActivityUnitsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_database(self) -> Path:
        handle, filename = tempfile.mkstemp(suffix="_DATA.dat")
        os.close(handle)
        database = Path(filename)
        connection = sqlite3.connect(database)
        try:
            connection.executescript(
                """
                CREATE TABLE activites (
                    IDactivite INTEGER PRIMARY KEY,
                    nom TEXT, abrege TEXT, coords_org INTEGER, rue TEXT, cp TEXT,
                    ville TEXT, tel TEXT, fax TEXT, mail TEXT, site TEXT,
                    date_debut TEXT, date_fin TEXT, nbre_inscrits_max INTEGER,
                    code_comptable TEXT, regie INTEGER, code_produit_local TEXT,
                    inscriptions_multiples INTEGER, code_service TEXT, code_analytique TEXT
                );
                CREATE TABLE factures_regies (IDregie INTEGER PRIMARY KEY, nom TEXT);
                CREATE TABLE types_groupes_activites (
                    IDtype_groupe_activite INTEGER PRIMARY KEY, nom TEXT, observations TEXT
                );
                CREATE TABLE groupes_activites (IDtype_groupe_activite INTEGER, IDactivite INTEGER);
                CREATE TABLE groupes (
                    IDgroupe INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER, nom TEXT, ordre INTEGER, abrege TEXT,
                    nbre_inscrits_max INTEGER
                );
                CREATE TABLE unites (
                    IDunite INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER,
                    nom TEXT,
                    abrege TEXT,
                    type TEXT,
                    heure_debut TEXT,
                    heure_fin TEXT,
                    repas INTEGER,
                    IDrestaurateur INTEGER,
                    date_debut TEXT,
                    date_fin TEXT,
                    touche_raccourci TEXT,
                    heure_debut_fixe INTEGER,
                    heure_fin_fixe INTEGER,
                    autogen_active INTEGER,
                    autogen_conditions TEXT,
                    autogen_parametres TEXT,
                    ordre INTEGER
                );
                CREATE TABLE unites_groupes (
                    IDunite_groupe INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDunite INTEGER,
                    IDgroupe INTEGER
                );
                CREATE TABLE unites_incompat (
                    IDunite_incompat INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDunite INTEGER,
                    IDunite_incompatible INTEGER
                );
                CREATE TABLE restaurateurs (IDrestaurateur INTEGER PRIMARY KEY, nom TEXT);
                CREATE TABLE unites_remplissage (
                    IDunite_remplissage INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER,
                    nom TEXT,
                    abrege TEXT,
                    seuil_alerte INTEGER,
                    date_debut TEXT,
                    date_fin TEXT,
                    ordre INTEGER,
                    heure_min TEXT,
                    heure_max TEXT
                );
                CREATE TABLE unites_remplissage_unites (
                    IDunite_remplissage_unite INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDunite_remplissage INTEGER,
                    IDunite INTEGER
                );
                CREATE TABLE ouvertures (
                    IDouverture INTEGER PRIMARY KEY,
                    IDgroupe INTEGER,
                    IDunite INTEGER
                );
                CREATE TABLE inscriptions (IDinscription INTEGER PRIMARY KEY, IDgroupe INTEGER);
                CREATE TABLE consommations (
                    IDconso INTEGER PRIMARY KEY,
                    IDgroupe INTEGER,
                    IDunite INTEGER,
                    IDindividu INTEGER,
                    date TEXT
                );
                CREATE TABLE evenements (
                    IDevenement INTEGER PRIMARY KEY,
                    IDunite INTEGER,
                    date TEXT
                );
                CREATE TABLE tarifs (IDtarif INTEGER PRIMARY KEY, groupes TEXT);
                CREATE TABLE combi_tarifs_unites (
                    IDcombi_tarif INTEGER PRIMARY KEY,
                    IDunite INTEGER
                );
                CREATE TABLE aides_combi_unites (
                    IDaide_combi_unite INTEGER PRIMARY KEY,
                    IDunite INTEGER
                );
                CREATE TABLE remplissage (
                    IDremplissage INTEGER PRIMARY KEY,
                    IDgroupe INTEGER,
                    IDunite_remplissage INTEGER
                );
                """
            )
            connection.execute(
                "INSERT INTO activites VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    7, "École Multisports", "EMS", 1, None, None, None, None, None,
                    None, None, "1977-01-01", "2999-01-01", None, "706", None,
                    "SPORT", 0, "EMS", "A1",
                ),
            )
            connection.execute(
                "INSERT INTO groupes (IDactivite, nom, ordre, abrege, nbre_inscrits_max) VALUES (7, 'Petits', 1, 'P', 20)"
            )
            connection.execute(
                "INSERT INTO groupes (IDactivite, nom, ordre, abrege, nbre_inscrits_max) VALUES (7, 'Grands', 2, 'G', NULL)"
            )
            connection.execute("INSERT INTO restaurateurs VALUES (1, 'Cuisine centrale')")
            connection.execute(
                """
                INSERT INTO unites (
                    IDactivite, nom, abrege, type, heure_debut, heure_fin, repas,
                    IDrestaurateur, date_debut, date_fin, touche_raccourci,
                    heure_debut_fixe, heure_fin_fixe, autogen_active,
                    autogen_conditions, autogen_parametres, ordre
                ) VALUES (7, 'Journée', 'J', 'Unitaire', NULL, NULL, 0, NULL,
                          '1977-01-01', '2999-01-01', 'WXK_F1', 0, 0, 1,
                          'AGE>=3', 'ETAT:=reservation', 1)
                """
            )
            unit_id = int(connection.execute("SELECT IDunite FROM unites").fetchone()[0])
            group_id = int(connection.execute("SELECT IDgroupe FROM groupes ORDER BY ordre").fetchone()[0])
            connection.execute(
                "INSERT INTO unites_groupes (IDunite, IDgroupe) VALUES (?, ?)",
                (unit_id, group_id),
            )
            connection.execute(
                """
                INSERT INTO unites_remplissage (
                    IDactivite, nom, abrege, seuil_alerte, date_debut, date_fin,
                    ordre, heure_min, heure_max
                ) VALUES (7, 'Capacité journée', 'CAP', 5, '1977-01-01', '2999-01-01', 1, '08:00', '18:00')
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.addCleanup(database.unlink, missing_ok=True)
        return database

    def test_repository_reads_units_and_filling_units(self):
        repository = ActivityUnitsRepository(NativeActivityEditorRepository(self._make_database()))

        units = repository.list_units(7)
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].name, "Journée")
        self.assertEqual(units[0].type_code, "Unitaire")
        self.assertEqual(units[0].period, "Illimitée")
        self.assertTrue(units[0].auto_gen_active)
        self.assertEqual(units[0].auto_gen_conditions, "AGE>=3")

        filling = repository.list_filling_units(7)
        self.assertEqual(len(filling), 1)
        self.assertEqual(filling[0].name, "Capacité journée")
        self.assertEqual(filling[0].time_range, "08h00-18h00")
        self.assertEqual(filling[0].period, "Illimitée")

    def test_repository_adds_updates_links_and_preserves_autogen_parameters(self):
        database = self._make_database()
        repository = ActivityUnitsRepository(NativeActivityEditorRepository(database))
        groups = repository.list_groups(7)
        second_group = groups[1][0]

        unit = ConsumptionUnit(
            unit_id=None,
            activity_id=7,
            name="Demi-journée",
            short_name="DJ",
            type_code="Horaire",
            start_date=UNLIMITED_START,
            end_date=UNLIMITED_END,
            order=0,
            auto_gen_active=False,
            hour_start="08:30",
            hour_end="12:00",
            shortcut="WXK_F2",
        )
        unit_id = repository.save_unit(unit, group_ids=[second_group], incompatible_ids=[])
        created = next(row for row in repository.list_units(7) if row.unit_id == unit_id)
        self.assertEqual(created.name, "Demi-journée")
        self.assertEqual(repository.unit_group_ids(unit_id), {second_group})

        changed = replace(
            created,
            name="Matin",
            auto_gen_active=True,
            auto_gen_conditions="EXISTANT",
            auto_gen_parameters="ETAT:=attente",
        )
        repository.save_unit(changed, group_ids=None, incompatible_ids=[])
        updated = next(row for row in repository.list_units(7) if row.unit_id == unit_id)
        self.assertEqual(updated.name, "Matin")
        self.assertTrue(updated.auto_gen_active)
        self.assertEqual(updated.auto_gen_conditions, "EXISTANT")
        self.assertEqual(updated.auto_gen_parameters, "ETAT:=attente")
        self.assertEqual(repository.unit_group_ids(unit_id), set())

    def test_event_type_transition_is_blocked_when_consumptions_exist(self):
        database = self._make_database()
        repository = ActivityUnitsRepository(NativeActivityEditorRepository(database))
        unit = repository.list_units(7)[0]
        connection = sqlite3.connect(database)
        try:
            connection.execute(
                "INSERT INTO consommations VALUES (1, NULL, ?, 12, '2026-09-03')",
                (unit.unit_id,),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(ValueError):
            repository.save_unit(
                replace(unit, type_code="Evenement"),
                group_ids=None,
                incompatible_ids=[],
            )

    def test_delete_is_blocked_by_historic_dependencies(self):
        database = self._make_database()
        repository = ActivityUnitsRepository(NativeActivityEditorRepository(database))
        unit = repository.list_units(7)[0]
        connection = sqlite3.connect(database)
        try:
            connection.execute("INSERT INTO ouvertures VALUES (1, NULL, ?)", (unit.unit_id,))
            connection.execute("INSERT INTO combi_tarifs_unites VALUES (1, ?)", (unit.unit_id,))
            connection.commit()
        finally:
            connection.close()

        dependencies = repository.usage(unit.unit_id)
        self.assertIn("1 ouverture(s)", dependencies)
        self.assertIn("1 combinaison(s) de tarifs", dependencies)
        with self.assertRaises(ValueError):
            repository.delete_unit(7, unit.unit_id)

    def test_move_resequences_units(self):
        database = self._make_database()
        repository = ActivityUnitsRepository(NativeActivityEditorRepository(database))
        second = ConsumptionUnit(
            unit_id=None,
            activity_id=7,
            name="Soir",
            short_name="S",
            type_code="Unitaire",
            start_date=UNLIMITED_START,
            end_date=UNLIMITED_END,
            order=0,
            auto_gen_active=False,
        )
        second_id = repository.save_unit(second, group_ids=None, incompatible_ids=[])
        repository.move_unit(7, second_id, -1)
        rows = repository.list_units(7)
        self.assertEqual([row.name for row in rows], ["Soir", "Journée"])
        self.assertEqual([row.order for row in rows], [1, 2])

    def test_units_page_and_editor_smoke(self):
        editor_repository = NativeActivityEditorRepository(self._make_database())
        page = ActivityUnitsPage(editor_repository, 7)
        self.addCleanup(page.close)
        self.assertEqual(page.unit_model.rowCount(), 1)
        self.assertEqual(page.filling_model.rowCount(), 1)

        dialog = ActivityEditorDialog(editor_repository, 7)
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.tabs.tabText(2), "Groupes")
        self.assertEqual(dialog.tabs.tabText(5), "Unités")
        self.assertIs(dialog.tabs.widget(5), dialog.units_page)


if __name__ == "__main__":
    unittest.main()
