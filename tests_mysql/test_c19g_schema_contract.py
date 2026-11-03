"""C19g : verifier la projection du vrai dictionnaire DATA_Tables sans import."""
from __future__ import annotations

import ast
from pathlib import Path
import tempfile
import unittest

from experimental.qt_c19g_schema_lab.schema_contract import (
    REQUIRED, SOURCE, declared_projection, extract_table_declarations,
    projection_ddl, limitations,
)


class C19gStaticSchemaContractTests(unittest.TestCase):
    def test_official_declaration_loaded_without_import(self):
        self.assertTrue(SOURCE.is_file())
        declarations = extract_table_declarations()
        self.assertIn("prestations", declarations)
        self.assertIn("factures", declarations)
        self.assertGreater(len(declarations), 40)

    def test_exact_seven_tables_derived_not_invented(self):
        projection = declared_projection()
        self.assertEqual(set(projection), set(REQUIRED))
        for table, fields in projection.items():
            self.assertEqual({name for name, _ in fields}, set(REQUIRED[table]))
            self.assertEqual(len(fields), len(REQUIRED[table]))

    def test_invoice_and_service_have_distinct_id_and_payer(self):
        fields = {key: dict(cols) for key, cols in declared_projection().items()}
        self.assertIn("IDfacture", fields["prestations"])
        self.assertIn("IDfacture", fields["factures"])
        self.assertIn("IDcompte_payeur", fields["factures"])
        self.assertIn("IDcompte_payeur", fields["prestations"])
        self.assertIn("IDfamille", fields["comptes_payeurs"])

    def test_prestation_activity_is_direct_not_inferred_from_consumption(self):
        fields = dict(declared_projection()["prestations"])
        self.assertEqual(fields["IDactivite"], "INTEGER")
        self.assertEqual(dict(declared_projection()["consommations"])["IDprestation"],
                         "INTEGER")

    def test_types_document_the_real_float_limit(self):
        projected = {key: dict(cols) for key, cols in declared_projection().items()}
        for table, column in (
            ("prestations", "montant"),
            ("factures", "total"), ("factures", "regle"),
            ("factures", "solde"), ("ventilation", "montant"),
        ):
            self.assertEqual(projected[table][column], "FLOAT")
        self.assertTrue(any("FLOAT" in value for value in limitations()))
        # Les montants FLOAT sont les types source, pas des DECIMAL exacts.
        self.assertNotIn("DECIMAL", "".join(projection_ddl()))

    def test_mysql_ddl_projection_maps_only_known_types(self):
        ddls = projection_ddl()
        self.assertEqual(len(ddls), 7)
        for sql in ddls:
            self.assertTrue(sql.startswith("CREATE TABLE "))
            self.assertTrue(sql.endswith("ENGINE=InnoDB"))
            self.assertIn("AUTO_INCREMENT PRIMARY KEY", sql)
            self.assertNotIn("FOREIGN KEY", sql)

    def test_date_and_verrou_fields_are_from_source(self):
        dates = dict(declared_projection()["periodes_gestion"])
        self.assertEqual(dates["date_debut"], "DATE")
        self.assertEqual(dates["date_fin"], "DATE")
        self.assertEqual(dates["verrou_prestations"], "INTEGER")
        self.assertEqual(dates["verrou_factures"], "INTEGER")

    def test_schema_drift_of_montant_is_blocking(self):
        raw = SOURCE.read_text(encoding="utf-8")
        self.assertIn('("montant", "FLOAT"', raw)
        with tempfile.TemporaryDirectory(prefix="c19g-ast-drift-") as temp:
            fake = Path(temp) / "DATA_Tables.py"
            fake.write_text(
                raw.replace('("montant", "FLOAT"',
                            '("montant", "DECIMAL(10,2)"'),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Derive schema"):
                declared_projection(fake)

    def test_non_literal_db_data_is_not_evaluated(self):
        with tempfile.TemporaryDirectory(prefix="c19g-ast-noexec-") as temp:
            fake = Path(temp) / "schema.py"
            marker = Path(temp) / "should_never_exist"
            fake.write_text(
                "from pathlib import Path\n"
                "DB_DATA = Path(%r).write_text('UNSAFE')\n" % str(marker),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                extract_table_declarations(fake)
            self.assertFalse(marker.exists())

    def test_projection_never_offers_application_writers(self):
        import experimental.qt_c19g_schema_lab.schema_contract as module
        for name in ("facturer", "create_invoice", "send_invoice", "commit"):
            self.assertFalse(hasattr(module, name))


if __name__ == "__main__":
    unittest.main()
