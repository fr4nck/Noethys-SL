# -*- coding: utf-8 -*-
"""Recette du cycle de vie des modèles Noedoc de Convention."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

NOETHYS_DIR = TESTS_DIR.parent / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

from _fixtures_noethys_db import BaseTest, RedirectionGestionDB  # noqa: E402
import GestionDB  # noqa: E402
from Utils import UTILS_Convention_modeles  # noqa: E402


class GestionModelesConventionTests(unittest.TestCase):

    def test_installation_exemples_est_idempotente_et_inclut_scolaire(self):
        base = BaseTest()
        with RedirectionGestionDB(base.chemin):
            IDs1 = UTILS_Convention_modeles.InstallerModelesExemples()
            IDs2 = UTILS_Convention_modeles.InstallerModelesExemples()
            self.assertEqual(IDs1, IDs2)
            self.assertGreaterEqual(len(IDs1), 2)

            db = GestionDB.DB(nomFichier=base.chemin, suffixe=None)
            db.ExecuterReq("SELECT nom FROM documents_modeles WHERE categorie='convention' ORDER BY nom;")
            noms = [ligne[0].lower() for ligne in db.ResultatReq()]
            db.Close()
            self.assertTrue(any("scolaire" in nom for nom in noms), noms)

    def test_assurer_disponibles_n_ecrase_pas_un_modele_existant(self):
        base = BaseTest()
        with RedirectionGestionDB(base.chemin):
            db = GestionDB.DB(nomFichier=base.chemin, suffixe=None)
            IDmodele = db.ReqInsert("documents_modeles", [
                ("nom", "Mon modèle personnalisé"),
                ("categorie", "convention"),
                ("supprimable", 1),
                ("largeur", 210.0),
                ("hauteur", 297.0),
                ("observations", "perso"),
                ("IDfond", None),
                ("IDdonnee", None),
                ("defaut", 1),
            ])
            db.Close()

            IDs = UTILS_Convention_modeles.AssurerModelesDisponibles()
            self.assertEqual(IDs, [IDmodele])
            self.assertEqual(len(UTILS_Convention_modeles.GetModeles()), 1)

    def test_dupliquer_renommer_defaut_et_supprimer(self):
        base = BaseTest()
        with RedirectionGestionDB(base.chemin):
            IDs = UTILS_Convention_modeles.InstallerModelesExemples()
            source = IDs[0]
            UTILS_Convention_modeles.DefinirModeleDefaut(source)

            db = GestionDB.DB(nomFichier=base.chemin, suffixe=None)
            db.ExecuterReq("SELECT COUNT(*) FROM documents_objets WHERE IDmodele=%d;" % source)
            nb_objets_source = db.ResultatReq()[0][0]
            db.Close()

            copie = UTILS_Convention_modeles.DupliquerModele(source, "Convention de travail")
            self.assertNotEqual(copie, source)
            infos_copie = UTILS_Convention_modeles.GetModele(copie)
            self.assertEqual(infos_copie["nom"], "Convention de travail")
            self.assertEqual(infos_copie["defaut"], 0)
            self.assertEqual(infos_copie["supprimable"], 1)

            db = GestionDB.DB(nomFichier=base.chemin, suffixe=None)
            db.ExecuterReq("SELECT COUNT(*) FROM documents_objets WHERE IDmodele=%d;" % copie)
            nb_objets_copie = db.ResultatReq()[0][0]
            db.Close()
            self.assertEqual(nb_objets_copie, nb_objets_source)

            UTILS_Convention_modeles.RenommerModele(copie, "Convention personnalisée")
            self.assertEqual(UTILS_Convention_modeles.GetModele(copie)["nom"], "Convention personnalisée")

            UTILS_Convention_modeles.DefinirModeleDefaut(copie)
            modeles = UTILS_Convention_modeles.GetModeles()
            defaults = [m["IDmodele"] for m in modeles if m["defaut"]]
            self.assertEqual(defaults, [copie])

            UTILS_Convention_modeles.SupprimerModele(copie)
            self.assertIsNone(UTILS_Convention_modeles.GetModele(copie))
            db = GestionDB.DB(nomFichier=base.chemin, suffixe=None)
            db.ExecuterReq("SELECT COUNT(*) FROM documents_objets WHERE IDmodele=%d;" % copie)
            self.assertEqual(db.ResultatReq()[0][0], 0)
            db.Close()

            # La suppression du modèle par défaut doit laisser un défaut
            # cohérent parmi les modèles restants.
            self.assertEqual(sum(m["defaut"] for m in UTILS_Convention_modeles.GetModeles()), 1)

    def test_un_modele_protege_ne_peut_pas_etre_supprime(self):
        base = BaseTest()
        with RedirectionGestionDB(base.chemin):
            IDmodele = UTILS_Convention_modeles.InstallerModelesExemples()[0]
            db = GestionDB.DB(nomFichier=base.chemin, suffixe=None)
            db.ReqMAJ("documents_modeles", [("supprimable", 0)], "IDmodele", IDmodele)
            db.Close()

            with self.assertRaises(ValueError):
                UTILS_Convention_modeles.SupprimerModele(IDmodele)
            self.assertIsNotNone(UTILS_Convention_modeles.GetModele(IDmodele))


if __name__ == "__main__":
    unittest.main()
