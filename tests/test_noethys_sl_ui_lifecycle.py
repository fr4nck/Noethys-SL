# -*- coding: utf-8 -*-
"""Contrats de cycle de vie UI pour Noethys SL 0.1.0."""
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


def source_methode(path, class_name, method_name):
    source = lire(path)
    tree = ast.parse(source)
    cls = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    method = next(
        node for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    )
    return ast.get_source_segment(source, method)


class ListeConsommationsContracts(unittest.TestCase):
    def test_filtre_activite_est_peuple_meme_sur_base_vide(self):
        src = source_methode(
            "noethys/Dlg/DLG_Liste_consommations.py",
            "CTRL_Activite",
            "SetListeDonnees",
        )
        self.assertNotIn("if len(listeDonnees) == 0 : return", src)
        self.assertIn("self.SetItems(self.listeNoms)", src)

    def test_filtre_annee_garde_toutes_les_annees_sur_base_vide(self):
        src = source_methode(
            "noethys/Dlg/DLG_Liste_consommations.py",
            "CTRL_Annee",
            "SetListeDonnees",
        )
        self.assertNotIn("if len(listeDonnees) == 0 : return", src)
        self.assertIn("self.SetItems(self.listeNoms)", src)

    def test_avertissement_prestation_detruit_le_dialogue_avant_retour(self):
        src = source_methode(
            "noethys/Ol/OL_Liste_consommations.py",
            "ListView",
            "Supprimer",
        )
        self.assertIn("reponse = dlg.ShowModal()", src)
        self.assertIn("dlg.Destroy()", src)
        self.assertNotIn("if dlg.ShowModal() != wx.ID_YES:\n                return False", src)


class MenuCommandContracts(unittest.TestCase):
    def test_pieces_fournies_et_manquantes_ont_des_codes_distincts(self):
        source = lire("noethys/Noethys.py")
        self.assertEqual(source.count('"code" : "liste_pieces_fournies"'), 1)
        self.assertEqual(source.count('"code" : "liste_pieces_manquantes"'), 1)


class FamilleNotebookContracts(unittest.TestCase):
    def test_mapping_utilise_les_pages_reellement_affichees(self):
        source = lire("noethys/Dlg/DLG_Famille.py")
        self.assertIn("self.codesPagesAffichees.append(codePage)", source)
        src = source_methode(
            "noethys/Dlg/DLG_Famille.py",
            "Notebook",
            "OnPageChanged",
        )
        self.assertIn("self.codesPagesAffichees[indexAnciennePage]", src)
        self.assertNotIn("self.listePages[indexAnciennePage]", src)

    def test_callbacks_differes_sont_arretes_a_la_destruction(self):
        src = source_methode(
            "noethys/Dlg/DLG_Famille.py",
            "Notebook",
            "OnDestroy",
        )
        self.assertIn("appel.Stop()", src)
        self.assertIn("self._maj_differees = []", src)


class TickerLifecycleContracts(unittest.TestCase):
    def test_ticker_arrete_ses_deux_timers_a_la_destruction(self):
        src = source_methode(
            "noethys/Ctrl/CTRL_Ticker_presents.py",
            "CTRL",
            "OnDestroy",
        )
        self.assertIn("self.timer.Stop()", src)
        self.assertIn("self.ticker.Stop()", src)


class RemplissageLifecycleContracts(unittest.TestCase):
    def test_maj_auto_est_stoppee_quand_le_panel_est_detruit(self):
        src = source_methode(
            "noethys/Dlg/DLG_Remplissage.py",
            "Panel",
            "OnDestroy",
        )
        self.assertIn("MAJ_AUTO_EN_ATTENTE.Stop()", src)
        self.assertIn("MAJ_AUTO_EN_ATTENTE = None", src)


if __name__ == "__main__":
    unittest.main()
