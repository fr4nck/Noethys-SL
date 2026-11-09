# -*- coding: utf-8 -*-
"""Q4-C1 - 15 graphiques sur vrai Matplotlib Agg, sans wx ni production.

Les methodes source MAJ() sont reutilisees depuis les bancs SQLite Q4.
Les donnees et le SQL restent synthetiques et les sorties PNG sont gardees
en memoire. Les trois premieres couches (SQL, Matplotlib, format PNG) sont
exercees ; wx.MemoryFS, HTML, impression et exécutable installé NE LE SONT PAS.

NOETHYS_STATS_Q4_AGG=1 active ces tests dans une CI dediee disposant de
matplotlib et numpy. La CI rapide ordinaire les ignore volontairement.
"""
import io
import os
import sys
import unittest

CASES = (
    ("indiv_nombre", "Graphe_nombre_individus"),
    ("indiv_ages", "Graphe_repartition_genre"),
    ("indiv_ages", "Graphe_repartition_ages"),
    ("indiv_ages", "Graphe_repartition_annees_naiss"),
    ("indiv_scolarite", "Graphe_repartition_ecoles"),
    ("indiv_scolarite", "Graphe_repartition_niveaux_scolaires"),
    ("indiv_profession", "Graphe_activites_professionnelles"),
    ("indiv_profession", "Graphe_nouveaux_individus"),
    ("indiv_profession", "Graphe_arrivee_individus"),
    ("indiv_villes", "Graphe_repartition_villes"),
    ("fam_nombre", "Graphe_nombre_familles"),
    ("fam_pies", "Graphe_repartition_caisses"),
    ("fam_pies", "Graphe_nombre_membres"),
    ("fam_qf", "Graphe_qf_tarifs"),
    ("fam_qf", "Graphe_qf_defaut"),
)


def preparer(categorie, testcase):
    """Retourne le code source compile, une connexion SQLite et ses params."""
    if categorie == "indiv_nombre" or categorie == "fam_nombre":
        from tests.test_stats_q4_comparatifs_sqlite import (
            extraits_reels, INDIV_SOURCE, FAM_SOURCE,
            RecetteDB, parametres,
        )
        base = INDIV_SOURCE if categorie == "indiv_nombre" else FAM_SOURCE
        cls = "Graphe_nombre_individus" if categorie == "indiv_nombre" else "Graphe_nombre_familles"
        return extraits_reels(base, cls), RecetteDB(), parametres()

    if categorie == "indiv_ages":
        from tests.test_stats_q4_individus_genre_ages_sqlite import (
            preparer_sources, SQLiteRecette, parametres, CIVILITES,
        )
        from types import ModuleType, SimpleNamespace
        from unittest import mock
        d = ModuleType("Data")
        d.DATA_Civilites = SimpleNamespace(GetDictCivilites=lambda: {
            k: {"sexe": sexe} for k, sexe in CIVILITES.items()
        })
        patcher = mock.patch.dict(sys.modules, {"Data": d})
        patcher.start()
        testcase.addCleanup(patcher.stop)
        return preparer_sources(), SQLiteRecette(), parametres("presents")

    if categorie == "indiv_scolarite":
        from tests.test_stats_q4_individus_scolarite_sqlite import (
            charger_vraies_classes, SQLiteScolarite, parametres,
        )
        return charger_vraies_classes(), SQLiteScolarite(), parametres()

    if categorie == "indiv_profession":
        from tests.test_stats_q4_individus_profession_anciennete_sqlite import (
            charger_classes, DBSQLite, parametres,
        )
        return charger_classes(), DBSQLite(), parametres()

    if categorie == "indiv_villes":
        from tests.test_stats_q4_individus_villes_sqlite import (
            classes_reelles, DBSQLite, parametres,
        )
        env, _appels = classes_reelles()
        return env, DBSQLite(), parametres()

    if categorie == "fam_pies":
        from tests.test_stats_q4_graphes_familles_donnees import graphes_reels
        from tests.test_stats_q4_caisses_membres_sqlite import (
            SQLiteFamilles, parametres,
        )
        return graphes_reels(), SQLiteFamilles(), parametres("presents")

    if categorie == "fam_qf":
        from tests.test_stats_q4_familles_qf_objets_sqlite import (
            extraire_sources, SQLiteStatsDB, params,
        )
        return extraire_sources(), SQLiteStatsDB(), params("presents")

    raise AssertionError("Categorie Q4 inconnue : %s" % categorie)


@unittest.skipUnless(
    os.environ.get("NOETHYS_STATS_Q4_AGG") == "1",
    "Rendu Agg Q4 uniquement dans CI isolee explicite"
)
class Q4MatplotlibAggTests(unittest.TestCase):
    def verifier(self, groupe, nom):
        import matplotlib
        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
        import numpy as np
        from PIL import Image

        espace, db, p = preparer(groupe, self)
        self.addCleanup(db.Close)

        # Les bancs SQLite capturent des axes fictifs. En Q4-C1, les vraies
        # fonctions matplotlib/numpy et des couleurs RGB normalisees sont
        # reinstallees dans leur environnement d'execution.
        espace["matplotlib"] = matplotlib
        espace["arange"] = np.arange
        modele = espace["MODELES"]
        if hasattr(modele, "ConvertitCouleur2"):
            modele.ConvertitCouleur2 = lambda rgb: tuple(x / 255.0 for x in rgb)

        graphe = espace[nom]()
        fig = plt.figure(figsize=(6, 4), dpi=100)
        self.addCleanup(lambda: plt.close(fig))
        retour = graphe.MAJ(figure=fig, DB=db, dictParametres=p)
        self.assertIs(retour, fig)
        self.assertEqual(len(fig.axes), 1)
        axe = fig.axes[0]
        # Pie : patches ; bar : patches ; line : lines.
        self.assertGreater(
            len(axe.patches) + len(axe.lines), 0,
            "Graphe sans aucun element dessine : %s" % nom)

        dest = io.BytesIO()
        fig.savefig(dest, format="png")
        image = dest.getvalue()
        self.assertTrue(image.startswith(b"\x89PNG\r\n\x1a\n"),
                        "PNG non conforme : %s" % nom)
        self.assertGreater(len(image), 2000, nom)
        dest.seek(0)
        with Image.open(dest) as png:
            self.assertEqual(png.format, "PNG")
            self.assertEqual(png.size, (600, 400))
            png.verify()


def _creer_test(groupe, nom):
    def exercice(self):
        self.verifier(groupe, nom)
    exercice.__doc__ = "MAJ()+matplotlib Agg PNG reel : " + nom
    return exercice


for _groupe, _nom in CASES:
    setattr(Q4MatplotlibAggTests, "test_" + _nom.lower(),
            _creer_test(_groupe, _nom))


if __name__ == "__main__":
    unittest.main()
