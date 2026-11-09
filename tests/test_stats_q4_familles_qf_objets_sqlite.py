# -*- coding: utf-8 -*-
"""Q4-B9 - 4 objets QF (vraies MAJ + SQLite purement synthetique).

ATTENTION : ce banc qualifie le SQL, les comptes et les series transmises
au rendu. Il NE tranche PAS la regle metier multi-types des QF. Les graphes
utilisent des axes fictifs ; wx, HTML et impression restent non testes.
"""
import ast
import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest

from tests.test_stats_restore_qf_sqlite import SQLiteStatsDB
from tests.test_stats_q4_individus_genre_ages_sqlite import (
    FigureCapture, ObjetBase, Vector,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "noethys" / "Utils" / "UTILS_Stats_familles.py"
CLASSES = (
    "Tableau_qf_tarifs", "Graphe_qf_tarifs",
    "Tableau_qf_defaut", "Graphe_qf_defaut",
)
FUNCTIONS = (
    "_QuotientsAlaDate",
    "_TranchesTarifsExclusives",
    "GetDictQuotients",
    "TrierQF",
)


def extraire_sources():
    source = ast.parse(SOURCE.read_text(encoding="utf-8"))
    elements = [
        element for element in source.body
        if (isinstance(element, ast.ClassDef) and element.name in CLASSES)
        or (isinstance(element, ast.FunctionDef) and element.name in FUNCTIONS)
    ]
    if len(elements) != len(CLASSES) + len(FUNCTIONS):
        raise AssertionError("Moteur QF modifie : requalification requise")
    modeles = SimpleNamespace(
        Tableau=ObjetBase, Graphe=ObjetBase,
        GetConditionActivites=lambda p: "(" + ",".join(
            str(x) for x in p["listeActivites"]) + ")",
        GetDatesPeriode=lambda p: (
            p["periode"]["date_debut"], p["periode"]["date_fin"]),
        # Le jeu SQLite ne contient aucune table activites; la date
        # extreme en mode inscrits est donc une stub fixe, documentee.
        GetDateExtremeActivites=lambda db, **kw: (
            datetime.date(2026, 1, 1)
            if kw["typeDate"] == "date_debut"
            else datetime.date(2026, 12, 31)),
        ConvertitCouleur2=lambda x: x,
        COULEUR_VERT_POMME=(151, 253, 79),
    )
    mpl = SimpleNamespace(
        cm=SimpleNamespace(hsv=lambda x: ("hsv", x)),
        pyplot=SimpleNamespace(setp=lambda *args, **kwargs: None))
    env = {
        "MODELES": modeles, "matplotlib": mpl,
        "arange": lambda n: Vector(range(n)),
        "datetime": datetime,
        "_": lambda x: x,
    }
    module = ast.Module(body=elements, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(SOURCE), "exec"), env)
    return env


def params(mode="presents", activites=(1, 2)):
    return {
        "mode": mode,
        "listeActivites": list(activites),
        "periode": {
            "date_debut": datetime.date(2026, 1, 1),
            "date_fin": datetime.date(2026, 12, 31),
        },
    }


def attendu_tranches_tarifs():
    # Oracle manuel du jeu SQL strictement fictif de QFSQLiteTests.
    # Famille 1: 150 ; 2: deux types contradictoires ; 3: sans QF ; 4: zero.
    return {
        (0, 299): 2, (300, 699): 0, (700, 999999): 0,
        "pasqf": 1, "a_verifier": 1, "autre": 0,
    }


