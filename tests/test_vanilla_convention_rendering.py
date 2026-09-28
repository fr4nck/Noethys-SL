# -*- coding: utf-8 -*-
"""Rendu PDF d'une convention via le moteur Noedoc historique : premier
jalon vertical complet (fiche Famille -> modele categorie "convention"
-> prereplissage des champs -> PDF), sur un modele et des donnees
entierement fictifs et anonymises.

Verifie aussi, par contrat de source, qu'aucun texte d'article ni
aucune identite PMSL reelle n'est codee en dur dans le moteur Python.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
NOETHYS_DIR = TESTS_DIR.parent / "noethys"
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import wx  # noqa: E402

_APP = wx.App(False)

from _fixtures_noethys_db import (  # noqa: E402
    RedirectionGestionDB,
    creer_base_association_simple,
    inserer_modele_convention_fictif,
    inserer_modele_document,
)
from Utils import UTILS_Impression_convention as UIC  # noqa: E402
from reportlab.platypus import KeepTogether  # noqa: E402


def _AplatitStory(story):
    """ UIC._ConstruitStory regroupe le dernier objet flottant dans un
    KeepTogether (voir sa docstring) : cet utilitaire de test retrouve
    la liste à plat des Paragraph, quel que soit ce groupement. """
    liste = []
    for item in story:
        if isinstance(item, KeepTogether):
            liste.extend(item._content)
        else:
            liste.append(item)
    return liste


TEXTES_INTERDITS_DANS_LE_MOTEUR = (
    "ARTICLE 1", "ARTICLE 2", "ARTICLE 3", "ARTICLE 4", "ARTICLE 5", "ARTICLE 6",
    "PÊLE-MÊLE", "PELE-MELE", "Nelly ESTIER", "Groupama", "La Guerche",
)


class ContratSourceMoteurConventionTests(unittest.TestCase):
    """ Le moteur Python ne doit contenir ni texte d'article, ni identite
    PMSL : tout cela doit venir du modele .ndc et des donnees Noethys. """

    def test_aucun_texte_darticle_ni_identite_pmsl_dans_le_moteur(self):
        source = (NOETHYS_DIR / "Utils" / "UTILS_Impression_convention.py").read_text(encoding="utf-8")
        for texte_interdit in TEXTES_INTERDITS_DANS_LE_MOTEUR:
            self.assertNotIn(texte_interdit, source,
                              "%r ne doit pas etre code en dur dans le moteur" % texte_interdit)

    def test_module_ne_construit_plus_de_document_reportlab_dedie(self):
        """ Non-regression du refactor : plus de SimpleDocTemplate construit
        a la main avec une mise en page fixe par convention -- seul le
        moteur generique (BaseDocTemplate + Frame(cadre_principal)) est
        utilise. """
        source = (NOETHYS_DIR / "Utils" / "UTILS_Impression_convention.py").read_text(encoding="utf-8")
        self.assertNotIn("SimpleDocTemplate", source)
        self.assertIn("cadre_principal", source)
        self.assertIn("ModeleDoc", source)


class GenerationPDFConventionTests(unittest.TestCase):
    """ Premier jalon : fiche Famille -> choix modele "convention" ->
    periode -> prereplissage -> PDF via Noedoc, sur donnees fictives. """

    def test_pipeline_complet_association_produit_un_pdf_valide(self):
        with creer_base_association_simple() as base:
            IDmodele = inserer_modele_convention_fictif(base)
            chemin_pdf = tempfile.mktemp(suffix=".pdf")
            try:
                with RedirectionGestionDB(base.chemin):
                    resultat = UIC.Impression(
                        IDfamille=1, IDmodele=IDmodele,
                        date_debut="2026-09-01", date_fin="2026-09-30",
                        saison="2026-2027", listeIDindividus=[2, 3],
                        nomDoc=chemin_pdf, afficherDoc=False,
                    )
                self.assertIsInstance(resultat, dict, "la generation a echoue : %r" % (resultat,))
                self.assertTrue(os.path.isfile(chemin_pdf))
                self.assertGreater(os.path.getsize(chemin_pdf), 0)
                with open(chemin_pdf, "rb") as f:
                    self.assertTrue(f.read(5).startswith(b"%PDF-"))

                champs = resultat["champs"]
                self.assertEqual(champs["{CONVENTION_SAISON}"], "2026-2027")
                self.assertEqual(champs["{CONVENTION_TARIF_ADULTE}"], 36.5)
                self.assertEqual(champs["{CONVENTION_TARIF_ENFANT}"], 24.0)
                self.assertIn("Encadrement sportif enfants", champs["{CONVENTION_PLANNING_DETAIL}"])
            finally:
                if os.path.isfile(chemin_pdf):
                    os.remove(chemin_pdf)

    def test_IDfamille_manquant_leve_une_erreur_explicite(self):
        with self.assertRaises(ValueError):
            UIC.Impression(IDfamille=None, IDmodele=1)

    def test_IDmodele_manquant_leve_une_erreur_explicite(self):
        with self.assertRaises(ValueError):
            UIC.Impression(IDfamille=1, IDmodele=None)

    def test_texte_long_s_ecoule_automatiquement_sur_plusieurs_pages(self):
        """ Cas scolaire (ex. La Providence) : un corps de convention
        nettement plus long qu'une page doit se paginer automatiquement,
        via le meme mecanisme Frame/Platypus que les factures -- aucune
        pagination specifique aux conventions n'est ecrite ici. """
        import sys as _sys
        if str(NOETHYS_DIR) not in _sys.path:
            _sys.path.insert(0, str(NOETHYS_DIR))
        from Dlg import DLG_Noedoc
        from reportlab.platypus.doctemplate import BaseDocTemplate

        paragraphe = (
            "Ceci est un paragraphe fictif de test pour verifier que le "
            "texte long deborde correctement sur plusieurs pages sans "
            "etre coupe ni superpose. "
        ) * 6
        corps = "\n\n".join(
            "ARTICLE FICTIF %d\n%s" % (i, paragraphe) for i in range(1, 13)
        )

        with creer_base_association_simple() as base:
            IDmodele = inserer_modele_document(base, "Convention longue", "convention", [
                {"nom": "Cadre principal", "categorie": "special", "champ": "cadre_principal",
                 "ordre": 0, "x": 13, "y": 20, "largeur": 182, "hauteur": 250},
                {"nom": "Corps", "categorie": "bloc_texte", "ordre": 1,
                 "x": 13, "y": 20, "largeur": 182, "texte": corps},
            ])
            chemin_pdf = tempfile.mktemp(suffix=".pdf")
            try:
                with RedirectionGestionDB(base.chemin):
                    modeleDoc = DLG_Noedoc.ModeleDoc(IDmodele=IDmodele)
                    cadre, objetsFlottants = UIC._SepareObjetsFixesEtFlottants(modeleDoc)
                    story = UIC._ConstruitStory(modeleDoc, objetsFlottants, {})
                    doc = BaseDocTemplate(chemin_pdf, pagesize=UIC.TAILLE_PAGE)
                    doc.addPageTemplates([UIC._GabaritConvention(cadre, modeleDoc, {}, objetsFlottants)])
                    doc.build(story)
                    nb_pages = doc.page
                self.assertGreater(nb_pages, 1, "le texte long doit produire plusieurs pages")
                self.assertTrue(os.path.isfile(chemin_pdf))
                self.assertGreater(os.path.getsize(chemin_pdf), 0)
            finally:
                if os.path.isfile(chemin_pdf):
                    os.remove(chemin_pdf)

    def test_modele_sans_cadre_principal_echoue_proprement(self):
        """ Impression() affiche un wx.MessageDialog reel sur erreur : un
        vrai ShowModal() peut bloquer indefiniment sur un runner CI sans
        utilisateur interactif pour le fermer (constate : un job a
        realmenet bloque 19 minutes jusqu'au timeout avant ce correctif).
        On verifie donc le meme chemin de code (l'exception est bien
        levee par GenererPDF, capturee par Impression, qui renvoie False)
        sans jamais laisser un vrai ShowModal() s'executer. """
        with creer_base_association_simple() as base:
            IDmodele = inserer_modele_document(base, "Sans cadre", "convention", [
                {"nom": "Texte", "categorie": "bloc_texte", "ordre": 0, "x": 10, "y": 10, "texte": "Bonjour"},
            ])
            with RedirectionGestionDB(base.chemin):
                with unittest.mock.patch("wx.MessageDialog") as FauxMessageDialog:
                    FauxMessageDialog.return_value.ShowModal.return_value = wx.ID_OK
                    resultat = UIC.Impression(IDfamille=1, IDmodele=IDmodele, listeIDindividus=[2], afficherDoc=False)
        self.assertFalse(resultat)
        FauxMessageDialog.assert_called_once()
        FauxMessageDialog.return_value.ShowModal.assert_called_once()

    def test_ordre_des_blocs_flottants_suit_la_colonne_ordre_pas_l_insertion(self):
        """ Plusieurs blocs de texte dans le cadre principal : leur ordre
        de lecture (et donc l'ordre du "story" ReportLab) doit suivre
        exclusivement la colonne "ordre" des documents_objets -- celle
        que l'éditeur Noedoc réécrit selon l'ordre d'empilement (voir
        DLG_Noedoc.ModeleDoc.Sauvegarde, "ordre": index), pas l'ordre
        dans lequel les lignes ont été insérées en base, ni leur position
        géométrique. On insère volontairement les blocs dans un ordre
        d'insertion différent de leur "ordre" voulu pour le prouver. """
        import sys as _sys
        if str(NOETHYS_DIR) not in _sys.path:
            _sys.path.insert(0, str(NOETHYS_DIR))
        from Dlg import DLG_Noedoc

        with creer_base_association_simple() as base:
            IDmodele = inserer_modele_document(base, "Ordre blocs", "convention", [
                {"nom": "Cadre principal", "categorie": "special", "champ": "cadre_principal",
                 "ordre": 0, "x": 13, "y": 20, "largeur": 182, "hauteur": 250},
                # Insérés dans l'ordre C, A, B mais avec ordre=3/1/2 :
                # la lecture attendue est A (ordre=1), B (ordre=2), C (ordre=3).
                {"nom": "Bloc C", "categorie": "bloc_texte", "ordre": 3,
                 "x": 13, "y": 200, "largeur": 182, "texte": "Texte C"},
                {"nom": "Bloc A", "categorie": "bloc_texte", "ordre": 1,
                 "x": 13, "y": 100, "largeur": 182, "texte": "Texte A"},
                {"nom": "Bloc B", "categorie": "bloc_texte", "ordre": 2,
                 "x": 13, "y": 150, "largeur": 182, "texte": "Texte B"},
            ])
            with RedirectionGestionDB(base.chemin):
                modeleDoc = DLG_Noedoc.ModeleDoc(IDmodele=IDmodele)
                cadre, objetsFlottants = UIC._SepareObjetsFixesEtFlottants(modeleDoc)
                story = UIC._ConstruitStory(modeleDoc, objetsFlottants, {})

        self.assertEqual([o.nom for o in objetsFlottants], ["Bloc A", "Bloc B", "Bloc C"])
        self.assertEqual([p.text for p in _AplatitStory(story)], ["Texte A", "Texte B", "Texte C"])

    def test_ancien_modele_facture_reste_generable_par_le_meme_moteur_noedoc(self):
        """ Non-regression : le moteur Noedoc (DLG_Noedoc.ModeleDoc) reste
        utilisable pour une autre categorie apres l'ajout de Convention. """
        import sys as _sys
        if str(NOETHYS_DIR) not in _sys.path:
            _sys.path.insert(0, str(NOETHYS_DIR))
        from Dlg import DLG_Noedoc

        with creer_base_association_simple() as base:
            IDmodele = inserer_modele_document(base, "Facture test", "facture", [
                {
                    "nom": "Cadre principal", "categorie": "special", "champ": "cadre_principal",
                    "ordre": 0, "x": 13, "y": 20, "largeur": 182, "hauteur": 250,
                },
            ])
            with RedirectionGestionDB(base.chemin):
                modeleDoc = DLG_Noedoc.ModeleDoc(IDmodele=IDmodele)
        self.assertEqual(len(modeleDoc.listeObjets), 1)
        self.assertEqual(modeleDoc.listeObjets[0].categorie, "special")


if __name__ == "__main__":
    unittest.main()