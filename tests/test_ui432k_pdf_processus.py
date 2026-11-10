# -*- coding: utf-8 -*-
"""UI-432K : comparaison du vrai rendu Noedoc dans un processus isole.

Base SQLite de test uniquement. Aucune connexion PMSL, aucun email.
"""
import os
import re
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "tests", ROOT / "noethys"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import _garde_reseau  # noqa: E402,F401


class ProcessusNoedocTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import wx
        from tests.test_vanilla_facture_prestation_sans_activite import (
            _creer_base_facture_avec_prestation_sans_activite,
            _dict_options_minimal,
        )
        cls.app = wx.GetApp() or wx.App(False)
        cls.creer = staticmethod(_creer_base_facture_avec_prestation_sans_activite)
        cls.options_min = staticmethod(_dict_options_minimal)

    def setUp(self):
        self.base, self.modele = self.creer()
        self.addCleanup(self.base.fermer)
        self.options = self.options_min(self.modele)
        from _fixtures_noethys_db import RedirectionGestionDB
        from Utils import UTILS_Facturation
        with RedirectionGestionDB(self.base.chemin):
            facturation = UTILS_Facturation.Facturation()
            valeur = facturation.GetDonneesImpression(
                listeFactures=[1], dictOptions=self.options, parent=None)
        self.assertIsNot(valeur, False)
        self.comptes, _ = valeur

    def _verifier(self):
        from _fixtures_noethys_db import RedirectionGestionDB
        from Utils import UTILS_PDF_processus, UTILS_Impression_facture
        from Utils import UTILS_PDF_securise

        with tempfile.TemporaryDirectory(prefix="ui432k-render-test-") as dossier:
            ancien = str(Path(dossier) / "historique.pdf")
            nouveau = str(Path(dossier) / "processus.pdf")
            with RedirectionGestionDB(self.base.chemin):
                UTILS_Impression_facture.Impression(
                    self.comptes, self.options, IDmodele=self.modele,
                    ouverture=False, nomFichier=ancien)

            comptes, options = UTILS_PDF_processus.Preparer(
                self.comptes, self.options)
            with mock.patch.dict(os.environ, {
                "NOETHYS_SL_PDF_TEST_ISOLE": "1"
            }):
                UTILS_PDF_securise.Generer(
                    nouveau, lambda chemin: UTILS_PDF_processus.Generer(
                        comptes, options, self.modele, chemin,
                        self.base.chemin, delai=60, donnees_pretes=True))
            a, b = Path(ancien).read_bytes(), Path(nouveau).read_bytes()
            self.assertTrue(a.startswith(b"%PDF-"))
            self.assertTrue(b.startswith(b"%PDF-"))
            self.assertIn(b"%%EOF", a[-2048:])
            self.assertIn(b"%%EOF", b[-2048:])
            self.assertEqual(
                len(re.findall(rb"/Type\s*/Page\b", a)),
                len(re.findall(rb"/Type\s*/Page\b", b)))
            self.assertGreater(len(b), 900)
            self.assertLess(abs(len(a)-len(b)), max(2000,int(len(a)*0.10)))
            self.assertEqual(sorted(os.listdir(dossier)),
                             ["historique.pdf", "processus.pdf"])

    def test_facture_sqlite_minimale(self):
        self._verifier()

    def test_bloc_texte_noedoc_avec_wx_memorydc(self):
        from _fixtures_noethys_db import _DEFAUTS_OBJET
        objet = dict(_DEFAUTS_OBJET)
        objet.update({
            "IDmodele": self.modele, "nom": "Texte fictif",
            "categorie": "bloc_texte", "ordre": 1,
            "x": 22, "y": 235, "largeur": 115, "hauteur": 35,
            "texte": "Facture de test\nSans donnees utilisateur",
            "largeurTexte": 100,
        })
        self.base.db.ReqInsert("documents_objets", list(objet.items()))
        self.base.db.Commit()
        self._verifier()

    def test_source_manquante_refusee_sans_lancer_processus(self):
        from Utils import UTILS_PDF_processus
        with self.assertRaises(ValueError):
            UTILS_PDF_processus.Generer(
                self.comptes, self.options, self.modele,
                "facture.pdf", None, delai=10)

    def test_couleurs_devenues_tuples_pour_ipc(self):
        from Utils import UTILS_PDF_processus
        comptes, options = UTILS_PDF_processus.Preparer(
            self.comptes, self.options)
        self.assertIsInstance(options["couleur_fond_1"], tuple)
        self.assertEqual(len(options["couleur_fond_1"]), 3)
        self.assertEqual(set(comptes), set(self.comptes))


    def test_source_mysql_explicite_et_photos_ne_lisent_pas_le_profil(self):
        from Utils import UTILS_PDF_processus as pdf
        source = "3399;127.0.0.1;recette;motdepasse-fictif[RESEAU]zz_test_data"
        self.assertTrue(pdf.SourceCompatible(source))
        self.assertEqual(pdf._nom_base(source, "DATA"), source)
        self.assertEqual(
            pdf._nom_base(source, "PHOTOS"),
            source[:-5] + "_PHOTOS")
        self.assertFalse(pdf.SourceCompatible("3399;host;user[RESEAU]source_DATA"))
        self.assertFalse(pdf.SourceCompatible("3399;host;user;pw[RESEAU]autre"))
        with self.assertRaises(ValueError):
            pdf._nom_base("source-invalide[RESEAU]zz_test_data", "PHOTOS")

    def test_sources_sql_secondaires_fail_closed(self):
        from Utils import UTILS_PDF_processus
        chemin = self.base.chemin
        self.assertEqual(UTILS_PDF_processus._nom_base(chemin, "DATA"), chemin)
        self.assertEqual(UTILS_PDF_processus._nom_base(chemin, None), chemin)
        with self.assertRaises(ValueError):
            UTILS_PDF_processus._nom_base(chemin, "PHOTOS")
        with self.assertRaises(ValueError):
            UTILS_PDF_processus._nom_base(chemin, "ARCHIVE")
        self.assertEqual(UTILS_PDF_processus._nom_base(
            chemin.replace("test.dat", "test_DATA.dat"), "PHOTOS"),
            chemin.replace("test.dat", "test_PHOTOS.dat"))


if __name__ == "__main__":
    unittest.main()
