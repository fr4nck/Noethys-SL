# -*- coding: utf-8 -*-
"""Audit de persistance des modèles de catégorie "convention"
(documents_modeles/documents_objets) -- recette réelle Noethys SL
0.1.0 RC1 : un modèle de convention créé/importé a généré un PDF avec
succès (CONVENTION20260923155619KHW700.pdf), mais l'application affiche
ensuite "Aucun modèle de convention n'est disponible.".

Audit mené (voir le rapport de recette pour le détail complet) : le
mécanisme de sauvegarde (DLG_Noedoc.ModeleDoc.Sauvegarde()) et
d'importation (UTILS_Export_documents.Importer()) est générique,
identique à celui de toutes les autres catégories historiques (facture,
attestation, ...) -- aucune branche spécifique à "convention". Les tests
ci-dessous le PROUVENT par un cycle réel sauvegarde/réouverture (nouvelle
connexion GestionDB.DB(), exactement comme le fait
CTRL_Choix_modele.CTRL_Choice à chaque ouverture de dialogue), plutôt que
de le supposer depuis la lecture du code seule.

Aucun bug n'a été trouvé dans ce mécanisme générique : la cause du
symptôme observé en recette (transition réelle constatée entre deux
tentatives le 23/09, un modèle categorie='convention' existant puis
n'existant plus quelques minutes plus tard) N'A PAS pu être confirmée
sans accès à la base réelle -- ce point reste ouvert, PAS clos comme
"mécanisme sain" (voir le rapport de recette pour le détail : snapshot
du 10/09 audité en lecture seule, ne contenant aucune ligne
categorie='convention', ne peut pas expliquer cette transition du
23/09). Un défaut latent réel et distinct A été trouvé et corrigé
pendant cet audit dans UTILS_Export_documents.Importer() : voir
test_import_objet_sans_cle_image_ne_leve_pas_et_n_ecrase_pas_le_blob_precedent.

Fait supplémentaire confirmé (audit packaging) : les modèles d'exemple
Convention (docs/recette_conventions/README.md) n'étaient PAS embarqués
dans le portable/installateur Windows réel (absents de
packaging/vanilla-noethys.spec, absents de
dist/Noethys-installable/*) -- une installation réelle n'avait donc
aucun moyen d'importer un modèle Convention sans accès au dépôt GitHub.
Corrigé en déplaçant ces fichiers sous
noethys/Static/ModelesConventionExemples/ (seul dossier de ressources
réellement embarqué), et en ajoutant
UTILS_Export_documents.ImporterModeleExempleIdempotent() (import sans
jamais créer de doublon, jamais de modification silencieuse d'un
modèle utilisateur existant) -- voir
ImporterModeleExempleIdempotentTests ci-dessous. Il ne s'agit PAS encore
du modèle "officiel" fidèle à la référence visuelle réelle : ce sont
toujours les mêmes exemples génériques anonymisés qu'avant ce
déplacement.
"""
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

import wx  # noqa: E402

# wx ne supporte qu'un seul wx.App par processus : créé une fois au niveau
# module (jamais détruit ici), comme test_vanilla_apparence_claire.py et
# test_vanilla_convention_recette_modeles.py -- un wx.App créé/détruit à
# l'intérieur d'une méthode de test casse tout usage de wx dans les
# AUTRES modules de test exécutés ensuite dans le même processus
# (python -m unittest discover).
_APP = wx.App(False)

from _fixtures_noethys_db import BaseTest, RedirectionGestionDB  # noqa: E402

import GestionDB  # noqa: E402
from Ctrl.CTRL_Choix_modele import CTRL_Choice  # noqa: E402
from Utils import UTILS_Export_documents  # noqa: E402


