# -*- coding: utf-8 -*-
"""STATS Q4-B1 : SQL et tableaux Caisses/Composition sur SQLite fictif.

Les classes et les deux fonctions de calcul sont compilees directement depuis
UTILS_Stats_familles.py. Les totaux attendus sont obtenus par des requetes
COUNT(DISTINCT ...) independantes. Ce test n'est pas une recette GUI.
"""
import ast
import collections
import datetime
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "noethys" / "Utils" / "UTILS_Stats_familles.py"
MODELES_SOURCE = ROOT / "noethys" / "Utils" / "UTILS_Stats_modeles.py"


class TableauFictif:
    def __init__(self):
        self.dictParametres = {}
        self.lignes = []


class SQLiteFamilles:
    def __init__(self):
        self.connexion = sqlite3.connect(":memory:")
        self.cursor = self.connexion.cursor()
        self.requetes = []
        self.cursor.executescript("""
            CREATE TABLE familles(IDfamille INTEGER PRIMARY KEY, IDcaisse INTEGER);
            CREATE TABLE caisses(IDcaisse INTEGER PRIMARY KEY, nom TEXT);
            CREATE TABLE comptes_payeurs(
                IDcompte_payeur INTEGER PRIMARY KEY, IDfamille INTEGER);
            CREATE TABLE consommations(
                IDcompte_payeur INTEGER, IDindividu INTEGER,
                date TEXT, etat TEXT, IDactivite INTEGER);
            CREATE TABLE inscriptions(
                IDcompte_payeur INTEGER, IDindividu INTEGER,
                statut TEXT, IDactivite INTEGER);
        """)
        self.cursor.executemany("INSERT INTO familles VALUES (?,?)", [
            (1, 10), (2, 20), (3, 999), (4, 10), (5, 10)])
        self.cursor.executemany("INSERT INTO caisses VALUES (?,?)", [
            (10, "CAF"), (20, "MSA")])
        self.cursor.executemany("INSERT INTO comptes_payeurs VALUES (?,?)", [
            (11, 1), (12, 1), (21, 2), (31, 3), (41, 4), (51, 5)])
        self.cursor.executemany(
            "INSERT INTO consommations VALUES (?,?,?,?,?)", [
                (11, 101, "2026-04-01", "present", 1),
                (11, 101, "2026-04-02", "present", 1),
                (12, 102, "2026-04-03", "reservation", 1),
                (12, 102, "2026-04-04", "present", 2),
                (21, 201, "2026-04-02", "present", 1),
                (21, 202, "2026-04-02", "present", 2),
                (31, 301, "2026-04-05", "present", 2),
                (41, 401, "2026-04-01", "absent", 1),
                (41, 401, "2025-04-01", "present", 1),
                (41, 401, "2026-04-01", "present", 3),
                (51, 501, "2026-04-08", "reservation", 1),
            ])
        self.cursor.executemany(
            "INSERT INTO inscriptions VALUES (?,?,?,?)", [
                (11, 101, "ok", 1), (12, 102, "ok", 1),
                (12, 102, "ok", 2), (21, 201, "ok", 1),
                (21, 202, "ok", 2), (31, 301, "annule", 2),
                (41, 401, "annule", 1), (41, 401, "ok", 3),
                (51, 501, "ok", 1),
            ])

    def ExecuterReq(self, sql):
        self.requetes.append(sql)
        self.cursor.execute(sql)

    def ResultatReq(self):
        return self.cursor.fetchall()

    def Close(self):
        self.connexion.close()


def charger_code_reel():
    """Aucun remplacement des algorithmes metier du moteur cible."""
    modele = ast.parse(MODELES_SOURCE.read_text(encoding="utf-8"))
    aides = [
        n for n in modele.body if isinstance(n, ast.FunctionDef)
        and n.name in ("LireCacheStats", "EcrireCacheStats")
    ]
    if len(aides) != 2:
        raise AssertionError("Contrat du cache de statistiques introuvable")
    code = ast.parse(SOURCE.read_text(encoding="utf-8"))
    noms = (
        "GetDictCaisses", "GetDictMembres",
        "Tableau_repartition_caisses", "Tableau_nombre_membres",
    )
    cibles = [
        n for n in code.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))
        and n.name in noms
    ]
    if len(cibles) != len(noms):
        raise AssertionError("Objets Caisses/Composition introuvables")
    ns_aides = {}
    module = ast.Module(body=aides, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(MODELES_SOURCE), "exec"), ns_aides)
    modeles = SimpleNamespace(
        Tableau=TableauFictif,
        GetDatesPeriode=lambda p: (
            p["periode"]["date_debut"], p["periode"]["date_fin"]),
        GetConditionActivites=lambda p: "(" + ",".join(
            str(x) for x in p["listeActivites"]) + ")",
        LireCacheStats=ns_aides["LireCacheStats"],
        EcrireCacheStats=ns_aides["EcrireCacheStats"],
    )
    ns = {"MODELES": modeles, "_": lambda texte: texte}
    module = ast.Module(body=cibles, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(SOURCE), "exec"), ns)
    return ns


def parametres(mode, activites=(1, 2)):
    return {
        "mode": mode, "listeActivites": list(activites),
        "periode": {
            "date_debut": datetime.date(2026, 1, 1),
            "date_fin": datetime.date(2026, 12, 31),
        },
    }


