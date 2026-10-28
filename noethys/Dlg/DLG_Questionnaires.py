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

import GestionDB
from Ctrl import CTRL_Bandeau

from Ctrl import CTRL_Questionnaire
from Utils import UTILS_Repas_questionnaire


LISTE_CATEGORIES = [
    ("individu", _(u"Individu"), "Personnes.png"),
    ("famille", _(u"Famille"), "Famille.png"),
    ("categorie_produit", _(u"Catégorie de produits"), "Categorie_produits.png"),
    ("produit", _(u"Produit"), "Produit.png"),
    ("location", _(u"Location"), "Location.png"),
    ("location_demande", _(u"Demande de location"), "Location_demande.png"),
    ("inscription", _(u"Inscription"), "Activite.png"),
    ]


class CTRL_Type(wx.Choice):
    def __init__(self, parent, listeData=[]):
        wx.Choice.__init__(self, parent, -1)
        self.parent = parent
        self.listeCategories = LISTE_CATEGORIES
        self.SetListe()

    def SetListe(self):
        self.Clear()
        for code, label, image in self.listeCategories:
            self.Append(label)
        self.SetSelection(0)

    def SetID(self, code=None):
        index = 0
        for codeTemp, label, image in self.listeCategories:
            if codeTemp == code:
                self.SetSelection(index)
            index += 1

    def GetID(self):
        index = self.GetSelection()
        if index == -1: return None
        return self.listeCategories[index][0]


