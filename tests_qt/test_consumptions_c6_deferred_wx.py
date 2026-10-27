"""C6: comparaison du corps wx Sauvegarde sous commits historiques ou differes.

Strictement en tests_qt, sur bases C5 fictives, sans autre acces DB.
Cette preuve mecanique ne porte ni droits, ni facturation reelle.
"""
from __future__ import annotations

import datetime as dt
import importlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from noethys_qt.consumptions_preparation_core import SUPPORTED_STATES

# Ne pas importer une classe unittest.TestCase dans les globals du module :
# unittest discovery la rejouerait sous une deuxieme identite.
c5 = importlib.import_module("test_consumptions_c5_wx_execution")
ORIGINAL_DB_CLASS = c5.GuardedFixtureDb


class _DeferredFixtureDb(ORIGINAL_DB_CLASS):
    """Adapter de TEST uniquement: reporte tous les Commit/Close wx."""

    def __init__(self, filename, root, *, fail_on=None):
        super().__init__(filename, root, fail_on=fail_on)
        self.commit_requests = 0
        self.close_requests = 0
        self.finalized = False
        self.physical_commits = 0

    def Commit(self):
        self.commit_requests += 1

    def Close(self):
        self.close_requests += 1

    def ReqInsert(self, table, data, commit=True):
        identifier = super().ReqInsert(table, data, commit=commit)
        if self.fail_on == "after_memo_insert":
            raise c5.SimulatedFailure("Panne artificielle après mémo")
        return identifier

    def finalize(self, *, success: bool):
        if self.finalized:
            raise AssertionError("Double finalisation C6")
        self.finalized = True
        try:
            if success:
                self.con.commit()
                self.physical_commits += 1
            else:
                self.con.rollback()
        finally:
            ORIGINAL_DB_CLASS.Close(self)


