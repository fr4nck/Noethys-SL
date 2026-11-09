# -*- coding: utf-8 -*-
"""STATS-RESTORE : regressions des classes d'ages sans wx ni donnees reelles."""
import ast
import datetime
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Stats_individus.py"


def extraire(nom, classe=None, espace=None):
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    definitions = arbre.body
    if classe is not None:
        definitions = next(x.body for x in arbre.body
                           if isinstance(x, ast.ClassDef) and x.name == classe)
    fonction = next(x for x in definitions
                    if isinstance(x, ast.FunctionDef) and x.name == nom)
    module = ast.Module(body=[fonction], type_ignores=[])
    ast.fix_missing_locations(module)
    environnement = dict(espace or {})
    exec(compile(module, str(SOURCE), "exec"), environnement)
    return environnement[nom]


class TranchesAgesTests(unittest.TestCase):
    def setUp(self):
        self.cle = extraire("_CleTriStatistiques")

    def test_classement_decennal_zero_dix_huit_inconnu(self):
        date_reference = datetime.date(2026, 12, 31)
        lignes = [
            (1, 1, "2026-03-10"),
            (2, 1, "2018-04-20"),
            (3, 2, "2016-09-10"),
            (4, 2, "2008-08-20"),
            (5, 3, None),
        ]
        civ = SimpleNamespace(GetDictCivilites=lambda: {
            1: {"sexe": "M"}, 2: {"sexe": "F"}, 3: {"sexe": None}})
        module_data = ModuleType("Data")
        module_data.DATA_Civilites = civ
        modeles = SimpleNamespace(
            GetDatesPeriode=lambda p: (datetime.date(2026, 1, 1), date_reference),
            GetConditionActivites=lambda p: "(7)",
        )
        db = SimpleNamespace(
            ExecuterReq=mock.Mock(),
            ResultatReq=lambda: list(lignes))
        espace = {
            "MODELES": modeles, "datetime": datetime,
            "DICT_AGES": {"dictParametres": {}, "dictAges": {}, "dictAnnees": {}},
        }
        lire_ages = extraire("GetDictAges", espace=espace)
        p = {"mode": "presents", "listeActivites": [7], "periode": {
            "date_debut": datetime.date(2026, 1, 1),
            "date_fin": date_reference}}
        with mock.patch.dict(sys.modules, {"Data": module_data}):
            genres, annees = lire_ages(db, p, mode_tranches=True)
        self.assertEqual(genres, {0: {"M": 2}, 1: {"F": 2},
                                  None: {"None": 1}})
        self.assertEqual(annees[2026], 1)
        self.assertEqual(annees[2018], 1)
        self.assertEqual(annees[2016], 1)
        self.assertEqual(annees[2008], 1)
        self.assertEqual(annees[None], 1)
        db.ExecuterReq.assert_called_once()

    def test_tableau_decennal_et_age_inconnu(self):
        donnees = {0: {"M": 2}, 1: {"F": 2}, None: {"None": 1}}
        maj = extraire("MAJ", classe="Tableau_repartition_tranches_ages",
                      espace={"GetDictAges": lambda *a, **k: (donnees, {}),
                              "_": lambda t: t,
                              "_CleTriStatistiques": self.cle})
        objet = SimpleNamespace()
        maj(objet, DB=object(), dictParametres={"listeActivites": [7]})
        self.assertEqual(objet.lignes, [
            ("0 - 9", 2, 0, 0, 2),
            ("10 - 19", 0, 2, 0, 2),
            ("Age inconnu", 0, 0, 1, 1),
        ])

    def test_tableaux_ages_et_annees_trient_les_valeurs_absentes(self):
        cas = [
            ("Tableau_repartition_ages",
             {0: 2, 18: 3, None: 1}, {2026: 2, 2008: 3, None: 1},
             ["0", "18", "Date de naissance inconnue"]),
            ("Tableau_repartition_annees_naiss",
             {0: 2, 18: 3, None: 1}, {2026: 2, 2008: 3, None: 1},
             ["2008", "2026", "Année de naissance inconnue"]),
        ]
        for classe, ages, annees, labels in cas:
            with self.subTest(classe=classe):
                maj = extraire("MAJ", classe=classe, espace={
                    "GetDictAges": lambda *a, **k: (ages, annees),
                    "_": lambda t: t, "_CleTriStatistiques": self.cle})
                objet = SimpleNamespace()
                maj(objet, DB=object(), dictParametres={})
                self.assertEqual([ligne[0] for ligne in objet.lignes], labels)


if __name__ == "__main__":
    unittest.main()
