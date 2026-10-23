import unittest
from afas_referentiel import *

MATRIX = {
 ('ALSH', 'Périscolaire'): ('Bais +6 ans','Bais -6 ans','Moutiers','La Guerche-de-Bretagne'),
 ('ALSH', 'Extrascolaire'): ('Bais +6 ans','Bais -6 ans','Moutiers','La Guerche-de-Bretagne','Minicamps 6/8','Minicamps 8/10'),
 ('ALSH Ados', 'Périscolaire'): ('Bais Club Ados',),
 ('ALSH Ados', 'Extrascolaire'): ('Bais Club Ados','Minicamps Ados'),
}
class ReferentielTests(unittest.TestCase):
 def setUp(self):
  self.rows = []
  self.catalog = {}
  groups = {}
  for key, labels in MATRIX.items():
   self.catalog[key] = {}
   for label in labels:
    logical = key[0]
    if (logical,label) not in groups:
     a = 101 if logical == 'ALSH' else 102
     g = len(groups) + 201
     groups[logical,label] = (a,g)
     self.rows.append((a,g,logical,label))
    a,g = groups[logical,label]
    self.catalog[key][label] = dict(IDactivite=a, IDgroupe=g, verified=True)
 def test_all_four_contexts(self):
  self.assertEqual(len(verify_mapping(self.catalog,self.rows,MATRIX)),4)
 def test_exact_scope(self):
  ctx = verify_mapping(self.catalog,self.rows,MATRIX)[('ALSH','Périscolaire')]
  self.assertEqual(len(exact_scope(ctx,['Bais +6 ans','Bais -6 ans'],self.rows)),2)
 def test_cross_product_excluded(self):
  # Activite 101 + groupe 999 inexistant : un filtre sur activites seulement l'admettrait.
  ctx = verify_mapping(self.catalog,self.rows,MATRIX)[('ALSH','Périscolaire')]
  scope = exact_scope(ctx,['Bais +6 ans'],self.rows)
  self.assertFalse(eligible_consumption(dict(IDactivite=101,IDgroupe=999),scope))
 def test_mismatched_activity(self):
  self.catalog[('ALSH','Périscolaire')]['Moutiers']['IDactivite']=102
  with self.assertRaises(ReferentialError): verify_mapping(self.catalog,self.rows,MATRIX)
 def test_unverified(self):
  self.catalog[('ALSH','Périscolaire')]['Moutiers']['verified']=False
  with self.assertRaises(ReferentialError): verify_mapping(self.catalog,self.rows,MATRIX)
 def test_duplicate_binding(self):
  x=self.catalog[('ALSH','Périscolaire')]
  x['Moutiers']=x['Bais +6 ans'].copy()
  with self.assertRaises(ReferentialError): verify_mapping(self.catalog,self.rows,MATRIX)
 def test_cross_logical_activities(self):
  self.catalog[('ALSH Ados','Périscolaire')]['Bais Club Ados']=self.catalog[('ALSH','Périscolaire')]['Moutiers'].copy()
  with self.assertRaises(ReferentialError): verify_mapping(self.catalog,self.rows,MATRIX)
 def test_mini_peri(self):
  self.catalog[('ALSH','Périscolaire')]['Minicamps 6/8']=self.catalog[('ALSH','Extrascolaire')]['Minicamps 6/8'].copy()
  with self.assertRaises(ReferentialError): verify_mapping(self.catalog,self.rows,MATRIX)
 def test_bais_generic(self):
  self.catalog[('ALSH','Périscolaire')]['Bais']=self.catalog[('ALSH','Périscolaire')]['Moutiers'].copy()
  with self.assertRaises(ReferentialError): verify_mapping(self.catalog,self.rows,MATRIX)
 def test_obsolete(self):
  ctx=verify_mapping(self.catalog,self.rows,MATRIX)[('ALSH','Périscolaire')]
  scope_rows=[r for r in self.rows if r[3]!='Moutiers']
  with self.assertRaises(ReferentialError): exact_scope(ctx,['Moutiers'],scope_rows)
 def test_empty_selection(self):
  ctx=verify_mapping(self.catalog,self.rows,MATRIX)[('ALSH','Périscolaire')]
  with self.assertRaises(ReferentialError): exact_scope(ctx,[],self.rows)
 def test_row_collision(self):
  with self.assertRaises(ReferentialError): parse_groups([(1,8,'A','X'),(2,8,'B','Y')])

if __name__=='__main__': unittest.main()
