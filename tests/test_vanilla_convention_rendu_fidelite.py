# -*- coding: utf-8 -*-
"""Non-regression : fidelite du rendu Convention, suite a la recette
reelle Atout Sports.

1) Encodage : une chaine temoin accentuee/€ doit traverser sans
   alteration .ndc -> import -> DB -> GetValeur -> Paragraph, aussi bien
   comme texte litteral du modele que comme valeur substituee via
   {CHAMP}. Ceci prouve que le CODE (ImportationObjets, GetValeur,
   _ConstruitStory, UTILS_Export_documents) ne fait aucun encode/decode
   qui corromprait la chaine -- il ne prouve PAS l'absence de corruption
   d'octets deja stockes dans une ligne d'une vraie base MySQL (hors de
   portee sans acces a cette base ; voir le rapport joint pour le
   diagnostic complet).

2) Fidelite Noedoc : alignement, couleur de texte, fond, bordure,
   padding, interligne et soulignement reellement definis sur un objet
   Noedoc doivent se retrouver dans le ParagraphStyle ReportLab utilise
   pour le rendre. Un objet SANS ces proprietes ne doit dessiner ni
   bordure ni fond inventes.

3) Pagination : seul le DERNIER objet flottant reellement rendu est
   protege par KeepTogether (pour eviter qu'un bloc de signature court
   se retrouve seul en haut d'une page presque vide) ; les objets
   precedents, memes longs, restent libres de s'ecouler sur plusieurs
   pages.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
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
from Dlg import DLG_Noedoc  # noqa: E402
from Utils import UTILS_Export_documents  # noqa: E402
from Utils import UTILS_Impression_convention as UIC  # noqa: E402
from Utils import UTILS_Json  # noqa: E402
from reportlab.platypus import KeepTogether, Paragraph  # noqa: E402
from reportlab.lib.enums import TA_RIGHT  # noqa: E402


def _AplatitStory(story):
    """ UIC._ConstruitStory regroupe le dernier objet flottant dans un
    KeepTogether : cet utilitaire de test retrouve la liste à plat des
    Paragraph, quel que soit ce groupement. """
    liste = []
    for item in story:
        if isinstance(item, KeepTogether):
            liste.extend(item._content)
        else:
            liste.append(item)
    return liste


CHAINE_TEMOIN = u"é è à À ç œ € Présidente durée pédagogique responsabilité"


def _modele_temoin(base, texte):
    return inserer_modele_document(base, "Temoin encodage", "convention", [
        {"nom": "Cadre principal", "categorie": "special", "champ": "cadre_principal",
         "ordre": 0, "x": 13, "y": 20, "largeur": 182, "hauteur": 250},
        {"nom": "Corps", "categorie": "bloc_texte", "ordre": 1,
         "x": 13, "y": 20, "largeur": 182, "texte": texte},
    ])


class EncodageChaineTemoinTests(unittest.TestCase):
    def test_texte_litteral_du_modele_traverse_sans_alteration(self):
        with creer_base_association_simple() as base:
            IDmodele = _modele_temoin(base, CHAINE_TEMOIN)
            with RedirectionGestionDB(base.chemin):
                modeleDoc = DLG_Noedoc.ModeleDoc(IDmodele=IDmodele)
                objet = next(o for o in modeleDoc.listeObjets if o.nom == "Corps")
                # 1) tel que stocké/relu en base (ImportationObjets)
                self.assertEqual(objet.GetTexte(), CHAINE_TEMOIN)
                # 2) après résolution des {CHAMP}/[[SI ...]] (GetValeur)
                valeur = modeleDoc.GetValeur(objet, {})
                self.assertEqual(valeur, CHAINE_TEMOIN)
                # 3) après construction du "story" ReportLab (Paragraph)
                cadre, objetsFlottants = UIC._SepareObjetsFixesEtFlottants(modeleDoc)
                story = UIC._ConstruitStory(modeleDoc, objetsFlottants, {})
        paragraphes = _AplatitStory(story)
        self.assertEqual(paragraphes[0].text, CHAINE_TEMOIN)

    def test_valeur_substituee_via_champ_traverse_sans_alteration(self):
        with creer_base_association_simple() as base:
            IDmodele = _modele_temoin(base, "{TEMOIN}")
            with RedirectionGestionDB(base.chemin):
                modeleDoc = DLG_Noedoc.ModeleDoc(IDmodele=IDmodele)
                cadre, objetsFlottants = UIC._SepareObjetsFixesEtFlottants(modeleDoc)
                story = UIC._ConstruitStory(modeleDoc, objetsFlottants, {"{TEMOIN}": CHAINE_TEMOIN})
        paragraphes = _AplatitStory(story)
        self.assertEqual(paragraphes[0].text, CHAINE_TEMOIN)

    def test_survit_a_un_export_puis_import_ndc(self):
        """ Chaîne .ndc -> import -> DB -> GetValeur, exactement le
        parcours demandé. """
        with creer_base_association_simple() as base:
            IDmodeleSource = _modele_temoin(base, CHAINE_TEMOIN)
            chemin_ndc = tempfile.mktemp(suffix=".ndc")
            try:
                with RedirectionGestionDB(base.chemin):
                    UTILS_Export_documents.Exporter(IDmodele=IDmodeleSource, fichier=chemin_ndc)
                    IDmodeleImporte = UTILS_Export_documents.Importer(fichier=chemin_ndc)
                    modeleDoc = DLG_Noedoc.ModeleDoc(IDmodele=IDmodeleImporte)
                    objet = next(o for o in modeleDoc.listeObjets if o.nom == "Corps")
                    self.assertEqual(objet.GetTexte(), CHAINE_TEMOIN)
                    valeur = modeleDoc.GetValeur(objet, {})
                    self.assertEqual(valeur, CHAINE_TEMOIN)
            finally:
                if os.path.isfile(chemin_ndc):
                    os.remove(chemin_ndc)

    def test_utils_json_ecrire_lire_precise_lencodage_utf8(self):
        """ UTILS_Json.Ecrire()/Lire() ouvraient le fichier .ndc sans
        encoding= explicite (dépendant du locale OS par défaut). Sans
        conséquence tant que json.dump reste ensure_ascii=True (comme
        actuellement -- le fichier produit est alors intégralement en
        ASCII), mais un futur fichier .ndc contenant des octets non-ASCII
        littéraux (produit autrement que par Ecrire()) serait mal lu sur
        un poste dont le locale par défaut n'est pas UTF-8. Durci
        explicitement plutôt que de reposer sur ce détail d'implémentation. """
        chemin = tempfile.mktemp(suffix=".ndc")
        try:
            UTILS_Json.Ecrire(nom_fichier=chemin, data={"texte": CHAINE_TEMOIN})
            self.assertEqual(UTILS_Json.Lire(nom_fichier=chemin)["texte"], CHAINE_TEMOIN)
        finally:
            if os.path.isfile(chemin):
                os.remove(chemin)

    def test_modele_deja_mojibake_est_refuse_explicitement(self):
        with creer_base_association_simple() as base:
            IDmodele = _modele_temoin(base, u"TÃ©l. — ReprÃ©sentÃ©e")
            with RedirectionGestionDB(base.chemin):
                modeleDoc = DLG_Noedoc.ModeleDoc(IDmodele=IDmodele)
                _cadre, objetsFlottants = UIC._SepareObjetsFixesEtFlottants(modeleDoc)
                with self.assertRaisesRegex(ValueError, "mal encodé"):
                    UIC._ConstruitStory(modeleDoc, objetsFlottants, {})

    def test_symbole_euro_seul(self):
        with creer_base_association_simple() as base:
            IDmodele = _modele_temoin(base, u"Tarif : 24,00 €/h")
            with RedirectionGestionDB(base.chemin):
                modeleDoc = DLG_Noedoc.ModeleDoc(IDmodele=IDmodele)
                cadre, objetsFlottants = UIC._SepareObjetsFixesEtFlottants(modeleDoc)
                story = UIC._ConstruitStory(modeleDoc, objetsFlottants, {})
        self.assertEqual(_AplatitStory(story)[0].text, u"Tarif : 24,00 €/h")


