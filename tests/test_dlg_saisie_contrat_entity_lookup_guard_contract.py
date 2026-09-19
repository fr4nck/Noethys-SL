#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contrat de non-régression pour les deux lookups d'entité effectués au
tout début de DLG_Saisie_contrat.Dialog.__init__.

La méthode __init__ est extraite par AST afin de ne charger ni wx réel ni les
contrôles Noethys. Les cas absents doivent lever ValueError après fermeture de
la DB et avant le premier widget. Les cas présents doivent conserver les
attributs historiques puis atteindre la première création de widget.
"""

import ast
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "noethys" / "Dlg" / "DLG_Saisie_contrat.py"


class StopAtFirstWidget(Exception):
    pass


class FakeDB:
    def __init__(self, resultat):
        self.resultat = resultat
        self.requetes = []
        self.close_appele = False

    def ExecuterReq(self, req):
        self.requetes.append(req)

    def ResultatReq(self):
        return self.resultat

    def Close(self):
        self.close_appele = True


class FakeDialogBase:
    init_calls = []

    def __init__(self, parent, identifiant, **kwargs):
        FakeDialogBase.init_calls.append((parent, identifiant, kwargs))


class StaticBoxTrap:
    calls = 0

    def __new__(cls, *args, **kwargs):
        cls.calls += 1
        raise StopAtFirstWidget()


def _fake_wx():
    FakeDialogBase.init_calls = []
    StaticBoxTrap.calls = 0
    return types.SimpleNamespace(
        Dialog=FakeDialogBase,
        StaticBox=StaticBoxTrap,
        DEFAULT_DIALOG_STYLE=1,
        RESIZE_BORDER=2,
        MAXIMIZE_BOX=4,
        MINIMIZE_BOX=8,
        ID_ANY=-1,
    )


def _extract_init(extra_namespace):
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SOURCE_PATH))
    class_node = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Dialog"
    )
    init_node = next(
        node for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )
    module = ast.Module(body=[init_node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = dict(extra_namespace)
    exec(compile(module, str(SOURCE_PATH), "exec"), namespace)
    return namespace["__init__"]


def _identity(value):
    return value


class DialogEntityLookupGuardTests(unittest.TestCase):
    def _load(self, resultat):
        fake_db = FakeDB(resultat)
        fake_wx = _fake_wx()
        init = _extract_init({
            "wx": fake_wx,
            "GestionDB": types.SimpleNamespace(DB=lambda: fake_db),
            "_": _identity,
        })
        return init, fake_db

    def test_missing_modele_activity_raises_valueerror_before_first_widget(self):
        init, fake_db = self._load([])

        with self.assertRaisesRegex(ValueError, r"Activité introuvable : 5"):
            init(
                types.SimpleNamespace(),
                parent=object(),
                mode_modele=True,
                IDactivite=5,
            )

        self.assertTrue(fake_db.close_appele)
        self.assertEqual(len(fake_db.requetes), 1)
        self.assertEqual(StaticBoxTrap.calls, 0)

    def test_missing_inscription_raises_valueerror_before_first_widget(self):
        init, fake_db = self._load([])

        with self.assertRaisesRegex(ValueError, r"Inscription introuvable : 42"):
            init(
                types.SimpleNamespace(),
                parent=object(),
                mode_modele=False,
                IDinscription=42,
            )

        self.assertTrue(fake_db.close_appele)
        self.assertEqual(len(fake_db.requetes), 1)
        self.assertEqual(StaticBoxTrap.calls, 0)

    def test_existing_modele_activity_keeps_loaded_attributes_then_builds_widgets(self):
        init, fake_db = self._load([(5, "Multisport")])
        fake_self = types.SimpleNamespace()

        with self.assertRaises(StopAtFirstWidget):
            init(
                fake_self,
                parent=object(),
                mode_modele=True,
                IDactivite=5,
            )

        self.assertTrue(fake_db.close_appele)
        self.assertEqual(fake_self.IDactivite, 5)
        self.assertEqual(fake_self.nomActivite, "Multisport")
        self.assertIsNone(fake_self.IDcompte_payeur)
        self.assertIsNone(fake_self.IDfamille)
        self.assertIsNone(fake_self.IDcategorie_tarif)
        self.assertIsNone(fake_self.IDgroupe)
        self.assertIsNone(fake_self.nomGroupe)
        self.assertEqual(StaticBoxTrap.calls, 1)

    def test_existing_inscription_keeps_loaded_attributes_then_builds_widgets(self):
        init, fake_db = self._load([
            (5, "Multisport", 9, 7, 3, 2, "Groupe A")
        ])
        fake_self = types.SimpleNamespace()

        with self.assertRaises(StopAtFirstWidget):
            init(
                fake_self,
                parent=object(),
                mode_modele=False,
                IDinscription=42,
            )

        self.assertTrue(fake_db.close_appele)
        self.assertEqual(fake_self.IDactivite, 5)
        self.assertEqual(fake_self.nomActivite, "Multisport")
        self.assertEqual(fake_self.IDcompte_payeur, 9)
        self.assertEqual(fake_self.IDfamille, 7)
        self.assertEqual(fake_self.IDcategorie_tarif, 3)
        self.assertEqual(fake_self.IDgroupe, 2)
        self.assertEqual(fake_self.nomGroupe, "Groupe A")
        self.assertEqual(StaticBoxTrap.calls, 1)


if __name__ == "__main__":
    unittest.main()
