# -*- coding: utf-8 -*-
import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def lire(path):
    return (ROOT / path).read_text(encoding="utf-8")


def source_fonction(path, name, class_name=None):
    source = lire(path)
    tree = ast.parse(source)
    nodes = tree.body
    if class_name is not None:
        cls = next(node for node in nodes if isinstance(node, ast.ClassDef) and node.name == class_name)
        nodes = cls.body
    func = next(node for node in nodes if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.get_source_segment(source, func)


class VanillaCandidateContractTests(unittest.TestCase):
    def test_vacances_accepte_les_dates_python3(self):
        maj = source_fonction("noethys/Ctrl/CTRL_Grille_periode.py", "MAJ", "Vacances")
        self.assertIn("UTILS_Dates.DateEngEnDateDD(date_debut)", maj)
        self.assertIn("UTILS_Dates.DateEngEnDateDD(date_fin)", maj)
        self.assertNotIn("date_debut[:", maj)
        self.assertNotIn("date_fin[:", maj)

    def test_liste_attente_accepte_date_datetime_et_chaine(self):
        conversion = source_fonction("noethys/Ctrl/CTRL_Attente.py", "DateEngEnDateDD")
        self.assertIn("isinstance(dateEng, datetime.datetime)", conversion)
        self.assertIn("return dateEng.date()", conversion)
        self.assertIn("return UTILS_Dates.DateEngEnDateDD(dateEng)", conversion)
        self.assertNotIn("dateEng[:", conversion)

    def test_fermeture_consommations_nettoie_la_liste_virtuelle(self):
        source = lire("noethys/Dlg/DLG_Liste_consommations.py")
        self.assertIn("self.Bind(wx.EVT_CLOSE, self.OnFermer)", source)
        self.assertIn("def _NettoieAvantFermeture(self):", source)
        self.assertIn("ctrl.SetObjectGetter(None)", source)
        self.assertIn("ctrl.SetItemCount(0)", source)
        self.assertIn("timer.Stop()", source)

    def test_fermeture_consommations_est_idempotente(self):
        cleanup = source_fonction("noethys/Dlg/DLG_Liste_consommations.py", "_NettoieAvantFermeture", "Dialog")
        fermer = source_fonction("noethys/Dlg/DLG_Liste_consommations.py", "OnFermer", "Dialog")
        self.assertIn("if self._fermeture_en_cours", cleanup)
        self.assertIn("self._fermeture_en_cours = True", cleanup)
        self.assertIn("self._NettoieAvantFermeture()", fermer)


if __name__ == "__main__":
    unittest.main()
