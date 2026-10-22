# -*- coding: utf-8 -*-
"""Regression Noethys SL wx : Entree dans la recherche rapide d'individus.

Exercices sans base PMSL, sans ouverture de fiche réelle et sans réseau.
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import _garde_reseau  # noqa: F401,E402
sys.path.insert(0, str(ROOT / "noethys"))
import wx  # noqa: E402
from Ol import OL_Individus  # noqa: E402


class BarreRechercheEnterTests(unittest.TestCase):
    def test_handler_recoit_entree_classique_et_pave_numerique(self):
        for touche in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            with self.subTest(touche=touche):
                recherche = SimpleNamespace(OnEnter=Mock(), OnCancel=Mock())
                evenement = SimpleNamespace(
                    GetKeyCode=lambda: touche, Skip=Mock()
                )
                OL_Individus.BarreRecherche.OnKeyDown(recherche, evenement)
                recherche.OnEnter.assert_called_once_with(None)
                recherche.OnCancel.assert_not_called()
                evenement.Skip.assert_not_called()

    def test_autres_touches_et_echap_conserves(self):
        recherche = SimpleNamespace(OnEnter=Mock(), OnCancel=Mock())
        normale = SimpleNamespace(GetKeyCode=lambda: ord("a"), Skip=Mock())
        OL_Individus.BarreRecherche.OnKeyDown(recherche, normale)
        normale.Skip.assert_called_once_with()
        esc = SimpleNamespace(GetKeyCode=lambda: wx.WXK_ESCAPE, Skip=Mock())
        OL_Individus.BarreRecherche.OnKeyDown(recherche, esc)
        recherche.OnCancel.assert_called_once_with(None)
        esc.Skip.assert_not_called()
        recherche.OnEnter.assert_not_called()

    def _recherche_fictive(self, texte, personnes, timer_en_cours=True):
        filtre = SimpleNamespace(texte="")
        filtre.SetText = lambda value: setattr(filtre, "texte", value)
        vue = SimpleNamespace()
        vue.donnees = personnes
        vue.GetFilter = lambda: filtre
        vue.visible = personnes[:]
        vue.actualisations = 0
        vue.selection = []
        vue.ouvertures = []

        def actualiser():
            vue.actualisations += 1
            vue.visible = [
                p for p in personnes if filtre.texte.lower() in p.nom.lower()
            ]
        vue.RepopulateList = actualiser
        vue.Refresh = Mock()
        vue.GetFilteredObjects = lambda: vue.visible
        vue.SelectObject = lambda track: vue.selection.append(track)
        vue.OuvrirFicheFamille = lambda track: vue.ouvertures.append(track)

        timer = SimpleNamespace(en_cours=timer_en_cours, arrêts=0)
        timer.IsRunning = lambda: timer.en_cours

        def stopper():
            timer.en_cours = False
            timer.arrêts += 1
        timer.Stop = stopper

        recherche = SimpleNamespace(
            _ouverture_entree_en_cours=False,
            ouvrir_fiche=True,  # ancien drapeau en attente : pas de double ouverture
            timer=timer, listView=vue,
            GetValue=lambda: texte,
            ShowCancelButton=Mock(),
        )
        recherche.Recherche = lambda evt=None: OL_Individus.BarreRecherche.Recherche(
            recherche, evt
        )
        recherche.OuvrirFiche = lambda: OL_Individus.BarreRecherche.OuvrirFiche(
            recherche
        )
        return recherche, vue, timer, filtre

    def test_entree_force_filtrage_avant_ouverture_famille_unique(self):
        personnes = [
            SimpleNamespace(IDindividu=10, nom="Dupont"),
            SimpleNamespace(IDindividu=11, nom="Durand"),
        ]
        recherche, vue, timer, filtre = self._recherche_fictive(
            "Durand", personnes, timer_en_cours=True
        )
        # Avant Entree le filtrage n'a pas encore eu lieu.
        self.assertEqual(len(vue.GetFilteredObjects()), 2)
        OL_Individus.BarreRecherche.OnEnter(recherche, None)
        self.assertEqual(filtre.texte, "Durand")
        self.assertEqual(vue.actualisations, 1)
        self.assertEqual(vue.ouvertures, [personnes[1]])
        self.assertEqual(vue.selection, [personnes[1]])
        self.assertEqual(timer.arrêts, 1)
        self.assertFalse(recherche.ouvrir_fiche)
        self.assertFalse(recherche._ouverture_entree_en_cours)

    def test_aucun_individu_ne_provoque_ouverture_ou_ancienne_selection(self):
        personnes = [SimpleNamespace(IDindividu=10, nom="Dupont")]
        recherche, vue, timer, filtre = self._recherche_fictive(
            "Introuvable", personnes, timer_en_cours=True
        )
        OL_Individus.BarreRecherche.OnEnter(recherche, None)
        self.assertEqual(vue.visible, [])
        self.assertEqual(vue.ouvertures, [])
        self.assertEqual(vue.selection, [])
        self.assertFalse(recherche.ouvrir_fiche)
        self.assertFalse(recherche._ouverture_entree_en_cours)
        self.assertEqual(timer.arrêts, 1)

    def test_evenement_reentrant_n_ouvre_pas_deux_fois_la_fiche(self):
        personne = SimpleNamespace(IDindividu=19, nom="Dupont")
        recherche, vue, timer, filtre = self._recherche_fictive("Dupont", [personne])
        ancienne_ouverture = vue.OuvrirFicheFamille

        def ouvrir_et_reentrer(track):
            ancienne_ouverture(track)
            OL_Individus.BarreRecherche.OnEnter(recherche, None)
        vue.OuvrirFicheFamille = ouvrir_et_reentrer
        OL_Individus.BarreRecherche.OnEnter(recherche, None)
        self.assertEqual(vue.ouvertures, [personne])
        self.assertEqual(vue.actualisations, 1)

    def test_garde_retablie_apres_erreur_d_ouverture(self):
        personne = SimpleNamespace(IDindividu=19, nom="Dupont")
        recherche, vue, timer, filtre = self._recherche_fictive("Dupont", [personne])

        def echouer(track):
            raise RuntimeError("dialogue fictif")
        vue.OuvrirFicheFamille = echouer
        with self.assertRaisesRegex(RuntimeError, "dialogue fictif"):
            OL_Individus.BarreRecherche.OnEnter(recherche, None)
        self.assertFalse(recherche._ouverture_entree_en_cours)

    def test_controle_garde_evenement_natif_et_ancien_evt_text_enter(self):
        source = (ROOT / "noethys" / "Ol" / "OL_Individus.py").read_text(
            encoding="utf-8"
        )
        arbre = ast.parse(source)
        cls = next(
            n for n in arbre.body
            if isinstance(n, ast.ClassDef) and n.name == "BarreRecherche"
        )
        init = next(
            n for n in cls.body
            if isinstance(n, ast.FunctionDef) and n.name == "__init__"
        )
        segment = ast.get_source_segment(source, init)
        self.assertIn("self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyDown)", segment)
        self.assertIn("self.Bind(wx.EVT_TEXT_ENTER, self.OnEnter)", segment)
        self.assertIn("child.Bind(wx.EVT_CHAR, self.OnKeyDown)", segment)


if __name__ == "__main__":
    unittest.main()
