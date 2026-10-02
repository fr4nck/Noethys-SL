# -*- coding: utf-8 -*-
"""Non-régression : édition PDF d'une facture comportant, pour un même
individu, à la fois une prestation rattachée à une activité et une
prestation SANS activité (IDactivite NULL en base -- ex. une cotisation ou
des frais divers facturés à l'individu mais non rattachés à un créneau).

Défaut réel (recette) : "Désolé, le problème suivant a été rencontré dans
l'édition des factures : \n\n'<' not supported between instances of
'NoneType' and 'str'" lors de l'édition d'une facture acquittée en PDF
avec envoi par email.

Cause racine confirmée par traceback réel :
  UTILS_Facturation.py:1219, in Impression
    UTILS_Impression_facture.Impression(...)
  UTILS_Impression_facture.py:398, in __init__
    listeIDactivite.sort()
  TypeError: '<' not supported between instances of 'NoneType' and 'str'

Origine de chaque valeur ajoutée à listeIDactivite (UTILS_Facturation.py) :
- la requête SQL de GetDonnees() (~L206-220) sélectionne activites.nom via
  LEFT JOIN activites ON prestations.IDactivite = activites.IDactivite, et
  inclut EXPLICITEMENT les prestations où IDactivite IS NULL (~L201) --
  c'est un cas prévu, pas accidentel (prestation "diverse", non rattachée
  à une activité, ex. cotisation) ;
- ~L606-607 : IDactivite==None est normalisé à la clé de regroupement 0 ;
- ~L644 : texteActivite = nomActivite -- reste None pour ce panier ;
- ~L648-649 : stocké tel quel dans
  dictComptes[ID]["individus"][IDindividu]["activites"][0]["texte"].

En aval (UTILS_Impression_facture.py:403), "if texteActivite != None"
prouve que ce None est un signal INTENTIONNEL (ne pas afficher d'en-tête
d'activité pour ce panier) -- ce n'est donc jamais une donnée corrompue à
filtrer ou à remplacer arbitrairement, seulement une clé de tri à traiter
explicitement. listeIDactivite ne sert QUE pour l'ordre d'affichage des
blocs activité d'un individu (vérifié : aucune requête ni logique métier
ultérieure ne la réutilise).

Aucun envoi d'email réel : ce test n'exerce que la génération du PDF
(UTILS_Impression_facture.Impression), jamais UTILS_Envoi_email. Le mode
"facture acquittée" observé en recette correspond à l'option d'affichage
"afficher_reglements" (période intégralement réglée) ; le défaut est
cependant indépendant de cette option -- il touche tout individu combinant
une prestation liée à une activité et une prestation sans activité sur la
même facture, avec ou sans "afficher_reglements".
"""
from __future__ import annotations

import datetime
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
NOETHYS_DIR = TESTS_DIR.parent / "noethys"
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

import wx  # noqa: E402

_APP = wx.App(False)

from _fixtures_noethys_db import (  # noqa: E402
    BaseTest,
    RedirectionGestionDB,
    inserer_modele_document,
)
from Data import DATA_Tables as Tables  # noqa: E402


TABLES_FACTURATION_SUPPLEMENTAIRES = (
    "comptes_payeurs", "factures", "factures_prefixes", "lots_factures",
    "tarifs", "noms_tarifs", "categories_tarifs",
    "ventilation", "reglements", "modes_reglements", "emetteurs", "payeurs",
    "quotients", "messages",
    "prelevements", "lots_prelevements", "comptes_bancaires",
    "pes_pieces", "pes_lots",
)


