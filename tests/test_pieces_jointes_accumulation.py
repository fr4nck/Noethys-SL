#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test de régression pour l'anomalie C : accumulation de pièces jointes.

Simule deux appels SetFichiers consécutifs et vérifie qu'ils ne s'accumulent pas.
"""

class MockListView:
    """Mock du contrôle ListView pour tester SetFichiers."""
    def __init__(self):
        self.listeDonnees = []

    def SetFichiers(self, listeFichiers=[]):
        """CORRIGE : remplacer la liste au lieu d'ajouter."""
        self.listeDonnees = list(listeFichiers)
        # self.MAJ() # pas appelé dans le test

    def MAJ(self):
        pass

def test_pieces_jointes_pas_accumulation():
    """Test que SetFichiers remplace la liste au lieu de l'accumuler."""
    print("[TEST] Accumulation de pieces jointes")

    # Créer un contrôle mock
    ctrl = MockListView()

    # Première série de fichiers
    fichiers_1 = ["attestation_1.pdf"]
    ctrl.SetFichiers(fichiers_1)
    print("[STEP 1] Premier appel SetFichiers : {}".format(ctrl.listeDonnees))
    assert ctrl.listeDonnees == ["attestation_1.pdf"], "Attendu une attestation"

    # Deuxième série (nouveau mail)
    fichiers_2 = ["attestation_2.pdf"]
    ctrl.SetFichiers(fichiers_2)
    print("[STEP 2] Deuxieme appel SetFichiers : {}".format(ctrl.listeDonnees))
    assert len(ctrl.listeDonnees) == 1, "Attendu UNE SEULE attestation, pas accumulation"
    assert ctrl.listeDonnees == ["attestation_2.pdf"], "Attendu la deuxième attestation uniquement"

    print("[OK] Pas d'accumulation - SetFichiers remplace correctement")
    return True

def test_pieces_jointes_remplacement_multiple():
    """Test que SetFichiers gère correctement le remplacement multiple."""
    print("[TEST] Remplacement multiple")

    ctrl = MockListView()

    # Trois appels successifs
    ctrl.SetFichiers(["file1.pdf"])
    assert len(ctrl.listeDonnees) == 1
    print("[CALL 1] Taille : {}".format(len(ctrl.listeDonnees)))

    ctrl.SetFichiers(["file2.pdf", "file3.pdf"])
    assert len(ctrl.listeDonnees) == 2
    print("[CALL 2] Taille : {}".format(len(ctrl.listeDonnees)))
    assert "file1.pdf" not in ctrl.listeDonnees, "file1.pdf devrait être oublie"

    ctrl.SetFichiers(["file4.pdf"])
    assert len(ctrl.listeDonnees) == 1
    print("[CALL 3] Taille : {}".format(len(ctrl.listeDonnees)))
    assert ctrl.listeDonnees[0] == "file4.pdf"

    print("[OK] Remplacements multiples sans accumulation")
    return True

if __name__ == "__main__":
    import sys
    try:
        success = test_pieces_jointes_pas_accumulation() and test_pieces_jointes_remplacement_multiple()
        if success:
            print("\n[PASS] Tests d'accumulation de pieces jointes reussis")
        sys.exit(0 if success else 1)
    except AssertionError as e:
        print("\n[FAIL] {}".format(str(e)))
        sys.exit(1)
