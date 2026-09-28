#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Orchestration de l'impression d'une convention.

Ce module ne contient AUCUN texte d'article, AUCUNE identité PMSL,
AUCUNE mise en page spécifique aux conventions : tout cela vit dans le
modèle .ndc choisi (documents_modeles/documents_objets), édité avec le
concepteur Noedoc habituel (Dlg/DLG_Noedoc.py), exactement comme une
facture ou une attestation.

Ce module se contente de :
- construire le dictionnaire de champs {CODE: valeur} depuis les données
  Noethys réelles (Utils/UTILS_Convention_champs.py) ;
- charger le modèle choisi (DLG_Noedoc.ModeleDoc) ;
- déclencher le rendu en réutilisant le même mécanisme générique que les
  autres catégories : fond/formes/images/codes-barres dessinés à
  position fixe par ModeleDoc, et les blocs de texte placés dans le
  cadre principal transformés en paragraphes ReportLab (Platypus) pour
  bénéficier de la même pagination automatique que les factures et
  attestations fiscales. Aucune logique de pagination propre aux
  conventions n'est réintroduite ici.
- gérer le fichier final (nom, ouverture).

Audit ciblé (dernier jalon avant recette utilisateur) : BaseDocTemplate/
PageTemplate/Frame/Paragraph ne sont utilisés ici QUE pour permettre
l'écoulement multipage du contenu du cadre principal -- exactement le
même besoin que pour une facture longue. Aucun de ces objets ne reçoit
de texte, de style ou de coordonnées écrits en dur dans ce fichier :
le texte et le style de police viennent de objet.texte/GetValeur() et
objet.taillePolicePDF/Weight/Style (colonnes documents_objets, éditées
dans le concepteur Noedoc), les coordonnées viennent de
modeleDoc.GetCoordsObjet(cadre_principal).

L'ordre de lecture des blocs flottants (et l'ordre de dessin des objets
fixes qui se chevauchent) suit exclusivement la colonne "ordre" de
documents_objets, PAS l'ordre d'insertion en base ni la position
géométrique d'un objet. Cette colonne est réécrite par
DLG_Noedoc.ModeleDoc.Sauvegarde() selon l'ordre d'empilement du canvas
(index de self.GetObjets()), donc SEULES les actions explicites
"Mettre au premier/arrière-plan" du concepteur changent cet ordre :
déplacer un bloc (changer x/y) ne le modifie jamais. Un bloc déplacé
hors du cadre principal bascule en revanche de "flottant" à "fixe" (ou
inversement) via la règle géométrique _ObjetDansCadre -- c'est le seul
changement de comportement attendu d'un déplacement visuel, et il est
volontaire : un objet sorti du cadre n'est plus paginable, donc il doit
redevenir un objet à position fixe. Voir
tests/test_vanilla_convention_rendering.py::
test_ordre_des_blocs_flottants_suit_la_colonne_ordre_pas_l_insertion.

Audit fidélité (recette réelle Atout Sports) : le rendu flottant ne
restituait que police/taille/interligne fixe des objets Noedoc, perdant
couleur de texte, fond, bordure, padding, alignement et soulignement
réellement définis dans le concepteur. _StyleReportLab() les traduit
maintenant en ParagraphStyle (textColor/backColor/borderColor/
borderWidth/borderPadding/alignment), à partir des mêmes attributs déjà
stockés sur l'objet FloatCanvas par DLG_Noedoc.ImportationObjets/
AjouterBlocTexte (Color/BackgroundColor/LineColor/LineWidth/PadSize/
Alignment/LineSpacing/Underlined) -- aucune valeur n'est inventée, une
propriété non définie sur l'objet (None) n'est simplement jamais
appliquée. Voir tests/test_vanilla_convention_rendu_fidelite.py.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

import wx

import FonctionsPerso
from Utils.UTILS_Traduction import _
from Dlg import DLG_Noedoc
from Utils import UTILS_Convention_champs

