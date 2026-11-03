"""C19e : ORACLE EXPERIMENTAL de transaction sur SQLite :memory: seulement.

Toute la logique de transaction est dans ce fichier de test. Il ne
constitue PAS un moteur facturant, pas de driver production, pas de GUI,
pas de MySQL, pas de code reutilisable par le logiciel sans revue.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
import unittest
from decimal import Decimal


def _ids(values):
    if (
        type(values) is not tuple or not values
        or any(type(v) is not int or v <= 0 for v in values)
        or len(values) != len(set(values))
    ):
        raise ValueError("Selection non exhaustive ou invalide")
    return values


class TinyMemoryTransactionLab:
    """Demonstrateur synthetique volontairement non importable en production."""

    def __init__(self):
        self.db = sqlite3.connect(":memory:", isolation_level=None, timeout=1)
        if self.db.execute("PRAGMA database_list").fetchone()[2] != "":
            raise AssertionError("LAB : disque non autorise")
        self.db.executescript("""
            CREATE TABLE rights (
                actor INTEGER, activity INTEGER, action TEXT, allowed INTEGER,
                PRIMARY KEY(actor, activity, action)
            );
            CREATE TABLE periods (
                start TEXT, end TEXT, lock_prestations INTEGER,
                lock_invoices INTEGER
            );
            CREATE TABLE prestations (
                id INTEGER PRIMARY KEY, family INTEGER, payer INTEGER,
                activity INTEGER, date TEXT, amount TEXT,
                invoice_id INTEGER
            );
            CREATE TABLE invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idem TEXT NOT NULL UNIQUE, actor INTEGER NOT NULL,
                family INTEGER NOT NULL, payer INTEGER NOT NULL,
                fingerprint TEXT NOT NULL
            );
            CREATE TABLE invoice_lines (
                invoice_id INTEGER, prestation_id INTEGER UNIQUE
            );
            INSERT INTO rights VALUES
                (7,1,'facturation_factures/creer',1),
                (7,2,'facturation_factures/creer',1),
                (8,1,'facturation_factures/creer',0);
            INSERT INTO prestations VALUES
                (301,100,201,1,'2026-10-05','12.005',NULL),
                (302,100,201,2,'2026-10-06','-1.005',NULL),
                (303,101,202,2,'2026-10-07','18.50',NULL);
        """)

    def close(self):
        self.db.close()

    def apply(self, *, actor=7, family=100, payer=201,
              activities=(1, 2), prestations=(301, 302),
              key="in-memory-fictif-1", fail_after_header=False):
        _ids(activities)
        _ids(prestations)
        if type(actor) is not int or actor <= 0:
            raise ValueError("Auteur invalide")
        if type(family) is not int or family <= 0:
            raise ValueError("Famille invalide")
        if type(payer) is not int or payer <= 0:
            raise ValueError("Compte payeur invalide")
        if type(key) is not str or not key or len(key) > 80:
            raise ValueError("Cle idempotence invalide")
        fingerprint = repr((actor, family, payer, activities, prestations))
        self.db.execute("BEGIN IMMEDIATE")
        try:
            existing = self.db.execute(
                "SELECT id, fingerprint FROM invoices WHERE idem=?", (key,)
            ).fetchone()
            if existing is not None:
                if existing[1] != fingerprint:
                    raise PermissionError("Cle idempotente utilisee pour un autre perimetre")
                self.db.execute("COMMIT")
                return existing[0]

            for activity in activities:
                right = self.db.execute(
                    "SELECT allowed FROM rights "
                    "WHERE actor=? AND activity=? AND action=?",
                    (actor, activity, "facturation_factures/creer"),
                ).fetchone()
                if right != (1,):
                    raise PermissionError("Autorisation explicite absente sur activite")
            placeholders = ",".join("?" for _ in prestations)
            rows = self.db.execute(
                "SELECT id, family, payer, activity, date, amount, invoice_id "
                "FROM prestations WHERE id IN (" + placeholders + ")",
                prestations,
            ).fetchall()
            if len(rows) != len(prestations):
                raise ValueError("Prestation manquante")
            if {row[3] for row in rows} != set(activities):
                raise PermissionError("Périmètre des activités non exhaustif")
            for prest, fam, pay, activity, date, amount, invoice_id in rows:
                if fam != family or pay != payer or invoice_id is not None:
                    raise PermissionError("Famille, payeur ou facture incompatibles")
                if not Decimal(amount).is_finite():
                    raise ValueError("Montant brut invalide")
                closed = self.db.execute(
                    "SELECT 1 FROM periods WHERE start<=? AND end>=? "
                    "AND (lock_prestations=1 OR lock_invoices=1) LIMIT 1",
                    (date, date),
                ).fetchone()
                if closed is not None:
                    raise PermissionError("Période fermée")
            cur = self.db.execute(
                "INSERT INTO invoices (idem,actor,family,payer,fingerprint) "
                "VALUES (?,?,?,?,?)",
                (key, actor, family, payer, fingerprint),
            )
            iid = cur.lastrowid
            if fail_after_header:
                raise RuntimeError("Injection de panne apres en-tete fictif")
            for prest in prestations:
                updated = self.db.execute(
                    "UPDATE prestations SET invoice_id=? "
                    "WHERE id=? AND invoice_id IS NULL",
                    (iid, prest),
                )
                if updated.rowcount != 1:
                    raise RuntimeError("Concurrent ou deja facture")
                self.db.execute(
                    "INSERT INTO invoice_lines VALUES (?,?)", (iid, prest)
                )
            self.db.execute("COMMIT")
            return iid
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def counts(self):
        return (
            self.db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0],
            self.db.execute("SELECT COUNT(*) FROM invoice_lines").fetchone()[0],
            self.db.execute(
                "SELECT COUNT(*) FROM prestations WHERE invoice_id IS NOT NULL"
            ).fetchone()[0],
        )


class C19eInMemoryTransactionOracleTests(unittest.TestCase):
    def setUp(self):
        self.lab = TinyMemoryTransactionLab()
        self.addCleanup(self.lab.close)

    def test_idempotent_replay_is_exactly_once(self):
        first = self.lab.apply()
        second = self.lab.apply()
        self.assertEqual(first, second)
        self.assertEqual(self.lab.counts(), (1, 2, 2))

    def test_same_idempotency_key_cannot_change_scope(self):
        self.lab.apply()
        with self.assertRaises(PermissionError):
            self.lab.apply(prestations=(301,), activities=(1,))
        self.assertEqual(self.lab.counts(), (1, 2, 2))

    def test_new_key_cannot_bill_existing_service_again(self):
        self.lab.apply()
        with self.assertRaises(PermissionError):
            self.lab.apply(key="different-key")
        self.assertEqual(self.lab.counts(), (1, 2, 2))

    def test_missing_permission_is_denied_without_partial_write(self):
        with self.assertRaises(PermissionError):
            self.lab.apply(actor=8, activities=(1,), prestations=(301,))
        self.assertEqual(self.lab.counts(), (0, 0, 0))

    def test_multi_activity_requires_all_rights(self):
        self.lab.db.execute(
            "DELETE FROM rights WHERE activity=2 AND actor=7"
        )
        with self.assertRaises(PermissionError):
            self.lab.apply()
        self.assertEqual(self.lab.counts(), (0, 0, 0))

    def test_activity_selection_empty_or_duplicated(self):
        for activities in ((), (1, 1), (True,), ("1",)):
            with self.subTest(activities=activities), self.assertRaises(ValueError):
                self.lab.apply(activities=activities)
        self.assertEqual(self.lab.counts(), (0, 0, 0))

    def test_closed_period_boundary_inclusive(self):
        self.lab.db.execute(
            "INSERT INTO periods VALUES ('2026-10-05','2026-10-05',1,0)"
        )
        with self.assertRaises(PermissionError):
            self.lab.apply()
        self.assertEqual(self.lab.counts(), (0, 0, 0))

    def test_invoice_lock_also_blocks(self):
        self.lab.db.execute(
            "INSERT INTO periods VALUES ('2026-10-06','2026-10-06',0,1)"
        )
        with self.assertRaises(PermissionError):
            self.lab.apply()
        self.assertEqual(self.lab.counts(), (0, 0, 0))

    def test_error_after_header_rolls_back_header_and_lines(self):
        with self.assertRaises(RuntimeError):
            self.lab.apply(fail_after_header=True)
        self.assertEqual(self.lab.counts(), (0, 0, 0))
        self.assertIsNone(
            self.lab.db.execute(
                "SELECT invoice_id FROM prestations WHERE id=301"
            ).fetchone()[0]
        )

    def test_cross_family_service_rejected(self):
        with self.assertRaises(PermissionError):
            self.lab.apply(activities=(1, 2), prestations=(301, 303))
        self.assertEqual(self.lab.counts(), (0, 0, 0))

    def test_precision_and_negative_values_never_recomputed(self):
        old = tuple(self.lab.db.execute(
            "SELECT amount FROM prestations WHERE id IN (301,302) ORDER BY id"
        ))
        self.lab.apply()
        self.assertEqual(old, (("12.005",), ("-1.005",)))
        self.assertEqual(old, tuple(self.lab.db.execute(
            "SELECT amount FROM prestations WHERE id IN (301,302) ORDER BY id"
        )))
        self.assertEqual(self.lab.counts(), (1, 2, 2))

    def test_prestation_missing_leaves_no_invoice(self):
        with self.assertRaises(ValueError):
            self.lab.apply(prestations=(301, 999), activities=(1, 2))
        self.assertEqual(self.lab.counts(), (0, 0, 0))

    def test_malformed_actor_and_key_denied(self):
        for opts in ({"actor":True}, {"key":""}, {"payer":0}, {"family":-1}):
            with self.subTest(opts=opts), self.assertRaises(ValueError):
                self.lab.apply(**opts)
        self.assertEqual(self.lab.counts(), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