class Dialog(wx.Dialog):
    def __init__(self, parent, type="individu"):
        wx.Dialog.__init__(self, parent, -1, style=wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER|wx.MAXIMIZE_BOX|wx.MINIMIZE_BOX)
        self.parent = parent      
        self.type = type
        
        intro = _(u"Vous pouvez ici concevoir des questionnaires personnalisés pour les fiches individuelles et familiales. Commencez par créer des catégories puis paramétrez des questions basées sur les contrôles de votre choix en fonction des données à saisir : texte, liste, entier, etc...")
        titre = _(u"Questionnaires")
        self.SetTitle(titre)
        self.ctrl_bandeau = CTRL_Bandeau.Bandeau(self, titre=titre, texte=intro, hauteurHtml=30, nomImage="Images/32x32/Questionnaire.png")
        
        # Type
        self.box_questionnaire_staticbox = wx.StaticBox(self, -1, _(u"Questionnaire"))
        self.box_type_staticbox = wx.StaticBox(self, -1, _(u"Type de fiche"))
        self.label_type = wx.StaticText(self, -1, _(u"Type de fiche :"))
        self.ctrl_type = CTRL_Type(self)
        self.ctrl_type.SetID(self.type)
        self.bouton_repas = wx.Button(
            self, -1, _(u"Préparer « Type de repas »"))
        self.label_repas = wx.StaticText(
            self, -1, _(u"Questionnaire repas : non vérifié"))

        # Questionnaire
        self.ctrl_questionnaire = CTRL_Questionnaire.CTRL(self, type=type, menuActif=True, afficherInvisibles=True)
        
        self.bouton_ajouter = wx.BitmapButton(self, -1, wx.Bitmap(Chemins.GetStaticPath(u"Images/16x16/Ajouter.png"), wx.BITMAP_TYPE_ANY))
        self.bouton_modifier = wx.BitmapButton(self, -1, wx.Bitmap(Chemins.GetStaticPath(u"Images/16x16/Modifier.png"), wx.BITMAP_TYPE_ANY))
        self.bouton_supprimer = wx.BitmapButton(self, -1, wx.Bitmap(Chemins.GetStaticPath(u"Images/16x16/Supprimer.png"), wx.BITMAP_TYPE_ANY))
        self.bouton_monter = wx.BitmapButton(self, -1, wx.Bitmap(Chemins.GetStaticPath(u"Images/16x16/Fleche_haut.png"), wx.BITMAP_TYPE_ANY))
        self.bouton_descendre = wx.BitmapButton(self, -1, wx.Bitmap(Chemins.GetStaticPath(u"Images/16x16/Fleche_bas.png"), wx.BITMAP_TYPE_ANY))
        
        # Boutons
        self.bouton_aide = CTRL_Bouton_image.CTRL(self, texte=_(u"Aide"), cheminImage="Images/32x32/Aide.png")
        self.bouton_fermer = CTRL_Bouton_image.CTRL(self, texte=_(u"Fermer"), cheminImage="Images/32x32/Fermer.png")

        self.__set_properties()
        self.__do_layout()

        self.Bind(wx.EVT_CHOICE, self.OnChoixType, self.ctrl_type)
        self.Bind(wx.EVT_BUTTON, self.OnPreparerQuestionnaireRepas, self.bouton_repas)
        self.Bind(wx.EVT_BUTTON, self.OnBoutonAjouter, self.bouton_ajouter)
        self.Bind(wx.EVT_BUTTON, self.OnBoutonModifier, self.bouton_modifier)
        self.Bind(wx.EVT_BUTTON, self.OnBoutonSupprimer, self.bouton_supprimer)
        self.Bind(wx.EVT_BUTTON, self.OnBoutonMonter, self.bouton_monter)
        self.Bind(wx.EVT_BUTTON, self.OnBoutonDescendre, self.bouton_descendre)
        self.Bind(wx.EVT_BUTTON, self.OnBoutonAide, self.bouton_aide)
        self.Bind(wx.EVT_BUTTON, self.OnBoutonFermer, self.bouton_fermer)
        
        # Init contrôles
        self.ctrl_questionnaire.MAJ()
        self.bouton_repas.Enable(self.type == "individu")
        if self.type == "individu":
            self.ActualiserEtatRepas()
        

    def __set_properties(self):
        self.ctrl_type.SetToolTip(wx.ToolTip(_(u"Sélectionnez ici le type")))
        self.bouton_repas.SetToolTip(wx.ToolTip(
            _(u"Vérifier la question individuelle et proposer sa création sans doublon")))
        self.bouton_ajouter.SetToolTip(wx.ToolTip(_(u"Cliquez ici pour ajouter une catégorie ou une question")))
        self.bouton_modifier.SetToolTip(wx.ToolTip(_(u"Cliquez ici pour modifier la catégorie ou la question sélectionnée")))
        self.bouton_supprimer.SetToolTip(wx.ToolTip(_(u"Cliquez ici pour supprimer la catégorie ou la question sélectionnée")))
        self.bouton_monter.SetToolTip(wx.ToolTip(_(u"Cliquez ici pour monter la catégorie ou la question sélectionnée")))
        self.bouton_descendre.SetToolTip(wx.ToolTip(_(u"Cliquez ici pour descendre la catégorie ou la question sélectionnée")))
        self.bouton_aide.SetToolTip(wx.ToolTip(_(u"Cliquez ici pour obtenir de l'aide")))
        self.bouton_fermer.SetToolTip(wx.ToolTip(_(u"Cliquez ici pour fermer")))
        self.SetMinSize((690, 700))

    def __do_layout(self):
        grid_sizer_base = wx.FlexGridSizer(rows=4, cols=1, vgap=10, hgap=10)
        grid_sizer_boutons = wx.FlexGridSizer(rows=1, cols=4, vgap=10, hgap=10)
        box_questionnaire = wx.StaticBoxSizer(self.box_questionnaire_staticbox, wx.VERTICAL)
        grid_sizer_questionnaire = wx.FlexGridSizer(rows=1, cols=2, vgap=5, hgap=5)
        grid_sizer_boutons_questionnaire = wx.FlexGridSizer(rows=8, cols=1, vgap=5, hgap=5)
        box_type = wx.StaticBoxSizer(self.box_type_staticbox, wx.VERTICAL)
        grid_sizer_type = wx.FlexGridSizer(rows=1, cols=3, vgap=10, hgap=10)
        grid_sizer_base.Add(self.ctrl_bandeau, 0, wx.EXPAND, 0)
        grid_sizer_type.Add(self.label_type, 0, wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_type.Add(self.ctrl_type, 0, wx.EXPAND, 0)
        grid_sizer_type.Add(self.bouton_repas, 0, wx.EXPAND, 0)
        grid_sizer_type.AddGrowableCol(1)
        box_type.Add(grid_sizer_type, 0, wx.ALL|wx.EXPAND, 5)
        box_type.Add(self.label_repas, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, 5)
        grid_sizer_base.Add(box_type, 1, wx.LEFT|wx.RIGHT|wx.EXPAND, 10)
        grid_sizer_questionnaire.Add(self.ctrl_questionnaire, 1, wx.EXPAND, 0)
        grid_sizer_boutons_questionnaire.Add(self.bouton_ajouter, 0, 0, 0)
        grid_sizer_boutons_questionnaire.Add(self.bouton_modifier, 0, 0, 0)
        grid_sizer_boutons_questionnaire.Add(self.bouton_supprimer, 0, 0, 0)
        grid_sizer_boutons_questionnaire.Add((20, 20), 0, wx.EXPAND, 0)
        grid_sizer_boutons_questionnaire.Add(self.bouton_monter, 0, 0, 0)
        grid_sizer_boutons_questionnaire.Add(self.bouton_descendre, 0, 0, 0)
        grid_sizer_questionnaire.Add(grid_sizer_boutons_questionnaire, 1, wx.EXPAND, 0)
        grid_sizer_questionnaire.AddGrowableRow(0)
        grid_sizer_questionnaire.AddGrowableCol(0)
        box_questionnaire.Add(grid_sizer_questionnaire, 1, wx.ALL|wx.EXPAND, 5)
        grid_sizer_base.Add(box_questionnaire, 1, wx.LEFT|wx.RIGHT|wx.EXPAND, 10)
        grid_sizer_boutons.Add(self.bouton_aide, 0, 0, 0)
        grid_sizer_boutons.Add((20, 20), 0, wx.EXPAND, 0)
        grid_sizer_boutons.Add(self.bouton_fermer, 0, 0, 0)
        grid_sizer_boutons.AddGrowableCol(1)
        grid_sizer_base.Add(grid_sizer_boutons, 1, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND, 10)
        self.SetSizer(grid_sizer_base)
        grid_sizer_base.Fit(self)
        grid_sizer_base.AddGrowableRow(2)
        grid_sizer_base.AddGrowableCol(0)
        self.Layout()
        self.CenterOnScreen() 

    def OnChoixType(self, event):
        self.type = self.ctrl_type.GetID()
        self.ctrl_questionnaire.SetType(self.type)
        self.bouton_repas.Enable(self.type == "individu")
        if self.type == "individu":
            self.ActualiserEtatRepas()
        else:
            self.label_repas.SetLabel(_(u"Le type de repas est une question individuelle."))

    def ActualiserEtatRepas(self):
        """État de la base active, vérifié sans la modifier."""
        try:
            etat = UTILS_Repas_questionnaire.ExaminerQuestionnaire()
            textes = {
                "pret": _(u"Questionnaire repas : PRÊT (4 réponses, choix unique)"),
                "absent": _(u"Questionnaire repas : ABSENT — préparation disponible"),
                "conflit": _(u"Questionnaire repas : À CORRIGER — %s") % etat["detail"],
            }
            self.label_repas.SetLabel(textes[etat["etat"]])
            return etat
        except Exception:
            self.label_repas.SetLabel(_(u"Questionnaire repas : vérification impossible"))
            return None

    def OnPreparerQuestionnaireRepas(self, event=None):
        if self.type != "individu":
            return False
        etat = self.ActualiserEtatRepas()
        if not etat:
            wx.MessageBox(_(u"Impossible de vérifier le questionnaire. Aucune modification."),
                          _(u"Questionnaire repas"), wx.OK | wx.ICON_WARNING, self)
            return False
        if etat["etat"] == "conflit":
            wx.MessageBox(etat["detail"], _(u"Questionnaire repas à corriger"),
                          wx.OK | wx.ICON_WARNING, self)
            return False
        if etat["etat"] == "pret":
            return True
        accord = wx.MessageBox(
            _(u"Créer la question individuelle « Type de repas » avec quatre choix "
              u"exclusifs : Standard, Sans porc, Végétarien et Repas apporté par "
              u"la famille ?\n\nAucune réponse existante ni facture n'est modifiée."),
            _(u"Préparer le questionnaire repas"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self)
        if accord != wx.YES:
            return False
        try:
            resultat = UTILS_Repas_questionnaire.PreparerQuestionnaire()
            self.ctrl_questionnaire.MAJ()
            self.ActualiserEtatRepas()
            return resultat["etat"] == "pret"
        except Exception as exc:
            self.label_repas.SetLabel(_(u"Questionnaire repas : préparation refusée"))
            wx.MessageBox(_(u"Aucune création terminée : %s") % exc,
                          _(u"Questionnaire repas"), wx.OK | wx.ICON_WARNING, self)
            return False

    def OnBoutonAjouter(self, event): 
        self.ctrl_questionnaire.Ajouter()

    def OnBoutonModifier(self, event): 
        self.ctrl_questionnaire.Modifier()

    def OnBoutonSupprimer(self, event):
        self.ctrl_questionnaire.Supprimer()

    def OnBoutonMonter(self, event): 
        self.ctrl_questionnaire.Monter()

    def OnBoutonDescendre(self, event): 
        self.ctrl_questionnaire.Descendre()

    def OnBoutonAide(self, event): 
        from Utils import UTILS_Aide
        UTILS_Aide.Aide("Questionnaires")

    def OnBoutonFermer(self, event): 
        self.EndModal(wx.ID_OK)



if __name__ == u"__main__":
    app = wx.App(0)
    #wx.InitAllImageHandlers()
    dialog_1 = Dialog(None, type="individu")
    app.SetTopWindow(dialog_1)
    dialog_1.ShowModal()
    app.MainLoop()
