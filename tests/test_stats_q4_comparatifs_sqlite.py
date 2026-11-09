# -*- coding: utf-8 -*-
"""Q4-B7 - Comparatifs Familles et Individus : SQL et 2 MAJ source.

Le decoupage annuel est extrait de la vraie fonction des modeles.
Les valeurs sont comparees a des ensembles distincts independants.
Les barres sont capturees ; aucune image/GUI native dans ce banc.
"""
import ast
from collections import defaultdict
import datetime
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest

from tests.test_stats_q4_individus_genre_ages_sqlite import ObjetBase, Vector

ROOT = Path(__file__).resolve().parents[1]
INDIV_SOURCE = ROOT / "noethys" / "Utils" / "UTILS_Stats_individus.py"
FAM_SOURCE = ROOT / "noethys" / "Utils" / "UTILS_Stats_familles.py"
MODEL_SOURCE = ROOT / "noethys" / "Utils" / "UTILS_Stats_modeles.py"


class AxComparatif:
    def __init__(self):
        self.barres = []
        self.labels = []
        self.xticks = []
        self.ylabel = None
        self.title = None

    def bar(self, x, y, largeur, **props):
        self.barres.append((x, y, largeur, props))
        return None

    def set_xticks(self, xs):
        self.xticks = list(xs)

    def set_xticklabels(self, labels):
        self.labels = list(labels)

    def get_xticklabels(self):
        return self.labels

    def get_yticklabels(self):
        return []

    def set_ylabel(self, label, **kwargs):
        self.ylabel = label

    def set_title(self, titre, **kwargs):
        self.title = titre
        return titre

    def grid(self, *args, **kwargs):
        self.grid_args = args


class Figure:
    def __init__(self):
        self.axes = []
        self.ajustements = []

    def add_subplot(self, identifiant):
        if identifiant != 111:
            raise AssertionError("Subplot invalide")
        a = AxComparatif()
        self.axes.append(a)
        return a

    def subplots_adjust(self, **kwargs):
        self.ajustements.append(kwargs)


class RecetteDB:
    def __init__(self):
        self.connexion = sqlite3.connect(":memory:")
        self.cursor = self.connexion.cursor()
        self.requetes = []
        self.cursor.executescript("""
            CREATE TABLE comptes_payeurs(
                IDcompte_payeur INTEGER PRIMARY KEY,
                IDfamille INTEGER NOT NULL);
            CREATE TABLE consommations(
                IDindividu INTEGER,
                IDcompte_payeur INTEGER,
                date TEXT, etat TEXT, IDactivite INTEGER);
        """)
        self.cursor.executemany(
            "INSERT INTO comptes_payeurs VALUES (?,?)", [
                (11, 1), (12, 1), (21, 2), (31, 3), (41, 4)])
        self.cursor.executemany(
            "INSERT INTO consommations VALUES (?,?,?,?,?)", [
                (101, 11, "2024-02-01", "present", 1),
                (102, 12, "2024-03-01", "reservation", 1),
                (101, 11, "2024-03-01", "present", 1),
                (101, 11, "2025-02-01", "present", 1),
                (103, 21, "2025-03-01", "present", 2),
                (103, 21, "2025-03-02", "present", 2),
                (104, 31, "2025-02-01", "absent", 1),
                (105, 31, "2026-03-01", "present", 1),
                (106, 41, "2026-03-01", "reservation", 2),
                (107, 12, "2026-03-02", "present", 2),
                (108, 11, "2026-03-03", "present", 1),
                (109, 41, "2026-03-03", "absent", 1),
                (110, 41, "2026-03-04", "present", 3),
                (111, 41, "2027-01-05", "present", 1),
            ])

    def ExecuterReq(self, sql):
        self.requetes.append(sql)
        self.cursor.execute(sql)

    def ResultatReq(self):
        return self.cursor.fetchall()

    def Close(self):
        self.connexion.close()


def extraits_reels(source, classe):
    modele = ast.parse(MODEL_SOURCE.read_text(encoding="utf-8"))
    periode = next(
        x for x in modele.body
        if isinstance(x, ast.FunctionDef)
        and x.name == "GetPeriodesComparatives")
    impl = ast.Module(body=[periode], type_ignores=[])
    ast.fix_missing_locations(impl)
    helper = {
        "datetime": datetime, "_": lambda x: x,
        "DateEngEnDateDD": lambda s: datetime.date.fromisoformat(str(s)[:10]),
    }
    exec(compile(impl, str(MODEL_SOURCE), "exec"), helper)
    modeles = SimpleNamespace(
        Graphe=ObjetBase,
        GetDatesPeriode=lambda p: (
            p["periode"]["date_debut"], p["periode"]["date_fin"]),
        GetConditionActivites=lambda p: "(" + ",".join(
            str(i) for i in p["listeActivites"]) + ")",
        GetPeriodesComparatives=helper["GetPeriodesComparatives"],
        DateEngEnDateDD=lambda s: datetime.date.fromisoformat(str(s)[:10]),
        ConvertitCouleur2=lambda c: c,
        COULEUR_VERT_POMME=(35, 100, 20),
        COULEUR_BLEU_CIEL=(20, 50, 200),
    )
    tree = ast.parse(source.read_text(encoding="utf-8"))
    defs = [
        n for n in tree.body
        if (isinstance(n, ast.FunctionDef) and n.name == "GetComparatifNombre")
        or (isinstance(n, ast.ClassDef) and n.name == classe)
    ]
    if len(defs) != 2:
        raise AssertionError("Graphe comparatif ou SQL source introuvable")
    namespace = {
        "MODELES": modeles, "_": lambda x: x,
        "DICT_COMPARATIF_NOMBRE": {"dictParametres": {}, "dictResultats": {}},
        "arange": lambda n: Vector(range(n)),
        "matplotlib": SimpleNamespace(pyplot=SimpleNamespace(
            setp=lambda *args, **kwargs: None)),
    }
    module = ast.Module(body=defs, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(source), "exec"), namespace)
    return namespace


