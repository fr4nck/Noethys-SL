# -*- coding: utf-8 -*-
"""Q4-B4 - Genre et ages : sept vraies classes MAJ, SQL SQLite fictif.

Exerce les calculs SQL et les valeurs de tableaux/graphes.
Les figures sont des doubles collectant les donnees, PAS des rendus natifs.
Aucun wx, aucune installation, aucune donnee utilisateur.
"""
import ast
from collections import Counter
import datetime
from pathlib import Path
import sqlite3
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Stats_individus.py"
MODELES_SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Stats_modeles.py"
CIVILITES = {1: "M", 2: "F", 3: None}
NOMS_GENRES = {"M": "Garçons", "F": "Filles", "None": "N.C."}
CLASSES = (
    "Tableau_repartition_genre",
    "Graphe_repartition_genre",
    "Tableau_repartition_ages",
    "Graphe_repartition_ages",
    "Tableau_repartition_annees_naiss",
    "Graphe_repartition_annees_naiss",
    "Tableau_repartition_tranches_ages",
)


class ObjetBase:
    def __init__(self):
        self.dictParametres = {}
        self.lignes = []
        self.decalage_x = 0.0


class Vector(list):
    def __add__(self, nombre):
        return Vector([x + nombre for x in self])


class AxeCapture:
    def __init__(self):
        self.labels = []
        self.valeurs = []
        self.barres = []
        self.titre = None
        self.xticks = []
        self.xlabel = None
        self.ylabel = None
        self.options = {}

    def pie(self, valeurs, labels=(), colors=(), **options):
        self.valeurs = list(valeurs)
        self.labels = list(labels)
        self.options = options
        self.couleurs = list(colors)
        return ([], [], [])

    def bar(self, positions, valeurs, largeur, **options):
        self.barres.append((list(positions), list(valeurs), largeur, options))
        return []

    def set_title(self, titre, **kwargs):
        self.titre = titre
        return titre

    def set_aspect(self, aspect):
        self.aspect = aspect

    def set_xlabel(self, label, **kwargs):
        self.xlabel = label

    def set_ylabel(self, label, **kwargs):
        self.ylabel = label

    def set_xticks(self, positions):
        self.xticks = list(positions)

    def set_xticklabels(self, labels):
        self.labels = list(labels)

    def get_xticklabels(self):
        return self.labels

    def get_yticklabels(self):
        return []

    def grid(self, *args, **kwargs):
        self.grille = (args, kwargs)


class FigureCapture:
    def __init__(self):
        self.axes = []
        self.ajustements = []

    def add_subplot(self, identifiant):
        if identifiant != 111:
            raise AssertionError("Sous-figure inattendue")
        axe = AxeCapture()
        self.axes.append(axe)
        return axe

    def subplots_adjust(self, **kwargs):
        self.ajustements.append(kwargs)


class SQLiteRecette:
    def __init__(self):
        self.connexion = sqlite3.connect(":memory:")
        self.cursor = self.connexion.cursor()
        self.requetes = []
        self.cursor.executescript("""
            CREATE TABLE individus(
                IDindividu INTEGER PRIMARY KEY,
                IDcivilite INTEGER,
                date_naiss TEXT);
            CREATE TABLE consommations(
                IDindividu INTEGER, date TEXT, etat TEXT, IDactivite INTEGER);
            CREATE TABLE inscriptions(
                IDindividu INTEGER, statut TEXT, IDactivite INTEGER);
        """)
        self.cursor.executemany("INSERT INTO individus VALUES (?,?,?)", [
            (101, 1, "2026-03-10"),  # 0 an
            (102, 1, "2018-04-20"),  # 8 ans
            (103, 2, "2016-09-10"),  # 10 ans
            (104, 2, "2008-08-20"),  # 18 ans
            (105, 3, None),          # civilite et naissance inconnues
            (106, 1, "2012-12-31"),  # anniversaire sur la borne
            (107, 2, "2007-12-31"),  # activite non choisie
            (108, 3, "2017-01-01"),  # age connu, genre inconnu
            (109, 1, "2016-12-31"),  # hors periode en presents
            (110, 2, ""),            # naissance vide
            (111, 1, "2010-04-01"),
        ])
        self.cursor.executemany(
            "INSERT INTO consommations VALUES (?,?,?,?)", [
                (101, "2026-03-01", "present", 1),
                (101, "2026-03-02", "reservation", 1),
                (101, "2026-03-03", "present", 2),
                (102, "2026-03-02", "reservation", 1),
                (103, "2026-03-04", "present", 2),
                (104, "2026-03-05", "present", 1),
                (105, "2026-03-06", "present", 2),
                (106, "2026-03-06", "absent", 1),
                (107, "2026-03-06", "present", 3),
                (108, "2026-03-06", "reservation", 1),
                (109, "2025-03-06", "present", 1),
                (110, "2026-03-07", "present", 2),
                (111, "2026-03-07", "present", 1),
            ])
        self.cursor.executemany(
            "INSERT INTO inscriptions VALUES (?,?,?)", [
                (101, "ok", 1), (101, "ok", 2),
                (102, "ok", 1),
                (103, "ok", 2),
                (104, "annule", 1),
                (105, "ok", 2),
                (106, "ok", 1),
                (107, "ok", 3),
                (108, "ok", 1),
                (109, "ok", 2),
                (110, "annule", 2),
                (111, "ok", 1),
            ])

    def ExecuterReq(self, sql):
        self.requetes.append(sql)
        self.cursor.execute(sql)

    def ResultatReq(self):
        return self.cursor.fetchall()

    def Close(self):
        self.connexion.close()


