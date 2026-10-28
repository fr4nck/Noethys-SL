#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Auteur:          Ivan LUCAS
# Copyright:       (c) 2010-19 Ivan LUCAS
# Licence:         Licence GNU GPL
#------------------------------------------------------------------------

import Chemins
from Utils.UTILS_Traduction import _
import wx
import six
import os
import sys
import base64
import zipfile
import GestionDB
import subprocess
import shutil
import time

import GestionDB
from Utils import UTILS_Fichiers
from Utils import UTILS_Config
from Utils import UTILS_Cryptage_fichier
from Utils import UTILS_Fichiers
from Utils import UTILS_Envoi_email
from Utils import UTILS_Customize
from Utils import UTILS_SQL_Integrite
from Utils import UTILS_MySQL_backup

LISTE_CATEGORIES = [
    (_(u"Données de base"), "DATA"),
    (_(u"Photos individuelles"), "PHOTOS"),
    (_(u"Documents"), "DOCUMENTS"),
    ]

EXTENSIONS = {
    "decrypte" : "nod",
    "crypte" : "noc",
    }




def Sauvegarde(listeFichiersLocaux=[], listeFichiersReseau=[], nom="", repertoire=None, motdepasse=None, listeEmails=None, dictConnexion=None):
    """ Processus de de création du ZIP """
    # Si aucun fichier à sauvegarder
    if len(listeFichiersLocaux) == 0 and len(listeFichiersReseau) == 0 : 
        return False

    # Refuser une sauvegarde reseau qui serait silencieusement incomplete.
    # Aucun ZIP ou fichier temporaire n est encore cree a ce stade.
    if len(listeFichiersReseau) > 0 and dictConnexion is None:
        return False
    
    # Initialisation de la barre de progression
    nbreEtapes = 3
    nbreEtapes += len(listeFichiersLocaux)
    nbreEtapes += len(listeFichiersReseau)
    if motdepasse != None : nbreEtapes += 1
    if repertoire != None : nbreEtapes += 1
    if listeEmails != None : nbreEtapes += 1
    
    # Création du nom du fichier de destination
    if motdepasse != None :
        extension = EXTENSIONS["crypte"]
    else:
        extension = EXTENSIONS["decrypte"]

    # Vérifie si fichier de destination existe déjà
    if repertoire != None :
        fichierDest = u"%s/%s.%s" % (repertoire, nom, extension)
        if os.path.isfile(fichierDest) == True :
            dlg = wx.MessageDialog(None, _(u"Un fichier de sauvegarde portant ce nom existe déjà. \n\nVoulez-vous le remplacer ?"), "Attention !", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_EXCLAMATION)
            reponse = dlg.ShowModal()
            dlg.Destroy()
            if reponse != wx.ID_YES :
                return False
        # Valider le répertoire avant un long export réseau. Une procédure copiée
        # d'un autre poste peut désigner un chemin inexistant ici.
        try:
            import tempfile
            fd, essaiEcriture = tempfile.mkstemp(prefix=".noethys-writecheck-", dir=repertoire)
            os.close(fd)
            os.remove(essaiEcriture)
        except OSError as err:
            dlgErreur = wx.MessageDialog(None, _(u"Le répertoire de sauvegarde est introuvable ou inaccessible : %s\n\nVérifiez le répertoire choisi dans la procédure de sauvegarde.\n\nErreur : %s") % (repertoire, err), _(u"Erreur"), wx.OK | wx.ICON_ERROR)
            dlgErreur.ShowModal()
            dlgErreur.Destroy()
            return False

    # Récupération des paramètres de l'adresse d'expéditeur par défaut
    if listeEmails != None :
        dictAdresse = UTILS_Envoi_email.GetAdresseExpDefaut()
        if dictAdresse == None :
            dlgErreur = wx.MessageDialog(None, _(u"Envoi par Email impossible :\n\nAucune adresse d'expéditeur n'a été définie. Veuillez la saisir dans le menu Paramétrage du logiciel..."), _(u"Erreur"), wx.OK | wx.ICON_ERROR)
            dlgErreur.ShowModal() 
            dlgErreur.Destroy()
            return False

    # Fenêtre de progression
    dlgprogress = wx.ProgressDialog(_(u"Sauvegarde"), _(u"Lancement de la sauvegarde..."), maximum=nbreEtapes, parent=None, style= wx.PD_SMOOTH | wx.PD_AUTO_HIDE | wx.PD_APP_MODAL)
    
    # Création du fichier ZIP temporaire
    nomFichierTemp = u"%s.%s" % (nom, EXTENSIONS["decrypte"])
    fichierZip = zipfile.ZipFile(UTILS_Fichiers.GetRepTemp(fichier=nomFichierTemp), "w", allowZip64=True, compression=zipfile.ZIP_DEFLATED)
    numEtape = 1
    dlgprogress.Update(numEtape, _(u"Création du fichier de compression..."));numEtape += 1
    
    # Intégration des fichiers locaux
    for nomFichier in listeFichiersLocaux :
        dlgprogress.Update(numEtape, _(u"Compression du fichier %s...") % nomFichier);numEtape += 1
        fichier = UTILS_Fichiers.GetRepData(nomFichier)
        if os.path.isfile(fichier) == True :
            fichierZip.write(fichier, nomFichier)
        else :
            dlgprogress.Destroy()
            dlgErreur = wx.MessageDialog(None, _(u"Le fichier '%s' n'existe plus sur cet ordinateur. \n\nVeuillez ôter ce fichier de la procédure de sauvegarde automatique (Menu Fichier > Sauvegardes automatiques)") % nomFichier, _(u"Erreur"), wx.OK | wx.ICON_ERROR)
            dlgErreur.ShowModal() 
            dlgErreur.Destroy()
            fichierZip.close()
            os.remove(UTILS_Fichiers.GetRepTemp(fichier=nomFichierTemp))
            return False
        
    # Intégration des fichiers réseau
    if len(listeFichiersReseau) > 0 and dictConnexion != None :
        
        # Création du répertoire temporaire
        import tempfile
        repTemp = tempfile.mkdtemp(prefix="savetemp-", dir=UTILS_Fichiers.GetRepTemp(fichier=""))
        reseauTermine = False
        try:
        
            # Recherche du répertoire d'installation de MySQL
            repMySQL = GetRepertoireMySQL(dictConnexion) 
            if repMySQL == None :
                dlgprogress.Destroy()
                dlgErreur = wx.MessageDialog(None, _(u"Noethys n'a pas réussi à localiser MySQL sur votre ordinateur.\n\nNotez bien que MySQL doit être installé obligatoirement pour créer une sauvegarde réseau."), _(u"Erreur"), wx.OK | wx.ICON_ERROR)
                dlgErreur.ShowModal() 
                dlgErreur.Destroy()
                return False
        
            # Création du fichier de login
            nomFichierLoginTemp = repTemp + "/logintemp.cnf" #os.path.abspath(os.curdir) + "/" + repTemp + "/logintemp.cnf"
            CreationFichierLoginTemp(host=dictConnexion["host"], port=dictConnexion["port"], user=dictConnexion["user"], password=dictConnexion["password"], nomFichier=nomFichierLoginTemp)
        
            # Création du backup pour chaque fichier MySQL
            for nomFichier in listeFichiersReseau :
                dlgprogress.Update(numEtape, _(u"Export MySQL %s...") % nomFichier);numEtape += 1
                fichierSave = u"%s/%s.sql" % (repTemp, nomFichier)
                options = UTILS_Customize.GetValeur("sauvegarde", "options", "", ajouter_si_manquant=False)

                # Export direct : mysqldump devient l'enfant surveille de Noethys.
                # --opt re-active --lock-tables : conserver l'ordre historique.
                programme = os.path.join(repMySQL, "bin",
                                         "mysqldump.exe" if os.name == "nt" else "mysqldump")
                def progressionDump(taille):
                    dlgprogress.Update(
                        numEtape - 1,
                        _(u"Export MySQL %s : %.1f Mo produits (surveillance active)...")
                        % (nomFichier, taille / 1048576.0))

                resultatDump = UTILS_MySQL_backup.ExporterSQL(
                    programme, nomFichierLoginTemp, fichierSave, nomFichier,
                    options=options, progression=progressionDump,
                    secrets=(dictConnexion.get("user"), dictConnexion.get("password")))
                erreurDump = resultatDump["erreur"]
                if erreurDump is not None:
                    import json
                    rapport = UTILS_Fichiers.GetRepTemp(fichier="sauvegarde-diagnostic.json")
                    try:
                        with open(rapport, "w", encoding="utf-8") as fichierRapport:
                            json.dump(resultatDump, fichierRapport, ensure_ascii=False, indent=2)
                        erreurDump += u"\nDiagnostic : %s" % rapport
                    except OSError:
                        pass
                    # Aucun ZIP partiel ne doit etre considere comme une sauvegarde.
                    print(("Echec export MySQL :", nomFichier, erreurDump))
                    dlgprogress.Destroy()
                    dlgErreur = wx.MessageDialog(
                        None,
                        _(u"Une erreur a été détectée dans la procédure de sauvegarde !\n\nErreur : %s")
                        % erreurDump, _(u"Erreur"), wx.OK | wx.ICON_ERROR)
                    dlgErreur.ShowModal()
                    dlgErreur.Destroy()
                    fichierZip.close()
                    fichierTemp = UTILS_Fichiers.GetRepTemp(fichier=nomFichierTemp)
                    if os.path.isfile(fichierTemp):
                        os.remove(fichierTemp)
                    return False

                # Ajout compatible avec les restaurations historiques : deux commentaires SQL.
                # En cas d'echec, aucun ZIP partiel ne doit etre publie.
                try:
                    # Meme analyse qu'a la restauration : ne pas archiver un dump qui y serait refuse.
                    dlgprogress.Update(numEtape - 1, _(u"Vérification du dump SQL %s...") % nomFichier)
                    # L'analyse des gros dumps travaille hors du fil wx.
                    from concurrent.futures import ThreadPoolExecutor, TimeoutError as DelaiVerification
                    with ThreadPoolExecutor(max_workers=1) as verification:
                        travail = verification.submit(UTILS_SQL_Integrite.AnalyserDumpSQL,
                                                      fichierSave, exiger_fin_mysqldump=True)
                        while True:
                            try:
                                analyseSQL, erreurSQL = travail.result(timeout=0.2)
                                break
                            except DelaiVerification:
                                dlgprogress.Update(numEtape - 1, _(u"Vérification du dump SQL %s...") % nomFichier)
                    if erreurSQL is not None:
                        raise ValueError(erreurSQL)
                    UTILS_SQL_Integrite.AjouterManifesteIntegriteSQL(fichierSave)
                except Exception as err:
                    dlgprogress.Destroy()
                    dlgErreur = wx.MessageDialog(None, _(u"Impossible de fiabiliser le dump SQL : %s") % err, _(u"Erreur"), wx.OK | wx.ICON_ERROR)
                    dlgErreur.ShowModal()
                    dlgErreur.Destroy()
                    fichierZip.close()
                    fichierTemp = UTILS_Fichiers.GetRepTemp(fichier=nomFichierTemp)
                    if os.path.isfile(fichierTemp):
                        os.remove(fichierTemp)
                    return False

                # Insère le fichier Sql dans le ZIP
                try :
                    fichierZip.write(fichierSave, u"%s.sql" % nomFichier)
                except Exception as err :
                    dlgprogress.Destroy()
                    print(("insertion sql dans zip : ", err,))
                    try :
                        if six.PY2:
                            err = str(err).decode("utf8")
                    except :
                        pass
                    dlgErreur = wx.MessageDialog(None, _(u"Une erreur est survenue dans la sauvegarde !\n\nErreur : %s") % err, _(u"Erreur"), wx.OK | wx.ICON_ERROR)
                    dlgErreur.ShowModal() 
                    dlgErreur.Destroy()
                    return False

            reseauTermine = True
        except Exception as err:
            erreur = UTILS_MySQL_backup.NettoyerDiagnostic(str(err), (
                dictConnexion.get("user"), dictConnexion.get("password")))
            dlgprogress.Destroy()
            dlgErreur = wx.MessageDialog(None, _(u"La sauvegarde réseau a échoué : %s") % erreur,
                                        _(u"Erreur"), wx.OK | wx.ICON_ERROR)
            dlgErreur.ShowModal()
            dlgErreur.Destroy()
            return False
        finally:
            # Couvre aussi client absent, erreur de login ou insertion ZIP échouée.
            if not reseauTermine:
                fichierZip.close()
                fichierPartiel = UTILS_Fichiers.GetRepTemp(fichier=nomFichierTemp)
                if os.path.isfile(fichierPartiel):
                    os.remove(fichierPartiel)
            if os.path.isdir(repTemp):
                shutil.rmtree(repTemp)

    # Finalise le fichier ZIP
    fichierZip.close()
    
    # Cryptage du fichier
    if motdepasse != None :
        dlgprogress.Update(numEtape, _(u"Cryptage du fichier..."));numEtape += 1
        fichierCrypte = u"%s.%s" % (nom, EXTENSIONS["crypte"])
        motdepasse = base64.b64decode(motdepasse)
        if six.PY3:
            motdepasse = motdepasse.decode('utf8')
        ancienne_methode = UTILS_Customize.GetValeur("version_cryptage", "sauvegarde", "1", ajouter_si_manquant=False) in ("1", None)
        UTILS_Cryptage_fichier.CrypterFichier(UTILS_Fichiers.GetRepTemp(fichier=nomFichierTemp), UTILS_Fichiers.GetRepTemp(fichier=fichierCrypte), motdepasse, ancienne_methode=ancienne_methode)
        nomFichierTemp = fichierCrypte
        extension = EXTENSIONS["crypte"]
    else:
        extension = EXTENSIONS["decrypte"]
    
    # Copie le fichier obtenu dans le répertoire donné
    if repertoire != None :
        dlgprogress.Update(numEtape, _(u"Création du fichier dans le répertoire cible..."));numEtape += 1
        copieTemp = None
        try :
            # Une copie interrompue ne doit jamais écraser l'ancienne sauvegarde.
            import tempfile
            descripteur, copieTemp = tempfile.mkstemp(prefix=".noethys-save-", dir=repertoire)
            os.close(descripteur)
            shutil.copy2(UTILS_Fichiers.GetRepTemp(fichier=nomFichierTemp), copieTemp)
            os.replace(copieTemp, fichierDest)
        except Exception as err:
            print("Le repertoire de destination de sauvegarde n'existe pas : %s" % err)
            dlgprogress.Destroy()
            dlgErreur = wx.MessageDialog(None, _(u"Impossible d'enregistrer la sauvegarde dans le répertoire cible.\n\nErreur : %s") % err, _(u"Erreur"), wx.OK | wx.ICON_ERROR)
            dlgErreur.ShowModal()
            dlgErreur.Destroy()
            return False
        finally:
            if copieTemp is not None and os.path.isfile(copieTemp):
                os.remove(copieTemp)

    # Préparation du message
    message = UTILS_Envoi_email.Message(destinataires=listeEmails, sujet=_(u"Sauvegarde Noethys : %s") % nom,
                                        texte_html=_(u"Envoi de la sauvegarde de Noethys"),
                                        fichiers=[UTILS_Fichiers.GetRepTemp(fichier=nomFichierTemp),])

    # Envoi par Email
    if listeEmails != None :
        dlgprogress.Update(numEtape, _(u"Expédition de la sauvegarde par Email..."));numEtape += 1
        try :
            messagerie = UTILS_Envoi_email.Messagerie(backend=dictAdresse["moteur"], hote=dictAdresse["smtp"], port=dictAdresse["port"], utilisateur=dictAdresse["utilisateur"],
                                                      motdepasse=dictAdresse["motdepasse"], email_exp=dictAdresse["adresse"], use_tls=dictAdresse["startTLS"],
                                                      timeout=60*3, parametres=dictAdresse["parametres"])
            messagerie.Connecter()
            messagerie.Envoyer(message)
            messagerie.Fermer()
        except Exception as err:
            dlgprogress.Destroy()
            print((err,))
            if six.PY2:
                err = str(err).decode("utf8")
            dlgErreur = wx.MessageDialog(None, _(u"Une erreur a été détectée dans l'envoi par Email !\n\nErreur : %s") % err, _(u"Erreur"), wx.OK | wx.ICON_ERROR)
            dlgErreur.ShowModal() 
            dlgErreur.Destroy()
            return False
    
    # Suppression des répertoires et fichiers temporaires
    dlgprogress.Update(numEtape, _(u"Suppression des fichiers temporaires..."));numEtape += 1
    fichier = UTILS_Fichiers.GetRepTemp(fichier=u"%s.%s" % (nom, EXTENSIONS["decrypte"]))
    if os.path.isfile(fichier) == True :
        os.remove(fichier)
    fichier = UTILS_Fichiers.GetRepTemp(fichier=u"%s.%s" % (nom, EXTENSIONS["crypte"]))
    if os.path.isfile(fichier) == True :
        os.remove(fichier)
    
    # Fin du processus
    dlgprogress.Update(numEtape, _(u"Sauvegarde terminée avec succès !"))
    dlgprogress.Destroy()
    
    return True

