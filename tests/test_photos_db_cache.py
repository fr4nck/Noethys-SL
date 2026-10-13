#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test de régression pour l'anomalie B : gestion gracieuse de l'absence de base PHOTOS.

Vérifie que le code réel de production gère correctement l'absence de base PHOTOS
en utilisant un cache au niveau du module.

Tests :
1. Le cache mémorise la disponibilité après une seule tentative
2. GetPhoto ne crash pas quand base indisponible
3. GetPhotos ne crash pas quand base indisponible
4. Le fallback vers images par défaut fonctionne
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import du module réel de production (noethys.Ctrl, pas Ctrl)
from noethys.Ctrl import CTRL_Photo


class TestPhotosCacheRegression(unittest.TestCase):
    """Tests de régression pour le cache PHOTOS (anomalie B)."""

    def setUp(self):
        """Réinitialiser le cache avant chaque test pour isolation."""
        CTRL_Photo._PHOTOS_DB_AVAILABLE = None

    def test_cache_memorisation(self):
        """Le cache doit mémoriser la disponibilité après une seule tentative.

        Test de régression : Si le cache n'est pas utilisé, chaque appel
        tenterait de reconnecter à la base PHOTOS, générant une erreur MySQL 1049.
        """
        # Première vérification
        dispo_1 = CTRL_Photo._check_photos_db_availability()

        # Deuxième vérification (devrait être cachetée, pas recalculée)
        dispo_2 = CTRL_Photo._check_photos_db_availability()

        # Les deux doivent être identiques (cache cohérent)
        self.assertEqual(dispo_1, dispo_2,
                        "Cache incohérent : deux vérifications doivent retourner la même valeur")

        # Vérifier que le cache est effectivement défini
        self.assertIsNotNone(CTRL_Photo._PHOTOS_DB_AVAILABLE,
                           "Cache devrait être défini après première vérification")

    def test_get_photo_sans_crash_base_indisponible(self):
        """GetPhoto ne doit pas crasher quand base PHOTOS indisponible.

        Test de régression : Avant correction, GetPhoto tentait une connexion
        directe à la base PHOTOS et déclenchait MySQL 1049.
        """
        # Forcer la base à indisponible (pour tester le code réel sans base)
        CTRL_Photo._PHOTOS_DB_AVAILABLE = False

        # Appel qui doit retourner (None, None) sans crash
        try:
            result = CTRL_Photo.GetPhoto(IDindividu=999999, nomFichier=None)
            self.assertIsNotNone(result)
            # Résultat attendu quand pas de photo : (None, None)
            self.assertEqual(result, (None, None))
        except Exception as e:
            self.fail("GetPhoto crash avec base indisponible: {}".format(str(e)))

    def test_get_photos_sans_crash_base_indisponible(self):
        """GetPhotos ne doit pas crasher quand base PHOTOS indisponible.

        Test de régression : Avant correction, GetPhotos tentait une connexion
        directe et déclenchait MySQL 1049 à chaque appel.
        """
        # Forcer la base à indisponible
        CTRL_Photo._PHOTOS_DB_AVAILABLE = False

        # Appel qui doit retourner un dictionnaire sans crash
        try:
            result = CTRL_Photo.GetPhotos(listeIndividus=[(999999, None)], taillePhoto=(128, 128))
            self.assertIsInstance(result, dict, "GetPhotos doit retourner un dictionnaire")
            # Vérifier que l'individu est présent dans le résultat
            self.assertIn(999999, result)
        except Exception as e:
            self.fail("GetPhotos crash avec base indisponible: {}".format(str(e)))

    def test_cache_persiste_entre_appels(self):
        """Le cache persiste entre plusieurs appels successifs.

        Test de régression : Si le cache n'existait pas, chaque appel
        recalculerait, causant des tentatives répétées.
        """
        # Première tentative
        CTRL_Photo._check_photos_db_availability()
        cache_value_1 = CTRL_Photo._PHOTOS_DB_AVAILABLE

        # Plusieurs appels successifs
        for _ in range(5):
            CTRL_Photo.GetPhoto(IDindividu=999999)
            CTRL_Photo.GetPhotos(listeIndividus=[(999999, None)])

        # Le cache ne doit pas changer
        cache_value_2 = CTRL_Photo._PHOTOS_DB_AVAILABLE
        self.assertEqual(cache_value_1, cache_value_2,
                        "Cache ne doit pas changer après plusieurs appels")


if __name__ == "__main__":
    # Exécuter les tests avec unittest
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPhotosCacheRegression)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Retourner le code d'exit approprié
    sys.exit(0 if result.wasSuccessful() else 1)