def preparer_sources():
    """Compiler les vrais algorithmes sans importer le module wx."""
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    fonctions = ("GetDictGenres", "GetDictAges", "_CleTriStatistiques")
    extraits = [
        item for item in arbre.body
        if (isinstance(item, ast.FunctionDef) and item.name in fonctions)
        or (isinstance(item, ast.ClassDef) and item.name in CLASSES)
    ]
    if len(extraits) != len(fonctions) + len(CLASSES):
        raise AssertionError("Inventaire Q4-B4 modifie, requalification requise")

    module_modeles = ast.parse(MODELES_SOURCE.read_text(encoding="utf-8"))
    cache = [
        item for item in module_modeles.body
        if isinstance(item, ast.FunctionDef)
        and item.name in ("LireCacheStats", "EcrireCacheStats")
    ]
    if len(cache) != 2:
        raise AssertionError("Contrats cache non disponibles")
    module = ast.Module(body=cache, type_ignores=[])
    ast.fix_missing_locations(module)
    espaces_cache = {}
    exec(compile(module, str(MODELES_SOURCE), "exec"), espaces_cache)

    modeles = SimpleNamespace(
        Texte=ObjetBase, Tableau=ObjetBase, Graphe=ObjetBase,
        GetDatesPeriode=lambda p: (
            p["periode"]["date_debut"], p["periode"]["date_fin"]),
        GetConditionActivites=lambda p: "(" + ",".join(
            str(x) for x in p["listeActivites"]) + ")",
        LireCacheStats=espaces_cache["LireCacheStats"],
        EcrireCacheStats=espaces_cache["EcrireCacheStats"],
        ConvertitCouleur2=lambda x: x,
        COULEUR_VERT_POMME=(151, 253, 79),
        COULEUR_BLEU_CIEL=(174, 212, 253),
    )
    faux_mpl = SimpleNamespace(
        pyplot=SimpleNamespace(setp=lambda *a, **k: None))
    environnement = {
        "MODELES": modeles, "matplotlib": faux_mpl,
        "datetime": datetime, "_": lambda x: x,
        "arange": lambda n: Vector(range(n)),
        "DICT_AGES": {"dictParametres": {}, "dictAges": {}, "dictAnnees": {}},
        "DICT_GENRES": {"dictParametres": {}, "dictResultats": {}},
    }
    module = ast.Module(body=extraits, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(SOURCE), "exec"), environnement)
    return environnement


def parametres(mode, activites=(1, 2), debut=2026, fin=2026):
    return {
        "mode": mode, "listeActivites": list(activites),
        "periode": {
            "date_debut": datetime.date(debut, 1, 1),
            "date_fin": datetime.date(fin, 12, 31),
        },
    }


