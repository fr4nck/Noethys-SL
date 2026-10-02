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

    def test_ouverture_apres_fondu_et_delai(self):
        start = next(i for i, n in enumerate(INIT.body) if isinstance(n, ast.Assign)
                     and any(isinstance(v, ast.Name) and v.id == 'frame' for v in n.targets))
        for fichier_deja_ouvert, annulation in ((False, False), (False, True), (True, False)):
            with self.subTest(deja_ouvert=fichier_deja_ouvert, annulation=annulation):
                calls, pending = [], []
                frame = Mock()
                frame.userConfig = {'nomFichier': 'autre_base' if fichier_deja_ouvert else ''}
                frame.maximiser_au_demarrage = True
                frame.AnnonceTemoignages.return_value = True
                frame.EstFichierExemple.return_value = False
                frame.ProposeMAJ.return_value = False
                for name in ('Initialisation', 'Show', 'Update'):
                    getattr(frame, name).side_effect = lambda *args, n=name: calls.append(n)
                frame.OuvrirDernierFichier.side_effect = lambda: calls.append('ouvrir') or not annulation
                splash = Mock()
                splash.GetWindowStyleFlag.return_value = 0
                def fade(logo, on_finished):
                    calls.append('fade')
                    on_finished()
                def later(delay, callback):
                    pending.append((delay, callback))
                ns = dict(MainFrame=lambda parent: frame, self=Mock(), splash=splash,
                          CUSTOMIZE=Mock(), wx=SimpleNamespace(STAY_ON_TOP=1, CallLater=later),
                          FermerSplashProgressivement=fade,
                          time=SimpleNamespace(time=lambda: 1), heure_debut=0, print=lambda *args: None)
                function = ast.FunctionDef(name='run', args=ast.arguments(posonlyargs=[], args=[],
                    kwonlyargs=[], kw_defaults=[], defaults=[]), body=INIT.body[start:], decorator_list=[])
                module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
                exec(compile(module, str(SOURCE), 'exec'), ns)
                self.assertTrue(ns['run']())
                self.assertEqual(calls.count('Show'), 1)
                frame.OuvrirDernierFichier.assert_not_called()
                self.assertLess(calls.index('Update'), calls.index('fade'))
                delay, callback = pending.pop()
                self.assertEqual(delay, 500)
                callback()
                self.assertFalse(pending)
                if fichier_deja_ouvert:
                    frame.OuvrirDernierFichier.assert_not_called()
                else:
                    frame.OuvrirDernierFichier.assert_called_once()
                    self.assertLess(calls.index('fade'), calls.index('ouvrir'))
                splash.Destroy.assert_not_called()

    def test_callback_apres_disparition(self):
        for transparent in (True, False):
            pending, calls = [], []
            splash = Mock(SetTransparent=Mock(return_value=transparent))
            splash.Destroy.side_effect = lambda: calls.append('destroy')
            ns = {'wx': SimpleNamespace(CallLater=lambda delay, cb, *a: pending.append((cb, a)))}
            exec(compile(ast.Module(body=[FADE], type_ignores=[]), str(SOURCE), 'exec'), ns)
            ns['FermerSplashProgressivement'](splash, lambda: calls.append('finished'))
            self.assertFalse(calls)
            while pending:
                cb, args = pending.pop(0)
                cb(*args)
            self.assertEqual(calls, ['destroy', 'finished'])

if __name__ == '__main__':
    unittest.main()
