#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Auteur:           Ivan LUCAS
# Copyright:       (c) 2010-11 Ivan LUCAS
# Licence:         Licence GNU GPL
# ------------------------------------------------------------------------


import Chemins
from Utils.UTILS_Traduction import _
import wx
from Ctrl import CTRL_Bouton_image
import sys
import FonctionsPerso
import datetime

from Utils import UTILS_Organisateur
from Utils import UTILS_Config
from Utils import UTILS_Customize
SYMBOLE = UTILS_Config.GetParametre("monnaie_symbole", u"€")


def DateEngFr(textDate):
    text = str(textDate[8:10]) + "/" + \
        str(textDate[5:7]) + "/" + str(textDate[:4])
    return text


def LabelEtat(etat):
    """ Traduit un code etat de consommation en libellé humain (voir CTRL_Grille.CreationPDF) """
    return {
        "reservation": _(u"Réservation"),
        "absenti": _(u"Absence injustifiée"),
        "absentj": _(u"Absence justifiée"),
        "present": _(u"Présent"),
        "attente": _(u"Attente"),
        "refus": _(u"Refus"),
    }.get(etat, etat)


def GetDonnees(listeIDindividus=[], date_debut=None, date_fin=None, DB=None):
    """ Reconstitue, à partir de la base, le dict Individu>Activite>Date>Unite
    attendu par Impression(), sans dépendre d'une grille CTRL_Grille déjà
    chargée en mémoire.

    C'est l'extraction générique la plus basse permettant de produire le
    même rapport Réservations depuis n'importe quel écran (grille de
    saisie historique, génération de convention, ...) : la seule
    différence avec CTRL_Grille.CreationPDF() est la façon dont les
    consommations sont récupérées (requête directe ici, cache mémoire de
    la grille là-bas). Le format du dict et le rendu produit par
    Impression() restent strictement identiques.
    """
    if not listeIDindividus:
        return {}

    fermer_connexion = DB is None
    if DB is None:
        import GestionDB
        DB = GestionDB.DB()

    from Data import DATA_Civilites
    dictCivilites = DATA_Civilites.GetDictCivilites()

    placeholders = ", ".join(str(int(IDindividu)) for IDindividu in listeIDindividus)
    req = """
        SELECT consommations.IDindividu, consommations.IDactivite, consommations.date,
            consommations.IDunite, consommations.heure_debut, consommations.heure_fin,
            consommations.etat, consommations.IDgroupe, consommations.IDprestation,
            individus.nom, individus.prenom, individus.date_naiss, individus.IDcivilite,
            activites.nom,
            unites.nom, unites.ordre, unites.type,
            prestations.montant, prestations.label
        FROM consommations
        LEFT JOIN individus ON individus.IDindividu = consommations.IDindividu
        LEFT JOIN activites ON activites.IDactivite = consommations.IDactivite
        LEFT JOIN unites ON unites.IDunite = consommations.IDunite
        LEFT JOIN prestations ON prestations.IDprestation = consommations.IDprestation
        WHERE consommations.IDindividu IN (%s)
        AND (consommations.etat IS NULL OR consommations.etat <> 'refus')
    """ % placeholders
    if date_debut is not None:
        req += " AND consommations.date >= '%s'" % str(date_debut)
    if date_fin is not None:
        req += " AND consommations.date <= '%s'" % str(date_fin)
    req += " ORDER BY consommations.date, consommations.heure_debut;"
    DB.ExecuterReq(req)
    listeConsommations = DB.ResultatReq()

    req = "SELECT IDactivite, agrement, date_debut, date_fin FROM agrements ORDER BY date_debut;"
    DB.ExecuterReq(req)
    listeAgrements = DB.ResultatReq()

    if fermer_connexion:
        DB.Close()

    def RechercheAgrement(IDactivite, date):
        for IDactiviteTmp, agrement, debut, fin in listeAgrements:
            if IDactivite == IDactiviteTmp and str(date) >= debut and str(date) <= fin:
                return agrement
        return None

    dictDonnees = {}
    for (IDindividu, IDactivite, date, IDunite, heure_debut, heure_fin, etat, IDgroupe,
         IDprestation, nom, prenom, date_naiss, IDcivilite, nomActivite, nomUnite,
         ordreUnite, typeUnite, montant, label) in listeConsommations:

        sexe = dictCivilites.get(IDcivilite, {}).get("sexe")

        agrement = RechercheAgrement(IDactivite, date)
        if agrement is not None:
            agrement = _(u" - n° agrément : %s") % agrement

        if IDindividu not in dictDonnees:
            dictDonnees[IDindividu] = {
                "nom": nom, "prenom": prenom, "date_naiss": date_naiss,
                "sexe": sexe, "activites": {},
            }
        dictActivites = dictDonnees[IDindividu]["activites"]
        if IDactivite not in dictActivites:
            dictActivites[IDactivite] = {"nom": nomActivite, "agrement": agrement, "dates": {}}
        dictDates = dictActivites[IDactivite]["dates"]
        if date not in dictDates:
            dictDates[date] = {"unites": {}}
        dictUnites = dictDates[date]["unites"]
        if IDunite not in dictUnites:
            dictUnites[IDunite] = []

        if montant is not None:
            # "paye" (montant déjà ventilé/réglé) n'est volontairement pas
            # recalculé ici : cette information de règlement n'est pas
            # nécessaire pour un planning/convention prévisionnel, et sa
            # reconstitution demanderait de rejouer la logique de
            # ventilation des règlements, hors périmètre de cette extraction.
            prestation = {"montant": montant, "label": label, "paye": None}
        else:
            prestation = None

        dictUnites[IDunite].append({
            "nomUnite": nomUnite, "ordreUnite": ordreUnite, "etat": LabelEtat(etat),
            "IDgroupe": IDgroupe, "IDprestation": IDprestation, "prestation": prestation,
            "type": typeUnite, "heure_debut": heure_debut, "heure_fin": heure_fin,
            "evenement": None,
        })

    return dictDonnees