from reportlab.platypus.doctemplate import BaseDocTemplate, PageTemplate
from reportlab.platypus.frames import Frame
from reportlab.platypus import Paragraph, KeepTogether, PageBreak, Spacer, Image as PlatypusImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.lib.units import mm as mmPDF
from reportlab.pdfbase import pdfmetrics
import io


TAILLE_PAGE = A4


def _PoliceReportLab(objet):
    """Respecte la face Noedoc si elle est réellement enregistrée."""
    face = (getattr(objet, "FaceName", None) or u"").strip()
    if face.lower() in ("arial", "arial regular"):
        face = "Arial"
    enregistrees = set(pdfmetrics.getRegisteredFontNames())
    if face not in enregistrees:
        face = "Arial"
    if face == "Arial":
        if objet.Style == wx.ITALIC and objet.Weight == wx.BOLD:
            return "Arial-BoldOblique"
        if objet.Weight == wx.BOLD:
            return "Arial-Bold"
        if objet.Style == wx.ITALIC:
            return "Arial-Oblique"
        return "Arial"
    suffixe = u""
    if objet.Style == wx.ITALIC and objet.Weight == wx.BOLD:
        suffixe = "-BoldOblique"
    elif objet.Weight == wx.BOLD:
        suffixe = "-Bold"
    elif objet.Style == wx.ITALIC:
        suffixe = "-Oblique"
    candidate = face + suffixe if suffixe else face
    return candidate if candidate in enregistrees else face


ALIGNEMENTS_REPORTLAB = {
    "left": TA_LEFT,
    "right": TA_RIGHT,
    "center": TA_CENTER,
    "justify": TA_JUSTIFY,
}


def _CouleurReportLab(couleurRGB):
    """ objet.Color/BackgroundColor/LineColor (Dlg.DLG_Noedoc, objets
    FloatCanvas ScaledTextBox) sont des tuples (r, g, b) 0-255 ou None --
    exactement la même représentation que
    DLG_Noedoc.ImportationObjets.ConvertCouleur(), jamais reconvertie ni
    devinée ici. """
    if not couleurRGB:
        return None
    r, g, b = couleurRGB
    return colors.Color(r / 255.0, g / 255.0, b / 255.0)


def _StyleReportLab(objet):
    """ Traduit en ParagraphStyle ReportLab les propriétés visuelles
    réellement portées par l'objet Noedoc -- les mêmes que celles
    éditées dans le concepteur et stockées par
    DLG_Noedoc.ImportationObjets/AjouterBlocTexte sur l'objet FloatCanvas
    ScaledTextBox sous-jacent (attributs Color, BackgroundColor,
    LineColor/LineWidth, PadSize, Alignment, LineSpacing) : couleur de
    texte, fond, bordure, padding, alignement, interligne. Le
    soulignement (Underlined) est appliqué séparément (balise <u> autour
    du texte, car ParagraphStyle ne porte pas de propriété "souligné"
    globale). Gras/italique sont déjà gérés par _PoliceReportLab via le
    nom de police (comme pour les objets à position fixe). Aucune valeur
    n'est codée en dur : une propriété non définie sur l'objet (None)
    n'est simplement jamais appliquée au style. """
    style = ParagraphStyle(
        "convention_objet_%s" % id(objet),
        fontName=_PoliceReportLab(objet),
        fontSize=objet.taillePolicePDF,
        leading=objet.taillePolicePDF * 1.2 * (objet.LineSpacing or 1.0),
        alignment=ALIGNEMENTS_REPORTLAB.get(objet.Alignment, TA_LEFT),
        textColor=_CouleurReportLab(objet.Color) or colors.black,
        # Espacement générique entre paragraphes (pas une règle
        # spécifique à un modèle) : sans lui, des paragraphes consécutifs
        # se retrouvent collés, ce qui contribue à une page 1 trop dense.
        spaceAfter=objet.taillePolicePDF * 0.5,
    )
    couleurFond = _CouleurReportLab(objet.BackgroundColor)
    if couleurFond is not None:
        style.backColor = couleurFond
    couleurBordure = _CouleurReportLab(objet.LineColor)
    if couleurBordure is not None:
        style.borderColor = couleurBordure
        style.borderWidth = (objet.LineWidth or 0) * mmPDF
    if objet.PadSize:
        style.borderPadding = objet.PadSize * mmPDF
    return style


