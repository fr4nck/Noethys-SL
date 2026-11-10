# -*- coding: utf-8 -*-
"""UI-432K : deux factures Noedoc reelles, donnees SQLite fictives.

Le processus PDF source doit conserver la pagination du moteur historique.
Aucun SQL de production, aucun destinataire reel, aucun envoi.
"""
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for chemin in (ROOT, ROOT / "tests", ROOT / "noethys"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))

import _garde_reseau  # noqa: E402,F401


class PDFLotDeuxFamillesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import wx
        cls.app = wx.GetApp() or wx.App(False)

    def test_deux_factures_avec_prestations_diverses_et_bloc_texte(self):
        from _fixtures_noethys_db import RedirectionGestionDB, _DEFAUTS_OBJET
        from tests.test_vanilla_facture_prestation_sans_activite import (
            _creer_base_facture_avec_prestation_sans_activite,
            _dict_options_minimal,
        )
        from Utils import (
            UTILS_Facturation, UTILS_Impression_facture,
            UTILS_PDF_processus, UTILS_PDF_securise,
        )
        base, modele = _creer_base_facture_avec_prestation_sans_activite()
        try:
            base.inserer("familles", ["IDfamille"], [(2,)])
            base.inserer(
                "individus", ["IDindividu", "nom", "prenom", "IDcivilite"],
                [(3, "TEST", "Responsable", 1), (4, "TEST", "Enfant", 2)],
            )
            base.inserer(
                "rattachements",
                ["IDrattachement", "IDfamille", "IDindividu",
                 "IDcategorie", "titulaire"],
                [(3, 2, 3, 1, 1), (4, 2, 4, 2, 0)],
            )
            base.inserer(
                "comptes_payeurs", ["IDcompte_payeur", "IDfamille"], [(2, 2)],
            )
            base.inserer(
                "factures",
                ["IDfacture", "numero", "IDcompte_payeur", "date_edition",
                 "date_echeance", "activites", "individus", "IDutilisateur",
                 "date_debut", "date_fin", "total", "regle", "solde",
                 "prestations", "mention1", "mention2", "mention3"],
                [(2, 2, 2, "2026-09-30", "2026-10-31",
                  "10", "4", 1, "2026-09-01", "2026-09-30",
                  25.0, 25.0, 0.0, "consommation;cotisation", "", "", "")],
            )
            base.inserer(
                "prestations",
                ["IDprestation", "IDcompte_payeur", "date", "categorie", "label",
                 "montant_initial", "montant", "IDactivite", "IDfacture",
                 "IDfamille", "IDindividu"],
                [
                    (200, 2, "2026-09-02", "consommation", "Repas fictif",
                     5.0, 5.0, 10, 2, 2, 4),
                    (201, 2, "2026-09-01", "cotisation", "Cotisation fictive",
                     20.0, 20.0, None, 2, 2, 4),
                ],
            )
            objet = dict(_DEFAUTS_OBJET)
            objet.update({
                "IDmodele": modele, "nom": "Texte fictif",
                "categorie": "bloc_texte", "ordre": 1,
                "x": 22, "y": 235, "largeur": 115, "hauteur": 35,
                "texte": "Document de recette uniquement",
                "largeurTexte": 100,
            })
            base.db.ReqInsert("documents_objets", list(objet.items()))
            base.db.Commit()

            options = _dict_options_minimal(modele)
            with RedirectionGestionDB(base.chemin):
                facturation = UTILS_Facturation.Facturation()
                resultat = facturation.GetDonneesImpression(
                    listeFactures=[1, 2], dictOptions=options, parent=None)
            self.assertIsNot(resultat, False)
            comptes = resultat[0]

            with tempfile.TemporaryDirectory(prefix="ui432k-pdf-lot-") as dossier:
                original = str(Path(dossier) / "historique.pdf")
                isole = str(Path(dossier) / "processus.pdf")
                with RedirectionGestionDB(base.chemin):
                    UTILS_Impression_facture.Impression(
                        comptes, options, IDmodele=modele,
                        ouverture=False, nomFichier=original)

                comptes, options = UTILS_PDF_processus.Preparer(
                    comptes, options)
                with mock.patch.dict(os.environ, {
                    "NOETHYS_SL_PDF_TEST_ISOLE": "1"
                }):
                    UTILS_PDF_securise.Generer(
                        isole, lambda temporaire: UTILS_PDF_processus.Generer(
                            comptes, options, modele, temporaire, base.chemin,
                            delai=90, donnees_pretes=True))
                a, b = Path(original).read_bytes(), Path(isole).read_bytes()
                for pdf in (a, b):
                    self.assertTrue(pdf.startswith(b"%PDF-"))
                    self.assertIn(b"%%EOF", pdf[-2048:])
                pages = lambda pdf: len(
                    re.findall(rb"/Type\s*/Page\b", pdf))
                self.assertGreaterEqual(pages(a), 2)
                self.assertEqual(pages(a), pages(b))
                self.assertLess(
                    abs(len(a)-len(b)), max(2000, int(len(a)*0.10)))
                self.assertEqual(
                    sorted(os.listdir(dossier)),
                    ["historique.pdf", "processus.pdf"])
        finally:
            base.fermer()


if __name__ == "__main__":
    unittest.main()