def selection_independante(db, p):
    """Requete parametree SELECT DISTINCT, independante du SQL produit."""
    marks = ",".join("?" for _ in p["listeActivites"])
    if p["mode"] == "presents":
        jointure = "consommations c"
        condition = ("c.etat IN ('reservation','present') "
                     "AND c.date BETWEEN ? AND ? "
                     "AND c.IDactivite IN (" + marks + ")")
        args = (str(p["periode"]["date_debut"]),
                str(p["periode"]["date_fin"]), *p["listeActivites"])
    else:
        jointure = "inscriptions c"
        condition = "c.statut='ok' AND c.IDactivite IN (" + marks + ")"
        args = tuple(p["listeActivites"])
    return db.connexion.execute(
        "SELECT DISTINCT i.IDindividu, i.IDcivilite, i.date_naiss "
        "FROM individus i JOIN " + jointure +
        " ON c.IDindividu = i.IDindividu WHERE " + condition,
        args,
    ).fetchall()


def oracle(db, p):
    personnes = selection_independante(db, p)
    genres = Counter()
    ages = Counter()
    annees = Counter()
    tranches = {}
    date_reference = p["periode"]["date_fin"]
    for _, civilite, date_texte in personnes:
        genre = str(CIVILITES[civilite])
        genres[genre] += 1
        if date_texte:
            naissance = datetime.date.fromisoformat(date_texte)
            age = date_reference.year - naissance.year
            if (date_reference.month, date_reference.day) < (
                    naissance.month, naissance.day):
                age -= 1
            annee = naissance.year
        else:
            age, annee = None, None
        ages[age] += 1
        annees[annee] += 1
        tranche = age // 10 if age is not None else None
        valeur = tranches.setdefault(tranche, Counter())
        valeur[genre] += 1
    return genres, ages, annees, tranches


