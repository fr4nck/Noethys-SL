"""C19h : replay du vrai SauvegardeFactures wx sur MySQL CI strictement jetable.

Le test extrait les methodes historiques par AST sans charger wx ni
GestionDB. Les ECRITURES ne concernent que les tables synthétiques dans
qt_c19h_lab sur 127.0.0.1:33069, runners GitHub Actions, sans profils.
"""
from __future__ import annotations

from decimal import Decimal
import os
import threading
import unittest
from unittest.mock import patch

from test_c19h_wx_original_semantics import (
    DB, compile_function, fake_panel, method_from_source, wx_generator,
)

MARKER = "C19H_WX_MYSQL_FAKE_ONLY_20261103"
DBNAME = "qt_c19h_lab"


def options():
    env = {
        "CI": "true",
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "fr4nck/Noethys-SL",
        "GITHUB_REF": "refs/heads/qt",
        "C19H_DISPOSABLE_MYSQL": "yes",
        "C19H_MYSQL_HOST": "127.0.0.1",
        "C19H_MYSQL_PORT": "33069",
        "C19H_MYSQL_DATABASE": DBNAME,
        "C19H_MYSQL_USER": "qt_c19h",
    }
    if any(os.environ.get(k) != v for k, v in env.items()):
        raise PermissionError("C19h : seul le conteneur MySQL CI fictif est autorise")
    secret = os.environ.get("C19H_MYSQL_PASSWORD")
    if not secret:
        raise PermissionError("C19h : secret synthetique absent")
    return dict(
        host="127.0.0.1", port=33069, user="qt_c19h",
        password=secret, database=DBNAME, charset="utf8mb4",
        autocommit=False, connect_timeout=5, read_timeout=8,
        write_timeout=8,
    )


def connect():
    import pymysql
    return pymysql.connect(**options())


def _marker(cur):
    cur.execute("SELECT token FROM c19h_marker WHERE id=1")
    if cur.fetchone() != (MARKER,):
        raise PermissionError("C19h : mauvais marqueur fictif")


def create_fixture():
    db = connect()
    try:
        with db.cursor() as cur:
            cur.execute("SHOW TABLES")
            if cur.fetchall():
                raise PermissionError("C19h : base non vide, aucune creation")
            statements = [
                "CREATE TABLE c19h_marker (id INT PRIMARY KEY,"
                " token VARCHAR(100) NOT NULL) ENGINE=InnoDB",
                "CREATE TABLE c19h_fault (id INT PRIMARY KEY,"
                " fail_at INT NOT NULL) ENGINE=InnoDB",
                # Champs factures = sous-ensemble de la declaration wx.
                # AUCUNE unique (IDprefixe,numero) inventee.
                "CREATE TABLE factures ("
                " IDfacture INT AUTO_INCREMENT PRIMARY KEY,"
                " IDprefixe INT NULL, numero BIGINT NULL,"
                " IDcompte_payeur INT NULL, date_edition DATE NULL,"
                " date_echeance DATE NULL, activites VARCHAR(500),"
                " individus VARCHAR(500), IDutilisateur INT,"
                " date_debut DATE NULL, date_fin DATE NULL,"
                " total FLOAT, regle FLOAT, solde FLOAT,"
                " IDlot INT, prestations VARCHAR(500), IDregie INT,"
                " mention1 VARCHAR(300), mention2 VARCHAR(300),"
                " mention3 VARCHAR(300)) ENGINE=InnoDB",
                "CREATE TABLE prestations ("
                " IDprestation INT PRIMARY KEY, IDfacture INT NULL"
                ") ENGINE=InnoDB",
            ]
            for statement in statements:
                cur.execute(statement)
            cur.execute(
                "CREATE TRIGGER c19h_reject_link "
                "BEFORE UPDATE ON prestations FOR EACH ROW "
                "BEGIN "
                " IF (SELECT fail_at FROM c19h_fault WHERE id=1) = "
                " NEW.IDprestation THEN "
                " SIGNAL SQLSTATE '45000' "
                " SET MESSAGE_TEXT = 'c19h deliberately failed update'; "
                " END IF; "
                "END"
            )
            cur.execute(
                "INSERT INTO c19h_marker VALUES (1,%s)", (MARKER,)
            )
            cur.execute("INSERT INTO c19h_fault VALUES (1,0)")
        db.commit()
    finally:
        db.close()


