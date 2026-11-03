# -*- coding: utf-8 -*-
"""Rendu hors-ligne, uniquement apres lecture du registre D6."""
import io
import unittest
from pathlib import Path
import sys
from zipfile import ZipFile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'noethys'))
sys.path.insert(0,str(ROOT/'tests'))
import test_partenaires_d6 as d6_fixtures
from Utils.UTILS_Partenaires_D6 import FactureInvalide,FactureIntegrite
from Utils.UTILS_Partenaires_D7_Documents import creer_docx_facture,_construire

class DocumentsPartenairesD7(unittest.TestCase):
    def setUp(self):
        self.fixture=d6_fixtures.D6Tests('test_01_aucune_tva_comptable_et_montant_unique')
        self.fixture.setUp()
        self.fixture.valider_lot()
        self.record=self.fixture.enregistrer()
    def tearDown(self):self.fixture.tearDown()

    def pdf_style(self):
        blob=creer_docx_facture(self.fixture.d6,self.record['IDfacture_partenaire'],acteur='direction')
        with ZipFile(io.BytesIO(blob)) as z:
            xml=''.join(z.read(n).decode('utf-8') for n in z.namelist() if n=='word/document.xml' or n.startswith('word/header'))
        return blob,xml

    def test_01_docx_offline_and_registered_number(self):
        blob,xml=self.pdf_style()
        self.assertGreater(len(blob),10000)
        for s in ('FACTURE','PMSL-2025-000001','NON TRANSMISE','20,00 EUR'):
            self.assertIn(s,xml)
        self.assertEqual(self.fixture.conn.execute('SELECT COUNT(*) FROM partenaires_factures_evenements').fetchone()[0],1)

    def test_02_no_transmission_or_payment_effect(self):
        self.pdf_style(); self.pdf_style()
        rec=self.fixture.d6.lire_facture(self.record['IDfacture_partenaire'],acteur='direction')
        self.assertFalse(rec['transmise'] or rec['pdf_genere'])
        self.assertEqual(self.fixture.conn.execute('SELECT COUNT(*) FROM partenaires_factures_officielles').fetchone()[0],1)

    def test_03_denied_read_does_not_create_document(self):
        with self.assertRaises(Exception):
            creer_docx_facture(self.fixture.d6,self.record['IDfacture_partenaire'],acteur='observateur')

    def test_04_no_unchecked_record(self):
        with self.assertRaises(FactureInvalide):
            creer_docx_facture({},self.record['IDfacture_partenaire'],acteur='direction')

    def test_05_detects_tampered_document(self):
        self.fixture.conn.execute('UPDATE partenaires_factures_officielles SET donnees_json=?',('{}',))
        self.fixture.conn.commit()
        with self.assertRaises(FactureIntegrite):
            creer_docx_facture(self.fixture.d6,self.record['IDfacture_partenaire'],acteur='direction')

    def test_06_no_implicit_tax_computation(self):
        blob,xml=self.pdf_style()
        self.assertNotIn('Taux TVA',xml)
        self.assertNotIn('TOTAL TTC',xml)
        self.assertIn('Mention fiscale',xml)

    def test_07_rejects_forged_amount(self):
        doc=self.fixture.d6.lire_facture(self.record['IDfacture_partenaire'],acteur='direction')['facture']
        doc['total_eur']='20.01'
        with self.assertRaises(FactureIntegrite):_construire(doc)

    def test_08_rejects_invalid_recipient(self):
        doc=self.fixture.d6.lire_facture(self.record['IDfacture_partenaire'],acteur='direction')['facture']
        doc['destinataire'].pop('adresse_ligne1')
        with self.assertRaises(FactureInvalide):_construire(doc)

if __name__=='__main__':unittest.main()
