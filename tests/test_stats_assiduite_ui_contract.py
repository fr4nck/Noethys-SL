# -*- coding: utf-8 -*-
"""AST contracts: dormant UI is additive to existing wx statistics."""
import ast
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
DLG=ROOT/'noethys'/'Dlg'/'DLG_Stats.py'


class AssiduiteUiContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=DLG.read_text(encoding='utf-8')
        cls.ast=ast.parse(cls.source)
        cls.dialogue=next(n for n in cls.ast.body
                          if isinstance(n,ast.ClassDef) and n.name=='Dialog')
    def test_new_rubric_registered_without_overwriting_old_rubrics(self):
        self.assertIn('ASSIDUITE.preparer_pages(MODELES, self.listeObjets)',self.source)
        self.assertIn('INDIVIDUS.Tableau_nombre_individus()',self.source)
        self.assertIn('FAMILLES.Tableau_qf_tarifs()',self.source)
    def test_export_action_is_connected_to_a_real_button(self):
        self.assertIn('self.bouton_export_assiduite = wx.Button',self.source)
        self.assertIn('self.Bind(wx.EVT_BUTTON, self.OnBoutonExporterAssiduite,',self.source)
        names={node.name for node in self.dialogue.body if isinstance(node,ast.FunctionDef)}
        self.assertIn('OnBoutonExporterAssiduite',names)
    def test_export_keeps_atomic_write_and_read_only_adapter(self):
        method=next(node for node in self.dialogue.body
                    if isinstance(node,ast.FunctionDef) and node.name=='OnBoutonExporterAssiduite')
        text=ast.get_source_segment(self.source,method)
        self.assertIn('ASSIDUITE.est_disponible',text)
        self.assertIn('ASSIDUITE.obtenir_resultat',text)
        self.assertIn('os.replace',text)
        self.assertIn('connexion.Close()',text)
    def test_no_new_database_migration_or_bill_recalculation(self):
        method=next(node for node in self.dialogue.body
                    if isinstance(node,ast.FunctionDef) and node.name=='OnBoutonExporterAssiduite')
        text=ast.get_source_segment(self.source,method)
        for bad in ('INSERT INTO','UPDATE ','DELETE FROM','RecalculerToutesPrestations'):
            self.assertNotIn(bad,text)


if __name__=='__main__':
    unittest.main()
