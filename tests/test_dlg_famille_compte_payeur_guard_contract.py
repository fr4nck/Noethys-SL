#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Non-régression pour la garde "compte payeur absent" de Dlg/DLG_Famille.py.

GetIDcomptePayeur rend désormais l'absence explicite (None) dans deux cas :
famille supprimée (aucune ligne) et famille sans compte payeur rattaché
(colonne NULL). Les cinq actions de menu qui consommaient cette valeur
abandonnent l'action avec un message au lieu de transmettre None aux
composants aval, où None signifie "aucun filtre", donc TOUTES les familles
(OL_Verification_ventilation.Importation l.51-54, OL_Rappels l.103-104).

Les méthodes sont extraites par AST et exécutées réellement avec un faux
GestionDB, un faux wx et de faux modules Dlg.* espionnés : le critère
principal testé ici n'est pas la présence d'un `if` mais le fait qu'aucun
composant aval ne soit JAMAIS atteint avec IDcompte_payeur=None.
Aucun wx.App réel n'est nécessaire.
"""

import ast
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "noethys" / "Dlg" / "DLG_Famille.py"

MESSAGE_ATTENDU = u"Cette famille n'a pas de compte payeur rattaché. Cette opération est impossible."

MENUS_VENTILATION = [
    ("MenuImprimerReleve", "DLG_Releve_prestations"),
    ("MenuGenererAttestation", "DLG_Impression_attestation"),
    ("MenuGenererDevis", "DLG_Impression_devis"),
    ("MenuGenererRappel", "DLG_Rappels_generation"),
]


# ---------------------------------------------------------------------------
# Extraction AST
# ---------------------------------------------------------------------------

def _find_method(tree, class_name, method_name):
    class_node = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return next(
        node for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    )


def _extract_methods(method_names, namespace):
    """Extrait des méthodes de Dialog comme fonctions autonomes partageant
    un même dict de globales (celui qu'on alimente en faux modules)."""
    tree = ast.parse(SOURCE_PATH.read_text(encoding="utf-8"), filename=str(SOURCE_PATH))
    nodes = [_find_method(tree, "Dialog", name) for name in method_names]
    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(SOURCE_PATH), "exec"), namespace)
    return {name: namespace[name] for name in method_names}


# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------

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


class FakeMessageDialog:
    instances = []

    def __init__(self, parent, message, titre, style):
        self.parent = parent
        self.message = message
        self.titre = titre
        self.style = style
        self.shown = False
        self.destroyed = False
        FakeMessageDialog.instances.append(self)

    def ShowModal(self):
        self.shown = True
        return 5100

    def Destroy(self):
        self.destroyed = True


class SpyDialog:
    """Dialogue métier aval espionné : toute construction est enregistrée,
    ce qui permet de prouver qu'aucun n'est atteint sur le chemin d'erreur."""

    def __init__(self, nom, journal):
        self.nom = nom
        self.journal = journal

    def Dialog(self, *args, **kwargs):
        self.journal.append((self.nom, args, kwargs))
        return mock.MagicMock()

    # DLG_Rappels_generation.Dialog(self) puis dlg.SetFamille(...)
    def __call__(self, *args, **kwargs):
        return self.Dialog(*args, **kwargs)


class SpyVerification:
    """Faux module DLG_Verification_ventilation : enregistre chaque appel à
    Verification(), avec l'argument reçu."""

    def __init__(self, tracks=None):
        self.appels = []
        self._tracks = [] if tracks is None else tracks

    def Verification(self, IDcompte_payeur=None):
        self.appels.append(IDcompte_payeur)
        return self._tracks


def _fake_wx():
    FakeMessageDialog.instances = []
    return types.SimpleNamespace(
        MessageDialog=FakeMessageDialog,
        OK=4,
        ICON_EXCLAMATION=512,
        ICON_ERROR=256,
        ICON_INFORMATION=2048,
        ID_OK=5100,
    )


def _underscore(texte):
    return texte


def _fake_dlg_package(spy_verification, journal_dialogues):
    """Construit un faux package Dlg pour les imports inline
    `from Dlg import DLG_xxx` présents dans les méthodes extraites."""
    fake_dlg = types.ModuleType("Dlg")
    fake_dlg.DLG_Verification_ventilation = spy_verification
    modules = {"Dlg": fake_dlg}
    for nom in ("DLG_Releve_prestations", "DLG_Impression_attestation",
                "DLG_Impression_devis", "DLG_Rappels_generation",
                "DLG_Liste_rappels"):
        spy = SpyDialog(nom, journal_dialogues)
        setattr(fake_dlg, nom, spy)
        sous_module = types.ModuleType("Dlg.%s" % nom)
        sous_module.Dialog = spy.Dialog
        modules["Dlg.%s" % nom] = sous_module
    return modules


