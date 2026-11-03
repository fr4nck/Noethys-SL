# -*- coding: utf-8 -*-
"""D7 : tests de contrat de transaction MySQL, sans serveur et sans reseau."""
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'noethys'))
from Utils.UTILS_Partenaires_D1 import AnnuairePartenaires, PartenairesErreur
from Utils.UTILS_Partenaires_D2 import RegistreConventions, ConventionInvalide
from Utils.UTILS_Partenaires_D34 import InterventionsPartenaires


class FakeMySQL:
    def __init__(self, autocommit=False, begin_error=False):
        self.autocommit = autocommit
        self.begin_error = begin_error
        self.events = []
    def get_autocommit(self):
        return self.autocommit
    def begin(self):
        self.events.append('begin')
        if self.begin_error:
            raise RuntimeError('START TRANSACTION impossible')
    def commit(self):
        self.events.append('commit')
    def rollback(self):
        self.events.append('rollback')


class TestsTransactionsMySQLContrat(unittest.TestCase):
    def moteur(self, kind, conn):
        return kind(conn, dialecte='mysql', autoriser=lambda a,b: True)

    def test_trois_moteurs_refusent_autocommit(self):
        for kind in (AnnuairePartenaires, RegistreConventions, InterventionsPartenaires):
            with self.subTest(kind=kind.__name__):
                with self.assertRaises((PartenairesErreur, ConventionInvalide)):
                    self.moteur(kind, FakeMySQL(autocommit=True))

    def test_trois_moteurs_refusent_driver_non_contractuel(self):
        for kind in (AnnuairePartenaires, RegistreConventions, InterventionsPartenaires):
            with self.subTest(kind=kind.__name__):
                with self.assertRaises((PartenairesErreur, ConventionInvalide)):
                    self.moteur(kind, object())

    def test_d1_begin_commit_et_avant_operation(self):
        conn = FakeMySQL()
        m = self.moteur(AnnuairePartenaires, conn)
        self.assertEqual(m._mutation(lambda: (conn.events.append('write'),'ok')[1]), 'ok')
        self.assertEqual(conn.events,['begin','write','commit'])

    def test_d2_begin_commit_et_avant_operation(self):
        conn = FakeMySQL()
        m = self.moteur(RegistreConventions, conn)
        self.assertEqual(m._ecrire(lambda: (conn.events.append('write'),'ok')[1]), 'ok')
        self.assertEqual(conn.events,['begin','write','commit'])

    def test_d34_begin_commit_et_avant_operation(self):
        conn = FakeMySQL()
        m = self.moteur(InterventionsPartenaires, conn)
        self.assertEqual(m._ecrire(lambda: (conn.events.append('write'),'ok')[1]), 'ok')
        self.assertEqual(conn.events,['begin','write','commit'])

    def test_trois_moteurs_rollback_sur_exception(self):
        def f():
            raise RuntimeError('defaut journal simule')
        for kind,method in ((AnnuairePartenaires,'_mutation'),
                            (RegistreConventions,'_ecrire'),
                            (InterventionsPartenaires,'_ecrire')):
            with self.subTest(kind=kind.__name__):
                conn=FakeMySQL()
                with self.assertRaises(RuntimeError):
                    getattr(self.moteur(kind, conn), method)(f)
                self.assertEqual(conn.events,['begin','rollback'])

    def test_aucune_operation_si_begin_echoue(self):
        for kind,method in ((AnnuairePartenaires,'_mutation'),
                            (RegistreConventions,'_ecrire'),
                            (InterventionsPartenaires,'_ecrire')):
            with self.subTest(kind=kind.__name__):
                conn=FakeMySQL(begin_error=True)
                with self.assertRaises(RuntimeError):
                    getattr(self.moteur(kind,conn),method)(lambda: conn.events.append('write'))
                self.assertEqual(conn.events,['begin'])

if __name__ == '__main__': unittest.main()
