"""Sauvegarde reelle sur donnees strictement synthetiques, sans wx ni profil."""
import pathlib
from contextlib import closing
import sqlite3
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _synthetic_grille import Database, FIELDS, ROOT, conso, grille, method, saver, schema


class SauvegardeSyntheticTests(unittest.TestCase):
    def test_mixte_ecritures_historique_et_frontieres(self):
        with sqlite3.connect(':memory:') as cn:
            schema(cn)
            cn.executemany('INSERT INTO consommations (IDconso, etat) VALUES (?, ?)',
                           [(1, 'attente'), (2, 'attente'), (3, 'attente'), (4, 'attente')])
            db = Database(cn)
            saver(db)(grille([conso(1), conso(2, 'modification', 'reservation'),
                             conso(3, 'suppression'), conso(4, None, None),
                             conso(None, 'ajout', 'reservation')]))
            self.assertEqual(cn.execute('SELECT IDconso, etat FROM consommations ORDER BY IDconso').fetchall(),
                             [(1, 'attente'), (2, 'reservation'), (5, 'reservation')])
            self.assertEqual([a['IDcategorie'] for a in db.history], [10, 29, 9])
            self.assertEqual(db.history[0]['action'], '02/01/26(SYN+SYN)')
            self.assertEqual([c[0] for c in db.calls],
                             ['many', 'many', 'execute', 'commit', 'commit', 'commit', 'close'])
            self.assertTrue(all(c[3] is False for c in db.calls if c[0] == 'many'))

    def test_multihoraires_supprimes_hors_grille(self):
        db = Database()
        g = grille([conso(1)])
        c = conso(7)
        c.case = SimpleNamespace(IDunite=1, IDindividu=1, date=next(iter(g.dictConsoIndividus[1])))
        g.listeConsoSupprimees = [c]
        saver(db)(g)
        self.assertEqual(db.calls[0], ('execute', 'DELETE FROM consommations WHERE IDconso IN (7)'))
        self.assertEqual(db.history[0]['IDcategorie'], 10)

    def test_pas_de_conversion_sur_lignes_inchangees(self):
        db, conversion = Database(), Mock(return_value='')
        saver(db, convert=conversion)(grille([conso(n) for n in range(1, 1001)]))
        conversion.assert_not_called()
        self.assertEqual(db.calls, [('commit',), ('commit',), ('close',)])
        self.assertEqual(db.history, [])

    def test_erreur_update_remonte_avant_commit_et_historique(self):
        db = Database(fail=True)
        with self.assertRaisesRegex(RuntimeError, 'synthetic'):
            saver(db)(grille([conso(1, 'modification')]))
        self.assertEqual([c[0] for c in db.calls], ['many'])
        self.assertEqual(db.history, [])

    def test_deux_connexions_changement_externe_sur_ligne_inchangee_preserve(self):
        with tempfile.TemporaryDirectory() as tmp:
            with closing(sqlite3.connect(str(pathlib.Path(tmp) / 'synthetic.db'))) as a, \
                    closing(sqlite3.connect(str(pathlib.Path(tmp) / 'synthetic.db'))) as b:
                schema(a)
                a.executemany('INSERT INTO consommations (IDconso, etat) VALUES (?, ?)',
                              [(1, 'attente'), (2, 'attente')])
                a.commit()
                loaded = grille([conso(1), conso(2, 'modification', 'reservation')])
                b.execute("UPDATE consommations SET etat='present' WHERE IDconso=1")
                b.commit()
                saver(Database(a))(loaded)
                self.assertEqual(b.execute('SELECT etat FROM consommations ORDER BY IDconso').fetchall(),
                                 [('present',), ('reservation',)])

    def test_update_conserve_les_vingt_champs_et_nulls(self):
        db = Database()
        saver(db)(grille([conso(1, 'modification', 'reservation')]))
        req, rows = db.calls[0][1:3]
        self.assertEqual(req, 'UPDATE consommations SET %s WHERE IDconso=?' %
                         ', '.join('%s=?' % field for field in FIELDS))
        self.assertEqual(len(rows[0]), 21)
        self.assertIsNone(rows[0][14])  # IDprestation NULL reste une ecriture explicite.
        self.assertEqual(rows[0][9], 0)  # verrouillage historique conserve.

    def test_deux_postes_ecritures_disjointes_attendent_le_verrou(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp) / 'concurrent.db')
            entered, done = threading.Event(), threading.Event()
            errors = []
            with closing(sqlite3.connect(path)) as a:
                schema(a)
                a.executemany('INSERT INTO consommations (IDconso, etat) VALUES (?, ?)',
                              [(1, 'attente'), (2, 'attente')])
                a.commit()
                a.execute("UPDATE consommations SET etat='present' WHERE IDconso=1")

                class WaitingDB(Database):
                    def Executermany(self, *args, **kwargs):
                        entered.set()
                        return super().Executermany(*args, **kwargs)

                def poste_b():
                    try:
                        with closing(sqlite3.connect(path, timeout=5)) as b:
                            saver(WaitingDB(b))(grille([conso(1), conso(2, 'modification', 'reservation')]))
                    except Exception as error:
                        errors.append(error)
                    finally:
                        done.set()

                thread = threading.Thread(target=poste_b)
                thread.start()
                try:
                    self.assertTrue(entered.wait(5))
                    self.assertFalse(done.wait(0.1), 'B doit attendre le verrou de A')
                finally:
                    a.commit()
                    thread.join(6)
                self.assertFalse(thread.is_alive())
                self.assertEqual(errors, [])
                self.assertEqual(a.execute('SELECT etat FROM consommations ORDER BY IDconso').fetchall(),
                                 [('present',), ('reservation',)])


class ExecutermanyDialectTests(unittest.TestCase):
    def test_deux_dialectes_et_commit_false(self):
        execute = method(ROOT / 'noethys/GestionDB.py', 'DB', 'Executermany', {})
        for network, placeholder in [(False, '?'), (True, '%s')]:
            with self.subTest(network=network):
                db = SimpleNamespace(isNetwork=network, cursor=Mock(), connexion=Mock())
                rows = [(None, 1), ('reservation', 2)]
                execute(db, 'UPDATE consommations SET etat=? WHERE IDconso=?', rows, commit=False)
                db.cursor.executemany.assert_called_once_with(
                    'UPDATE consommations SET etat=%s WHERE IDconso=%s' % (placeholder, placeholder), rows)
                db.connexion.commit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