def parametres(mode="presents", activites=(1, 2), annee=2026):
    return {
        "mode": mode,
        "listeActivites": list(activites),
        "periode": {
            "type": "annee", "annee": annee,
            "date_debut": datetime.date(annee, 1, 1),
            "date_fin": datetime.date(annee, 12, 31),
        },
    }


def reference(db, p):
    """Oracle independant : grouper par annee en ensembles SQL bruts."""
    if p["mode"] != "presents":
        return {}, {}
    comptes = dict(db.connexion.execute(
        "SELECT IDcompte_payeur,IDfamille FROM comptes_payeurs"
    ).fetchall())
    individu = defaultdict(set)
    famille = defaultdict(set)
    for ind, payeur, date, etat, act in db.connexion.execute(
            "SELECT IDindividu,IDcompte_payeur,date,etat,IDactivite FROM consommations"):
        if act not in p["listeActivites"] or etat not in ("present", "reservation"):
            continue
        annee = int(date[:4])
        individu[annee].add(ind)
        famille[annee].add(comptes[payeur])
    return {a: len(v) for a, v in individu.items()}, {
        a: len(v) for a, v in famille.items()}


class ComparatifsSQLTests(unittest.TestCase):
    def setUp(self):
        self.db = RecetteDB()
        self.codes = {
            "individus": extraits_reels(
                INDIV_SOURCE, "Graphe_nombre_individus"),
            "familles": extraits_reels(
                FAM_SOURCE, "Graphe_nombre_familles"),
        }

    def tearDown(self):
        self.db.Close()

    def verifier(self, params, existe):
        nombres_individus, nombres_familles = reference(self.db, params)
        years = sorted(nombres_individus)
        for typ, nombres, classe in (
            ("individus", nombres_individus, "Graphe_nombre_individus"),
            ("familles", nombres_familles, "Graphe_nombre_familles"),
        ):
            with self.subTest(type=typ, mode=params["mode"],
                              activites=params["listeActivites"]):
                ns = self.codes[typ]
                g = ns[classe]()
                f = Figure()
                nbAvant = len(self.db.requetes)
                self.assertIs(g.MAJ(
                    figure=f, DB=self.db, dictParametres=params), f)
                ax = f.axes[0]
                if not existe:
                    self.assertFalse(ax.barres)
                    self.assertEqual(len(self.db.requetes), nbAvant)
                else:
                    self.assertEqual(
                        ax.labels, ["Année %d" % y for y in years])
                    self.assertEqual(
                        [item[1] for item in ax.barres],
                        [nombres[y] for y in years])
                    self.assertEqual(
                        [item[3]["color"] for item in ax.barres],
                        [ns["MODELES"].COULEUR_VERT_POMME
                         if y == params["periode"]["annee"]
                         else ns["MODELES"].COULEUR_BLEU_CIEL
                         for y in years])
                    self.assertEqual(len(ax.barres), len(years))
                    self.assertTrue(ax.ylabel)

    def test_comparatifs_presents_plusieurs_annees(self):
        self.verifier(parametres(), existe=True)

    def test_comparatifs_presents_filtre_unique(self):
        self.verifier(parametres(activites=(1,)), existe=True)

    def test_inscrits_ne_declenche_pas_de_comparatif(self):
        self.verifier(parametres("inscrits"), existe=False)

    def test_periode_reference_differente_change_couleur(self):
        self.verifier(parametres(annee=2025), existe=True)

    def test_absence_de_consommer_ne_trace_pas_de_barres(self):
        p = parametres(activites=(99,))
        for type_, classe in (("individus", "Graphe_nombre_individus"),
                              ("familles", "Graphe_nombre_familles")):
            with self.subTest(type=type_):
                f = Figure()
                ns = self.codes[type_]
                g = ns[classe]()
                self.assertIs(g.MAJ(
                    figure=f, DB=self.db, dictParametres=p), f)
                self.assertEqual(f.axes[0].barres, [])


if __name__ == "__main__":
    unittest.main()