class Q4GenreAgesSQLiteTests(unittest.TestCase):
    def setUp(self):
        self.db = SQLiteRecette()
        self.source = preparer_sources()
        self.data = ModuleType("Data")
        self.data.DATA_Civilites = SimpleNamespace(
            GetDictCivilites=lambda: {
                cle: {"sexe": valeur} for cle, valeur in CIVILITES.items()
            })
        self.patch = mock.patch.dict(sys.modules, {"Data": self.data})
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.db.Close()

    def test_tableau_genre_present_et_inscrit(self):
        for mode in ("presents", "inscrits"):
            for activites in ((1, 2), (1,)):
                with self.subTest(mode=mode, activites=activites):
                    p = parametres(mode, activites)
                    attendu, _, _, _ = oracle(self.db, p)
                    tableau = self.source["Tableau_repartition_genre"]()
                    tableau.MAJ(DB=self.db, dictParametres=p)
                    obtenu = dict(tableau.lignes)
                    self.assertEqual(
                        obtenu, {NOMS_GENRES[k]: v
                                 for k, v in attendu.items() if v > 0})
                    self.assertEqual(sum(obtenu.values()),
                                     len(selection_independante(self.db, p)))

    def test_graphe_genre_donnees_axe_sans_rendu(self):
        for mode in ("presents", "inscrits"):
            with self.subTest(mode=mode):
                p = parametres(mode)
                genres, _, _, _ = oracle(self.db, p)
                fig = FigureCapture()
                graphe = self.source["Graphe_repartition_genre"]()
                self.assertIs(graphe.MAJ(
                    figure=fig, DB=self.db, dictParametres=p), fig)
                axe = fig.axes[0]
                self.assertEqual(
                    dict(zip(axe.labels, axe.valeurs)),
                    {NOMS_GENRES[k]: v for k, v in genres.items() if v})
                self.assertEqual(axe.aspect, 1)
                self.assertEqual(axe.options.get("autopct"), "%1.1f%%")
                self.assertEqual(len(axe.couleurs), len(axe.valeurs))

    def test_tableaux_age_annee_et_tranches_present_inscrit(self):
        configurations = (
            ("Tableau_repartition_ages", "ages"),
            ("Tableau_repartition_annees_naiss", "annees"),
            ("Tableau_repartition_tranches_ages", "tranches"),
        )
        for mode in ("presents", "inscrits"):
            for activites in ((1, 2), (1,)):
                p = parametres(mode, activites)
                _, ages, annees, tranches = oracle(self.db, p)
                for nom, famille in configurations:
                    with self.subTest(mode=mode, activites=activites, objet=nom):
                        objet = self.source[nom]()
                        objet.MAJ(DB=self.db, dictParametres=p)
                        if famille == "ages":
                            attendu = [
                                (str(k) if k is not None
                                 else "Date de naissance inconnue", v)
                                for k, v in sorted(ages.items(),
                                                   key=lambda kv: (
                                                       kv[0] is None,
                                                       kv[0] or 0))
                            ]
                        elif famille == "annees":
                            attendu = [
                                (str(k) if k is not None
                                 else "Année de naissance inconnue", v)
                                for k, v in sorted(annees.items(),
                                                   key=lambda kv: (
                                                       kv[0] is None,
                                                       kv[0] or 0))
                            ]
                        else:
                            attendu = []
                            for tranche in sorted(
                                    tranches, key=lambda k: (
                                        k is None, k or 0)):
                                groupes = tranches[tranche]
                                label = (
                                    "%d - %d" % (tranche * 10, tranche * 10 + 9)
                                    if tranche is not None else "Age inconnu")
                                m, f, inconnu = (groupes["M"], groupes["F"],
                                                 groupes["None"])
                                attendu.append((
                                    label, m, f, inconnu, m + f + inconnu))
                        self.assertEqual(objet.lignes, attendu)

    def test_graphiques_age_et_annee_donnees_axes(self):
        mapping = (
            ("Graphe_repartition_ages", "ages", "N.C."),
            ("Graphe_repartition_annees_naiss", "annees", "N.C."),
        )
        for mode in ("presents", "inscrits"):
            p = parametres(mode)
            _, ages, annees, _ = oracle(self.db, p)
            for nom, famille, label_inconnu in mapping:
                with self.subTest(mode=mode, objet=nom):
                    donnees = ages if famille == "ages" else annees
                    fig = FigureCapture()
                    graphe = self.source[nom]()
                    self.assertIs(
                        graphe.MAJ(
                            figure=fig, DB=self.db, dictParametres=p), fig)
                    axe = fig.axes[0]
                    attendu = {
                        str(k) if k is not None else label_inconnu: v
                        for k, v in donnees.items()
                    }
                    self.assertEqual(
                        dict(zip(axe.labels, axe.barres[0][1])), attendu)
                    self.assertEqual(len(axe.barres), 1)
                    self.assertEqual(axe.barres[0][2], 0.5)
                    self.assertTrue(axe.titre)

    def test_cache_genre_filtres_et_connexions_isolees(self):
        params = parametres("presents")
        ancien = self.source["GetDictGenres"](self.db, params)
        debut = len(self.db.requetes)
        self.assertIs(self.source["GetDictGenres"](self.db, params), ancien)
        self.assertEqual(len(self.db.requetes), debut)
        params["listeActivites"][:] = [1]
        nouveau = self.source["GetDictGenres"](self.db, params)
        self.assertEqual(len(self.db.requetes), debut + 1)
        self.assertNotEqual(
            {k: v["quantite"] for k, v in ancien.items()},
            {k: v["quantite"] for k, v in nouveau.items()})
        self.assertEqual(
            {k: v["quantite"] for k, v in nouveau.items() if v["quantite"]},
            dict(oracle(self.db, params)[0]))
        autre = SQLiteRecette()
        try:
            autre.cursor.execute(
                "INSERT INTO individus VALUES (?,?,?)",
                (199, 2, "2015-12-31"))
            autre.cursor.execute(
                "INSERT INTO consommations VALUES (?,?,?,?)",
                (199, "2026-04-01", "present", 1))
            resultat = self.source["GetDictGenres"](autre, params)
            self.assertEqual(
                resultat["F"]["quantite"], nouveau["F"]["quantite"] + 1)
        finally:
            autre.Close()

    def test_absence_et_dates_hors_plage_tableaux(self):
        for mode, p in (
            ("presents", parametres("presents", (99,))),
            ("presents", parametres("presents", (1, 2), 2027, 2027)),
            ("inscrits", parametres("inscrits", (99,))),
        ):
            with self.subTest(mode=mode, params=p):
                self.assertFalse(selection_independante(self.db, p))
                for nom in (
                    "Tableau_repartition_genre",
                    "Tableau_repartition_ages",
                    "Tableau_repartition_annees_naiss",
                    "Tableau_repartition_tranches_ages",
                ):
                    obj = self.source[nom]()
                    obj.MAJ(DB=self.db, dictParametres=p)
                    self.assertEqual(obj.lignes, [])


if __name__ == "__main__":
    unittest.main()