class StyleNoedocRestitueTests(unittest.TestCase):
    def test_proprietes_definies_sont_restituees_dans_le_paragraphstyle(self):
        with creer_base_association_simple() as base:
            IDmodele = inserer_modele_document(base, "Style", "convention", [
                {"nom": "Cadre principal", "categorie": "special", "champ": "cadre_principal",
                 "ordre": 0, "x": 13, "y": 20, "largeur": 182, "hauteur": 250},
                {"nom": "Corps", "categorie": "bloc_texte", "ordre": 1,
                 "x": 13, "y": 20, "largeur": 182, "texte": "Texte stylisé",
                 "couleurTexte": "(200, 0, 0)", "couleurFond": "(255, 255, 0)",
                 "couleurTrait": "(0, 0, 200)", "epaissTrait": 0.5,
                 "padding": 3.0, "interligne": 2.0, "alignement": "right",
                 "soulignePolice": 1, "taillePolice": 10},
            ])
            with RedirectionGestionDB(base.chemin):
                modeleDoc = DLG_Noedoc.ModeleDoc(IDmodele=IDmodele)
                cadre, objetsFlottants = UIC._SepareObjetsFixesEtFlottants(modeleDoc)
                objet = objetsFlottants[0]
                style = UIC._StyleReportLab(objet)
                story = UIC._ConstruitStory(modeleDoc, objetsFlottants, {})

        self.assertEqual(style.alignment, TA_RIGHT)
        self.assertAlmostEqual(style.textColor.red, 200 / 255.0)
        self.assertAlmostEqual(style.backColor.red, 1.0)
        self.assertAlmostEqual(style.backColor.green, 1.0)
        self.assertAlmostEqual(style.borderColor.blue, 200 / 255.0)
        self.assertGreater(style.borderWidth, 0)
        self.assertGreater(style.borderPadding, 0)
        self.assertAlmostEqual(style.leading, 10 * 1.2 * 2.0)

        # Le soulignement s'applique via une balise <u> autour du texte
        # (ParagraphStyle n'a pas de propriété "souligné" globale).
        paragraphe = _AplatitStory(story)[0]
        self.assertIn("<u>", paragraphe.text)

    def test_nom_police_stocke_est_restaure_sur_objet_noedoc(self):
        with creer_base_association_simple() as base:
            IDmodele = inserer_modele_document(base, "Police stockée", "convention", [
                {"nom": "Cadre principal", "categorie": "special", "champ": "cadre_principal",
                 "ordre": 0, "x": 13, "y": 20, "largeur": 182, "hauteur": 250},
                {"nom": "Corps", "categorie": "bloc_texte", "ordre": 1,
                 "x": 13, "y": 20, "largeur": 182, "texte": "Police témoin",
                 "nomPolice": "Arial"},
            ])
            with RedirectionGestionDB(base.chemin):
                modeleDoc = DLG_Noedoc.ModeleDoc(IDmodele=IDmodele)
                objet = next(o for o in modeleDoc.listeObjets if o.nom == "Corps")
                self.assertEqual(objet.FaceName, "Arial")
                style = UIC._StyleReportLab(objet)
        self.assertEqual(style.fontName, "Arial")

    def test_proprietes_non_definies_ninventent_ni_bordure_ni_fond(self):
        """ Modèle fictif existant, sans couleurTrait/couleurFond définis
        (valeurs par défaut None) : aucune bordure ni fond ne doit être
        dessiné -- rien n'est inventé quand le modèle n'a rien défini. """
        with creer_base_association_simple() as base:
            IDmodele = inserer_modele_convention_fictif(base)
            with RedirectionGestionDB(base.chemin):
                modeleDoc = DLG_Noedoc.ModeleDoc(IDmodele=IDmodele)
                cadre, objetsFlottants = UIC._SepareObjetsFixesEtFlottants(modeleDoc)
                style = UIC._StyleReportLab(objetsFlottants[0])
        self.assertIsNone(style.backColor)
        self.assertIsNone(style.borderColor)
        self.assertEqual(style.borderWidth, 0)
        self.assertEqual(style.borderPadding, 0)