class Harness:
    """Porteur minimal reproduisant le sous-ensemble de Dialog utilisé par
    GetIDcomptePayeur et les cinq menus."""

    def __init__(self, resultat_db, droits=True):
        self.IDfamille = 7
        self.fake_db = FakeDB(resultat_db)
        self.destroy_appele = 0
        self.endmodal_appele = []
        self.journal_dialogues = []
        self.spy_verification = SpyVerification()
        self.droits = droits

    def Destroy(self):
        self.destroy_appele += 1

    def EndModal(self, code):
        self.endmodal_appele.append(code)


def _build(resultat_db, method_names, droits=True, tracks=None):
    harness = Harness(resultat_db, droits=droits)
    if tracks is not None:
        harness.spy_verification = SpyVerification(tracks=tracks)
    fake_wx = _fake_wx()
    namespace = {
        "GestionDB": types.SimpleNamespace(DB=lambda: harness.fake_db),
        "wx": fake_wx,
        "_": _underscore,
        "UTILS_Utilisateurs": types.SimpleNamespace(
            VerificationDroitsUtilisateurActuel=lambda *a, **k: droits
        ),
    }
    methods = _extract_methods(["GetIDcomptePayeur"] + list(method_names), namespace)
    for name, func in methods.items():
        setattr(harness, name, types.MethodType(func, harness))
    modules = _fake_dlg_package(harness.spy_verification, harness.journal_dialogues)
    return harness, fake_wx, modules


# ---------------------------------------------------------------------------
# A / B / C — contrat de GetIDcomptePayeur
# ---------------------------------------------------------------------------

class GetIDcomptePayeurContractTests(unittest.TestCase):
    def test_A_compte_valide_retour_historique(self):
        harness, _wx, _modules = _build([(123,)], [])

        resultat = harness.GetIDcomptePayeur()

        self.assertEqual(resultat, 123)
        self.assertTrue(harness.fake_db.close_appele)
        self.assertEqual(len(harness.fake_db.requetes), 1)

    def test_B_famille_avec_compte_payeur_null_retourne_none(self):
        harness, _wx, _modules = _build([(None,)], [])

        resultat = harness.GetIDcomptePayeur()

        self.assertIsNone(resultat)
        self.assertTrue(harness.fake_db.close_appele)

    def test_C_famille_absente_retourne_none_sans_indexerror(self):
        harness, _wx, _modules = _build([], [])

        resultat = harness.GetIDcomptePayeur()

        self.assertIsNone(resultat)
        self.assertTrue(harness.fake_db.close_appele)


# ---------------------------------------------------------------------------
# D — les 4 menus passant par Verification
# ---------------------------------------------------------------------------

class MenusVentilationSansComptePayeurTests(unittest.TestCase):
    def _executer(self, nom_menu, resultat_db):
        harness, fake_wx, modules = _build(resultat_db, [nom_menu])
        with mock.patch.dict(sys.modules, modules):
            retour = getattr(harness, nom_menu)(event=None)
        return harness, retour

    def test_compte_absent_abandonne_sans_appeler_verification(self):
        for nom_menu, nom_dialogue in MENUS_VENTILATION:
            for etiquette, resultat_db in (("famille absente", []), ("compte NULL", [(None,)])):
                with self.subTest(menu=nom_menu, cas=etiquette):
                    harness, retour = self._executer(nom_menu, resultat_db)

                    # Critère principal : aucune portée élargie.
                    self.assertEqual(
                        harness.spy_verification.appels, [],
                        "Verification ne doit jamais être appelée sans compte payeur",
                    )
                    self.assertEqual(
                        harness.journal_dialogues, [],
                        "aucun dialogue métier aval ne doit être construit",
                    )
                    # Message explicite affiché puis détruit.
                    messages = [d for d in FakeMessageDialog.instances if d.titre == "Erreur"]
                    self.assertEqual(len(messages), 1)
                    self.assertEqual(messages[0].message, MESSAGE_ATTENDU)
                    self.assertTrue(messages[0].shown)
                    self.assertTrue(messages[0].destroyed)
                    # L'action est abandonnée, la fiche reste ouverte.
                    self.assertIsNone(retour)
                    self.assertEqual(harness.destroy_appele, 0)
                    self.assertEqual(harness.endmodal_appele, [])


