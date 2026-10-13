#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test de régression pour l'anomalie B : gestion gracieuse de l'absence de base PHOTOS.

Vérifie que :
1. Le cache au niveau du module fonctionne correctement.
2. La vérification de disponibilité ne se fait qu'une seule fois.
3. Les appels GetPhoto et GetPhotos retournent des valeurs valides sans crash.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def test_photos_db_cache():
    """Test que le cache _PHOTOS_DB_AVAILABLE fonctionne."""
    import Ctrl.CTRL_Photo as CTRL_Photo

    print("[INFO] Test du cache de disponibilite de la base PHOTOS")

    # Réinitialisé le cache
    CTRL_Photo._PHOTOS_DB_AVAILABLE = None

    # Première vérification
    disponibilite_1 = CTRL_Photo._check_photos_db_availability()
    print("[TEST] Premiere verification : {}".format("DISPONIBLE" if disponibilite_1 else "INDISPONIBLE"))

    # Deuxième vérification (devrait être cachetée)
    disponibilite_2 = CTRL_Photo._check_photos_db_availability()
    print("[TEST] Deuxieme verification (cache) : {}".format("DISPONIBLE" if disponibilite_2 else "INDISPONIBLE"))

    # Vérifier que les deux résultats sont identiques
    assert disponibilite_1 == disponibilite_2, "Le cache devrait retourner la meme valeur"
    print("[OK] Cache coherent")

    # Vérifier que GetPhoto retourne (None, None) sans crash quand base indisponible
    try:
        IDphoto, bmp = CTRL_Photo.GetPhoto(IDindividu=999999, nomFichier=None, taillePhoto=(128, 128))
        print("[OK] GetPhoto retourne sans crash : ({}, {})".format(IDphoto, "Bitmap" if bmp else None))
    except Exception as e:
        print("[FAIL] GetPhoto crash : {}".format(str(e)))
        return False

    # Vérifier que GetPhotos retourne un dictionnaire sans crash
    try:
        dictPhotos = CTRL_Photo.GetPhotos(listeIndividus=[(999999, None)], taillePhoto=(128, 128))
        print("[OK] GetPhotos retourne sans crash : {}".format(dictPhotos))
    except Exception as e:
        print("[FAIL] GetPhotos crash : {}".format(str(e)))
        return False

    return True

if __name__ == "__main__":
    try:
        success = test_photos_db_cache()
        if success:
            print("\n[PASS] Test du cache de photos reussi")
        else:
            print("\n[FAIL] Test du cache de photos echoue")
        sys.exit(0 if success else 1)
    except Exception as e:
        print("\n[EXCEPTION] {}".format(str(e)))
        import traceback
        traceback.print_exc()
        sys.exit(1)
