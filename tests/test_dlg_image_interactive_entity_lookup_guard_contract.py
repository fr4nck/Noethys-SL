#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Non-régression pour la garde ResultatReq() vide ajoutée dans
Dlg/DLG_Image_interactive.py : Data.MAJ.

Track et Data sont extraites par AST et exécutées isolément avec de faux
modules GestionDB/Utils.*, sans wx ni interface réelle. Le test du modèle
absent démontre que la ligne "self.categorie, self.IDdonnee =
listeDonnees[0]" ne lève plus d'IndexError, que la requête produits n'est
jamais exécutée, que la DB est fermée, et que l'objet Data reste dans un
état neutre exploitable par GetTrack/GetCouleur/GetTexteInfoBulle. Le
chemin nominal vérifie que le comportement historique (modèle présent) est
inchangé.
"""

import ast
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "noethys" / "Dlg" / "DLG_Image_interactive.py"


def _extract_classes(names):
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SOURCE_PATH))
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name in names
    ]
    assert len(nodes) == len(names), "classe(s) introuvable(s) dans le fichier source"
    # Respecte l'ordre demandé (Track avant Data), pas l'ordre de découverte.
    nodes.sort(key=lambda node: names.index(node.name))
    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {}
    exec(compile(module, str(SOURCE_PATH), "exec"), namespace)
    return namespace


class FakeDB:
    """Double minimal de GestionDB.DB() : une file de résultats préconfigurés,
    un par appel de ResultatReq(), et trace requêtes/fermeture."""

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


class FakeQuestionnaires:
    def GetQuestions(self, type=None):
        return []

    def GetReponses(self, type=None):
        return {}


def _fake_modules(fake_db_factory, dict_titulaires=None, dict_locations=None):
    """Construit les modules Utils.* et GestionDB nécessaires aux imports
    inline de Data.MAJ() ("import GestionDB", "from Utils import ...")."""
    fake_gestiondb = types.ModuleType("GestionDB")
    fake_gestiondb.DB = fake_db_factory

    fake_utils_titulaires = types.ModuleType("Utils.UTILS_Titulaires")
    fake_utils_titulaires.GetTitulaires = lambda: (dict_titulaires if dict_titulaires is not None else {})

    fake_utils_questionnaires = types.ModuleType("Utils.UTILS_Questionnaires")
    fake_utils_questionnaires.Questionnaires = FakeQuestionnaires

    fake_utils_locations = types.ModuleType("Utils.UTILS_Locations")
    fake_utils_locations.GetProduitsLoues = lambda DB=None: (dict_locations if dict_locations is not None else {})

    fake_utils = types.ModuleType("Utils")
    fake_utils.UTILS_Titulaires = fake_utils_titulaires
    fake_utils.UTILS_Questionnaires = fake_utils_questionnaires
    fake_utils.UTILS_Locations = fake_utils_locations

    return {
        "GestionDB": fake_gestiondb,
        "Utils": fake_utils,
        "Utils.UTILS_Titulaires": fake_utils_titulaires,
        "Utils.UTILS_Questionnaires": fake_utils_questionnaires,
        "Utils.UTILS_Locations": fake_utils_locations,
    }


def _load_data_class():
    namespace = _extract_classes(["Track", "Data"])
    return namespace["Data"]


class DataMajModeleAbsentTests(unittest.TestCase):
    def test_modele_absent_no_indexerror_no_produits_query_db_closed(self):
        fake_db = FakeDB(resultats=[[]])  # documents_modeles vide
        modules = _fake_modules(fake_db_factory=lambda: fake_db)
        Data = _load_data_class()

        with mock.patch.dict(sys.modules, modules):
            data = Data(IDmodele=999)

        self.assertIsNone(data.categorie)
        self.assertIsNone(data.IDdonnee)
        self.assertEqual(data.dictTracks, {})
        self.assertTrue(fake_db.close_appele)
        self.assertEqual(
            len(fake_db.requetes), 1,
            "la requête produits ne doit jamais être exécutée avec un IDdonnee invalide",
        )


class DataMajModelePresentTests(unittest.TestCase):
    def test_modele_present_chemin_historique_inchange(self):
        resultats = [
            [(3, 42)],  # documents_modeles : categorie=3, IDdonnee=42
            [(101, "Tapis", "", "Sport", 5)],  # produits de la catégorie 42
        ]
        fake_db = FakeDB(resultats=resultats)
        modules = _fake_modules(fake_db_factory=lambda: fake_db)
        Data = _load_data_class()

        with mock.patch.dict(sys.modules, modules):
            data = Data(IDmodele=5)

        self.assertEqual(data.categorie, 3)
        self.assertEqual(data.IDdonnee, 42)
        self.assertEqual(len(data.dictTracks), 1)
        self.assertIn(101, data.dictTracks)
        self.assertEqual(data.dictTracks[101].nom, "Tapis")
        self.assertTrue(fake_db.close_appele)
        self.assertEqual(len(fake_db.requetes), 2)


class DataMajRepeteeApresModeleAbsentTests(unittest.TestCase):
    def test_maj_repetee_apres_modele_absent_reste_stable_sans_residu(self):
        # Premier MAJ : modèle présent, produit un dictTracks non vide.
        fake_db_1 = FakeDB(resultats=[
            [(3, 42)],
            [(101, "Tapis", "", "Sport", 5)],
        ])
        Data = _load_data_class()

        with mock.patch.dict(sys.modules, _fake_modules(fake_db_factory=lambda: fake_db_1)):
            data = Data(IDmodele=5)
        self.assertEqual(len(data.dictTracks), 1)

        # Second MAJ sur le même objet : le modèle a disparu entre-temps.
        fake_db_2 = FakeDB(resultats=[[]])
        with mock.patch.dict(sys.modules, _fake_modules(fake_db_factory=lambda: fake_db_2)):
            data.MAJ()

        self.assertIsNone(data.categorie)
        self.assertIsNone(data.IDdonnee)
        self.assertEqual(
            data.dictTracks, {},
            "aucun résidu du chargement précédent (Tapis/101) ne doit survivre",
        )
        self.assertTrue(fake_db_2.close_appele)
        self.assertEqual(len(fake_db_2.requetes), 1)


class DataConsommateursNeutresTests(unittest.TestCase):
    def test_consommateurs_neutres_ne_plantent_pas(self):
        fake_db = FakeDB(resultats=[[]])
        modules = _fake_modules(fake_db_factory=lambda: fake_db)
        Data = _load_data_class()

        with mock.patch.dict(sys.modules, modules):
            data = Data(IDmodele=999)

        self.assertIsNone(data.GetTrack(IDproduit=101))
        self.assertIsNone(data.GetCouleur(IDdonnee=101))
        self.assertIsNone(data.GetTexteInfoBulle(IDdonnee=101))
        self.assertEqual(data.GetReponse(IDquestion=1, ID=101), u"")


if __name__ == "__main__":
    unittest.main()