def VerificationZip(fichier=""):
    """ Vérifie que le fichier est une archive zip valide """
    return zipfile.is_zipfile(fichier)
    
def GetListeFichiersZIP(fichier):
    """ Récupère la liste des fichiers du ZIP """
    with zipfile.ZipFile(fichier, "r") as fichierZip:
        return list(fichierZip.namelist())
    
def _NomFichierReseau(dictConnexion, fichier):
    return u"%s;%s;%s;%s[RESEAU]%s" % (
        dictConnexion["port"], dictConnexion["host"], dictConnexion["user"], dictConnexion["password"], fichier)


def _VerifierPostconditionRestaurationMySQL(dictConnexion, fichier, marqueur, objetsAttendus):
    """ Noe-032 : marqueur terminal execute et objets attendus presents, puis retrait du marqueur. """
    DB = GestionDB.DB(suffixe=None, nomFichier=_NomFichierReseau(dictConnexion, fichier))
    try:
        if getattr(DB, "echec", 1) == 1:
            return False, _(u"la base restaurée n'est pas accessible")
        try:
            resultat = UTILS_SQL_Integrite.VerifierPostconditionMySQL(DB, fichier, marqueur, objetsAttendus)
        except Exception as err:
            resultat = (False, _(u"la vérification post-restauration a échoué : %s") % err)
        nettoyageOk = UTILS_SQL_Integrite.SupprimerMarqueurMySQL(DB, marqueur)
    finally:
        DB.Close()
    if resultat[0] and nettoyageOk == False:
        return False, _(u"le marqueur terminal n'a pas pu être supprimé après vérification")
    return resultat


