#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test de régression pour l'anomalie C : accumulation de pièces jointes.

Vérifie que le code réel de production (OL_Pieces_jointes_emails.ListView.SetFichiers)
remplace correctement la liste au lieu de l'accumuler.

Test de régression : Si SetFichiers ajoute au lieu de remplacer, deux appels
consécutifs avec des listes différentes causent une accumulation.

Symptôme observé : Deuxième envoi d'attestation contient deux PJ au lieu d'une.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import du module réel de production
from noethys.Ol import OL_Pieces_jointes_emails


class TestPiecesJointesAccumulation(unittest.TestCase):
    """Tests de régression pour l'accumulation de pièces jointes (anomalie C)."""

    def setUp(self):
        """Créer une instance réelle du contrôle ListView pour chaque test."""
        # Créer un fake wx.Frame minimal pour le parent
        import wx
        self.app = wx.App(False)
        self.parent = wx.Frame(None)

        # Créer le contrôle réel de production
        self.listview = OL_Pieces_jointes_emails.ListView(
            self.parent, id=-1,
            style=wx.LC_NO_HEADER|wx.LC_REPORT|wx.SUNKEN_BORDER|wx.LC_SINGLE_SEL|wx.LC_HRULES|wx.LC_VRULES
        )

    def tearDown(self):
        """Nettoyer après chaque test."""
        self.parent.Destroy()

    def test_set_fichiers_remplace_pas_accumule(self):
        """SetFichiers doit remplacer la liste, pas l'accumuler.

        Test de régression : Avant correction, SetFichiers faisait append()
        au lieu de remplacer, causant l'accumulation.
        """
        # Premier appel
        self.listview.SetFichiers(["fichier1.pdf"])
        self.assertEqual(len(self.listview.listeDonnees), 1,
                        "Après premier SetFichiers, doit avoir 1 fichier")
        self.assertEqual(self.listview.listeDonnees[0], "fichier1.pdf")

        # Deuxième appel avec un fichier différent
        self.listview.SetFichiers(["fichier2.pdf"])
        self.assertEqual(len(self.listview.listeDonnees), 1,
                        "Après deuxième SetFichiers, doit avoir 1 fichier, pas 2 (pas d'accumulation)")
        self.assertEqual(self.listview.listeDonnees[0], "fichier2.pdf",
                        "Fichier 1 doit être remplacé par fichier 2")
        self.assertNotIn("fichier1.pdf", self.listview.listeDonnees,
                        "Fichier 1 ne doit pas rester après remplacement")

    def test_set_fichiers_multiple_replacements(self):
        """Plusieurs appels SetFichiers consécutifs doivent fonctionner.

        Simule l'envoi de plusieurs attestations d'affilée avec des PJ différentes.
        """
        # Envoi 1 : une attestation
        self.listview.SetFichiers(["attestation_arthure_2026.pdf"])
        self.assertEqual(len(self.listview.listeDonnees), 1)

        # Envoi 2 : une autre attestation
        self.listview.SetFichiers(["attestation_lina_2026.pdf"])
        self.assertEqual(len(self.listview.listeDonnees), 1,
                        "Envoi 2 : doit avoir 1 fichier uniquement")
        self.assertIn("attestation_lina_2026.pdf", self.listview.listeDonnees)
        self.assertNotIn("attestation_arthure_2026.pdf", self.listview.listeDonnees,
                        "PJ d'Arthur ne doit pas être présente dans envoi de Lina")

        # Envoi 3 : deux attestations pour une famille
        self.listview.SetFichiers(["attestation_chlooe_2026.pdf", "attestation_marie_2026.pdf"])
        self.assertEqual(len(self.listview.listeDonnees), 2,
                        "Envoi 3 : doit avoir 2 fichiers")

        # Envoi 4 : retour à une seule attestation
        self.listview.SetFichiers(["attestation_yannick_2026.pdf"])
        self.assertEqual(len(self.listview.listeDonnees), 1,
                        "Envoi 4 : doit avoir 1 fichier, pas 3")
        self.assertIn("attestation_yannick_2026.pdf", self.listview.listeDonnees)

    def test_set_fichiers_liste_vide(self):
        """SetFichiers avec une liste vide doit vider la liste existante."""
        # Ajouter des fichiers
        self.listview.SetFichiers(["file1.pdf", "file2.pdf"])
        self.assertEqual(len(self.listview.listeDonnees), 2)

        # Vider la liste
        self.listview.SetFichiers([])
        self.assertEqual(len(self.listview.listeDonnees), 0,
                        "SetFichiers([]) doit vider la liste")

    def test_aucun_melange_entre_familles(self):
        """Pièces jointes d'une famille ne doivent pas apparaître dans une autre.

        Test de régression : La symptomatologie reportée suggérait que des PJ
        d'une famille pouvaient apparaître dans l'envoi d'une autre.
        """
        # Envoi famille 1
        self.listview.SetFichiers(["famille_1_attestation.pdf"])
        self.assertEqual(self.listview.listeDonnees, ["famille_1_attestation.pdf"])

        # Envoi famille 2
        self.listview.SetFichiers(["famille_2_attestation.pdf"])
        self.assertEqual(len(self.listview.listeDonnees), 1,
                        "Doit avoir une seule PJ après SetFichiers sur famille 2")
        self.assertEqual(self.listview.listeDonnees[0], "famille_2_attestation.pdf")
        self.assertNotIn("famille_1_attestation.pdf", self.listview.listeDonnees,
                        "PJ famille 1 ne doit pas être dans envoi famille 2")


if __name__ == "__main__":
    # Exécuter les tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPiecesJointesAccumulation)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Retourner le code d'exit approprié
    sys.exit(0 if result.wasSuccessful() else 1)