def _creer_base_facture_avec_prestation_sans_activite():
    """ Une famille, un enfant, une facture avec DEUX prestations pour le
    même enfant : l'une liée à une activité réelle ("Cantine", str), l'autre
    sans activité (IDactivite NULL -- ex. cotisation, montant fixe non lié
    à un créneau). Structure minimale mais réelle (vraies tables, vraie
    requête SQL), pas un dict construit à la main. """
    base = BaseTest()
    for nom_table in TABLES_FACTURATION_SUPPLEMENTAIRES:
        base.db.CreationTable(nom_table, dicoDB=Tables.DB_DATA)
    base.db.Commit()

    base.inserer(
        "organisateur",
        ["IDorganisateur", "nom", "rue", "cp", "ville", "tel", "fax", "mail", "site", "num_agrement", "num_siret", "code_ape"],
        [(1, "Association Test Loisirs", "1 rue des Tests", "00000", "Testville", "", "", "test@example.org", "", "", "", "")],
    )
    base.inserer("familles", ["IDfamille"], [(1,)])
    base.inserer(
        "individus",
        ["IDindividu", "nom", "prenom", "IDcivilite"],
        [(1, "MARTIN", "Alice", 1), (2, "MARTIN", "Bob", 2)],
    )
    base.inserer(
        "rattachements",
        ["IDrattachement", "IDfamille", "IDindividu", "IDcategorie", "titulaire"],
        [(1, 1, 1, 1, 1), (2, 1, 2, 2, 0)],
    )
    base.inserer("comptes_payeurs", ["IDcompte_payeur", "IDfamille"], [(1, 1)])
    base.inserer("activites", ["IDactivite", "nom"], [(10, "Cantine")])

    base.inserer(
        "factures",
        ["IDfacture", "numero", "IDcompte_payeur", "date_edition", "date_echeance",
         "activites", "individus", "IDutilisateur", "date_debut", "date_fin",
         "total", "regle", "solde", "prestations", "mention1", "mention2", "mention3"],
        [(1, 1, 1, "2026-09-30", "2026-10-31",
          "10", "2", 1, "2026-09-01", "2026-09-30",
          25.0, 25.0, 0.0, "consommation;cotisation", "", "", "")],
    )

    base.inserer(
        "prestations",
        ["IDprestation", "IDcompte_payeur", "date", "categorie", "label",
         "montant_initial", "montant", "IDactivite", "IDfacture", "IDfamille", "IDindividu"],
        [
            # Prestation liée à une activité réelle -> texte = "Cantine" (str)
            (100, 1, "2026-09-02", "consommation", "Repas", 5.0, 5.0, 10, 1, 1, 2),
            # Prestation SANS activité (IDactivite NULL) pour le MÊME individu
            # -> texte = None (cas réel, ex. cotisation/frais divers)
            (101, 1, "2026-09-01", "cotisation", "Cotisation annuelle", 20.0, 20.0, None, 1, 1, 2),
        ],
    )

    IDmodele = inserer_modele_document(
        base, "Facture de test", "facture",
        [{
            "nom": "Cadre principal", "categorie": "special", "champ": "cadre_principal",
            "ordre": 0, "x": 13, "y": 20, "largeur": 182, "hauteur": 250,
        }],
    )
    return base, IDmodele


def _dict_options_minimal(IDmodele):
    """ Reflète les valeurs par défaut réelles déclarées dans
    Ctrl/CTRL_Factures_options.py (pas des valeurs arbitraires). Les
    options d'affichage additionnelles (règlements, coupon, prélèvements...)
    sont désactivées : le défaut ne dépend d'aucune d'elles (voir docstring
    du module), les désactiver isole le test sur la cause réelle. """
    return {
        "IDmodele": IDmodele,
        "affichage_solde": 0,
        "afficher_impayes": False,
        "integrer_impayes": False,
        "afficher_coupon_reponse": False,
        "afficher_messages": False,
        "messages": [],
        "afficher_codes_barres": False,
        "afficher_reglements": False,
        "afficher_avis_prelevements": False,
        "afficher_qf_dates": False,
        "afficher_classes": False,
        "afficher_titre": True,
        "texte_titre": "Facture",
        "taille_texte_titre": 19,
        "afficher_periode": True,
        "taille_texte_periode": 8,
        "affichage_prestations": 0,
        "intitules": 0,
        "afficher_sous_total_activite": False,
        "couleur_fond_1": wx.Colour(204, 204, 255),
        "couleur_fond_2": wx.Colour(234, 234, 255),
        "largeur_colonne_date": 50,
        "largeur_colonne_montant_ht": 50,
        "largeur_colonne_montant_tva": 50,
        "largeur_colonne_montant_ttc": 70,
        "taille_texte_individu": 9,
        "taille_texte_activite": 6,
        "taille_texte_noms_colonnes": 5,
        "taille_texte_prestation": 7,
        "taille_texte_messages": 7,
        "taille_texte_labels_totaux": 9,
        "taille_texte_montants_totaux": 10,
        "taille_texte_prestations_anterieures": 5,
        "texte_prestations_anterieures": "Des prestations antérieures ont été reportées sur cette facture.",
        "texte_introduction": "",
        "taille_texte_introduction": 9,
        "style_texte_introduction": 0,
        "couleur_fond_introduction": wx.Colour(255, 255, 255),
        "couleur_bord_introduction": wx.Colour(255, 255, 255),
        "alignement_texte_introduction": 0,
        "texte_conclusion": "",
        "taille_texte_conclusion": 9,
        "style_texte_conclusion": 0,
        "couleur_fond_conclusion": wx.Colour(255, 255, 255),
        "couleur_bord_conclusion": wx.Colour(255, 255, 255),
        "alignement_texte_conclusion": 0,
        "image_signature": "",
        "taille_image_signature": 100,
        "alignement_image_signature": 0,
    }