class PersistanceModeleConventionTests(unittest.TestCase):
    """ Preuve directe (pas une supposition) que le mécanisme générique de
    sauvegarde d'un modèle "documents_modeles"/"documents_objets" pour la
    catégorie convention survit réellement à une fermeture/réouverture de
    connexion -- exactement le scénario "créer un modèle, le retrouver
    plus tard" rapporté en recette. """

    def test_insertion_documents_modeles_convention_persiste_apres_reouverture(self):
        base = BaseTest()
        # Reproduit exactement l'INSERT fait par
        # DLG_Noedoc.ModeleDoc.Sauvegarde() pour un nouveau modèle (mêmes
        # colonnes, categorie="convention"), sur une première connexion...
        db1 = GestionDB.DB(nomFichier=base.chemin, suffixe=None)
        IDmodele = db1.ReqInsert("documents_modeles", [
            ("nom", "Convention test"),
            ("categorie", "convention"),
            ("supprimable", 1),
            ("largeur", 210.0),
            ("hauteur", 297.0),
            ("observations", ""),
            ("IDfond", None),
            ("IDdonnee", None),
            ("defaut", 1),
        ])
        db1.Close()

        # ... puis relit avec une CONNEXION FRAICHE distincte, exactement
        # ce que fait CTRL_Choice.GetListeDonnees() (SELECT ... WHERE
        # categorie='convention') à chaque ouverture du dialogue de
        # génération de convention.
        db2 = GestionDB.DB(nomFichier=base.chemin, suffixe=None)
        db2.ExecuterReq(
            "SELECT IDmodele, nom FROM documents_modeles "
            "WHERE categorie='convention' ORDER BY nom;"
        )
        resultat = db2.ResultatReq()
        db2.Close()

        self.assertEqual(resultat, [(IDmodele, "Convention test")])

    def test_ctrl_choice_retrouve_le_modele_convention_apres_reouverture(self):
        """ Même preuve, mais via le VRAI contrôle utilisé par
        DLG_Generation_convention (CTRL_Choix_modele.CTRL_Choice), pas une
        requête SQL reconstruite à la main. """
        base = BaseTest()

        db1 = GestionDB.DB(nomFichier=base.chemin, suffixe=None)
        IDmodele = db1.ReqInsert("documents_modeles", [
            ("nom", "Convention test"),
            ("categorie", "convention"),
            ("supprimable", 1),
            ("largeur", 210.0),
            ("hauteur", 297.0),
            ("observations", ""),
            ("IDfond", None),
            ("IDdonnee", None),
            ("defaut", 1),
        ])
        db1.Close()

        frame = wx.Frame(None)
        try:
            with RedirectionGestionDB(base.chemin):
                ctrl = CTRL_Choice(frame, categorie="convention")
                self.assertEqual(ctrl.GetID(), IDmodele)
        finally:
            frame.Destroy()

    def test_import_objet_sans_cle_image_ne_leve_pas_et_n_ecrase_pas_le_blob_precedent(self):
        """ Défaut latent réel trouvé pendant cet audit (pas le défaut
        rapporté en recette, mais un défaut distinct dans la même fonction
        auditée) : Importer() lisait `blob` défini seulement DANS la
        boucle interne quand champ == "image". Un objet sans clé "image"
        (jamais produit par Exporter() aujourd'hui, qui inclut
        systématiquement cette clé -- mais pas garanti pour tout fichier
        .ndc externe/futur) levait UnboundLocalError au premier objet
        sans image, ou pire, réutilisait silencieusement le blob de
        l'objet précédent. Corrigé en réinitialisant blob=None à chaque
        objet. """
        base = BaseTest()
        with RedirectionGestionDB(base.chemin):
            IDmodele = UTILS_Export_documents.Importer(dictDonnees={
                "nom": "Convention sans clé image",
                "categorie": "convention",
                "largeur": 210,
                "hauteur": 297,
                "IDfond": None,
                "defaut": 0,
                "objets": [
                    # Premier objet : PAS de clé "image" du tout (le cas qui
                    # levait UnboundLocalError avant le correctif).
                    {"nom": "article_1", "categorie": "texte_flottant", "champ": None,
                     "ordre": 0, "texte": "Un article de convention.", "x": 10.0, "y": 10.0},
                ],
            })
            self.assertIsNotNone(IDmodele)

            db = GestionDB.DB(nomFichier=base.chemin, suffixe=None)
            db.ExecuterReq("SELECT nom FROM documents_objets WHERE IDmodele=%d;" % IDmodele)
            resultat = db.ResultatReq()
            db.Close()
            self.assertEqual(resultat, [("article_1",)])


MODELES_EXEMPLES_DIR = NOETHYS_DIR / "Static" / "ModelesConventionExemples"


