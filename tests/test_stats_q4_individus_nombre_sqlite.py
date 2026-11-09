# -*- coding: utf-8 -*-
"""Q4-B3 : SQL du nombre d'individus sur SQLite synthetique.

Executer les MAJ() originales (sans interfaces wx) et comparer les nombres
uniques a des requetes DISTINCT independantes. Ni base PMSL ni MySQL.
"""
import ast
import datetime
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Stats_individus.py"


class ObjetBase:
    def __init__(self):
        self.dictParametres = {}


class DBSQLite:
    def __init__(self):
        self.connexion = sqlite3.connect(":memory:")
        self.cursor = self.connexion.cursor()
        self.requetes = []
        self.cursor.executescript("""
            CREATE TABLE consommations(
                IDindividu INTEGER, date TEXT, etat TEXT, IDactivite INTEGER);
            CREATE TABLE inscriptions(
                IDindividu INTEGER, statut TEXT, IDactivite INTEGER);
        """)
        self.cursor.executemany(
            "INSERT INTO consommations VALUES (?,?,?,?)", [
                (101, "2026-03-01", "present", 1),
                (101, "2026-03-02", "reservation", 1),
                (101, "2026-03-03", "present", 2),
                (102, "2026-03-02", "present", 1),
                (103, "2026-03-04", "reservation", 2),
                (104, "2026-03-05", "absent", 1),
                (105, "2025-03-01", "present", 1),
                (106, "2026-03-01", "present", 3),
            ])
        self.cursor.executemany(
            "INSERT INTO inscriptions VALUES (?,?,?)", [
                (101, "ok", 1), (101, "ok", 1),
                (101, "ok", 2), (102, "ok", 1),
                (103, "annule", 2), (104, "ok", 2),
                (107, "ok", 2), (106, "ok", 3),
            ])

    def ExecuterReq(self, sql):
        self.requetes.append(sql)
        self.cursor.execute(sql)

    def ResultatReq(self):
        return self.cursor.fetchall()

    def Close(self):
        self.connexion.close()


def objets_source():
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    noms = ("Texte_nombre_individus", "Tableau_nombre_individus")
    classes = [
        node for node in arbre.body
        if isinstance(node, ast.ClassDef) and node.name in noms
    ]
    if len(classes) != len(noms):
        raise AssertionError("Classes Individus/Nombre non retrouvees")
    modeles = SimpleNamespace(
        Texte=ObjetBase, Tableau=ObjetBase,
        GetDatesPeriode=lambda p: (
            p["periode"]["date_debut"], p["periode"]["date_fin"]),
        GetConditionActivites=lambda p: "(" + ",".join(
            str(x) for x in p["listeActivites"]) + ")",
    )
    ns = {"MODELES": modeles, "_": lambda txt: txt}
    module = ast.Module(body=classes, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(SOURCE), "exec"), ns)
    return ns


def parametres(mode, activites=(1, 2)):
    return {
        "mode": mode, "listeActivites": list(activites),
        "dictActivites": {1: "ALSH A", 2: "ALSH B", 3: "Hors selection"},
        "periode": {
            "date_debut": datetime.date(2026, 1, 1),
            "date_fin": datetime.date(2026, 12, 31),
        },
    }


def oracle(db, p):
    activites = p["listeActivites"]
    marques = ",".join("?" for _ in activites)
    if p["mode"] == "presents":
        source = "consommations"
        where = ("etat IN ('reservation','present') "
                 "AND date BETWEEN ? AND ? "
                 "AND IDactivite IN (" + marques + ")")
        args = (str(p["periode"]["date_debut"]),
                str(p["periode"]["date_fin"]), *activites)
    else:
        source = "inscriptions"
        where = "statut='ok' AND IDactivite IN (" + marques + ")"
        args = tuple(activites)
    nombre = db.connexion.execute(
        "SELECT COUNT(DISTINCT IDindividu) FROM " + source +
        " WHERE " + where, args).fetchone()[0]
    repartition = dict(db.connexion.execute(
        "SELECT IDactivite, COUNT(DISTINCT IDindividu) FROM " +
        source + " WHERE " + where + " GROUP BY IDactivite",
        args).fetchall())
    return nombre, repartition


class Q4IndividusNombreSQLTests(unittest.TestCase):
    def setUp(self):
        self.db = DBSQLite()
        self.objets = objets_source()

    def tearDown(self):
        self.db.Close()

    def verifier(self, p):
        nombre, attendu = oracle(self.db, p)
        texte = self.objets["Texte_nombre_individus"]()
        tableau = self.objets["Tableau_nombre_individus"]()
        debut = len(self.db.requetes)
        texte.MAJ(DB=self.db, dictParametres=p)
        tableau.MAJ(DB=self.db, dictParametres=p)
        self.assertEqual(len(self.db.requetes) - debut, 2)
        if nombre:
            self.assertIn("%s individus" % nombre, texte.texte)
        else:
            self.assertIn("Aucun individu", texte.texte)
        obtenu = {
            nom: n for nom, n in tableau.lignes
        }
        reference = {
            p["dictActivites"][activite]: n
            for activite, n in attendu.items()
        }
        self.assertEqual(obtenu, reference)
        self.assertEqual(sum(obtenu.values()), sum(attendu.values()))

    def test_presents_multi_activites_et_doublons(self):
        self.verifier(parametres("presents"))

    def test_inscrits_en_excluant_les_annulations(self):
        self.verifier(parametres("inscrits"))

    def test_filtre_une_activite_pour_chaque_mode(self):
        for mode in ("presents", "inscrits"):
            with self.subTest(mode=mode):
                self.verifier(parametres(mode, (1,)))

    def test_selection_sans_donnees(self):
        for mode in ("presents", "inscrits"):
            with self.subTest(mode=mode):
                self.verifier(parametres(mode, (99,)))

    def test_periode_hors_plage_en_mode_presents(self):
        p = parametres("presents")
        p["periode"]["date_debut"] = datetime.date(2027, 1, 1)
        p["periode"]["date_fin"] = datetime.date(2027, 12, 31)
        self.verifier(p)


if __name__ == "__main__":
    unittest.main()
