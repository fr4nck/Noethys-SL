"""Qt C4: mécanique transactionnelle EXCLUSIVEMENT sur SQLite fictif jetable.

Pas d'import dans le produit Qt, pas de chemin externe, pas de règles
de facturation réelles. Les tables lab_* ne sont PAS le schéma Noethys.
"""
from __future__ import annotations

import inspect
import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from noethys_qt.consumptions_preparation_core import (
    FINANCIAL_FAMILY, SUPPORTED_STATES,
)

MARKER = "NOETHYS_C4_SYNTHETIC_ONLY_NOT_FOR_REAL_RECORDS"
TABLES = (
    "lab_consumptions", "lab_prestations", "lab_deductions",
    "lab_ventilation", "lab_historique",
)
STAGES = ("consommation", "prestation", "deduction", "ventilation", "historique")


class FixtureRejected(RuntimeError):
    """Protection fictive refusant la simulation."""


class InjectedCrash(RuntimeError):
    """Interruption synthétique au milieu de la transaction."""


@dataclass(frozen=True)
class MechanicalProof:
    before: tuple
    during: tuple
    after: tuple
    committed: bool

    @property
    def atomic(self):
        return self.after == (self.during if self.committed else self.before)


class DisposableConsumptionLab:
    """Une nouvelle base jetable par instance. Aucun paramètre de chemin/connexion."""

    def __init__(self):
        self._temp = tempfile.TemporaryDirectory(prefix="c4-fictif-noethys-")
        self._root = Path(self._temp.name).resolve()
        self.path = self._root / "C4_SYNTHETIC.sqlite"
        self._backup = self._root / "C4_BACKUP.sqlite"
        self._make_fixture()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def close(self):
        self._temp.cleanup()

    def _guard(self, file, *, is_backup=False):
        expected = self._root / ("C4_BACKUP.sqlite" if is_backup else "C4_SYNTHETIC.sqlite")
        if (
            not isinstance(file, Path) or file != expected
            or file.is_symlink() or file.resolve() != expected
            or file.parent.resolve() != self._root or not file.is_file()
        ):
            raise FixtureRejected("Accès à une base non jetable interdit.")

    def _check(self, con, *, is_backup=False):
        dbs = con.execute("PRAGMA database_list").fetchall()
        expected = self._root / ("C4_BACKUP.sqlite" if is_backup else "C4_SYNTHETIC.sqlite")
        if len(dbs) != 1 or dbs[0][1] != "main" or Path(dbs[0][2]).resolve() != expected:
            raise FixtureRejected("Connexion extérieure ou base attachée interdite.")
        if con.execute("SELECT token FROM lab_marker").fetchone() != (MARKER,):
            raise FixtureRejected("Marqueur synthétique absent.")

    def _open(self):
        self._guard(self.path)
        con = sqlite3.connect(self.path, isolation_level=None, timeout=2)
        try:
            con.execute("PRAGMA foreign_keys=ON")
            self._check(con)
            return con
        except BaseException:
            con.close()
            raise

    def _make_fixture(self):
        # Seul cet endroit crée une base, chemin produit par TemporaryDirectory.
        with closing(sqlite3.connect(self.path)) as con:
            con.executescript("""
                PRAGMA foreign_keys=ON;
                CREATE TABLE lab_marker (token TEXT PRIMARY KEY);
                CREATE TABLE lab_consumptions (
                    IDconso INTEGER PRIMARY KEY,
                    etat TEXT NOT NULL, IDinscription INTEGER, IDprestation INTEGER,
                    verrouillage INTEGER NOT NULL DEFAULT 0, forfait INTEGER,
                    period_open INTEGER NOT NULL DEFAULT 1,
                    permission_ok INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE lab_prestations (
                    IDprestation INTEGER PRIMARY KEY, IDfacture INTEGER,
                    lab_touches INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE lab_deductions (
                    IDdeduction INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDprestation INTEGER NOT NULL, lab_note TEXT NOT NULL,
                    FOREIGN KEY (IDprestation) REFERENCES lab_prestations (IDprestation)
                );
                CREATE TABLE lab_ventilation (
                    IDventilation INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDprestation INTEGER NOT NULL, amount_text TEXT NOT NULL,
                    lab_note TEXT NOT NULL,
                    FOREIGN KEY (IDprestation) REFERENCES lab_prestations (IDprestation)
                );
                CREATE TABLE lab_historique (
                    IDaction INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDconso INTEGER NOT NULL, lab_action TEXT NOT NULL,
                    FOREIGN KEY (IDconso) REFERENCES lab_consumptions (IDconso)
                );
                INSERT INTO lab_prestations VALUES (101, NULL, 0);
                INSERT INTO lab_prestations VALUES (104, 900, 0);
                INSERT INTO lab_prestations VALUES (105, NULL, 0);
                INSERT INTO lab_prestations VALUES (108, NULL, 0);
                INSERT INTO lab_ventilation (IDprestation, amount_text, lab_note)
                VALUES (105, '0.00', 'ventilation fictive initiale');
                INSERT INTO lab_consumptions
                  (IDconso, etat, IDinscription, IDprestation,
                   verrouillage, forfait, period_open, permission_ok)
                VALUES
                  (1, 'reservation', 77, 101, 0, NULL, 1, 1),
                  (2, 'present', 77, 101, 1, NULL, 1, 1),
                  (3, 'reservation', 77, 101, 0, 2, 1, 1),
                  (4, 'reservation', 77, 104, 0, NULL, 1, 1),
                  (5, 'reservation', 77, 105, 0, NULL, 1, 1),
                  (6, 'reservation', 77, 101, 0, NULL, 0, 1),
                  (7, 'reservation', 77, 101, 0, NULL, 1, 0),
                  (8, 'attente', 77, 108, 0, NULL, 1, 1),
                  (9, 'absentj', 77, 101, 0, NULL, 1, 1),
                  (10, 'reservation', NULL, 101, 0, NULL, 1, 1),
                  (11, 'reservation', 77, 999, 0, NULL, 1, 1),
                  (12, 'inconnu', 77, 101, 0, NULL, 1, 1),
                  (13, 'reservation', 77, NULL, 0, NULL, 1, 1);
            """)
            con.execute("INSERT INTO lab_marker VALUES (?)", (MARKER,))
            con.commit()

    @staticmethod
    def _snapshot(con):
        return tuple(
            (table, tuple(con.execute(
                "SELECT * FROM " + table + " ORDER BY rowid"
            ).fetchall()))
            for table in TABLES
        )

    def snapshot(self):
        with closing(self._open()) as con:
            return self._snapshot(con)

    def _precheck(self, con, ident, source, target):
        # Doublures artificielles, PAS les contrôles réels de l'application.
        if source not in SUPPORTED_STATES or target not in SUPPORTED_STATES:
            raise FixtureRejected("État historique non reconnu.")
        if target == source:
            raise FixtureRejected("Aucun changement à appliquer.")
        row = con.execute(
            "SELECT etat, IDinscription, IDprestation, verrouillage, forfait, "
            "period_open, permission_ok FROM lab_consumptions WHERE IDconso=?",
            (ident,),
        ).fetchone()
        if row is None or row[0] != source:
            raise FixtureRejected("Consommation supprimée ou sélection périmée.")
        state, inscription, prestation, locked, forfait, period, permission = row
        if locked:
            raise FixtureRejected("Verrouillage.")
        if forfait not in (None, 0):
            raise FixtureRejected("Forfait non qualifié.")
        if period != 1:
            raise FixtureRejected("Période fermée dans la fixture.")
        if permission != 1:
            raise FixtureRejected("Droits refusés dans la fixture.")
        if inscription is None or prestation is None:
            raise FixtureRejected("Inscription ou prestation absente.")
        bill = con.execute(
            "SELECT IDfacture FROM lab_prestations WHERE IDprestation=?",
            (prestation,),
        ).fetchone()
        if bill is None or bill[0] is not None:
            raise FixtureRejected("Prestation orpheline ou facturée.")
        linked = con.execute(
            "SELECT COUNT(*) FROM lab_ventilation WHERE IDprestation=?",
            (prestation,),
        ).fetchone()[0]
        if linked:
            raise FixtureRejected("Ventilation existante, même à montant nul.")
        if (state in FINANCIAL_FAMILY) != (target in FINANCIAL_FAMILY):
            raise FixtureRejected("Frontière tarifante non raccordée.")
        return prestation

    def simulate(
        self, ident: int, source: str, target: str, *,
        fail_after: str | None = None, rollback_only: bool = False,
    ) -> MechanicalProof:
        """Marqueurs artificiels dans 5 tables, jamais une sauvegarde Noethys."""
        if fail_after is not None and fail_after not in STAGES:
            raise ValueError("Étape de panne non reconnue.")
        before = self.snapshot()
        con = self._open()
        try:
            con.execute("BEGIN IMMEDIATE")
            prestation = self._precheck(con, ident, source, target)

            def inject(stage):
                if stage == fail_after:
                    raise InjectedCrash("Panne artificielle après " + stage)

            changed = con.execute(
                "UPDATE lab_consumptions SET etat=? WHERE IDconso=? AND etat=?",
                (target, ident, source),
            )
            if changed.rowcount != 1:
                raise FixtureRejected("Changement concurrent.")
            inject("consommation")

            changed = con.execute(
                "UPDATE lab_prestations SET lab_touches=lab_touches+1 "
                "WHERE IDprestation=?", (prestation,),
            )
            if changed.rowcount != 1:
                raise FixtureRejected("Prestation absente.")
            inject("prestation")

            con.execute(
                "INSERT INTO lab_deductions (IDprestation, lab_note) VALUES (?,?)",
                (prestation, "MARQUEUR NON FINANCIER"),
            )
            inject("deduction")

            con.execute(
                "INSERT INTO lab_ventilation "
                "(IDprestation, amount_text, lab_note) VALUES (?,?,?)",
                (prestation, "0.00", "MARQUEUR SANS REGLEMENT"),
            )
            inject("ventilation")

            con.execute(
                "INSERT INTO lab_historique (IDconso, lab_action) VALUES (?,?)",
                (ident, "SIMULATION " + source + " -> " + target),
            )
            inject("historique")

            during = self._snapshot(con)
            if rollback_only:
                con.rollback()
            else:
                con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()
        return MechanicalProof(before, during, self.snapshot(), not rollback_only)

    def backup(self):
        self._guard(self.path)
        expected = self._root / "C4_BACKUP.sqlite"
        if self._backup != expected or self._backup.exists():
            raise FixtureRejected("Sauvegarde externe ou répétée interdite.")
        with closing(self._open()) as source:
            with closing(sqlite3.connect(self._backup)) as destination:
                source.backup(destination)
                self._check(destination, is_backup=True)

    def restore(self):
        self._guard(self.path)
        self._guard(self._backup, is_backup=True)
        with closing(sqlite3.connect(self._backup)) as source:
            self._check(source, is_backup=True)
            with closing(self._open()) as dest:
                source.backup(dest)
                self._check(dest)


