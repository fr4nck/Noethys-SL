# -*- coding: utf-8 -*-
"""Choix humain des cotisations ; base SQLite fictive et wx simule.

Aucune connexion reelle ni aucun dossier de famille n'est utilise.
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

NOETHYS = Path(__file__).resolve().parents[1] / "noethys"
ASSISTANT = NOETHYS / "Dlg" / "DLG_Factures_generation.py"
SELECTION = NOETHYS / "Dlg" / "DLG_Factures_generation_selection.py"


class SelectionMetierTests(unittest.TestCase):
    def proposer(self, env):
        return E.Proposer(D(2026, 9, 1), D(2026, 9, 30),
                          D(2026, 10, 19), [1, 2])

    def test_une_personne_non_retenue_n_est_pas_facturee(self):
        with Env() as env:
            env.conso(100, D(2026, 9, 5), payeur=11)
            env.conso(200, D(2026, 9, 6), payeur=12)
            proposition = self.proposer(env)
            self.assertEqual({p["IDtitulaire"] for p in proposition["propositions"]},
                             {100, 200})
            resultats = E.Executer(proposition, confirmation=True,
                                  selection_titulaires=[100])
            self.assertEqual([r["statut"] for r in resultats], ["cree"])
            self.assertEqual(env.compte("cotisations", "IDindividu=100"), 1)
            self.assertEqual(env.compte("cotisations", "IDindividu=200"), 0)
            self.assertEqual(env.compte("prestations", "categorie='cotisation'"), 1)
            self.assertEqual([p["IDtitulaire"] for p in self.proposer(env)["propositions"]],
                             [200])

    def test_selection_vide_ne_cree_rien(self):
        with Env() as env:
            env.conso(100, D(2026, 9, 5))
            p = self.proposer(env)
            self.assertEqual(E.Executer(p, confirmation=True,
                                       selection_titulaires=[]), [])
            self.assertEqual(env.compte("cotisations"), 0)
            self.assertEqual(env.compte("prestations", "categorie='cotisation'"), 0)

    def test_identifiant_etranger_refuse_avant_ecriture(self):
        with Env() as env:
            env.conso(100, D(2026, 9, 5))
            p = self.proposer(env)
            with self.assertRaises(ValueError):
                E.Executer(p, confirmation=True, selection_titulaires=[999999])
            self.assertEqual(env.compte("cotisations"), 0)


def methode(path, nom, classe):
    racine = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    objet = next(x for x in racine.body if isinstance(x, ast.ClassDef)
                 and x.name == classe)
    noeud = next(x for x in objet.body if isinstance(x, ast.FunctionDef)
                 and x.name == nom)
    return compile(ast.fix_missing_locations(
        ast.Module(body=[noeud], type_ignores=[])), str(path), "exec")


class SelectionInterfaceTests(unittest.TestCase):
    def contexte(self):
        return types.SimpleNamespace(dictParametres={
            "prestations": ["cotisation", "consommation"],
            "date_debut": D(2026, 9, 1),
            "date_fin": D(2026, 9, 30),
            "listeActivites": [1],
            "IDcompte_payeur": None,
        })

    def preparer_harnais(self, choisi=(0,), panne=False):
        appels = {"messages": [], "executions": [], "labels": [],
                  "lectures": 0, "selection_initiale": []}
        candidats = [
            {"IDtitulaire": 100, "IDcompte_payeur": 11,
             "date_debut": D(2026, 9, 5), "montant": 7.5},
            {"IDtitulaire": 200, "IDcompte_payeur": 12,
             "date_debut": D(2026, 9, 6), "montant": 7.5},
        ]

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
            if panne:
                raise RuntimeError("2005 DNS")
            # Premiere lecture : 2 cotisations. Ensuite : le titulaire 100
            # a ete choisi et regle ; le 200 reste a la main de l'operateur.
            propositions = candidats if appels["lectures"] == 1 else [candidats[1]]
            return {"propositions": propositions, "a_verifier": []}

        def executer(proposition, **kw):
            appels["executions"].append(kw)
            return [{"statut": "cree"} for _ in kw["selection_titulaires"]]

        echeances = types.SimpleNamespace(
            Proposer=proposer, Executer=executer,
            Empreinte=lambda vals: tuple(sorted(x["IDtitulaire"] for x in vals)),
        )
        adhesions = types.SimpleNamespace(
            _liste_sql=lambda ids: "(" + ",".join(str(v) for v in ids) + ")",
            _lire=lambda req: [(100, "ALPHA", "Louis"), (200, "BETA", "Camille")],
        )
        util = types.ModuleType("Utils")
        util.UTILS_Adhesions_echeances = echeances
        util.UTILS_Adhesions = adhesions
        util.UTILS_Identification = types.SimpleNamespace(GetIDutilisateur=lambda: 3)
        globals_ = {"wx": wx, "_": lambda s: s, "datetime": datetime}
        for nom in ("PreparerCotisationsPourApercu", "VerifierCotisationsAvantEmission"):
            exec(methode(ASSISTANT, nom, "Dialog"), globals_)
        return wx, echeances, util, globals_, appels

    def test_personne_ecartee_et_autres_cotisations_conservees(self):
        wx, echeances, util, fonctions, appels = self.preparer_harnais()
        with patch.dict(sys.modules, {"Utils": util}):
            ctx = self.contexte()
            self.assertTrue(fonctions["PreparerCotisationsPourApercu"](ctx))
            self.assertEqual(appels["selection_initiale"], [0, 1])
            self.assertIn("Camille", appels["labels"][1])
            self.assertEqual(appels["executions"][0]["selection_titulaires"], {100})
            self.assertTrue(fonctions["VerifierCotisationsAvantEmission"](ctx, [11, 12]))
        self.assertEqual(appels["messages"], [])

    def test_changement_apres_apercu_exige_nouvelle_revue(self):
        wx, echeances, util, fonctions, appels = self.preparer_harnais()
        with patch.dict(sys.modules, {"Utils": util}):
            ctx = self.contexte()
            self.assertTrue(fonctions["PreparerCotisationsPourApercu"](ctx))
            echeances.Proposer = lambda **kw: {
                "propositions": [{"IDtitulaire": 999, "IDcompte_payeur": 11}],
                "a_verifier": []}
            self.assertFalse(fonctions["VerifierCotisationsAvantEmission"](ctx, [11]))
        self.assertTrue(appels["messages"])

    def test_panne_a_emission_demande_un_second_accord_expresse(self):
        wx, echeances, util, fonctions, appels = self.preparer_harnais(panne=True)
        with patch.dict(sys.modules, {"Utils": util}):
            ctx = self.contexte()
            self.assertTrue(fonctions["PreparerCotisationsPourApercu"](ctx))
            wx.MessageBox = lambda *args: wx.NO
            self.assertFalse(fonctions["VerifierCotisationsAvantEmission"](ctx, [11]))
            wx.MessageBox = lambda *args: wx.YES
            self.assertTrue(fonctions["VerifierCotisationsAvantEmission"](ctx, [11]))

    def executer_validation_factures(self, accord=True, controle=True):
        """Verifie l'ordre confirmation -> controle -> ecriture."""
        appels = []
        class Liste:
            def GetObjects(self):
                return [object()]
            def GetTracksCoches(self):
                return [types.SimpleNamespace(IDcompte_payeur=11)]

        class Dialogue:
            def __init__(self, *args, **kwargs):
                pass
            def ShowModal(self):
                appels.append("confirmation")
                return 1 if accord else 2
            def Destroy(self):
                pass

        def verifier(payeurs):
            self.assertEqual(payeurs, [11])
            appels.append("controle")
            return controle

        def sauvegarder():
            appels.append("sauvegarde")
            return [321]

        def preferences(**kw):
            appels.append("preferences")
            self.assertEqual(kw["mode"], "set")

        parent = types.SimpleNamespace(
            VerifierCotisationsAvantEmission=verifier,
            dictParametres={"prestations": ["cotisation"]})
        selecteur = types.SimpleNamespace(
            ctrl_factures=Liste(), parent=parent,
            SauvegardeFactures=sauvegarder,
            ctrl_option_montant=types.SimpleNamespace(GetMontant=lambda: 0.0))
        wx = types.SimpleNamespace(
            MessageDialog=Dialogue, YES_NO=4, YES_DEFAULT=8,
            CANCEL=16, ICON_QUESTION=32, ID_YES=1)
        glob = {"wx": wx, "_": lambda s: s,
                "UTILS_Parametres": types.SimpleNamespace(Parametres=preferences)}
        exec(methode(SELECTION, "Validation", "Panel"), glob)
        return glob["Validation"](selecteur), appels, parent

    def test_page_de_selection_n_ecrit_rien_si_garde_refuse(self):
        resultat, appels, _ = self.executer_validation_factures(controle=False)
        self.assertFalse(resultat)
        self.assertEqual(appels, ["confirmation", "controle"])

    def test_annuler_la_confirmation_evite_la_connexion_reseau(self):
        resultat, appels, _ = self.executer_validation_factures(accord=False)
        self.assertFalse(resultat)
        self.assertEqual(appels, ["confirmation"])

    def test_validation_finale_juste_avant_sauvegarde(self):
        resultat, appels, parent = self.executer_validation_factures()
        self.assertTrue(resultat)
        self.assertEqual(appels, ["confirmation", "controle",
                                  "sauvegarde", "preferences"])
        self.assertEqual(parent.listeFacturesGenerees, [321])


    @unittest.skipUnless(sys.platform == "win32", "interface native Windows requise")
    def test_vrai_dialogue_wx_permet_de_decocher_une_seule_personne(self):
        """La selection reelle wx 4.2 doit accepter le choix partiel."""
        import wx
        application = wx.GetApp() or wx.App(False)
        dlg = wx.MultiChoiceDialog(
            None, "Choix des cotisations", "Cotisations",
            ["Bénéficiaire fictif A", "Bénéficiaire fictif B"])
        # wx 4.2 ne garantit pas GetSelections() AVANT ShowModal :
        # le controle natif est initialise pendant l'ouverture du dialogue.
        # Reproduire donc exactement ce que verra un operateur.
        selections = []
        def inspecter_dialogue_ouvert():
            selections.append(list(dlg.GetSelections()))
            dlg.SetSelections([0])
            selections.append(list(dlg.GetSelections()))
            dlg.EndModal(wx.ID_OK)
        try:
            dlg.SetSelections([0, 1])  # ordre actuel du code applicatif
            wx.CallAfter(inspecter_dialogue_ouvert)
            self.assertEqual(dlg.ShowModal(), wx.ID_OK)
            self.assertEqual(selections, [[0, 1], [0]])
        finally:
            dlg.Destroy()
        self.assertIsNotNone(application)


if __name__ == "__main__":
    unittest.main()
