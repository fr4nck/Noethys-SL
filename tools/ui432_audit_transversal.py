# -*- coding: utf-8 -*-
"""UI-432J - inventaire statique reproductible des risques d'interface wx.

Aucun module Noethys n'est importe, aucune base n'est ouverte. Les categories
sont des signaux de revue, jamais une preuve de gel Windows. Sortie :
fichiers/fonctions/lignes et familles de risques, sans SQL ni donnees metier.
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1] / "noethys"
DOSSIERS = ("Dlg", "Ctrl", "Ol", "Utils")
NIVEAUX = {
    "progression_sans_proprietaire": "P2",
    "attente_sans_proprietaire": "P2",
    "pause_ui_potentielle": "P2",
    "reentrance_wx_potentielle": "P2",
    "sql_handler_potentiel": "P2",
    "reseau_handler_potentiel": "P1",
    "etat_fenetre_modifie": "P2",
}


def _nom_appel(expr):
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        racine = _nom_appel(expr.value)
        return (racine + "." if racine else "") + expr.attr
    if isinstance(expr, ast.Call):
        return _nom_appel(expr.func) + "()"
    return ""


def _est_none(noeud):
    return isinstance(noeud, ast.Constant) and noeud.value is None


class _AppelsLocaux(ast.NodeVisitor):
    """N'attribue pas les appels des fonctions imbriquees a leur parente."""
    def __init__(self):
        self.appels = []

    def visit_Call(self, noeud):
        self.appels.append(noeud)
        self.generic_visit(noeud)

    def visit_FunctionDef(self, noeud):
        pass

    def visit_AsyncFunctionDef(self, noeud):
        pass

    def visit_Lambda(self, noeud):
        pass


def analyser_source(source, chemin="fictif.py"):
    arbre = ast.parse(source, filename=chemin)
    observations = []
    for fonction in ast.walk(arbre):
        if not isinstance(fonction, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        appels = _AppelsLocaux()
        for etape in fonction.body:
            appels.visit(etape)
        noms = [_nom_appel(appel.func) for appel in appels.appels]
        handler = fonction.name.startswith(
            ("On", "MAJ", "Init", "Actualis", "Rafraich", "Refresh", "Imprim", "Envoy"))
        types = set()

        for appel, nom in zip(appels.appels, noms):
            if nom.endswith(".ProgressDialog") or nom == "ProgressDialog":
                parent = next((kw.value for kw in appel.keywords
                               if kw.arg == "parent"), None)
                if parent is None or _est_none(parent):
                    types.add("progression_sans_proprietaire")
            if nom.endswith(".BusyInfo") or nom == "BusyInfo":
                parent = next((kw.value for kw in appel.keywords
                               if kw.arg == "parent"), None)
                if parent is None and len(appel.args) > 1:
                    parent = appel.args[1]
                if parent is None or _est_none(parent):
                    types.add("attente_sans_proprietaire")
            if nom in ("time.sleep", "sleep") and handler:
                types.add("pause_ui_potentielle")
            if nom in ("wx.Yield", "wx.SafeYield", "wx.YieldIfNeeded") and handler:
                types.add("reentrance_wx_potentielle")
            if handler and nom.endswith((".Connecter", ".Envoyer_lot")):
                types.add("reseau_handler_potentiel")
            if handler and nom.endswith((".Iconize", ".Maximize", ".Restore")):
                types.add("etat_fenetre_modifie")
        if handler and any(n.endswith(".ExecuterReq") for n in noms):
            types.add("sql_handler_potentiel")
        for categorie in sorted(types):
            observations.append({
                "fichier": str(chemin).replace("\\", "/"),
                "fonction": fonction.name,
                "ligne": fonction.lineno,
                "risque": categorie,
                "niveau": NIVEAUX[categorie],
            })
    return observations


def parcourir_sources(racine=RACINE):
    chemins = [racine / "Noethys.py"]
    for dossier in DOSSIERS:
        chemins.extend(sorted((racine / dossier).glob("*.py")))
    resultats = []
    erreurs = []
    for chemin in chemins:
        if not chemin.is_file():
            continue
        try:
            relatif = chemin.relative_to(racine)
            texte = chemin.read_text(encoding="utf-8-sig")
            resultats.extend(analyser_source(texte, relatif))
        except (OSError, UnicodeError, SyntaxError):
            erreurs.append(str(chemin.relative_to(racine)).replace("\\", "/"))
    return len(chemins), resultats, erreurs


def main(argv=None):
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--limit", type=int, default=25)
    analyseur.add_argument("--json", action="store_true")
    options = analyseur.parse_args(argv)
    total, observations, erreurs = parcourir_sources()
    observations.sort(key=lambda o: (
        0 if o["niveau"] == "P1" else 1,
        o["fichier"], o["ligne"], o["risque"]))
    frequences = collections.Counter(o["risque"] for o in observations)
    synthese = {
        "modules": total,
        "anomalies_analyse": len(observations),
        "erreurs_analyse": len(erreurs),
        "par_risque": dict(sorted(frequences.items())),
        "selection": observations[:max(0, options.limit)],
    }
    if options.json:
        print(json.dumps(synthese, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print("UI432J_SCAN modules=%d signaux=%d erreurs_analyse=%d" %
              (total, len(observations), len(erreurs)))
        for nom, nombre in sorted(frequences.items()):
            print("UI432J_RISQUE %s=%d" % (nom, nombre))
        for observation in synthese["selection"]:
            print("UI432J_PRIORITE %s %s:%d %s %s" %
                  (observation["niveau"], observation["fichier"],
                   observation["ligne"], observation["fonction"],
                   observation["risque"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
