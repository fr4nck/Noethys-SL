#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Non-régression du flux d'importation des contrats PSU."""

import ast
import datetime
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "noethys" / "Dlg" / "DLG_Saisie_contratpsu.py"


class FakeDB:
    def __init__(self, resultats):
        self._resultats = list(resultats)
        self.requetes = []
        self.close_calls = 0

    def ExecuterReq(self, req):
        self.requetes.append(req)

    def ResultatReq(self):
        return self._resultats.pop(0)

    def Close(self):
        self.close_calls += 1


class FakeSelf:
    def __init__(self, IDcontrat=None, IDinscription=None):
        self.IDcontrat = IDcontrat
        self.IDinscription = IDinscription
        self.dictContrat = {}

    def SetValeurs(self, valeurs):
        self.dictContrat.update(valeurs)

    def GetValeur(self, key=None, defaut=None):
        return self.dictContrat.get(key, defaut)


class FakeDates:
    @staticmethod
    def DateEngEnDateDD(value):
        return value

    @staticmethod
    def HeureStrEnDelta(value):
        return datetime.timedelta(0)

    @staticmethod
    def HeureStrEnTime(value):
        return value


def _extract_importation(gestion_db):
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SOURCE_PATH))
    class_node = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Base"
    )
    method_node = next(
        node for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == "Importation"
    )
    module = ast.Module(body=[method_node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "GestionDB": gestion_db,
        "UTILS_Dates": FakeDates,
        "UTILS_Texte": types.SimpleNamespace(ConvertStrToListe=lambda value: []),
        "datetime": datetime,
        "Track_conso": mock.MagicMock(),
        "Track_tarif": mock.MagicMock(),
        "FloatToDecimal": lambda value: value,
    }
    exec(compile(module, str(SOURCE_PATH), "exec"), namespace)
    return namespace["Importation"]


def _contract_row(IDinscription=42):
    return (
        1, IDinscription, "2026-09-01", "2027-07-01", "",
        5, "psu", "00:00", "00:00", "duree", 30, "00:00",
        None, "DUPONT", "Jean",
    )


def _inscription_row():
    return (1, 7, 5, 2, 3, 9, "2026-09-01", 0)


class ImportationEntityLookupGuardTests(unittest.TestCase):
    def _owned(self, resultats):
        db = FakeDB(resultats)
        factory = mock.MagicMock(return_value=db)
        method = _extract_importation(types.SimpleNamespace(DB=factory))
        return method, db, factory

    def test_missing_contract_raises_and_closes_owned_db(self):
        method, db, _factory = self._owned([[]])
        fake_self = FakeSelf(IDcontrat=99)

        with self.assertRaisesRegex(ValueError, r"Contrat PSU introuvable : 99"):
            method(fake_self)

        self.assertEqual(db.close_calls, 1)
        self.assertEqual(len(db.requetes), 1)
        self.assertEqual(fake_self.dictContrat, {})

    def test_existing_contract_without_inscription_is_rejected(self):
        method, db, _factory = self._owned([[_contract_row(IDinscription=None)]])
        fake_self = FakeSelf(IDcontrat=8)

        with self.assertRaisesRegex(ValueError, r"Inscription requise pour un contrat PSU"):
            method(fake_self)

        self.assertEqual(db.close_calls, 1)
        self.assertEqual(len(db.requetes), 1)
        self.assertEqual(fake_self.dictContrat, {})

    def test_missing_inscription_raises_before_activity_lookup(self):
        method, db, _factory = self._owned([[]])
        fake_self = FakeSelf(IDinscription=42)

        with self.assertRaisesRegex(ValueError, r"Inscription introuvable : 42"):
            method(fake_self)

        self.assertEqual(db.close_calls, 1)
        self.assertEqual(len(db.requetes), 1)
        self.assertEqual(fake_self.dictContrat, {})

    def test_missing_activity_raises_after_inscription_and_closes_owned_db(self):
        method, db, _factory = self._owned([
            [_inscription_row()],
            [],
            [],
        ])
        fake_self = FakeSelf(IDinscription=42)

        with self.assertRaisesRegex(ValueError, r"Activité introuvable : 5"):
            method(fake_self)

        self.assertEqual(db.close_calls, 1)
        self.assertEqual(len(db.requetes), 3)
        self.assertEqual(fake_self.dictContrat, {})

    def test_missing_activity_does_not_close_external_dbtemp(self):
        external_db = FakeDB([
            [_inscription_row()],
            [],
            [],
        ])
        factory = mock.MagicMock(side_effect=AssertionError("DB locale interdite"))
        method = _extract_importation(types.SimpleNamespace(DB=factory))
        fake_self = FakeSelf(IDinscription=42)

        with self.assertRaisesRegex(ValueError, r"Activité introuvable : 5"):
            method(fake_self, DBtemp=external_db)

        factory.assert_not_called()
        self.assertEqual(external_db.close_calls, 0)
        self.assertEqual(fake_self.dictContrat, {})

    def test_valid_new_contract_keeps_historical_import_path(self):
        method, db, _factory = self._owned([
            [_inscription_row()],
            [],
            [(10, 11, 12, "RTT")],
        ])
        fake_self = FakeSelf(IDinscription=42)

        result = method(fake_self)

        self.assertIsNone(result)
        self.assertEqual(db.close_calls, 1)
        self.assertEqual(len(db.requetes), 3)
        self.assertEqual(fake_self.dictContrat["IDinscription"], 42)
        self.assertEqual(fake_self.dictContrat["IDactivite"], 5)
        self.assertEqual(fake_self.dictContrat["IDunite_prevision"], 10)
        self.assertEqual(fake_self.dictContrat["IDunite_presence"], 11)
        self.assertEqual(fake_self.dictContrat["IDtarif"], 12)
        self.assertEqual(fake_self.dictContrat["psu_etiquette_rtt"], "RTT")

    def test_valid_existing_contract_imports_full_read_only_sequence(self):
        method, db, _factory = self._owned([
            [_contract_row()],
            [_inscription_row()],
            [],
            [(10, 11, 12, "RTT")],
            [],
            [],
            [],
        ])
        fake_self = FakeSelf(IDcontrat=8)

        result = method(fake_self)

        self.assertIsNone(result)
        self.assertEqual(db.close_calls, 1)
        self.assertEqual(len(db.requetes), 7)
        self.assertEqual(fake_self.IDinscription, 42)
        self.assertEqual(fake_self.dictContrat["IDactivite"], 5)
        self.assertEqual(fake_self.dictContrat["tracks_previsions"], [])
        self.assertEqual(fake_self.dictContrat["tracks_tarifs"], [])
        self.assertEqual(fake_self.dictContrat["liste_prestations"], [])


if __name__ == "__main__":
    unittest.main()
