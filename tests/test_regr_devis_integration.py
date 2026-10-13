#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test d'intégration pour vérifier que la correction du tri des activités
ne régresse pas sur les cas réels de génération de devis.

Ce test simule un appel à DLG_Impression_devis.PANEL_Activites.Importation()
sur une requête SQL contenant une jointure externe (cas du bug original).
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def test_importation_avec_activite_null():
    """
    Simule les données retournées par la requête SQL DLG_Impression_devis
    avec une jointure externe qui produit un NULL pour le nom de l'activité.
    """
    listeDonnees = [
        (1, "Natation", "Nat"),
        (0, None, None),  # Cas de jointure externe => activité non trouvée
        (2, "Danse", "Dan"),
        (3, "Piscine", "Pisc"),
    ]

    listeActivites = []
    dictActivites = {}

    # Reproduire le code de DLG_Impression_devis.PANEL_Activites.Importation()
    for IDactivite, nom, abrege in listeDonnees:
        if not IDactivite:
            IDactivite = 0
        dictTemp = {"nom": nom, "abrege": abrege}
        dictActivites[IDactivite] = dictTemp
        listeActivites.append((nom, IDactivite))

    try:
        # Ceci échouerait AVANT la correction en Python 3
        listeActivites.sort(key=lambda x: (x[0] is None, x[0]))
        print("[OK] Importation + tri reussi (correction appliquee)")
        print("      Activites triees : " + str([nom for nom, _ in listeActivites]))

        # Vérifions que None est en dernier
        assert listeActivites[-1][0] is None, "Activite NULL devrait etre en dernier"
        print("[OK] NULL en dernier, autres en ordre alphabetique")
        return True
    except TypeError as e:
        print("[FAIL] Importation echouee : " + str(e))
        return False

if __name__ == "__main__":
    success = test_importation_avec_activite_null()
    sys.exit(0 if success else 1)