def oracle_sql(db, mode, activites):
    """Oracle distinct par famille/individu, avec filtres SQL explicites."""
    marques = ",".join("?" for _ in activites)
    if mode == "presents":
        from_sql = """consommations c
            JOIN comptes_payeurs p ON p.IDcompte_payeur=c.IDcompte_payeur"""
        filtre = ("c.etat IN ('reservation','present') "
                  "AND c.date BETWEEN ? AND ? "
                  "AND c.IDactivite IN (" + marques + ")")
        arguments = ("2026-01-01", "2026-12-31", *activites)
    else:
        from_sql = """inscriptions c
            JOIN comptes_payeurs p ON p.IDcompte_payeur=c.IDcompte_payeur"""
        filtre = "c.statut='ok' AND c.IDactivite IN (" + marques + ")"
        arguments = tuple(activites)
    base = " FROM " + from_sql + " WHERE " + filtre
    participants = db.connexion.execute(
        "SELECT DISTINCT p.IDfamille, c.IDindividu" + base, arguments
    ).fetchall()
    membres = collections.Counter()
    for famille, individu in participants:
        membres[famille] += 1
    histogramme = dict(collections.Counter(membres.values()))
    caisses = dict(db.connexion.execute(
        "SELECT f.IDcaisse, COUNT(DISTINCT f.IDfamille) FROM familles f "
        "WHERE f.IDfamille IN (SELECT DISTINCT p.IDfamille" + base +
        ") GROUP BY f.IDcaisse", arguments
    ).fetchall())
    return caisses, histogramme


class Q4CaissesMembresSQLTests(unittest.TestCase):
    def setUp(self):
        self.db = SQLiteFamilles()
        self.classes = charger_code_reel()

    def tearDown(self):
        self.db.Close()

    def verifier(self, db, mode, activites=(1, 2)):
        params = parametres(mode, activites)
        attendu_caisses, attendu_membres = oracle_sql(
            db, mode, activites)
        reponse_caisses = self.classes["GetDictCaisses"](db, params)
        reponse_membres = self.classes["GetDictMembres"](db, params)
        self.assertEqual(
            {cle: val["nbreFamilles"]
             for cle, val in reponse_caisses.items()}, attendu_caisses)
        self.assertEqual(reponse_membres, attendu_membres)
        self.assertEqual(
            reponse_caisses.get(999, {}).get("nom"),
            "Caisse inconnue" if 999 in attendu_caisses else None)
        tableau_caisses = self.classes["Tableau_repartition_caisses"]()
        tableau_membres = self.classes["Tableau_nombre_membres"]()
        requetes_initiales = len(db.requetes)
        tableau_caisses.MAJ(DB=db, dictParametres=params)
        tableau_membres.MAJ(DB=db, dictParametres=params)
        # Les methodes reelles partagent le cache d'une meme connexion.
        self.assertEqual(len(db.requetes), requetes_initiales)
        libelles = {10: "CAF", 20: "MSA", 999: "Caisse inconnue"}
        attendu_affichage = collections.Counter({
            libelles[k]: v for k, v in attendu_caisses.items()
        })
        self.assertEqual(collections.Counter(
            dict(tableau_caisses.lignes)), attendu_affichage)
        self.assertEqual(dict(tableau_membres.lignes), attendu_membres)
        self.assertEqual(
            tableau_membres.lignes, sorted(tableau_membres.lignes))
        return reponse_caisses, reponse_membres

    def test_presents_distinct_familles_et_personnes(self):
        self.verifier(self.db, "presents")

    def test_inscrits_exclut_annulations(self):
        self.verifier(self.db, "inscrits")

    def test_cache_invalide_apres_mutation_filtre(self):
        params = parametres("presents")
        original = self.classes["GetDictCaisses"](self.db, params)
        avant = len(self.db.requetes)
        self.assertIs(self.classes["GetDictCaisses"](self.db, params), original)
        self.assertEqual(len(self.db.requetes), avant)
        params["listeActivites"][:] = [1]
        filtre = self.classes["GetDictCaisses"](self.db, params)
        self.assertGreater(len(self.db.requetes), avant)
        self.assertEqual(
            {k: v["nbreFamilles"] for k, v in filtre.items()},
            oracle_sql(self.db, "presents", (1,))[0])
        self.assertNotEqual(filtre, original)

    def test_cache_isole_sur_deux_connexions(self):
        params = parametres("presents")
        precedent = self.classes["GetDictCaisses"](self.db, params)
        nouvelle = SQLiteFamilles()
        try:
            nouvelle.cursor.execute("INSERT INTO familles VALUES (?,?)", (6, 20))
            nouvelle.cursor.execute(
                "INSERT INTO comptes_payeurs VALUES (?,?)", (61, 6))
            nouvelle.cursor.execute(
                "INSERT INTO consommations VALUES (?,?,?,?,?)",
                (61, 601, "2026-04-11", "present", 1))
            actuel = self.classes["GetDictCaisses"](nouvelle, params)
            self.assertEqual(actuel[20]["nbreFamilles"],
                             precedent[20]["nbreFamilles"] + 1)
            self.assertEqual(
                {k: v["nbreFamilles"] for k, v in actuel.items()},
                oracle_sql(nouvelle, "presents", (1, 2))[0])
            self.assertIsNot(actuel, precedent)
        finally:
            nouvelle.Close()

    def test_selection_absente_aucun_resultat(self):
        for mode in ("presents", "inscrits"):
            with self.subTest(mode=mode):
                db = SQLiteFamilles()
                try:
                    self.verifier(db, mode, (99,))
                finally:
                    db.Close()


if __name__ == "__main__":
    unittest.main()