def _ObjetDansCadre(modeleDoc, objet, cadre):
    """ Un objet texte placé à l'intérieur du cadre principal porte du
    contenu éditable destiné à s'écouler sur plusieurs pages (articles,
    résumé de planning, ...) ; tout objet hors de ce cadre reste dessiné
    à position fixe par le moteur générique, exactement comme pour les
    autres catégories de document. Règle purement géométrique et
    générique : elle ne connaît rien de "convention". """
    x, y, largeur, hauteur = cadre
    ox, oy, _l, _h = modeleDoc.GetCoordsObjet(objet)
    return (x <= ox <= x + largeur) and (y <= oy <= y + hauteur)


def _SepareObjetsFixesEtFlottants(modeleDoc):
    cadre_principal = modeleDoc.FindObjet("cadre_principal")
    if cadre_principal is None:
        raise ValueError(_(u"Le modèle choisi n'a pas de cadre principal."))
    cadre = modeleDoc.GetCoordsObjet(cadre_principal)
    objetsFlottants = []
    for objet in modeleDoc.listeObjets:
        if objet is cadre_principal or objet.champ == "cadre_pages_suivantes":
            continue
        if objet.categorie == "special" and objet.champ in ("saut_page", "espace_vertical"):
            objetsFlottants.append(objet)
            continue
        if (objet.categorie == "image"
                and objet.champ == "convention_flow_image"
                and _ObjetDansCadre(modeleDoc, objet, cadre)):
            objetsFlottants.append(objet)
            continue
        if "texte" in objet.categorie and _ObjetDansCadre(modeleDoc, objet, cadre):
            objetsFlottants.append(objet)
    return cadre, objetsFlottants


def _GetCadrePagesSuivantes(modeleDoc, cadre_principal):
    objet = modeleDoc.FindObjet("cadre_pages_suivantes")
    return cadre_principal if objet is None else modeleDoc.GetCoordsObjet(objet)


_MARQUEURS_MOJIBAKE = (u"Ã", u"Â", u"â‚", u"â€™", u"â€œ", u"â€", u"�")


def _ValideEncodageModele(modeleDoc):
    suspects = []
    for objet in modeleDoc.listeObjets:
        if "texte" not in objet.categorie:
            continue
        texte = objet.GetTexte() or u""
        if any(marqueur in texte for marqueur in _MARQUEURS_MOJIBAKE):
            suspects.append(objet.nom or u"objet #%s" % getattr(objet, "IDobjet", u"?"))
    if suspects:
        raise ValueError(_(
            u"Le texte du modèle semble déjà mal encodé (UTF-8/mojibake) dans : %s. "
            u"Corrigez ou réimportez ce modèle avant de générer la convention."
        ) % u", ".join(suspects))


def _ImagePlatypus(modeleDoc, objet):
    fichier = io.BytesIO()
    image_wx = objet.Image
    if isinstance(image_wx, wx.Bitmap):
        image_wx = image_wx.ConvertToImage()
    image_wx.SaveFile(fichier, wx.BITMAP_TYPE_PNG)
    fichier.seek(0)
    _x, _y, largeur, hauteur = modeleDoc.GetCoordsObjet(objet)
    image = PlatypusImage(fichier, width=largeur, height=hauteur)
    image.hAlign = "CENTER"
    image._noethys_source = fichier
    return image


