# -*- coding: utf-8 -*-
"""Recette Windows réelle : depuis la fiche famille, la génération d'une
convention Noedoc est bloquée par

    « Impossible de générer la convention. Le texte du modèle semble déjà
    mal encodé (UTF-8/mojibake) dans : En-tÃªte organisateur, Parties,
    Article 1 corps, ... Corrigez ou réimportez ce modèle avant de générer
    la convention. »

Chaîne causale reproduite ici, contre les VRAIS fichiers livrés :

1. l'ancien UTILS_Json.Lire() ouvrait le .ndc sans encoding explicite,
   donc en cp1252 sous Windows français ;
2. modele_convention_pmsl_associative.ndc est le seul modèle fourni qui
   contient des octets UTF-8 bruts (les deux autres sont en ASCII
   échappé \\u00xx, insensibles au locale) : son import historique a
   persisté du mojibake dans documents_modeles / documents_objets
   (y compris dans le NOM du modèle : « rÃ©fÃ©rence ») ;
3. le loader est désormais corrigé, le fichier livré est propre, mais
   rien ne répare le modèle déjà en base, ImporterModeleExempleIdempotent()
   renvoie le modèle existant sans le remplacer (nom + catégorie
   identiques) et _ValideEncodageModele() bloque -- à juste titre -- la
   génération : l'utilisateur n'a aucun chemin sûr de récupération.

Le correctif testé ici n'écrase ni ne supprime jamais le modèle
historique : il installe, après confirmation explicite, une COPIE PROPRE
d'un modèle fourni, sous un nom distinct si nécessaire, sans jamais
tenter de « réparer » le contenu utilisateur.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
NOETHYS_DIR = TESTS_DIR.parent / "noethys"
MODELES_DIR = NOETHYS_DIR / "Static" / "ModelesConventionExemples"
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import wx  # noqa: E402

_APP = wx.App(False)

from _fixtures_noethys_db import (  # noqa: E402
    RedirectionGestionDB,
    creer_base_association_simple,
    inserer_modele_document,
)
import GestionDB  # noqa: E402
from Ctrl.CTRL_Choix_modele import CTRL_Choice  # noqa: E402
from Dlg import DLG_Noedoc  # noqa: E402
from Dlg import DLG_Generation_convention  # noqa: E402
from Utils import UTILS_Export_documents as UED  # noqa: E402
from Utils import UTILS_Impression_convention as UIC  # noqa: E402

FICHIER_PMSL = MODELES_DIR / "modele_convention_pmsl_associative.ndc"
FICHIERS_EXEMPLES = (
    MODELES_DIR / "modele_convention_associative.ndc",
    FICHIER_PMSL,
    MODELES_DIR / "modele_convention_scolaire.ndc",
)

# Objets supplémentaires reprenant les libellés exacts du message de
# recette (le modèle réellement en base n'est pas disponible ici).
OBJETS_RECETTE = (
    (u"En-tÃªte organisateur", u"TÃ©l. {ORGANISATEUR_TEL}"),
    (u"Parties", u"ReprÃ©sentÃ©e par {CONVENTION_REPRESENTANT_NOM_COMPLET}"),
    (u"Article 2 titre", u"ARTICLE 2 - DURÃ‰E"),
)


def _donnees_import_historique_windows(fichier=FICHIER_PMSL, objets_supplementaires=True):
    """ Reproduction déterministe de l'ancien import Windows : le .ndc UTF-8
    lu en cp1252 (voir EncodageHistoriqueNdcTests). """
    data = json.loads(Path(fichier).read_text(encoding="cp1252"))
    if objets_supplementaires:
        # Clone d'un vrai bloc_texte du fichier (tous les champs Noedoc
        # requis), seuls le nom et le texte changent.
        gabarit = next(o for o in data["objets"] if o["categorie"] == "bloc_texte")
        for index, (nom, texte) in enumerate(OBJETS_RECETTE):
            objet = dict(gabarit)
            objet.update({"nom": nom, "texte": texte, "ordre": 900 + index})
            data["objets"].append(objet)
    return data


def _instantane_modele(chemin, IDmodele):
    db = GestionDB.DB(nomFichier=chemin, suffixe=None)
    db.ExecuterReq("SELECT * FROM documents_modeles WHERE IDmodele=%d;" % IDmodele)
    modele = db.ResultatReq()
    db.ExecuterReq("SELECT * FROM documents_objets WHERE IDmodele=%d ORDER BY IDobjet;" % IDmodele)
    objets = db.ResultatReq()
    db.Close()
    return modele, objets


def _modeles_convention(chemin):
    db = GestionDB.DB(nomFichier=chemin, suffixe=None)
    db.ExecuterReq("SELECT IDmodele, nom FROM documents_modeles WHERE categorie='convention' ORDER BY IDmodele;")
    resultat = db.ResultatReq()
    db.Close()
    return resultat


def _textes_objets(chemin, IDmodele):
    db = GestionDB.DB(nomFichier=chemin, suffixe=None)
    db.ExecuterReq("SELECT nom, texte FROM documents_objets WHERE IDmodele=%d;" % IDmodele)
    resultat = db.ResultatReq()
    db.Close()
    return resultat


class DetecteurMojibakeTests(unittest.TestCase):
    """ Audit de _ValideEncodageModele() : la protection reste, mais sans
    faux positif sur des majuscules accentuées légitimes (ÂGE, CHÂTEAU,
    PÂQUES...) que l'ancien marqueur isolé « Â » bloquait. """

    MOJIBAKE = (
        u"En-tÃªte organisateur", u"TÃ©l.", u"DURÃ‰E", u"ReprÃ©sentÃ©e",
        u"Lâ€™Association", u"sâ€™engage Ã\xa0 encadrer", u"Ã€ TESTVILLE",
        u"NÂ° 12", u"Â« guillemets Â»", u"cÅ“ur", u"texte avec �",
        u"prix : 24 â‚¬",
    )
    LEGITIMES = (
        u"En-tête organisateur", u"Tél.", u"DURÉE", u"Représentée",
        u"L’Association", u"s’engage à encadrer", u"À TESTVILLE",
        u"N° 12", u"« guillemets »", u"cœur", u"Tarif : 24,00 €/h",
        u"ÂGE MINIMUM", u"CHÂTEAU", u"PÂQUES", u"SÃO PAULO", u"",
    )

    def test_mojibake_historique_detecte(self):
        for texte in self.MOJIBAKE:
            self.assertTrue(UED.TexteSembleMalEncode(texte), texte)

    def test_texte_utf8_correct_accepte(self):
        for texte in self.LEGITIMES:
            self.assertFalse(UED.TexteSembleMalEncode(texte), texte)

    def test_valide_encodage_modele_utilise_le_meme_detecteur(self):
        """ Avant ce correctif, « CHÂTEAU » (Â isolé) était refusé à tort. """
        with creer_base_association_simple() as base:
            for texte, attendu_ok in ((u"CHÂTEAU — ÂGE — DURÉE", True), (u"En-tÃªte", False)):
                IDmodele = inserer_modele_document(base, u"Témoin", "convention", [
                    {"nom": "Corps", "categorie": "bloc_texte", "ordre": 1,
                     "x": 13, "y": 20, "largeur": 182, "texte": texte},
                ])
                with RedirectionGestionDB(base.chemin):
                    modeleDoc = DLG_Noedoc.ModeleDoc(IDmodele=IDmodele)
                    if attendu_ok:
                        UIC._ValideEncodageModele(modeleDoc)
                    else:
                        with self.assertRaisesRegex(ValueError, "mal encodé"):
                            UIC._ValideEncodageModele(modeleDoc)


