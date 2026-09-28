#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Auteur:           Ivan LUCAS
# Copyright:       (c) 2010-11 Ivan LUCAS
# Licence:         Licence GNU GPL
#------------------------------------------------------------------------


import Chemins
from Utils.UTILS_Traduction import _
import wx
import socket
import os
import sys
import time
import GestionDB
import FonctionsPerso
import re
import traceback
import base64
from Utils import UTILS_Html2text
from Utils import UTILS_Titulaires
from Utils import UTILS_Parametres
from Dlg import DLG_Messagebox

import smtplib
import six
from six.moves.email_mime_multipart import MIMEMultipart
from six.moves.email_mime_base import MIMEBase
from six.moves.email_mime_text import MIMEText
from six.moves.email_mime_image import MIMEImage
from email.utils import COMMASPACE, formatdate
from email.header import Header
from email.utils import formatdate, formataddr
from email import encoders
import mimetypes

from Outils import mail

# Import pour permettre compilation windows
from Outils.mail import base, smtp

def _TexteUtf8(valeur):
    """Normalise en texte Python 3 sans masquer l'erreur d'origine."""
    if isinstance(valeur, bytes):
        return valeur.decode("utf-8", errors="replace")
    return six.text_type(valeur)




def EnvoiEmailFamille(parent=None, IDfamille=None, nomDoc="", categorie="", listeAdresses=[], visible=True, log=None, CreationPDF=None, IDmodele=None):
    # Création du PDF
    if CreationPDF != None :
        temp = CreationPDF
    else :
        temp = parent.CreationPDF
    dictChamps = temp(nomDoc=nomDoc, afficherDoc=False)
    if dictChamps == False :
        return False

    if nomDoc != False :
        liste_pieces = [nomDoc,]
    else :
        liste_pieces = []

    # Recherche adresse famille
    if len(listeAdresses) == 0 :
        listeAdresses = GetAdresseFamille(IDfamille)
        if listeAdresses == False or len(listeAdresses) == 0 :
            return False
    
    # DLG Mailer
    listeDonnees = []
    for adresse in listeAdresses :
        listeDonnees.append({
            "adresse" : adresse, 
            # "pieces" : liste_pieces,
            "champs" : dictChamps,
            })
    from Dlg import DLG_Mailer
    dlg = DLG_Mailer.Dialog(parent, categorie=categorie, afficher_confirmation_envoi=visible)
    dlg.SetDonnees(listeDonnees, modificationAutorisee=True)
    dlg.SetPiecesJointes(liste_pieces)
    if IDmodele == None :
        dlg.ChargerModeleDefaut()
    else :
        dlg.ChargerModele(IDmodele)

    if visible == True :
        # Fenêtre visible
        dlg.ShowModal()

    else :
        # Fenêtre cachée
        dlg.OnBoutonEnvoyer(None)

    if len(dlg.listeSucces) > 0 :
        resultat = True
        if log : log.EcritLog(_(u"L'Email a été envoyé avec succès."))
    else :
        resultat = False
        if log : log.EcritLog(_(u"L'email n'a pas été envoyé."))

    dlg.Destroy()

    # Suppression du PDF temporaire
    if nomDoc != False :
        try :
            os.remove(nomDoc)
        except :
            pass

    return resultat



def ValidationEmail(email):
    if re.match("^.+\\@(\\[?)[a-zA-Z0-9\\-\\.]+\\.([a-zA-Z]{2,3}|[0-9]{1,3})(\\]?)$", email) != None:
        return True
    else :
        return False


def GetAdresseExpDefaut():
    """ Retourne les paramètres de l'adresse d'expéditeur par défaut """
    return GetAdresseExp(IDadresse=None)

def GetAdresseExp(IDadresse=None):
    """ Si IDadresse = None, retourne l'adresse par défaut"""
    if IDadresse == None :
        condition = "defaut=1"
    else :
        condition = "IDadresse=%d" % IDadresse
    # Récupération des données
    DB = GestionDB.DB()        
    req = """SELECT IDadresse, moteur, adresse, nom_adresse, motdepasse, smtp, port, defaut, connexionAuthentifiee, startTLS, utilisateur, parametres
    FROM adresses_mail WHERE %s ORDER BY adresse;""" % condition
    DB.ExecuterReq(req)
    listeDonnees = DB.ResultatReq()
    DB.Close()
    if len(listeDonnees) == 0 : return None
    IDadresse, moteur, adresse, nom_adresse, motdepasse, smtp, port, defaut, auth, startTLS, utilisateur, parametres = listeDonnees[0]
    dictAdresse = {"adresse":adresse, "moteur": moteur, "nom_adresse":nom_adresse, "motdepasse":motdepasse,
                   "smtp":smtp, "port":port, "auth" : auth, "startTLS":startTLS, "utilisateur" : utilisateur, "parametres": parametres}
    return dictAdresse

