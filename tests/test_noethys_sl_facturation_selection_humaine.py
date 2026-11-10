# -*- coding: utf-8 -*-
"""Facturation : choix nominatif, absence de contrainte et garde avant emission.

Aucune connexion ni aucun dossier PMSL : base SQLite fictive et interface wx
simulee a partir des methodes reelles (AST).
"""
import ast
import datetime
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from tests.test_noethys_sl_adhesions import Env, D
from Utils import UTILS_Adhesions_echeances as E

CHEMIN = Path(__file__).resolve().parents[1] / "noethys" / "Dlg" / "DLG_Factures_generation.py"


class SelectionMetierTests(unittest.TestCase):
    def test_une_personne_dispensée_n_est_pas_facturee_mais_une_autre_oui(self):
        with Env() as env:
            env.conso(100, D(2026, 9, 5), payeur=11)
            env.conso(200, D(2026, 9, 6), payeur=12)
            proposition = E.Proposer(D(2026, 9, 1), D(2026, 9, 30),
                                    D(2026, 10, 19), [1, 2])
            self.assertEqual({p["IDtitulaire"] for p in proposition["propositions"]},
                             {100, 200})
            resultats = E.Executer(proposition, confirmation=True,
                                  selection_titulaires=[100])
            self.assertEqual([r["statut"] for r in resultats], ["cree"])
            self.assertEqual(env.compte("cotisations", "IDindividu=100"), 1)
            self.assertEqual(env.compte("cotisations", "IDindividu=200"), 0)
            self.assertEqual(env.compte("prestations", "categorie='cotisation'"), 1)
            restant = E.Proposer(D(2026, 9, 1), D(2026, 9, 30),
                                 D(2026, 10, 19), [1, 2])
            self.assertEqual([p["IDtitulaire"] for p in restant["propositions"]], [200])

    def test_aucune_selection_ne_cree_aucune_cotisation(self):
        with Env() as env:
            env.conso(100, D(2026, 9, 5))
            p = E.Proposer(D(2026, 9, 1), D(2026, 9, 30),
                           D(2026, 10, 19), [1])
            self.assertEqual(E.Executer(p, confirmation=True,
                                       selection_titulaires=[]), [])
            self.assertEqual(env.compte("cotisations"), 0)
            self.assertEqual(env.compte("prestations", "categorie='cotisation'"), 0)

    def test_identifiant_inconnu_refuse_toute_creation(self):
        with Env() as env:
            env.conso(100, D(2026, 9, 5))
            p = E.Proposer(D(2026, 9, 1), D(2026, 9, 30),
                           D(2026, 10, 19), [1])
            with self.assertRaises(ValueError):
                E.Executer(p, confirmation=True, selection_titulaires=[999999])
            self.assertEqual(env.compte("cotisations"), 0)


def charger_methodes(wx, echeances, adhesions):
    racine = ast.parse(CHEMIN.read_text(encoding="utf-8"), filename=str(CHEMIN))
    dialogue = next(n for n in racine.body
                    if isinstance(n, ast.ClassDef) and n.name == "Dialog")
    noms = {"PreparerCotisationsPourApercu", "VerifierCotisationsAvantEmission"}
    fonctions = [n for n in dialogue.body
                 if isinstance(n, ast.FunctionDef) and n.name in noms]
    util = types.ModuleType("Utils")
    util.UTILS_Adhesions_echeances = echeances
    util.UTILS_Adhesions = adhesions
    util.UTILS_Identification = types.SimpleNamespace(GetIDutilisateur=lambda: 3)
    env = {"wx": wx, "_": lambda texte: texte, "datetime": datetime}
    with patch.dict(sys.modules, {"Utils": util}):
        exec(compile(ast.fix_missing_locations(
            ast.Module(body=fonctions, type_ignores=[])), str(CHEMIN), "exec"), env)
        yield env


