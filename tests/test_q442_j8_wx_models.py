# -*- coding: utf-8 -*-
"""Q442/J8 - actual wx + MODELES statistical objects on wholly fake SQLite.

No real database, no user profile, no application login, no network and no
release build. This qualifies real wx.MemoryFS/HTML after the J3-J7 SQL tests.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"


@unittest.skipUnless(sys.platform == "win32", "Native wxPython on Windows required")
class Q442NativeWxObjects(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for folder in (ROOT, NOETHYS):
            if str(folder) not in sys.path:
                sys.path.insert(0, str(folder))
        from tests import _garde_reseau  # Import network guard before Noethys
        import wx
        import matplotlib
        matplotlib.use("Agg", force=True)
        from matplotlib import pyplot as plt
        from Utils import UTILS_Stats_modeles as MODELES
        from Utils import UTILS_Stats_qf_objets as Q442
        from tests.test_q442_j6_mysql57 import fixture_sqlite, config, ReadDB
        cls.wx = wx
        cls.plt = plt
        cls.MODELES = MODELES
        cls.Q442 = Q442
        cls.fixture_sqlite = staticmethod(fixture_sqlite)
        cls.config = staticmethod(config)
        cls.ReadDB = ReadDB
        cls.app = wx.App(False)

    @classmethod
    def tearDownClass(cls):
        cls.plt.close("all")
        cls.app = None

    def setUp(self):
        self.sqlite = self.fixture_sqlite()
        self.db = self.ReadDB(self.sqlite, sqlite=True)
        self.p = {
            "mode": "presents",
            "listeActivites": [10],
            "dictActivites": {10: "ALSH MULTISITE FICTIF"},
            "periode": {"date_debut": "2026-07-01", "date_fin": "2026-07-31"},
            "q442_configuration": self.config(),
            "q442_sites": None,
            "q442_vue": "global",
        }

    def tearDown(self):
        self.sqlite.close()
        self.plt.close("all")

    def test_native_table_html_and_denominator(self):
        table = self.Q442.TableauQ442("familles", "qf")
        self.assertIsInstance(table, self.MODELES.Tableau)
        table.MAJ(DB=self.db, dictParametres=self.p)
        self.assertEqual(table.totaux[0][1], 9)
        self.assertEqual(sum(row[1] for row in table.lignes), 9)
        html = table.GetObjetHTML()
        self.assertIn("QF non communique", html)
        self.assertIn("TOTAL", html)

    def test_native_bar_chart_memoryfs_png(self):
        chart = self.Q442.GrapheBarresQ442("individus", "qf")
        self.assertIsInstance(chart, self.MODELES.Graphe)
        figure = self.plt.figure()
        chart.MAJ(figure=figure, DB=self.db, dictParametres=self.p)
        chart.MemoriseImage(figure)
        self.assertTrue(chart.bitmap.IsOk())
        self.assertIn("memory:image-", chart.GetObjetHTML())
        self.assertEqual(self.db.queries and len(self.db.queries), 3)

    def test_native_pie_chart_keeps_zero_category_in_legend(self):
        chart = self.Q442.GrapheSecteursQ442("familles", "qf")
        figure = self.plt.figure()
        chart.MAJ(figure=figure, DB=self.db, dictParametres=self.p)
        legend = figure.axes[0].get_legend()
        self.assertIsNotNone(legend)
        self.assertTrue(any("E historique : 0" in text.get_text()
                            for text in legend.get_texts()))
        chart.MemoriseImage(figure)
        self.assertTrue(chart.bitmap.IsOk())

    def test_real_html_model_registration_and_print_preview_markup(self):
        from unittest import mock
        rubriques = [
            {"nom": "Familles", "code": "familles", "visible": True, "pages": []},
            {"nom": "Individus", "code": "individus", "visible": True, "pages": []},
        ]
        self.Q442.preparer_pages(self.MODELES, rubriques,
                                  configuration=self.p["q442_configuration"])
        self.assertEqual(len(rubriques[0]["pages"]), 2)
        self.assertEqual(len(rubriques[1]["pages"]), 2)
        html_model = self.MODELES.HTML(liste_objets=rubriques)
        html_model.SetParametres(self.p)
        # Only the fake in-memory connection may be used by the real model.
        self.db.Close = lambda: None
        with mock.patch.object(self.MODELES.GestionDB, "DB", return_value=self.db):
            html_model.MAJ(page="q442_familles_qf")
            display = html_model.GetHTML(page="q442_familles_qf")
            selection = ["familles", "q442_familles_qf"]
            selection += [x.code for x in rubriques[0]["pages"][0]["objets"]]
            printable = html_model.GetHTML(
                mode="impression", selectionsCodes=selection,
                rubrique="familles", page="q442_familles_qf")
        self.assertIn("QF non communique", display)
        self.assertIn("memory:image-", display)
        self.assertIn("QF non communique", printable)
        self.assertIn("memory:image-", printable)
        self.assertGreater(len(printable), 100)


if __name__ == "__main__":
    unittest.main()
