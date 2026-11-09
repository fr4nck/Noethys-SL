# -*- coding: utf-8 -*-
"""UI-432K : PNG Agg hors wx pour deux comparatifs statistiques qualifies."""
import io
import sys
import threading
from pathlib import Path
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "tests", ROOT / "noethys"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import _garde_reseau  # noqa: F401,E402
from Utils import UTILS_Stats_graphes_worker, UTILS_Stats_individus
from Utils import UTILS_Stats_familles

PNG = b"\x89PNG\r\n\x1a\n"
COMPARATIF = {
    "labels": ["2025", "2026"], "valeurs": [7, 9],
    "indexPeriodeReference": 1,
}


def nouvelle_instance(classe):
    obj = classe.__new__(classe)
    obj.taille = (470, 360)
    obj.decalage_x = 0.5
    return obj


class GraphesUnitairesTests(unittest.TestCase):
    def _qualifier(self, module, classe):
        objet = nouvelle_instance(classe)
        parametres = {"periode": 2026}
        self.assertTrue(UTILS_Stats_graphes_worker.est_compatible(objet))
        db = mock.Mock()
        origins = []
        results = []
        with mock.patch.object(UTILS_Stats_graphes_worker.GestionDB, "DB",
                               return_value=db) as ouverture, \
             mock.patch.object(module, "GetComparatifNombre",
                               side_effect=lambda *a: origins.append(
                                   threading.current_thread().name
                               ) or COMPARATIF):
            calcul = UTILS_Stats_graphes_worker.preparer(
                objet, parametres, "SQL_FICTIVE")
            parametres["periode"] = 1998
            def executer():
                results.append(calcul())
            worker = threading.Thread(target=executer, name="Stats-Graphe-Test")
            worker.start()
            worker.join(timeout=8)
        self.assertFalse(worker.is_alive())
        self.assertEqual(origins, ["Stats-Graphe-Test"])
        ouverture.assert_called_once_with(
            nomFichier="SQL_FICTIVE", suffixe=None, pooling=False)
        db.Close.assert_called_once()
        self.assertEqual(len(results), 1)
        image = results[0]
        self.assertTrue(image.startswith(PNG))
        from PIL import Image
        bmp = Image.open(io.BytesIO(image))
        self.assertEqual(bmp.size, objet.taille)
        self.assertIsNone(getattr(objet, "bitmap", None))

    def test_comparatif_individus_sans_acces_wx(self):
        self._qualifier(
            UTILS_Stats_individus,
            UTILS_Stats_individus.Graphe_nombre_individus)

    def test_comparatif_familles_sans_acces_wx(self):
        self._qualifier(
            UTILS_Stats_familles,
            UTILS_Stats_familles.Graphe_nombre_familles)

    def test_graphes_non_qualifies_restent_sur_gui(self):
        graphe = nouvelle_instance(
            UTILS_Stats_familles.Graphe_repartition_caisses)
        self.assertFalse(UTILS_Stats_graphes_worker.est_compatible(graphe))
        with self.assertRaises(ValueError):
            UTILS_Stats_graphes_worker.preparer(graphe, {}, "SQL_FICTIVE")

    def test_aucune_connexion_sans_source_explicitement_connue(self):
        objet = nouvelle_instance(
            UTILS_Stats_individus.Graphe_nombre_individus)
        with self.assertRaises(ValueError):
            UTILS_Stats_graphes_worker.preparer(objet, {}, None)

    def test_echec_graphique_ferme_connexion_sans_resultat_partiel(self):
        objet = nouvelle_instance(
            UTILS_Stats_individus.Graphe_nombre_individus)
        db = mock.Mock()
        with mock.patch.object(UTILS_Stats_graphes_worker.GestionDB, "DB",
                               return_value=db), \
             mock.patch.object(UTILS_Stats_individus, "GetComparatifNombre",
                               side_effect=RuntimeError("SQL fictif")):
            calcul = UTILS_Stats_graphes_worker.preparer(
                objet, {"periode": 2026}, "SQL_FICTIVE")
            with self.assertRaisesRegex(RuntimeError, "SQL fictif"):
                calcul()
        db.Close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
