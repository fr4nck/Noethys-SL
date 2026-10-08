# -*- coding: utf-8 -*-
"""Backports de défauts déjà prouvés sur la ligne master."""
from __future__ import annotations

import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def lire(path):
    return (ROOT / path).read_text(encoding="utf-8")


def source_fonction(path, nom):
    source = lire(path)
    tree = ast.parse(source)
    node = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == nom
    )
    return ast.get_source_segment(source, node)


def source_methode(path, class_name, method_name):
    source = lire(path)
    tree = ast.parse(source)
    cls = next(
        n for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == class_name
    )
    node = next(
        n for n in cls.body
        if isinstance(n, ast.FunctionDef) and n.name == method_name
    )
    return ast.get_source_segment(source, node)


class ExportComptaBackportTests(unittest.TestCase):
    def test_get_keys_dict_tries_iterates_the_list(self):
        src = source_fonction(
            "noethys/Dlg/DLG_Export_compta.py",
            "GetKeysDictTries",
        )
        self.assertIn("for keyTemp, ID in listeKeys :", src)
        self.assertNotIn("listeKeys()", src)

    def test_mode_uses_its_own_accounting_code(self):
        src = source_methode(
            "noethys/Dlg/DLG_Export_compta.py",
            "Donnees",
            "GetReglements_Modes",
        )
        self.assertIn('"code_compta" : dictMode["code_compta"]', src)


class BadgeageBackportTests(unittest.TestCase):
    def test_open_consumption_is_the_one_reused(self):
        src = source_methode(
            "noethys/Dlg/DLG_Badgeage_interface.py",
            "CTRL_Interface",
            "Procedure_enregistrer",
        )
        self.assertIn("heureDebut = conso_a_modifier.heure_debut", src)
        self.assertIn("badgeage_debut = conso_a_modifier.badgeage_debut", src)
        self.assertNotIn("heureDebut = conso.heure_debut", src)


class RestoreBackportTests(unittest.TestCase):
    def test_empty_selection_has_no_unbound_progress_dialog(self):
        src = source_fonction(
            "noethys/Utils/UTILS_Sauvegarde.py",
            "Restauration",
        )
        self.assertIn("dlgprogress = None", src)
        self.assertIn("if dlgprogress is not None:", src)


class EtatNominatifBackportTests(unittest.TestCase):
    def test_unsupported_questionnaire_types_are_skipped(self):
        src = source_methode(
            "noethys/Ol/OL_Etat_nomin_champs.py",
            "Champs",
            "GetTracks",
        )
        self.assertIn('elif type == "famille"', src)
        self.assertIn("continue", src)

    def test_translated_categories_are_resolved_safely(self):
        source = lire("noethys/Ol/OL_Etat_nomin_resultats.py")
        self.assertIn('champ.categorie == _(u"Individu")', source)
        self.assertIn('champ.categorie == _(u"Famille")', source)


if __name__ == "__main__":
    unittest.main()
