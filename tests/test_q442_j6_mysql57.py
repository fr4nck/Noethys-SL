# -*- coding: utf-8 -*-
"""Q442/J6 - MySQL 5.7 real, *disposable* synthetic fixture only.

Runs only with NOETHYS_Q442_MYSQL_EXIGER=1 on a local ephemeral MySQL server.
Never opens user profiles, real Noethys databases, or nonlocal hosts.
The QF reader uses only SELECT; all fixture writes occur in a uniquely named
throwaway schema and are undone when the test completes.
"""
from __future__ import annotations

import os
import re
import sqlite3
from contextlib import closing
import unittest
from datetime import date
from secrets import token_hex

from qa.q442_candidate.source_j3.source_j2.fixture_q442_precedente import create_fixture
from Utils.UTILS_Stats_qf_sites import (
    ConfigurationMultisite, LecteurMultisite, SiteRegle, SiteNonResoluble,
)

ACTIVITY = 10
START = "2026-07-01"
END = "2026-07-31"
EXPECTED_SITES = {"Bais": 6, "La Guerche": 3, "Moutiers": 1}
SAFE_DATABASE = re.compile(r"^zz_q442_j6_[0-9a-f]{16}$")
SAFE_TABLE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
DATE_COLUMNS = {
    "date", "date_debut", "date_fin", "date_saisie", "forfait_date_debut",
    "forfait_date_fin",
}


def config():
    """IDs belong to the synthetic fixture, NOT to any association data."""
    return ConfigurationMultisite(
        regles=(
            SiteRegle("Bais", ACTIVITY, (1,), (101,)),
            SiteRegle("La Guerche", ACTIVITY, (1,), (102,)),
            SiteRegle("Moutiers", ACTIVITY, (1,), (103,)),
        ),
        tarifs_accueil={ACTIVITY: (100, 110)},
        libelles={"1": "A", "2": "B", "3": "C", "4": "D"},
        categories_historiques=("E historique",),
    )


def fixture_sqlite():
    """Use the same isolated 9-family/11-child fixture as J4/J5.

    Site group identifiers and the original activity remapping are part of the
    *synthetic* data, not a proposed mapping for the real PMSL databases.
    """
    cn = create_fixture()
    cn.execute("ALTER TABLE consommations ADD COLUMN IDgroupe INTEGER")
    cn.execute("ALTER TABLE consommations ADD COLUMN IDinscription INTEGER")
    cn.executescript("""
        CREATE TABLE activites(IDactivite INTEGER PRIMARY KEY,nom TEXT,abrege TEXT,date_debut TEXT,date_fin TEXT);
        CREATE TABLE unites(IDunite INTEGER PRIMARY KEY,IDactivite INTEGER,nom TEXT,repas INTEGER);
        CREATE TABLE groupes(IDgroupe INTEGER PRIMARY KEY,IDactivite INTEGER,nom TEXT);
        CREATE TABLE inscriptions(IDinscription INTEGER PRIMARY KEY,IDfamille INTEGER,IDindividu INTEGER,
                                  IDactivite INTEGER,IDgroupe INTEGER,IDcategorie_tarif INTEGER,statut TEXT);
    """)
    cn.execute("INSERT INTO activites VALUES(10,'ALSH MULTISITE','ALSH','2026-01-01','2026-12-31')")
    cn.executemany("INSERT INTO unites VALUES(?,?,?,?)", [(1, 10, "Journee", 0), (2, 10, "Repas", 1)])
    cn.executemany("INSERT INTO groupes VALUES(?,?,?)", [
        (101, 10, "Groupe Bais"),
        (102, 10, "Groupe La Guerche"),
        (103, 10, "Groupe Moutiers"),
    ])
    cn.execute("UPDATE tarifs SET IDactivite=10 WHERE IDtarif=110")
    cn.execute("UPDATE prestations SET IDactivite=10 WHERE IDactivite=11")
    for c_id, act, individual, payer in list(cn.execute(
            "SELECT IDconso,IDactivite,IDindividu,IDcompte_payeur FROM consommations")):
        group = 102 if act == 11 else 101
        if c_id == 15:
            group = 103
        cn.execute("UPDATE consommations SET IDactivite=10,IDgroupe=?,IDinscription=? WHERE IDconso=?",
                   (group, c_id, c_id))
        family, = cn.execute("SELECT IDfamille FROM comptes_payeurs WHERE IDcompte_payeur=?",
                             (payer,)).fetchone()
        cn.execute("INSERT INTO inscriptions VALUES(?,?,?,?,?,?,?)",
                   (c_id, family, individual, 10, group, 1, "ok"))
    cn.commit()
    return cn


