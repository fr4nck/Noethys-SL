#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Non-régression pour la dégradation gracieuse ajoutée dans
Dlg/DLG_Inscription.py quand une activité référencée n'existe plus :

- Page_Activite.GetDictActivite retourne None au lieu de lever IndexError ;
- CTRL_Activite.MAJ bascule vers un état neutre (IDactivite=None, label="") ;
- ListBox.Importation_groupes / Importation_categories ne font rien si
  controller.dictActivite est None.

Les classes/méthodes réellement concernées sont extraites par AST et
exécutées avec de vrais objets minimaux (un faux GestionDB.DB(), un faux
wx.ListBox qui reproduit fidèlement Set/Select/SetSelection/GetSelection),
pas de simple recherche de chaînes. Aucun wx.App réel n'est nécessaire.
"""

import ast
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "noethys" / "Dlg" / "DLG_Inscription.py"


def _source_tree():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    return source, ast.parse(source, filename=str(SOURCE_PATH))


def _find_class(tree, name):
    return next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == name
    )


def _find_method(class_node, name):
    return next(
        node for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _exec_nodes(nodes, namespace):
    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(SOURCE_PATH), "exec"), namespace)
    return namespace


def _extract_class(name, namespace):
    _, tree = _source_tree()
    node = _find_class(tree, name)
    ns = _exec_nodes([node], dict(namespace))
    return ns[name]


def _extract_methods(class_name, method_names):
    """Extrait des méthodes d'une classe comme fonctions autonomes
    (premier paramètre = self), sans exécuter le reste de la classe."""
    _, tree = _source_tree()
    class_node = _find_class(tree, class_name)
    nodes = [_find_method(class_node, name) for name in method_names]
    ns = _exec_nodes(nodes, {})
    return {name: ns[name] for name in method_names}


# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------

class FakeDB:
    """File de résultats préconfigurés, un par appel ResultatReq()."""

    def __init__(self, resultats):
        self._resultats = list(resultats)
        self.requetes = []
        self.close_appele = False

    def ExecuterReq(self, req):
        self.requetes.append(req)

    def ResultatReq(self):
        return self._resultats.pop(0)

    def Close(self):
        self.close_appele = True


class FakeWxListBox:
    """Reproduit le sous-ensemble de wx.ListBox utilisé par ListBox :
    Set() remplace les items et réinitialise la sélection, comme le vrai
    contrôle wx (c'est cette réinitialisation que ListBox.MAJ() compense
    en retentant SetID(selection_actuelle) sur la nouvelle liste)."""

    def __init__(self, parent, id=-1, choices=None):
        self._choices = list(choices) if choices else []
        self._selection = -1

    def Set(self, items):
        self._choices = list(items)
        self._selection = -1

    def GetSelection(self):
        return self._selection

    def SetSelection(self, index):
        self._selection = index

    def Select(self, index):
        self._selection = index


def _make_listbox_class():
    fake_wx = types.SimpleNamespace(ListBox=FakeWxListBox)
    return _extract_class("ListBox", {"wx": fake_wx})


class FakeStaticText:
    def __init__(self):
        self._label = ""

    def SetLabel(self, label):
        self._label = label

    def GetLabel(self):
        return self._label


class FakeCtrlActivite:
    """Double minimal de CTRL_Activite : les méthodes MAJ/GetID/GetNomActivite
    extraites du vrai code sont attachées dessus, seul __init__ est simulé
    pour éviter de reconstruire les widgets wx (StaticBox/sizers) sans
    rapport avec la garde testée."""

    def __init__(self, controller):
        self.controller = controller
        self.IDactivite = None
        self.ctrl_activite = FakeStaticText()
        self.layout_calls = 0

    def Layout(self):
        self.layout_calls += 1


_ctrl_activite_methods = _extract_methods("CTRL_Activite", ["MAJ", "GetID", "GetNomActivite"])
for _name, _func in _ctrl_activite_methods.items():
    setattr(FakeCtrlActivite, _name, _func)


def _underscore(texte):
    return texte


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


class FakeDlgSelectionActivite:
    """Double du sélecteur DLG_Selection_activite.Dialog : renvoie un ID
    préconfiguré au ShowModal(), pour simuler à la fois une sélection
    réussie et la disparition TOCTOU de l'activité choisie."""

    instances = []

    def __init__(self, parent):
        self.parent = parent
        self.destroyed = False
        FakeDlgSelectionActivite.instances.append(self)

    def SetIDactivite(self, IDactivite=None):
        self.id_initial = IDactivite

    def ShowModal(self):
        return 5100  # wx.ID_OK

    def GetIDactivite(self):
        return self.selected_id

    def Destroy(self):
        self.destroyed = True


