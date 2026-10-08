# -*- coding: utf-8 -*-
import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import ast
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

class DevisTests(unittest.TestCase):
    def method(self, rights, shown):
        path=Path(__file__).parents[1]/'noethys/Dlg/DLG_Famille.py'
        tree=ast.parse(path.read_text(encoding='utf-8'))
        method=next(n for c in tree.body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='MenuGenererDevis')
        dialog=SimpleNamespace(ShowModal=lambda:shown.append('ouvert'),Destroy=lambda:shown.append('fermé'))
        context={'UTILS_Utilisateurs':SimpleNamespace(VerificationDroitsUtilisateurActuel=lambda *args:rights)}
        exec(compile(ast.Module(body=[method],type_ignores=[]),str(path),'exec'),context)
        fake=SimpleNamespace(IDfamille=41)
        with patch.dict(sys.modules,{'Dlg':SimpleNamespace(DLG_Impression_devis=SimpleNamespace(Dialog=lambda parent,IDfamille:dialog))}):
            context['MenuGenererDevis'](fake,None)
    def test_devis_sans_appel_ventilation(self):
        shown=[];self.method(True,shown)
        self.assertEqual(shown,['ouvert','fermé'])
    def test_droits_toujours_verifies(self):
        shown=[];self.method(False,shown)
        self.assertEqual(shown,[])

if __name__=='__main__':unittest.main()
