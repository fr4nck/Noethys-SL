#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Non-régression pour la garde ResultatReq() vide ajoutée dans trois
``Importation()`` de type "entité principale, dialogue déjà construit" :

- Dlg/DLG_Saisie_classe.py
- Dlg/DLG_Saisie_location_demande.py
- Dlg/DLG_Saisie_typesPieces.py

Chaque ``Importation()`` est extraite par AST (comme test_dates_forfait_color_
contract.py) et exécutée isolément avec un faux GestionDB.DB() et un ``self``
minimal (MagicMock), sans instancier de wx.Dialog réel ni charger wx. Ces
tests démontrent uniquement le comportement de Importation() (pas de crash,
DB fermée, valeurs affectées) — pas le rendu final du dialogue, qui reste du
ressort d'une recette manuelle.
"""

import ast
import datetime
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "noethys"


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


def _extract_method(source_path: Path, class_name: str, method_name: str, extra_namespace: dict):
    """Extrait UNE méthode d'une classe par AST et la compile isolément,
    sans exécuter le reste du fichier (donc sans avoir besoin de wx réel)."""
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
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
    exec(compile(module, str(source_path), "exec"), namespace)
    return namespace[method_name]


class SaisieClasseImportationGuardTests(unittest.TestCase):
    SOURCE_PATH = SOURCE_ROOT / "Dlg" / "DLG_Saisie_classe.py"

    def _load(self, resultat_classe, resultat_scolarite=()):
        fake_db = FakeDB([resultat_classe, resultat_scolarite])
        fake_gestiondb = types.SimpleNamespace(DB=lambda: fake_db)
        importation = _extract_method(
            self.SOURCE_PATH, "Dialog", "Importation", {"GestionDB": fake_gestiondb}
        )
        return importation, fake_db

    def test_empty_result_does_not_raise_and_closes_db(self):
        importation, fake_db = self._load(resultat_classe=[])
        fake_self = mock.MagicMock()
        fake_self.niveaux_bloques = {}

        importation(fake_self)  # ne doit lever aucune IndexError

        self.assertTrue(fake_db.close_appele)
        self.assertEqual(len(fake_db.requetes), 1, "la 2e requête (scolarite) est inutile sans classe")
        fake_self.ctrl_nom.SetValue.assert_not_called()
        self.assertEqual(fake_self.niveaux_bloques, {}, "reste à la valeur posée par __init__")

    def test_normal_result_still_populates_fields(self):
        importation, fake_db = self._load(
            resultat_classe=[("CP", "2024-09-01", "2025-07-01", "1;2")],
            resultat_scolarite=[],
        )
        fake_self = mock.MagicMock()
        fake_self.niveaux_bloques = {}

        importation(fake_self)

        fake_self.ctrl_nom.SetValue.assert_called_once_with("CP")
        fake_self.ctrl_date_debut.SetDate.assert_called_once_with("2024-09-01")
        fake_self.ctrl_date_fin.SetDate.assert_called_once_with("2025-07-01")
        fake_self.ctrl_niveaux.SetIDcoches.assert_called_once_with(["1", "2"])
        self.assertTrue(fake_db.close_appele)
        self.assertEqual(len(fake_db.requetes), 2)


class SaisieLocationDemandeImportationGuardTests(unittest.TestCase):
    SOURCE_PATH = SOURCE_ROOT / "Dlg" / "DLG_Saisie_location_demande.py"

    def _namespace(self):
        return {
            "datetime": datetime,
            "copy": __import__("copy"),
            "UTILS_Dates": types.SimpleNamespace(
                DateEngEnDateDDT=lambda date: datetime.datetime(2024, 1, 1)
            ),
            "UTILS_Texte": types.SimpleNamespace(
                ConvertStrToListe=lambda texte: [texte] if texte else []
            ),
        }

    def _load(self, resultat_demande, resultat_filtres=()):
        fake_db = FakeDB([resultat_demande, resultat_filtres])
        fake_gestiondb = types.SimpleNamespace(DB=lambda: fake_db)
        namespace = self._namespace()
        namespace["GestionDB"] = fake_gestiondb
        importation = _extract_method(self.SOURCE_PATH, "Dialog", "Importation", namespace)
        return importation, fake_db

    def test_empty_result_does_not_raise_and_closes_db(self):
        importation, fake_db = self._load(resultat_demande=[])
        fake_self = mock.MagicMock()
        fake_self.IDdemande = 999
        fake_self.listeInitialeFiltres = []

        importation(fake_self)

        self.assertTrue(fake_db.close_appele)
        self.assertEqual(len(fake_db.requetes), 1, "la requête des filtres est inutile sans demande")
        fake_self.ctrl_observations.SetValue.assert_not_called()
        self.assertEqual(fake_self.listeInitialeFiltres, [], "reste à la valeur posée par __init__")

    def test_normal_result_still_populates_fields(self):
        importation, fake_db = self._load(
            resultat_demande=[("2024-01-01", 42, "Note test", "1;2", "3;4", "attente", None, None)],
            resultat_filtres=[],
        )
        fake_self = mock.MagicMock()
        fake_self.IDdemande = 999

        importation(fake_self)

        fake_self.ctrl_loueur.SetIDfamille.assert_called_once_with(42)
        fake_self.ctrl_observations.SetValue.assert_called_once_with("Note test")
        fake_self.ctrl_statut.SetPageByCode.assert_called_once_with("attente")
        self.assertEqual(fake_self.listeInitialeFiltres, [])
        self.assertTrue(fake_db.close_appele)
        self.assertEqual(len(fake_db.requetes), 2)


class SaisieTypesPiecesImportationGuardTests(unittest.TestCase):
    SOURCE_PATH = SOURCE_ROOT / "Dlg" / "DLG_Saisie_typesPieces.py"

    def _load(self, resultat):
        fake_db = FakeDB([resultat])
        fake_gestiondb = types.SimpleNamespace(DB=lambda: fake_db)
        importation = _extract_method(
            self.SOURCE_PATH, "Dialog", "Importation", {"GestionDB": fake_gestiondb}
        )
        return importation, fake_db

    def test_empty_result_does_not_raise_and_db_was_already_closed(self):
        importation, fake_db = self._load(resultat=[])
        fake_self = mock.MagicMock()

        importation(fake_self)

        self.assertTrue(fake_db.close_appele)
        fake_self.ctrl_nom.SetValue.assert_not_called()
        fake_self.SetPublic.assert_not_called()

    def test_normal_result_still_populates_fields(self):
        importation, fake_db = self._load(resultat=[("Fiche sanitaire", "individu", None, True)])
        fake_self = mock.MagicMock()

        importation(fake_self)

        fake_self.ctrl_nom.SetValue.assert_called_once_with("Fiche sanitaire")
        fake_self.SetPublic.assert_called_once_with("individu")
        fake_self.SetValidite.assert_called_once_with(None)
        fake_self.SetRattachement.assert_called_once_with(True)
        self.assertTrue(fake_db.close_appele)


if __name__ == "__main__":
    unittest.main()