def GetAdresseFamille(IDfamille=None, choixMultiple=True, muet=False, nomTitulaires=None):
    """ Récupère l'adresse email de la famille """
    # Récupération du nom de la famille
    if nomTitulaires == None :
        dictTitulaires = UTILS_Titulaires.GetTitulaires([IDfamille,])
        if IDfamille in dictTitulaires:
            nomTitulaires = dictTitulaires[IDfamille]["titulairesSansCivilite"]
        else :
            nomTitulaires = _(u"Famille inconnue")
    # Récupération des adresses mails de chaque membre de la famille
    DB = GestionDB.DB()
    req = """
    SELECT 
    rattachements.IDindividu, IDcategorie,
    individus.nom, individus.prenom, individus.mail, individus.travail_mail
    FROM rattachements 
    LEFT JOIN individus ON individus.IDindividu = rattachements.IDindividu
    WHERE IDcategorie=1 AND titulaire=1 AND IDfamille=%d
    ;""" % IDfamille
    DB.ExecuterReq(req)
    listeDonnees = DB.ResultatReq()
    DB.Close() 
    listeAdresses = []
    listeTemp = []
    for IDindividu,  IDcategorie, nom, prenom, mailPerso, mailTravail in listeDonnees :
        if mailPerso != None and mailPerso != "" and mailPerso not in listeTemp :
            listeAdresses.append((_(u"%s (Adresse perso de %s)") % (mailPerso, prenom), mailPerso))
            listeTemp.append(mailPerso)
        if mailTravail != None and mailTravail != "" and mailTravail not in listeTemp :
            listeAdresses.append((_(u"%s (Adresse pro de %s)") % (mailTravail, prenom), mailTravail))
            listeTemp.append(mailTravail)
    if len(listeAdresses) == 0 :
        if muet == False :
            dlg = wx.MessageDialog(None, _(u"Aucun titulaire de la famille de %s ne dispose d'adresse mail !") % nomTitulaires, "Erreur", wx.OK | wx.ICON_EXCLAMATION)
            dlg.ShowModal()
            dlg.Destroy()
        return []
    elif len(listeAdresses) == 1 :
        listeMails = [listeAdresses[0][1],]
    else:
        listeLabels = []
        listeMails = []
        for label, adresse in listeAdresses :
            listeLabels.append(label)
        if choixMultiple == True :
            dlg = wx.MultiChoiceDialog(None, _(u"%d adresses internet sont disponibles pour la famille de %s.\nSélectionnez celles que vous souhaitez utiliser puis cliquez sur le bouton 'Ok' :") % (len(listeAdresses), nomTitulaires), _(u"Choix d'adresses Emails"), listeLabels)
        else :
            dlg = wx.SingleChoiceDialog(None, _(u"%d adresses internet sont disponibles pour la famille de %s.\nSélectionnez celle que vous souhaitez utiliser puis cliquez sur le bouton 'Ok' :") % (len(listeAdresses), nomTitulaires), _(u"Choix d'une adresse Email"), listeLabels)
        dlg.SetSize((450, -1))
        dlg.CenterOnScreen() 
        if dlg.ShowModal() == wx.ID_OK :
            if choixMultiple == True :
                selections = dlg.GetSelections()
            else :
                selections = [dlg.GetSelection(),]
            dlg.Destroy()
            if len(selections) == 0 :
                dlg = wx.MessageDialog(None, _(u"Vous n'avez sélectionné aucune adresse mail !"), "Erreur", wx.OK | wx.ICON_EXCLAMATION)
                dlg.ShowModal()
                dlg.Destroy()
                return []
            for index in selections :
                listeMails.append(listeAdresses[index][1])
        else:
            dlg.Destroy()
            return False
    
    if choixMultiple == True :
        return listeMails
    else :
        return listeMails[0]

# -------------------------------------------------------------------------------------------------------

