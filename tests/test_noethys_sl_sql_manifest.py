import importlib.util
import pathlib
import tempfile
import unittest
from unittest import mock

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_SQL_Integrite.py"
SPEC = importlib.util.spec_from_file_location("noethys_sql_integrite_test", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
AjouterManifesteIntegriteSQL = MODULE.AjouterManifesteIntegriteSQL
VerifierIntegriteSQL = MODULE.VerifierIntegriteSQL


class IntegriteSQLTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = pathlib.Path(self.temp.name) / 'dump.sql'

    def _ecrire(self, payload):
        self.path.write_bytes(payload)
        return self.path

    def test_manifeste_compatible_maitre_et_sql_original_identique(self):
        original = b'CREATE TABLE demo (id INT);\nINSERT INTO demo VALUES (1);\n'
        self._ecrire(original)
        AjouterManifesteIntegriteSQL(self.path)
        donnees = self.path.read_bytes()
        self.assertTrue(donnees.startswith(b'-- NOETHYS-SQL-MANIFEST-V1 '))
        self.assertIn(original, donnees)
        self.assertEqual(VerifierIntegriteSQL(self.path), (True, None))

    def test_tampering_de_meme_taille_detecte(self):
        self._ecrire(b'CREATE TABLE demo (id INT);\n')
        AjouterManifesteIntegriteSQL(self.path)
        self.path.write_bytes(self.path.read_bytes().replace(b'demo', b'dema'))
        self.assertIn('SHA-256', VerifierIntegriteSQL(self.path)[1])

    def test_troncature_detectee(self):
        self._ecrire(b'CREATE TABLE demo (id INT);\n')
        AjouterManifesteIntegriteSQL(self.path)
        self.path.write_bytes(self.path.read_bytes()[:-17])
        self.assertIsNotNone(VerifierIntegriteSQL(self.path)[1])

    def test_manifeste_absent_reste_compatible(self):
        self._ecrire(b'CREATE TABLE ancienne (id INT);\n')
        self.assertEqual(VerifierIntegriteSQL(self.path), (False, None))

    def test_fin_sans_entete_rejetee(self):
        self._ecrire(b'CREATE TABLE ancienne (id INT);\n-- NOETHYS-SQL-MANIFEST-END-V1 fake\n')
        self.assertIsNotNone(VerifierIntegriteSQL(self.path)[1])

    def test_fichier_vide_refuse(self):
        self._ecrire(b'')
        self.assertIsNotNone(VerifierIntegriteSQL(self.path)[1])

    def test_deuxieme_enveloppement_refuse_et_source_preservee(self):
        self._ecrire(b'CREATE TABLE demo (id INT);\n')
        AjouterManifesteIntegriteSQL(self.path)
        original = self.path.read_bytes()
        with self.assertRaises(ValueError):
            AjouterManifesteIntegriteSQL(self.path)
        self.assertEqual(self.path.read_bytes(), original)

    def test_replace_echoue_original_preserve_et_temporaire_nettoye(self):
        self._ecrire(b'CREATE TABLE demo (id INT);\n')
        with mock.patch.object(MODULE.os, 'replace', side_effect=OSError('simulation')):
            with self.assertRaises(OSError):
                AjouterManifesteIntegriteSQL(self.path)
        self.assertEqual(self.path.read_bytes(), b'CREATE TABLE demo (id INT);\n')
        self.assertEqual(list(pathlib.Path(self.temp.name).iterdir()), [self.path])

    def test_dump_plus_grand_que_le_bloc(self):
        self._ecrire(b'INSERT INTO t VALUES (1);\n' * 60000)
        AjouterManifesteIntegriteSQL(self.path)
        self.assertEqual(VerifierIntegriteSQL(self.path), (True, None))

    def test_changement_jeton_rejete(self):
        self._ecrire(b'CREATE TABLE demo (id INT);\n')
        AjouterManifesteIntegriteSQL(self.path)
        data = self.path.read_bytes()
        fin = data.rfind(b'-- NOETHYS-SQL-MANIFEST-END-V1 ')
        altered = bytearray(data)
        altered[fin+len(b'-- NOETHYS-SQL-MANIFEST-END-V1 ')] = ord(b'f') if altered[fin+len(b'-- NOETHYS-SQL-MANIFEST-END-V1 ')] != ord(b'f') else ord(b'e')
        self.path.write_bytes(bytes(altered))
        self.assertIn('differents', VerifierIntegriteSQL(self.path)[1])


if __name__ == '__main__':
    unittest.main()
