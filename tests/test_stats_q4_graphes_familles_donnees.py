# -*- coding: utf-8 -*-
"""Q4-B2 : verifier les donnees transmises aux 2 graphes Familles.

Les methodes MAJ() des deux vraies classes et leur calcul SQL sont executes
sur SQLite synthetique. Seul l'axe matplotlib est une doublure capturant
les points/etiquettes : ce test NE qualifie pas le rendu PNG/HTML/wx natif.
"""
import ast
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import unittest

from tests.test_stats_q4_caisses_membres_sqlite import (
    SQLiteFamilles, charger_code_reel, oracle_sql, parametres,
)

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Stats_familles.py"


class GrapheBase:
    def __init__(self):
        self.dictParametres = {}
        self.nom = ""


class AxeCapture:
    def __init__(self):
        self.valeurs = []
        self.labels = []
        self.couleurs = []
        self.titre = None
        self.aspect = None

    def pie(self, valeurs, labels=(), colors=(), **kwargs):
        self.valeurs = list(valeurs)
        self.labels = list(labels)
        self.couleurs = list(colors)
        self.options = kwargs
        return ([], [], [])

    def set_title(self, texte, **kwargs):
        self.titre = texte
        return texte

    def set_aspect(self, aspect):
        self.aspect = aspect


class FigureCapture:
    def __init__(self):
        self.axes = []

    def add_subplot(self, code):
        if code != 111:
            raise AssertionError("Sous-graphe inattendu")
        a = AxeCapture()
        self.axes.append(a)
        return a


def graphes_reels():
    environnement = charger_code_reel()
    definitions = ast.parse(SOURCE.read_text(encoding="utf-8"))
    noms = ("Graphe_repartition_caisses", "Graphe_nombre_membres")
    classes = [
        n for n in definitions.body if isinstance(n, ast.ClassDef)
        and n.name in noms
    ]
    if len(classes) != len(noms):
        raise AssertionError("Graphes Familles Q4-B2 introuvables")
    # Aucune substitution du code metier ni des methodes MAJ.
    # Conserver le MODELES d'origine des fonctions SQL extraites : il fournit
    # LireCacheStats et EcrireCacheStats. Ne remplacer que le parent du graphe.
    environnement["MODELES"].Graphe = GrapheBase
    matplotlib = SimpleNamespace(
        cm=SimpleNamespace(hsv=lambda value: ("hsv", value)),
        pyplot=SimpleNamespace(setp=lambda *args, **kwargs: None),
    )
    environnement.update({
        "matplotlib": matplotlib, "_": lambda s: s,
    })
    module = ast.Module(body=classes, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(SOURCE), "exec"), environnement)
    return environnement


class Q4GraphesFamillesDonneesTests(unittest.TestCase):
    def setUp(self):
        self.db = SQLiteFamilles()
        self.code = graphes_reels()

    def tearDown(self):
        self.db.Close()

    def verifier(self, mode, activites=(1, 2)):
        p = parametres(mode, activites)
        repartition_caisses, histogramme = oracle_sql(
            self.db, mode, activites)
        noms_caisses = {
            10: "CAF", 20: "MSA", 999: "Caisse inconnue",
        }
        for nom, attendu in (
            ("Graphe_repartition_caisses",
             {noms_caisses[k]: v for k, v in repartition_caisses.items()}),
            ("Graphe_nombre_membres",
             {("%s membre" if k == 1 else "%s membres") % k: v
              for k, v in histogramme.items()}),
        ):
            with self.subTest(mode=mode, graphe=nom, activites=activites):
                figure = FigureCapture()
                graphe = self.code[nom]()
                retour = graphe.MAJ(
                    figure=figure, DB=self.db, dictParametres=p)
                self.assertIs(retour, figure)
                self.assertEqual(len(figure.axes), 1)
                axe = figure.axes[0]
                self.assertEqual(
                    Counter(dict(zip(axe.labels, axe.valeurs))),
                    Counter(attendu))
                self.assertEqual(sum(axe.valeurs), sum(attendu.values()))
                self.assertEqual(axe.aspect, 1)
                self.assertTrue(axe.titre)
                self.assertEqual(len(axe.couleurs), len(axe.valeurs))
                self.assertEqual(axe.options["autopct"], "%1.1f%%")
                self.assertIs(axe.options["shadow"], False)

    def test_graphes_matiere_presents(self):
        self.verifier("presents")

    def test_graphes_matiere_inscrits(self):
        self.verifier("inscrits")

    def test_graphes_filtre_une_seule_activite(self):
        for mode in ("presents", "inscrits"):
            self.verifier(mode, (1,))


if __name__ == "__main__":
    unittest.main()
