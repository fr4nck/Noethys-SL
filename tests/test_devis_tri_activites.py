#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test de régression pour l'anomalie A : tri des activités dans la génération de devis.
Vérifie que le tri n'échoue pas quand des activités ont un nom NULL (jointure externe).
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def test_sort_avec_none():
    """Simule le tri des activités comme dans DLG_Impression_devis.Importation()"""
    listeActivites = [
        ("Natation", 1),
        (None, 0),  # jointure externe => nom NULL
        ("Danse", 2),
        ("Piscine", 3),
    ]

    # Avant correction : cela échouerait avec TypeError en Python 3
    # Après correction : le tri doit réussir
    try:
        listeActivites.sort(key=lambda x: (x[0] is None, x[0]))
        print("[OK] Tri reussi")
        print("      Resultat : " + str(listeActivites))
        # Vérifions que None est en dernier et le reste alphabétique
        assert listeActivites[-1] == (None, 0), "None devrait être en dernier"
        assert listeActivites[0][0] == "Danse", "Attendu 'Danse' en premier (tri alphabétique)"
        print("[OK] Ordre correct : noms alphabétiques, None en dernier")
        return True
    except TypeError as e:
        print("[FAIL] Tri échoué : " + str(e))
        return False

if __name__ == "__main__":
    success = test_sort_avec_none()
    sys.exit(0 if success else 1)