class C4SyntheticTests(unittest.TestCase):
    def setUp(self):
        self.lab = DisposableConsumptionLab()
        self.addCleanup(self.lab.close)

    def test_atomic_commit_changes_five_tables(self):
        proof = self.lab.simulate(1, "reservation", "present")
        self.assertTrue(proof.committed)
        self.assertTrue(proof.atomic)
        for name in TABLES:
            with self.subTest(table=name):
                self.assertNotEqual(dict(proof.before)[name], dict(proof.after)[name])
        self.assertEqual(dict(proof.after)["lab_consumptions"][0][1], "present")

    def test_explicit_rollback_reverts_all_changes(self):
        result = self.lab.simulate(1, "reservation", "present", rollback_only=True)
        self.assertFalse(result.committed)
        self.assertTrue(result.atomic)
        self.assertNotEqual(result.before, result.during)
        self.assertEqual(result.before, result.after)

    def test_injected_exception_at_each_stage_restores_all_tables(self):
        for stage in STAGES:
            with self.subTest(stage=stage), DisposableConsumptionLab() as lab:
                initial = lab.snapshot()
                with self.assertRaises(InjectedCrash):
                    lab.simulate(1, "reservation", "present", fail_after=stage)
                self.assertEqual(initial, lab.snapshot())
                self.assertTrue(lab.simulate(1, "reservation", "present").atomic)

    def test_sqlite_trigger_exception_rolls_back_all(self):
        with closing(self.lab._open()) as con:
            con.execute("""
                CREATE TRIGGER fail_history BEFORE INSERT ON lab_historique
                BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END
            """)
        initial = self.lab.snapshot()
        with self.assertRaises(sqlite3.IntegrityError):
            self.lab.simulate(1, "reservation", "present")
        self.assertEqual(initial, self.lab.snapshot())

    def test_lock_forfait_invoice_and_ventilation_block_simulation(self):
        for ident, source, target in (
            (2, "present", "absenti"), (3, "reservation", "present"),
            (4, "reservation", "present"), (5, "reservation", "present"),
        ):
            with self.subTest(ident=ident):
                original = self.lab.snapshot()
                with self.assertRaises(FixtureRejected):
                    self.lab.simulate(ident, source, target)
                self.assertEqual(original, self.lab.snapshot())

    def test_period_permission_boundary_and_orphans_fail_closed(self):
        for ident, source, target in (
            (6, "reservation", "present"), (7, "reservation", "present"),
            (8, "attente", "present"), (1, "reservation", "absentj"),
            (10, "reservation", "present"), (11, "reservation", "present"),
            (12, "inconnu", "present"), (13, "reservation", "present"),
        ):
            with self.subTest(ident=ident), self.assertRaises(FixtureRejected):
                self.lab.simulate(ident, source, target)

    def test_same_nonfinancial_group_is_only_a_mock(self):
        result = self.lab.simulate(9, "absentj", "refus")
        self.assertTrue(result.atomic)
        self.assertIn("SIMULATION absentj -> refus", str(result.after))

    def test_replay_stale_and_missing_record_all_rejected(self):
        self.lab.simulate(1, "reservation", "present")
        stable = self.lab.snapshot()
        for ident, source, target in (
            (1, "reservation", "absenti"), (1, "present", "present"),
            (999, "reservation", "present"),
        ):
            with self.subTest(ident=ident), self.assertRaises(FixtureRejected):
                self.lab.simulate(ident, source, target)
            self.assertEqual(stable, self.lab.snapshot())

    def test_unknown_injected_stage_never_writes(self):
        initial = self.lab.snapshot()
        with self.assertRaises(ValueError):
            self.lab.simulate(1, "reservation", "present", fail_after="oops")
        self.assertEqual(initial, self.lab.snapshot())

    def test_backup_and_restore_after_success_and_crash(self):
        initial = self.lab.snapshot()
        self.lab.backup()
        with self.assertRaises(InjectedCrash):
            self.lab.simulate(1, "reservation", "present", fail_after="historique")
        self.assertEqual(initial, self.lab.snapshot())
        self.lab.simulate(1, "reservation", "present")
        self.assertNotEqual(initial, self.lab.snapshot())
        self.lab.restore()
        self.assertEqual(initial, self.lab.snapshot())

    def test_backup_is_non_overwriting(self):
        self.lab.backup()
        with self.assertRaises(FixtureRejected):
            self.lab.backup()

    def test_external_file_cannot_be_opened_even_if_path_reassigned(self):
        original = self.lab.path
        with tempfile.TemporaryDirectory() as outside:
            foreign = Path(outside) / "other.sqlite"
            with closing(sqlite3.connect(foreign)) as con:
                con.execute("CREATE TABLE sentinel (v INTEGER)")
                con.commit()
            self.lab.path = foreign
            try:
                with self.assertRaises(FixtureRejected):
                    self.lab.simulate(1, "reservation", "present")
                with self.assertRaises(FixtureRejected):
                    self.lab.backup()
                with closing(sqlite3.connect(foreign)) as con:
                    self.assertIsNotNone(
                        con.execute("SELECT name FROM sqlite_master WHERE name='sentinel'").fetchone()
                    )
            finally:
                self.lab.path = original

    def test_restore_refuses_foreign_backup_file(self):
        original = self.lab._backup
        with tempfile.TemporaryDirectory() as outside:
            foreign = Path(outside) / "foreign.sqlite"
            with closing(sqlite3.connect(foreign)) as con:
                con.execute("CREATE TABLE sentinel (v INTEGER)")
                con.commit()
            self.lab._backup = foreign
            try:
                with self.assertRaises(FixtureRejected):
                    self.lab.restore()
            finally:
                self.lab._backup = original

    def test_two_separate_commits_cannot_rollback_first_phase(self):
        """Démonstration du risque générique de commit intermédiaire."""
        original = self.lab.snapshot()
        with closing(self.lab._open()) as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute("UPDATE lab_consumptions SET etat='present' WHERE IDconso=1")
            con.commit()
            con.execute("BEGIN IMMEDIATE")
            con.execute("UPDATE lab_prestations SET lab_touches=5 WHERE IDprestation=101")
            con.rollback()
        after = self.lab.snapshot()
        self.assertNotEqual(original, after)
        self.assertEqual(dict(after)["lab_consumptions"][0][1], "present")
        self.assertEqual(dict(after)["lab_prestations"][0][2], 0)

    def test_lab_cannot_be_instantiated_with_any_database_path(self):
        self.assertEqual(list(inspect.signature(DisposableConsumptionLab).parameters), [])
        root = Path(__file__).resolve().parents[1] / "noethys_qt"
        for path in root.glob("*.py"):
            with self.subTest(module=path.name):
                self.assertNotIn(
                    "DisposableConsumptionLab",
                    path.read_text(encoding="utf-8"),
                )


if __name__ == "__main__":
    unittest.main()