def GetAdressesFamilles(liste_IDfamille=[]):
    dictTitulaires = UTILS_Titulaires.GetTitulaires()

    # Sélection des adresses mail
    liste_actions = [
        ("all", _(u"Toutes les adresses de la famille")),
        ("one_perso_first", _(u"Une seule adresse par famille (perso en priorité)")),
        ("one_pro_first", _(u"Une seule adresse par famille (pro en priorité)")),
        ("all_perso", _(u"Toutes les adresses personnelles de la famille")),
        ("all_pro", _(u"Toutes les adresses professionnelles de la famille")),
        ("all_perso_first", _(u"Toutes les adresses personnelles de la famille en priorité")),
        ("all_pro_first", _(u"Toutes les adresses professionnelles de la famille en priorité")),
        ("selection", _(u"Je veux sélectionner les adresses pour chaque famille")),
        ]
    dlg = wx.SingleChoiceDialog(None, u"Quelles adresses internet souhaitez-vous utiliser ?", u"Sélection des adresses", [label for code, label in liste_actions], wx.CHOICEDLG_STYLE)
    dlg.SetSize((350, 240))
    dlg.CenterOnScreen()
    if dlg.ShowModal() == wx.ID_OK:
        code_action = liste_actions[dlg.GetSelection()][0]
        dlg.Destroy()
    else:
        dlg.Destroy()
        return False

    # Importation des toutes les adresses existantes
    DB = GestionDB.DB()
    req = """
    SELECT IDfamille, rattachements.IDindividu,
    individus.nom, individus.prenom, individus.mail, individus.travail_mail
    FROM rattachements 
    LEFT JOIN individus ON individus.IDindividu = rattachements.IDindividu
    WHERE IDcategorie=1 AND titulaire=1
    ;"""
    DB.ExecuterReq(req)
    liste_adresses = DB.ResultatReq()
    DB.Close()
    dict_individus = {}
    for IDfamille, IDindividu, nom, prenom, mail_perso, mail_pro in liste_adresses:
        if IDfamille not in dict_individus:
            dict_individus[IDfamille] = []
        dict_individus[IDfamille].append({"IDindividu": IDindividu, "nom": nom, "prenom": prenom, "mail_perso": mail_perso, "mail_pro": mail_pro})

    # Création du dict de résultats
    dict_adresses = {}
    listeFamillesAvecAdresses = []
    liste_anomalies = []

    def Ajouter_adresse(IDfamille, adresse):
        if adresse not in (None, ""):
            if IDfamille not in dict_adresses:
                dict_adresses[IDfamille] = []
            if adresse not in dict_adresses[IDfamille]:
                dict_adresses[IDfamille].append(adresse)
                if IDfamille not in listeFamillesAvecAdresses:
                    listeFamillesAvecAdresses.append(IDfamille)

    # Toutes les adresses
    if code_action == "all":
        for IDfamille, liste_individus in dict_individus.items():
            for dict_individu in liste_individus:
                Ajouter_adresse(IDfamille, dict_individu["mail_perso"])
                Ajouter_adresse(IDfamille, dict_individu["mail_pro"])

    # Toutes les adresses perso
    if code_action == "all_perso":
        for IDfamille, liste_individus in dict_individus.items():
            for dict_individu in liste_individus:
                Ajouter_adresse(IDfamille, dict_individu["mail_perso"])

    # Toutes les adresses pro
    if code_action == "all_pro":
        for IDfamille, liste_individus in dict_individus.items():
            for dict_individu in liste_individus:
                Ajouter_adresse(IDfamille, dict_individu["mail_pro"])

    # L'adresse personnelle en priorité
    if code_action == "all_perso_first":
        for IDfamille, liste_individus in dict_individus.items():
            for dict_individu in liste_individus:
                if dict_individu["mail_perso"] not in ("", None):
                    Ajouter_adresse(IDfamille, dict_individu["mail_perso"])
                else:
                    Ajouter_adresse(IDfamille, dict_individu["mail_pro"])

    # L'adresse professionnelle en priorité
    if code_action == "all_pro_first":
        for IDfamille, liste_individus in dict_individus.items():
            for dict_individu in liste_individus:
                if dict_individu["mail_pro"] not in ("", None):
                    Ajouter_adresse(IDfamille, dict_individu["mail_pro"])
                else:
                    Ajouter_adresse(IDfamille, dict_individu["mail_perso"])

    # Une adresse par famille (perso en priorité)
    if code_action == "one_perso_first":
        for IDfamille, liste_individus in dict_individus.items():
            liste_temp = []
            for dict_individu in liste_individus:
                if dict_individu["mail_perso"] not in ("", None): liste_temp.append((1, dict_individu["mail_perso"]))
                if dict_individu["mail_pro"] not in ("", None): liste_temp.append((2, dict_individu["mail_pro"]))
            liste_temp.sort()
            if len(liste_temp) > 0:
                Ajouter_adresse(IDfamille, liste_temp[0][1])

    # Une adresse par famille (pro en priorité)
    if code_action == "one_pro_first":
        for IDfamille, liste_individus in dict_individus.items():
            liste_temp = []
            for dict_individu in liste_individus:
                if dict_individu["mail_perso"] not in ("", None): liste_temp.append((2, dict_individu["mail_perso"]))
                if dict_individu["mail_pro"] not in ("", None): liste_temp.append((1, dict_individu["mail_pro"]))
            liste_temp.sort()
            if len(liste_temp) > 0:
                Ajouter_adresse(IDfamille, liste_temp[0][1])

    # Je veux sélectionner les adresses
    if code_action == "selection":
        for IDfamille in liste_IDfamille :
            nom_titulaires = dictTitulaires[IDfamille]["titulairesSansCivilite"]
            adresses = GetAdresseFamille(IDfamille, choixMultiple=True, muet=True, nomTitulaires=nom_titulaires)
            if adresses == False:
                return False
            for adresse in adresses:
                Ajouter_adresse(IDfamille, adresse)

    # Annonce les anomalies trouvées
    for IDfamille in liste_IDfamille:
        if IDfamille not in listeFamillesAvecAdresses:
            if IDfamille in dictTitulaires:
                nom_titulaires = dictTitulaires[IDfamille]["titulairesSansCivilite"]
            else:
                nom_titulaires = _(u"Titulaires inconnus")
            liste_anomalies.append(nom_titulaires)

    if len(liste_anomalies) > 0 and len(liste_anomalies) != len(liste_IDfamille):
        intro = _(u"%d des familles sélectionnées n'ont pas d'adresse Email :") % len(liste_anomalies)
        conclusion = _(u"Souhaitez-vous quand même continuer avec les autres destinataires ?")
        detail = u"\n".join([nom for nom in liste_anomalies])
        dlgErreur = DLG_Messagebox.Dialog(None, titre=_(u"Avertissement"), introduction=intro, detail=detail, conclusion=conclusion, icone=wx.ICON_EXCLAMATION, boutons=[_(u"Oui"), _(u"Non"), _(u"Annuler")])
        reponse = dlgErreur.ShowModal()
        dlgErreur.Destroy()
        if reponse != 0:
            return False

    # Dernière vérification avant transfert
    if len(dict_adresses) == 0 :
        dlg = wx.MessageDialog(None, _(u"Il ne reste finalement aucune adresse internet !"), _(u"Erreur"), wx.OK | wx.ICON_EXCLAMATION)
        dlg.ShowModal()
        dlg.Destroy()
        return False

    # Renvoie le dict des adresses
    return dict_adresses






# -------------------------------------------------------------------------------------------------------


class Message():
    def __init__(self, destinataires=[], sujet="", texte_html="", fichiers=[], images=[], champs={}):
        self.destinataires = destinataires
        self.sujet = sujet
        self.fichiers = fichiers
        self.images = images
        self.texte_html = texte_html
        self.champs = champs

        # Corrige le pb des images embarquées
        index = 0
        for img in images:
            img = img.replace(u"\\", u"/")
            img = img.replace(u":", u"%3a")
            self.texte_html = self.texte_html.replace(u"file:/%s" % img, u"cid:image%d" % index)
            index += 1

        # Conversion du html en texte plain
        self.texte_plain = UTILS_Html2text.html2text(self.texte_html)

    def AttacheImagesIncluses(self, email=None):
        index = 0
        for img in self.images:
            fp = open(img, 'rb')
            msgImage = MIMEImage(fp.read())
            fp.close()
            msgImage.add_header('Content-ID', '<image%d>' % index)
            msgImage.add_header('Content-Disposition', 'inline', filename=img)
            email.attach(msgImage)
            index += 1

    def AttacheFichiersJoints(self, email=None):
        for fichier in self.fichiers:
            """Guess the content type based on the file's extension. Encoding
            will be ignored, altough we should check for simple things like
            gzip'd or compressed files."""
            ctype, encoding = mimetypes.guess_type(fichier)
            if ctype is None or encoding is not None:
                # No guess could be made, or the file is encoded (compresses), so
                # use a generic bag-of-bits type.
                ctype = 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)
            if maintype == 'text':
                fp = open(fichier)
                # Note : we should handle calculating the charset
                part = MIMEText(fp.read(), _subtype=subtype)
                fp.close()
            elif maintype == 'image':
                fp = open(fichier, 'rb')
                part = MIMEImage(fp.read(), _subtype=subtype)
                fp.close()
            else:
                fp = open(fichier, 'rb')
                part = MIMEBase(maintype, subtype)
                part.set_payload(fp.read())
                fp.close()
                # Encode the payload using Base64
                encoders.encode_base64(part)
            # Set the filename parameter
            nomFichier = os.path.basename(fichier)
            if type(nomFichier) == six.text_type:
                nomFichier = FonctionsPerso.Supprime_accent(nomFichier)
            # changement cosmetique pour ajouter les guillements autour du filename
            part.add_header('Content-Disposition', "attachment; filename=\"%s\"" % nomFichier)
            email.attach(part)

    def GetLabelDestinataires(self):
        return ";".join(self.destinataires)



