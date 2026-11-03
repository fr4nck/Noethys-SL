# -*- coding: utf-8 -*-
"""Verification documentaire du DDL MySQL 5.7, PAS un test MySQL runtime."""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=['d1','d2','d34','d5','d6']


def collecter():
    chemin=ROOT/'noethys/Data/Migrations'
    return [(code, '\n'.join(line for line in (chemin/('partenaires_%s_mysql57.sql'%code)).read_text(encoding='utf-8').splitlines() if not line.lstrip().startswith('--')))
            for code in SCRIPTS]

class SchemaMySQL57Statique(unittest.TestCase):
    def test_01_only_new_partners_tables(self):
        for name,sql in collecter():
            with self.subTest(lot=name):
                self.assertNotRegex(sql, r'(?im)^\s*(?:ALTER|DROP|TRUNCATE|REPLACE|DELETE|UPDATE)\s')
                created=re.findall(r'CREATE\s+TABLE\s+([\w]+)',sql,re.I)
                self.assertTrue(created)
                self.assertTrue(all(x.startswith('partenaires_') for x in created))
                self.assertEqual(len(created),len(set(created)))

    def test_02_all_tables_explicit_InnoDB_utf8mb4(self):
        for name,sql in collecter():
            with self.subTest(lot=name):
                tables=len(re.findall(r'CREATE\s+TABLE',sql,re.I))
                self.assertEqual(tables,len(re.findall(r'ENGINE\s*=\s*InnoDB',sql,re.I)))
                self.assertEqual(tables,len(re.findall(r'CHARSET\s*=\s*utf8mb4',sql,re.I)))

    def test_03_foreign_references_defined_in_migration_order(self):
        defined=set()
        for name,sql in collecter():
            for chunk in re.split(r'(?i)\bCREATE\s+TABLE\s+',sql)[1:]:
                table=chunk.split('(',1)[0].strip().split()[0]
                refs=re.findall(r'REFERENCES\s+(partenaires_\w+)\s*\(',chunk,re.I)
                self.assertTrue(all(r in defined for r in refs),
                                '%s %s depends on absent %s'%(name,table,[r for r in refs if r not in defined]))
                defined.add(table)
        self.assertEqual(len(defined),22)

    def test_04_d6_no_tax_columns(self):
        d6=dict(collecter())['d6']
        self.assertNotRegex(d6, r'(?i)\b(?:taux_tva|montant_tva|total_ht|total_ttc)\b')
        self.assertRegex(d6, r'(?i)UNIQUE\s+KEY\s+uq_part_facture_lot\s*\(IDbordereau\)')
        self.assertRegex(d6, r'(?i)UNIQUE\s+KEY\s+uq_part_facture_exercice\s*\(exercice\s*,\s*ordre\)')
        self.assertRegex(d6, r'(?i)SELECT\s+IDbordereau\s+FROM\s+partenaires_bordereaux\s+LIMIT\s+0')

    def test_05_no_mysql8_features_and_historical_writes(self):
        forbidden=(r'(?i)\bGENERATED\s+ALWAYS\b',r'(?i)\bCHECK\s*\(',
                   r'(?i)\bCREATE\s+(?:OR\s+REPLACE\s+)?VIEW\b',
                   r'(?i)\bALTER\s+TABLE\s+(?:factures|prestations|familles|comptes_payeurs)\b')
        for name,sql in collecter():
            with self.subTest(lot=name):
                for expr in forbidden: self.assertNotRegex(sql,expr)

if __name__=='__main__':unittest.main()
