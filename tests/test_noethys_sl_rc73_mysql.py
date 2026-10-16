# -*- coding: utf-8 -*-
"""Qualification opt-in : serveur LOCAL jetable et données strictement fictives.

Le workflow Windows crée seul le serveur ; aucune configuration utilisateur,
aucun appel Mailjet et aucun email. Les seuls objets supprimés appartiennent à
la base unique créée par cette classe pendant ce processus.
"""
import concurrent.futures
import datetime as dt
import os
from pathlib import Path
import sys
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402
from test_noethys_sl_accueil_compact import ReadOnlyFixture
from Utils import UTILS_Accueil_jour as day
from Utils import UTILS_Suivi_mailjet as tracking


class LocalAdapter:
    isNetwork = True
    echec = 0

    def __init__(self, connection):
        self.connexion = connection
        self.cursor = connection.cursor()

    def ExecuterReq(self, sql):
        if not sql.lstrip().upper().startswith('SELECT'):
            raise AssertionError('Le programme du jour doit rester en lecture seule')
        self.cursor.execute(sql)
        return True

    def ResultatReq(self):
        return self.cursor.fetchall()

    def Commit(self):
        self.connexion.commit()

    def Close(self):
        self.connexion.close()


class ConfigurationTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('NOETHYS_TEST_MYSQL_EXIGER') == '1',
                         'recette serveur non demandée')
    def test_serveur_local_explicitement_declare(self):
        self.assertIsNotNone(_garde_reseau.ParametresMySQLDeTest())


@unittest.skipUnless(_garde_reseau.ParametresMySQLDeTest(), 'serveur MySQL jetable non déclaré')
class RecetteMySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import MySQLdb
        cls.params = _garde_reseau.ParametresMySQLDeTest()
        cls.database = 'noethys_rc73_synthetic_' + uuid.uuid4().hex
        cls.connect = staticmethod(lambda db='': MySQLdb.connect(
            host=cls.params['hote'], port=cls.params['port'],
            user=cls.params['utilisateur'], passwd=cls.params['motdepasse'],
            db=db, charset='utf8'))
        cx = cls.connect()
        try:
            cx.cursor().execute('CREATE DATABASE `%s` CHARACTER SET utf8' % cls.database)
        finally:
            cx.close()
        cls.addClassCleanup(cls.drop_owned_database)
        print('RC7.3 : MySQL local, base synthétique unique créée pour cette recette')

    @classmethod
    def drop_owned_database(cls):
        assert cls.database.startswith('noethys_rc73_synthetic_')
        assert len(cls.database) == len('noethys_rc73_synthetic_') + 32
        cx = cls.connect()
        try:
            cx.cursor().execute('DROP DATABASE `%s`' % cls.database)
        finally:
            cx.close()

    def test_accueil_memes_resultats_sqlite_mysql_et_aucune_ecriture(self):
        fixture = ReadOnlyFixture()
        self.addCleanup(fixture.db.close)
        fixture.db.execute("INSERT INTO unites VALUES(9,1,'12:00','13:00',NULL,NULL)")
        fixture.db.execute("INSERT INTO consommations VALUES(1,999,9,'2026-10-16','reservation',NULL,NULL,10,NULL)")
        fixture.db.execute("INSERT INTO ouvertures VALUES(1,'2026-10-16',11)")
        fixture.db.execute("INSERT INTO consommations VALUES(1,201,1,'2026-10-16','reservation',NULL,NULL,11,NULL)")
        fixture.db.execute("UPDATE unites_remplissage SET heure_min='09:00',heure_max='11:00',etiquettes='7' WHERE IDunite_remplissage=101")
        fixture.db.execute("UPDATE consommations SET heure_debut='08:00',heure_fin='12:00',etiquettes='7;9' WHERE IDindividu IN (101,201)")
        cx = self.connect(self.database)
        self.addCleanup(cx.close)
        cur = cx.cursor()
        tables = [row[0] for row in fixture.db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in tables:
            columns = [row[1] for row in fixture.db.execute('PRAGMA table_info(%s)' % table)]
            def sql_type(name):
                if name.startswith('ID'):
                    return 'INT'
                if name.startswith('date'):
                    return 'DATE'
                if name.startswith('heure'):
                    return 'TIME'
                return 'VARCHAR(255)'
            cur.execute('CREATE TABLE `%s` (%s)' % (table, ','.join(
                '`%s` %s' % (c, sql_type(c)) for c in columns)))
            values = list(fixture.db.execute('SELECT * FROM %s' % table))
            if values:
                cur.executemany('INSERT INTO `%s` VALUES (%s)' % (table, ','.join(['%s']*len(columns))), values)
        cx.commit()
        def snapshot():
            result = {}
            for table in tables:
                cur.execute('SELECT * FROM `%s`' % table)
                result[table] = cur.fetchall()
            return result
        before = snapshot()
        expected = day.read_day(fixture, dt.date(2026, 10, 16))
        actual = day.read_day(LocalAdapter(cx), dt.date(2026, 10, 16))
        self.assertEqual(actual, expected)
        self.assertEqual([(r['morning'], r['afternoon']) for r in actual[0] if r['alsh']], [(1,2),(1,0)])
        self.assertEqual(snapshot(), before)

    def test_mailjet_verrou_reel_concurrence_unicode_et_actualisation_comparee(self):
        cx = self.connect(self.database)
        try:
            cur = cx.cursor()
            cur.execute('CREATE TABLE parametres (IDparametre INT PRIMARY KEY AUTO_INCREMENT, '
                        'categorie VARCHAR(255), nom VARCHAR(255), parametre TEXT) ENGINE=InnoDB')
            cx.commit()
        finally:
            cx.close()
        journal = tracking.Journal(self.database, lambda _: LocalAdapter(self.connect(self.database)))
        key = 'CLE-STRICTEMENT-FICTIVE-RC73'
        def register(_):
            journal.Enregistrer(key, 'exp@example.invalid', 'Sujet fictif é 😀',
                                [('dest@example.invalid', 'uuid-fictif', '18446744073709551614')])
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(register, range(8)))
        rows = journal.Lister()
        self.assertEqual(len(rows), 1)
        first = rows[0]
        self.assertEqual(first['sujet'], 'Sujet fictif é 😀')
        self.assertTrue(journal.SauverResultat(first, dict(etat='sent', verifie_le=tracking.Maintenant())))
        self.assertFalse(journal.SauverResultat(first, erreur='Ancienne consultation'))
        register(None)
        self.assertEqual(journal.Lister()[0]['etat'], 'sent')
        self.assertEqual(journal.Lister()[0]['erreur_consultation'], '')
        cx = self.connect(self.database)
        try:
            cur = cx.cursor()
            cur.execute('SELECT COUNT(*) FROM parametres')
            self.assertEqual(cur.fetchone()[0], 1)
        finally:
            cx.close()


if __name__ == '__main__':
    unittest.main()
