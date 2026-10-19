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
from Utils import UTILS_Adaptations
from Utils.UTILS_Traduction import _
import wx
from Ctrl import CTRL_Bouton_image
import datetime
import GestionDB
from Ctrl import CTRL_Bandeau

from Dlg.DLG_Factures_generation_parametres import Panel as Page1
from Dlg.DLG_Factures_generation_selection import Panel as Page2
from Dlg.DLG_Factures_generation_actions import Panel as Page3


class Dialog(wx.Dialog):
    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, -1, name="DLG_Facturation", style=wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER|wx.MAXIMIZE_BOX|wx.MINIMIZE_BOX)
        self.parent = parent
        
        intro = _(u"Vous pouvez ici générer des factures. Page 1 : Sélectionnez des paramètres puis cliquez sur Suite pour afficher les factures disponibles. Page 2 : Cochez les factures à générer puis cliquez sur Suite. Page 3 : Vous pouvez effectuer d'autres actions sur les factures générées.")
        titre = _(u"Génération de factures")
        self.SetTitle(titre)
        self.ctrl_bandeau = CTRL_Bandeau.Bandeau(self, titre=titre, texte=intro, hauteurHtml=30, nomImage="Images/32x32/Generation.png")
        
        self.listePages = ("Page1", "Page2", "Page3")
        self.nbrePages = len(self.listePages)

        self.static_line = wx.StaticLine(self, -1)
        
        self.bouton_aide = CTRL_Bouton_image.CTRL(self, texte=_(u"Aide"), cheminImage="Images/32x32/Aide.png")
        self.bouton_retour = CTRL_Bouton_image.CTRL(self, texte=_(u"Retour"), cheminImage="Images/32x32/Fleche_gauche.png")
        self.bouton_suite = CTRL_Bouton_image.CTRL(self, texte=_(u"Suite"), cheminImage="Images/32x32/Fleche_droite.png", margesImage=(0, 0, 4, 0), positionImage=wx.RIGHT)
        self.bouton_annuler = CTRL_Bouton_image.CTRL(self, id=wx.ID_CANCEL, texte=_(u"Annuler"), cheminImage="Images/32x32/Annuler.png")
        
        self.__set_properties()
        self.__do_layout()
                
        self.Bind(wx.EVT_BUTTON, self.Onbouton_aide, self.bouton_aide)
        self.Bind(wx.EVT_BUTTON, self.Onbouton_retour, self.bouton_retour)
        self.Bind(wx.EVT_BUTTON, self.Onbouton_suite, self.bouton_suite)
        
        self.bouton_retour.Enable(False)
        self.pageVisible = 1
                        

    def Creation_Pages(self):
        """ Creation des pages """
        for numPage in range(1, self.nbrePages+1) :
            setattr(self, "page%d" % numPage, eval(self.listePages[numPage-1] + "(self)"))
            self.sizer_pages.Add(getattr(self, "page%d" % numPage), 1, wx.EXPAND, 0)
            self.sizer_pages.Layout()
            getattr(self, "page%d" % numPage).Show(False)
        self.page1.Show(True)
        self.sizer_pages.Layout()

    def __set_properties(self):
        self.bouton_aide.SetToolTip(wx.ToolTip(_(u"Cliquez ici pour obtenir de l'aide")))
        self.bouton_retour.SetToolTip(wx.ToolTip(_(u"Cliquez ici pour revenir à la page précédente")))
        self.bouton_suite.SetToolTip(wx.ToolTip(_(u"Cliquez ici pour passer à l'étape suivante")))
        self.bouton_annuler.SetToolTip(wx.ToolTip(_(u"Cliquez pour annuler")))

    def __do_layout(self):
        grid_sizer_base = wx.FlexGridSizer(rows=4, cols=1, vgap=0, hgap=0)
        # Bandeau
        grid_sizer_base.Add(self.ctrl_bandeau, 1, wx.EXPAND, 0)
        
        # Contenu
        sizer_base = wx.BoxSizer(wx.VERTICAL)
        sizer_pages = wx.BoxSizer(wx.VERTICAL)
        self.sizer_pages = sizer_pages

        grid_sizer_base.Add(sizer_pages, 1, wx.EXPAND|wx.ALL, 10)
        grid_sizer_base.Add(self.static_line, 0, wx.LEFT|wx.RIGHT|wx.EXPAND, 10)
        
        # Boutons
        grid_sizer_boutons = wx.FlexGridSizer(rows=1, cols=6, vgap=10, hgap=10)
        grid_sizer_boutons.Add(self.bouton_aide, 0, 0, 0)
        grid_sizer_boutons.Add((20, 20), 0, wx.EXPAND, 0)
        grid_sizer_boutons.Add(self.bouton_retour, 0, 0, 0)
        grid_sizer_boutons.Add(self.bouton_suite, 0, 0, 0)
        grid_sizer_boutons.Add(self.bouton_annuler, 0, wx.LEFT, 10)
        grid_sizer_boutons.AddGrowableCol(1)
        grid_sizer_base.Add(grid_sizer_boutons, 1, wx.ALL|wx.EXPAND, 10)
        grid_sizer_base.AddGrowableRow(1)
        grid_sizer_base.AddGrowableCol(0)

        self.Creation_Pages()

        self.SetSizer(grid_sizer_base)
        grid_sizer_base.Fit(self)
        self.Layout()
        self.SetMinSize(self.GetSize())
        self.CenterOnScreen()

    def Onbouton_aide(self, event):
        from Utils import UTILS_Aide
        UTILS_Aide.Aide("Gnration")

    def Onbouton_retour(self, event):
        # rend invisible la page affichée
        pageCible = eval("self.page"+str(self.pageVisible))
        pageCible.Show(False)
        # Fait apparaître nouvelle page
        self.pageVisible -= 1
        pageCible = eval("self.page"+str(self.pageVisible))
        pageCible.Show(True)
        self.sizer_pages.Layout()
        # Si on quitte l'avant-dernière page, on active le bouton Suivant
        if self.pageVisible == self.nbrePages :
            self.bouton_suite.Enable(True)
            self.bouton_suite.SetImage(Chemins.GetStaticPath("Images/32x32/Fermer.png"))
        else:
            self.bouton_suite.Enable(True)
            self.bouton_suite.SetImage(Chemins.GetStaticPath("Images/32x32/Fleche_droite.png"))
        # Si on revient à la première page, on désactive le bouton Retour
        if self.pageVisible == 1 :
            self.bouton_retour.Enable(False)
        # On active le bouton annuler
        self.bouton_annuler.Enable(True)

    def PreparerCotisationsPourApercu(self):
        """P1 #426 : consentement AVANT la sélection et l'aperçu des factures.

        Toute création est visible par le calcul page2.MAJ() qui relit ensuite
        les prestations. Aucune création au moment du bouton 'Générer'.
        """
        params = self.dictParametres
        if "cotisation" not in params.get("prestations", []):
            return True
        from Utils import UTILS_Adhesions_echeances as echeances
        from Utils import UTILS_Identification
        try:
            date_debut = params.get("date_anterieure") or params["date_debut"]
            propo = echeances.Proposer(
                date_debut=date_debut, date_fin=params["date_fin"],
                date_reference=datetime.date.today(),
                liste_activites=params["listeActivites"],
                IDcompte_payeur=params["IDcompte_payeur"])
        except Exception as err:
            wx.MessageBox(
                _(u"Impossible de vérifier les cotisations automatiques. "
                  u"Aucune cotisation n'a été créée.\n\n%s") % err,
                _(u"Cotisations - vérification nécessaire"),
                wx.OK | wx.ICON_ERROR, self)
            return False
        if propo["a_verifier"]:
            message = _(u"%d situation(s) d'adhésion nécessitent une vérification "
                        u"(participations antérieures, chevauchements ou payeur).\n"
                        u"AUCUNE cotisation automatique ne sera créée dans cette opération.\n\n"
                        u"Continuer uniquement avec les prestations déjà enregistrées ?") % len(propo["a_verifier"])
            confirmation = wx.MessageBox(
                message, _(u"Cotisations à vérifier"),
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self)
            return confirmation == wx.YES
        if not propo["propositions"]:
            return True
        somme = sum(float(p["montant"]) for p in propo["propositions"])
        message = _(u"%d cotisation(s) éligible(s) correspondant à des participations "
                    u"déjà réalisées : %.2f EUR.\n"
                    u"Aucune réservation future n'est prise en compte.\n\n"
                    u"Créer maintenant les cotisations et prestations dans la base, "
                    u"AVANT de calculer l'aperçu des factures ?\n\n"
                    u"Oui : création contrôlée (elle reste enregistrée si vous "
                    u"annulez ensuite la facture).\n"
                    u"Non : continuer sans création.\n"
                    u"Annuler : revenir aux paramètres.") % (len(propo["propositions"]), somme)
        choix = wx.MessageBox(
            message, _(u"Préparation des cotisations de la période"),
            wx.YES_NO | wx.CANCEL | wx.NO_DEFAULT | wx.ICON_QUESTION, self)
        if choix == wx.CANCEL:
            return False
        if choix != wx.YES:
            return True
        try:
            reponses = echeances.Executer(
                propo, confirmation=True,
                liste_activites=params["listeActivites"],
                IDcompte_payeur=params["IDcompte_payeur"],
                IDutilisateur=UTILS_Identification.GetIDutilisateur())
        except Exception as err:
            wx.MessageBox(
                _(u"La proposition a changé ou sa création a échoué. "
                  u"Ne générez aucune facture sans recalculer.\n\n%s") % err,
                _(u"Facturation interrompue"), wx.OK | wx.ICON_ERROR, self)
            return False
        erreurs = [r for r in reponses
                   if r.get("statut") not in ("cree", "rien_a_faire")]
        if erreurs or len(reponses) != len(propo["propositions"]):
            wx.MessageBox(
                _(u"Certaines cotisations n'ont pas pu être créées "
                  u"(%d erreur(s)). Des écritures précédentes peuvent exister. "
                  u"Revenez aux paramètres puis actualisez avant de facturer.") %
                len(erreurs), _(u"Facturation interrompue"),
                wx.OK | wx.ICON_ERROR, self)
            return False
        return True

    def Onbouton_suite(self, event):
        # Vérifie que les données de la page en cours sont valides
        validation = self.ValidationPages()
        if validation == False : return
        if self.pageVisible == 1 and not self.PreparerCotisationsPourApercu():
            return
        # Si on est déjà sur la dernière page : on termine
        if self.pageVisible == self.nbrePages :
            self.Terminer()
            return
        # Rend invisible la page affichée
        pageCible = eval("self.page"+str(self.pageVisible))
        pageCible.Show(False)
        # Fait apparaître nouvelle page
        self.pageVisible += 1
        pageCible = eval("self.page"+str(self.pageVisible))
        pageCible.MAJ() 
        pageCible.Show(True)
        self.sizer_pages.Layout()
        # Si on arrive à la dernière page, on désactive le bouton Suivant
        if self.pageVisible == self.nbrePages :
            self.bouton_suite.SetImage(Chemins.GetStaticPath("Images/32x32/Fermer.png"))
            self.bouton_suite.SetTexte(_(u"Fermer"))
            self.bouton_annuler.Enable(False)
        # Si on quitte la première page, on active le bouton Retour
        if self.pageVisible > 1 :
            self.bouton_retour.Enable(True)
        
        # Désactivation du bouton Retour si dernière page > SPECIAL FACTURATION !!!
        if self.pageVisible == self.nbrePages :            
            self.bouton_retour.Enable(False)

    def ValidationPages(self) :
        """ Validation des données avant changement de pages """
        validation = getattr(self, "page%s" % self.pageVisible).Validation()
        return validation
    
    def Terminer(self):
        # Fermeture
        self.EndModal(wx.ID_OK)
        
    def SetFamille(self, IDfamille=None):
        self.page1.SetFamille(IDfamille)
        
        
        
if __name__ == "__main__":
    app = wx.App(0)
    #wx.InitAllImageHandlers()
    IDactivite = 1
    frame_1 = Dialog(None) 
    # TESTS
    frame_1.page1.ctrl_date_debut.SetDate(datetime.date(2017, 1, 1))
    frame_1.page1.ctrl_date_fin.SetDate(datetime.date(2017, 1, 31))
    
    app.SetTopWindow(frame_1)
    frame_1.ShowModal()
    app.MainLoop()
