# -*- coding: utf-8 -*-
"""Vanilla : aucun bouton wx cree sans etre place dans un sizer ou masque.

Un bouton enfant sans sizer s'affiche en (0, 0) par-dessus le dialogue
(audit Vanilla : bouton Modifier de la liste detaillee des consommations).
Analyse statique AST de tout noethys/, sans wx ni base.
"""
import ast
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1] / "noethys"
CONSTRUCTEURS = {"Button", "BitmapButton", "ToggleButton", "BitmapToggleButton",
                 "GenBitmapButton", "GenBitmapTextButton", "ThemedGenBitmapTextButton"}
PLACEMENTS = {"Add", "Insert", "Prepend", "AddButton", "SetAffirmativeButton",
              "SetNegativeButton", "SetCancelButton"}
GESTION_DIRECTE = {"Show", "Hide", "SetPosition", "Move", "SetSize"}

# Exceptions motivees : panneau de test a enfant unique, hors parcours utilisateur.
TOLERES = {"noethys/Ctrl/CTRL_Badgeage_controles.py:boutonTest"}


def _attribut_self(noeud):
    if isinstance(noeud, ast.Attribute) and isinstance(noeud.value, ast.Name) and noeud.value.id == "self":
        return noeud.attr
    return None


def boutons_orphelins():
    orphelins = []
    for fichier in sorted(RACINE.rglob("*.py")):
        try:
            arbre = ast.parse(fichier.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        crees = {}
        places = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Assign) and isinstance(noeud.value, ast.Call):
                fonction = noeud.value.func
                nom = fonction.attr if isinstance(fonction, ast.Attribute) else getattr(fonction, "id", "")
                if nom in CONSTRUCTEURS:
                    for cible in noeud.targets:
                        attribut = _attribut_self(cible)
                        if attribut:
                            crees.setdefault(attribut, noeud.lineno)
            if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute):
                if noeud.func.attr in PLACEMENTS:
                    places.update(filter(None, (_attribut_self(arg) for arg in noeud.args)))
                if noeud.func.attr in GESTION_DIRECTE:
                    attribut = _attribut_self(noeud.func.value)
                    if attribut:
                        places.add(attribut)
        relatif = fichier.relative_to(RACINE.parent).as_posix()
        for attribut, ligne in crees.items():
            cle = "%s:%s" % (relatif, attribut)
            if attribut not in places and cle not in TOLERES:
                orphelins.append("%s (ligne %d)" % (cle, ligne))
    return orphelins


class BoutonsPlacesTests(unittest.TestCase):
    def test_aucun_bouton_orphelin(self):
        self.assertEqual(boutons_orphelins(), [])

    def test_boutons_morts_connus_masques(self):
        for chemin, appel in (
                ("noethys/Dlg/DLG_Liste_consommations.py", "self.bouton_modifier.Hide()"),
                ("noethys/Ctrl/CTRL_Liste_inscriptions.py", "self.bouton_supprimer.Hide()")):
            with self.subTest(chemin=chemin):
                self.assertIn(appel, (RACINE.parent / chemin).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
