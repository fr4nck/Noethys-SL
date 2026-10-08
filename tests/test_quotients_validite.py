"""Dates, confirmation et écritures atomiques sur une base fictive."""
import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import datetime
import importlib.util
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('validite', ROOT / 'noethys/Utils/UTILS_Quotients_validite.py')
validite = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validite)
D = datetime.date


class ValiditeTests(unittest.TestCase):
    def test_limites_et_annees(self):
        for debut, fin in [(D(2026, 1, 9), D(2026, 1, 9)),
                           (D(2026, 1, 10), D(2026, 9, 9)),
                           (D(2026, 9, 9), D(2026, 9, 9)),
                           (D(2026, 9, 10), D(2027, 1, 9)),
                           (D(2026, 12, 31), D(2027, 1, 9)),
                           (D(2028, 2, 29), D(2028, 9, 9))]:
            with self.subTest(debut=debut):
                self.assertEqual(validite.DateFinProposee(debut), fin)

    def test_conflits_non_ajustables(self):
        ligne = (1, D(2026, 10, 2), D(2027, 1, 9), '')
        for lignes in [[], [ligne], [ligne, ligne]]:
            self.assertIsNone(validite.PrecedentACloturer(lignes, D(2026, 10, 2)))


class EnregistrementTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(':memory:')
        self.addCleanup(self.connection.close)
        self.connection.executescript('''
            CREATE TABLE quotients (IDquotient INTEGER PRIMARY KEY, IDfamille INTEGER,
              date_debut TEXT, date_fin TEXT, quotient INTEGER, revenu REAL,
              observations TEXT, IDtype_quotient INTEGER);
            CREATE TABLE factures (IDfacture INTEGER PRIMARY KEY, montant REAL);
            CREATE TABLE prestations (IDprestation INTEGER PRIMARY KEY, montant REAL);
            INSERT INTO factures VALUES (1, 123.45);
            INSERT INTO prestations VALUES (1, 67.89);
            INSERT INTO quotients VALUES (1, 1, '2026-09-10', '2027-01-09', 700, 0, 'Note initiale', 1);
        ''')
        self.db = SimpleNamespace(connexion=self.connection, cursor=self.connection.cursor(),
                                  isNetwork=False, Commit=self.connection.commit)
        self.donnees = dict(IDfamille=1, date_debut=D(2026, 10, 2), date_fin=D(2027, 1, 9),
                            quotient=900, revenu=0, observations='Nouveau', IDtype_quotient=1)

    def chevauchements(self):
        d = self.donnees
        return validite.LireChevauchements(self.db, d['IDfamille'], d['IDtype_quotient'],
                                         None, d['date_debut'], d['date_fin'])

    def test_renouvellement_et_factures_inchangees(self):
        precedent = self.chevauchements()[0]
        ID = validite.Enregistrer(self.db, self.donnees, precedent=precedent)
        self.assertEqual(ID, 2)
        fin, observations = self.connection.execute('SELECT date_fin, observations FROM quotients WHERE IDquotient=1').fetchone()
        self.assertEqual(fin, '2026-10-01')
        self.assertIn('Note initiale', observations)
        self.assertIn('09/01/2027', observations)
        self.assertEqual(self.connection.execute('SELECT * FROM factures').fetchall(), [(1, 123.45)])
        self.assertEqual(self.connection.execute('SELECT * FROM prestations').fetchall(), [(1, 67.89)])

    def test_sans_confirmation_aucune_ecriture(self):
        with self.assertRaises(ValueError):
            validite.Enregistrer(self.db, self.donnees)
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM quotients').fetchone()[0], 1)
        self.assertEqual(self.connection.execute('SELECT date_fin FROM quotients').fetchone()[0], '2027-01-09')

    def test_echec_insert_annule_cloture(self):
        precedent = self.chevauchements()[0]
        self.connection.execute("CREATE TRIGGER echec BEFORE INSERT ON quotients BEGIN SELECT RAISE(ABORT, 'test'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            validite.Enregistrer(self.db, self.donnees, precedent=precedent)
        self.assertEqual(self.connection.execute('SELECT date_fin, observations FROM quotients').fetchone(),
                         ('2027-01-09', 'Note initiale'))

    def test_precedent_modifie_depuis_confirmation(self):
        precedent = self.chevauchements()[0]
        self.connection.execute("UPDATE quotients SET date_fin='2026-12-31'")
        self.connection.commit()
        with self.assertRaises(ValueError):
            validite.Enregistrer(self.db, self.donnees, precedent=precedent)
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM quotients').fetchone()[0], 1)

    def test_autre_type_et_autre_famille_non_modifies(self):
        self.donnees['IDtype_quotient'] = 2
        validite.Enregistrer(self.db, self.donnees)
        self.donnees['IDfamille'] = 2
        self.donnees['IDtype_quotient'] = 1
        validite.Enregistrer(self.db, self.donnees)
        self.assertEqual(self.connection.execute('SELECT date_fin FROM quotients WHERE IDquotient=1').fetchone()[0], '2027-01-09')

    def test_type_null(self):
        self.connection.execute('UPDATE quotients SET IDtype_quotient=NULL')
        self.connection.commit()
        self.donnees['IDtype_quotient'] = None
        self.assertEqual(len(self.chevauchements()), 1)

    def test_modification_chargee_sans_changer_autres_dates(self):
        self.donnees['date_debut'] = D(2026, 9, 10)
        validite.Enregistrer(self.db, self.donnees, IDquotient=1)
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM quotients').fetchone()[0], 1)
        self.assertEqual(self.connection.execute('SELECT quotient FROM quotients').fetchone()[0], 900)

    def test_dates_inversees(self):
        self.donnees['date_fin'] = D(2026, 1, 9)
        with self.assertRaises(ValueError):
            validite.Enregistrer(self.db, self.donnees)

    def test_parametres_mysql_et_verrouillage(self):
        cursor = self.db.cursor
        requetes = []
        class AdaptateurMySQL:
            statut = False
            def execute(self, sql, params=()):
                requetes.append(sql)
                self.statut = sql.startswith('SHOW TABLE STATUS')
                if self.statut:
                    return
                if sql == 'START TRANSACTION':
                    sql = 'BEGIN IMMEDIATE'
                cursor.execute(sql.replace('%s', '?').replace(' FOR UPDATE', ''), params)
            def fetchone(self):
                return ('quotients', 'InnoDB') if self.statut else cursor.fetchone()
            def __getattr__(self, nom):
                return getattr(cursor, nom)
        precedent = self.chevauchements()[0]
        self.db.isNetwork = True
        self.db.cursor = AdaptateurMySQL()
        validite.Enregistrer(self.db, self.donnees, precedent=precedent)
        self.assertTrue(any('FOR UPDATE' in sql for sql in requetes))
        self.assertEqual(self.connection.execute('SELECT date_fin FROM quotients WHERE IDquotient=1').fetchone()[0], '2026-10-01')

    def test_mysql_non_transactionnel_refuse_avant_ecriture(self):
        precedent = self.chevauchements()[0]
        from unittest.mock import Mock
        self.db.isNetwork = True
        self.db.cursor = Mock()
        self.db.cursor.fetchone.return_value = ('quotients', 'MyISAM')
        with self.assertRaises(ValueError):
            validite.Enregistrer(self.db, self.donnees, precedent=precedent)
        self.db.cursor.execute.assert_called_once_with("SHOW TABLE STATUS LIKE 'quotients'")
        self.assertEqual(self.connection.execute('SELECT date_fin FROM quotients').fetchone()[0], '2027-01-09')


if __name__ == '__main__':
    unittest.main()