def _fake_page_activite(listbox_class, id_activite_selectionnee=None):
    """Construit un porteur minimal reproduisant le sous-ensemble d'attributs
    de Page_Activite consommé par GetDictActivite/SetIDactivite/
    GetIDactivite/Importation/Validation, avec de VRAIS ListBox (extraits du
    fichier réel) et un double minimal pour CTRL_Activite, de façon à
    exécuter réellement le cycle vidage/repeuplement (pas un mock muet)."""

    class FakePageActivite(object):
        pass

    page = FakePageActivite()
    page.dictActivite = None
    page.IDgroupe = None
    page.IDinscription = 1
    page.IDindividu = 1
    page.cp = None
    page.ville = None
    page.mode = "saisie"
    page.date_inscription = None
    page.ancien_statut = None
    page.controller = mock.MagicMock()
    page.ctrl_groupes = listbox_class(parent=None, controller=page, type="groupes")
    page.ctrl_categories = listbox_class(parent=None, controller=page, type="categories")
    page.ctrl_activite = FakeCtrlActivite(controller=page)
    page.ctrl_check_depart = mock.MagicMock()
    page.ctrl_date_depart = mock.MagicMock()
    return page


def _load_page_activite_methods():
    return _extract_methods(
        "Page_Activite",
        ["GetDictActivite", "SetIDactivite", "GetIDactivite", "Importation", "Validation"],
    )


def _bind(page, methods, names):
    for name in names:
        setattr(page, name, types.MethodType(methods[name], page))


DICT_ACTIVITE_A_RESULTATS = [
    [("Multisport", "MS", "2024-09-01", "2025-07-01", None, 0)],  # activités
    [(2, 3)],  # inscriptions groupées : IDgroupe=2 -> 3 inscrits
    [(2, "GroupeA", None)],  # groupes
    [(9, "Tarif normal")],  # categories_tarifs
    [],  # categories_tarifs_villes
]


# ---------------------------------------------------------------------------
# A/B — GetDictActivite
# ---------------------------------------------------------------------------

class GetDictActiviteTests(unittest.TestCase):
    def _load(self, fake_db):
        methods = _extract_methods("Page_Activite", ["GetDictActivite"])
        gestiondb = types.SimpleNamespace(DB=lambda: fake_db)
        namespace = {"GestionDB": gestiondb}
        ns = _exec_nodes(
            [_find_method(_find_class(_source_tree()[1], "Page_Activite"), "GetDictActivite")],
            namespace,
        )
        return ns["GetDictActivite"]

    def test_activite_absente_retourne_none_sans_indexerror_et_ferme_la_db(self):
        fake_db = FakeDB(resultats=[[]])
        get_dict_activite = self._load(fake_db)

        resultat = get_dict_activite(None, IDactivite=999)

        self.assertIsNone(resultat)
        self.assertTrue(fake_db.close_appele)
        self.assertEqual(
            len(fake_db.requetes), 1,
            "les requêtes inscriptions/groupes/catégories ne doivent jamais être exécutées",
        )

    def test_activite_presente_chemin_historique_inchange(self):
        fake_db = FakeDB(resultats=[row for row in DICT_ACTIVITE_A_RESULTATS])
        get_dict_activite = self._load(fake_db)

        resultat = get_dict_activite(None, IDactivite=5)

        self.assertIsNotNone(resultat)
        self.assertEqual(resultat["nom"], "Multisport")
        self.assertEqual(resultat["IDactivite"], 5)
        self.assertEqual(len(resultat["groupes"]), 1)
        self.assertEqual(resultat["groupes"][0]["nom"], "GroupeA")
        self.assertEqual(len(resultat["categories_tarifs"]), 1)
        self.assertTrue(fake_db.close_appele)
        self.assertEqual(len(fake_db.requetes), 5)


# ---------------------------------------------------------------------------
# C — CTRL_Activite.MAJ
# ---------------------------------------------------------------------------

