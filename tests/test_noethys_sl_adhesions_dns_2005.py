# -*- coding: utf-8 -*-
"""Regression autonome : l'erreur MySQL 2005 ne doit jamais produire un faux zero."""
import ast
from pathlib import Path
import re
import types
import unittest
from unittest.mock import patch


SOURCE = (Path(__file__).resolve().parents[1] / "noethys" / "Utils" /
          "UTILS_Adhesions.py")


def charger_lecture_isolee():
    """Teste les vraies fonctions sans charger wx ni ouvrir une base reelle."""
    racine = ast.parse(SOURCE.read_text(encoding="utf-8"))
    noms = {"_code_erreur_sql", "_lire_sur_connexion", "_lire"}
    noeuds = [
        noeud for noeud in racine.body
        if (isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef))
            and noeud.name in noms)
        or (isinstance(noeud, ast.Assign)
            and any(isinstance(cible, ast.Name)
                    and cible.id == "_CODES_SQL_RECONNEXION"
                    for cible in noeud.targets))
    ]
    contexte = {"re": re}
    exec(compile(ast.fix_missing_locations(ast.Module(body=noeuds, type_ignores=[])),
                 str(SOURCE), "exec"), contexte)
    return contexte


class BaseFactice:
    def __init__(self, erreur=None, reseau=True, resultat=None):
        self.isNetwork = reseau
        self.erreur = erreur
        self.echec = int(erreur is not None)
        self.derniere_erreur_sql = None
        self.resultat = [(1,)] if resultat is None else resultat
        self.fermetures = 0
        self.lectures = 0

    def ExecuterReq(self, req):
        self.lectures += 1
        return 1

    def ResultatReq(self):
        return self.resultat

    def Close(self):
        self.fermetures += 1


class MySQLDNS2005Tests(unittest.TestCase):
    REQUETE = "SELECT IDtype_cotisation FROM types_cotisations;"

    def setUp(self):
        self.code = charger_lecture_isolee()

    def lire(self, bases, requete=None):
        ouvrir = unittest.mock.Mock(side_effect=bases)
        self.code["GestionDB"] = types.SimpleNamespace(DB=ouvrir)
        if requete is None:
            requete = self.REQUETE
        return ouvrir, lambda: self.code["_lire"](requete)

    def test_2005_resolu_au_second_essai(self):
        premiere = BaseFactice(erreur=RuntimeError(2005, "Unknown server host (11001)"))
        deuxieme = BaseFactice()
        ouvrir, lire = self.lire([premiere, deuxieme])
        self.assertEqual(lire(), [(1,)])
        self.assertEqual(ouvrir.call_count, 2)
        self.assertEqual(ouvrir.call_args_list[1].kwargs, {"pooling": False})
        self.assertEqual((premiere.fermetures, deuxieme.fermetures), (1, 1))

    def test_2005_persistant_est_une_erreur_pas_une_absence_d_adhesion(self):
        premiere = BaseFactice(erreur=RuntimeError(2005, "Unknown server host (11001)"))
        deuxieme = BaseFactice(erreur=RuntimeError(2005, "Unknown server host (11001)"))
        ouvrir, lire = self.lire([premiere, deuxieme])
        with self.assertRaisesRegex(RuntimeError, "Connexion .* impossible"):
            lire()
        self.assertEqual(ouvrir.call_count, 2)
        self.assertEqual((premiere.fermetures, deuxieme.fermetures), (1, 1))

    def test_erreur_authentification_ne_reconnecte_pas(self):
        premiere = BaseFactice(erreur=RuntimeError(1045, "Access denied"))
        ouvrir, lire = self.lire([premiere])
        with self.assertRaisesRegex(RuntimeError, "Connexion .* impossible"):
            lire()
        self.assertEqual(ouvrir.call_count, 1)
        self.assertEqual(premiere.fermetures, 1)

    def test_aucun_retry_sur_ecriture(self):
        premiere = BaseFactice(erreur=RuntimeError(2005, "Unknown server host"))
        ouvrir, lire = self.lire([premiere], "UPDATE cotisations SET observations='x';")
        with self.assertRaises(RuntimeError):
            lire()
        self.assertEqual(ouvrir.call_count, 1)

    def test_aucun_retry_sur_base_locale(self):
        premiere = BaseFactice(erreur=RuntimeError(2005, "erreur locale"), reseau=False)
        ouvrir, lire = self.lire([premiere])
        with self.assertRaises(RuntimeError):
            lire()
        self.assertEqual(ouvrir.call_count, 1)


if __name__ == "__main__":
    unittest.main()