def _SupprimerMarqueurRestaurationMySQL(dictConnexion, fichier, marqueur):
    """ Nettoyage de secours du marqueur, y compris apres un echec du client mysql. """
    try:
        DB = GestionDB.DB(suffixe=None, nomFichier=_NomFichierReseau(dictConnexion, fichier))
    except Exception:
        return False
    try:
        if getattr(DB, "echec", 1) == 1:
            return False
        return UTILS_SQL_Integrite.SupprimerMarqueurMySQL(DB, marqueur)
    finally:
        DB.Close()


def Restauration(parent=None, fichier="", listeFichiersLocaux=[], listeFichiersReseau=[], dictConnexion=None):
    """ Restauration à partir des listes de fichiers locaux et réseau

    Noe-032 : confirmations, prerequis MySQL et controle de TOUTE l'archive
    (fichiers locaux et dumps SQL) avant la premiere ecriture locale ou MySQL.
    """
    listeFichiersRestaures = []
    dlgprogress = None
    repTemp = None

    # Initialisation de la barre de progression
    fichierZip = zipfile.ZipFile(fichier, "r")
    #fichierZip = MyZipFile(fichier, "r")

    # Refuser une restauration reseau sans connexion, avant toute extraction.
    if len(listeFichiersReseau) > 0 and dictConnexion is None:
        fichierZip.close()
        return False

    # Confirmation du remplacement des fichiers locaux Sqlite (aucune ecriture) ----------------------------------------------
    if len(listeFichiersLocaux) > 0 :

        # Vérifie qu'on les remplace bien
        listeExistantsTemp = []
        for fichier in listeFichiersLocaux :
            if os.path.isfile(UTILS_Fichiers.GetRepData(fichier)) == True :
                listeExistantsTemp.append(fichier)

        if len(listeExistantsTemp) > 0 :
            if len(listeExistantsTemp) == 1 :
                message = _(u"Le fichier '%s' existe déjà.\n\nSouhaitez-vous vraiment le remplacer ?") % listeExistantsTemp[0]
            else :
                message = _(u"Les fichiers suivants existent déjà :\n\n   - %s\n\nSouhaitez-vous vraiment les remplacer ?") % "\n   - ".join(listeExistantsTemp)
            dlg = wx.MessageDialog(parent, message, "Attention !", wx.YES_NO | wx.CANCEL |wx.NO_DEFAULT | wx.ICON_EXCLAMATION)
            reponse = dlg.ShowModal()
            dlg.Destroy()
            if reponse != wx.ID_YES :
                fichierZip.close()
                return False

    # Prerequis et confirmation des fichiers réseau MySQL (lecture seule) ----------------------------------------------------
    if len(listeFichiersReseau) > 0 :

        # Récupération de la liste des fichiers MySQL de l'ordinateur
        listeFichiersExistants = GetListeFichiersReseau(dictConnexion)

        # Recherche du répertoire d'installation de MySQL
        repMySQL = GetRepertoireMySQL(dictConnexion)
        if repMySQL == None :
            dlgErreur = wx.MessageDialog(None, _(u"Noethys n'a pas réussi à localiser MySQL sur votre ordinateur.\nNotez bien que MySQL doit être installé obligatoirement pour créer une restauration réseau."), _(u"Erreur"), wx.OK | wx.ICON_ERROR)
            dlgErreur.ShowModal()
            dlgErreur.Destroy()
            fichierZip.close()
            return False

        # Vérifie qu'on les remplace bien
        listeExistantsTemp = []
        for fichier in listeFichiersReseau :
            fichier = fichier[:-4]
            if fichier in listeFichiersExistants :
                listeExistantsTemp.append(fichier)

        if len(listeExistantsTemp) > 0 :
            if len(listeExistantsTemp) == 1 :
                message = _(u"Le fichier '%s' existe déjà.\n\nSouhaitez-vous vraiment le remplacer ?") % listeExistantsTemp[0]
            else :
                message = _(u"Les fichiers suivants existent déjà :\n\n   - %s\n\nSouhaitez-vous vraiment les remplacer ?") % "\n   - ".join(listeExistantsTemp)
            dlg = wx.MessageDialog(parent, message, "Attention !", wx.YES_NO | wx.CANCEL |wx.NO_DEFAULT | wx.ICON_EXCLAMATION)
            reponse = dlg.ShowModal()
            dlg.Destroy()
            if reponse != wx.ID_YES :
                fichierZip.close()
                return False

    try:
        # Controle prealable de toute l'archive, avant la moindre ecriture --------------------------------------------------
        # Une restauration mixte ne doit jamais remplacer les fichiers Sqlite
        # pour decouvrir ensuite qu'un dump MySQL est invalide.
        erreurControle = None
        for fichier in listeFichiersLocaux :
            try:
                # Lecture complete : le ZIP verifie le CRC du membre en fin de flux.
                with fichierZip.open(fichier) as flux:
                    while flux.read(1024 * 1024):
                        pass
            except Exception as err:
                erreurControle = _(u"Le fichier '%s' de la sauvegarde est illisible ou corrompu :\n\n%s") % (fichier, err)
                break

        dictAnalysesSQL = {}
        if erreurControle is None and len(listeFichiersReseau) > 0 :
            repTemp = UTILS_Fichiers.GetRepTemp(fichier="restoretemp")
            if os.path.isdir(repTemp) == True :
                shutil.rmtree(repTemp)
            os.mkdir(repTemp)
            for fichier in listeFichiersReseau :
                fichier = fichier[:-4]
                try:
                    fichierZip.extract(u"%s.sql" % fichier, repTemp)
                except Exception as err:
                    erreurControle = _(u"Le fichier SQL '%s' de la sauvegarde est illisible :\n\n%s") % (fichier, err)
                    break
                # Manifeste V1 (SHA-256), ligne finale mysqldump des anciens dumps,
                # syntaxe et objets attendus : refus AVANT toute creation de base ou commande mysql.
                analyseSQL, erreurSQL = UTILS_SQL_Integrite.AnalyserDumpSQL(u"%s/%s.sql" % (repTemp, fichier))
                if erreurSQL is not None :
                    erreurControle = _(u"Le fichier SQL '%s' est incomplet ou invalide :\n\n%s") % (fichier, erreurSQL)
                    break
                dictAnalysesSQL[fichier] = analyseSQL

        if erreurControle is not None :
            dlgErreur = wx.MessageDialog(None, _(u"Restauration annulée, aucune donnée n'a été modifiée.\n\n%s") % erreurControle, _(u"Erreur"), wx.OK | wx.ICON_ERROR)
            dlgErreur.ShowModal()
            dlgErreur.Destroy()
            fichierZip.close()
            return False

        # Restauration des fichiers locaux Sqlite --------------------------------------------------------------------------
        if len(listeFichiersLocaux) > 0 :
            nbreEtapes = len(listeFichiersLocaux)
            dlgprogress = wx.ProgressDialog(_(u"Merci de patienter"), _(u"Lancement de la restauration..."), maximum=nbreEtapes, parent=parent, style= wx.PD_SMOOTH | wx.PD_AUTO_HIDE | wx.PD_APP_MODAL)
            numEtape = 1

            for fichier in listeFichiersLocaux :
                dlgprogress.Update(numEtape, _(u"Restauration du fichier %s...") % fichier);numEtape += 1
                try :
                    fichierZip.extract(fichier, UTILS_Fichiers.GetRepData())
                except Exception as err:
                    dlgprogress.Destroy()
                    print(err)
                    dlg = wx.MessageDialog(None, _(u"La restauration du fichier '%s' a rencontré l'erreur suivante : \n%s") % (fichier, err), "Erreur", wx.OK| wx.ICON_ERROR)
                    dlg.ShowModal()
                    dlg.Destroy()
                    fichierZip.close()
                    return False

                listeFichiersRestaures.append(fichier[:-4])

        # Restauration des fichiers réseau MySQL -------------------------------------------------------------------------------
        if len(listeFichiersReseau) > 0 :
            try:
                # Création du fichier de login
                nomFichierLoginTemp = repTemp + "/logintemp.cnf"
                CreationFichierLoginTemp(host=dictConnexion["host"], port=dictConnexion["port"], user=dictConnexion["user"], password=dictConnexion["password"], nomFichier=nomFichierLoginTemp)

                # Restauration
                nbreEtapes = len(listeFichiersReseau)
                dlgprogress = wx.ProgressDialog(_(u"Merci de patienter"), _(u"Lancement de la restauration..."), maximum=nbreEtapes, parent=parent, style= wx.PD_SMOOTH | wx.PD_AUTO_HIDE | wx.PD_APP_MODAL)
                numEtape = 1

                for fichier in listeFichiersReseau:
                    fichier = fichier[:-4]
                    fichierRestore = u"%s/%s.sql" % (repTemp, fichier)

                    # Création de la base si elle n'existe pas, apres controle de toute l'archive.
                    if fichier not in listeFichiersExistants :
                        DB = GestionDB.DB(suffixe=None, nomFichier=_NomFichierReseau(dictConnexion, fichier), modeCreation=True)
                        echecCreation = getattr(DB, "echec", 0) == 1
                        DB.Close()
                        if echecCreation :
                            raise RuntimeError(_(u"La base MySQL '%s' n'a pas pu être créée.") % fichier)

                    # Le marqueur est ajoute a la seule copie extraite : il doit etre execute en toute fin d'import.
                    marqueurRestauration = UTILS_SQL_Integrite.AjouterMarqueurTerminalSQL(fichierRestore, fichier)
                    try:
                        # Importation du fichier SQL dans MySQL
                        dlgprogress.Update(numEtape, _(u"Restauration du fichier %s...") % fichier);numEtape += 1

                        args = u""""%sbin/mysql" --defaults-extra-file="%s" %s < "%s" """ % (repMySQL, nomFichierLoginTemp, fichier, fichierRestore)
                        print(("Chemin mysql =", args))
                        if six.PY2:
                            args = args.encode("utf8")
                        proc = subprocess.Popen(args, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE)
                        out, temp = proc.communicate()

                        # Une sortie vide ne prouve pas que la restauration a reussi.
                        if proc.returncode != 0:
                            if isinstance(out, bytes):
                                out = out.decode("utf8", "replace")
                            if not out:
                                out = u"mysql a echoue avec le code %s, sans diagnostic." % proc.returncode
                            print(("subprocess de restauration mysql :", out))
                            dlgprogress.Destroy()
                            dlgErreur = wx.MessageDialog(None, _(u"Une erreur a été détectée dans la procédure de restauration !\n\nErreur : %s") % out, _(u"Erreur"), wx.OK | wx.ICON_ERROR)
                            dlgErreur.ShowModal()
                            dlgErreur.Destroy()
                            fichierZip.close()
                            return False

                        # Code retour nul : verifier quand meme que la fin a ete executee et que les objets existent.
                        postconditionOk, diagnostic = _VerifierPostconditionRestaurationMySQL(
                            dictConnexion, fichier, marqueurRestauration, dictAnalysesSQL[fichier]["objets"])
                        if postconditionOk == False :
                            dlgprogress.Destroy()
                            dlgErreur = wx.MessageDialog(None, _(u"Le client MySQL n'a signalé aucune erreur, mais la restauration est incomplète :\n\n%s") % diagnostic, _(u"Erreur"), wx.OK | wx.ICON_ERROR)
                            dlgErreur.ShowModal()
                            dlgErreur.Destroy()
                            fichierZip.close()
                            return False
                    finally:
                        _SupprimerMarqueurRestaurationMySQL(dictConnexion, fichier, marqueurRestauration)

                    listeFichiersRestaures.append(fichier)

            except Exception as err:
                if dlgprogress is not None:
                    dlgprogress.Destroy()
                print(("Echec de la restauration MySQL :", err))
                dlgErreur = wx.MessageDialog(None, _(u"Une erreur a été détectée dans la procédure de restauration !\n\nErreur : %s") % err, _(u"Erreur"), wx.OK | wx.ICON_ERROR)
                dlgErreur.ShowModal()
                dlgErreur.Destroy()
                fichierZip.close()
                return False

    finally:
        if repTemp is not None and os.path.isdir(repTemp):
            shutil.rmtree(repTemp)
        # Exception imprevue : ne jamais laisser l'archive verrouillee (close est idempotent).
        fichierZip.close()

    # Fin de la procédure
    if dlgprogress is not None:
        dlgprogress.Destroy()
    fichierZip.close()
    return listeFichiersRestaures
    

