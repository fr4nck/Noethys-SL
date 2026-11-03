"""C19f : MySQL 5.7 / 8.0 jetable, transactions et concurrence REELLE.

Lance UNIQUEMENT par la CI GitHub (runner Ubuntu, service MySQL docker
de test sur 127.0.0.1:33067, schema fixe qt_c19f_lab). Jamais Noethys.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import unittest
from unittest.mock import patch

from experimental.qt_c19f_mysql_lab.transaction_lab import (
    Intent, Refused, InjectedFailure, MARKER, SCHEMA, ACTION,
    _connection_options, connect,
    create_disposable_schema_for_tests,
    reset_fictive_data_for_tests,
    simulate_transaction,
)


def intention(*, actor=7, session="fake-session-7", family=100, payer=201,
             activities=(1, 2), prestations=(301, 302),
             key="c19f-unique-key"):
    return Intent(actor, session, family, payer, activities, prestations, key)


def _multiprocess_worker(start_gate, output, key):
    # Processus DISTINCT, aucune connexion SQL partagee.
    if not start_gate.wait(8):
        output.put(("error", "gate-timeout"))
        return
    try:
        result = simulate_transaction(intention(key=key))
    except Exception as exc:
        output.put(("error", type(exc).__name__))
    else:
        output.put(("ok", result))


class C19fMySQLTransactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Une base non vide / non jetable => refuser et ne rien supprimer.
        create_disposable_schema_for_tests()

    def setUp(self):
        reset_fictive_data_for_tests()

    def query(self, sql, args=()):
        db = connect()
        try:
            with db.cursor() as cur:
                cur.execute("SELECT magic FROM c19f_marker WHERE id=1")
                self.assertEqual(cur.fetchone(), (MARKER,))
                cur.execute(sql, args)
                return cur.fetchall()
        finally:
            db.close()

    def exec_sql(self, sql, args=()):
        db = connect()
        try:
            with db.cursor() as cur:
                cur.execute("SELECT magic FROM c19f_marker WHERE id=1")
                self.assertEqual(cur.fetchone(), (MARKER,))
                cur.execute(sql, args)
            db.commit()
        finally:
            db.close()

    def counts(self):
        return tuple(
            self.query("SELECT COUNT(*) FROM " + table)[0][0]
            for table in ("c19f_invoices", "c19f_invoice_lines")
        ) + (
            self.query(
                "SELECT COUNT(*) FROM c19f_prestations "
                "WHERE invoice_id IS NOT NULL"
            )[0][0],
        )

    def test_guard_rejects_external_host_before_network(self):
        with patch.dict(os.environ, {"C19F_MYSQL_HOST": "SERVEURPMSL"}):
            with self.assertRaises(PermissionError):
                _connection_options()
        with patch.dict(os.environ, {"C19F_MYSQL_DATABASE": "production"}):
            with self.assertRaises(PermissionError):
                _connection_options()
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaises(PermissionError):
                _connection_options()

    def test_only_synthetic_tables_exist(self):
        tables = self.query("SHOW TABLES")
        self.assertGreaterEqual(len(tables), 8)
        self.assertTrue(all(row[0].startswith("c19f_") for row in tables))
        self.assertEqual(SCHEMA, "qt_c19f_lab")

    def test_happy_path_is_still_only_a_synthetic_invoice(self):
        first = simulate_transaction(intention())
        self.assertGreater(first, 0)
        self.assertEqual(self.counts(), (1, 2, 2))
        rows = self.query(
            "SELECT idempotency_key, family_id, payer_id "
            "FROM c19f_invoices WHERE id=%s", (first,)
        )
        self.assertEqual(rows, (("c19f-unique-key", 100, 201),))

    def test_same_key_and_same_scope_is_idempotent(self):
        first = simulate_transaction(intention())
        second = simulate_transaction(intention())
        self.assertEqual(first, second)
        self.assertEqual(self.counts(), (1, 2, 2))

    def test_same_key_with_changed_prestation_is_rejected(self):
        simulate_transaction(intention())
        with self.assertRaisesRegex(Refused, "autre perimetre"):
            simulate_transaction(intention(
                activities=(1,), prestations=(301,)
            ))
        self.assertEqual(self.counts(), (1, 2, 2))

    def test_new_key_cannot_reinvoice_same_service(self):
        simulate_transaction(intention())
        with self.assertRaisesRegex(Refused, "deja attribuee"):
            simulate_transaction(intention(key="another-c19f-key"))
        self.assertEqual(self.counts(), (1, 2, 2))

    def test_wrong_session_actor_denied(self):
        with self.assertRaisesRegex(Refused, "session"):
            simulate_transaction(intention(actor=8))
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_session_revocation_is_checked_inside_transaction(self):
        self.exec_sql(
            "UPDATE c19f_sessions SET revoked=1 WHERE actor=7"
        )
        with self.assertRaisesRegex(Refused, "session"):
            simulate_transaction(intention())
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_expired_session_denied(self):
        self.exec_sql(
            "UPDATE c19f_sessions SET expires='2001-01-01 00:00:00' "
            "WHERE actor=7"
        )
        with self.assertRaisesRegex(Refused, "expiree"):
            simulate_transaction(intention())
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_missing_single_activity_right_denies_all(self):
        self.exec_sql(
            "DELETE FROM c19f_rights WHERE actor=7 AND activity=2"
        )
        with self.assertRaisesRegex(Refused, "toutes les activites"):
            simulate_transaction(intention())
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_explicit_forbidden_right_denies_all(self):
        self.exec_sql(
            "UPDATE c19f_rights SET allowed=0 WHERE actor=7 AND activity=2"
        )
        with self.assertRaises(Refused):
            simulate_transaction(intention())
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_inclusive_prestation_lock_on_start_date(self):
        self.exec_sql(
            "INSERT INTO c19f_periods "
            "(start_day,end_day,lock_prestations,lock_invoices) "
            "VALUES ('2026-10-05','2026-10-05',1,0)"
        )
        with self.assertRaisesRegex(Refused, "periode verrouillee"):
            simulate_transaction(intention())
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_inclusive_invoice_lock_on_end_date(self):
        self.exec_sql(
            "INSERT INTO c19f_periods "
            "(start_day,end_day,lock_prestations,lock_invoices) "
            "VALUES ('2026-10-04','2026-10-06',0,1)"
        )
        with self.assertRaises(Refused):
            simulate_transaction(intention())
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_empty_duplicate_malformed_scopes_rejected(self):
        for fields in (
            {"activities": ()}, {"activities": (1, 1)},
            {"activities": (True,)}, {"activities": ("1",)},
            {"prestations": ()}, {"prestations": (301, 301)},
            {"prestations": (0,)}, {"prestations": (True,)},
            {"actor": True}, {"family": 0}, {"key": ""},
        ):
            with self.subTest(fields=fields), self.assertRaises(Refused):
                simulate_transaction(intention(**fields))
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_activity_scope_not_equal_to_lines_denied(self):
        with self.assertRaisesRegex(Refused, "non exhaustives"):
            simulate_transaction(intention(
                activities=(1,), prestations=(301, 302),
            ))
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_missing_prestation_denied(self):
        with self.assertRaisesRegex(Refused, "absente"):
            simulate_transaction(intention(prestations=(301, 99999)))
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_other_family_and_payer_denied(self):
        with self.assertRaises(Refused):
            simulate_transaction(intention(prestations=(301, 303)))
        with self.assertRaises(Refused):
            simulate_transaction(intention(payer=202))
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_invalid_amount_denied_before_header(self):
        self.exec_sql(
            "UPDATE c19f_prestations SET raw_amount='NaN' WHERE id=301"
        )
        with self.assertRaisesRegex(Refused, "montant"):
            simulate_transaction(intention())
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_rollback_after_header(self):
        with self.assertRaises(InjectedFailure):
            simulate_transaction(
                intention(), inject_failure="after_header"
            )
        self.assertEqual(self.counts(), (0, 0, 0))
        self.assertGreater(simulate_transaction(intention()), 0)

    def test_rollback_after_first_link(self):
        with self.assertRaises(InjectedFailure):
            simulate_transaction(
                intention(), inject_failure="after_first_line"
            )
        self.assertEqual(self.counts(), (0, 0, 0))
        self.assertTrue(all(
            row[0] is None
            for row in self.query(
                "SELECT invoice_id FROM c19f_prestations "
                "WHERE id IN (301,302)"
            )
        ))

    def test_exact_raw_amounts_preserved(self):
        before = self.query(
            "SELECT raw_amount FROM c19f_prestations "
            "WHERE id IN (301,302,304) ORDER BY id"
        )
        self.assertEqual(
            before, (("12.005",), ("-1.005",), ("1000.0003",))
        )
        simulate_transaction(intention())
        after = self.query(
            "SELECT raw_amount FROM c19f_prestations "
            "WHERE id IN (301,302,304) ORDER BY id"
        )
        self.assertEqual(after, before)

    def test_marker_change_rejected_before_facture(self):
        self.exec_sql(
            "UPDATE c19f_marker SET magic=%s WHERE id=1",
            ("BAD_MARKER",),
        )
        try:
            with self.assertRaises(PermissionError):
                simulate_transaction(intention())
        finally:
            db = connect()
            try:
                with db.cursor() as cur:
                    cur.execute(
                        "UPDATE c19f_marker SET magic=%s WHERE id=1",
                        (MARKER,),
                    )
                db.commit()
            finally:
                db.close()
        self.assertEqual(self.counts(), (0, 0, 0))

    def _racing(self, *, same_key):
        ctx = mp.get_context("spawn")
        gate = ctx.Event()
        queue = ctx.Queue()
        keys = ("same-key", "same-key") if same_key else (
            "different-key-a", "different-key-b"
        )
        processes = [
            ctx.Process(
                target=_multiprocess_worker,
                args=(gate, queue, key),
            )
            for key in keys
        ]
        for process in processes:
            process.start()
        try:
            gate.set()
            results = [queue.get(timeout=18) for _ in processes]
        finally:
            for process in processes:
                process.join(15)
                if process.is_alive():
                    process.terminate()
                    process.join(5)
        self.assertTrue(all(p.exitcode == 0 for p in processes))
        return results

    def test_two_processes_same_key_get_same_invoice(self):
        results = self._racing(same_key=True)
        self.assertEqual([status for status, _ in results], ["ok", "ok"])
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(self.counts(), (1, 2, 2))

    def test_two_processes_different_keys_only_one_succeeds(self):
        results = self._racing(same_key=False)
        self.assertEqual(
            sorted(status for status, _ in results),
            ["error", "ok"],
        )
        self.assertIn(("error", "Refused"), results)
        self.assertEqual(self.counts(), (1, 2, 2))


if __name__ == "__main__":
    unittest.main()
