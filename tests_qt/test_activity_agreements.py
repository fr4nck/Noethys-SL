import datetime as dt
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from noethys_qt.activity_agreements import (
    ActivityAgreementsPage,
    ActivityAgreementsRepository,
    Agreement,
    AgreementState,
    UNIQUE_END,
    UNIQUE_START,
)
from noethys_qt.activity_editor import NativeActivityEditorRepository


class ActivityAgreementsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _database(self) -> Path:
        handle, filename = tempfile.mkstemp(suffix="_DATA.dat")
        os.close(handle)
        path = Path(filename)
        connection = sqlite3.connect(path)
        try:
            connection.executescript(
                """
                CREATE TABLE agrements (
                    IDagrement INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER,
                    agrement TEXT,
                    date_debut TEXT,
                    date_fin TEXT
                );
                INSERT INTO agrements (IDactivite, agrement, date_debut, date_fin)
                    VALUES (8, 'AUTRE-ACTIVITE', '2026-01-01', '2026-12-31');
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def _repo(self, path: Path) -> ActivityAgreementsRepository:
        return ActivityAgreementsRepository(NativeActivityEditorRepository(path))

    def test_empty_activity_loads_none_mode(self):
        path = self._database()
        self.assertEqual(self._repo(path).load(7), AgreementState("none", "", ()))

    def test_unique_sentinel_is_detected_and_updated_without_duplicate(self):
        path = self._database()
        connection = sqlite3.connect(path)
        try:
            cursor = connection.execute(
                "INSERT INTO agrements (IDactivite, agrement, date_debut, date_fin) VALUES (7, ?, ?, ?)",
                ("JS-001", UNIQUE_START.isoformat(), UNIQUE_END.isoformat()),
            )
            original_id = cursor.lastrowid
            connection.commit()
        finally:
            connection.close()

        repo = self._repo(path)
        state = repo.load(7)
        self.assertEqual(state.mode, "unique")
        self.assertEqual(state.unique_number, "JS-001")
        repo.save(7, AgreementState("unique", "JS-002", ()))

        rows = repo.list_agreements(7)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].agreement_id, original_id)
        self.assertEqual(rows[0].number, "JS-002")
        self.assertTrue(rows[0].is_unique)

    def test_switching_to_multiple_removes_unique_sentinel_and_roundtrips(self):
        path = self._database()
        repo = self._repo(path)
        repo.save(7, AgreementState("unique", "UNIQUE", ()))
        multiple = (
            Agreement(None, 7, "PERIODE-A", dt.date(2026, 1, 1), dt.date(2026, 6, 30)),
            Agreement(None, 7, "PERIODE-B", dt.date(2026, 7, 1), dt.date(2026, 12, 31)),
        )
        repo.save(7, AgreementState("multiple", "", multiple))
        state = repo.load(7)
        self.assertEqual(state.mode, "multiple")
        self.assertEqual([row.number for row in state.multiple], ["PERIODE-A", "PERIODE-B"])
        self.assertTrue(all(not row.is_unique for row in state.multiple))

    def test_multiple_update_preserves_existing_id_and_deletes_removed_row(self):
        path = self._database()
        repo = self._repo(path)
        repo.save(
            7,
            AgreementState(
                "multiple",
                "",
                (
                    Agreement(None, 7, "A", dt.date(2026, 1, 1), dt.date(2026, 3, 31)),
                    Agreement(None, 7, "B", dt.date(2026, 4, 1), dt.date(2026, 6, 30)),
                ),
            ),
        )
        rows = repo.list_agreements(7)
        keep = rows[0]
        removed_id = rows[1].agreement_id
        repo.save(
            7,
            AgreementState(
                "multiple",
                "",
                (Agreement(keep.agreement_id, 7, "A modifié", keep.start_date, keep.end_date),),
            ),
        )
        rows = repo.list_agreements(7)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].agreement_id, keep.agreement_id)
        self.assertEqual(rows[0].number, "A modifié")
        self.assertNotEqual(rows[0].agreement_id, removed_id)

    def test_validations_match_historic_modes(self):
        path = self._database()
        repo = self._repo(path)
        with self.assertRaises(ValueError):
            repo.save(7, AgreementState("unique", "", ()))
        with self.assertRaises(ValueError):
            repo.save(7, AgreementState("multiple", "", ()))
        with self.assertRaises(ValueError):
            repo.save(
                7,
                AgreementState(
                    "multiple",
                    "",
                    (Agreement(None, 7, "", dt.date(2026, 1, 1), dt.date(2026, 12, 31)),),
                ),
            )

    def test_none_deletes_only_target_activity(self):
        path = self._database()
        repo = self._repo(path)
        repo.save(7, AgreementState("unique", "A7", ()))
        repo.save(7, AgreementState("none", "", ()))
        self.assertEqual(repo.list_agreements(7), [])
        connection = sqlite3.connect(path)
        try:
            row = connection.execute(
                "SELECT agrement FROM agrements WHERE IDactivite=8"
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(row, ("AUTRE-ACTIVITE",))

    def test_page_smoke_loads_multiple_agreements(self):
        path = self._database()
        repo = self._repo(path)
        repo.save(
            7,
            AgreementState(
                "multiple",
                "",
                (Agreement(None, 7, "JS-2026", dt.date(2026, 1, 1), dt.date(2026, 12, 31)),),
            ),
        )
        page = ActivityAgreementsPage(NativeActivityEditorRepository(path), 7)
        self.addCleanup(page.close)
        self.assertTrue(page.multiple_radio.isChecked())
        self.assertEqual(page.table.rowCount(), 1)
        self.assertEqual(page.table.item(0, 1).text(), "JS-2026")


if __name__ == "__main__":
    unittest.main()
