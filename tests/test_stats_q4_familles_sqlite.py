# -*- coding: utf-8 -*-
"""Q4-A : deux vrais objets Familles executes sur SQLite synthetique.

Leurs MAJ() viennent de UTILS_Stats_familles, sans wx, MySQL ou base PMSL.
Une requete SQL DISTINCT independante fournit la valeur de reference.
"""
import ast
import datetime
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest


SOURCE = (Path(__file__).resolve().parents[1] / "noethys" / "Utils" /
          "UTILS_Stats_familles.py")


class ObjetBase:
    def __init__(self):
        self.dictParametres = {}


class DBSQLite:
    def __init__(self):
        self.connexion = sqlite3.connect(":memory:")
        self.cursor = self.connexion.cursor()
        self.requetes = []
        self.cursor.executescript("""
            CREATE TABLE comptes_payeurs(
                IDcompte_payeur INTEGER PRIMARY KEY, IDfamille INTEGER);
            CREATE TABLE consommations(
                IDcompte_payeur INTEGER, date TEXT, etat TEXT, IDactivite INTEGER);
            CREATE TABLE inscriptions(
                IDcompte_payeur INTEGER, statut TEXT, IDactivite INTEGER);
        """)
        self.cursor.executemany("INSERT INTO comptes_payeurs VALUES (?,?)", [
            (11, 1), (12, 1), (21, 2), (31, 3), (41, 4)])
        self.cursor.executemany(
            "INSERT INTO consommations VALUES (?,?,?,?)", [
                (11, "2026-04-01", "present", 1),
                (11, "2026-04-02", "present", 1),
                (12, "2026-04-03", "reservation", 1),
                (21, "2026-04-01", "present", 1),
                (21, "2026-04-02", "present", 2),
                (31, "2026-04-03", "reservation", 2),
                (41, "2026-04-01", "absent", 1),
                (41, "2025-04-01", "present", 1),
                (41, "2026-04-01", "present", 3),
            ])
        self.cursor.executemany(
            "INSERT INTO inscriptions VALUES (?,?,?)", [
                (11, "ok", 1), (12, "ok", 1),
                (21, "ok", 1), (21, "ok", 2),
                (31, "ok", 2), (41, "annule", 1),
                (41, "ok", 3),
            ])

    def ExecuterReq(self, sql):
        self.requetes.append(sql)
        self.cursor.execute(sql)

    def ResultatReq(self):
        return self.cursor.fetchall()

    def Close(self):
        self.connexion.close()


def classes_reelles():
    """Compiler les classes sources (constructeur et MAJ), sans dependances GUI."""
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    noms = ("Texte_nombre_familles", "Tableau_nombre_familles")
    definitions = [
        node for node in arbre.body
        if isinstance(node, ast.ClassDef) and node.name in noms
    ]
    if len(definitions) != len(noms):
        raise AssertionError("Objets Q4-A introuvables")
    module = ast.Module(body=definitions, type_ignores=[])
    ast.fix_missing_locations(module)
    modeles = SimpleNamespace(
        Texte=ObjetBase, Tableau=ObjetBase,
        GetDatesPeriode=lambda p: (
            p["periode"]["date_debut"], p["periode"]["date_fin"]),
        GetConditionActivites=lambda p: "(" + ",".join(
            str(x) for x in p["listeActivites"]) + ")",
    )
    env = {"MODELES": modeles, "_": lambda s: s}
    exec(compile(module, str(SOURCE), "exec"), env)
    return env


class Q4FamillesSQLTests(unittest.TestCase):
    def setUp(self):
        self.db = DBSQLite()
        self.objets = classes_reelles()

    def tearDown(self):
        self.db.Close()

    def parametres(self, mode, activites=(1, 2)):
        return {
            "mode": mode, "listeActivites": list(activites),
            "dictActivites": {1: "ALSH A", 2: "ALSH B", 3: "Hors filtre"},
            "periode": {
                "date_debut": datetime.date(2026, 1, 1),
                "date_fin": datetime.date(2026, 12, 31),
            },
        }

    def valeurs_de_reference(self, mode, activites):
        marques = ",".join("?" for _ in activites)
        if mode == "presents":
            source = """consommations c JOIN comptes_payeurs p
                        ON p.IDcompte_payeur = c.IDcompte_payeur"""
            filtre = ("c.etat IN ('reservation','present') "
                      "AND c.date BETWEEN ? AND ? "
                      "AND c.IDactivite IN (" + marques + ")")
            params = ("2026-01-01", "2026-12-31", *activites)
        else:
            source = """inscriptions c JOIN comptes_payeurs p
                        ON p.IDcompte_payeur = c.IDcompte_payeur"""
            filtre = "c.statut='ok' AND c.IDactivite IN (" + marques + ")"
            params = tuple(activites)
        nombre = self.db.connexion.execute(
            "SELECT COUNT(DISTINCT p.IDfamille) FROM " + source +
            " WHERE " + filtre, params).fetchone()[0]
        distribution = dict(self.db.connexion.execute(
            "SELECT c.IDactivite, COUNT(DISTINCT p.IDfamille) FROM " +
            source + " WHERE " + filtre + " GROUP BY c.IDactivite",
            params).fetchall())
        return nombre, distribution

    def verifier(self, mode, activites=(1, 2)):
        p = self.parametres(mode, activites)
        attendu_nombre, attendu_par_activite = self.valeurs_de_reference(
            mode, activites)
        texte = self.objets["Texte_nombre_familles"]()
        tableau = self.objets["Tableau_nombre_familles"]()
        texte.MAJ(DB=self.db, dictParametres=p)
        tableau.MAJ(DB=self.db, dictParametres=p)
        self.assertEqual(len(self.db.requetes), 2)
        self.assertIn(str(attendu_nombre) + " familles", texte.texte)
        obtenu = {
            next(k for k, v in p["dictActivites"].items() if v == nom): nombre
            for nom, nombre in tableau.lignes
        }
        self.assertEqual(obtenu, attendu_par_activite)
        self.assertEqual(sum(obtenu.values()),
                         sum(attendu_par_activite.values()))
        self.assertIn("GROUP BY", self.db.requetes[0])
        self.assertIn("GROUP BY", self.db.requetes[1])

    def test_presents_doublons_et_deux_comptes_payeurs(self):
        self.verifier("presents")

    def test_inscrits_doublons_annulations_et_deux_activites(self):
        self.verifier("inscrits")

    def test_selection_unique_activite(self):
        for mode in ("presents", "inscrits"):
            with self.subTest(mode=mode):
                self.db.requetes.clear()
                self.verifier(mode, (1,))

    def test_aucune_activite_avec_donnees(self):
        for mode in ("presents", "inscrits"):
            with self.subTest(mode=mode):
                self.db.requetes.clear()
                p = self.parametres(mode, (99,))
                nombre, distribution = self.valeurs_de_reference(mode, (99,))
                self.assertEqual((nombre, distribution), (0, {}))
                texte = self.objets["Texte_nombre_familles"]()
                tableau = self.objets["Tableau_nombre_familles"]()
                texte.MAJ(DB=self.db, dictParametres=p)
                tableau.MAJ(DB=self.db, dictParametres=p)
                self.assertIn("Aucune famille", texte.texte)
                self.assertEqual(tableau.lignes, [])


if __name__ == "__main__":
    unittest.main()
