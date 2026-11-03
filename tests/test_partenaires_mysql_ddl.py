# -*- coding: utf-8 -*-
"""Audit statique des DDL MySQL 5.7 D1, D2 et D3-D4.

Ce test ne remplace pas une recette sur un serveur MySQL 5.7 reel.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ('d1', 'd2', 'd34')


def collecter():
    root = ROOT / 'noethys' / 'Data' / 'Migrations'
    resultats = []
    for lot in SCRIPTS:
        texte = (root / ('partenaires_%s_mysql57.sql' % lot)).read_text(encoding='utf-8')
        sql = '\n'.join(ligne for ligne in texte.splitlines()
                        if not ligne.lstrip().startswith('--'))
        resultats.append((lot, sql))
    return resultats


class SchemaPartenairesMySQL57Statique(unittest.TestCase):
    def test_nouvelles_tables_seulement(self):
        for nom, sql in collecter():
            with self.subTest(lot=nom):
                self.assertNotRegex(sql, r'(?im)^\s*(?:ALTER|DROP|TRUNCATE|REPLACE|DELETE|UPDATE)\s')
                tables = re.findall(r'CREATE\s+TABLE\s+(partenaires_\w+)', sql, re.I)
                self.assertTrue(tables)
                self.assertEqual(len(tables), len(set(tables)))

    def test_moteur_innodb_charset_utf8mb4(self):
        for nom, sql in collecter():
            with self.subTest(lot=nom):
                total = len(re.findall(r'CREATE\s+TABLE\b', sql, re.I))
                self.assertEqual(total, len(re.findall(r'ENGINE\s*=\s*InnoDB', sql, re.I)))
                self.assertEqual(total, len(re.findall(r'CHARSET\s*=\s*utf8mb4', sql, re.I)))

    def test_ordre_des_cles_etrangeres(self):
        creees = set()
        for nom, sql in collecter():
            for morceau in re.split(r'(?i)\bCREATE\s+TABLE\s+', sql)[1:]:
                table = morceau.split('(', 1)[0].strip().split()[0]
                refs = re.findall(r'REFERENCES\s+(partenaires_\w+)\s*\(', morceau, re.I)
                self.assertTrue(all(ref in creees for ref in refs),
                                '%s %s vers %s' % (nom, table, [r for r in refs if r not in creees]))
                creees.add(table)
        self.assertEqual(len(creees), 15)

    def test_pas_de_schema_comptable_parallele(self):
        for nom, sql in collecter():
            with self.subTest(lot=nom):
                self.assertNotRegex(sql, r'(?i)\bpartenaires_factures_officielles\b')
                self.assertNotRegex(sql, r'(?i)\bpartenaires_bordereaux\b')
                self.assertNotRegex(sql, r'(?i)\bALTER\s+TABLE\s+(?:factures|prestations|familles|comptes_payeurs)\b')

    def test_pas_de_fonction_mysql_8_ou_check_non_applique(self):
        for nom, sql in collecter():
            with self.subTest(lot=nom):
                self.assertNotRegex(sql, r'(?i)\bGENERATED\s+ALWAYS\b')
                self.assertNotRegex(sql, r'(?i)\bCHECK\s*\(')


if __name__ == '__main__':
    unittest.main()