class FacturePrestationSansActiviteTests(unittest.TestCase):
    def _generer_pdf(self):
        from Utils import UTILS_Facturation

        base, IDmodele = _creer_base_facture_avec_prestation_sans_activite()
        dictOptions = _dict_options_minimal(IDmodele)

        with RedirectionGestionDB(base.chemin):
            facturation = UTILS_Facturation.Facturation()
            with tempfile.TemporaryDirectory() as tmp:
                nomDoc = str(Path(tmp) / "facture_test.pdf")
                resultat = facturation.Impression(
                    listeFactures=[1], nomDoc=nomDoc, afficherDoc=False,
                    dictOptions=dictOptions, afficherOptions=False,
                )
                if resultat is not False:
                    self.assertTrue(Path(nomDoc).is_file())
                    self.assertGreater(Path(nomDoc).stat().st_size, 0)
                return resultat

    def test_facture_standard_activite_seule_fonctionne(self):
        """ Témoin : une facture dont l'individu n'a QUE des prestations
        liées à une activité (aucun None) doit toujours fonctionner --
        preuve que le correctif ne casse pas le cas courant. """
        from Utils import UTILS_Facturation

        base, IDmodele = _creer_base_facture_avec_prestation_sans_activite()
        # Supprime la prestation sans activité : il ne reste que la Cantine.
        base.db.ExecuterReq("DELETE FROM prestations WHERE IDprestation=101;")
        base.db.Commit()
        dictOptions = _dict_options_minimal(IDmodele)

        with RedirectionGestionDB(base.chemin):
            facturation = UTILS_Facturation.Facturation()
            with tempfile.TemporaryDirectory() as tmp:
                nomDoc = str(Path(tmp) / "facture_test.pdf")
                resultat = facturation.Impression(
                    listeFactures=[1], nomDoc=nomDoc, afficherDoc=False,
                    dictOptions=dictOptions, afficherOptions=False,
                )
                self.assertIsNot(resultat, False)
                self.assertTrue(Path(nomDoc).is_file())

    def test_facture_avec_prestation_sans_activite_ne_leve_plus_typeerror(self):
        """ Reproduit EXACTEMENT le cas réel : un individu avec une
        prestation liée à une activité (str) ET une prestation sans
        activité (None) sur la même facture. Avant le correctif, ceci
        levait TypeError('<' not supported between instances of
        'NoneType' and 'str') dans listeIDactivite.sort(). """
        resultat = self._generer_pdf()
        self.assertIsNot(resultat, False, "L'édition de la facture ne doit plus échouer")

    def test_lot_de_deux_factures_avec_et_sans_activite(self):
        """ Édition d'un LOT (plusieurs factures en une seule passe, comme
        le fait réellement Facturation.Impression avec plusieurs
        IDfacture) : le correctif doit s'appliquer pour chaque facture du
        lot, pas seulement pour un cas isolé. """
        from Utils import UTILS_Facturation

        base, IDmodele = _creer_base_facture_avec_prestation_sans_activite()
        # Deuxième famille/facture, avec la même combinaison activité + sans-activité.
        base.inserer("familles", ["IDfamille"], [(2,)])
        base.inserer(
            "individus",
            ["IDindividu", "nom", "prenom", "IDcivilite"],
            [(3, "DURAND", "Chloe", 1), (4, "DURAND", "Eli", 2)],
        )
        base.inserer(
            "rattachements",
            ["IDrattachement", "IDfamille", "IDindividu", "IDcategorie", "titulaire"],
            [(3, 2, 3, 1, 1), (4, 2, 4, 2, 0)],
        )
        base.inserer("comptes_payeurs", ["IDcompte_payeur", "IDfamille"], [(2, 2)])
        base.inserer(
            "factures",
            ["IDfacture", "numero", "IDcompte_payeur", "date_edition", "date_echeance",
             "activites", "individus", "IDutilisateur", "date_debut", "date_fin",
             "total", "regle", "solde", "prestations", "mention1", "mention2", "mention3"],
            [(2, 2, 2, "2026-09-30", "2026-10-31",
              "10", "4", 1, "2026-09-01", "2026-09-30",
              25.0, 25.0, 0.0, "consommation;cotisation", "", "", "")],
        )
        base.inserer(
            "prestations",
            ["IDprestation", "IDcompte_payeur", "date", "categorie", "label",
             "montant_initial", "montant", "IDactivite", "IDfacture", "IDfamille", "IDindividu"],
            [
                (200, 2, "2026-09-02", "consommation", "Repas", 5.0, 5.0, 10, 2, 2, 4),
                (201, 2, "2026-09-01", "cotisation", "Cotisation annuelle", 20.0, 20.0, None, 2, 2, 4),
            ],
        )

        dictOptions = _dict_options_minimal(IDmodele)
        with RedirectionGestionDB(base.chemin):
            facturation = UTILS_Facturation.Facturation()
            with tempfile.TemporaryDirectory() as tmp:
                nomDoc = str(Path(tmp) / "lot_factures.pdf")
                resultat = facturation.Impression(
                    listeFactures=[1, 2], nomDoc=nomDoc, afficherDoc=False,
                    dictOptions=dictOptions, afficherOptions=False,
                )
                self.assertIsNot(resultat, False)
                self.assertTrue(Path(nomDoc).is_file())


if __name__ == "__main__":
    unittest.main()
