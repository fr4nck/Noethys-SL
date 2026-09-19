#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Non-régression pour la garde ResultatReq() vide ajoutée dans
Dlg/DLG_Saisie_inscriptions_scolaires.py : Dialog.OnBoutonOk.

La méthode est extraite par AST et exécutée isolément avec de faux objets DB
et wx. Le test du chemin absent démontre que la classe supprimée ne provoque
plus d'IndexError, que le BusyInfo est libéré avant le message d'erreur et
qu'aucune écriture n'est tentée. Le chemin nominal vérifie que les insertions
historiques restent inchangées.
"""

import ast
import datetime
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "noethys" / "Dlg" / "DLG_Saisie_inscriptions_scolaires.py"


def _extract_method(extra_namespace):
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SOURCE_PATH))
    class_node = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Dialog"
    )
    method_node = next(
        node for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == "OnBoutonOk"
    )
    module = ast.Module(body=[method_node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = dict(extra_namespace)
    exec(compile(module, str(SOURCE_PATH), "exec"), namespace)
    return namespace["OnBoutonOk"]


class FakeDB:
    def __init__(self, resultat=None):
        self.resultat = [] if resultat is None else resultat
        self.requetes = []
        self.inserts = []
        self.close_appele = False

    def ExecuterReq(self, req):
        self.requetes.append(req)

    def ResultatReq(self):
        return self.resultat

    def ReqInsert(self, table, donnees):
        self.inserts.append((table, donnees))
        return len(self.inserts)

    def Close(self):
        self.close_appele = True


class DBFactory:
    def __init__(self, dbs):
        self.dbs = list(dbs)
        self.calls = 0

    def __call__(self):
        db = self.dbs[self.calls]
        self.calls += 1
        return db


class FakeMessageDialog:
    instances = []
    events = None

    def __init__(self, parent, message, titre, style):
        self.message = message
        self.titre = titre
        self.style = style
        self.destroyed = False
        FakeMessageDialog.instances.append(self)
        if FakeMessageDialog.events is not None:
            FakeMessageDialog.events.append(("dialog_create", titre, message))

    def ShowModal(self):
        if self.titre == "Confirmation":
            return 5103
        return 5100

    def Destroy(self):
        self.destroyed = True


class FakeBusyInfo:
    events = None

    def __init__(self, message, parent):
        if FakeBusyInfo.events is not None:
            FakeBusyInfo.events.append(("busy_create", message))

    def __del__(self):
        if FakeBusyInfo.events is not None:
            FakeBusyInfo.events.append(("busy_del",))


def _fake_wx(events):
    FakeMessageDialog.instances = []
    FakeMessageDialog.events = events
    FakeBusyInfo.events = events
    return types.SimpleNamespace(
        MessageDialog=FakeMessageDialog,
        BusyInfo=FakeBusyInfo,
        PlatformInfo=("phoenix",),
        YES_NO=1,
        YES_DEFAULT=2,
        CANCEL=4,
        ICON_QUESTION=8,
        OK=16,
        ICON_EXCLAMATION=32,
        ICON_INFORMATION=64,
        ID_YES=5103,
        ID_OK=5100,
        Yield=lambda: None,
    )


def _underscore(texte):
    return texte


def _fake_self(liste_individus=(101, 102)):
    fake_self = mock.MagicMock()
    fake_self.IDclasse = 42
    fake_self.IDecole = 7
    fake_self.ctrl_date_debut.GetDate.return_value = datetime.date(2026, 9, 1)
    fake_self.ctrl_date_fin.GetDate.return_value = datetime.date(2027, 7, 1)
    fake_self.ctrl_niveau.GetNiveau.return_value = 3
    fake_self.ctrl_niveau.GetStringSelection.return_value = "CP"
    fake_self.ctrl_individus.GetCoches.return_value = list(liste_individus)
    fake_self.parent.GetScolariteIndividu.return_value = []
    return fake_self


class OnBoutonOkEntityLookupGuardTests(unittest.TestCase):
    def _load(self, db_factory, events, historique=None):
        fake_wx = _fake_wx(events)
        historique = historique or mock.MagicMock()
        method = _extract_method({
            "GestionDB": types.SimpleNamespace(DB=db_factory),
            "wx": fake_wx,
            "_": _underscore,
            "DateEngFr": lambda valeur: str(valeur),
            "UTILS_Historique": historique,
        })
        return method, fake_wx, historique

    def test_missing_classe_stops_cleanly_before_any_write_and_releases_busyinfo_first(self):
        events = []
        lookup_db = FakeDB(resultat=[])
        db_factory = DBFactory([lookup_db])
        method, _fake_wx_obj, historique = self._load(db_factory, events)
        fake_self = _fake_self()

        method(fake_self, event=None)

        self.assertEqual(db_factory.calls, 1)
        self.assertTrue(lookup_db.close_appele)
        self.assertEqual(lookup_db.inserts, [])
        historique.InsertActions.assert_not_called()
        fake_self.parent.GetScolariteIndividu.assert_not_called()
        fake_self.EndModal.assert_not_called()

        erreurs = [
            dlg for dlg in FakeMessageDialog.instances
            if dlg.titre == "Erreur de saisie"
        ]
        self.assertEqual(len(erreurs), 1)
        self.assertEqual(
            erreurs[0].message,
            "Cette classe n'existe plus en base de données !",
        )
        self.assertTrue(erreurs[0].destroyed)

        busy_del_index = next(
            i for i, event in enumerate(events) if event[0] == "busy_del"
        )
        error_dialog_index = next(
            i for i, event in enumerate(events)
            if event[0] == "dialog_create" and event[1] == "Erreur de saisie"
        )
        self.assertLess(busy_del_index, error_dialog_index)

    def test_existing_classe_keeps_historical_write_path(self):
        events = []
        lookup_db = FakeDB(
            resultat=[("Ecole A", "CP", "2026-09-01", "2027-07-01")]
        )
        write_db = FakeDB()
        db_factory = DBFactory([lookup_db, write_db])
        historique = mock.MagicMock()
        method, fake_wx, historique = self._load(
            db_factory, events, historique=historique
        )
        fake_self = _fake_self(liste_individus=(101, 102))

        method(fake_self, event=None)

        self.assertEqual(db_factory.calls, 2)
        self.assertTrue(lookup_db.close_appele)
        self.assertTrue(write_db.close_appele)
        self.assertEqual(len(write_db.inserts), 2)
        self.assertTrue(
            all(table == "scolarite" for table, _ in write_db.inserts)
        )
        self.assertEqual(historique.InsertActions.call_count, 2)
        self.assertEqual(
            [dlg.titre for dlg in FakeMessageDialog.instances],
            ["Confirmation", "Information"],
        )
        fake_self.EndModal.assert_called_once_with(fake_wx.ID_OK)


if __name__ == "__main__":
    unittest.main()
