# -*- coding: utf-8 -*-
"""Client mysql simule, pas de serveur ni de profil PMSL."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / 'noethys' / 'Utils' / 'UTILS_MySQL_restore.py'
sp = importlib.util.spec_from_file_location('mysql_restore_pur', SOURCE)
R = importlib.util.module_from_spec(sp)
sp.loader.exec_module(R)


class FauxProcessus:
    def __init__(self, code=0, blocage=False, ignore_terminate=False):
        self.returncode = None if blocage else code
        self.blocage = blocage
        self.ignore_terminate = ignore_terminate
        self.terminations = 0
        self.kills = 0
        self.attentes = 0

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.attentes += 1
        if self.returncode is None:
            raise subprocess.TimeoutExpired(['mysql'], timeout)
        return self.returncode

    def terminate(self):
        self.terminations += 1
        if not self.ignore_terminate:
            self.returncode = -15

    def kill(self):
        self.kills += 1
        self.returncode = -9


class RestoreRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='noethys-restoration-test-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.sql = self.base / 'donnees avec espaces.sql'
        self.sql.write_bytes(b'CREATE TABLE temoin (id INT);\n')
        self.login = self.base / 'login avec espaces.cnf'
        self.login.write_text('[client]\npassword="MotDePasseSecret"\n', encoding='utf-8')

    def lancer(self, enfant, diagnostic=b'', **options):
        appels = []
        def popen(args, **kw):
            appels.append((args, kw))
            self.assertFalse(kw['shell'])
            self.assertEqual(kw['stdin'].read(), self.sql.read_bytes())
            self.assertEqual(kw['stdout'], subprocess.DEVNULL)
            kw['stderr'].write(diagnostic)
            kw['stderr'].flush()
            return enfant
        with mock.patch.object(R.subprocess, 'Popen', side_effect=popen):
            resultat = R.ImporterSQL(self.base / 'mysql client', self.login,
                                     self.sql, 'zz_test_base', **options)
        return resultat, appels

    def test_succes_arguments_sans_shell_et_stdin_binaire(self):
        retour, appels = self.lancer(FauxProcessus())
        self.assertIsNone(retour['erreur'])
        self.assertEqual(retour['code_retour'], 0)
        self.assertEqual(len(appels), 1)
        self.assertEqual(appels[0][0], [str(self.base / 'mysql client'),
             '--defaults-extra-file=' + str(self.login), 'zz_test_base'])

    def test_echec_sans_stdout_est_bloquant_et_diagnostic_masque(self):
        retour, _ = self.lancer(FauxProcessus(code=19),
            b'Access denied using password MotDePasseSecret',
            secrets=('MotDePasseSecret',))
        self.assertEqual(retour['code_retour'], 19)
        self.assertIn('19', retour['erreur'])
        self.assertNotIn('MotDePasseSecret', retour['erreur'])
        self.assertIn('[masque]', retour['diagnostic'])

    def test_fils_bloque_est_termine_et_attendu(self):
        enfant = FauxProcessus(blocage=True)
        appels = []
        retour, _ = self.lancer(enfant, duree_max=0.03, intervalle=0.01,
                                progression=lambda: appels.append(1))
        self.assertIn('maximale', retour['erreur'])
        self.assertGreaterEqual(enfant.terminations, 1)
        self.assertEqual(enfant.poll(), -15)
        self.assertGreaterEqual(len(appels), 1)

    def test_fils_resistant_est_tue_et_attendu(self):
        enfant = FauxProcessus(blocage=True, ignore_terminate=True)
        retour, _ = self.lancer(enfant, duree_max=0.03, intervalle=0.01)
        self.assertIsNotNone(retour['erreur'])
        self.assertEqual(enfant.terminations, 1)
        self.assertEqual(enfant.kills, 1)
        self.assertEqual(enfant.poll(), -9)

    def test_refuse_noms_de_base_options_et_fichier_absent(self):
        for base in ('--execute=DELETE', 'foo; DROP DATABASE x', '', 'ab\x00cd'):
            with self.subTest(base=base):
                with mock.patch.object(R.subprocess, 'Popen') as p:
                    resultat = R.ImporterSQL(self.base / 'mysql', self.login, self.sql, base)
                    self.assertIsNotNone(resultat['erreur'])
                    p.assert_not_called()
        with mock.patch.object(R.subprocess, 'Popen') as p:
            resultat = R.ImporterSQL(self.base / 'mysql', self.login,
                                     self.base / 'absent.sql', 'zz_test_base')
            self.assertIn('impossible', resultat['erreur'])
            p.assert_not_called()

    def test_ne_jamais_afficher_du_sql_dans_les_erreurs(self):
        retour, _ = self.lancer(FauxProcessus(code=1),
                                b'ERROR 1064: INSERT INTO enfants VALUES (1,\'ENFANT SECRET\')')
        self.assertNotIn('ENFANT SECRET', retour['diagnostic'])
        self.assertNotIn('ENFANT SECRET', retour['erreur'])

    def test_exception_de_progression_arrete_le_client(self):
        enfant = FauxProcessus(blocage=True)
        def stop():
            raise RuntimeError('fenetre fermee')
        retour, _ = self.lancer(enfant, duree_max=1, intervalle=0.001,
                                progression=stop)
        self.assertIn('interrompu', retour['erreur'])
        self.assertEqual(enfant.poll(), -15)


if __name__ == '__main__':
    unittest.main()