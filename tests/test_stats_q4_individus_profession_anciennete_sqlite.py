# -*- coding: utf-8 -*-
"""Q4-B6 : MAJ reelles des 6 objets Profession/Anciennete sur SQLite fictif.

Vrais SQL, caches sources, et contenu de tableaux / series d'axes.
Les axes capture sont des doublures ; aucun PNG, wx, HTML ou impression.
"""
import ast
from collections import Counter, defaultdict
import datetime
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest

from tests.test_stats_q4_individus_genre_ages_sqlite import (
    AxeCapture, ObjetBase, Vector,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "noethys" / "Utils" / "UTILS_Stats_individus.py"
MODELES_SOURCE = ROOT / "noethys" / "Utils" / "UTILS_Stats_modeles.py"
PROFESSIONS = {10: "Salariés", 20: "Indépendants"}
MOIS = ("Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
        "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre")

FUNCTIONS = ("GetListeActivitesPro", "GetAnciennete", "GetDesinscrits")
CLASSES = (
    "Tableau_activites_professionnelles",
    "Graphe_activites_professionnelles",
    "Tableau_nouveaux_individus",
    "Graphe_nouveaux_individus",
    "Graphe_arrivee_individus",
    "Tableau_anciens_individus",
)


class AxeCaptureQ4(AxeCapture):
    def plot(self, x, y, *args, **kwargs):
        self.plots = getattr(self, "plots", [])
        self.plots.append((list(x), list(y)))

    def set_xlim(self, bas, haut):
        self.xlim = (bas, haut)


class FigureCaptureQ4:
    def __init__(self):
        self.axes = []
        self.autoformatte = False

    def add_subplot(self, code):
        if code != 111:
            raise AssertionError("subplot inconnu")
        ax = AxeCaptureQ4()
        self.axes.append(ax)
        return ax

    def subplots_adjust(self, **kwargs):
        self.ajustement = kwargs

    def autofmt_xdate(self):
        self.autoformatte = True


class DBSQLite:
    def __init__(self):
        self.connexion = sqlite3.connect(":memory:")
        self.cursor = self.connexion.cursor()
        self.requetes = []
        self.cursor.executescript("""
            CREATE TABLE individus(
                IDindividu INTEGER PRIMARY KEY,
                IDcategorie_travail INTEGER);
            CREATE TABLE categories_travail(
                IDcategorie INTEGER PRIMARY KEY, nom TEXT);
            CREATE TABLE consommations(
                IDindividu INTEGER, date TEXT, etat TEXT, IDactivite INTEGER);
            CREATE TABLE inscriptions(
                IDindividu INTEGER, statut TEXT, IDactivite INTEGER,
                date_desinscription TEXT);
        """)
        self.cursor.executemany(
            "INSERT INTO individus VALUES (?,?)", [
                (101, 10), (102, 10), (103, 20),
                (104, None), (105, 20), (106, 10),
                (107, None), (108, 20), (109, 10),
            ])
        self.cursor.executemany(
            "INSERT INTO categories_travail VALUES (?,?)",
            sorted(PROFESSIONS.items()))
        self.cursor.executemany(
            "INSERT INTO consommations VALUES (?,?,?,?)", [
                (101, "2025-08-10", "present", 1),
                (101, "2026-02-01", "present", 1),
                (101, "2026-02-02", "reservation", 1),
                (102, "2026-02-01", "present", 1),
                (102, "2026-04-09", "present", 2),
                (103, "2026-03-01", "present", 2),
                (104, "2026-03-02", "reservation", 1),
                (105, "2026-03-02", "absent", 1),
                (106, "2025-11-01", "present", 3),
                (106, "2026-05-01", "present", 3),
                (107, "2027-02-01", "present", 1),
                (108, "2025-12-10", "present", 2),
                (109, "2025-06-01", "present", 1),
            ])
        self.cursor.executemany(
            "INSERT INTO inscriptions VALUES (?,?,?,?)", [
                (101, "ok", 1, "2026-05-01"),
                (101, "ok", 2, None),       # one deregistration per person
                (102, "ok", 1, None),
                (103, "ok", 2, "2026-03-11"),
                (104, "ok", 1, None),
                (105, "annule", 2, None),
                (106, "ok", 3, "2026-05-12"),  # outside selected activities
                (107, "ok", 1, "2025-10-20"), # before requested window
                (108, "ok", 2, None),
                (109, "ok", 1, "2027-03-01"), # after requested window
            ])

    def ExecuterReq(self, req):
        self.requetes.append(req)
        self.cursor.execute(req)

    def ResultatReq(self):
        return self.cursor.fetchall()

    def Close(self):
        self.connexion.close()


def charger_classes():
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    extraits = [
        item for item in arbre.body
        if (isinstance(item, ast.FunctionDef) and item.name in FUNCTIONS)
        or (isinstance(item, ast.ClassDef) and item.name in CLASSES)
    ]
    if len(extraits) != len(FUNCTIONS) + len(CLASSES):
        raise AssertionError("Inventaire fonctions/objets Q4-B6 modifie")
    tree = ast.parse(MODELES_SOURCE.read_text(encoding="utf-8"))
    caches = [n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name in ("LireCacheStats", "EcrireCacheStats")]
    if len(caches) != 2:
        raise AssertionError("Cache SQL absent")
    module = ast.Module(body=caches, type_ignores=[])
    ast.fix_missing_locations(module)
    espace = {}
    exec(compile(module, str(MODELES_SOURCE), "exec"), espace)
    modeles = SimpleNamespace(
        Tableau=ObjetBase, Graphe=ObjetBase,
        GetDatesPeriode=lambda p: (
            p["periode"]["date_debut"], p["periode"]["date_fin"]),
        GetConditionActivites=lambda p: "(" + ",".join(
            str(v) for v in p["listeActivites"]) + ")",
        DateEngEnDateDD=lambda s: datetime.date.fromisoformat(str(s)[:10]),
        LireCacheStats=espace["LireCacheStats"],
        EcrireCacheStats=espace["EcrireCacheStats"],
        LISTE_NOMS_MOIS=MOIS,
        ConvertitCouleur2=lambda c: c,
        COULEUR_VERT_POMME=(151, 253, 79),
    )
    mpl = SimpleNamespace(
        cm=SimpleNamespace(hsv=lambda valeur: ("hsv", valeur)),
        pyplot=SimpleNamespace(setp=lambda *args, **kwargs: None),
    )
    namespace = {
        "MODELES": modeles, "matplotlib": mpl, "datetime": datetime,
        "arange": lambda n: Vector(range(n)), "_": lambda x: x,
        "DICT_ACTI_PRO": {}, "DICT_ANCIENNETE": {},
        "DICT_DESINSCRITS": {},
    }
    module = ast.Module(body=extraits, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace


def parametres(mode="presents", activites=(1, 2), annee=2026):
    return {
        "mode": mode,
        "listeActivites": list(activites),
        "periode": {
            "date_debut": datetime.date(annee, 1, 1),
            "date_fin": datetime.date(annee, 12, 31),
        },
    }


def reference_pro(db, params):
    activites = set(params["listeActivites"])
    if params["mode"] == "presents":
        enregistrements = db.connexion.execute(
            "SELECT IDindividu, date, etat, IDactivite FROM consommations"
        ).fetchall()
        identifiants = {
            id_individu for id_individu, date, statut, activite in enregistrements
            if activite in activites
            and statut in ("reservation", "present")
            and params["periode"]["date_debut"] <= datetime.date.fromisoformat(date)
            <= params["periode"]["date_fin"]
        }
    else:
        enregistrements = db.connexion.execute(
            "SELECT IDindividu, statut, IDactivite FROM inscriptions"
        ).fetchall()
        identifiants = {
            identifiant for identifiant, statut, activite in enregistrements
            if activite in activites and statut == "ok"
        }
    personnes = dict(db.connexion.execute(
        "SELECT IDindividu, IDcategorie_travail FROM individus").fetchall())
    distribution = Counter(personnes[i] for i in identifiants)
    return sorted([(nb, PROFESSIONS.get(categorie, "Catégorie inconnue"))
                   for categorie, nb in distribution.items()], reverse=True)


def reference_anciennete(db, params):
    """Premier jour de presence historique, dernier jour dans le perimetre."""
    if params["mode"] != "presents":
        return {}, []
    valeurs = defaultdict(list)
    for identifiant, jour, etat, activite in db.connexion.execute(
            "SELECT IDindividu,date,etat,IDactivite FROM consommations"):
        date = datetime.date.fromisoformat(jour)
        if (activite in params["listeActivites"]
                and etat in ("reservation", "present")
                and date <= params["periode"]["date_fin"]):
            valeurs[identifiant].append(date)
    distribution = Counter()
    for dates in valeurs.values():
        if max(dates) >= params["periode"]["date_debut"]:
            premiere = min(dates)
            distribution[(premiere.year, premiere.month)] += 1
    debut = params["periode"]["date_debut"]
    fin = params["periode"]["date_fin"]
    mois = [(annee, m) for annee in range(debut.year, fin.year + 1)
            for m in range(1, 13)
            if (debut.year, debut.month) <= (annee, m) <= (fin.year, fin.month)]
    return dict(distribution), mois


def reference_desinscrits(db, params):
    if params["mode"] != "presents":
        return {}, []
    valeurs = {}
    for identifiant, jour, activite in db.connexion.execute(
            "SELECT IDindividu,date_desinscription,IDactivite "
            "FROM inscriptions WHERE date_desinscription IS NOT NULL"):
        d = datetime.date.fromisoformat(jour)
        if activite in params["listeActivites"] and (
                params["periode"]["date_debut"] <= d <=
                params["periode"]["date_fin"]):
            valeurs[identifiant] = (d.year, d.month)
    if not valeurs:
        return {}, []
    compter = dict(Counter(valeurs.values()))
    debut = params["periode"]["date_debut"]
    fin = params["periode"]["date_fin"]
    mois = [(annee, m) for annee in range(debut.year, fin.year + 1)
            for m in range(1, 13)
            if (debut.year, debut.month) <= (annee, m) <= (fin.year, fin.month)]
    return compter, mois


class Q4ProfessionAncienneteTests(unittest.TestCase):
    def setUp(self):
        self.db = DBSQLite()
        self.ns = charger_classes()

    def tearDown(self):
        self.db.Close()

    def test_profession_vraie_maj_tableau_graphe_modes(self):
        for mode in ("presents", "inscrits"):
            for filtre in ((1, 2), (1,)):
                with self.subTest(mode=mode, filtre=filtre):
                    p = parametres(mode, filtre)
                    attendu = reference_pro(self.db, p)
                    t = self.ns["Tableau_activites_professionnelles"]()
                    t.MAJ(DB=self.db, dictParametres=p)
                    self.assertEqual(t.lignes,
                                     [(label, n) for n, label in attendu])
                    f = FigureCaptureQ4()
                    g = self.ns["Graphe_activites_professionnelles"]()
                    self.assertIs(g.MAJ(
                        figure=f, DB=self.db, dictParametres=p), f)
                    axe = f.axes[0]
                    self.assertEqual(
                        list(zip(axe.valeurs, axe.labels)), attendu)
                    self.assertEqual(axe.options["autopct"], "%1.1f%%")

    def test_profession_cache_change_filtre_et_connexion(self):
        p = parametres()
        initial = self.ns["GetListeActivitesPro"](self.db, p)
        n = len(self.db.requetes)
        self.assertIs(self.ns["GetListeActivitesPro"](self.db, p), initial)
        self.assertEqual(n, len(self.db.requetes))
        p["listeActivites"][:] = [1]
        filtree = self.ns["GetListeActivitesPro"](self.db, p)
        self.assertEqual(filtree, reference_pro(self.db, p))
        self.assertNotEqual(filtree, initial)
        autre = DBSQLite()
        try:
            autre.cursor.execute("INSERT INTO individus VALUES (?,?)", (190, 20))
            autre.cursor.execute(
                "INSERT INTO consommations VALUES (?,?,?,?)",
                (190, "2026-08-01", "present", 1))
            nouveau = self.ns["GetListeActivitesPro"](autre, p)
            self.assertNotEqual(nouveau, filtree)
            self.assertEqual(nouveau, reference_pro(autre, p))
        finally:
            autre.Close()

    def test_anciennete_quatre_maj_donnees_et_serie(self):
        p = parametres()
        mois = reference_anciennete(self.db, p)
        attendu, calendrier = mois
        self.assertEqual(self.ns["GetAnciennete"](self.db, p), mois)
        t = self.ns["Tableau_nouveaux_individus"]()
        t.MAJ(DB=self.db, dictParametres=p)
        self.assertEqual(t.lignes, [
            ("%s %d" % (MOIS[m-1], an), attendu[(an, m)])
            for an, m in calendrier if (an, m) in attendu])
        f = FigureCaptureQ4()
        g = self.ns["Graphe_nouveaux_individus"]()
        self.assertIs(g.MAJ(figure=f, DB=self.db, dictParametres=p), f)
        self.assertEqual(f.axes[0].barres[0][1],
                         [attendu.get(k, 0) for k in calendrier])
        self.assertEqual(f.axes[0].labels,
                         ["%s %d" % (MOIS[m-1], an) for an, m in calendrier])
        f2 = FigureCaptureQ4()
        g2 = self.ns["Graphe_arrivee_individus"]()
        self.assertIs(g2.MAJ(figure=f2, DB=self.db, dictParametres=p), f2)
        self.assertEqual(f2.axes[0].plots[0], (
            [datetime.date(an, m, 1) for an, m in calendrier],
            [attendu.get(k, 0) for k in calendrier]))
        self.assertTrue(f2.autoformatte)
        self.assertEqual(f2.axes[0].xlim, (
            datetime.date(2026, 1, 1), datetime.date(2027, 1, 1)))
        dref, mdref = reference_desinscrits(self.db, p)
        t2 = self.ns["Tableau_anciens_individus"]()
        t2.MAJ(DB=self.db, dictParametres=p)
        self.assertEqual(t2.lignes, [
            ("%s %d" % (MOIS[m-1], an), dref[(an, m)])
            for an, m in mdref if (an, m) in dref])

    def test_anciennete_filtre_mutation_et_cache(self):
        p = parametres()
        initial = self.ns["GetAnciennete"](self.db, p)
        debut = len(self.db.requetes)
        self.assertIs(self.ns["GetAnciennete"](self.db, p), initial)
        self.assertEqual(len(self.db.requetes), debut)
        p["listeActivites"][:] = [1]
        change = self.ns["GetAnciennete"](self.db, p)
        self.assertEqual(change, reference_anciennete(self.db, p))
        self.assertNotEqual(change, initial)
        self.assertGreater(len(self.db.requetes), debut)

    def test_anciennete_inscrits_sans_source_et_filtres_absents(self):
        p = parametres("inscrits")
        self.assertEqual(self.ns["GetAnciennete"](self.db, p), ({}, []))
        self.assertEqual(self.ns["GetDesinscrits"](self.db, p), ({}, []))
        t = self.ns["Tableau_nouveaux_individus"]()
        t.MAJ(DB=self.db, dictParametres=p)
        self.assertEqual(t.lignes, [])
        t2 = self.ns["Tableau_anciens_individus"]()
        t2.MAJ(DB=self.db, dictParametres=p)
        self.assertEqual(t2.lignes, [])
        p2 = parametres("presents", (99,))
        self.assertEqual(self.ns["GetAnciennete"](self.db, p2), ({}, []))
        self.assertEqual(self.ns["GetDesinscrits"](self.db, p2), ({}, []))

    def test_profession_periode_vide_et_sans_activites(self):
        for p in (parametres("presents", (99,)),
                  parametres("presents", (1, 2), 2028)):
            with self.subTest(p=p):
                t = self.ns["Tableau_activites_professionnelles"]()
                t.MAJ(DB=self.db, dictParametres=p)
                self.assertEqual(t.lignes, [])


if __name__ == "__main__":
    unittest.main()
