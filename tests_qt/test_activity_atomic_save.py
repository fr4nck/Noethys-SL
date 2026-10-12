from __future__ import annotations

import datetime as dt
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from noethys_qt.activity_agreements import (
    ActivityAgreementsRepository,
    ActivityEditorDialog,
    AgreementState,
)
from noethys_qt.activity_editor import ActivityDetails, NativeActivityEditorRepository
from noethys_qt.activity_requirements import RequirementsState
from noethys_qt.activity_transaction import activity_transaction


class _Repository:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self):
        return sqlite3.connect(self.path), "?"


class _GroupPage:
    @staticmethod
    def group_count() -> int:
        return 1


class _PricingPage:
    @staticmethod
    def has_categories() -> bool:
        return True


class _RequirementsPage:
    def __init__(self, state: RequirementsState):
        self._collected = state
        self.state = None

    def collect(self) -> RequirementsState:
        return self._collected


class _AgreementsPage:
    def __init__(self, state: AgreementState):
        self._collected = state
        self.state = None

    def collect(self, *, confirm_delete: bool = True) -> AgreementState:
        return self._collected


class _EditorHarness:
    def __init__(self, repository: NativeActivityEditorRepository, details: ActivityDetails):
        self.repository = repository
        self.activity_id = details.activity_id
        self._details = details
        self.group_page = _GroupPage()
        self.pricing_page = _PricingPage()
        self.requirements_page = _RequirementsPage(
            RequirementsState(
                piece_ids=frozenset({10}),
                cotisation_required=True,
                cotisation_ids=frozenset({20}),
                vaccines_required=True,
                information_ids=frozenset({1}),
            )
        )
        self.agreements_page = _AgreementsPage(AgreementState("unique", "JS-2026", ()))
        self.details = None
        self.accepted = False

    def _validate_composed_editor(self) -> bool:
        return ActivityEditorDialog._validate_composed_editor(self)

    def _collect(self) -> ActivityDetails:
        return self._details

    @staticmethod
    def _checked_group_ids() -> list[int]:
        return [30]

    def accept(self) -> None:
        self.accepted = True


class ActivityTransactionTests(unittest.TestCase):
    def test_inner_commit_is_deferred_and_outer_rollback_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "transaction.sqlite"
            with closing(sqlite3.connect(path)) as connection:
                connection.execute("CREATE TABLE probe (value TEXT)")
                connection.commit()

            with self.assertRaises(RuntimeError):
                with activity_transaction(_Repository(path)) as shared:
                    connection, _placeholder = shared._connect()
                    connection.execute("INSERT INTO probe (value) VALUES ('x')")
                    connection.commit()
                    connection.close()
                    raise RuntimeError("boom")

            with closing(sqlite3.connect(path)) as connection:
                count = connection.execute("SELECT COUNT(*) FROM probe").fetchone()[0]
            self.assertEqual(count, 0)

    def test_final_editor_rolls_back_all_sections_when_agreements_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "activity.sqlite"
            self._create_schema(path)
            repository = NativeActivityEditorRepository(path)
            details = ActivityDetails(
                activity_id=1,
                name="Modifiée",
                short_name="MOD",
                coords_from_organizer=False,
                street="Rue test",
                postal_code="35000",
                city="Rennes",
                phone="",
                fax="",
                email="",
                website="",
                start_date=dt.date(2026, 1, 1),
                end_date=dt.date(2026, 12, 31),
                max_members=None,
                accounting_code="",
                regie_id=None,
                local_product_code="",
                multiple_registrations=False,
                service_code="",
                analytic_code="",
            )
            editor = _EditorHarness(repository, details)
            original_save = ActivityAgreementsRepository.save

            def fail_after_write(repo, activity_id, state):
                original_save(repo, activity_id, state)
                raise RuntimeError("échec agréments simulé")

            with patch.object(ActivityAgreementsRepository, "save", new=fail_after_write), patch(
                "noethys_qt.activity_agreements.QMessageBox.critical"
            ) as critical:
                ActivityEditorDialog._save(editor)

            self.assertFalse(editor.accepted)
            critical.assert_called_once()
            with closing(sqlite3.connect(path)) as connection:
                name = connection.execute("SELECT nom FROM activites WHERE IDactivite=1").fetchone()[0]
                groups = connection.execute("SELECT COUNT(*) FROM groupes_activites").fetchone()[0]
                pieces = connection.execute("SELECT COUNT(*) FROM pieces_activites").fetchone()[0]
                agreements = connection.execute("SELECT COUNT(*) FROM agrements").fetchone()[0]
                vaccines = connection.execute(
                    "SELECT vaccins_obligatoires FROM activites WHERE IDactivite=1"
                ).fetchone()[0]

            self.assertEqual(name, "Originale")
            self.assertEqual(groups, 0)
            self.assertEqual(pieces, 0)
            self.assertEqual(agreements, 0)
            self.assertEqual(vaccines, 0)

    @staticmethod
    def _create_schema(path: Path) -> None:
        with closing(sqlite3.connect(path)) as connection:
            connection.executescript(
                """
                CREATE TABLE activites (
                    IDactivite INTEGER PRIMARY KEY,
                    nom TEXT, abrege TEXT, coords_org INTEGER, rue TEXT, cp TEXT,
                    ville TEXT, tel TEXT, fax TEXT, mail TEXT, site TEXT,
                    date_debut TEXT, date_fin TEXT, nbre_inscrits_max INTEGER,
                    code_comptable TEXT, regie INTEGER, code_produit_local TEXT,
                    inscriptions_multiples INTEGER, code_service TEXT,
                    code_analytique TEXT, vaccins_obligatoires INTEGER
                );
                INSERT INTO activites (
                    IDactivite, nom, abrege, coords_org, vaccins_obligatoires
                ) VALUES (1, 'Originale', 'ORI', 1, 0);

                CREATE TABLE groupes_activites (
                    IDtype_groupe_activite INTEGER, IDactivite INTEGER
                );
                CREATE TABLE pieces_activites (
                    IDactivite INTEGER, IDtype_piece INTEGER
                );
                CREATE TABLE cotisations_activites (
                    IDactivite INTEGER, IDtype_cotisation INTEGER
                );
                CREATE TABLE renseignements_activites (
                    IDactivite INTEGER, IDtype_renseignement INTEGER
                );
                CREATE TABLE agrements (
                    IDagrement INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER, agrement TEXT, date_debut TEXT, date_fin TEXT
                );
                """
            )
            connection.commit()


if __name__ == "__main__":
    unittest.main()