def Messagerie(backend='smtp', **kwds):
    # Ancien moteur SMTP
    if backend == "smtp_obsolete":
        klass = SmtpV1(**kwds)
    # Nouveau moteur SMTP
    elif backend == "smtp":
        klass = SmtpV2(**kwds)
    # Mailjet
    elif backend == "mailjet":
        klass = Mailjet(**kwds)
    else:
        klass = SmtpV2(**kwds)
    return klass




class Base_messagerie():
    def __init__(self, hote=None, port=None, utilisateur=None, motdepasse=None, email_exp=None, nom_exp=None, timeout=None, use_tls=False, fail_silently=False, parametres=None):
        self.hote = hote
        self.port = port
        self.utilisateur = utilisateur
        self.motdepasse = motdepasse
        self.email_exp = email_exp
        self.nom_exp = nom_exp
        self.timeout = timeout
        self.use_tls = use_tls
        self.fail_silently = fail_silently
        self.parametres = parametres

        if self.utilisateur == "" : self.utilisateur = None
        if self.motdepasse == "" : self.motdepasse = None

        # Timeout
        timeout = UTILS_Parametres.Parametres(mode="get", categorie="email", nom="timeout", valeur=None)
        if timeout not in ("", None):
            self.timeout = int(timeout)

        # Préparation de l'adresse d'expédition
        if self.nom_exp not in ("", None):
            self.from_email = u"%s <%s>" % (self.nom_exp, self.email_exp)
        else :
            self.from_email = self.email_exp

        # Formatage des paramètres
        self.dict_parametres = {}
        if parametres not in ("", None):
            liste_parametres = parametres.split("##")
            for texte in liste_parametres:
                nom, valeur = texte.split("==")
                self.dict_parametres[nom] = valeur


    def Connecter(self):
        pass

    def Envoyer(self, message=None):
        pass

    def Fermer(self):
        pass





class SmtpV1(Base_messagerie):
    def __init__(self, **kwds):
        Base_messagerie.__init__(self, **kwds)

    def Connecter(self):
        try :
            if self.motdepasse == None: self.motdepasse = ""
            if self.utilisateur == None: self.utilisateur = ""

            if self.utilisateur == None and self.motdepasse == None:
                # Envoi standard
                self.connection = smtplib.SMTP(self.hote, timeout=self.timeout)
            else:
                # Si identification SSL nécessaire :
                self.connection = smtplib.SMTP(self.hote, self.port, timeout=self.timeout)
                self.connection.ehlo()
                if self.use_tls == True:
                    self.connection.starttls()
                    self.connection.ehlo()
                self.connection.login(self.utilisateur.encode('utf-8'), self.motdepasse.encode('utf-8'))
        except smtplib.SMTPException:
            if not self.fail_silently:
                raise

    def Envoyer(self, message=None):
        # Création du message
        email = MIMEMultipart('alternative')
        # msg['Message-ID'] = make_msgid()

        # if accuseReception == True:
        #     msg['Disposition-Notification-To'] = adresseExpediteur

        email.attach(MIMEText(message.texte_plain.encode('utf-8'), 'plain', 'utf-8'))
        email.attach(MIMEText(message.texte_html.encode('utf-8'), 'html', 'utf-8'))

        tmpmsg = email
        email = MIMEMultipart('mixed')
        email.attach(tmpmsg)

        # Ajout des headers à ce Multipart
        if self.nom_exp in ("", None):
            email['From'] = self.email_exp
        else:
            sender = Header(self.nom_exp, "utf-8")
            sender.append(self.email_exp, "ascii")
            email['From'] = sender  # formataddr((nomadresseExpediteur, adresseExpediteur))
        email['To'] = ";".join(message.destinataires)
        email['Date'] = formatdate(localtime=True)
        email['Subject'] = message.sujet

        message.AttacheImagesIncluses(email)
        message.AttacheFichiersJoints(email)

        try:
            self.connection.sendmail(self.email_exp, message.destinataires, email.as_string())
        except smtplib.SMTPException:
            if not self.fail_silently:
                raise
            return False
        return True

    def Fermer(self):
        self.connection.close()