class PaginationDernierBlocProtegeTests(unittest.TestCase):
    def test_seul_le_dernier_bloc_est_dans_un_keeptogether(self):
        long_texte = "\n\n".join(["Paragraphe long numéro %d. " % i * 20 for i in range(1, 8)])
        with creer_base_association_simple() as base:
            IDmodele = inserer_modele_document(base, "Pagination", "convention", [
                {"nom": "Cadre principal", "categorie": "special", "champ": "cadre_principal",
                 "ordre": 0, "x": 13, "y": 20, "largeur": 182, "hauteur": 250},
                {"nom": "Corps", "categorie": "bloc_texte", "ordre": 1,
                 "x": 13, "y": 20, "largeur": 182, "texte": long_texte},
                {"nom": "Signature", "categorie": "bloc_texte", "ordre": 2,
                 "x": 13, "y": 20, "largeur": 182, "texte": "Fait le ...\n\nSignatures"},
            ])
            with RedirectionGestionDB(base.chemin):
                modeleDoc = DLG_Noedoc.ModeleDoc(IDmodele=IDmodele)
                cadre, objetsFlottants = UIC._SepareObjetsFixesEtFlottants(modeleDoc)
                story = UIC._ConstruitStory(modeleDoc, objetsFlottants, {})

        self.assertGreater(len(story), 1)
        for item in story[:-1]:
            self.assertIsInstance(item, Paragraph, "seul le dernier bloc doit être groupé")
        self.assertIsInstance(story[-1], KeepTogether)
        # Le bloc de signature protégé contient bien ses deux paragraphes.
        self.assertEqual(len(story[-1]._content), 2)

    def test_long_contenu_precedent_reste_libre_de_paginer(self):
        """ Non-régression explicite : un long article au milieu du
        document ne devient jamais "insécable" -- seul le tout dernier
        bloc l'est. Reprend le scénario déjà validé de pagination
        multipage (voir test_vanilla_convention_rendering.py). """
        import sys as _sys
        if str(NOETHYS_DIR) not in _sys.path:
            _sys.path.insert(0, str(NOETHYS_DIR))
        from reportlab.platypus.doctemplate import BaseDocTemplate

        paragraphe = (
            "Ceci est un paragraphe fictif de test pour vérifier que le "
            "texte long déborde correctement sur plusieurs pages. "
        ) * 6
        corps = "\n\n".join("ARTICLE FICTIF %d\n%s" % (i, paragraphe) for i in range(1, 13))

        with creer_base_association_simple() as base:
            IDmodele = inserer_modele_document(base, "Convention longue + signature", "convention", [
                {"nom": "Cadre principal", "categorie": "special", "champ": "cadre_principal",
                 "ordre": 0, "x": 13, "y": 20, "largeur": 182, "hauteur": 250},
                {"nom": "Corps", "categorie": "bloc_texte", "ordre": 1,
                 "x": 13, "y": 20, "largeur": 182, "texte": corps},
                {"nom": "Signature", "categorie": "bloc_texte", "ordre": 2,
                 "x": 13, "y": 20, "largeur": 182, "texte": "Fait le ...\n\nSignatures"},
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


if __name__ == "__main__":
    unittest.main()