# -*- coding: utf-8 -*-
"""Static Q442/J5 integration contract. Does not import wx or connect to DB.

Used in GitHub CI to validate the exact submitted Noethys sources.
Real wx interaction/Windows installed and MySQL tests remain separate gates.
"""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLG = ROOT / 'noethys' / 'Dlg' / 'DLG_Stats.py'
OBJ = ROOT / 'noethys' / 'Utils' / 'UTILS_Stats_qf_objets.py'


def source_tree(path):
    source = path.read_text(encoding='utf-8')
    return source, ast.parse(source, filename=str(path))


def method(tree, cls, name):
    target = next(c for c in tree.body if isinstance(c, ast.ClassDef) and c.name == cls)
    return next(n for n in target.body if isinstance(n, ast.FunctionDef) and n.name == name)


class Q442J5ContractTests(unittest.TestCase):
    def test_sources_compile_without_wx_import(self):
        for path in (DLG,OBJ):
            source=path.read_text(encoding='utf-8')
            compile(source,str(path),'exec')

    def test_dialog_default_has_no_qf_config(self):
        _,tree=source_tree(DLG)
        ctor=method(tree,'Dialog','__init__')
        self.assertEqual([a.arg for a in ctor.args.args][-2:],
                         ['q442_configuration','q442_sites'])
        self.assertEqual(len(ctor.args.defaults),2)
        self.assertTrue(all(isinstance(a,ast.Constant) and a.value is None
                            for a in ctor.args.defaults))

    def test_dialog_optin_pages_only(self):
        source,_=source_tree(DLG)
        self.assertIn('if self._q442_configuration is not None:',source)
        self.assertIn('Q442.preparer_pages(MODELES, self.listeObjets,',source)
        self.assertNotIn('q442_configuration=ConfigurationMultisite(',source)

    def test_export_gates_and_atomic_output(self):
        _,tree=source_tree(DLG)
        handler=method(tree,'Dialog','OnBoutonExporterQ442')
        names={n.attr for n in ast.walk(handler) if isinstance(n,ast.Attribute)}
        for expected in ('est_disponible','obtenir_resultat',
                         'export_xlsx_aggreges','export_csv_lot_aggreges',
                         'mkstemp','replace','Close'):
            self.assertIn(expected,names)

    def test_historical_objects_not_replaced(self):
        source,_=source_tree(DLG)
        self.assertIn('FAMILLES.Tableau_qf_tarifs()',source)
        self.assertIn('FAMILLES.Graphe_qf_tarifs()',source)
        self.assertIn('INDIVIDUS.Texte_nombre_individus()',source)

    def test_new_exports_reuse_pinned_reader(self):
        source,tree=source_tree(OBJ)
        functions={n.name for n in tree.body if isinstance(n,ast.FunctionDef)}
        for name in ('obtenir_resultat','est_disponible','construire_classes',
                     'export_csv_aggreges','export_xlsx_aggreges','export_csv_lot_aggreges'):
            self.assertIn(name,functions)
        self.assertIn('import xlsxwriter',source)
        self.assertNotIn('import openpyxl',source)
        self.assertIn("dictParametres.get('mode') == 'presents'",source)


if __name__ == '__main__':
    unittest.main()
