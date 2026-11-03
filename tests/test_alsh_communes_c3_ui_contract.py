# -*- coding: utf-8 -*-
"""Contrats source wx sans dependance au runtime graphique pour CI."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / 'noethys' / 'Dlg' / 'DLG_ALSH_Commune_C3.py'
SERVICE = ROOT / 'noethys' / 'Utils' / 'UTILS_ALSH_C3_Session.py'


class ContratInterfaceC3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = GUI.read_text(encoding='utf-8')
        cls.ast = ast.parse(cls.source)
        cls.service = SERVICE.read_text(encoding='utf-8')

    def test_01_syntaxe_importable_wx(self):
        self.assertTrue(self.ast.body)

    def test_02_une_seule_facade_moteur(self):
        self.assertIn('self.session=c3.SituationC3', self.source)
        self.assertIn('self.session.recalculer(', self.source)
        self.assertNotIn('importer_journees(', self.source)

    def test_03_perimetres_et_unites_explicitement_regles(self):
        for marker in ('self.session.perimetres()', 'self.service.unites(',
                       'Aucune activite ALSH selectionnee',
                       'Toutes les unites doivent etre classees',
                       'Ajouter les clauses des conventions signees'):
            with self.subTest(marker=marker):
                if marker == 'self.session.perimetres()':
                    self.assertIn('service.perimetres()',self.source)
                else:
                    self.assertIn(marker,self.source)

    def test_04_vue_nominative_exige_commune(self):
        self.assertIn('self.session.vue(self.resultat,self._filtre())',self.source)
        self.assertIn('Choisir une seule commune pour un export nominatif',self.source)
        self.assertIn("if nature!='anonyme' and code is None",self.source)

    def test_05_pas_de_migration_automatique(self):
        self.assertIn('ALSH C1/C2 non installe',self.source)
        self.assertNotIn('executescript(',self.source)
        self.assertNotIn('CREATE TABLE ',self.source)
        self.assertNotIn('ALTER TABLE ',self.source)

    def test_06_pieces_brouillons_sans_facture(self):
        self.assertIn('BROUILLON NON FACTURABLE',self.source)
        self.assertNotIn('ReqInsert("factures"',self.source)
        self.assertNotIn("ReqMAJ('factures'",self.source)

    def test_07_droits_controles_sur_lecture_et_exports(self):
        self.assertIn("droits.imposer('frequentation_lire_nominatif')",self.source)
        self.assertIn("'frequentation_export_nominatif': 'exporter'",self.service)
        self.assertIn("'communes_parametrer': 'modifier'",self.service)

    def test_08_compte_explicite_adresse_parent(self):
        self.assertIn('Corriger une date de demenagement',self.source)
        self.assertIn('ID individu ou representant',self.source)
        self.assertIn('self.service.confirmer_demenagement(',self.source)

    def test_09_csv_creation_exclusive(self):
        self.assertIn('c3.enregistrer_csv_nouveau(path,texte)',self.source)
        self.assertIn("with chemin.open('x',",self.service)

    def test_10_connexion_dediee_et_fermee(self):
        self.assertIn('GestionDB.DB(pooling=False)',self.source)
        self.assertIn('self.db.Close()',self.source)

if __name__ == '__main__': unittest.main()