def fixture_to_mysql(synthetic, mysql):
    """Copy all tables and synthetic rows; schema built only in throwaway DB.

    MySQL DATE columns return datetime.date while SQLite returns ISO text.
    This deliberately probes the cross-DB date boundary in the *real reader*.
    """
    cur = mysql.cursor()
    try:
        names = [row[0] for row in synthetic.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        assert len(names) >= 10, "Synthetic fixture appears incomplete"
        for table in names:
            if not SAFE_TABLE.fullmatch(table):
                raise AssertionError("Unsafe synthetic table name")
            fields = list(synthetic.execute("PRAGMA table_info(`%s`)" % table))
            pieces = []
            for field in fields:
                name, col_type, pk = field[1], field[2].upper(), field[5]
                if not SAFE_TABLE.fullmatch(name):
                    raise AssertionError("Unsafe synthetic field name")
                if name in DATE_COLUMNS and (col_type == 'TEXT'):
                    sql_type = 'DATE'
                elif col_type == 'INTEGER':
                    sql_type = 'INT'
                elif col_type == 'REAL':
                    sql_type = 'DOUBLE'
                elif col_type == 'TEXT':
                    sql_type = 'VARCHAR(255)'
                else:
                    raise AssertionError('Unmapped synthetic type: %s' % col_type)
                pieces.append('`%s` %s%s' % (name, sql_type, ' PRIMARY KEY' if pk else ''))
            cur.execute('CREATE TABLE `%s` (%s) ENGINE=InnoDB' % (table, ','.join(pieces)))
            rows = [tuple(row) for row in synthetic.execute('SELECT * FROM `%s`' % table)]
            if rows:
                markers = ','.join(['%s'] * len(fields))
                cur.executemany('INSERT INTO `%s` VALUES (%s)' % (table, markers), rows)
        mysql.commit()
    finally:
        cur.close()


class ReadDB:
    """Emulate the public GestionDB read interface with either SQL engine."""
    def __init__(self, connection, sqlite=False):
        self.connection = connection
        self.sqlite = sqlite
        self.queries = []
        self.rows = None

    def ExecuterReq(self, sql):
        if not sql.lstrip().upper().startswith('SELECT '):
            raise AssertionError('Unexpected non-SELECT from QF reader')
        self.queries.append(sql)
        if self.sqlite:
            self.rows = self.connection.execute(sql).fetchall()
        else:
            cursor = self.connection.cursor()
            try:
                cursor.execute(sql)
                self.rows = cursor.fetchall()
            finally:
                cursor.close()
        return True

    def ResultatReq(self):
        return self.rows


def read_stats(connection, sqlite=False, sites=None, begin=START, end=END):
    db = ReadDB(connection, sqlite=sqlite)
    data = LecteurMultisite(db, config()).lire(begin, end, selection_sites=sites)
    if not db.queries or any(not query.lstrip().upper().startswith('SELECT ') for query in db.queries):
        raise AssertionError('QF reader emitted a non-SELECT or no query')
    return data, db.queries


@unittest.skipUnless(os.environ.get('NOETHYS_Q442_MYSQL_EXIGER') == '1',
                     'MySQL Q442 J6 only with explicit local ephemeral-server opt-in')
class Q442J6MySQL57(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The MySQL test user is created by the existing CI-local preparer.
        if os.environ.get('NOETHYS_Q442_MYSQL_EXIGER') != '1':
            return
        host = os.environ.get('NOETHYS_TEST_MYSQL_HOST', '').strip().lower()
        port = int(os.environ.get('NOETHYS_TEST_MYSQL_PORT', '0'))
        if host != '127.0.0.1' or port != 3402:
            raise RuntimeError('Q442 J6 refuses any MySQL host/port outside CI localhost:3402')
        import MySQLdb
        cls._mysql = MySQLdb.connect(
            host=host, port=port,
            user=os.environ['NOETHYS_TEST_MYSQL_USER'],
            passwd=os.environ['NOETHYS_TEST_MYSQL_PASSWORD'],
            charset='utf8mb4', connect_timeout=5,
        )
        cls._mysql.autocommit(False)
        with cls._mysql.cursor() as cur:
            cur.execute('SELECT VERSION()')
            version, = cur.fetchone()
        if not version.startswith('5.7.'):
            cls._mysql.close()
            raise RuntimeError('Expected real MySQL 5.7, not %s' % version)
        cls._database = 'zz_q442_j6_' + token_hex(8)
        if not SAFE_DATABASE.fullmatch(cls._database):
            raise RuntimeError('Incorrect disposable schema name')
        with cls._mysql.cursor() as cur:
            cur.execute('CREATE DATABASE `%s` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci' % cls._database)
        cls._mysql.select_db(cls._database)
        cls._fixture = fixture_sqlite()
        try:
            fixture_to_mysql(cls._fixture, cls._mysql)
        except Exception:
            cls.tearDownClass()
            raise
        cls._version = version

    @classmethod
    def tearDownClass(cls):
        synthetic = getattr(cls, '_fixture', None)
        if synthetic is not None:
            synthetic.close()
            cls._fixture = None
        mysql = getattr(cls, '_mysql', None)
        if mysql is not None:
            name = getattr(cls, '_database', None)
            if name is not None and SAFE_DATABASE.fullmatch(name):
                with mysql.cursor() as cur:
                    cur.execute('DROP DATABASE IF EXISTS `%s`' % name)
            mysql.close()
            cls._mysql = None

    def tearDown(self):
        self._mysql.rollback()

    def test_01_server_is_real_mysql57(self):
        self.assertTrue(self._version.startswith('5.7.'))

    def test_02_same_global_family_child_denominators(self):
        mysql, queries = read_stats(self._mysql)
        self.assertEqual(mysql['global']['familles']['total'], 9)
        self.assertEqual(mysql['global']['enfants']['total'], 11)
        self.assertEqual(mysql['lectures_sql'], len(queries))
        self.assertEqual(len(queries), 3)

    def test_03_site_counts_and_family_deduplication(self):
        result, _ = read_stats(self._mysql)
        self.assertEqual({name: value['familles']['total'] for name, value in result['sites'].items()}, EXPECTED_SITES)
        self.assertEqual(sum(EXPECTED_SITES.values()), 10)
        self.assertEqual(result['global']['familles']['total'], 9)

    def test_04_same_categories_as_sqlite(self):
        expected, _ = read_stats(self._fixture, sqlite=True)
        observed, _ = read_stats(self._mysql)
        for scope in ('global', 'sites'):
            self.assertEqual(observed[scope], expected[scope], 'MySQL and SQLite QF series must match exactly')

    def test_05_non_communicated_qf_and_zero_categories(self):
        result, _ = read_stats(self._mysql)
        global_fam = result['global']['familles']
        self.assertEqual(global_fam['qf']['QF non communique'], 2)
        self.assertEqual(global_fam['tarifs_indicatifs']['E historique'], 0)
        self.assertEqual(sum(global_fam['qf'].values()), 9)
        self.assertEqual(sum(global_fam['tarifs_indicatifs'].values()), 9)

    def test_06_before_invoicing_and_representative_subperiod(self):
        early, _ = read_stats(self._mysql, begin='2026-07-01', end='2026-07-14')
        reference, _ = read_stats(self._fixture, sqlite=True, begin='2026-07-01', end='2026-07-14')
        self.assertEqual(early['global'], reference['global'])
        with self._mysql.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM prestations WHERE IDfacture IS NOT NULL')
            count, = cur.fetchone()
        self.assertEqual(count, 0)

    def test_07_same_site_selection_as_sqlite(self):
        for sites in [('Bais',), ('Bais', 'La Guerche'), ('Moutiers',)]:
            with self.subTest(sites=sites):
                expected, _ = read_stats(self._fixture, sqlite=True, sites=sites)
                result, _ = read_stats(self._mysql, sites=sites)
                self.assertEqual(result['global'], expected['global'])
                self.assertEqual(result['sites'], expected['sites'])

    def test_08_fail_closed_on_missing_physical_site(self):
        with self._mysql.cursor() as cur:
            cur.execute('UPDATE consommations SET IDgroupe=999 WHERE IDconso=1')
        with self.assertRaises(SiteNonResoluble):
            read_stats(self._mysql)

    def test_09_fail_closed_on_cross_activity_group(self):
        with self._mysql.cursor() as cur:
            cur.execute('UPDATE groupes SET IDactivite=999 WHERE IDgroupe=101')
        with self.assertRaises(SiteNonResoluble):
            read_stats(self._mysql)

    def test_10_only_selected_receipted_categories_are_indicative(self):
        result, _ = read_stats(self._mysql)
        for group in (result['global'], *result['sites'].values()):
            for kind in ('familles', 'enfants'):
                self.assertEqual(group[kind]['categories_tarif_attestees'], 0)
                self.assertEqual(group[kind]['categories_historiques_non_attestees'], group[kind]['total'])


    def test_11_no_payer_still_counts_enrolled_child_and_family(self):
        # Before billing, payer assignment is optional: enrollment is source.
        with self._mysql.cursor() as cur:
            cur.execute("UPDATE consommations SET IDcompte_payeur=NULL WHERE IDconso=10")
        reference, _ = read_stats(self._fixture, sqlite=True)
        observed, _ = read_stats(self._mysql)
        self.assertEqual(observed['global'], reference['global'])
        self.assertEqual(observed['global']['familles']['total'], 9)
        self.assertEqual(observed['global']['enfants']['total'], 11)

    def test_12_third_party_payer_cannot_change_qf_family(self):
        # A different paying family must not absorb the enrolled family.
        with self._mysql.cursor() as cur:
            cur.execute("UPDATE consommations SET IDcompte_payeur=1001 WHERE IDconso=10")
        reference, _ = read_stats(self._fixture, sqlite=True)
        observed, _ = read_stats(self._mysql)
        self.assertEqual(observed['global']['familles']['total'], 9)
        self.assertEqual(observed['global']['familles']['qf'],
                         reference['global']['familles']['qf'])
        self.assertGreaterEqual(
            observed['global']['familles']['anomalies'].get(
                'FAMILLE_INSCRIPTION_PAYEUR_DIFFERENTE', 0), 1)


class Q442J6SQLiteContract(unittest.TestCase):
    """Runs without server, proving fixture and date-adapter behavior locally."""
    def test_sqlite_reference_still_has_9_families(self):
        with closing(fixture_sqlite()) as synthetic:
            report, queries = read_stats(synthetic, sqlite=True)
            self.assertEqual(report['global']['familles']['total'], 9)
            self.assertEqual(report['global']['enfants']['total'], 11)
            self.assertEqual(len(queries), 3)

    def test_dates_have_explicit_mysql_date_column_type(self):
        with closing(fixture_sqlite()) as synthetic:
            for table in ('quotients', 'consommations', 'prestations'):
                fields = {x['name'] for x in synthetic.execute('PRAGMA table_info(`%s`)' % table)}
                self.assertIn('date' if table != 'quotients' else 'date_debut', fields)


    def test_reader_accepts_mysql_datetime_date_rows(self):
        # Mimic mysqlclient DATE decoding even without a local MySQL server.
        class MySQLDateRows(ReadDB):
            def ResultatReq(self):
                out = []
                for row in self.rows:
                    values = list(row)
                    if 'FROM consommations c' in self.queries[-1]:
                        columns = (1, 15)
                    elif 'FROM quotients WHERE' in self.queries[-1]:
                        columns = (3, 4)
                    else:
                        columns = ()
                    for index in columns:
                        if values[index] is not None and isinstance(values[index], str):
                            values[index] = date.fromisoformat(values[index])
                    out.append(tuple(values))
                return out
        with closing(fixture_sqlite()) as synthetic:
            baseline, _ = read_stats(synthetic, sqlite=True)
            bridge = MySQLDateRows(synthetic, sqlite=True)
            converted = LecteurMultisite(bridge, config()).lire(START, END)
            self.assertEqual(converted['global'], baseline['global'])
            self.assertEqual(converted['sites'], baseline['sites'])

    def test_mysql_loader_transfers_only_temporary_fixture(self):
        class FakeCursor:
            def __init__(self):
                self.ddls = []
                self.inserts = []
            def execute(self, sql):
                self.ddls.append(sql)
            def executemany(self, sql, rows):
                self.inserts.append((sql, len(rows)))
            def close(self):
                pass
        class FakeMysql:
            def __init__(self):
                self.cursor_obj = FakeCursor()
                self.commits = 0
            def cursor(self):
                return self.cursor_obj
            def commit(self):
                self.commits += 1
        with closing(fixture_sqlite()) as synthetic:
            fake = FakeMysql()
            fixture_to_mysql(synthetic, fake)
            self.assertGreaterEqual(len(fake.cursor_obj.ddls), 10)
            self.assertEqual(fake.commits, 1)
            self.assertTrue(all(sql.startswith('CREATE TABLE `') for sql in fake.cursor_obj.ddls))
            self.assertTrue(all(sql.startswith('INSERT INTO `') for sql, n in fake.cursor_obj.inserts))
            self.assertTrue(any('`date` DATE' in ddl for ddl in fake.cursor_obj.ddls))
            self.assertTrue(any('`date_debut` DATE' in ddl for ddl in fake.cursor_obj.ddls))


    def test_enrollment_family_without_payer(self):
        with closing(fixture_sqlite()) as synthetic:
            expected, _ = read_stats(synthetic, sqlite=True)
            synthetic.execute('UPDATE consommations SET IDcompte_payeur=NULL WHERE IDconso=10')
            obtained, _ = read_stats(synthetic, sqlite=True)
            self.assertEqual(obtained['global'], expected['global'])
            self.assertEqual(obtained['sites'], expected['sites'])

    def test_third_party_payer_cannot_reassign_family(self):
        with closing(fixture_sqlite()) as synthetic:
            baseline, _ = read_stats(synthetic, sqlite=True)
            synthetic.execute('UPDATE consommations SET IDcompte_payeur=1001 WHERE IDconso=10')
            actual, _ = read_stats(synthetic, sqlite=True)
            self.assertEqual(actual['global']['familles']['total'], 9)
            self.assertEqual(actual['global']['familles']['qf'],
                             baseline['global']['familles']['qf'])
            self.assertGreaterEqual(
                actual['global']['familles']['anomalies'].get(
                    'FAMILLE_INSCRIPTION_PAYEUR_DIFFERENTE', 0), 1)

    def test_both_enrollment_and_payer_missing_fail_closed(self):
        with closing(fixture_sqlite()) as synthetic:
            synthetic.execute(
                'UPDATE consommations SET IDinscription=NULL, IDcompte_payeur=NULL '
                'WHERE IDconso=10')
            with self.assertRaises(SiteNonResoluble):
                read_stats(synthetic, sqlite=True)


if __name__ == '__main__':
    unittest.main()
