#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Auteur:           Ivan LUCAS
# Copyright:       (c) 2010-13 Ivan LUCAS
# Licence:         Licence GNU GPL
#------------------------------------------------------------------------


import Chemins
from Utils.UTILS_Traduction import _
import wx
from Ctrl import CTRL_Bouton_image
import datetime
import time
import socket
import os
import glob
import random
import wx.lib.dialogs as dialogs

import GestionDB
from Utils import UTILS_Sauvegarde
from Utils.UTILS_Divers import ConvertChaineEnListe, ConvertListeEnChaine
from Utils import UTILS_Dates
from Utils import UTILS_Identification
from Utils import UTILS_Parametres
from Utils import UTILS_Config
import hashlib
import json
import tempfile


def _CleRepertoirePoste(procedure):
    # Identite stable : ne pas inclure le nom horodate de l'archive.
    identite = [procedure.get(cle) for cle in (
        "IDsauvegarde", "nom", "sauvegarde_repertoire",
        "sauvegarde_fichiers_locaux", "sauvegarde_fichiers_reseau")]
    donnees = json.dumps(identite, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(donnees).hexdigest()


def _VerifierRepertoireDestination(repertoire):
    """Controle AVANT mysqldump ; la seule ecriture est un temoin temporaire."""
    if not isinstance(repertoire, str) or not os.path.isdir(repertoire):
        return False, u"Le dossier de destination est introuvable : %s" % repertoire
    try:
        with tempfile.NamedTemporaryFile(
                prefix=".noethys-prevol-", dir=repertoire) as temoin:
            pass
    except OSError as err:
        return False, u"Ecriture impossible dans %s : %s" % (repertoire, err)
    return True, None


def ChoisirRepertoirePoste(parent, procedure):
    """Retourne (dossier, cle_a_memoriser), sans modifier la procedure SQL."""
    repertoire = procedure["sauvegarde_repertoire"]
    if repertoire is None:
        # Envoi par courriel uniquement : ne pas imposer de dossier.
        return None, None

    cle = _CleRepertoirePoste(procedure)
    dossiers = UTILS_Config.GetParametre("sauvegarde_repertoires_poste", defaut={})
    if not isinstance(dossiers, dict):
        dossiers = {}

    # Priorite au choix local deja confirme, sinon a la procedure partagee.
    for chemin in (dossiers.get(cle), repertoire):
        if isinstance(chemin, str):
            valide, _erreur = _VerifierRepertoireDestination(chemin)
            if valide:
                return chemin, None

    valide, erreur = _VerifierRepertoireDestination(repertoire)
    message = _(u"Le dossier de sauvegarde configure pour cette procedure est indisponible sur cet ordinateur :\n\n%s\n\n%s\n\nChoisissez un autre dossier. Ce choix sera conserve uniquement sur cet ordinateur apres une sauvegarde reussie.") % (repertoire, erreur)
    dlg = wx.DirDialog(parent, message,
                       style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
    try:
        if dlg.ShowModal() != wx.ID_OK:
            return False, None
        choisi = dlg.GetPath()
    finally:
        dlg.Destroy()

    valide, erreur = _VerifierRepertoireDestination(choisi)
    if not valide:
        dlgErreur = wx.MessageDialog(
            parent, _(u"Impossible d'utiliser le dossier choisi :\n\n%s") % erreur,
            _(u"Erreur"), wx.OK | wx.ICON_ERROR)
        dlgErreur.ShowModal()
        dlgErreur.Destroy()
        return False, None
    return choisi, cle


def MemoriserRepertoirePoste(cle, repertoire):
    """N'enregistre le choix local qu'apres le succes de la sauvegarde."""
    dossiers = UTILS_Config.GetParametre("sauvegarde_repertoires_poste", defaut={})
    dossiers = dict(dossiers) if isinstance(dossiers, dict) else {}
    dossiers[cle] = repertoire
    UTILS_Config.SetParametre("sauvegarde_repertoires_poste", dossiers)
    # Quitter() ecrit parfois Config.json AVANT de lancer la sauvegarde.
    UTILS_Config.FichierConfig().SetItemConfig("sauvegarde_repertoires_poste", dossiers)


class Sauvegarde_auto():
    def __init__(self, parent=None):
        self.parent = parent
        
        # Importations
        self.listeSauvegardes = self.Importation() 
        self.listeVacances = self.GetListeVacances() 
                    

    def Start(self):
        # Annonce rappel de sauvegarde auto
        if len(self.listeSauvegardes) == 0 :
            resultat = self.AnnonceRappel()
            return resultat

        # Lancement des sauvegardes
        for dictSauvegarde in self.listeSauvegardes :
            valide = True
            resultat = False
            cleRepertoirePoste = None
            
            # Création du nom de la sauvegarde
            prefixe = dictSauvegarde["sauvegarde_nom"]
            dictSauvegarde["sauvegarde_nom"] = u"%s_%s" % (dictSauvegarde["sauvegarde_nom"], datetime.datetime.now().strftime("%Y%m%d_%H%M"))
                        
            # Vérification des conditions
            if valide == True :
                valide = self.VerificationConditions(dictSauvegarde) 

            # Demande de confirmation
            if valide == True and dictSauvegarde["option_demander"] == "1" :
                image = wx.Bitmap(Chemins.GetStaticPath("Images/48x48/Sauvegarder.png"), wx.BITMAP_TYPE_ANY)
                message1 = _(u"Souhaitez-vous lancer la procédure de sauvegarde '%s' ?") % dictSauvegarde["nom"]
                dlg = dialogs.MultiMessageDialog(self.parent, message1, caption=_(u"Sauvegarde automatique"), msg2=None, style = wx.NO | wx.CANCEL | wx.YES | wx.YES_DEFAULT, icon=image, btnLabels={wx.ID_YES : _(u"Oui"), wx.ID_NO : _(u"Non"), wx.ID_CANCEL : _(u"Annuler")})
                reponse = dlg.ShowModal() 
                try :
                    dlg.Destroy() 
                except :
                    pass
                if reponse == wx.ID_NO :
                    valide = False
                if reponse == wx.ID_CANCEL :
                    return wx.ID_CANCEL

            # Un dossier partage invalide ne doit pas provoquer un long export.
            # Le choix local ne change jamais la procedure en base.
            if valide == True and dictSauvegarde["option_afficher_interface"] != "1" :
                repertoirePoste, cleRepertoirePoste = ChoisirRepertoirePoste(self.parent, dictSauvegarde)
                if repertoirePoste is False:
                    return wx.ID_CANCEL
                dictSauvegarde["sauvegarde_repertoire"] = repertoirePoste

            # Afficher interface
            if valide == True and dictSauvegarde["option_afficher_interface"] == "1" :
                from Dlg import DLG_Sauvegarde
                dlg = DLG_Sauvegarde.Dialog(self.parent, dictDonnees=dictSauvegarde)
                dlg.ShowModal() 
                resultat = dlg.GetResultat()
                dlg.Destroy()
            
            # Sauvegarde
            if valide == True and dictSauvegarde["option_afficher_interface"] != "1" :
                resultat = self.Sauvegarde(dictSauvegarde)
                
                if resultat == True and dictSauvegarde["option_confirmation"] == "1" :
                    dlg = wx.MessageDialog(self.parent, _(u"La procédure de sauvegarde '%s' s'est terminée avec succès.") % dictSauvegarde["nom"], _(u"Sauvegarde"), wx.OK | wx.ICON_INFORMATION)
                    dlg.ShowModal()
                    dlg.Destroy()

                if resultat == False :
                    dlg = wx.MessageDialog(self.parent, _(u"Echec de la procédure de sauvegarde '%s' !") % dictSauvegarde["nom"], _(u"Annulation"), wx.OK | wx.ICON_ERROR)
                    dlg.ShowModal()
                    dlg.Destroy()
                    return wx.ID_CANCEL

            # Sauvegarde de la date de la sauvegarde
            if resultat == True :
                if cleRepertoirePoste is not None:
                    try:
                        MemoriserRepertoirePoste(
                            cleRepertoirePoste, dictSauvegarde["sauvegarde_repertoire"])
                    except Exception:
                        # L'archive deja creee reste un succes, meme si le
                        # parametrage local ne peut pas etre memorise.
                        dlg = wx.MessageDialog(
                            self.parent,
                            _(u"La sauvegarde est creee, mais le nouveau dossier n'a pas pu etre memorise sur cet ordinateur."),
                            _(u"Sauvegarde"), wx.OK | wx.ICON_EXCLAMATION)
                        dlg.ShowModal()
                        dlg.Destroy()
                DB = GestionDB.DB()
                DB.ReqMAJ("sauvegardes_auto", [("date_derniere", str(datetime.date.today())),], "IDsauvegarde", dictSauvegarde["IDsauvegarde"])
                DB.Close()
                
            # Suppression des sauvegardes obsolètes
            if resultat == True and dictSauvegarde["option_suppression"] != None and dictSauvegarde["sauvegarde_repertoire"] != None and os.path.isdir(dictSauvegarde["sauvegarde_repertoire"]) == True :
                nbreJours = int(dictSauvegarde["option_suppression"])
                repertoire = dictSauvegarde["sauvegarde_repertoire"]
                listeFichiersPresents = glob.glob(repertoire + "/*")
                for fichier in listeFichiersPresents :
                    nomFichier = os.path.basename(fichier)
                    if (fichier.endswith(".nod") or fichier.endswith(".noc")) and nomFichier.startswith(prefixe) :
                        dateCreationFichier = datetime.date.fromtimestamp(os.path.getctime(fichier))
                        nbreJoursFichier = (datetime.date.today() - dateCreationFichier).days
                        if nbreJoursFichier >= nbreJours :
                            try:
                                os.remove(fichier)
                            except:
                                pass
                            
        return True       

    def GetListeVacances(self):
        DB = GestionDB.DB()
        req = """SELECT date_debut, date_fin, nom, annee
        FROM vacances 
        ORDER BY date_debut; """
        DB.ExecuterReq(req)
        listeDonnees = DB.ResultatReq()
        DB.Close()
        return listeDonnees

    def Importation(self):
        """ Importation des sauvegardes auto """
        listeChamps = [
            "IDsauvegarde", "nom", "observations", "date_derniere", 
            "sauvegarde_nom", "sauvegarde_motdepasse", "sauvegarde_repertoire", "sauvegarde_emails", "sauvegarde_fichiers_locaux", "sauvegarde_fichiers_reseau",
            "condition_jours_scolaires", "condition_jours_vacances", "condition_heure", "condition_poste", "condition_derniere", "condition_utilisateur",
            "option_afficher_interface", "option_demander", "option_suppression", "option_confirmation",
            ]
        DB = GestionDB.DB()
        req = """SELECT %s
        FROM sauvegardes_auto
        ;""" % ",".join(listeChamps)
        DB.ExecuterReq(req)
        listeDonnees = DB.ResultatReq()
        DB.Close()
        listeSauvegardes = []
        for sauvegarde in listeDonnees :
            dictTemp = {}
            index = 0
            for valeur in sauvegarde :
                dictTemp[listeChamps[index]] = valeur
                index += 1
            listeSauvegardes.append(dictTemp) 
        return listeSauvegardes

    def EstEnVacances(self, dateDD):
        date = str(dateDD)
        for valeurs in self.listeVacances :
            date_debut = valeurs[0]
            date_fin = valeurs[1]
            if date >= date_debut and date <= date_fin :
                return True
        return False

    def VerificationConditions(self, dictSauvegarde={}):
        """ Vérifie si conditions de la procédure sont valides """
        jours_scolaires = dictSauvegarde["condition_jours_scolaires"] 
        jours_vacances = dictSauvegarde["condition_jours_vacances"]
        heures = dictSauvegarde["condition_heure"]
        poste = dictSauvegarde["condition_poste"]
        derniere = dictSauvegarde["condition_derniere"]
        utilisateur = dictSauvegarde["condition_utilisateur"]
        
        dateDuJour = datetime.date.today()
        
        # Jour
        if jours_scolaires != None or jours_vacances != None :
            jours_scolaires = ConvertChaineEnListe(jours_scolaires)
            jours_vacances = ConvertChaineEnListe(jours_vacances)
            valide = False
            if jours_scolaires != None :
                if self.EstEnVacances(dateDuJour) == False :
                    if dateDuJour.weekday() in jours_scolaires :
                        valide = True
            if jours_vacances != None :
                if self.EstEnVacances(dateDuJour) == True :
                    if dateDuJour.weekday() in jours_vacances :
                        valide = True
            if valide == False :
                return False
        
        # Heure
        if heures != None :
            heureActuelle = time.strftime('%H:%M', time.localtime()) 
            heure_min, heure_max = heures.split(";")
            if heureActuelle < heure_min or heureActuelle > heure_max :
                return False
        
        # Poste
        if poste != None :
            listePostes = poste.split(";")
            if socket.gethostname() not in listePostes :
                return False
            
        # Dernière sauvegarde
        if derniere != None :
            date_derniere = dictSauvegarde["date_derniere"]
            if date_derniere != None : 
                date_derniere = UTILS_Dates.DateEngEnDateDD(date_derniere)
                nbreJours = (dateDuJour - date_derniere).days
                if nbreJours < int(derniere) :
                    return False
            
        # Utilisateur
        if utilisateur != None :
            listeUtilisateurs = ConvertChaineEnListe(utilisateur)
            IDutilisateur = UTILS_Identification.GetIDutilisateur()
            if IDutilisateur not in listeUtilisateurs :
                return False
            
        return True
        
        
        
    def Sauvegarde(self, dictSauvegarde={}):
        """ Lancement de la sauvegarde """
        listeFichiersLocaux = dictSauvegarde["sauvegarde_fichiers_locaux"]
        listeFichiersReseau = dictSauvegarde["sauvegarde_fichiers_reseau"]
        nom = dictSauvegarde["sauvegarde_nom"]
        repertoire = dictSauvegarde["sauvegarde_repertoire"]
        motdepasse = dictSauvegarde["sauvegarde_motdepasse"]
        listeEmails = dictSauvegarde["sauvegarde_emails"]
        
        # Fichiers locaux
        if listeFichiersLocaux == None :
            listeFichiersLocaux = []
        else :
            listeFichiersLocaux = listeFichiersLocaux.split(";")
        
        # Fichiers réseau
        dictConnexion = None
        if listeFichiersReseau == None :
            listeFichiersReseau = []
        else :
            listeFichiersReseau = listeFichiersReseau.split(";")
            DB = GestionDB.DB() 
            if DB.echec != 1 :
                if DB.isNetwork == True :
                    dictConnexion = DB.GetParamConnexionReseau() 
            DB.Close() 
            
            if dictConnexion == None :
                dictConnexion = self.GetDictConnexion()
                if dictConnexion == False :
                    return False
            
        # Liste Emails
        if listeEmails != None :
            listeEmails = listeEmails.split(";")
        
        # Sauvegarde
        resultat = UTILS_Sauvegarde.Sauvegarde(listeFichiersLocaux, listeFichiersReseau, nom, repertoire, motdepasse, listeEmails, dictConnexion)
        if resultat == False :
            return False
        return True

    def GetDictConnexion(self):
        # Demande les paramètres de connexion
        from Dlg import DLG_Saisie_param_reseau
        intro = _(u"Pour accéder à la liste des fichiers réseau disponibles, un accès MySQL \nest nécessaire. Veuillez saisir vos paramètres de connexion réseau :")
        dlg = DLG_Saisie_param_reseau.Dialog(self.parent, intro=intro)
        if dlg.ShowModal() == wx.ID_OK:
            dictValeurs = dlg.GetDictValeurs()
            dlg.Destroy()
        else:
            dlg.Destroy()
            return False
        # Vérifie si la connexion est bonne
        resultat = DLG_Saisie_param_reseau.TestConnexion(dictValeurs)
        if resultat == False :
            dlg = wx.MessageDialog(self.parent, _(u"Echec du test de connexion.\n\nLes paramètres ne semblent pas exacts !"), _(u"Erreur"), wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return False
        return dictValeurs


    def AnnonceRappel(self):
        # Affichage à 70 % de chance
        if random.randrange(1, 100) > 70 :
            return False
        
        # Vérifie si case Ne plus Afficher cochée ou non
        if UTILS_Parametres.Parametres(mode="get", categorie="ne_plus_afficher", nom="sauvegarde_automatique", valeur=False) == True :
            return False
        
        try :
            image = wx.Bitmap(Chemins.GetStaticPath("Images/48x48/Sauvegarder.png"), wx.BITMAP_TYPE_ANY)
            message1 = _(u"Vous n'avez paramétré aucune sauvegarde automatique.\n\nSouhaitez-vous le faire maintenant ?")
            dlg = dialogs.MultiMessageDialog(self.parent, message1, caption=_(u"Rappel de sauvegarde"), msg2=None, style = wx.NO | wx.CANCEL | wx.YES | wx.YES_DEFAULT, icon=image, btnLabels={wx.ID_YES : _(u"Oui"), wx.ID_NO : _(u"Ne plus rappeler"), wx.ID_CANCEL : _(u"Pas maintenant")})
            reponse = dlg.ShowModal() 
            dlg.Destroy() 
        except :
            reponse = None
        if reponse == wx.ID_YES :
            from Dlg import DLG_Sauvegardes_auto
            dlg = DLG_Sauvegardes_auto.Dialog(self.parent)
            dlg.ShowModal() 
            dlg.Destroy()
            return wx.ID_CANCEL
        if reponse == wx.ID_NO :
            UTILS_Parametres.Parametres(mode="set", categorie="ne_plus_afficher", nom="sauvegarde_automatique", valeur=True)
        if reponse == wx.ID_CANCEL :
            return True

        return True
    
    
    
    
    

if __name__ == u"__main__":
    app = wx.App(0)
    save = Sauvegarde_auto()
    save.Start() 
    app.MainLoop()