class CtrlActiviteMajTests(unittest.TestCase):
    def test_dictactivite_none_etat_neutre_sans_exception(self):
        controller = mock.MagicMock()
        controller.dictActivite = None
        ctrl = FakeCtrlActivite(controller=controller)
        ctrl.IDactivite = 42  # valeur d'une activité précédente, doit être écrasée

        ctrl.MAJ()

        self.assertIsNone(ctrl.IDactivite)
        self.assertEqual(ctrl.ctrl_activite.GetLabel(), "")
        self.assertEqual(ctrl.layout_calls, 1)

    def test_dictactivite_present_chemin_historique_inchange(self):
        controller = mock.MagicMock()
        controller.dictActivite = {"IDactivite": 5, "nom": "Multisport"}
        ctrl = FakeCtrlActivite(controller=controller)

        ctrl.MAJ()

        self.assertEqual(ctrl.IDactivite, 5)
        self.assertEqual(ctrl.ctrl_activite.GetLabel(), "Multisport")
        self.assertEqual(ctrl.layout_calls, 1)


# ---------------------------------------------------------------------------
# D — ListBox.Importation_groupes / Importation_categories
# ---------------------------------------------------------------------------

class ListBoxImportationGuardTests(unittest.TestCase):
    def test_dictactivite_none_ne_leve_rien_et_najoute_rien(self):
        ListBox = _make_listbox_class()
        controller = mock.MagicMock()
        controller.dictActivite = None

        listbox_groupes = ListBox(parent=None, controller=controller, type="groupes")
        listbox_groupes.Importation_groupes()
        self.assertEqual(listbox_groupes.listeDonnees, [])

        listbox_categories = ListBox(parent=None, controller=controller, type="categories")
        listbox_categories.Importation_categories()
        self.assertEqual(listbox_categories.listeDonnees, [])

    def test_dictactivite_present_chemin_historique_inchange(self):
        ListBox = _make_listbox_class()
        controller = mock.MagicMock()
        controller.dictActivite = {
            "groupes": [{"IDgroupe": 2, "nom": "GroupeA"}],
            "categories_tarifs": [{"IDcategorie_tarif": 9, "nom": "Tarif normal", "listeVilles": []}],
        }

        listbox_groupes = ListBox(parent=None, controller=controller, type="groupes")
        listbox_groupes.Importation_groupes()
        self.assertEqual(listbox_groupes.listeDonnees, [{"ID": 2, "label": "GroupeA"}])

        listbox_categories = ListBox(parent=None, controller=controller, type="categories")
        listbox_categories.Importation_categories()
        self.assertEqual(
            listbox_categories.listeDonnees,
            [{"ID": 9, "label": "Tarif normal", "listeVilles": []}],
        )


# ---------------------------------------------------------------------------
# E — absence de résidu (charge A, puis bascule sur activité disparue)
# ---------------------------------------------------------------------------

class AbsenceDeResiduTests(unittest.TestCase):
    def test_aucune_information_de_lancienne_activite_ne_survit(self):
        ListBox = _make_listbox_class()
        page = _fake_page_activite(ListBox)
        methods = _load_page_activite_methods()
        _bind(page, methods, ["GetDictActivite", "SetIDactivite", "GetIDactivite"])

        # 1) Charge l'activité A, bien réelle.
        # GetDictActivite est liée dynamiquement (types.MethodType) : GestionDB
        # est résolu comme nom global de la fonction extraite elle-même.
        fake_db_a = FakeDB(resultats=[row for row in DICT_ACTIVITE_A_RESULTATS])
        page.GetDictActivite.__func__.__globals__["GestionDB"] = types.SimpleNamespace(DB=lambda: fake_db_a)
        page.SetIDactivite(5)

        self.assertEqual(page.dictActivite["nom"], "Multisport")
        self.assertEqual(page.ctrl_activite.ctrl_activite.GetLabel(), "Multisport")
        self.assertEqual(page.ctrl_groupes.listeDonnees, [{"ID": 2, "label": "GroupeA"}])
        self.assertEqual(
            page.ctrl_categories.listeDonnees,
            [{"ID": 9, "label": "Tarif normal", "listeVilles": []}],
        )

        # 2) L'activité A a disparu entre-temps (même méthode, nouvelle DB vide).
        fake_db_absent = FakeDB(resultats=[[]])
        page.GetDictActivite.__func__.__globals__["GestionDB"] = types.SimpleNamespace(DB=lambda: fake_db_absent)
        page.SetIDactivite(5)

        self.assertIsNone(page.dictActivite)
        self.assertIsNone(page.ctrl_activite.IDactivite)
        self.assertEqual(
            page.ctrl_activite.ctrl_activite.GetLabel(), "",
            "le label ne doit plus afficher 'Multisport'",
        )
        self.assertEqual(page.ctrl_groupes.listeDonnees, [], "aucun groupe de A ne doit rester")
        self.assertEqual(page.ctrl_categories.listeDonnees, [], "aucune catégorie de A ne doit rester")
        # ListBox.MAJ() a bien tenté de réappliquer l'ancienne sélection sur
        # la liste vide, sans laisser de sélection fantôme :
        self.assertEqual(page.ctrl_groupes.GetID(), None)
        self.assertEqual(page.ctrl_categories.GetID(), None)