# ---------------------------------------------------------------------------
# E — MenuListeRappels
# ---------------------------------------------------------------------------

class MenuListeRappelsSansComptePayeurTests(unittest.TestCase):
    def test_compte_absent_ne_construit_jamais_la_liste(self):
        for etiquette, resultat_db in (("famille absente", []), ("compte NULL", [(None,)])):
            with self.subTest(cas=etiquette):
                harness, fake_wx, modules = _build(resultat_db, ["MenuListeRappels"])
                with mock.patch.dict(sys.modules, modules):
                    retour = harness.MenuListeRappels(event=None)

                self.assertEqual(
                    harness.journal_dialogues, [],
                    "DLG_Liste_rappels.Dialog ne doit jamais être construit sans compte payeur",
                )
                messages = [d for d in FakeMessageDialog.instances if d.titre == "Erreur"]
                self.assertEqual(len(messages), 1)
                self.assertEqual(messages[0].message, MESSAGE_ATTENDU)
                self.assertIsNone(retour)
                self.assertEqual(harness.destroy_appele, 0)
                self.assertEqual(harness.endmodal_appele, [])


# ---------------------------------------------------------------------------
# F — chemins normaux (compte payeur valide)
# ---------------------------------------------------------------------------

class CheminsNormauxTests(unittest.TestCase):
    def test_verification_recoit_exactement_lid_et_le_dialogue_souvre(self):
        for nom_menu, nom_dialogue in MENUS_VENTILATION:
            with self.subTest(menu=nom_menu):
                harness, fake_wx, modules = _build([(123,)], [nom_menu], tracks=[])
                with mock.patch.dict(sys.modules, modules):
                    getattr(harness, nom_menu)(event=None)

                self.assertEqual(
                    harness.spy_verification.appels, [123],
                    "le chemin nominal doit transmettre l'ID exact, une seule fois",
                )
                self.assertEqual(len(harness.journal_dialogues), 1)
                self.assertEqual(harness.journal_dialogues[0][0], nom_dialogue)
                self.assertEqual(
                    [d for d in FakeMessageDialog.instances if d.titre == "Erreur"], [],
                )

    def test_ventilation_incomplete_bloque_comme_avant(self):
        harness, fake_wx, modules = _build([(123,)], ["MenuImprimerReleve"], tracks=["track"])
        with mock.patch.dict(sys.modules, modules):
            harness.MenuImprimerReleve(event=None)

        self.assertEqual(harness.spy_verification.appels, [123])
        self.assertEqual(harness.journal_dialogues, [])
        titres = [d.titre for d in FakeMessageDialog.instances]
        self.assertIn("Ventilation", titres)
        self.assertNotIn("Erreur", titres)

    def test_liste_rappels_transmet_exactement_lid(self):
        harness, fake_wx, modules = _build([(123,)], ["MenuListeRappels"])
        with mock.patch.dict(sys.modules, modules):
            harness.MenuListeRappels(event=None)

        self.assertEqual(len(harness.journal_dialogues), 1)
        nom, args, kwargs = harness.journal_dialogues[0]
        self.assertEqual(nom, "DLG_Liste_rappels")
        self.assertEqual(kwargs.get("IDcompte_payeur"), 123)
        self.assertEqual([d for d in FakeMessageDialog.instances if d.titre == "Erreur"], [])


# ---------------------------------------------------------------------------
# G — les droits utilisateur restent prioritaires (comportement historique)
# ---------------------------------------------------------------------------

class DroitsUtilisateurTests(unittest.TestCase):
    def test_droits_refuses_abandonnent_avant_toute_requete(self):
        harness, fake_wx, modules = _build([], ["MenuImprimerReleve"], droits=False)
        with mock.patch.dict(sys.modules, modules):
            harness.MenuImprimerReleve(event=None)

        self.assertEqual(harness.fake_db.requetes, [], "aucune requête si les droits sont refusés")
        self.assertEqual(harness.spy_verification.appels, [])
        self.assertEqual(harness.journal_dialogues, [])
        self.assertEqual(FakeMessageDialog.instances, [])


if __name__ == "__main__":
    unittest.main()
