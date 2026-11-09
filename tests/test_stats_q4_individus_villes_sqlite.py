# -*- coding: utf-8 -*-
"""Q4-B8 - Deux objets Villes : SQL SQLite reel, distances fictives hors reseau.

Les MAJ() et GetDictVilles sources sont executes sur SQLite synthetique,
avec prise en compte d'adresse_auto, des doublons et du top-5+Autres.
La fonction reseau GetDistancesVilles est remplacee par un service local fixe.
Aucun test de geocodage reel, PNG/HTML, wx installe ni requete internet.
"""
import ast
from collections import Counter
import datetime
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest

from tests.test_stats_q4_individus_genre_ages_sqlite import (
    FigureCapture, ObjetBase,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "noethys" / "Utils" / "UTILS_Stats_individus.py"
MODEL_SOURCE = ROOT / "noethys" / "Utils" / "UTILS_Stats_modeles.py"
ORIGINE = ("35000", "Rennes")


class DBSQLite:
    def __init__(self):
        self.connexion = sqlite3.connect(":memory:")
        self.cursor = self.connexion.cursor()
        self.requetes = []
        self.cursor.executescript("""
            CREATE TABLE individus(
                IDindividu INTEGER PRIMARY KEY, nom TEXT, prenom TEXT,
                rue_resid TEXT, cp_resid TEXT, ville_resid TEXT,
                adresse_auto INTEGER);
            CREATE TABLE consommations(
                IDindividu INTEGER, date TEXT, etat TEXT, IDactivite INTEGER);
            CREATE TABLE inscriptions(
                IDindividu INTEGER, statut TEXT, IDactivite INTEGER);
            CREATE TABLE organisateur(
                IDorganisateur INTEGER PRIMARY KEY, cp TEXT, ville TEXT);
        """)
        adresses = [
            (1, "35000", "Rennes", None),
            (2, "35000", "Rennes", None),
            (3, "35300", "Fougeres", None),
            (4, None, None, None),
            (5, "35600", "Redon", None),
            (6, "35500", "Vitre", None),
            (7, "35170", "Bruz", None),
            (8, "35800", "Dinard", None),
            (9, "35400", "Saint-Malo", None),
            (10, "35170", "Bruz", None),
            (11, "44000", "Nantes", 1), # adresse_auto vers Rennes
            (12, "35400", "Saint-Malo", None),
        ]
        self.cursor.executemany(
            "INSERT INTO individus VALUES (?,?,?,?,?,?,?)",
            [(i, "Nom", "Prenom", "", cp, ville, auto)
             for i, cp, ville, auto in adresses])
        self.cursor.execute(
            "INSERT INTO organisateur VALUES (1,?,?)", ORIGINE)
        self.cursor.executemany(
            "INSERT INTO consommations VALUES (?,?,?,?)",
            [(i, "2026-04-01", "present", 1 if i % 2 else 2)
             for i in range(1, 12)] + [
                 (1, "2026-04-02", "reservation", 1),
                 (12, "2026-04-02", "absent", 1),
                 (12, "2025-04-01", "present", 1),
                 (12, "2026-04-02", "present", 3),
             ])
        self.cursor.executemany(
            "INSERT INTO inscriptions VALUES (?,?,?)",
            [(i, "ok", 1 if i % 2 else 2)
             for i in range(1, 12)] + [
                 (1, "ok", 1),
                 (12, "annule", 1),
             ])

    def ExecuterReq(self, sql):
        self.requetes.append(sql)
        self.cursor.execute(sql)

    def ResultatReq(self):
        return self.cursor.fetchall()

    def Close(self):
        self.connexion.close()


def stub_distance(orig, destinations):
    assert orig == ORIGINE, (orig, ORIGINE)
    return {
        key: {
            "distance_texte": "%d km" % (len(key[1]) + 1),
            "distance_metres": (len(key[1]) + 1) * 1000,
        }
        for key in destinations
        if key != ORIGINE
    }


def classes_reelles():
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    noms = (
        "GetDictVilles",
        "Tableau_repartition_villes",
        "Graphe_repartition_villes",
    )
    defs = [
        node for node in arbre.body
        if (isinstance(node, (ast.FunctionDef, ast.ClassDef))
            and node.name in noms)
    ]
    if len(defs) != len(noms):
        raise AssertionError("Objets Q4-B8 manquants")
    tree = ast.parse(MODEL_SOURCE.read_text(encoding="utf-8"))
    cache = [
        node for node in tree.body if isinstance(node, ast.FunctionDef)
        and node.name in ("LireCacheStats", "EcrireCacheStats")
    ]
    if len(cache) != 2:
        raise AssertionError("Contrat cache manquant")
    mod = ast.Module(body=cache, type_ignores=[])
    ast.fix_missing_locations(mod)
    ns_cache = {}
    exec(compile(mod, str(MODEL_SOURCE), "exec"), ns_cache)
    modeles = SimpleNamespace(
        Tableau=ObjetBase, Graphe=ObjetBase,
        GetDatesPeriode=lambda p: (
            p["periode"]["date_debut"], p["periode"]["date_fin"]),
        GetConditionActivites=lambda p: "(" + ",".join(
            str(x) for x in p["listeActivites"]) + ")",
        LireCacheStats=ns_cache["LireCacheStats"],
        EcrireCacheStats=ns_cache["EcrireCacheStats"],
    )
    mpl = SimpleNamespace(
        cm=SimpleNamespace(hsv=lambda x: ("hsv", x)),
        pyplot=SimpleNamespace(setp=lambda *args, **kwargs: None))
    appels = []

    def distances(p, origine, destinations):
        appels.append((origine, list(destinations)))
        return stub_distance(origine, destinations)

    env = {
        "MODELES": modeles, "matplotlib": mpl,
        "_": lambda text: text,
        "GetDistancesVilles": distances,
        "DICT_VILLES": {},
    }
    mod = ast.Module(body=defs, type_ignores=[])
    ast.fix_missing_locations(mod)
    exec(compile(mod, str(SOURCE), "exec"), env)
    return env, appels


def parametres(mode="presents", activites=(1, 2)):
    return {
        "mode": mode,
        "listeActivites": list(activites),
        "periode": {
            "date_debut": datetime.date(2026, 1, 1),
            "date_fin": datetime.date(2026, 12, 31),
        },
    }


def reference(db, p):
    """Oracle Python a partir de lignes brutes, sans GetDictVilles."""
    addresses = {}
    for ind, cp, ville, auto in db.connexion.execute(
            "SELECT IDindividu,cp_resid,ville_resid,adresse_auto FROM individus"):
        addresses[ind] = (cp, ville, auto)
    selected = set()
    if p["mode"] == "presents":
        for ind, jour, statut, activite in db.connexion.execute(
                "SELECT IDindividu,date,etat,IDactivite FROM consommations"):
            if (p["periode"]["date_debut"] <=
                    datetime.date.fromisoformat(jour) <=
                    p["periode"]["date_fin"]
                    and statut in ("present", "reservation")
                    and activite in p["listeActivites"]):
                selected.add(ind)
    else:
        for ind, statut, activite in db.connexion.execute(
                "SELECT IDindividu,statut,IDactivite FROM inscriptions"):
            if statut == "ok" and activite in p["listeActivites"]:
                selected.add(ind)
    distribution = Counter()
    for ind in selected:
        cp, ville, auto = addresses[ind]
        if auto is not None and auto in addresses:
            cp, ville, _ = addresses[auto]
        distribution[(cp, ville)] += 1
    result = {}
    for key, n in distribution.items():
        dist = stub_distance(ORIGINE, [key]).get(key)
        result[key] = {
            "nbreIndividus": n,
            "distance": dist["distance_texte"] if dist is not None else "",
            "distance_metres": dist["distance_metres"] if dist is not None else 0,
        }
    return result


class Q4VillesSQLiteTests(unittest.TestCase):
    def setUp(self):
        self.db = DBSQLite()
        self.classes, self.appels = classes_reelles()

    def tearDown(self):
        self.db.Close()

    def verifier(self, params):
        attendu = reference(self.db, params)
        donnees = self.classes["GetDictVilles"](self.db, params)
        self.assertEqual(donnees, attendu)
        nb = len(self.db.requetes)
        t = self.classes["Tableau_repartition_villes"]()
        t.MAJ(DB=self.db, dictParametres=params)
        self.assertEqual(len(self.db.requetes), nb)
        rows = []
        for key, val in attendu.items():
            nom = key[1] or ""
            rows.append((val["nbreIndividus"], nom, val["distance"]))
        rows.sort(reverse=True)
        self.assertEqual(t.lignes, [
            (nom or "Ville inconnue", dist, n)
            for n, nom, dist in rows
        ])
        f = FigureCapture()
        g = self.classes["Graphe_repartition_villes"]()
        self.assertIs(g.MAJ(figure=f, DB=self.db, dictParametres=params), f)
        axe = f.axes[0]
        series = sorted([
            (val["nbreIndividus"], key[1] or "")
            for key, val in attendu.items()
        ], reverse=True)
        if len(series) > 5:
            autres = sum(n for n, _ in series[5:])
            series = series[:5] + [(autres, "Autres")]
        series = [(n, nom or "N.C.") for n, nom in series]
        self.assertEqual(list(zip(axe.valeurs, axe.labels)), series)
        self.assertEqual(sum(axe.valeurs), sum(
            val["nbreIndividus"] for val in attendu.values()))
        self.assertEqual(axe.options["autopct"], "%1.1f%%")

    def test_presents_doublons_adresse_auto_top5(self):
        self.verifier(parametres())
        self.assertTrue(self.appels)
        self.assertEqual(self.appels[0][0], ORIGINE)

    def test_inscrits_doublons_et_annules(self):
        self.verifier(parametres("inscrits"))

    def test_filtre_une_activite(self):
        self.verifier(parametres(activites=(1,)))

    def test_cache_connexion_mutation_filtres(self):
        p = parametres()
        r = self.classes["GetDictVilles"](self.db, p)
        n = len(self.db.requetes)
        a = len(self.appels)
        self.assertIs(self.classes["GetDictVilles"](self.db, p), r)
        self.assertEqual(len(self.appels), a)
        self.assertEqual(len(self.db.requetes), n)
        p["listeActivites"][:] = [1]
        new = self.classes["GetDictVilles"](self.db, p)
        self.assertEqual(new, reference(self.db, p))
        self.assertNotEqual(new, r)
        self.assertEqual(len(self.appels), a + 1)

    def test_organisateur_sans_origine_pas_appel_distances(self):
        self.db.cursor.execute(
            "UPDATE organisateur SET cp='',ville='' WHERE IDorganisateur=1")
        p = parametres()
        donnees = self.classes["GetDictVilles"](self.db, p)
        self.assertFalse(self.appels)
        self.assertTrue(donnees)
        self.assertTrue(all(v["distance"] == "" for v in donnees.values()))

    def test_activite_sans_personnes_aucun_appel(self):
        p = parametres(activites=(99,))
        self.assertEqual(self.classes["GetDictVilles"](self.db, p), {})
        self.assertEqual(self.appels, [])


if __name__ == "__main__":
    unittest.main()