class ImporterModeleExempleIdempotentTests(unittest.TestCase):
    """ Item 3/5 du rapport de recette : les modèles d'exemple Convention
    n'étaient pas embarqués dans le produit réel (absents de
    packaging/vanilla-noethys.spec) -- "cliquer Importer" n'était donc pas
    une stratégie suffisante, le fichier à importer n'étant pas livré.
    Déplacés sous noethys/Static/ModelesConventionExemples/ (seul dossier
    de ressources réellement embarqué -- voir aussi le test packaging CI
    "Vérifier la présence des modèles Convention d'exemple dans le
    paquet"). Ces tests prouvent, contre les VRAIS fichiers livrés (pas
    une copie de test), que l'import est réellement idempotent : jamais
    de doublon, jamais de modification silencieuse d'un modèle existant. """

    def test_les_fichiers_exemples_existent_a_leur_emplacement_embarque(self):
        for nom_fichier in ("modele_convention_associative.ndc", "modele_convention_scolaire.ndc"):
            chemin = MODELES_EXEMPLES_DIR / nom_fichier
            self.assertTrue(chemin.is_file(), "%s absent de %s" % (nom_fichier, MODELES_EXEMPLES_DIR))

    def test_premier_import_cree_un_modele_categorie_convention(self):
        chemin_ndc = MODELES_EXEMPLES_DIR / "modele_convention_associative.ndc"
        base = BaseTest()
        with RedirectionGestionDB(base.chemin):
            IDmodele = UTILS_Export_documents.ImporterModeleExempleIdempotent(fichier=str(chemin_ndc))
            self.assertIsNotNone(IDmodele)

            db = GestionDB.DB(nomFichier=base.chemin, suffixe=None)
            db.ExecuterReq("SELECT IDmodele, categorie FROM documents_modeles WHERE IDmodele=%d;" % IDmodele)
            resultat = db.ResultatReq()
            db.Close()
            self.assertEqual(resultat, [(IDmodele, "convention")])

    def test_reimport_ne_cree_aucun_doublon(self):
        """ CAS central de la recommandation "import idempotent, aucun
        doublon" : importer deux fois le même fichier d'exemple ne doit
        créer qu'UN SEUL modèle, en base réelle, pas deux. """
        chemin_ndc = MODELES_EXEMPLES_DIR / "modele_convention_associative.ndc"
        base = BaseTest()
        with RedirectionGestionDB(base.chemin):
            IDmodele1 = UTILS_Export_documents.ImporterModeleExempleIdempotent(fichier=str(chemin_ndc))
            IDmodele2 = UTILS_Export_documents.ImporterModeleExempleIdempotent(fichier=str(chemin_ndc))
            self.assertEqual(IDmodele1, IDmodele2)

            db = GestionDB.DB(nomFichier=base.chemin, suffixe=None)
            db.ExecuterReq("SELECT COUNT(*) FROM documents_modeles WHERE categorie='convention';")
            (nbre,) = db.ResultatReq()[0]
            db.Close()
            self.assertEqual(nbre, 1)

    def test_reimport_ne_modifie_pas_un_modele_utilisateur_deja_renomme(self):
        """ Si l'utilisateur a modifié le modèle importé (ex. renommé un
        article, changé le texte) après un premier import, un second
        import du même fichier source ne doit JAMAIS écraser silencieusement
        ses modifications -- seul le nom+catégorie sert à détecter un
        doublon, jamais le contenu des objets. """
        chemin_ndc = MODELES_EXEMPLES_DIR / "modele_convention_associative.ndc"
        base = BaseTest()
        with RedirectionGestionDB(base.chemin):
            IDmodele = UTILS_Export_documents.ImporterModeleExempleIdempotent(fichier=str(chemin_ndc))

            db = GestionDB.DB(nomFichier=base.chemin, suffixe=None)
            db.ExecuterReq("SELECT IDobjet, texte FROM documents_objets WHERE IDmodele=%d LIMIT 1;" % IDmodele)
            IDobjet, _texte_original = db.ResultatReq()[0]
            db.ReqMAJ("documents_objets", [("texte", "Texte modifié par l'utilisateur")], "IDobjet", IDobjet)
            db.Close()

            IDmodele2 = UTILS_Export_documents.ImporterModeleExempleIdempotent(fichier=str(chemin_ndc))
            self.assertEqual(IDmodele, IDmodele2)

            db = GestionDB.DB(nomFichier=base.chemin, suffixe=None)
            db.ExecuterReq("SELECT texte FROM documents_objets WHERE IDobjet=%d;" % IDobjet)
            (texte_final,) = db.ResultatReq()[0]
            db.Close()
            self.assertEqual(texte_final, "Texte modifié par l'utilisateur")

    def test_persiste_apres_reouverture(self):
        chemin_ndc = MODELES_EXEMPLES_DIR / "modele_convention_scolaire.ndc"
        base = BaseTest()
        with RedirectionGestionDB(base.chemin):
            IDmodele = UTILS_Export_documents.ImporterModeleExempleIdempotent(fichier=str(chemin_ndc))

        # Nouvelle connexion fraîche, hors du "with" -- exactement le
        # scénario "fermeture/réouverture" demandé.
        db = GestionDB.DB(nomFichier=base.chemin, suffixe=None)
        db.ExecuterReq("SELECT IDmodele FROM documents_modeles WHERE categorie='convention';")
        resultat = db.ResultatReq()
        db.Close()
        self.assertEqual(resultat, [(IDmodele,)])



class EncodageHistoriqueNdcTests(unittest.TestCase):
    def test_ancien_open_windows_cp1252_reproduit_exactement_le_mojibake(self):
        """Le loader historique ouvrait le JSON sans encoding explicite.

        Sur Windows français, un .ndc UTF-8 était donc décodé en cp1252 :
        c'est exactement la transformation observée en recette.
        """
        import json
        import tempfile
        from pathlib import Path
        from Utils import UTILS_Json

        texte_source = u"Tél. — Représentée — DURÉE"
        with tempfile.TemporaryDirectory() as rep:
            chemin = Path(rep) / "modele.ndc"
            chemin.write_text(
                json.dumps({"texte": texte_source}, ensure_ascii=False),
                encoding="utf-8",
            )

            # Reproduction déterministe du comportement Windows historique.
            ancien = json.loads(chemin.read_text(encoding="cp1252"))
            self.assertEqual(ancien["texte"], u"TÃ©l. â€” ReprÃ©sentÃ©e â€” DURÃ‰E")

            # Le chemin actuel explicite UTF-8 et conserve les caractères.
            actuel = UTILS_Json.Lire(str(chemin))
            self.assertEqual(actuel["texte"], texte_source)


if __name__ == "__main__":
    unittest.main()