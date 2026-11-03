#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Auteur:           Ivan LUCAS
# Copyright:       (c) 2010-16 Ivan LUCAS
# Licence:         Licence GNU GPL
#------------------------------------------------------------------------


import Chemins
from Utils.UTILS_Traduction import _
import wx
import os
import time
try :
    import psutil
    IMPORT_PSUTIL_OK = True
except :
    IMPORT_PSUTIL_OK = False

import subprocess
import paramiko

from Utils import UTILS_Parametres
from Utils import UTILS_Config
from Utils import UTILS_Portail_securite


class ServeurConnecthys():
    def __init__(self, parent):
        self.parent = parent
        self.pid = ""
        self.isrunning = False
        self.dict_parametres = self.parent.ctrl_notebook.GetCtrlParametres().GetValeurs()
        if self.dict_parametres["hebergement_type"] == 2 :
            if self.dict_parametres["ssh_utilisateur"] == "root" :
                dlg = wx.MessageDialog(None, _(u"L utilisation de l utilisateur root pour l accès SSH/SFTP est dangereuse !!!"), _(u"SSH/SFTP Warning"), wx.OK | wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
                self.ssh = None
            else :
                self.ssh = self.OpenSSHConnec()

    def OpenSSHConnec(self) :
        ssh = None
        try :
            ssh = paramiko.SSHClient()
            UTILS_Portail_securite.ConfigurerPolitiqueSSH(ssh, self.dict_parametres)
            key_filename = self.dict_parametres.get("ssh_key_file") or None
            password = self.dict_parametres.get("ssh_mdp") or None
            ssh.connect(self.dict_parametres["ssh_serveur"], port=int(self.dict_parametres["ssh_port"]), username=self.dict_parametres["ssh_utilisateur"], password=password, key_filename=key_filename)
            return ssh
        except Exception as err:
            # La cle hote est verifiee avant toute authentification si une
            # empreinte a ete renseignee ; libere le transport meme sur echec.
            if ssh is not None:
                try:
                    ssh.close()
                except Exception:
                    pass
            self.parent.EcritLog(_(u"PROBLEME..."))
            self.parent.EcritLog(err)
            print(("Connection SSH/SFTP impossible :", err))

    def CloseSSHConnect(self, ssh=None) :
        try :
            ssh.close()
        except Exception as err:
            self.parent.EcritLog(_(u"PROBLEME..."))
            self.parent.EcritLog(err)
            print(("Deconnection SSH/SFTP impossible :", err))


    def GetServerStatus(self):
        """ Retourne le status du serveur Connecthys"""
        server_is_running = False
        if self.dict_parametres["hebergement_type"] == 0 :
            if IMPORT_PSUTIL_OK :
                try :
                    for p in psutil.process_iter():
                        if "python" in p.name() :
                            for nom in p.cmdline() :
                                if "run.py" in nom :
                                    server_is_running = True
                except Exception as err :
                    print("Erreur dans detection processus serveur Connecthys :", err)
        elif self.dict_parametres["hebergement_type"] == 1 :
            return False
        elif self.dict_parametres["hebergement_type"] == 2 and self.ssh != None:
            server_is_running = len(self.GetListeProcessBySSH()) > 0
        else :
            server_is_running = False

        self.isrunning = server_is_running
        return server_is_running

    def Demarrer_serveur(self, event):
        self.parent.EcritLog(_(u"Lancement du serveur Connecthys"))
        if self.dict_parametres["hebergement_type"] == 0 :
            self.Demarrer_serveurLocal()
        elif self.dict_parametres["hebergement_type"] == 2 :
            self.Demarrer_serveurBySSH()

        # Vérifie si le process est bien lancé
        time.sleep(2)
        if self.GetServerStatus() == True :
            self.parent.EcritLog(_(u"Serveur démarré"))
            dlg = wx.MessageDialog(None, _(u"Le serveur Connecthys a bien été démarré !"), _(u"Serveur Connecthys"), wx.OK | wx.ICON_INFORMATION)
            dlg.ShowModal()
            dlg.Destroy()
        else :
            self.parent.EcritLog(_(u"[ERREUR] Le serveur n'a pas pu être démarré"))
            dlg = wx.MessageDialog(None, _(u"Le serveur Connecthys n'a pas pu être démarré !"), _(u"Serveur Connecthys"), wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()

    def Demarrer_serveurLocal(self) :

        # Récupération des paramètres
        rep = self.dict_parametres["hebergement_local_repertoire"]
        options = self.dict_parametres["serveur_options"]
        chemin_executable = os.path.join(rep, "run.py")

        if rep == "" or os.path.isfile(chemin_executable) == False :
            dlg = wx.MessageDialog(None, _(u"Le chemin du répertoire d'installation de Connecthys n'est pas valide !"), _(u"Accès impossible"), wx.OK | wx.ICON_INFORMATION)
            dlg.ShowModal()
            dlg.Destroy()
            return

        process_ok = False
        for chemin_python in ["python", "C:/Python27/python.exe"] :
            args = [chemin_python, chemin_executable]
            for arg in options.split(" ") :
                if arg != "" :
                    args.append(arg)

            try :
                p = subprocess.Popen(args, shell=True, cwd=rep)
                process_ok = True
                break
            except Exception as err :
                print("Erreur lancement Connecthys :", err)
                print("args =", args)
                self.parent.EcritLog(_(u"Erreur dans le lancement du serveur Connecthys :"))
                self.parent.EcritLog(err)
                process_ok = False

        if process_ok == False :
            self.parent.EcritLog(_(u"[ERREUR] Le serveur n'a pas pu être démarré"))
            dlg = wx.MessageDialog(None, _(u"Le serveur Connecthys n'a pas pu être démarré !"), _(u"Serveur Connecthys"), wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()


    def Demarrer_serveurBySSH(self) :
        # Récupération des paramètres
        rep = self.dict_parametres["ssh_repertoire"]
        options = self.dict_parametres["serveur_options"]
        chemin_executable = os.path.join(rep, "run.py")

        if rep == "" :
            dlg = wx.MessageDialog(None, _(u"Le chemin du répertoire d'installation de Connecthys n'est pas valide !"), _(u"Accès impossible"), wx.OK | wx.ICON_INFORMATION)
            dlg.ShowModal()
            dlg.Destroy()
            return

        args = "python " +  str(chemin_executable)
        for arg in options.split(" ") :
            if arg != "" :
                args = args + " " + arg

        commande = "cd " + str(rep) + ";" + str(args)
        #self.parent.EcritLog(_(u"[DEBUG] commande: %s") % commande)
        stdin, stdout, stderr = self.ssh.exec_command(commande)

    def Arreter_serveur(self, event):
        self.parent.EcritLog(_(u"Arrêt du serveur Connecthys"))
        if self.dict_parametres["hebergement_type"] == 0 :
            self.Arreter_serveurLocal()
        elif self.dict_parametres["hebergement_type"] == 2 :
            self.Arreter_serveurBySSH()

        # Vérifie si le process est bien stoppé
        time.sleep(0.5)
        if self.GetServerStatus() == False :
            self.parent.EcritLog(_(u"Serveur stoppé"))
            dlg = wx.MessageDialog(None, _(u"Le serveur Connecthys a bien été stoppé !"), _(u"Serveur Connecthys"), wx.OK | wx.ICON_INFORMATION)
            dlg.ShowModal()
            dlg.Destroy()
        else :
            self.parent.EcritLog(_(u"[ERREUR] Le serveur n'a pas pu être stoppé"))
            dlg = wx.MessageDialog(None, _(u"Le serveur Connecthys n'a pas pu être stoppé !"), _(u"Serveur Connecthys"), wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()

    def Arreter_serveurLocal(self):
        """ Kill les process déjà ouverts """
        for p in self.GetListeProcessLocal() :
            p.kill()

    def Arreter_serveurBySSH(self):
        """ Kill les process déjà ouverts """
        liste_process = self.GetListeProcessBySSH()
        if len(liste_process) == 0 :
            return False
        for process_pid in liste_process :
            commande = "kill " + process_pid
            self.ssh.exec_command(commande)
        return True

    def GetListeProcessLocal(self):
        """ Recherche les process ouverts du portail """
        listeProcess = []
        if IMPORT_PSUTIL_OK :
            for p in psutil.process_iter():
                if "python" in p.name() :
                    for nom in p.cmdline() :
                        if "run.py" in nom and p not in listeProcess :
                            listeProcess.append(p)
        return listeProcess

    def GetListeProcessBySSH(self):
        """ Recherche les process ouverts du portail via SSH"""
        listeProcess = []

        stdin, stdout, stderr = self.ssh.exec_command('ps -eo pid=,comm=,args=')
        for line in stdout.readlines() :
            elements = line.strip().split(None, 2)
            if len(elements) == 3 :
                pid, commande, arguments = elements
                if "python" in commande.lower() and "run.py" in arguments :
                    listeProcess.append(pid)
        return listeProcess

if __name__ == u"__main__":
#    app = wx.App(0)
    pass