def _ConstruitStory(modeleDoc, objetsFlottants, dictChamps):
    _ValideEncodageModele(modeleDoc)
    textes_rendus = []
    for objet in objetsFlottants:
        if "texte" in objet.categorie:
            texte = modeleDoc.GetValeur(objet, dictChamps)
            if texte:
                textes_rendus.append(objet)
    dernier_texte = textes_rendus[-1] if textes_rendus else None
    dernier_element = objetsFlottants[-1] if objetsFlottants else None
    story = []
    for objet in objetsFlottants:
        if objet.categorie == "special" and objet.champ == "saut_page":
            story.append(PageBreak())
            continue
        if objet.categorie == "special" and objet.champ == "espace_vertical":
            _x, _y, _largeur, hauteur = modeleDoc.GetCoordsObjet(objet)
            story.append(Spacer(0, hauteur))
            continue
        if objet.categorie == "image":
            story.append(_ImagePlatypus(modeleDoc, objet))
            continue
        if "texte" not in objet.categorie:
            continue
        texte = modeleDoc.GetValeur(objet, dictChamps)
        if not texte:
            continue
        style = _StyleReportLab(objet)
        groupeObjet = []
        for paragraphe in texte.split(u"\n\n"):
            texte_html = escape(paragraphe).replace(u"\n", u"<br/>")
            if texte_html.strip():
                if objet.Underlined:
                    texte_html = u"<u>%s</u>" % texte_html
                groupeObjet.append(Paragraph(texte_html, style))
        if not groupeObjet:
            continue
        if objet is dernier_texte and objet is dernier_element:
            story.append(KeepTogether(groupeObjet))
        else:
            story.extend(groupeObjet)
    return story


def _DessineObjetsFixes(canvas, modeleDoc, dictChamps, objetsFlottants, dessiner_objets_modele=True):
    canvas.saveState()
    modeleDoc.DessineFond(canvas, dictChamps=dictChamps)
    if dessiner_objets_modele:
        ensembleFlottants = set(id(o) for o in objetsFlottants)
        for objet in modeleDoc.listeObjets:
            if id(objet) in ensembleFlottants:
                continue
            if objet.champ in ("cadre_principal", "cadre_pages_suivantes"):
                continue
            if objet.categorie == "special":
                continue
            valeur = modeleDoc.GetValeur(objet, dictChamps)
            if valeur is False:
                continue
            DLG_Noedoc.DessineObjetPDF(objet, canvas, valeur=valeur)
    canvas.restoreState()


class _GabaritConvention(PageTemplate):
    def __init__(self, cadre, modeleDoc, dictChamps, objetsFlottants,
                 nom="convention", dessiner_objets_modele=True,
                 autoNextPageTemplate=None):
        x, y, largeur, hauteur = cadre
        frame = Frame(x, y, largeur, hauteur, id="F_%s" % nom,
                      leftPadding=0, topPadding=0, rightPadding=0, bottomPadding=0)
        self._modeleDoc = modeleDoc
        self._dictChamps = dictChamps
        self._objetsFlottants = objetsFlottants
        self._dessiner_objets_modele = dessiner_objets_modele
        PageTemplate.__init__(
            self, nom, [frame], self._DessinePage,
            autoNextPageTemplate=autoNextPageTemplate,
        )
    def _DessinePage(self, canvas, doc):
        _DessineObjetsFixes(
            canvas, self._modeleDoc, self._dictChamps, self._objetsFlottants,
            dessiner_objets_modele=self._dessiner_objets_modele,
        )


