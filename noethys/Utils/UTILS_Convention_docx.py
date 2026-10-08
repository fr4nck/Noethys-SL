#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Génération d'une convention modifiable depuis un modèle Word ``.docx``.

Le fichier modèle reste un document Office Open XML normal. Les champs
Noethys sont remplacés dans le corps, les tableaux, les zones de texte, les
en-têtes et les pieds de page. La mise en page et les ressources du document
sont conservées. Le moteur utilise ``lxml``, déjà requis par Noethys : Word
ou LibreOffice ne sont nécessaires que pour modifier le résultat.
"""

from __future__ import annotations

import datetime
import os
import re
import tempfile
import zipfile
from decimal import Decimal

import wx
from lxml import etree

import FonctionsPerso
import GestionDB
from Utils import UTILS_Convention_champs
from Utils.UTILS_Traduction import _


NS_WORD = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_XML = "http://www.w3.org/XML/1998/namespace"
NAMESPACES = {"w": NS_WORD}
PARTIES_TEXTE = re.compile(
    r"^word/(?:document|header\d*|footer\d*|footnotes|endnotes|comments)\.xml$"
)
# Forme des mots-clés Noethys ({FAMILLE_NOM}, {CONVENTION_SAISON}...).
MOT_CLE = re.compile(r"\{[A-Z][A-Z0-9_]*\}")


def _TexteValeur(valeur):
    """Normalise une valeur métier pour son insertion dans Word."""
    if valeur is None:
        return u""
    if isinstance(valeur, datetime.datetime):
        valeur = valeur.date()
    if isinstance(valeur, datetime.date):
        return valeur.strftime("%d/%m/%Y")
    if isinstance(valeur, Decimal):
        return format(valeur, "f").replace(".", ",")
    if isinstance(valeur, float):
        texte = (u"%.2f" % valeur).rstrip("0").rstrip(".")
        return texte.replace(".", ",")
    return str(valeur)


def _GetChampsOrganisateur():
    """Retourne les champs organisateur historiques utilisés par Noedoc."""
    DB = GestionDB.DB()
    DB.ExecuterReq("""SELECT nom, rue, cp, ville, tel, fax, mail, site,
                             num_agrement, num_siret, code_ape
                      FROM organisateur WHERE IDorganisateur=1;""")
    lignes = DB.ResultatReq()
    DB.Close()
    if not lignes:
        return {}
    nom, rue, cp, ville, tel, fax, mail, site, agrement, siret, ape = lignes[0]
    return {
        "{ORGANISATEUR_NOM}": nom,
        "{ORGANISATEUR_RUE}": rue,
        "{ORGANISATEUR_CP}": cp,
        "{ORGANISATEUR_VILLE}": ville.capitalize() if ville else ville,
        "{ORGANISATEUR_TEL}": tel,
        "{ORGANISATEUR_FAX}": fax,
        "{ORGANISATEUR_MAIL}": mail,
        "{ORGANISATEUR_SITE}": site,
        "{ORGANISATEUR_AGREMENT}": agrement,
        "{ORGANISATEUR_SIRET}": siret,
        "{ORGANISATEUR_APE}": ape,
    }


def _TrouverNoeud(noeuds, position, fin=False):
    """Trouve le ``w:t`` et l'offset dans le texte concaténé."""
    curseur = 0
    for index, noeud in enumerate(noeuds):
        texte = noeud.text or u""
        limite = curseur + len(texte)
        if position < limite or (fin and position == limite and texte):
            return index, position - curseur
        curseur = limite
    return len(noeuds) - 1, len(noeuds[-1].text or u"")


def _PreserverEspaces(noeud):
    texte = noeud.text or u""
    cle = "{%s}space" % NS_XML
    if texte.startswith((" ", "\t")) or texte.endswith((" ", "\t")):
        noeud.set(cle, "preserve")
    else:
        noeud.attrib.pop(cle, None)


def _InsererRetoursLigne(noeud):
    """Convertit les retours présents dans un champ en ``w:br`` Word."""
    texte = noeud.text or u""
    if "\n" not in texte:
        _PreserverEspaces(noeud)
        return
    parent = noeud.getparent()
    if parent is None or parent.tag != "{%s}r" % NS_WORD:
        return
    morceaux = texte.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    noeud.text = morceaux[0]
    _PreserverEspaces(noeud)
    position = parent.index(noeud) + 1
    for morceau in morceaux[1:]:
        parent.insert(position, etree.Element("{%s}br" % NS_WORD))
        position += 1
        nouveau = etree.Element("{%s}t" % NS_WORD)
        nouveau.text = morceau
        _PreserverEspaces(nouveau)
        parent.insert(position, nouveau)
        position += 1


def _RemplacerDansParagraphe(paragraphe, remplacements):
    """Remplace les champs même lorsqu'ils sont découpés entre plusieurs runs."""
    noeuds = paragraphe.xpath(".//w:t", namespaces=NAMESPACES)
    if not noeuds:
        return 0
    texte = u"".join(noeud.text or u"" for noeud in noeuds)
    champs = [champ for champ in remplacements if champ in texte]
    if not champs:
        return 0
    motif = re.compile("|".join(
        re.escape(champ) for champ in sorted(champs, key=len, reverse=True)
    ))
    occurrences = list(motif.finditer(texte))
    for occurrence in reversed(occurrences):
        debut, fin = occurrence.span()
        index_debut, offset_debut = _TrouverNoeud(noeuds, debut)
        index_fin, offset_fin = _TrouverNoeud(noeuds, fin, fin=True)
        premier = noeuds[index_debut]
        dernier = noeuds[index_fin]
        valeur = remplacements[occurrence.group(0)]
        prefixe = (premier.text or u"")[:offset_debut]
        suffixe = (dernier.text or u"")[offset_fin:]
        if premier is dernier:
            premier.text = prefixe + valeur + suffixe
        else:
            premier.text = prefixe + valeur
            for index in range(index_debut + 1, index_fin):
                noeuds[index].text = u""
            dernier.text = suffixe
    for noeud in list(noeuds):
        _InsererRetoursLigne(noeud)
    return len(occurrences)


