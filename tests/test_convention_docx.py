# -*- coding: utf-8 -*-
import datetime
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile
from xml.etree import ElementTree as ET

path = Path(__file__).parents[1] / 'noethys/Utils/UTILS_Convention_docx.py'
spec = importlib.util.spec_from_file_location('convention_docx', path)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)

class ConventionWordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.folder = Path(self.tmp.name)
        self.template = self.folder / 'modele.docx'
        self.output = self.folder / 'sortie.docx'
    def tearDown(self):
        self.tmp.cleanup()
    def package(self, xml):
        with zipfile.ZipFile(self.template, 'w') as z:
            z.writestr('word/document.xml', xml)
            z.writestr('word/media/logo.png', b'unchanged image')
    def xml(self, content):
        return '<w:document xmlns:w="%s"><w:body>%s</w:body></w:document>' % (engine.W, content)
    def test_champ_coupe_en_runs_style_et_media_conserves(self):
        self.package(self.xml('<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Nom : {FAMI</w:t></w:r><w:r><w:t>LLE_NOM} !</w:t></w:r></w:p>'))
        original = self.template.read_bytes()
        engine.GenererDOCX(self.template, {'{FAMILLE_NOM}': 'école & loisirs'}, self.output)
        self.assertEqual(self.template.read_bytes(), original)
        with zipfile.ZipFile(self.output) as z:
            root = ET.fromstring(z.read('word/document.xml'))
            self.assertEqual(''.join(root.itertext()), 'Nom : école & loisirs !')
            self.assertIsNotNone(root.find('.//{%s}b' % engine.W))
            self.assertEqual(z.read('word/media/logo.png'), b'unchanged image')
    def test_dates_planning_et_entete(self):
        self.package(self.xml('<w:p><w:r><w:t>{DATE} {PLANNING}</w:t></w:r></w:p>'))
        with zipfile.ZipFile(self.template, 'a') as z:
            z.writestr('word/header1.xml', '<w:hdr xmlns:w="%s"><w:p><w:r><w:t>{NOM}</w:t></w:r></w:p></w:hdr>' % engine.W)
        engine.GenererDOCX(self.template, {'{DATE}': datetime.date(2026,9,10), '{PLANNING}':'Ligne 1\nLigne 2', '{NOM}':'PMSL'},self.output)
        with zipfile.ZipFile(self.output) as z:
            self.assertIn(b'10/09/2026', z.read('word/document.xml'))
            self.assertIsNotNone(ET.fromstring(z.read('word/document.xml')).find('.//{%s}br' % engine.W))
            self.assertIn(b'PMSL', z.read('word/header1.xml'))
    def test_inconnu_ne_detruit_pas_destination_existante(self):
        self.package(self.xml('<w:p><w:r><w:t>{INCONNU}</w:t></w:r></w:p>'))
        self.output.write_bytes(b'ancien document')
        with self.assertRaisesRegex(ValueError, 'INCONNU'):
            engine.GenererDOCX(self.template, {}, self.output)
        self.assertEqual(self.output.read_bytes(), b'ancien document')
    def test_modele_ne_peut_etre_ecrase(self):
        with self.assertRaises(ValueError):
            engine.GenererDOCX(self.template, {}, self.template)
    def test_prefixes_ignorable_conserves(self):
        self.package('<w:document xmlns:w="%s" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:w14="urn:extra" mc:Ignorable="w14"><w:body><w:p><w:r><w:t>{NOM}</w:t></w:r></w:p></w:body></w:document>' % engine.W)
        engine.GenererDOCX(self.template, {'{NOM}':'Test'}, self.output)
        with zipfile.ZipFile(self.output) as z:
            self.assertIn(b'xmlns:w14="urn:extra"',z.read('word/document.xml'))
    def test_mots_cles_dans_tableau(self):
        self.package(self.xml('<w:tbl><w:tr><w:tc><w:p><w:r><w:t>{TOTAL}</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'))
        engine.GenererDOCX(self.template, {'{TOTAL}':123.45}, self.output)
        with zipfile.ZipFile(self.output) as z:
            self.assertIn(b'123,45',z.read('word/document.xml'))

if __name__ == '__main__':
    unittest.main()
