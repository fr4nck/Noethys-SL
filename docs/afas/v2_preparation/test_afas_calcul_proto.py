import unittest
from afas_calcul_proto import calculate, CalculAFASInvalide
S={(1,11)}
P={"qualified":True,"mode":"Périscolaire","include_garderie_realisee":False,
   "billable_minutes":lambda key, intervals: sum(b-a for a,b in intervals)}
def row(category="accueil", start=480,end=600, individual=1, group=11, aeeh=False):
 return dict(IDactivite=1,IDgroupe=group,individual=individual,date="2026-10-01",
             unit_id=1,category=category,start=start,end=end,aeeh=aeeh)
class Tests(unittest.TestCase):
 def test_accueil(self): self.assertEqual(calculate([row()],S,P)["heures_realisees"],2)
 def test_facture(self): self.assertEqual(calculate([row()],S,P)["heures_facturees_caf"],2)
 def test_annexe_ignored(self): self.assertEqual(calculate([row(),row("annexe")],S,P)["heures_realisees"],2)
 def test_site_excluded(self): self.assertEqual(calculate([row(group=77)],S,P)["heures_realisees"],0)
 def test_garderie_matin(self):
  self.assertEqual(calculate([row(),row("garderie_matin",420,480)],S,P)["garderie_matin"],1)
 def test_garderie_soir(self):
  self.assertEqual(calculate([row(),row("garderie_soir",600,660)],S,P)["garderie_soir"],1)
 def test_garderie_separate(self):
  x=calculate([row(),row("garderie_matin",420,480)],S,P)
  self.assertEqual(x["heures_facturees_caf"],2)
 def test_garderie_realisee_if_authorized(self):
  p=dict(P,include_garderie_realisee=True)
  self.assertEqual(calculate([row(),row("garderie_matin",420,480)],S,p)["heures_realisees"],3)
 def test_aeeh_subset(self):
  x=calculate([row(aeeh=True)],S,P)
  self.assertEqual(x["heures_realisees_aeeh"],2)
 def test_overlap_rejected(self):
  with self.assertRaises(CalculAFASInvalide):calculate([row(),row(start=540,end=630)],S,P)
 def test_not_qualified(self):
  with self.assertRaises(CalculAFASInvalide):calculate([row()],S,dict(P,qualified=False))
 def test_no_billing_rule(self):
  with self.assertRaises(CalculAFASInvalide):calculate([row()],S,dict(P,billable_minutes=None))
 def test_missing_garderie_rule(self):
  p=dict(P);del p["include_garderie_realisee"]
  with self.assertRaises(CalculAFASInvalide):calculate([row()],S,p)
 def test_aeeh_conflict(self):
  with self.assertRaises(CalculAFASInvalide):calculate([row(),row(aeeh=True,start=600,end=630)],S,P)
 def test_unknown_category(self):
  with self.assertRaises(CalculAFASInvalide):calculate([row(category="inconnue")],S,P)
 def test_duplicate_consumption_id_rejected(self):
  a=row(); a["IDconso"]=101
  b=row(start=600,end=630); b["IDconso"]=101
  with self.assertRaises(CalculAFASInvalide): calculate([a,b],S,P)
 def test_billable_over_day_rejected(self):
  p=dict(P,billable_minutes=lambda key, intervals: 1500)
  with self.assertRaises(CalculAFASInvalide): calculate([row()],S,p)
 def test_garderie_rule_numeric_rejected(self):
  p=dict(P,include_garderie_realisee=1)
  with self.assertRaises(CalculAFASInvalide): calculate([row()],S,p)
if __name__=="__main__": unittest.main()