class SmtpV2(Base_messagerie):
    def __init__(self, **kwds):
        Base_messagerie.__init__(self, **kwds)

    def Connecter(self):
        try :
            self.connection = mail.get_connection(backend='Outils.mail.smtp.EmailBackend', fail_silently=self.fail_silently,
                                             host=self.hote, port=self.port, username=self.utilisateur, password=self.motdepasse,
                                             use_tls=self.use_tls, use_ssl=False, timeout=self.timeout, ssl_keyfile=None, ssl_certfile=None)
            self.connection.open()
        except smtplib.SMTPException:
            if not self.fail_silently:
                raise


    def Envoyer(self, message=None):
        headers = {}

        # Accusé de réception
        notification = self.dict_parametres.get("notification", 0)
        if notification == "1":
            headers["Return-Receipt-To"] = self.from_email
            headers["Disposition-Notification-To"] = self.from_email

        email = mail.EmailMultiAlternatives(
            subject=message.sujet,
            body=message.texte_plain,
            from_email=self.from_email,
            to=message.destinataires,
            connection=self.connection,
            headers=headers,
        )

        email.attach_alternative(message.texte_html, "text/html")

        message.AttacheImagesIncluses(email)
        message.AttacheFichiersJoints(email)

        resultat = email.send()
        return resultat

    def Fermer(self):
        self.connection.close()

    def Envoyer_lot(self, messages=[], dlg_progress=None, afficher_confirmation_envoi=True):
        """ Envoi des messages par lot """
        # Si envoi par lot activé
        nbre_mails_lot = self.dict_parametres.get("nbre_mails", None)
        duree_pause = self.dict_parametres.get("duree_pause", None)

        # Envoi des mails
        index = 1
        index_lot = 1
        listeAnomalies = []
        listeSucces = []
        ne_pas_signaler_erreurs = False
        for message in messages:
            while True:
                adresse = message.GetLabelDestinataires()
                labelAdresse = _TexteUtf8(adresse)
                label = _(u"Envoi %d/%d : %s...") % (index, len(messages), labelAdresse)

                # Si la dlg_progress a été fermée, on la réouvre
                if dlg_progress == None:
                    dlg_progress = wx.ProgressDialog(_(u"Envoi des mails"), _(u""), maximum=len(messages) + 1, parent=None)
                    dlg_progress.SetSize((450, 140))
                    dlg_progress.CenterOnScreen()
                dlg_progress.Update(index, label)

                # Envoi
                erreur = None
                try:
                    self.Envoyer(message)
                    listeSucces.append(message)
                except smtplib.SMTPServerDisconnected:
                    erreur = "deconnexion"
                except Exception as err:
                    erreur = err

                # Tentative de reconnexion du serveur de messagerie puis renvoi du mail
                if erreur == "deconnexion":
                    print("Reconnexion au serveur de messagerie...")
                    try:
                        self.Connecter()
                        self.Envoyer(message)
                        listeSucces.append(message)
                        erreur = None
                    except Exception as err:
                        traceback.print_exc(file=sys.stdout)
                        erreur = err

                if erreur != None:
                    if six.PY2:
                        err = str(erreur).decode("utf8")
                    else:
                        err = six.text_type(erreur)
                    listeAnomalies.append((message, err))
                    print(("Erreur dans l'envoi d'un mail : %s..." % err))

                    if ne_pas_signaler_erreurs == False:

                        # Fermeture de la dlg_progress
                        dlg_progress.Destroy()
                        dlg_progress = None

                        # Affichage de l'erreur
                        intro = _(u"L'erreur suivante a été détectée :")
                        detail = err
                        if index <= len(messages) - 1:
                            conclusion = _(u"Souhaitez-vous quand même continuer l'envoi des autres emails ?")
                            boutons = [_(u"Réessayer"), _(u"Continuer"),
                                       _(u"Continuer et ne plus signaler les erreurs"), _(u"Arrêter")]
                        else:
                            conclusion = None
                            boutons = [_(u"Réessayer"), _(u"Arrêter"), ]
                        dlgErreur = DLG_Messagebox.Dialog(None, titre=_(u"Erreur"), introduction=intro, detail=detail,
                                                          conclusion=conclusion, icone=wx.ICON_ERROR, boutons=boutons)
                        reponse = dlgErreur.ShowModal()
                        dlgErreur.Destroy()
                        if reponse == 0:
                            continue
                        if reponse == 2:
                            ne_pas_signaler_erreurs = True
                        if reponse == 3:
                            return listeSucces
                break

            # Petit pause après chaque message
            if len(messages) > 1:
                time.sleep(1)

            # Envoi par lot
            if nbre_mails_lot and len(messages) > 1:
                if index_lot >= int(nbre_mails_lot):
                    time.sleep(int(duree_pause))
                    index_lot = 0
                index_lot += 1

            index += 1

        # Fin de la gauge
        if dlg_progress != None:
            dlg_progress.Update(index, _(u"Fin de l'envoi."))
            dlg_progress.Destroy()

        # Si tous les Emails envoyés avec succès
        if len(listeAnomalies) == 0 and afficher_confirmation_envoi == True:
            if len(listeSucces) == 1:
                message = _(u"L'Email a été envoyé avec succès !")
            else:
                message = _(u"Les %d Emails ont été envoyés avec succès !") % len(listeSucces)
            dlg = wx.MessageDialog(None, message, _(u"Fin de l'envoi"), wx.OK | wx.ICON_INFORMATION)
            dlg.ShowModal()
            dlg.Destroy()

        # Si Anomalies
        if len(listeAnomalies) > 0 and len(messages) > 1:
            if len(listeSucces) > 0:
                intro = _(u"%d Email(s) ont été envoyés avec succès mais les %d envois suivants ont échoué :") % (
                len(listeSucces), len(listeAnomalies))
            else:
                intro = _(u"Tous les envois ont lamentablement échoué :")
            lignes = []
            for message, erreur in listeAnomalies:
                adresse = message.GetLabelDestinataires()
                lignes.append(u"- %s : %s" % (_TexteUtf8(adresse), _TexteUtf8(erreur)))
            dlg = DLG_Messagebox.Dialog(None, titre=_(u"Compte-rendu de l'envoi"), introduction=intro,
                                        detail="\n".join(lignes), icone=wx.ICON_INFORMATION, boutons=[_(u"Ok"), ])
            dlg.ShowModal()
            dlg.Destroy()

        return listeSucces






# Étapes réelles traversées pour l'envoi d'UN message via Mailjet
# (Mailjet.Envoyer_lot() / Mailjet.Envoyer()) : chacune correspond à une
# phase effectivement franchie, jamais à un pourcentage inventé.
_ETAPE_PREPARATION = 0
_ETAPE_PIECES_JOINTES = 1
_ETAPE_ENVOI_ET_ATTENTE = 2
_ETAPE_SUCCES = 3
_NB_ETAPES_PAR_MESSAGE = 4