def GetListeFichiersReseau(dictValeurs={}):
    """ Récupère la liste des fichiers MySQL existants 
         dictValeurs = valeurs de connexion
    """
    hote = dictValeurs["hote"]
    utilisateur = dictValeurs["utilisateur"]
    motdepasse = dictValeurs["mdp"]
    port = dictValeurs["port"]

    DB = GestionDB.DB(nomFichier=u"%s;%s;%s;%s[RESEAU]" % (port, hote, utilisateur, motdepasse))
    if DB.echec == 1 :
        DB.Close()
        return []
    
    DB.ExecuterReq("SHOW DATABASES;")
    listeValeurs = DB.ResultatReq()
    DB.Close()
    
    listeDatabases = []
    for valeurs in listeValeurs :
        listeDatabases.append(valeurs[0])
    
    return listeDatabases

REP_CLIENT_MYSQL_EMBARQUE = "mysql-client"

def GetRepertoireMySQLEmbarque():
    """ Répertoire des clients mysql/mysqldump livrés avec Noethys (bin/), ou None. """
    chemin = Chemins.GetMainPath(REP_CLIENT_MYSQL_EMBARQUE)
    for programme in ("mysql.exe", "mysqldump.exe") :
        if not os.path.isfile(os.path.join(chemin, "bin", programme)) :
            return None
    return chemin.replace("\\", "/").rstrip("/") + "/"