def reset_fixture():
    db = connect()
    try:
        db.begin()
        with db.cursor() as cur:
            _marker(cur)
            cur.execute("SHOW TABLES")
            actual = {row[0] for row in cur.fetchall()}
            expected = {
                "c19h_marker", "c19h_fault", "factures", "prestations",
            }
            if actual != expected:
                raise PermissionError("C19h : table inconnue sur base jetable")
            cur.execute("DELETE FROM factures")
            cur.execute("DELETE FROM prestations")
            cur.execute("INSERT INTO prestations VALUES(301,NULL),(302,NULL)")
            cur.execute("UPDATE c19h_fault SET fail_at=0 WHERE id=1")
        db.commit()
    finally:
        db.close()


def adapter_factory(*, barrier=None):
    insert = compile_function(
        method_from_source(DB, "DB", "ReqInsert"),
        {"_": lambda value: value},
    )
    update = compile_function(
        method_from_source(DB, "DB", "ReqMAJ"),
        {"_": lambda value: value},
    )

    class Adapter:
        isNetwork = True
        ReqInsert = insert
        ReqMAJ = update

        def __init__(self):
            self.connexion = connect()
            self.cursor = self.connexion.cursor()
            _marker(self.cursor)
            self._last_query = ""

        def Commit(self):
            self.connexion.commit()

        def ExecuterReq(self, query):
            self._last_query = query
            self.cursor.execute(query)

        def ResultatReq(self):
            rows = self.cursor.fetchall()
            if barrier is not None and "MAX(numero)" in self._last_query:
                # Les deux lecteurs ont vu le meme MAX avant tout INSERT.
                barrier.wait(timeout=10)
            return rows

        def Close(self):
            self.cursor.close()
            self.connexion.close()

    return Adapter