def Impression(dictDonnees={}, nomDoc=FonctionsPerso.GenerationNomDoc("RESERVATIONS", "pdf"), afficherDoc=True):
    # Création du PDF
    from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate, NextPageTemplate
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.platypus.flowables import ParagraphAndImage, Image
    from reportlab.platypus.frames import Frame
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import inch, cm, mm
    from reportlab.lib.utils import ImageReader
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.pdfgen.canvas import Canvas

    TAILLE_PAGE = A4
    LARGEUR_PAGE = TAILLE_PAGE[0]
    HAUTEUR_PAGE = TAILLE_PAGE[1]

    # Initialisation du document
    if sys.platform.startswith("win"):
        nomDoc = nomDoc.replace("/", "\\")
    doc = SimpleDocTemplate(
        nomDoc, topMargin=30, bottomMargin=30, pagesize=TAILLE_PAGE, showBoundary=False)
    story = []
    dictChampsFusion = {}

    largeurContenu = 520
    couleurFond = (0.8, 0.8, 1)
    couleurFondActivite = (0.92, 0.92, 1)

    # Création du titre du document
    def Header():
        dataTableau = []
        largeursColonnes = ((420, 100))
        dateDuJour = DateEngFr(str(datetime.date.today()))
        dataTableau.append((_(u"Réservations"), _(u"%s\nEdité le %s") % (
            UTILS_Organisateur.GetNom(), dateDuJour)))
        style = TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.25, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('FONT', (0, 0), (0, 0), "Helvetica-Bold", 16),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('FONT', (1, 0), (1, 0), "Helvetica", 6),
        ])
        tableau = Table(dataTableau, largeursColonnes)
        tableau.setStyle(style)
        story.append(tableau)
        story.append(Spacer(0, 20))

    # Insère un header
    Header()

    # Texte si aucune réservation
    if len(dictDonnees) == 0:
        paraStyle = ParagraphStyle(
            name="defaut", fontName="Helvetica", fontSize=11)
        story.append(Paragraph("&nbsp;", paraStyle))
        story.append(Paragraph("&nbsp;", paraStyle))
        story.append(Paragraph(
            _(u"<para align='centre'><b>Aucune réservation</b></para>"), paraStyle))

    # Tableau NOM INDIVIDU
    totalFacturationFamille = 0.0
    for IDindividu, dictIndividu in dictDonnees.items():
        nom = dictIndividu["nom"]
        prenom = dictIndividu["prenom"]
        date_naiss = dictIndividu["date_naiss"]
        sexe = dictIndividu["sexe"]
        if date_naiss != None:
            if sexe == "M":
                texteNaiss = _(u", né le %s") % DateEngFr(str(date_naiss))
            else:
                texteNaiss = _(u", née le %s") % DateEngFr(str(date_naiss))
        else:
            texteNaiss = u""
        texteIndividu = u"%s %s%s" % (nom, prenom, texteNaiss)

        totalFacturationIndividu = 0.0

        # Insertion du nom de l'individu
        paraStyle = ParagraphStyle(name="individu",
                                   fontName="Helvetica",
                                   fontSize=9,
                                   # leading=7,
                                   spaceBefore=0,
                                   spaceafter=0,
                                   )
        texteIndividu = Paragraph(texteIndividu, paraStyle)
        dataTableau = []
        dataTableau.append([texteIndividu,])
        tableau = Table(dataTableau, [largeurContenu,])
        listeStyles = [
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONT', (0, 0), (-1, -1), "Helvetica", 8),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), couleurFond),
        ]
        tableau.setStyle(TableStyle(listeStyles))
        story.append(tableau)

        # Tableau NOM ACTIVITE
        listePrestationsUtilisees = []
        for IDactivite, dictActivite in dictIndividu["activites"].items():
            texteActivite = dictActivite["nom"]
            if dictActivite["agrement"] != None:
                texteActivite += dictActivite["agrement"]

            if texteActivite != None:
                dataTableau = []
                dataTableau.append([texteActivite,])
                tableau = Table(dataTableau, [largeurContenu,])
                listeStyles = [
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONT', (0, 0), (-1, -1), "Helvetica", 6),
                    ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('BACKGROUND', (0, 0), (-1, 0), couleurFondActivite),
                ]
                tableau.setStyle(TableStyle(listeStyles))
                story.append(tableau)

            # Colonnes : Date, Consos, Etat, Prestations, Montant
            dataTableau = []
            largeursColonnes = [55, 165, 80, 160, 60]
            dataTableau.append([_(u"Date"), _(u"Consommations"), _(
                u"Etat"), _(u"Prestations"), _(u"Total")])

            paraStyle = ParagraphStyle(name="standard",
                                       fontName="Helvetica",
                                       fontSize=8,
                                       leading=10,
                                       # spaceBefore=8,
                                       spaceAfter=0,
                                       )

            # lignes DATES
            listeDates = []
            for date, dictDates in dictActivite["dates"].items():
                listeDates.append(date)
            listeDates.sort()

            for date in listeDates:
                dictDate = dictActivite["dates"][date]
                listeLigne = []

                # Insertion de la date
                texteDate = Paragraph(DateEngFr(str(date)), paraStyle)

                # Insertion des consommations
                listeEtats = []
                listeEtatsTemp = []
                listeConso = []
                listePrestations = []
                for IDunite, liste_unites in dictDate["unites"].items():
                    for dictUnite in liste_unites:
                        etat = dictUnite["etat"]
                        nomUnite = dictUnite["nomUnite"]
                        if dictUnite["evenement"]:
                            nomUnite = dictUnite["evenement"].nom

                        if etat != None:
                            labelUnite = nomUnite
                            afficher_horaires = UTILS_Customize.GetValeur(
                                "impression_consommations", "afficher_horaires", "1", ajouter_si_manquant=False) in ("1", None)
                            if afficher_horaires:
                                if dictUnite["type"] == "Horaire" or (dictUnite["type"] == "Evenement" and dictUnite["heure_debut"] and dictUnite["heure_fin"] and dictUnite["heure_debut"] != "00:00" and dictUnite["heure_fin"] != "00:00"):
                                    heure_debut = dictUnite["heure_debut"]
                                    if heure_debut == None:
                                        heure_debut = u"?"
                                    heure_debut = heure_debut.replace(":", "h")
                                    heure_fin = dictUnite["heure_fin"]
                                    if heure_fin == None:
                                        heure_fin = u"?"
                                    heure_fin = heure_fin.replace(":", "h")
                                    labelUnite += _(u" (%s-%s)") % (
                                        heure_debut, heure_fin)
                            listeConso.append(labelUnite)

                            if etat not in listeEtatsTemp:
                                if etat == "Attente":
                                    listeEtats.append(ParagraphAndImage(Paragraph(etat, paraStyle), Image(Chemins.GetStaticPath(
                                        "Images/16x16/Attention.png"), width=8, height=8), xpad=1, ypad=1, side="left"))
                                else:
                                    listeEtats.append(
                                        Paragraph(etat, paraStyle))
                                listeEtatsTemp.append(etat)

                            IDprestation = dictUnite["IDprestation"]
                            if dictUnite["prestation"] != None and IDprestation not in listePrestationsUtilisees:
                                listePrestations.append(
                                    dictUnite["prestation"])
                                listePrestationsUtilisees.append(IDprestation)

                texteConsos = Paragraph("<br/>".join(listeConso), paraStyle)

                # Insertion de l'état
                texteEtat = listeEtats

                # Insertion des prestations et montants
                textePrestations = []
                texteMontants = []
                for dictPrestation in listePrestations:
                    montant = dictPrestation["montant"]
                    label = dictPrestation["label"]
                    paye = dictPrestation["paye"]
                    textePrestations.append(Paragraph(label, paraStyle))
                    texteMontants.append(Paragraph(
                        u"<para align='right'>%.02f %s</para>" % (montant, SYMBOLE), paraStyle))

                    # Pour le total par individu :
                    if montant != None:
                        totalFacturationIndividu += montant
                        totalFacturationFamille += montant

                if len(listeConso) > 0:
                    dataTableau.append(
                        [texteDate, texteConsos, texteEtat, textePrestations, texteMontants])

            if len(dataTableau) == 1:
                dlg = wx.MessageDialog(None, _(u"Il n'y a aucune consommation à imprimer !"), _(
                    u"Erreur"), wx.OK | wx.ICON_INFORMATION)
                dlg.ShowModal()
                dlg.Destroy()
                return

            tableau = Table(dataTableau, largeursColonnes)
            listeStyles = [
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.black),

                ('FONT', (0, 0), (-1, 0), "Helvetica", 6),
                ('ALIGN', (0, 0), (-1, 0), 'CENTRE'),

                ('FONT', (0, 1), (-1, 1), "Helvetica", 8),
            ]
            tableau.setStyle(TableStyle(listeStyles))
            story.append(tableau)

        # Insertion du total par individu
        dataTableau = []
        montantIndividu = Paragraph(
            u"<para align='right'>%.02f %s</para>" % (totalFacturationIndividu, SYMBOLE), paraStyle)
        dataTableau.append(
            [Paragraph(_(u"<para align='right'>Total :</para>"), paraStyle), montantIndividu])

        listeStyles = [
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONT', (0, 0), (-1, -1), "Helvetica", 8),
            ('GRID', (-1, -1), (-1, -1), 0.25, colors.black),
            ('ALIGN', (-1, -1), (-1, -1), 'CENTRE'),
            ('BACKGROUND', (-1, -1), (-1, -1), couleurFond),
        ]

        # Création du tableau
        largeursColonnesTotal = [460, 60]
        tableau = Table(dataTableau, largeursColonnesTotal)
        tableau.setStyle(TableStyle(listeStyles))
        story.append(tableau)
        story.append(Spacer(0, 12))

    # Total facturation Famille
    nbreIndividus = len(dictDonnees)
    if nbreIndividus > 1:
        dataTableau = []
        montantFamille = Paragraph(
            u"<para align='right'>%.02f %s</para>" % (totalFacturationFamille, SYMBOLE), paraStyle)
        dataTableau.append(
            [Paragraph(_(u"<para align='right'>TOTAL :</para>"), paraStyle), montantFamille])
        largeursColonnesTotal = [460, 60]
        tableau = Table(dataTableau, largeursColonnesTotal)
        tableau.setStyle(TableStyle(listeStyles))
        story.append(tableau)

    # Champs pour fusion Email
    dictChampsFusion["{SOLDE}"] = u"%.02f %s" % (
        totalFacturationFamille, SYMBOLE)

    # Enregistrement et ouverture du PDF
    try:
        doc.build(story)
    except Exception as err:
        print("Erreur dans ouverture PDF :", err)
        if "Permission denied" in err:
            dlg = wx.MessageDialog(None, _(
                u"Noethys ne peut pas créer le PDF.\n\nVeuillez vérifier qu'un autre PDF n'est pas déjà ouvert en arrière-plan..."), _(u"Erreur d'édition"), wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return False

    if afficherDoc == True:
        FonctionsPerso.LanceFichierExterne(nomDoc)

    return dictChampsFusion