def _RemplacerPartieXML(contenu, remplacements, inconnus=None):
    """Remplace les champs d'une partie XML. Les mots-clés du modèle absents
    de ``remplacements`` sont ajoutés à ``inconnus`` (lus avant remplacement :
    une valeur insérée n'est jamais prise pour un mot-clé)."""
    parseur = etree.XMLParser(resolve_entities=False, no_network=True, recover=False)
    racine = etree.fromstring(contenu, parser=parseur)
    total = 0
    for paragraphe in racine.xpath(".//w:p", namespaces=NAMESPACES):
        if inconnus is not None:
            texte = u"".join(noeud.text or u"" for noeud in paragraphe.xpath(".//w:t", namespaces=NAMESPACES))
            inconnus.update(champ for champ in MOT_CLE.findall(texte) if champ not in remplacements)
        total += _RemplacerDansParagraphe(paragraphe, remplacements)
    if not total:
        return contenu, 0
    return etree.tostring(
        racine, xml_declaration=True, encoding="UTF-8", standalone=True
    ), total


def GenererDOCX(modele, dictChamps, nomDoc=None, afficherDoc=True):
    """Crée une copie Word du modèle avec les champs remplacés."""
    modele = os.path.abspath(os.fspath(modele))
    if not modele.lower().endswith(".docx"):
        raise ValueError(_(u"Le modèle doit être un document Word au format .docx."))
    if not os.path.isfile(modele):
        raise ValueError(_(u"Le modèle Word sélectionné est introuvable."))
    if not zipfile.is_zipfile(modele):
        raise ValueError(_(u"Le fichier sélectionné n'est pas un document .docx valide."))
    if nomDoc is None:
        nomDoc = FonctionsPerso.GenerationNomDoc("CONVENTION", "docx")
    nomDoc = os.path.abspath(os.fspath(nomDoc))
    if os.path.normcase(modele) == os.path.normcase(nomDoc):
        raise ValueError(_(u"Le document généré ne peut pas écraser le modèle Word."))

    remplacements = {
        champ: _TexteValeur(valeur) for champ, valeur in dictChamps.items()
    }

    # Tout est préparé en mémoire avant d'écrire : un modèle invalide ou un
    # mot-clé inconnu ne crée ni ne modifie aucun fichier.
    total = 0
    inconnus = set()
    parties = []
    try:
        with zipfile.ZipFile(modele, "r") as source:
            for info in source.infolist():
                contenu = source.read(info.filename)
                if PARTIES_TEXTE.match(info.filename) and b"<w:t" in contenu:
                    contenu, compteur = _RemplacerPartieXML(contenu, remplacements, inconnus)
                    total += compteur
                parties.append((info, contenu))
    except (OSError, zipfile.BadZipFile, etree.XMLSyntaxError) as err:
        raise ValueError(_(u"Le modèle Word n'a pas pu être lu : %s") % err)
    if inconnus:
        raise ValueError(_(u"Le modèle Word contient des mots-clés inconnus : %s.\n"
                           u"Corrigez-les dans le modèle (voir la liste des champs de Noedoc).")
                         % u", ".join(sorted(inconnus)))
    if total == 0:
        raise ValueError(_(u"Le modèle Word ne contient aucun champ Noethys reconnu."))

    # Écriture atomique : fichier temporaire dans le même dossier, puis
    # remplacement en une opération. Un document existant reste intact en
    # cas d'échec (disque plein, document ouvert dans Word...).
    descripteur, temporaire = tempfile.mkstemp(
        prefix=u".~", suffix=u".docx", dir=os.path.dirname(nomDoc) or None
    )
    os.close(descripteur)
    try:
        with zipfile.ZipFile(temporaire, "w") as destination:
            for info, contenu in parties:
                destination.writestr(info, contenu)
        os.replace(temporaire, nomDoc)
    except OSError as err:
        raise ValueError(_(u"Le document Word n'a pas pu être enregistré : %s") % err)
    finally:
        if os.path.exists(temporaire):
            try:
                os.remove(temporaire)
            except OSError:
                pass
    if afficherDoc:
        FonctionsPerso.LanceFichierExterne(nomDoc)
    return nomDoc


def Impression(IDfamille=None, modele=None, date_debut=None, date_fin=None,
               saison=None, listeIDindividus=None, nomDoc=None, afficherDoc=True,
               overrides=None):
    """Construit les champs Convention puis génère le document Word."""
    if IDfamille is None:
        raise ValueError(_(u"IDfamille obligatoire."))
    if not modele:
        raise ValueError(_(u"Choisissez un modèle Word de convention."))
    try:
        champs, _dictDonnees = UTILS_Convention_champs.GetChampsConvention(
            IDfamille=IDfamille, date_debut=date_debut, date_fin=date_fin,
            saison=saison, listeIDindividus=listeIDindividus, overrides=overrides,
        )
        rendu = _GetChampsOrganisateur()
        rendu.update(champs)
        nomFinal = GenererDOCX(
            modele, rendu, nomDoc=nomDoc, afficherDoc=afficherDoc
        )
    except Exception as err:
        dlg = wx.MessageDialog(
            None, _(u"Impossible de générer la convention Word.\n\n%s") % err,
            _(u"Convention"), wx.OK | wx.ICON_ERROR,
        )
        dlg.ShowModal()
        dlg.Destroy()
        return False
    return {"nomDoc": nomFinal, "champs": champs}
