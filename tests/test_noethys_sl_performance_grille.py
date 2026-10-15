# -*- coding: utf-8 -*-
"""Issue #427 : eviter des acces SQL inutiles lors d'un clic OK sur la grille.

Sans base exploitee : les tests de transport invoquent la methode reelle
avec GestionDB.DB remplace par un mock. Le contrat du prochain identifiant
de prestation est controle via l'AST (conserve la voie d'ajout historique).
"""
from __future__ import annotations

import ast
import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
for rep in (ROOT / "tests", ROOT / "noethys"):
    if str(rep) not in sys.path:
        sys.path.insert(0, str(rep))

import _garde_reseau  # noqa: E402,F401 (aucun reseau reel)
import wx  # noqa: E402

_APP = wx.App(False)
from Ctrl import CTRL_Grille  # noqa: E402


class SauvegardeTransportsSansAccesTests(unittest.TestCase):
    def save(self, dictTransports, initiaux):
        grille = SimpleNamespace(dict_transports=dictTransports,
                                 listeTransportsInitiale=initiaux)
        with patch.object(CTRL_Grille.GestionDB, "DB") as fabrique:
            CTRL_Grille.CTRL.SauvegardeTransports(grille)
            return fabrique

    def test_aucun_transport_ne_cree_une_connexion(self):
        self.save({}, []).assert_not_called()

    def test_transports_inchanges_ne_creent_pas_de_connexion(self):
        self.save({3: {41: {"etat": "ORIG"}}}, [41]).assert_not_called()

    def test_deux_familles_transports_inchanges_pas_de_connexion(self):
        self.save({3: {41: {"etat": "ORIG"}}, 5: {42: {"etat": "ORIG"}}}, [41, 42]).assert_not_called()

    def test_suppression_ouvre_et_execute_delete(self):
        fabrique = self.save({3: {}}, [41])
        fabrique.assert_called_once_with()
        db = fabrique.return_value
        db.ReqDEL.assert_called_once_with("transports", "IDtransport", 41)
        db.Close.assert_called_once_with()

    @staticmethod
    def transport(etat):
        champs = (
            "IDindividu", "mode", "categorie", "IDcompagnie", "IDligne",
            "numero", "details", "observations", "depart_date", "depart_heure",
            "depart_IDarret", "depart_IDlieu", "depart_localisation",
            "arrivee_date", "arrivee_heure", "arrivee_IDarret",
            "arrivee_IDlieu", "arrivee_localisation", "prog",
        )
        d = {champ: None for champ in champs}
        d["IDindividu"] = 3
        d["etat"] = etat
        return d

    def test_modification_conserve_update(self):
        fabrique = self.save({3: {41: self.transport("MODIF")}}, [41])
        fabrique.assert_called_once_with()
        db = fabrique.return_value
        self.assertEqual(db.ReqMAJ.call_count, 1)
        args = db.ReqMAJ.call_args.args
        self.assertEqual((args[0], args[2], args[3]),
                         ("transports", "IDtransport", 41))
        db.Close.assert_called_once_with()

    def test_nouveau_transport_conserve_insert(self):
        fabrique = self.save({3: {-1: self.transport("AJOUT")}}, [])
        fabrique.assert_called_once_with()
        db = fabrique.return_value
        self.assertEqual(db.ReqInsert.call_count, 1)
        self.assertEqual(db.ReqInsert.call_args.args[0], "transports")
        db.Close.assert_called_once_with()


class ReservationSansPrestationTests(unittest.TestCase):
    def test_getprochainid_est_reserve_aux_ajouts(self):
        source = (ROOT / "noethys" / "Ctrl" / "CTRL_Grille.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        cls = next(c for c in tree.body if isinstance(c, ast.ClassDef) and c.name == "CTRL")
        save = next(m for m in cls.body if isinstance(m, ast.FunctionDef) and m.name == "Sauvegarde")
        calls = [n for n in ast.walk(save) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and n.func.attr == "GetProchainID"]
        self.assertEqual(len(calls), 1, "La verification SHOW TABLE STATUS doit rester unique")
        guard = [n for n in ast.walk(save) if isinstance(n, ast.If)
                 and ast.unparse(n.test) == "IDprestation < 0"]
        self.assertEqual(len(guard), 1)
        self.assertIn(calls[0], list(ast.walk(guard[0])),
                      "L'appel doit rester sous la condition d'ajout, sans SQL sur modification simple")


if __name__ == "__main__":
    unittest.main()