class C6DeferredWxSaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c5.ActualWxSaveReplayTests.setUpClass()

    def setUp(self):
        self.fixture = self._fixture()

    def _fixture(self):
        item = c5.ActualWxSaveReplayTests(
            "test_actual_save_modifies_existing_consumption_and_history"
        )
        item.setUp()
        self.addCleanup(item.doCleanups)
        return item

    @staticmethod
    def _deferred(fixture, *, fail_on=None):
        with patch.object(c5, "GuardedFixtureDb", _DeferredFixtureDb):
            try:
                result = fixture._run_wx(fail_on=fail_on)
            except BaseException:
                if fixture.database is not None:
                    fixture.database.finalize(success=False)
                raise
            else:
                result.finalize(success=True)
                return result

    def test_success_rows_equal_between_original_and_single_commit(self):
        separate = self._fixture()
        self.fixture._run_wx()
        trial = self._deferred(separate)
        self.assertEqual(self.fixture._snapshot(), separate._snapshot())
        self.assertEqual(trial.commit_requests, 2)
        self.assertEqual(trial.physical_commits, 1)
        self.assertTrue(trial.closed)
        self.assertEqual(separate._snapshot()["consommations"][0][9], "present")
        self.assertEqual(len(separate._snapshot()["historique"]), 1)

    def test_prestation_update_and_ventilation_purge_match_wx(self):
        separate = self._fixture()
        for item in (self.fixture, separate):
            item.grid.listePrestationsModifiees = [101]
            item.grid.dictPrestations[101] = {
                "label": "Corrigée", "montant_initial": "13.00",
                "montant": "13.00", "forfait_date_debut": None,
                "forfait_date_fin": None, "code_compta": None,
                "code_produit_local": None, "tva": None,
            }
        self.fixture._run_wx()
        self._deferred(separate)
        self.assertEqual(self.fixture._snapshot(), separate._snapshot())
        self.assertEqual(separate._snapshot()["ventilation"], [])
        self.assertEqual(separate._snapshot()["prestations"][0][4], "Corrigée")

    def test_unchanged_row_generates_no_sql_writes(self):
        separate = self._fixture()
        for item in (self.fixture, separate):
            item.case.statut = None
            item.case.etat = "reservation"
        before = self.fixture._snapshot()
        regular = self.fixture._run_wx()
        trial = self._deferred(separate)
        self.assertEqual(regular.statements, [])
        self.assertEqual(trial.statements, [])
        self.assertEqual(self.fixture._snapshot(), before)
        self.assertEqual(separate._snapshot(), before)

    def test_history_failure_is_partial_in_original_but_atomic_in_trial(self):
        separate = self._fixture()
        before_regular = self.fixture._snapshot()
        before_trial = separate._snapshot()
        with self.assertRaises(c5.SimulatedFailure):
            self.fixture._run_wx(fail_on="history")
        with self.assertRaises(c5.SimulatedFailure):
            self._deferred(separate, fail_on="history")
        partial = self.fixture._snapshot()
        self.assertNotEqual(before_regular, partial)
        self.assertEqual(partial["consommations"][0][9], "present")
        self.assertEqual(partial["historique"], [])
        self.assertEqual(separate._snapshot(), before_trial)
        self.assertEqual(separate.database.commit_requests, 1)
        self.assertEqual(separate.database.physical_commits, 0)

    def test_precommit_sql_failure_also_rolls_back_all(self):
        before = self.fixture._snapshot()
        with self.assertRaises(c5.SimulatedFailure):
            self._deferred(self.fixture, fail_on="after_consumption_update")
        self.assertEqual(before, self.fixture._snapshot())
        self.assertEqual(self.fixture.database.physical_commits, 0)

    def test_memo_failure_rolls_back_already_changed_consumption(self):
        self.fixture.grid.dictMemos[(10, dt.date(2026, 10, 20))] = {
            "IDmemo": None, "texte": "memo synthétique",
            "couleur": "#aaaabb", "statut": "ajout",
        }
        before = self.fixture._snapshot()
        with self.assertRaises(c5.SimulatedFailure):
            self._deferred(self.fixture, fail_on="after_memo_insert")
        self.assertEqual(before, self.fixture._snapshot())
        self.assertEqual(self.fixture.database.commit_requests, 1)

    def test_memo_success_is_committed_with_history_and_consumption(self):
        self.fixture.grid.dictMemos[(10, dt.date(2026, 10, 20))] = {
            "IDmemo": None, "texte": "memo synthétique",
            "couleur": "#aaaabb", "statut": "ajout",
        }
        trial = self._deferred(self.fixture)
        final = self.fixture._snapshot()
        self.assertEqual(len(final["memo_journee"]), 1)
        self.assertEqual(len(final["historique"]), 1)
        self.assertEqual(final["consommations"][0][9], "present")
        self.assertEqual(trial.physical_commits, 1)

    def test_upstream_rights_and_period_checks_are_not_in_save_body(self):
        source = c5._method_source()
        self.assertNotIn("VerificationDroitsUtilisateurActuel", source)
        self.assertNotIn("gestion.Verification", source)
        self.assertEqual(
            SUPPORTED_STATES,
            frozenset(("reservation", "present", "absenti", "absentj", "attente", "refus")),
        )

    def test_deferred_test_adapter_is_absent_from_product_modules(self):
        folder = Path(__file__).resolve().parents[1] / "noethys_qt"
        for file in folder.glob("*.py"):
            with self.subTest(file=file.name):
                content = file.read_text(encoding="utf-8")
                self.assertNotIn("_DeferredFixtureDb", content)
                self.assertNotIn("test_consumptions_c6_deferred_wx", content)

    def test_external_path_stays_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            foreign = Path(directory) / "C5_SYNTHETIC.sqlite"
            with closing(sqlite3.connect(foreign)) as con:
                con.execute("CREATE TABLE sentinel (id INTEGER)")
                con.commit()
            with self.assertRaises(AssertionError):
                _DeferredFixtureDb(foreign, self.fixture.root)
            with closing(sqlite3.connect(foreign)) as con:
                self.assertEqual(
                    con.execute(
                        "SELECT name FROM sqlite_master WHERE name='sentinel'"
                    ).fetchone(), ("sentinel",),
                )


if __name__ == "__main__":
    unittest.main()