class ReproductionBugRecetteTests(unittest.TestCase):
    """ Étapes 1-2 : le modèle historique persisté est bien détecté, et le
    mécanisme existant ne fournit aucune issue. """

    def test_import_historique_pmsl_persiste_du_mojibake_y_compris_dans_le_nom(self):
        data = _donnees_import_historique_windows(objets_supplementaires=False)
        self.assertEqual(data["nom"], u"Convention PMSL - Associations sportives (rÃ©fÃ©rence)")

    def test_les_deux_autres_exemples_sont_insensibles_au_locale(self):
        for fichier in FICHIERS_EXEMPLES:
            if fichier == FICHIER_PMSL:
                continue
            self.assertEqual(json.loads(fichier.read_text(encoding="cp1252")),
                             json.loads(fichier.read_text(encoding="utf-8")))

    def test_validation_actuelle_detecte_le_modele_historique(self):
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                IDmodele = UED.Importer(dictDonnees=_donnees_import_historique_windows())
                modeleDoc = DLG_Noedoc.ModeleDoc(IDmodele=IDmodele)
                with self.assertRaisesRegex(ValueError, u"En-tÃªte organisateur.*mal encodé|mal encodé.*En-tÃªte organisateur"):
                    UIC._ValideEncodageModele(modeleDoc)
                suspects = UED.GetObjetsMalEncodes(IDmodele)
                for nom in (u"En-tÃªte organisateur", u"Parties", u"Article 2 titre", u"Article 1 corps"):
                    self.assertIn(nom, suspects)

    def test_import_idempotent_seul_renvoie_le_modele_corrompu(self):
        """ Cas « même nom + même catégorie » : l'import d'exemple existant
        retrouve l'ancien modèle et, volontairement, ne le remplace pas.
        Sans autre mécanisme, l'utilisateur reste bloqué. """
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                data = _donnees_import_historique_windows()
                data["nom"] = UED.UTILS_Json.Lire(str(FICHIER_PMSL))["nom"]
                IDcorrompu = UED.Importer(dictDonnees=data)
                self.assertEqual(UED.ImporterModeleExempleIdempotent(fichier=str(FICHIER_PMSL)), IDcorrompu)
                self.assertTrue(UED.GetObjetsMalEncodes(IDcorrompu))


