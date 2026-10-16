# -*- coding: utf-8 -*-
"""Données exclusivement synthétiques ; journal SQL réel et contrôles natifs wx."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401
import datetime as dt
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'noethys'))
from Utils import UTILS_Assiduite as stats


class Adapter:
    isNetwork = False

    def __init__(self, path):
        self.connexion = sqlite3.connect(path, timeout=15)
        self.cursor = self.connexion.cursor()

    def ExecuterReq(self, sql):
        self.cursor.execute(sql)
        return True

    def ResultatReq(self):
        return self.cursor.fetchall()

    def Commit(self):
        self.connexion.commit()

    def Close(self):
        self.connexion.close()


def schema(db):
    for sql in (
        'CREATE TABLE inscriptions (IDinscription INTEGER PRIMARY KEY, IDfamille INTEGER)',
        'CREATE TABLE consommations (IDconso INTEGER PRIMARY KEY, IDinscription INTEGER, IDindividu INTEGER, IDactivite INTEGER, date DATE, etat VARCHAR(20), montant INTEGER)',
        'CREATE TABLE individus (IDindividu INTEGER PRIMARY KEY, nom VARCHAR(50), prenom VARCHAR(50))',
        'INSERT INTO inscriptions VALUES (1, 10)',
    ):
        db.cursor.execute(sql)
    db.Commit()


def insert(db, ident, day='2026-10-01', state='reservation', child=1, inscription=1, activity=1):
    db.cursor.execute("INSERT INTO consommations VALUES (%d, %d, %d, %d, '%s', '%s', 0)" %
                      (ident, inscription, child, activity, day, state))


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='nsl-assiduite-synthetic-')
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / 'test.sqlite')
        self.db = Adapter(self.path)
        self.addCleanup(self.db.Close)
        schema(self.db)

    def report(self):
        self.db.Commit()
        result = stats.read(self.db, '2026-10-01', '2026-10-31', [1])
        return result

    def test_pas_de_migration_implicite_et_aucun_faux_zero(self):
        insert(self.db, 1)
        row = self.report()['children'][0]
        self.assertIsNone(row['cancellation_rate'])
        self.assertIsNone(row['absence_rate'])
        self.assertIsNone(stats.status(self.db))

    def test_anciens_non_inventes_et_activation_idempotente(self):
        insert(self.db, 1)
        self.db.Commit()
        first = stats.activate(self.db)
        self.assertEqual(stats.activate(self.db), first)
        self.db.cursor.execute("UPDATE consommations SET etat='absenti' WHERE IDconso=1")
        row = self.report()['children'][0]
        self.assertEqual(row['reserved'], 0)
        self.assertEqual(row['absent'], 1)
        self.assertIsNone(row['cancellation_rate'])

    def test_suppression_historisee_dans_la_transaction(self):
        stats.activate(self.db)
        insert(self.db, 1)
        self.db.Commit()
        self.db.cursor.execute('DELETE FROM consommations WHERE IDconso=1')
        self.db.connexion.rollback()
        row = self.report()['children'][0]
        self.assertEqual((row['reserved'], row['cancelled']), (1, 0))
        self.db.cursor.execute('DELETE FROM consommations WHERE IDconso=1')
        row = self.report()['children'][0]
        self.assertEqual((row['reserved'], row['cancelled'], row['cancellation_rate']), (1, 1, 100))

    def test_insertion_annulee_ne_cree_pas_de_reservation(self):
        stats.activate(self.db)
        insert(self.db, 1)
        self.db.connexion.rollback()
        self.assertEqual(self.report()['children'], [])

    def test_journee_remplace_demi_journees_sans_fausse_annulation(self):
        stats.activate(self.db)
        insert(self.db, 1)
        insert(self.db, 2)
        insert(self.db, 3)
        self.db.cursor.execute('DELETE FROM consommations')
        insert(self.db, 4)
        row = self.report()['children'][0]
        self.assertEqual((row['reserved'], row['cancelled']), (1, 0))

    def test_attente_refus_ne_sont_pas_reservations(self):
        stats.activate(self.db)
        insert(self.db, 1, state='attente')
        insert(self.db, 2, state='refus')
        self.db.cursor.execute('DELETE FROM consommations WHERE IDconso=2')
        self.assertEqual(self.report()['children'], [])
        self.db.cursor.execute("UPDATE consommations SET etat='reservation' WHERE IDconso=1")
        self.assertEqual(self.report()['children'][0]['reserved'], 1)

    def test_separation_famille_enfant_activite_et_date(self):
        stats.activate(self.db)
        self.db.cursor.execute('INSERT INTO inscriptions VALUES (2, 20)')
        insert(self.db, 1)
        insert(self.db, 2, child=2)
        insert(self.db, 3, child=1, inscription=2)
        insert(self.db, 4, day='2026-10-02')
        insert(self.db, 5, activity=2)
        self.db.cursor.execute('DELETE FROM consommations WHERE IDconso=1')
        result = self.report()
        family = next(r for r in result['families'] if r['family'] == 10)
        self.assertEqual((family['reserved'], family['cancelled']), (3, 1))
        self.assertAlmostEqual(family['cancellation_rate'], 100 / 3)
        self.assertEqual(next(r for r in result['families'] if r['family'] == 20)['cancelled'], 0)

    def test_pointage_tardif_et_absence_partielle_pas_confondues(self):
        stats.activate(self.db)
        insert(self.db, 1)
        insert(self.db, 2)
        self.db.cursor.execute("UPDATE consommations SET etat='present' WHERE IDconso=1")
        self.assertEqual(self.report()['children'][0]['pending'], 1)
        self.assertIsNone(self.report()['children'][0]['absence_rate'])
        self.db.cursor.execute("UPDATE consommations SET etat='absentj' WHERE IDconso=2")
        row = self.report()['children'][0]
        self.assertEqual((row['pointed'], row['absent'], row['partial']), (1, 0, 1))
        self.db.cursor.execute("UPDATE consommations SET etat='absenti' WHERE IDconso=1")
        row = self.report()['children'][0]
        self.assertEqual((row['pointed'], row['absent'], row['unjustified'], row['absence_rate']), (1, 1, 1, 100))

    def test_pointage_supprime_pas_reclasse_en_annulation(self):
        stats.activate(self.db)
        insert(self.db, 1)
        self.db.cursor.execute("UPDATE consommations SET etat='present' WHERE IDconso=1")
        self.db.cursor.execute('DELETE FROM consommations')
        self.assertEqual(self.report()['children'][0]['cancelled'], 0)

    def test_montant_inchange_aucun_evenement_en_plus(self):
        stats.activate(self.db)
        insert(self.db, 1)
        self.db.Commit()
        before = stats.query(self.db, 'SELECT COUNT(*) FROM ' + stats.TABLE)[0][0]
        self.db.cursor.execute('UPDATE consommations SET montant=123 WHERE IDconso=1')
        self.assertEqual(stats.query(self.db, 'SELECT COUNT(*) FROM ' + stats.TABLE)[0][0], before)

    def test_concurrence_quatre_postes_et_lecture_sans_ecriture(self):
        stats.activate(self.db)
        def work(ident):
            db = Adapter(self.path)
            try:
                insert(db, ident, child=ident)
                db.Commit()
                db.cursor.execute('DELETE FROM consommations WHERE IDconso=%d' % ident)
                if ident % 2:
                    db.Commit()
                else:
                    db.connexion.rollback()
            finally:
                db.Close()
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(work, range(1, 9)))
        before = self.db.connexion.total_changes
        result = self.report()
        self.assertEqual((len(result['children']), sum(r['cancelled'] for r in result['children'])), (8, 4))
        self.assertEqual(self.db.connexion.total_changes, before)

    def test_journal_incomplet_ne_retourne_pas_un_taux(self):
        stats.activate(self.db)
        self.db.cursor.execute('DROP TRIGGER ' + stats.TRIGGERS['delete'])  # base temporaire de ce test uniquement
        with self.assertRaises(RuntimeError):
            self.report()
        with self.assertRaisesRegex(RuntimeError, 'interrompu'):
            stats.activate(self.db)

    def test_filtres_invalides(self):
        for args in [('2026-11-01', '2026-10-01', [1]), ('x', '2026-10-01', [1]),
                     ('2026-10-01', '2026-10-31', []), ('2026-10-01', '2026-10-31', ['1) OR 1=1'])]:
            with self.assertRaises(ValueError):
                stats.read(self.db, *args)

    def test_copie_sqlite_conserve_journal_et_declencheurs(self):
        stats.activate(self.db)
        insert(self.db, 1)
        self.db.Commit()
        copy = Adapter(str(Path(self.temp.name) / 'restauration.sqlite'))
        try:
            self.db.connexion.backup(copy.connexion)
            self.assertEqual(stats.read(copy, '2026-10-01', '2026-10-31', [1]), self.report())
            copy.cursor.execute('DELETE FROM consommations')
            copy.Commit()
            self.assertEqual(stats.read(copy, '2026-10-01', '2026-10-31', [1])['children'][0]['cancelled'], 1)
            self.assertEqual(self.report()['children'][0]['cancelled'], 0)
        finally:
            copy.Close()

    def test_taux_familial_pondere_et_dates_futures_exclues_du_pointage(self):
        rows = [(10, 1, 1, '2026-10-01', 'absentj'),
                (10, 2, 1, '2026-10-01', 'present'),
                (10, 2, 1, '2026-10-02', 'present'),
                (10, 2, 1, '2026-10-03', 'present'),
                (10, 2, 1, '2026-10-10', 'absenti')]
        result = stats.summarize(rows, today=dt.date(2026, 10, 5))
        row = result['families'][0]
        self.assertEqual((row['pointed'], row['absent'], row['absence_rate']), (4, 1, 25))

    def test_reinscription_meme_jour_retire_annulation(self):
        stats.activate(self.db)
        insert(self.db, 1)
        self.db.cursor.execute('DELETE FROM consommations')
        insert(self.db, 2)
        row = self.report()['children'][0]
        self.assertEqual((row['reserved'], row['cancelled'], row['cancellation_rate']), (1, 0, 0))


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import wx
        cls.app = wx.GetApp() or wx.App(False)

    def test_dialogue_natif_sans_base_ni_activation(self):
        from Dlg import DLG_Assiduite as ui
        from Ctrl import CTRL_Selection_activites
        import wx
        class Activities(wx.Panel):
            def GetActivites(self):
                return [1]
        with patch.object(CTRL_Selection_activites, 'CTRL', Activities), \
             patch.object(ui.UTILS_Identification, 'GetDictUtilisateur', return_value={'profil': 'perso'}), \
             patch.object(ui.GestionDB, 'DB', side_effect=AssertionError('Aucun accès implicite')):
            dialog = ui.Dialog(None)
            try:
                self.assertFalse(dialog.enable.IsEnabled())
                self.assertEqual(dialog.list.GetColumnCount(), 10)
                dialog.report = stats.summarize([(10, 1, 1, '2026-10-01', 'absenti')])
                dialog.OnGroup()
                self.assertEqual(dialog.list.GetItemText(0, 3), '—')
                self.assertEqual(dialog.list.GetItemText(0, 7), '100,0 %')
            finally:
                dialog.Destroy()


if __name__ == '__main__':
    unittest.main()
