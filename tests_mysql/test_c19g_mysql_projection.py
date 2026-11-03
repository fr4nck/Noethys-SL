"""C19g: projection MySQL des noms/types historiques sur base 100% jetable."""
from __future__ import annotations

import unittest
from unittest.mock import patch
import os

from experimental.qt_c19g_schema_lab.schema_contract import (
    REQUIRED, declared_projection,
)
from experimental.qt_c19g_schema_lab.mysql_projection import (
    MARKER, DBNAME, _connect, _connection_options, _marker,
    create_empty_projection, reset_synthetic_rows,
    inspect_synthetic_prestations, SourceAudit,
)


class C19gMySQLProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        create_empty_projection()

    def setUp(self):
        reset_synthetic_rows()

    def query(self, sql, args=()):
        db = _connect()
        try:
            with db.cursor() as cur:
                _marker(cur)
                cur.execute(sql, args)
                return cur.fetchall()
        finally:
            db.close()

    def modify_fixture(self, sql, args=()):
        db = _connect()
        try:
            with db.cursor() as cur:
                _marker(cur)
                cur.execute(sql, args)
            db.commit()
        finally:
            db.close()

    def inspect(self, ids=(301, 302), family=100, payer=201):
        return inspect_synthetic_prestations(
            prestation_ids=ids, family_id=family, payer_id=payer,
        )

    def test_tables_match_only_partial_official_projection(self):
        actual = {row[0] for row in self.query("SHOW TABLES")}
        self.assertEqual(actual, set(REQUIRED) | {"c19g_marker"})
        self.assertEqual(DBNAME, "qt_c19g_lab")
        self.assertEqual(self.query(
            "SELECT magic FROM c19g_marker WHERE id=1"
        ), ((MARKER,),))

    def test_required_columns_and_float_types_are_mysql_compatible(self):
        projected = declared_projection()
        for table, fields in projected.items():
            observed = {row[0]: row[1].lower() for row in
                        self.query("SHOW COLUMNS FROM " + table)}
            for name, typ in fields:
                with self.subTest(table=table, column=name):
                    self.assertIn(name, observed)
                    expected = ("int" if typ.startswith("INTEGER")
                                else typ.lower().split("(")[0])
                    self.assertTrue(observed[name].startswith(expected))
        self.assertTrue(
            self.query("SHOW COLUMNS FROM prestations LIKE 'montant'")[0][1]
            .lower().startswith("float")
        )

    def test_account_and_family_checked_using_actual_ids(self):
        report = self.inspect(ids=(301,))
        self.assertEqual(report.lines[0].payer_id, 201)
        self.assertEqual(report.lines[0].family_id, 100)
        self.assertNotIn("FAMILLE_OU_PAYEUR_DIVERGENT", report.lines[0].alerts)
        self.assertFalse(report.executable)

    def test_shared_service_and_ventilation_are_not_multiplied(self):
        report = self.inspect(ids=(301,))
        self.assertEqual(len(report.lines), 1)
        row = report.lines[0]
        self.assertEqual(row.consumption_count, 2)
        self.assertEqual(row.ventilation_count, 1)
        self.assertIn("PRESTATION_PARTAGEE_NON_MULTIPLIABLE", row.alerts)
        self.assertIn("VENTILATION_PRESENTE", row.alerts)

    def test_uninvoiced_prestation_and_period_lock(self):
        report = self.inspect(ids=(302,))
        self.assertEqual(report.lines[0].activity_id, 2)
        self.assertIsNone(report.lines[0].invoice_id)
        self.assertIn("PERIODE_VERROUILLEE", report.lines[0].alerts)
        self.assertFalse(report.executable)

    def test_invoice_uses_actual_header_and_number(self):
        report = self.inspect(ids=(303,), family=101, payer=202)
        self.assertEqual(report.lines[0].invoice_id, 901)
        self.assertIn("DEJA_FACTUREE", report.lines[0].alerts)
        self.assertNotIn("FACTURE_ABSENTE_OU_COMPTE_DIVERGENT", report.lines[0].alerts)
        self.assertEqual(
            self.query("SELECT numero FROM factures WHERE IDfacture=901"),
            ((78001,),)
        )

    def test_cross_family_context_is_rejected_as_anomaly(self):
        report = self.inspect(ids=(303,), family=100, payer=201)
        self.assertIn("FAMILLE_OU_PAYEUR_DIVERGENT", report.lines[0].alerts)
        self.assertFalse(report.executable)

    def test_missing_invoice_header_detected(self):
        self.modify_fixture(
            "UPDATE prestations SET IDfacture=999 WHERE IDprestation=303"
        )
        report = self.inspect(ids=(303,), family=101, payer=202)
        self.assertIn(
            "FACTURE_ABSENTE_OU_COMPTE_DIVERGENT", report.lines[0].alerts
        )
        self.assertFalse(report.executable)

    def test_service_payer_is_compared_to_payer_family(self):
        self.modify_fixture(
            "UPDATE prestations SET IDcompte_payeur=202 WHERE IDprestation=301"
        )
        report = self.inspect(ids=(301,))
        self.assertIn(
            "RELATION_COMPTE_PAYEUR_INCOHERENTE", report.lines[0].alerts
        )

    def test_consumption_and_inscription_activity_mismatch(self):
        self.modify_fixture(
            "UPDATE consommations SET IDactivite=2 WHERE IDconso=1"
        )
        report = self.inspect(ids=(301,))
        self.assertIn(
            "CONSOMMATION_INSCRIPTION_DIVERGENTE", report.lines[0].alerts
        )

    def test_consumption_individual_mismatch(self):
        self.modify_fixture(
            "UPDATE consommations SET IDindividu=20 WHERE IDconso=1"
        )
        report = self.inspect(ids=(301,))
        self.assertIn(
            "CONSOMMATION_INSCRIPTION_DIVERGENTE", report.lines[0].alerts
        )

    def test_missing_service_cannot_be_silently_dropped(self):
        report = self.inspect(ids=(301, 999999))
        self.assertEqual(tuple(r.id for r in report.lines), (301, 999999))
        self.assertIn("PRESTATION_ABSENTE", report.lines[1].alerts)

    def test_numeric_float_is_not_an_exact_money_contract(self):
        row = self.inspect(ids=(301,)).lines[0]
        self.assertIsInstance(row.amount_float, float)
        self.assertTrue(any("FLOAT" in alert for alert in self.inspect().alerts))
        # Le source est FLOAT (binaire), pas un montant fixe DECIMAL.
        # Ne PAS comparer au texte exact de prix ni calculer une facture.
        self.assertFalse(self.inspect().executable)

    def test_read_only_transaction_rejects_insert(self):
        import pymysql
        db = _connect()
        try:
            with db.cursor() as cur:
                cur.execute("START TRANSACTION READ ONLY")
                _marker(cur)
                with self.assertRaises(pymysql.MySQLError):
                    cur.execute(
                        "INSERT INTO prestations(IDprestation) VALUES(987654)"
                    )
            db.rollback()
        finally:
            db.close()
        self.assertEqual(
            self.query("SELECT COUNT(*) FROM prestations WHERE IDprestation=987654"),
            ((0,),)
        )

    def test_wrong_marker_blocks_read(self):
        self.modify_fixture(
            "UPDATE c19g_marker SET magic='UNKNOWN' WHERE id=1"
        )
        try:
            with self.assertRaises(PermissionError):
                self.inspect(ids=(301,))
        finally:
            # Restauration du seul marqueur fictif via connexion deja
            # confinee au conteneur, sans exiger le marqueur invalide.
            db = _connect()
            try:
                with db.cursor() as cur:
                    cur.execute(
                        "UPDATE c19g_marker SET magic=%s WHERE id=1",
                        (MARKER,),
                    )
                db.commit()
            finally:
                db.close()

    def test_outside_environment_or_id_selection_denied(self):
        with patch.dict(os.environ, {"C19G_MYSQL_HOST": "SERVEURPMSL"}):
            with self.assertRaises(PermissionError):
                _connection_options()
        for ids in ((), (301, 301), (True,), ("301",), (0,), []):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                self.inspect(ids=ids)
        with self.assertRaises(ValueError):
            self.inspect(family=True)

    def test_projection_has_no_real_invoice_writer(self):
        import experimental.qt_c19g_schema_lab.mysql_projection as lab
        for name in ("facturer", "create_invoice", "commit_invoice", "send_invoice"):
            self.assertFalse(hasattr(lab, name))
        result = self.inspect(ids=(304,))
        self.assertIsInstance(result, SourceAudit)
        self.assertFalse(result.executable)


if __name__ == "__main__":
    unittest.main()