class RecuperationCopiePropreTests(unittest.TestCase):
    """ Étapes 3-4 : récupération par copie propre, sans toucher à
    l'original. """

    def _installer_corrompu(self, base, nom=None):
        data = _donnees_import_historique_windows()
        if nom is not None:
            data["nom"] = nom
        return UED.Importer(dictDonnees=data)

    def test_exemple_correspondant_retrouve_meme_avec_nom_mojibake(self):
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                IDcorrompu = self._installer_corrompu(base)
                self.assertEqual(Path(UED.TrouverModeleExempleCorrespondant(IDcorrompu)), FICHIER_PMSL)

    def test_exemple_correspondant_absent_pour_un_modele_utilisateur(self):
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                IDcorrompu = self._installer_corrompu(base, nom=u"Ma convention perso")
                self.assertIsNone(UED.TrouverModeleExempleCorrespondant(IDcorrompu))

    def test_liste_des_modeles_exemples_fournis(self):
        exemples = UED.GetModelesExemplesConvention()
        self.assertEqual(sorted(Path(e["fichier"]).name for e in exemples),
                         sorted(f.name for f in FICHIERS_EXEMPLES))
        for exemple in exemples:
            self.assertEqual(exemple["categorie"], "convention")
            self.assertFalse(UED.TexteSembleMalEncode(exemple["nom"]))

    def test_copie_propre_installee_sans_modifier_ni_supprimer_l_original(self):
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                IDcorrompu = self._installer_corrompu(base)
                avant = _instantane_modele(base.chemin, IDcorrompu)

                IDpropre, nom, cree = UED.InstallerCopiePropreModeleExemple(str(FICHIER_PMSL))

                self.assertTrue(cree)
                self.assertNotEqual(IDpropre, IDcorrompu)
                self.assertEqual(_instantane_modele(base.chemin, IDcorrompu), avant)
                self.assertTrue(avant[0] and avant[1])
                noms = dict(_modeles_convention(base.chemin))
                self.assertEqual(set(noms), {IDcorrompu, IDpropre})
                self.assertNotEqual(noms[IDpropre], noms[IDcorrompu])
                self.assertEqual(noms[IDpropre], nom)
                self.assertEqual(UED.GetObjetsMalEncodes(IDpropre), [])
                textes = dict(_textes_objets(base.chemin, IDpropre))
                self.assertEqual(textes[u"Téléphone organisateur entête"], u"Tél. {ORGANISATEUR_TEL}")
                self.assertIn(u"L’Association", textes[u"Article 1 corps"])

    def test_nom_distinct_quand_le_nom_fourni_est_deja_pris_par_le_modele_corrompu(self):
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                nomFourni = UED.UTILS_Json.Lire(str(FICHIER_PMSL))["nom"]
                IDcorrompu = self._installer_corrompu(base, nom=nomFourni)
                IDpropre, nom, cree = UED.InstallerCopiePropreModeleExemple(str(FICHIER_PMSL))
                self.assertTrue(cree)
                self.assertNotEqual(IDpropre, IDcorrompu)
                self.assertEqual(nom, nomFourni + u" (copie propre)")

                # Un second modèle corrompu occupant aussi ce nom : suffixe suivant.
                with creer_base_association_simple() as base2:
                    with RedirectionGestionDB(base2.chemin):
                        self._installer_corrompu(base2, nom=nomFourni)
                        self._installer_corrompu(base2, nom=nomFourni + u" (copie propre)")
                        _ID, nom2, _cree = UED.InstallerCopiePropreModeleExemple(str(FICHIER_PMSL))
                        self.assertEqual(nom2, nomFourni + u" (copie propre 2)")

    def test_relance_ne_cree_aucun_doublon(self):
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                nomFourni = UED.UTILS_Json.Lire(str(FICHIER_PMSL))["nom"]
                IDcorrompu = self._installer_corrompu(base, nom=nomFourni)
                ID1, nom1, cree1 = UED.InstallerCopiePropreModeleExemple(str(FICHIER_PMSL))
                ID2, nom2, cree2 = UED.InstallerCopiePropreModeleExemple(str(FICHIER_PMSL))
                ID3, _nom3, cree3 = UED.InstallerCopiePropreModeleExemple(str(FICHIER_PMSL))
                self.assertTrue(cree1)
                self.assertEqual((ID2, nom2), (ID1, nom1))
                self.assertFalse(cree2)
                self.assertFalse(cree3)
                self.assertEqual(ID1, ID3)
                self.assertEqual([ID for ID, _n in _modeles_convention(base.chemin)], [IDcorrompu, ID1])

    def test_ctrl_choice_retrouve_la_copie_propre_apres_reouverture(self):
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                self._installer_corrompu(base)
                IDpropre, nom, _cree = UED.InstallerCopiePropreModeleExemple(str(FICHIER_PMSL))

            frame = wx.Frame(None)
            try:
                with RedirectionGestionDB(base.chemin):
                    ctrl = CTRL_Choice(frame, categorie="convention")
                    self.assertIn(nom, ctrl.GetItems())
                    ctrl.SetID(IDpropre)
                    self.assertEqual(ctrl.GetID(), IDpropre)
                    self.assertEqual(ctrl.GetStringSelection(), nom)
            finally:
                frame.Destroy()

    def test_generation_convention_depasse_la_validation_avec_la_copie_propre(self):
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                IDcorrompu = self._installer_corrompu(base)
                IDpropre, _nom, _cree = UED.InstallerCopiePropreModeleExemple(str(FICHIER_PMSL))

                modeleDoc = DLG_Noedoc.ModeleDoc(IDmodele=IDpropre)
                UIC._ValideEncodageModele(modeleDoc)

                chemin_pdf = tempfile.mktemp(suffix=".pdf")
                try:
                    resultat = UIC.Impression(
                        IDfamille=1, IDmodele=IDpropre,
                        date_debut="2026-09-01", date_fin="2026-09-30",
                        saison="2026-2027", listeIDindividus=[2, 3],
                        nomDoc=chemin_pdf, afficherDoc=False,
                    )
                    self.assertIsInstance(resultat, dict, "génération échouée : %r" % (resultat,))
                    self.assertGreater(os.path.getsize(chemin_pdf), 0)
                finally:
                    if os.path.isfile(chemin_pdf):
                        os.remove(chemin_pdf)

                # L'original reste bloqué (protection intacte), et intact.
                with self.assertRaisesRegex(ValueError, "mal encodé"):
                    UIC._ValideEncodageModele(DLG_Noedoc.ModeleDoc(IDmodele=IDcorrompu))

    def test_compatible_avec_les_trois_modeles_fournis(self):
        for fichier in FICHIERS_EXEMPLES:
            with self.subTest(fichier=fichier.name):
                with creer_base_association_simple() as base:
                    with RedirectionGestionDB(base.chemin):
                        IDmodele, nom, cree = UED.InstallerCopiePropreModeleExemple(str(fichier))
                        self.assertTrue(cree)
                        self.assertEqual(nom, UED.UTILS_Json.Lire(str(fichier))["nom"])
                        self.assertEqual(UED.GetObjetsMalEncodes(IDmodele), [])
                        UIC._ValideEncodageModele(DLG_Noedoc.ModeleDoc(IDmodele=IDmodele))

    def test_refuse_d_installer_un_fichier_source_lui_meme_mal_encode(self):
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                chemin = tempfile.mktemp(suffix=".ndc")
                try:
                    Path(chemin).write_text(json.dumps(_donnees_import_historique_windows()), encoding="utf-8")
                    avant = _modeles_convention(base.chemin)
                    with self.assertRaisesRegex(ValueError, "mal encodé"):
                        UED.InstallerCopiePropreModeleExemple(chemin)
                    self.assertEqual(_modeles_convention(base.chemin), avant)
                finally:
                    if os.path.isfile(chemin):
                        os.remove(chemin)