def GetRepertoireMySQL(dictValeurs={}):
    """ Récupère le répertoire d'installation MySQL 
         dictValeurs = valeurs de connexion
    """
    # Récupération du chemin de MySQL à partir de la base de données

    # 1- Recherche automatique
    if "linux" in sys.platform :
        if os.path.isfile(u"/usr/bin/mysqldump") and os.path.isfile(u"/usr/bin/mysql") :
            return u"/usr/"
    else :

        # Clients MySQL 5.7 fournis avec le paquet Windows : prioritaires, un client
        # installé plus récent (8.x) n'étant pas compatible avec un serveur 5.7.
        chemin = GetRepertoireMySQLEmbarque()
        if chemin is not None :
            return chemin

        # Vérifie le chemin Canon (x86)
        chemin = "C:/Program Files (x86)/Canon/Easy-WebPrint EX/"
        if os.path.isfile(chemin + "bin/mysql.exe") :
            return chemin
        
        # Vérifie le chemin Canon
        chemin = "C:/Program Files/Canon/Easy-WebPrint EX/"
        if os.path.isfile(chemin + "bin/mysql.exe") :
            return chemin
        
        # Vérifie le chemin MySQL classique
        try :
            listeFichiers1 = os.listdir(u"C:/")
            for fichier1 in listeFichiers1 :
                
                if "Program" in fichier1 :
                    listeFichiers2 = os.listdir(u"C:/%s" % fichier1)
                    for fichier2 in listeFichiers2 :
                        if "MySQL" in fichier2 :
                            listeFichiers3 = os.listdir(u"C:/%s/%s" % (fichier1, fichier2))
                            listeFichiers3.sort(reverse=True)
                            for fichier3 in listeFichiers3 :
                                if "MySQL Server" in fichier3 :
                                    chemin = u"C:/%s/%s/%s/" % (fichier1, fichier2, fichier3)
                                    if os.path.isfile(chemin + "bin/mysql.exe") :
                                        return chemin
        except :
            pass
        
    # 2- Recherche dans le fichier Config
    try :
        chemin = UTILS_Config.GetParametre("sauvegarde_cheminmysql", defaut=None)
        if chemin != None :
            if os.path.isdir(chemin) :
                return chemin
    except :
        pass
        
    # 3- Demande le chemin à l'utilisateur
    try :
        if "linux" in sys.platform :
            message = _(u"Pour effectuer la sauvegarde de fichiers réseau, mysqlclient doit être installé. Sélectionnez ici le répertoire où se trouve 'mysqldump' sur votre ordinateur.")
        else :
            message = _(u"Pour effectuer la sauvegarde de fichiers réseau, Noethys \ndoit utiliser les outils de MySQL. Sélectionnez ici le répertoire qui se nomme 'MySQL Server...' sur votre ordinateur.")
        dlg = wx.DirDialog(None, message, style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            chemin = dlg.GetPath() + u"/"
            dlg.Destroy()    
        else:
            dlg.Destroy()    
            return None
    except :
        pass
    
    try :
        if os.path.isdir(chemin + _(u"bin/")) :
            UTILS_Config.SetParametre("sauvegarde_cheminmysql", chemin)
            return chemin
    except :
        pass
        
    return None

def _ValeurOptionMySQL(valeur):
    """ Valeur entre guillemets d'un fichier d'options MySQL : sans cela, '#' ouvre
        un commentaire et les espaces de bord sont retires (mot de passe tronque). """
    valeur = u"%s" % valeur
    for avant, apres in ((u"\\", u"\\\\"), (u'"', u'\\"'), (u"\n", u"\\n"), (u"\r", u"\\r"), (u"\t", u"\\t")):
        valeur = valeur.replace(avant, apres)
    return u'"%s"' % valeur

def CreationFichierLoginTemp(host="", user="", port="3306", password="", nomFichier=""):
    password = GestionDB.DecodeMdpReseau(password)
    if os.path.isfile(nomFichier) == True :
        os.remove(nomFichier)
    contenu = u"[client]\nhost=%s\nuser=%s\nport=%s\npassword=%s\n" % tuple(
        _ValeurOptionMySQL(valeur) for valeur in (host, user, port, password))
    # UTF-8 comme la connexion GestionDB ; fichier lisible du seul utilisateur (POSIX).
    descripteur = os.open(nomFichier, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(descripteur, "wb") as fichier:
        fichier.write(contenu.encode("utf-8"))


if __name__ == u"__main__":
    app = wx.App(0)
    from Dlg import DLG_Sauvegarde
    frame_1 = DLG_Sauvegarde.Dialog(None)
    app.SetTopWindow(frame_1)
    frame_1.ShowModal()
    app.MainLoop()