def _FormaterTailleOctets(nb_octets):
    """"XXX Ko", arrondi -- jamais d'octets bruts, jamais de décimale."""
    if nb_octets <= 0:
        return u"0 Ko"
    return u"%d Ko" % max(1, round(nb_octets / 1024.0))


def _LibelleProgressionEnvoi(index, total, label_destinataire, sujet=None, etape_texte=None):
    """Construit le message affiché par la wx.ProgressDialog de
    Mailjet.Envoyer_lot(). Ne doit jamais recevoir ni afficher de clé API,
    de secret Mailjet, de mot de passe, ni le contenu complet du mail :
    seuls index/total, le libellé destinataire, le sujet (tronqué à 80
    caractères) et un texte d'étape lui sont transmis."""
    lignes = [
        _(u"Message %d/%d") % (index, total),
        _(u"Destinataire : %s") % label_destinataire,
    ]
    if sujet:
        sujet_tronque = sujet if len(sujet) <= 80 else sujet[:80] + u"..."
        lignes.append(_(u"Sujet : %s") % sujet_tronque)
    if etape_texte:
        lignes.append(etape_texte)
    return u"\n".join(lignes)


def _FermerProgressDialog(dlg_progress):
    """Détruit dlg_progress si elle existe encore, puis renvoie None.
    Idempotent : n'appelle jamais Destroy() deux fois sur le même objet
    (dlg_progress est systématiquement remise à None par l'appelant après
    cet appel)."""
    if dlg_progress is not None:
        dlg_progress.Destroy()
    return None