# ---------------------------------------------------------------------------
# F — chemin historique (Importation)
# ---------------------------------------------------------------------------

class CheminHistoriqueImportationTests(unittest.TestCase):
    def test_inscription_avec_activite_supprimee_continue_sans_exception(self):
        ListBox = _make_listbox_class()
        page = _fake_page_activite(ListBox)
        page.mode = "modification"
        methods = _load_page_activite_methods()
        _bind(page, methods, ["GetDictActivite", "SetIDactivite", "GetIDactivite", "Importation"])
        page.Importation.__func__.__globals__["UTILS_Dates"] = types.SimpleNamespace(
            DateEngEnDateDD=lambda valeur: "converti:%s" % valeur
        )

        fake_db_inscription = FakeDB(resultats=[
            [(5, 2, 9, "2024-09-01", "2025-01-15", "ok")],  # SELECT ... FROM inscriptions
        ])
        fake_db_activite = FakeDB(resultats=[[]])  # activité 5 : disparue

        db_calls = {"n": 0}
        dbs = [fake_db_inscription, fake_db_activite]

        def _db_factory():
            db = dbs[db_calls["n"]]
            db_calls["n"] += 1
            return db

        # GetDictActivite et Importation partagent le même __globals__ (extraits
        # en un seul appel à _load_page_activite_methods) : un seul réglage suffit.
        page.Importation.__func__.__globals__["GestionDB"] = types.SimpleNamespace(DB=_db_factory)

        page.Importation()

        self.assertIsNone(page.dictActivite)
        self.assertEqual(page.IDgroupe, 2, "le groupe historique reste mémorisé")
        self.assertEqual(page.date_inscription, "converti:2024-09-01", "la date d'inscription reste chargée")
        self.assertEqual(page.ancien_statut, "ok", "le statut historique reste chargé")
        page.ctrl_check_depart.SetValue.assert_called_once_with(True)
        page.ctrl_date_depart.SetDate.assert_called_once_with("converti:2025-01-15")
        self.assertEqual(page.ctrl_activite.ctrl_activite.GetLabel(), "")
        self.assertEqual(page.ctrl_groupes.listeDonnees, [])


# ---------------------------------------------------------------------------
# G — Validation avec dictActivite=None
# ---------------------------------------------------------------------------

class ValidationSansActiviteTests(unittest.TestCase):
    def test_validation_retourne_false_et_naccede_a_rien_dautre(self):
        _, tree = _source_tree()
        class_node = _find_class(tree, "Page_Activite")
        node = _find_method(class_node, "Validation")
        FakeMessageDialog.instances = []
        fake_wx = types.SimpleNamespace(
            MessageDialog=FakeMessageDialog,
            OK=16,
            ICON_EXCLAMATION=32,
        )
        ns = _exec_nodes([node], {"wx": fake_wx, "_": _underscore})
        validation = ns["Validation"]

        class MinimalSelf(object):
            """Ne possède QUE ce dont Validation() a besoin avant le
            court-circuit : dictActivite et GetIDactivite. Tout accès à un
            attribut au-delà (ctrl_groupes, controller, DB...) ferait
            planter le test avec AttributeError, ce qui prouve
            mécaniquement qu'aucune logique ultérieure n'est atteinte."""

            dictActivite = None

            def GetIDactivite(self):
                return None if self.dictActivite is None else self.dictActivite["IDactivite"]

        resultat = validation(MinimalSelf())

        self.assertFalse(resultat)
        self.assertEqual(len(FakeMessageDialog.instances), 1)
        self.assertIn(
            "sélectionner une activité",
            FakeMessageDialog.instances[0].message,
        )
        self.assertTrue(FakeMessageDialog.instances[0].shown)
        self.assertTrue(FakeMessageDialog.instances[0].destroyed)


