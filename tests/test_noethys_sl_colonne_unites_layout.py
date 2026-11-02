# -*- coding: utf-8 -*-
"""Regression ergonomique : liste des unites dans la commande de repas wx.

Lecture de l'AST uniquement : pas de wx, base de donnees ni fenetre ouverte.
"""
import ast
import unittest
from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "noethys" / "Dlg" / "DLG_Saisie_commandes_colonne.py"
)


def page_unites_init():
    module = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    page = next(
        node for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "PAGE_Unites"
    )
    return next(
        node for node in page.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )


def appels(node, proprietaire, methode):
    return [
        appel for appel in ast.walk(node)
        if isinstance(appel, ast.Call)
        and isinstance(appel.func, ast.Attribute)
        and appel.func.attr == methode
        and isinstance(appel.func.value, ast.Name)
        and appel.func.value.id == proprietaire
    ]


def est_controle_unites(node):
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "ctrl_unites"
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


class ChoixUnitesLayoutTests(unittest.TestCase):
    def test_arbre_est_assez_haut_par_defaut(self):
        init = page_unites_init()
        tailles = [
            call for call in ast.walk(init)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "SetMinSize"
            and est_controle_unites(call.func.value)
        ]
        self.assertEqual(len(tailles), 1)
        taille = ast.literal_eval(tailles[0].args[0])
        self.assertGreaterEqual(taille[1], 120)
        self.assertGreaterEqual(taille[0], 100)

    def test_arbre_occupe_la_ligne_extensible(self):
        init = page_unites_init()
        ajouts = [
            call for call in appels(init, "grid_sizer_base", "Add")
            if call.args and est_controle_unites(call.args[0])
        ]
        self.assertEqual(len(ajouts), 1)
        self.assertGreaterEqual(len(ajouts[0].args), 3)
        flags = {
            sub.attr for sub in ast.walk(ajouts[0].args[2])
            if isinstance(sub, ast.Attribute)
            and isinstance(sub.value, ast.Name)
            and sub.value.id == "wx"
        }
        self.assertIn("EXPAND", flags)
        self.assertNotIn("ALIGN_CENTER_VERTICAL", flags)
        lignes = appels(init, "grid_sizer_base", "AddGrowableRow")
        self.assertIn(1, [ast.literal_eval(c.args[0]) for c in lignes])


if __name__ == "__main__":
    unittest.main()