def GenererPDF(IDmodele, dictChamps, nomDoc=None, afficherDoc=True):
    """ Charge le modèle Noedoc choisi et rend le PDF. Ne contient aucune
    donnée métier : dictChamps est déjà entièrement préparé par
    l'appelant (voir Impression() ci-dessous).

    ModeleDoc.__init__ charge toujours modeleDoc.dictOrganisateur (source
    historique Noedoc, {ORGANISATEUR_NOM}/{ORGANISATEUR_RUE}/...,
    ImportationOrganisateur) : c'est la même source que pour les autres
    catégories de documents, aucune nouvelle requête SQL. GetValeur() ne
    résout que les clés réellement présentes dans le dict qu'on lui donne
    (toute clé absente est silencieusement effacée du texte rendu) : sans
    cette fusion, un modèle Convention utilisant {ORGANISATEUR_*} verrait
    ces champs disparaître du PDF. dictChamps (calculé par
    UTILS_Convention_champs.GetChampsConvention) reste prioritaire sur
    dictOrganisateur en cas de clé identique. """
    modeleDoc = DLG_Noedoc.ModeleDoc(IDmodele=IDmodele)
    dictRendu = dict(modeleDoc.dictOrganisateur)
    dictRendu.update(dictChamps)

    cadre, objetsFlottants = _SepareObjetsFixesEtFlottants(modeleDoc)
    cadre_suivantes = _GetCadrePagesSuivantes(modeleDoc, cadre)
    story = _ConstruitStory(modeleDoc, objetsFlottants, dictRendu)
    if not story:
        raise ValueError(_(u"Le modèle choisi ne contient aucun contenu dans son cadre principal."))

    if nomDoc is None:
        nomDoc = FonctionsPerso.GenerationNomDoc("CONVENTION", "pdf")

    doc = BaseDocTemplate(nomDoc, pagesize=TAILLE_PAGE)
    premiere = _GabaritConvention(
        cadre, modeleDoc, dictRendu, objetsFlottants,
        nom="convention_premiere", dessiner_objets_modele=True,
        autoNextPageTemplate="convention_suivantes",
    )
    suivantes = _GabaritConvention(
        cadre_suivantes, modeleDoc, dictRendu, objetsFlottants,
        nom="convention_suivantes", dessiner_objets_modele=False,
    )
    doc.addPageTemplates([premiere, suivantes])
    doc.build(story)

    if afficherDoc:
        FonctionsPerso.LanceFichierExterne(nomDoc)
    return nomDoc


def Impression(IDfamille=None, IDmodele=None, date_debut=None, date_fin=None,
                saison=None, listeIDindividus=None, nomDoc=None, afficherDoc=True,
                overrides=None):
    """ Point d'entrée : construit les champs depuis les données Noethys
    réelles de la famille, puis délègue tout le rendu au moteur Noedoc.

    Aucun champ n'est obligatoire côté données : un représentant, un
    tarif ou une partie du planning introuvables automatiquement restent
    simplement vides dans le PDF généré (à compléter dans le modèle ou
    en relançant avec des valeurs saisies manuellement), plutôt que de
    bloquer la génération ou d'inventer une valeur.

    overrides : dict optionnel {"{CODE}": valeur} transmis tel quel à
    UTILS_Convention_champs.GetChampsConvention -- les corrections
    saisies par l'utilisateur dans DLG_Generation_convention (nom du
    représentant, fonction, date/lieu de signature, tarif horaire).
    N'écrit jamais rien dans Noethys : ce sont des valeurs de génération
    uniquement, propres à ce PDF.
    """
    if IDfamille is None:
        raise ValueError(_(u"IDfamille obligatoire."))
    if IDmodele is None:
        raise ValueError(_(u"Choisissez un modèle de convention."))

    try:
        champs, dictDonnees = UTILS_Convention_champs.GetChampsConvention(
            IDfamille=IDfamille, date_debut=date_debut, date_fin=date_fin,
            saison=saison, listeIDindividus=listeIDindividus, overrides=overrides,
        )
        nomDocFinal = GenererPDF(IDmodele, champs, nomDoc=nomDoc, afficherDoc=afficherDoc)
    except Exception as err:
        dlg = wx.MessageDialog(
            None, _(u"Impossible de générer la convention.\n\n%s") % err,
            _(u"Convention"), wx.OK | wx.ICON_ERROR,
        )
        dlg.ShowModal()
        dlg.Destroy()
        return False

    return {"nomDoc": nomDocFinal, "champs": champs}