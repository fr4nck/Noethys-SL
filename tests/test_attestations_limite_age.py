"""Exerce les méthodes de date sans connexion à une base de production."""
import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import ast
import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / 'noethys/Dlg/DLG_Attestations_fiscales_parametres.py'
tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
classe = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Parametres')
methods = [n for n in classe.body if isinstance(n, ast.FunctionDef) and n.name in
           ('OnChoixDate', 'OnCheckAge', 'MAJprestations', 'OnBoutonActualiser')]
namespace = {'datetime': datetime, 'wx': Mock(), '_': lambda s: s}
namespace['wx'].OK = 1
namespace['wx'].ICON_EXCLAMATION = 2
exec(compile(ast.Module(body=methods, type_ignores=[]), str(SOURCE), 'exec'), namespace)


class LimiteAgeTests(unittest.TestCase):
    def panel(self, debut):
        p = SimpleNamespace(ctrl_date_debut=Mock(), ctrl_date_fin=Mock(), ctrl_dateNaiss=Mock(),
                            check_dateNaiss=Mock(), check_repas=Mock(), parent=Mock(), ctrl_methode=Mock(),
                            GetActivites=Mock(return_value=[1]), GetModes=Mock(return_value=[1]))
        p.ctrl_date_debut.GetDate.return_value = debut
        p.check_dateNaiss.GetValue.return_value = True
        for method in methods:
            setattr(p, method.name, namespace[method.name].__get__(p))
        return p

    def test_limite_suit_annee_de_reference(self):
        p = self.panel(datetime.date(2025, 1, 1))
        p.OnChoixDate()
        p.ctrl_dateNaiss.SetDate.assert_called_with(datetime.date(2019, 1, 1))
        p.ctrl_date_debut.GetDate.return_value = datetime.date(2026, 9, 10)
        p.OnChoixDate()
        p.ctrl_dateNaiss.SetDate.assert_called_with(datetime.date(2020, 1, 1))

    def test_saisie_incomplete_sans_erreur(self):
        p = self.panel(None)
        p.OnChoixDate()
        p.ctrl_dateNaiss.SetDate.assert_not_called()

    def test_limite_non_modifiable(self):
        p = self.panel(datetime.date(2024, 2, 29))
        p.OnCheckAge(None)
        p.ctrl_dateNaiss.Enable.assert_called_with(False)
        p.ctrl_dateNaiss.SetDate.assert_called_with(datetime.date(2018, 1, 1))

    def test_actualisation_recalcule_avant_transmission(self):
        p = self.panel(datetime.date(2026, 1, 1))
        p.ctrl_dateNaiss.GetDate.return_value = datetime.date(2020, 1, 1)
        p.MAJprestations()
        p.ctrl_dateNaiss.SetDate.assert_called_with(datetime.date(2020, 1, 1))
        self.assertEqual(p.parent.ctrl_prestations.MAJ.call_args.args[2], datetime.date(2020, 1, 1))

    def test_periode_sur_deux_annees_refusee(self):
        p = self.panel(datetime.date(2025, 1, 1))
        p.ctrl_date_fin.GetDate.return_value = datetime.date(2026, 12, 31)
        self.assertFalse(p.OnBoutonActualiser(None))
        p.parent.ctrl_prestations.MAJ.assert_not_called()


if __name__ == '__main__':
    unittest.main()