class SelectionInterfaceTests(unittest.TestCase):
    def contexte(self):
        return types.SimpleNamespace(dictParametres={
            "prestations": ["cotisation", "consommation"],
            "date_debut": D(2026, 9, 1),
            "date_fin": D(2026, 9, 30),
            "listeActivites": [1],
            "IDcompte_payeur": None,
        })

    def construire(self, choisi=(0,), avant=None, apres=None, erreur=False):
        appels = {"messages": [], "executions": [], "labels": [], "lectures": 0}
        proposition_1 = {
            "propositions": [
                {"IDtitulaire": 100, "IDcompte_payeur": 11,
                 "date_debut": D(2026, 9, 5), "montant": 7.5},
                {"IDtitulaire": 200, "IDcompte_payeur": 12,
                 "date_debut": D(2026, 9, 6), "montant": 7.5},
            ], "a_verifier": [],
        }
        proposition_2 = {
            "propositions": [proposition_1["propositions"][1]],
            "a_verifier": [],
        }
        if avant is not None:
            proposition_1 = avant
        if apres is not None:
            proposition_2 = apres

        class Choix:
            def __init__(self, parent, texte, titre, labels):
                appels["labels"] = list(labels)

            def SetSelections(self, valeurs):
                appels["selection_initiale"] = list(valeurs)

            def ShowModal(self):
                return 100

            def GetSelections(self):
                return list(choisi)

            def Destroy(self):
                pass

        def message_box(message, titre, style, parent):
            appels["messages"].append((message, titre))
            return 1

        wx = types.SimpleNamespace(
            YES=1, NO=2, YES_NO=4, NO_DEFAULT=8,
            ICON_WARNING=16, OK=32, ICON_ERROR=64,
            ID_OK=100, MultiChoiceDialog=Choix, MessageBox=message_box,
        )
        def proposer(**kw):
            appels["lectures"] += 1
            if erreur:
                raise RuntimeError("2005 DNS")
            if appels["lectures"] == 1:
                return proposition_1
            return proposition_2

        def executer(proposition, **kw):
            appels["executions"].append(kw)
            return [{"statut": "cree"} for _ in kw["selection_titulaires"]]

        echeances = types.SimpleNamespace(
            Proposer=proposer, Executer=executer,
            Empreinte=lambda elements: tuple(sorted(p["IDtitulaire"] for p in elements)),
        )
        adhesions = types.SimpleNamespace(
            _liste_sql=lambda ids: "(" + ",".join(str(v) for v in ids) + ")",
            _lire=lambda req: [(100, "ALPHA", "Louis"), (200, "BETA", "Edgar")],
        )
        return wx, echeances, adhesions, appels

    def test_choix_partiel_explicitement_respecte_et_emission_autorisee(self):
        wx, echeances, adhesions, appels = self.construire()
        with next(charger_methodes(wx, echeances, adhesions)) if False else patch.dict(sys.modules, {}):
            pass
        # Les modules sont injectes uniquement lors de l'appel des methodes :
        # les imports des fonctions d'origine utilisent ces modules.
        racine = ast.parse(CHEMIN.read_text(encoding="utf-8"))
        dialogue = next(n for n in racine.body
                        if isinstance(n, ast.ClassDef) and n.name == "Dialog")
        fonctions = [n for n in dialogue.body
                     if isinstance(n, ast.FunctionDef)
                     and n.name in ("PreparerCotisationsPourApercu",
                                    "VerifierCotisationsAvantEmission")]
        env = {"wx": wx, "_": lambda s: s, "datetime": datetime}
        util = types.ModuleType("Utils")
        util.UTILS_Adhesions_echeances = echeances
        util.UTILS_Adhesions = adhesions
        util.UTILS_Identification = types.SimpleNamespace(GetIDutilisateur=lambda: 3)
        with patch.dict(sys.modules, {"Utils": util}):
            exec(compile(ast.fix_missing_locations(
                ast.Module(body=fonctions, type_ignores=[])), str(CHEMIN), "exec"), env)
            ctx = self.contexte()
            self.assertTrue(env["PreparerCotisationsPourApercu"](ctx))
            self.assertEqual(appels["selection_initiale"], [0, 1])
            self.assertIn("Edgar", appels["labels"][1])
            self.assertEqual(appels["executions"][0]["selection_titulaires"], {100})
            self.assertTrue(env["VerifierCotisationsAvantEmission"](ctx, [11, 12]))
        self.assertEqual(appels["messages"], [])

    def test_changement_de_cotisations_bloque_sans_confirmation_automatique(self):
        nouvelle = {"propositions": [
            {"IDtitulaire": 999, "IDcompte_payeur": 11,
             "date_debut": D(2026, 9, 10), "montant": 7.5}], "a_verifier": []}
        wx, echeances, adhesions, appels = self.construire(apres=nouvelle)
        env = {"wx": wx, "_": lambda s: s, "datetime": datetime}
        util = types.ModuleType("Utils")
        util.UTILS_Adhesions_echeances = echeances
        util.UTILS_Adhesions = adhesions
        util.UTILS_Identification = types.SimpleNamespace(GetIDutilisateur=lambda: 3)
        racine = ast.parse(CHEMIN.read_text(encoding="utf-8"))
        dialogue = next(n for n in racine.body if isinstance(n, ast.ClassDef)
                        and n.name == "Dialog")
        fonctions = [n for n in dialogue.body if isinstance(n, ast.FunctionDef)
                     and n.name in ("PreparerCotisationsPourApercu",
                                    "VerifierCotisationsAvantEmission")]
        with patch.dict(sys.modules, {"Utils": util}):
            exec(compile(ast.fix_missing_locations(
                ast.Module(body=fonctions, type_ignores=[])), str(CHEMIN), "exec"), env)
            ctx = self.contexte()
            self.assertTrue(env["PreparerCotisationsPourApercu"](ctx))
            self.assertTrue(env["VerifierCotisationsAvantEmission"](ctx, [11]))
        # Test ci-dessus : la relecture reste stable apres la preparation.
        # Une nouvelle divergence est testee en remplacant Proposer.
        def changer(**kw):
            return {"propositions": [
                {"IDtitulaire": 1024, "IDcompte_payeur": 11,
                 "date_debut": D(2026, 9, 22), "montant": 7.5}],
                    "a_verifier": []}
        echeances.Proposer = changer
        with patch.dict(sys.modules, {"Utils": util}):
            self.assertFalse(env["VerifierCotisationsAvantEmission"](ctx, [11]))
        self.assertTrue(appels["messages"])

    def test_erreur_persistante_exige_accord_humain_au_stade_emission(self):
        wx, echeances, adhesions, appels = self.construire(erreur=True)
        env = {"wx": wx, "_": lambda s: s, "datetime": datetime}
        util = types.ModuleType("Utils")
        util.UTILS_Adhesions_echeances = echeances
        util.UTILS_Adhesions = adhesions
        util.UTILS_Identification = types.SimpleNamespace(GetIDutilisateur=lambda: 3)
        racine = ast.parse(CHEMIN.read_text(encoding="utf-8"))
        dialogue = next(n for n in racine.body if isinstance(n, ast.ClassDef)
                        and n.name == "Dialog")
        fonctions = [n for n in dialogue.body if isinstance(n, ast.FunctionDef)
                     and n.name in ("PreparerCotisationsPourApercu",
                                    "VerifierCotisationsAvantEmission")]
        with patch.dict(sys.modules, {"Utils": util}):
            exec(compile(ast.fix_missing_locations(
                ast.Module(body=fonctions, type_ignores=[])), str(CHEMIN), "exec"), env)
            ctx = self.contexte()
            self.assertTrue(env["PreparerCotisationsPourApercu"](ctx))
            wx.MessageBox = lambda *args: 2
            self.assertFalse(env["VerifierCotisationsAvantEmission"](ctx, [11]))
            wx.MessageBox = lambda *args: 1
            self.assertTrue(env["VerifierCotisationsAvantEmission"](ctx, [11]))


if __name__ == "__main__":
    unittest.main()