class DialogRecuperationTests(unittest.TestCase):
    """ Chemin utilisateur : fiche famille > Générer une convention >
    bouton « Générer la convention » avec le modèle corrompu sélectionné. """

    def _dialog_avec_modele_corrompu(self, base, nom=None):
        data = _donnees_import_historique_windows()
        if nom is not None:
            data["nom"] = nom
        IDcorrompu = UED.Importer(dictDonnees=data)
        dlg = DLG_Generation_convention.Dialog(None, IDfamille=1)
        dlg.ctrl_modele.SetID(IDcorrompu)
        self.assertEqual(dlg.GetIDmodele(), IDcorrompu)
        return dlg, IDcorrompu

    def test_modele_corrompu_confirmation_installe_et_selectionne_la_copie(self):
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                dlg, IDcorrompu = self._dialog_avec_modele_corrompu(base)
                avant = _instantane_modele(base.chemin, IDcorrompu)
                questions, infos = [], []

                def demander(message, noms, selection):
                    questions.append((message, list(noms), selection))
                    return selection

                try:
                    with unittest.mock.patch.object(dlg, "_DemanderModeleExemple", side_effect=demander), \
                         unittest.mock.patch.object(dlg, "_Informer", side_effect=infos.append), \
                         unittest.mock.patch.object(dlg, "EndModal") as endModal:
                        dlg.OnBoutonOk(None)
                        endModal.assert_not_called()

                    message, noms, selection = questions[0]
                    self.assertIn(u"mauvais encodage", message)
                    self.assertIn(u"sans modifier l'original", message)
                    self.assertIn(u"En-tÃªte organisateur", message)
                    self.assertEqual(noms[selection], UED.UTILS_Json.Lire(str(FICHIER_PMSL))["nom"])

                    IDpropre = dlg.GetIDmodele()
                    self.assertNotEqual(IDpropre, IDcorrompu)
                    self.assertEqual(UED.GetObjetsMalEncodes(IDpropre), [])
                    self.assertIn(dlg.ctrl_modele.GetStringSelection(), infos[0])
                    self.assertEqual(_instantane_modele(base.chemin, IDcorrompu), avant)

                    # Nouvel appui sur « Générer » : la copie propre passe.
                    with unittest.mock.patch.object(dlg, "EndModal") as endModal:
                        dlg.OnBoutonOk(None)
                        endModal.assert_called_once_with(wx.ID_OK)
                finally:
                    dlg.Destroy()

    def test_modele_corrompu_annulation_n_installe_rien(self):
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                dlg, IDcorrompu = self._dialog_avec_modele_corrompu(base, nom=u"Ma convention perso")
                avant = _modeles_convention(base.chemin)
                try:
                    with unittest.mock.patch.object(dlg, "_DemanderModeleExemple", return_value=None) as demander, \
                         unittest.mock.patch.object(dlg, "_Informer"), \
                         unittest.mock.patch.object(dlg, "EndModal") as endModal:
                        dlg.OnBoutonOk(None)
                        endModal.assert_not_called()
                        # Aucun exemple ne correspond au nom : pas de présélection.
                        self.assertEqual(demander.call_args[0][2], -1)
                    self.assertEqual(_modeles_convention(base.chemin), avant)
                    self.assertEqual(dlg.GetIDmodele(), IDcorrompu)
                finally:
                    dlg.Destroy()

    def test_modele_propre_ferme_le_dialogue_sans_question(self):
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                IDmodele = UED.Importer(fichier=str(FICHIER_PMSL))
                dlg = DLG_Generation_convention.Dialog(None, IDfamille=1)
                dlg.ctrl_modele.SetID(IDmodele)
                try:
                    with unittest.mock.patch.object(dlg, "_DemanderModeleExemple") as demander, \
                         unittest.mock.patch.object(dlg, "EndModal") as endModal:
                        dlg.OnBoutonOk(None)
                        demander.assert_not_called()
                        endModal.assert_called_once_with(wx.ID_OK)
                finally:
                    dlg.Destroy()


if __name__ == "__main__":
    unittest.main()
