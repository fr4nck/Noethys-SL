"""Le chargement précède l'affichage ; le fondu reste non bloquant."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / 'noethys/Noethys.py'
TREE = ast.parse(SOURCE.read_text(encoding='utf-8'))
FADE = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == 'FermerSplashProgressivement')
APP = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == 'MyApp')
INIT = next(n for n in APP.body if isinstance(n, ast.FunctionDef) and n.name == 'OnInit')

class SplashTests(unittest.TestCase):
    def fade(self, splash):
        pending = []
        def later(delay, callback, *args):
            self.assertEqual(delay, 40)
            pending.append((callback, args))
        ns = {'wx': SimpleNamespace(CallLater=later)}
        exec(compile(ast.Module(body=[FADE], type_ignores=[]), str(SOURCE), 'exec'), ns)
        ns['FermerSplashProgressivement'](splash)
        if splash is not None:
            splash.Destroy.assert_not_called()
        while pending:
            callback, args = pending.pop(0)
            callback(*args)
        return splash

    def test_fondu_progressif(self):
        splash = self.fade(Mock(SetTransparent=Mock(return_value=True)))
        self.assertEqual([c.args[0] for c in splash.SetTransparent.call_args_list],
                         [230, 205, 180, 155, 130, 105, 80, 55, 30, 0])
        splash.Destroy.assert_called_once()

    def test_transparence_indisponible(self):
        splash = self.fade(Mock(SetTransparent=Mock(return_value=False)))
        splash.Destroy.assert_called_once()

    def test_sans_logo(self):
        self.fade(None)

    def test_fenetre_prete_avant_affichage(self):
        # Exerce la séquence réelle de démarrage, sans données ni connexion réseau.
        start = next(i for i, n in enumerate(INIT.body) if isinstance(n, ast.Assign)
                     and any(isinstance(v, ast.Name) and v.id == 'frame' for v in n.targets))
        body = INIT.body[start:]
        calls = []
        frame = Mock()
        frame.maximiser_au_demarrage = True
        frame.AnnonceTemoignages.return_value = True
        frame.EstFichierExemple.return_value = False
        frame.ProposeMAJ.return_value = False
        for name in ('Initialisation', 'OuvrirDernierFichier', 'Show', 'Update'):
            getattr(frame, name).side_effect = lambda *args, n=name: calls.append(n) or True
        splash = Mock()
        splash.GetWindowStyleFlag.return_value = 0
        ns = dict(MainFrame=lambda parent: frame, self=Mock(), splash=splash,
                  CUSTOMIZE=Mock(), wx=SimpleNamespace(STAY_ON_TOP=1),
                  FermerSplashProgressivement=lambda logo: calls.append('fade'),
                  time=SimpleNamespace(time=lambda: 1), heure_debut=0, print=lambda *args: None)
        function = ast.FunctionDef(name='run', args=ast.arguments(posonlyargs=[],args=[],
            kwonlyargs=[],kw_defaults=[],defaults=[]), body=body, decorator_list=[])
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        exec(compile(module, str(SOURCE), 'exec'), ns)
        self.assertTrue(ns['run']())
        self.assertLess(calls.index('OuvrirDernierFichier'), calls.index('Show'))
        self.assertLess(calls.index('Update'), calls.index('fade'))
        self.assertEqual(calls.count('Show'), 1)
        splash.Destroy.assert_not_called()

if __name__ == '__main__':
    unittest.main()