class Q4QFObjetsSQLiteTests(unittest.TestCase):
    def setUp(self):
        self.db = SQLiteStatsDB()
        self.env = extraire_sources()

    def tearDown(self):
        self.db.Close()

    def test_tableau_et_graphe_tarifs_vraies_maj(self):
        p = params()
        attendu = attendu_tranches_tarifs()
        o = self.env["Tableau_qf_tarifs"]()
        o.MAJ(DB=self.db, dictParametres=p)
        self.assertEqual(o.lignes, [
            ("0 - 299", 2), ("300 - 699", 0),
            ("700 - 999999", 0),
            ("Sans QF", 1), ("QF à vérifier", 1),
        ])
        self.assertIn("31/12/2026", o.nom)
        f = FigureCapture()
        graphique = self.env["Graphe_qf_tarifs"]()
        self.assertIs(graphique.MAJ(
            figure=f, DB=self.db, dictParametres=p), f)
        ax = f.axes[0]
        self.assertEqual(
            list(zip(ax.labels, ax.valeurs)),
            o.lignes)
        self.assertEqual(ax.options["autopct"], "%1.1f%%")
        self.assertEqual(sum(ax.valeurs), sum(attendu.values()))
        # Meme connexion et parametres : aucun nouveau SQL.
        self.assertEqual(len(self.db.queries), 2)

    def test_tableau_et_graphe_tranches_de_100(self):
        p = params()
        t = self.env["Tableau_qf_defaut"]()
        t.MAJ(DB=self.db, dictParametres=p)
        valeurs = dict(t.lignes)
        self.assertEqual(valeurs["0 - 100"], 1)
        self.assertEqual(valeurs["101 - 200"], 1)
        self.assertEqual(valeurs["Sans QF"], 1)
        self.assertEqual(valeurs["QF à vérifier"], 1)
        self.assertNotIn("Autre", valeurs)
        self.assertEqual(sum(valeurs.values()), 4)
        f = FigureCapture()
        graphique = self.env["Graphe_qf_defaut"]()
        self.assertIs(graphique.MAJ(
            figure=f, DB=self.db, dictParametres=p), f)
        ax = f.axes[0]
        # Le graphe historique omet les familles "sans QF" et
        # "a verifier". L'ecart de total est CONSTATE, pas avalise.
        self.assertEqual(list(zip(ax.labels, ax.barres[0][1])),
                         [("0 - 100", 1), ("101 - 200", 1)])
        self.assertEqual(sum(ax.barres[0][1]), 2)
        self.assertEqual(len(self.db.queries), 2)

    def test_cache_perimetre_et_mutation_des_activites(self):
        p = params()
        source = self.env["GetDictQuotients"]
        a = source(self.db, p)
        self.assertEqual(a["dictTranchesTarifs"], attendu_tranches_tarifs())
        self.assertEqual(len(self.db.queries), 2)
        self.assertIs(source(self.db, p), a)
        self.assertEqual(len(self.db.queries), 2)
        p["listeActivites"][:] = [1]
        b = source(self.db, p)
        self.assertEqual(len(self.db.queries), 4)
        self.assertIsNot(a, b)
        self.assertNotEqual(
            b["dictTranchesTarifs"], a["dictTranchesTarifs"])
        self.assertEqual(sum(b["dictTranchesTarifs"].values()), 4)

    def test_inscrits_conserve_qf_a_verifier_mais_date_a_valider(self):
        p = params("inscrits")
        source = self.env["GetDictQuotients"]
        r = source(self.db, p)
        self.assertEqual(r["date_reference"], datetime.date.today())
        self.assertEqual(r["dictTranchesTarifs"], attendu_tranches_tarifs())
        self.assertEqual(sum(r["dictTranchesDefaut"].values()), 4)
        # La date actuelle des inscrits n'est pas encore une regle
        # multi-activite/metier approuvee.
        t = self.env["Tableau_qf_tarifs"]()
        t.MAJ(DB=self.db, dictParametres=p)
        self.assertIn("QF à vérifier", dict(t.lignes))

    def test_meme_valeur_de_deux_types_ne_prove_pas_un_type_choisi(self):
        # Une famille avec deux IDtype_quotient actifs de valeur identique
        # est actuellement fusionnee numeriquement par le moteur.
        # Ce test observe le contrat sans le justifier du point de vue metier.
        self.db.cursor.execute(
            "INSERT INTO quotients VALUES (?,?,?,?,?,?)",
            (1, 12, "2026-01-01", "2099-12-31", 150, 2))
        r = self.env["GetDictQuotients"](self.db, params())
        self.assertEqual(r["dictTranchesTarifs"], attendu_tranches_tarifs())

    def test_absence_de_familles_filtrees_tables_vides_de_donnees(self):
        p = params(activites=(99,))
        r = self.env["GetDictQuotients"](self.db, p)
        self.assertEqual(sum(r["dictTranchesTarifs"].values()), 0)
        self.assertEqual(sum(r["dictTranchesDefaut"].values()), 0)
        t = self.env["Tableau_qf_tarifs"]()
        t.MAJ(DB=self.db, dictParametres=p)
        self.assertEqual(
            t.lignes, [("Sans QF", 0), ("QF à vérifier", 0)])
        g = self.env["Graphe_qf_defaut"]()
        f = FigureCapture()
        self.assertIs(g.MAJ(figure=f, DB=self.db, dictParametres=p), f)
        self.assertEqual(f.axes[0].barres[0][1], [])


if __name__ == "__main__":
    unittest.main()