class Mailjet(Base_messagerie):
    def __init__(self, **kwds):
        Base_messagerie.__init__(self, **kwds)

    def Connecter(self):
        # Récupération des clés Mailjet
        api_key = self.dict_parametres.get("api_key", None)
        api_secret = self.dict_parametres.get("api_secret", None)
        if api_key == None or api_secret == None:
            raise ValueError(u"Les codes MAILJET ne sont pas valides.")

        # Connexion à Mailjet
        try:
            from mailjet_rest import Client
            self.connection = Client(auth=(api_key, api_secret), version='v3.1')
        except Exception as err:
            raise

    # def Envoyer_archive(self, message=None, afficher_confirmation_envoi=False):
    #     self.Envoyer_lot(messages=[message,], afficher_confirmation_envoi=afficher_confirmation_envoi)
    #
    # def Envoyer_lot_archive(self, messages=[], dlg_progress=None, afficher_confirmation_envoi=True):
    #     """ Envoi des messages par lot """
    #     data = {"Messages": []}
    #     for message in messages:
    #
    #         # Préparation du message
    #         dict_message = {
    #             "From": {"Email": self.email_exp, "Name": self.nom_exp},
    #             "To": [{"Email": destinataire} for destinataire in message.destinataires],
    #             "Subject": message.sujet,
    #             "TextPart": message.texte_plain,
    #             "HTMLPart": message.texte_html,
    #             "Attachments": [],
    #             "InlinedAttachments": [],
    #         }
    #
    #         # Intégration des images incluses
    #         index = 0
    #         for fichier in message.images:
    #             ctype, encoding = mimetypes.guess_type(fichier)
    #             with open(fichier, "rb") as file:
    #                 Base64Content = base64.b64encode(file.read())
    #             nom_fichier = os.path.basename(fichier)
    #
    #             dict_fichier = {
    #                 "ContentType": ctype,
    #                 "Filename": nom_fichier,
    #                 "ContentID": "image%d" % index,
    #                 "Base64Content": Base64Content,
    #             }
    #             dict_message["InlinedAttachments"].append(dict_fichier)
    #             index += 1
    #
    #         # Intégration des pièces jointes
    #         for fichier in message.fichiers:
    #             ctype, encoding = mimetypes.guess_type(fichier)
    #             with open(fichier, "rb") as file:
    #                 Base64Content = base64.b64encode(file.read())
    #             nom_fichier = os.path.basename(fichier)
    #
    #             dict_fichier = {
    #                 "ContentType": ctype,
    #                 "Filename": nom_fichier,
    #                 "Base64Content": Base64Content,
    #             }
    #             dict_message["Attachments"].append(dict_fichier)
    #
    #         # Mémorisation du message
    #         data["Messages"].append(dict_message)
    #
    #     if wx.GetKeyState(wx.WXK_CONTROL) == True:
    #         from Utils import UTILS_Json
    #         UTILS_Json.Ecrire(nom_fichier=UTILS_Fichiers.GetRepTemp(fichier="appel_mailjet.txt"), data=data)
    #         return False
    #
    #     # Envoi de la requête à Mailjet
    #     resultats = self.connection.send.create(data=data)
    #     # print resultats.status_code
    #     # print resultats.json()
    #
    #     # Analyse des résultats
    #     liste_succes = []
    #     listeAnomalies = []
    #     index = 0
    #     for message in messages:
    #         resultat_message = resultats.json()["Messages"][index][u'Status']
    #         if resultat_message == u'success':
    #             liste_succes.append(message)
    #         else :
    #             listeAnomalies.append((message, resultat_message))
    #         index += 1
    #
    #     # Fin de la gauge
    #     if dlg_progress != None:
    #         dlg_progress.Update(index, _(u"Fin de l'envoi."))
    #         dlg_progress.Destroy()
    #
    #     # Si tous les Emails envoyés avec succès
    #     if len(listeAnomalies) == 0 and afficher_confirmation_envoi == True:
    #         if len(liste_succes) == 1:
    #             message = _(u"L'Email a été envoyé avec succès !")
    #         else:
    #             message = _(u"Les %d Emails ont été envoyés avec succès !") % len(liste_succes)
    #         dlg = wx.MessageDialog(None, message, _(u"Fin de l'envoi"), wx.OK | wx.ICON_INFORMATION)
    #         dlg.ShowModal()
    #         dlg.Destroy()
    #
    #     # Si Anomalies
    #     if len(listeAnomalies) > 0 and len(messages) > 1:
    #         if len(liste_succes) > 0:
    #             intro = _(u"%d Email(s) ont été envoyés avec succès mais les %d envois suivants ont échoué :") % (
    #             len(liste_succes), len(listeAnomalies))
    #         else:
    #             intro = _(u"Tous les envois ont lamentablement échoué :")
    #         lignes = []
    #         for message, erreur in listeAnomalies:
    #             adresse = message.GetLabelDestinataires()
    #             try:
    #                 lignes.append(u"- %s : %s" % (adresse.decode("utf8"), erreur))
    #             except:
    #                 lignes.append(u"- %s : %s" % (adresse, erreur))
    #         dlg = DLG_Messagebox.Dialog(None, titre=_(u"Compte-rendu de l'envoi"), introduction=intro,
    #                                     detail="\n".join(lignes), icone=wx.ICON_INFORMATION, boutons=[_(u"Ok"), ])
    #         dlg.ShowModal()
    #         dlg.Destroy()
    #
    #     return liste_succes


    def Envoyer(self, message=None):
        # Préparation du message
        dict_message = {
            "From": {"Email": self.email_exp, "Name": self.nom_exp},
            "To": [{"Email": destinataire} for destinataire in message.destinataires],
            "Subject": message.sujet,
            "TextPart": message.texte_plain,
            "HTMLPart": message.texte_html,
            "Attachments": [],
            "InlinedAttachments": [],
        }

        # Intégration des images incluses
        index = 0
        for fichier in message.images:
            ctype, encoding = mimetypes.guess_type(fichier)
            with open(fichier, "rb") as file:
                # base64.b64encode() renvoie des bytes (Python 2 comme
                # Python 3 : en Python 2, bytes == str, .decode("ascii")
                # y fonctionne aussi puisque l'alphabet Base64 est ASCII
                # pur). mailjet_rest transmet ce dictionnaire directement à
                # json.dumps() (via requests) : sous Python 3, des bytes
                # non décodés y lèvent TypeError("Object of type bytes is
                # not JSON serializable") -- reproduit à l'exécution avant
                # correctif. Mailjet exige explicitement une chaîne ASCII.
                Base64Content = base64.b64encode(file.read()).decode("ascii")
            nom_fichier = os.path.basename(fichier)

            dict_fichier = {
                "ContentType": ctype,
                "Filename": nom_fichier,
                "ContentID": "image%d" % index,
                "Base64Content": Base64Content,
            }
            dict_message["InlinedAttachments"].append(dict_fichier)
            index += 1

        # Intégration des pièces jointes
        for fichier in message.fichiers:
            ctype, encoding = mimetypes.guess_type(fichier)
            with open(fichier, "rb") as file:
                Base64Content = base64.b64encode(file.read()).decode("ascii")
            nom_fichier = os.path.basename(fichier)

            dict_fichier = {
                "ContentType": ctype,
                "Filename": nom_fichier,
                "Base64Content": Base64Content,
            }
            dict_message["Attachments"].append(dict_fichier)

        # Envoi de la requête à Mailjet
        resultats = self.connection.send.create(data={"Messages": [dict_message,]})

        # Analyse du résultat
        try:
            resultat = resultats.json()["Messages"][0][u'Status']
        except Exception as err:
            print(err)
            print(resultats.status_code)
            print(resultats.json())
            raise Exception(err)

        if resultat != u'success':
            print("Erreur envoi avec Mailjet")
            print(resultats.json())
            raise Exception(resultat)

        return resultat

    def Fermer(self):
        self.connection.close()

    def Envoyer_lot(self, messages=[], dlg_progress=None, afficher_confirmation_envoi=True):
        """ Envoi des messages par lot """
        index = 1
        total = len(messages)
        listeAnomalies = []
        listeSucces = []
        ne_pas_signaler_erreurs = False
        # Progression par étapes réellement franchies (préparation, pièces
        # jointes, envoi+attente, succès) et non plus un seul cran par
        # message entier : pour 1 message, l'ancien schéma
        # (maximum=len(messages)+1, un seul Update() avant l'envoi) laissait
        # la barre statique à 50% pendant toute la phase réelle d'envoi.
        maximum = total * _NB_ETAPES_PAR_MESSAGE + 1
        if dlg_progress is not None:
            # dlg_progress peut avoir été construite par l'appelant (ex.
            # DLG_Mailer.Envoyer(), qui l'utilise déjà pour afficher "Connexion
            # au serveur de messagerie...") avec un autre maximum : on aligne
            # sa plage sur notre propre schéma de progression, sans exiger de
            # l'appelant qu'il en connaisse le détail.
            dlg_progress.SetRange(maximum)

        for message in messages:
            while True:
                try:
                    adresse = message.GetLabelDestinataires()
                    labelAdresse = _TexteUtf8(adresse)
                    sujet = _TexteUtf8(message.sujet) if message.sujet else None
                    base = (index - 1) * _NB_ETAPES_PAR_MESSAGE

                    # Si la dlg_progress a été fermée (ou n'a jamais existé), on la (ré)ouvre.
                    if dlg_progress is None:
                        dlg_progress = wx.ProgressDialog(_(u"Envoi des mails"), _(u""), maximum=maximum, parent=None)
                        dlg_progress.SetSize((450, 140))
                        dlg_progress.CenterOnScreen()

                    # 1. Préparation.
                    dlg_progress.Update(
                        base + _ETAPE_PREPARATION,
                        _LibelleProgressionEnvoi(index, total, labelAdresse, sujet),
                    )

                    # 2. Pièces jointes (images incluses + fichiers joints), si présentes.
                    fichiers_joints = list(message.images) + list(message.fichiers)
                    if fichiers_joints:
                        taille_totale = sum(
                            os.path.getsize(fichier) for fichier in fichiers_joints if os.path.exists(fichier)
                        )
                        if len(fichiers_joints) == 1:
                            etape_texte = _(u"Préparation de 1 pièce jointe (%s)...") % _FormaterTailleOctets(taille_totale)
                        else:
                            etape_texte = _(u"Préparation de %d pièces jointes (%s)...") % (
                                len(fichiers_joints), _FormaterTailleOctets(taille_totale),
                            )
                        dlg_progress.Update(
                            base + _ETAPE_PIECES_JOINTES,
                            _LibelleProgressionEnvoi(index, total, labelAdresse, sujet, etape_texte),
                        )

                    # 3. Connexion/envoi + attente de la réponse : un seul appel
                    # bloquant (mailjet_rest exécute la requête HTTP de façon
                    # synchrone -- aucun évènement wx n'est traité, donc aucune
                    # animation possible pendant l'attente réseau elle-même).
                    # Le libellé n'est donc affiché qu'une fois, juste avant
                    # l'appel : c'est le seul moment où il est garanti d'être
                    # réellement peint à l'écran avant le blocage.
                    dlg_progress.Update(
                        base + _ETAPE_ENVOI_ET_ATTENTE,
                        _LibelleProgressionEnvoi(
                            index, total, labelAdresse, sujet,
                            _(u"Envoi via Mailjet — attente de la réponse..."),
                        ),
                    )

                    self.Envoyer(message)
                    listeSucces.append(message)

                    # 4. Succès.
                    dlg_progress.Update(
                        base + _ETAPE_SUCCES,
                        _LibelleProgressionEnvoi(index, total, labelAdresse, sujet, _(u"Envoi terminé avec succès")),
                    )
                except Exception as err:
                    # Toute exception survenue pendant la préparation, le
                    # calcul de taille des pièces jointes, l'appel à
                    # mailjet_rest (encodage + requête HTTP, dans Envoyer()),
                    # l'analyse de la réponse ou le formatage de l'erreur
                    # elle-même est capturée ici : aucune de ces phases ne
                    # doit laisser la dlg_progress ouverte dans un état
                    # incohérent.
                    try:
                        err_texte = _TexteUtf8(err)
                    except Exception:
                        # Filet ciblé : ne concerne que le formatage de
                        # l'erreur elle-même, ne masque jamais l'erreur
                        # d'origine (toujours mémorisée/affichée ensuite).
                        err_texte = repr(err)

                    listeAnomalies.append((message, err_texte))
                    print(("Erreur dans l'envoi d'un mail : %s..." % err_texte))
                    traceback.print_exc(file=sys.stdout)

                    if ne_pas_signaler_erreurs == False:

                        # La dlg_progress est toujours détruite avant
                        # l'affichage d'une boîte d'erreur bloquante, quelle
                        # que soit la phase où l'exception est survenue.
                        # Idempotent : jamais de double Destroy() (dlg_progress
                        # est remise à None juste après par _FermerProgressDialog).
                        dlg_progress = _FermerProgressDialog(dlg_progress)

                        # Affichage de l'erreur
                        intro = _(u"L'erreur suivante a été détectée :")
                        detail = err_texte
                        if index <= total - 1:
                            conclusion = _(u"Souhaitez-vous quand même continuer l'envoi des autres emails ?")
                            boutons = [_(u"Réessayer"), _(u"Continuer"),
                                       _(u"Continuer et ne plus signaler les erreurs"), _(u"Arrêter")]
                        else:
                            conclusion = None
                            boutons = [_(u"Réessayer"), _(u"Arrêter"), ]
                        dlgErreur = DLG_Messagebox.Dialog(None, titre=_(u"Erreur"), introduction=intro, detail=detail,
                                                          conclusion=conclusion, icone=wx.ICON_ERROR, boutons=boutons)
                        reponse = dlgErreur.ShowModal()
                        dlgErreur.Destroy()
                        if reponse == 0:
                            continue
                        if reponse == 2:
                            ne_pas_signaler_erreurs = True
                        if reponse == 3:
                            return listeSucces
                break

            if total > 1:
                time.sleep(1)
            index += 1

        # Fin de la gauge
        if dlg_progress is not None:
            dlg_progress.Update(maximum, _(u"Fin de l'envoi."))
            dlg_progress = _FermerProgressDialog(dlg_progress)

        # Si tous les Emails envoyés avec succès
        if len(listeAnomalies) == 0 and afficher_confirmation_envoi == True:
            if len(listeSucces) == 1:
                message = _(u"L'Email a été envoyé avec succès !")
            else:
                message = _(u"Les %d Emails ont été envoyés avec succès !") % len(listeSucces)
            dlg = wx.MessageDialog(None, message, _(u"Fin de l'envoi"), wx.OK | wx.ICON_INFORMATION)
            dlg.ShowModal()
            dlg.Destroy()

        # Si Anomalies
        if len(listeAnomalies) > 0 and len(messages) > 1:
            if len(listeSucces) > 0:
                intro = _(u"%d Email(s) ont été envoyés avec succès mais les %d envois suivants ont échoué :") % ( len(listeSucces), len(listeAnomalies))
            else:
                intro = _(u"Tous les envois ont lamentablement échoué :")
            lignes = []
            for message, erreur in listeAnomalies:
                adresse = message.GetLabelDestinataires()
                lignes.append(u"- %s : %s" % (_TexteUtf8(adresse), _TexteUtf8(erreur)))
            dlg = DLG_Messagebox.Dialog(None, titre=_(u"Compte-rendu de l'envoi"), introduction=intro, detail="\n".join(lignes), icone=wx.ICON_INFORMATION, boutons=[_(u"Ok"), ])
            dlg.ShowModal()
            dlg.Destroy()

        return listeSucces

    def Fermer(self):
        pass




if __name__ == u"__main__":
    # Préparation du message
    message = Message(destinataires=[""], sujet=u"Sujet du mail", texte_html="<p>Ceci est le <b>texte</b> html</p>", fichiers=[], images=[])

    # Envoi du message
    messagerie = Messagerie(backend='Mailjet', hote=None, port=None, utilisateur=None, motdepasse=None, email_exp=None, nom_exp=None, timeout=None, use_tls=False)
    messagerie.Connecter()
    messagerie.Envoyer(message)
    messagerie.Fermer()