class C19hMySQLWxReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        create_fixture()

    def setUp(self):
        reset_fixture()

    def query(self, sql, args=()):
        db = connect()
        try:
            with db.cursor() as cur:
                _marker(cur)
                cur.execute(sql, args)
                return cur.fetchall()
        finally:
            db.close()

    def modify(self, sql, args=()):
        db = connect()
        try:
            with db.cursor() as cur:
                _marker(cur)
                cur.execute(sql, args)
            db.commit()
        finally:
            db.close()

    def run_source(self, *, payer=201, lines=(301, 302), barrier=None):
        wx = wx_generator(adapter_factory(barrier=barrier))
        return wx(fake_panel(payer_id=payer, prestation_ids=lines))

    def test_guard_rejects_foreign_host_database_or_runner(self):
        for change in (
            {"C19H_MYSQL_HOST": "SERVEURPMSL"},
            {"C19H_MYSQL_DATABASE": "production"},
            {"GITHUB_ACTIONS": "false"},
            {"C19H_MYSQL_PORT": "3306"},
        ):
            with self.subTest(change=change), patch.dict(os.environ, change):
                with self.assertRaises(PermissionError):
                    options()

    def test_no_business_tables_or_production_markers(self):
        self.assertEqual(
            {row[0] for row in self.query("SHOW TABLES")},
            {"c19h_marker", "c19h_fault", "factures", "prestations"},
        )
        self.assertEqual(DBNAME, "qt_c19h_lab")

    def test_original_wx_generator_runs_against_fictive_mysql(self):
        created = self.run_source()
        self.assertEqual(len(created), 1)
        invoice_id = created[0]
        self.assertIsInstance(invoice_id, int)
        self.assertGreater(invoice_id, 0)
        self.assertEqual(
            self.query("SELECT numero FROM factures"), ((1,),)
        )
        self.assertEqual(
            self.query("SELECT IDfacture FROM prestations ORDER BY IDprestation"),
            ((invoice_id,), (invoice_id,)),
        )

    def test_original_wx_generator_commits_partial_invoice_on_update_failure(self):
        self.modify("UPDATE c19h_fault SET fail_at=302 WHERE id=1")
        # ReqMAJ capture son erreur SQL et ne la remonte pas.
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = self.run_source()
        self.assertEqual(len(result), 1)
        invoice_id = result[0]
        self.assertIn("c19h deliberately failed update", out.getvalue())
        self.assertEqual(
            self.query("SELECT IDprestation,IDfacture FROM prestations ORDER BY IDprestation"),
            ((301, invoice_id), (302, None)),
        )
        self.assertEqual(
            self.query("SELECT COUNT(*) FROM factures"), ((1,),)
        )

    def test_missing_service_id_is_silently_ignored(self):
        created = self.run_source(lines=(301, 999999))
        self.assertEqual(len(created), 1)
        self.assertEqual(
            self.query("SELECT IDprestation,IDfacture FROM prestations ORDER BY IDprestation"),
            ((301, created[0]), (302, None)),
        )

    def test_source_preserves_float_column_not_decimal(self):
        self.run_source()
        import decimal
        total = self.query("SELECT total FROM factures")[0][0]
        self.assertIsInstance(total, float)
        self.assertNotEqual(decimal.Decimal.from_float(total), decimal.Decimal("12.01"))

    def test_two_parallel_runs_can_reuse_same_invoice_number(self):
        # Deux sessions PyMySQL REELLES et deux threads independants.
        # Entrelacement force sur la lecture MAX(numero).
        barrier = threading.Barrier(2)
        results = []
        errors = []
        lock = threading.Lock()

        def run(payer):
            try:
                res = self.run_source(payer=payer, barrier=barrier)
                with lock:
                    results.append(res)
            except BaseException as exc:
                with lock:
                    errors.append(repr(exc))

        threads = [
            threading.Thread(target=run, args=(201,), daemon=True),
            threading.Thread(target=run, args=(202,), daemon=True),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)
        self.assertFalse(any(t.is_alive() for t in threads), "Timeout de concurrence")
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        # Projection sans index unique du couple (prefixe, numero) :
        # deux en-tetes partagent la meme reference documentaire.
        self.assertEqual(
            self.query("SELECT COUNT(*) FROM factures WHERE numero=1"),
            ((2,),),
        )
        # Les updates wx ne verifient pas WHERE IDfacture IS NULL :
        # une prestation peut etre reattribuee, laissant l'autre
        # facture sans ces lignes.
        factures = self.query("SELECT IDfacture FROM factures ORDER BY IDfacture")
        linked = self.query("SELECT DISTINCT IDfacture FROM prestations")
        self.assertEqual(len(factures), 2)
        self.assertEqual(len(linked), 1)
        self.assertIn(linked[0][0], {v[0] for v in factures})

    def test_null_prefix_unique_constraint_is_not_sufficient_by_itself(self):
        # Une cle UNIQUE(prefixe,numero) NULLABLE tolere deux valeurs NULL.
        # Table de contre-exemple fictive, pas un schema de production.
        db = connect()
        try:
            with db.cursor() as cur:
                _marker(cur)
                cur.execute(
                    "CREATE TEMPORARY TABLE c19h_unique_nullable("
                    " IDprefixe INT NULL, numero BIGINT NOT NULL,"
                    " UNIQUE KEY (IDprefixe,numero))"
                )
                cur.execute(
                    "INSERT INTO c19h_unique_nullable VALUES(NULL,1),(NULL,1)"
                )
                cur.execute("SELECT COUNT(*) FROM c19h_unique_nullable")
                self.assertEqual(cur.fetchone(), (2,))
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