# ---------------------------------------------------------------------------
# H — Sauvegarde jamais appelée
# ---------------------------------------------------------------------------

class OnBoutonOkSansActiviteTests(unittest.TestCase):
    def test_sauvegarde_jamais_appelee_si_validation_echoue(self):
        _, tree = _source_tree()
        class_node = _find_class(tree, "Dialog")
        node = _find_method(class_node, "OnBoutonOk")
        ns = _exec_nodes([node], {"GestionDB": mock.MagicMock()})
        on_bouton_ok = ns["OnBoutonOk"]

        fake_self = mock.MagicMock()
        fake_self.ctrl_parametres.Validation.return_value = False

        resultat = on_bouton_ok(fake_self, event=None)

        self.assertFalse(resultat)
        fake_self.ctrl_parametres.GetPageAvecCode.assert_not_called()


# ---------------------------------------------------------------------------
# I / J — changement interactif (OnBoutonActivites)
# ---------------------------------------------------------------------------

class OnBoutonActivitesTests(unittest.TestCase):
    def _load(self, selected_id):
        _, tree = _source_tree()
        class_node = _find_class(tree, "Page_Activite")
        node = _find_method(class_node, "OnBoutonActivites")
        FakeDlgSelectionActivite.instances = []
        FakeDlgSelectionActivite.selected_id = selected_id
        fake_wx = types.SimpleNamespace(ID_OK=5100)
        fake_dlg_module = types.SimpleNamespace(Dialog=FakeDlgSelectionActivite)
        ns = _exec_nodes(
            [node],
            {"wx": fake_wx, "DLG_Selection_activite": fake_dlg_module},
        )
        return ns["OnBoutonActivites"]

    def test_changement_interactif_reussi_chemin_historique_inchange(self):
        ListBox = _make_listbox_class()
        page = _fake_page_activite(ListBox)
        methods = _load_page_activite_methods()
        _bind(page, methods, ["GetDictActivite", "SetIDactivite", "GetIDactivite"])
        fake_db = FakeDB(resultats=[row for row in DICT_ACTIVITE_A_RESULTATS])
        page.GetDictActivite.__func__.__globals__["GestionDB"] = types.SimpleNamespace(DB=lambda: fake_db)

        on_bouton_activites = self._load(selected_id=5)
        on_bouton_activites(page, event=None)

        self.assertEqual(page.dictActivite["nom"], "Multisport")
        self.assertEqual(page.ctrl_activite.ctrl_activite.GetLabel(), "Multisport")
        self.assertTrue(FakeDlgSelectionActivite.instances[0].destroyed)

    def test_toctou_activite_disparue_avant_getdictactivite(self):
        ListBox = _make_listbox_class()
        page = _fake_page_activite(ListBox)
        methods = _load_page_activite_methods()
        _bind(page, methods, ["GetDictActivite", "SetIDactivite", "GetIDactivite"])

        # Charge d'abord une activité valide pour prouver l'absence de résidu.
        fake_db_a = FakeDB(resultats=[row for row in DICT_ACTIVITE_A_RESULTATS])
        page.GetDictActivite.__func__.__globals__["GestionDB"] = types.SimpleNamespace(DB=lambda: fake_db_a)
        page.SetIDactivite(5)
        self.assertEqual(page.dictActivite["nom"], "Multisport")

        # Le sélecteur renvoie un ID valide au moment du clic, mais
        # l'activité a disparu au moment de la ré-interrogation.
        fake_db_disparue = FakeDB(resultats=[[]])
        page.GetDictActivite.__func__.__globals__["GestionDB"] = types.SimpleNamespace(DB=lambda: fake_db_disparue)

        on_bouton_activites = self._load(selected_id=7)
        on_bouton_activites(page, event=None)

        self.assertIsNone(page.dictActivite)
        self.assertIsNone(page.ctrl_activite.IDactivite)
        self.assertEqual(page.ctrl_activite.ctrl_activite.GetLabel(), "")
        self.assertEqual(page.ctrl_groupes.listeDonnees, [])
        self.assertEqual(page.ctrl_categories.listeDonnees, [])


if __name__ == "__main__":
    unittest.main()
