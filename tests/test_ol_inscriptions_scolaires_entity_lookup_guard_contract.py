#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Non-régression pour la garde ResultatReq() vide ajoutée dans
Ol/OL_Inscriptions_scolaires.py : GetInfosClasse, Impression, Ajouter.

Chaque méthode est extraite par AST (même technique que
test_dates_forfait_color_contract.py / test_entity_lookup_importation_guard_
contract.py) et exécutée isolément avec un faux GestionDB.DB(), un faux wx
et un ``self`` minimal (MagicMock), sans instancier de wx.Dialog réel ni
charger wx. Ces tests démontrent le contrat de retour de GetInfosClasse et
l'abandon de l'action dans Impression/Ajouter — pas le rendu final de la
ListView ou de la boîte de dialogue, qui reste du ressort d'une recette
manuelle.
"""

import ast
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "noethys" / "Ol" / "OL_Inscriptions_scolaires.py"


class FakeDB:
    """Double minimal de GestionDB.DB() : renvoie une file de résultats
    préconfigurés, un par appel de ResultatReq(), et trace les appels."""

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


def _extract_method(class_name: str, method_name: str, extra_namespace: dict):
    """Extrait UNE méthode de la classe ListView par AST et la compile
    isolément, sans exécuter le reste du fichier (donc sans wx réel)."""
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SOURCE_PATH))
    class_node = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    method_node = next(
        node for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    )
    module = ast.Module(body=[method_node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = dict(extra_namespace)
    exec(compile(module, str(SOURCE_PATH), "exec"), namespace)
    return namespace[method_name]


class FakeMessageDialog:
    """Double de wx.MessageDialog : trace message/titre/style et les
    appels ShowModal()/Destroy(), sans afficher quoi que ce soit."""

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
        return None

    def Destroy(self):
        self.destroyed = True


def _fake_wx():
    FakeMessageDialog.instances = []
    return types.SimpleNamespace(
        MessageDialog=FakeMessageDialog,
        OK=1,
        ICON_EXCLAMATION=2,
        ID_OK=5100,
        PORTRAIT=1,
    )


def _underscore(texte):
    return texte


class GetInfosClasseContractTests(unittest.TestCase):
    def _load(self, resultat):
        fake_db = FakeDB([resultat])
        fake_gestiondb = types.SimpleNamespace(DB=lambda: fake_db)
        get_infos_classe = _extract_method(
            "ListView", "GetInfosClasse",
            {"GestionDB": fake_gestiondb, "_": _underscore, "DateEngFr": lambda date: date},
        )
        return get_infos_classe, fake_db

    def test_empty_result_returns_none_without_indexerror_and_closes_db(self):
        get_infos_classe, fake_db = self._load(resultat=[])
        fake_self = mock.MagicMock()

        resultat = get_infos_classe(fake_self, IDclasse=42)

        self.assertIsNone(resultat)
        self.assertTrue(fake_db.close_appele)
        self.assertEqual(len(fake_db.requetes), 1)

    def test_normal_result_returns_historical_structure_and_closes_db(self):
        get_infos_classe, fake_db = self._load(
            resultat=[(7, "CP", "2024-09-01", "2025-07-01", "1;2")]
        )
        fake_self = mock.MagicMock()

        resultat = get_infos_classe(fake_self, IDclasse=42)

        self.assertTrue(fake_db.close_appele)
        self.assertEqual(resultat["IDecole"], 7)
        self.assertEqual(resultat["nom"], "CP")
        self.assertEqual(resultat["date_debut"], "2024-09-01")
        self.assertEqual(resultat["date_fin"], "2025-07-01")
        self.assertEqual(resultat["listeNiveaux"], [1, 2])
        self.assertIn("nomComplet", resultat)
        self.assertIn("periode", resultat)


def _fake_module_chain(dotted_path, leaf_module):
    """Construit les entrées sys.modules nécessaires pour qu'un
    ``from pkg import sous_module`` inline trouve le double sans jamais
    toucher le vrai fichier (qui importe wx réel)."""
    parts = dotted_path.split(".")
    entries = {dotted_path: leaf_module}
    for i in range(1, len(parts)):
        pkg_name = ".".join(parts[:i])
        entries.setdefault(pkg_name, types.ModuleType(pkg_name))
    return entries


class ImpressionEntityLookupGuardTests(unittest.TestCase):
    def _load(self, fake_wx):
        return _extract_method("ListView", "Impression", {"wx": fake_wx, "_": _underscore})

    def test_missing_classe_shows_error_and_stops_before_any_printing(self):
        fake_wx = _fake_wx()
        fake_printer_module = types.SimpleNamespace(ObjectListViewPrinter=mock.MagicMock())
        impression = self._load(fake_wx)

        fake_self = mock.MagicMock()
        fake_self.donnees = [mock.MagicMock()]
        fake_self.IDclasse = 42
        fake_self.GetInfosClasse.return_value = None

        with mock.patch.dict(sys.modules, _fake_module_chain("Utils.UTILS_Printer", fake_printer_module)):
            impression(fake_self)

        self.assertEqual(len(FakeMessageDialog.instances), 1)
        dlg = FakeMessageDialog.instances[0]
        self.assertTrue(dlg.shown)
        self.assertTrue(dlg.destroyed)
        fake_printer_module.ObjectListViewPrinter.assert_not_called()

    def test_existing_classe_still_prints_as_before(self):
        fake_wx = _fake_wx()
        fake_printer_module = types.SimpleNamespace(ObjectListViewPrinter=mock.MagicMock())
        impression = self._load(fake_wx)

        fake_self = mock.MagicMock()
        fake_self.donnees = [mock.MagicMock(), mock.MagicMock()]
        fake_self.IDclasse = 42
        fake_self.GetInfosClasse.return_value = {"nom": "CP", "periode": "Du 01/09 au 01/07"}

        with mock.patch.dict(sys.modules, _fake_module_chain("Utils.UTILS_Printer", fake_printer_module)):
            impression(fake_self, mode="preview")

        self.assertEqual(len(FakeMessageDialog.instances), 0)
        fake_printer_module.ObjectListViewPrinter.assert_called_once()
        _, kwargs = fake_printer_module.ObjectListViewPrinter.call_args
        self.assertEqual(kwargs["titre"], "CP")
        fake_printer_module.ObjectListViewPrinter.return_value.Preview.assert_called_once()


class AjouterEntityLookupGuardTests(unittest.TestCase):
    def _load(self, fake_wx):
        return _extract_method("ListView", "Ajouter", {"wx": fake_wx, "_": _underscore})

    def test_missing_classe_shows_error_and_never_opens_the_add_dialog(self):
        fake_wx = _fake_wx()
        fake_dlg_module = types.SimpleNamespace(Dialog=mock.MagicMock())
        ajouter = self._load(fake_wx)

        fake_self = mock.MagicMock()
        fake_self.IDclasse = 42
        fake_self.GetInfosClasse.return_value = None

        with mock.patch.dict(
            sys.modules, _fake_module_chain("Dlg.DLG_Saisie_inscriptions_scolaires", fake_dlg_module)
        ):
            ajouter(fake_self)

        self.assertEqual(len(FakeMessageDialog.instances), 1)
        dlg = FakeMessageDialog.instances[0]
        self.assertTrue(dlg.shown)
        self.assertTrue(dlg.destroyed)
        fake_dlg_module.Dialog.assert_not_called()
        fake_self.MAJ.assert_not_called()

    def test_existing_classe_still_opens_the_add_dialog_as_before(self):
        fake_wx = _fake_wx()
        fake_dlg_module = types.SimpleNamespace(Dialog=mock.MagicMock())
        fake_dlg_module.Dialog.return_value.ShowModal.return_value = fake_wx.ID_OK
        ajouter = self._load(fake_wx)

        fake_self = mock.MagicMock()
        fake_self.IDclasse = 42
        fake_self.GetInfosClasse.return_value = {
            "IDecole": 7, "nom": "CP", "date_debut": "2024-09-01",
            "date_fin": "2025-07-01", "listeNiveaux": [1],
        }

        with mock.patch.dict(
            sys.modules, _fake_module_chain("Dlg.DLG_Saisie_inscriptions_scolaires", fake_dlg_module)
        ):
            ajouter(fake_self)

        self.assertEqual(len(FakeMessageDialog.instances), 0)
        fake_dlg_module.Dialog.assert_called_once_with(fake_self, IDecole=7, IDclasse=42)
        fake_dlg_module.Dialog.return_value.SetNomClasse.assert_called_once_with("CP")
        fake_dlg_module.Dialog.return_value.SetNiveau.assert_called_once_with(1)
        fake_self.MAJ.assert_called_once_with(IDclasse=42)


if __name__ == "__main__":
    unittest.main()
