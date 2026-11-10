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
from Utils import UTILS_Attente
from Utils import UTILS_Etapes_ui
from Utils import UTILS_Diagnostic_ui
from Ctrl import CTRL_Bouton_image
import sys
import datetime

import wx.lib.agw.labelbook as LB
import wx.lib.agw.flatnotebook as FNB
import wx.lib.agw.hyperlink as Hyperlink

import wx.html as  html
import wx.lib.wxpTag 

##for item in sorted(sys.modules.keys()):
##    if "STATS" in item :
##        print 'delete ' + str(sys.modules[item])
##        del(sys.modules[item])


from Ctrl import CTRL_Bandeau
from Ctrl import CTRL_Stats_objets
from Dlg import DLG_Stats_parametres

from Utils import UTILS_Stats_modeles as MODELES
from Utils import UTILS_Stats_individus as INDIVIDUS
from Utils import UTILS_Stats_familles as FAMILLES



def DateEngFr(textDate):
    text = str(textDate[8:10]) + "/" + str(textDate[5:7]) + "/" + str(textDate[:4])
    return text


class Hyperlien(Hyperlink.HyperLinkCtrl):
    def __init__(self, parent, id=-1, label="", infobulle="", URL="", ID=None, size=(-1, -1), pos=(0, 0)):
        Hyperlink.HyperLinkCtrl.__init__(self, parent, id, label, URL=URL, size=size, pos=pos)
        self.parent = parent
        self.ID = ID
        self.URL = URL
        
        # Construit l'hyperlink
        self.SetFont(wx.Font(7, wx.SWISS, wx.NORMAL, wx.NORMAL, False))
        self.AutoBrowse(False)
        self.SetColours("BLUE", "BLUE", "BLUE")
        self.SetUnderlines(False, False, True)
        self.SetBold(False)
        self.EnableRollover(True)
        self.SetToolTip(wx.ToolTip(infobulle))
        self.UpdateLink()
        self.DoPopup(False)
        self.Bind(Hyperlink.EVT_HYPERLINK_LEFT, self.OnLeftLink)
    
    def OnLeftLink(self, event):
        if self.URL == "selectionner" : self.parent.Coche(True)
        if self.URL == "deselectionner" : self.parent.Coche(False)
        if self.URL == "parametres" : self.parent.ModificationParametres()
        self.UpdateLink()
        


class HtmlPrintout(wx.html.HtmlPrintout):
    def __init__(self, html=""):
        wx.html.HtmlPrintout.__init__(self)
        self.SetHtmlText(html)
        self.SetMargins(10, 10, 10, 10, spaces=0)


class CTRL_Parametres(wx.html.HtmlWindow):
    def __init__(self, parent):
        wx.html.HtmlWindow.__init__(self, parent, id=-1, style=wx.SUNKEN_BORDER | wx.NO_FULL_REPAINT_ON_RESIZE)
        if "gtk2" in wx.PlatformInfo:
            self.SetStandardFonts()
        self.SetMinSize((-1, 120))
        self.periode = None
        self.dictParametres = {}
    
    def SetParametres(self, dictParametres={}):
        self.dictParametres = dictParametres

    def MAJ(self):
        """ Création de la source HTML """
        html = ""
        
        if ("mode" in self.dictParametres) == False or len(self.dictParametres["listeActivites"]) == 0 :
            return
        
        # Période
        if self.dictParametres["mode"] == "inscrits" :
            html += _(u"<U><B>Période :</B></U> Aucune")
        else:
            html += _(u"<U><B>Période :</B></U> %s") % self.dictParametres["periode"]["label"]
        html += u"<BR><BR>"
        
        # Activités
        listeActivites = self.dictParametres["listeActivites"]
        if len(listeActivites) == 0 :
            html += _(u"<U><B>Activités :</B></U> Aucune")
        else :
            html += _(u"<U><B>Activités : </B></U><UL>")
            for IDactivite in listeActivites :
                nomActivite = self.dictParametres["dictActivites"][IDactivite]
                html += u"<LI>%s</LI>" % nomActivite
            html += u"</UL>"

        # Options
        
        
        
        # Finalisation du html
        html = _(u"<html><head><title>Paramètres</title></head><body><FONT SIZE=-1>%s</FONT></body></html>") % html
        self.SetPage(html)



class MyHtml(html.HtmlWindow):
    def __init__(self, parent):
        html.HtmlWindow.__init__(self, parent, id=-1, style=wx.NO_FULL_REPAINT_ON_RESIZE)
        self.parent = parent
        if "gtk2" in wx.PlatformInfo:
            self.SetStandardFonts()

    def OnLinkClicked(self, linkinfo):
        code = linkinfo.GetHref()
        figure = self.parent.GetGrandParent().baseHTML.GetFigure(code)
        from Dlg import DLG_Zoom_graphe
        dlg = DLG_Zoom_graphe.Dialog(self, figure=figure)
        dlg.ShowModal() 
        dlg.Destroy()
        


class Dialog(wx.Dialog):
    def __init__(self, parent, q442_configuration=None, q442_sites=None):
        wx.Dialog.__init__(self, parent, -1, name="DLG_Stats", style=wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER|wx.MAXIMIZE_BOX|wx.MINIMIZE_BOX)
        self.parent = parent
        self.couleurFond = wx.SystemSettings.GetColour(30)

        # Q442 est inactif par defaut. Seul un appelant ayant qualifie
        # explicitement sites, unites, groupes et tarifs peut l'activer.
        self._q442_configuration = q442_configuration
        self._q442_sites = q442_sites
        self.dictParametres = {}

####Liste d'objets ici
        self.listeObjets = [

            {"nom" : _(u"Individus"), "code" : "individus", "image" : None, "ctrl_notebook" : None, "visible" : True, "pages" : [
            
                    {"nom" : _(u"Nombre"), "code" : "individus_nombre", "image" : None, "ctrl_html" : None, "visible" : True, "objets" : [
                            INDIVIDUS.Texte_nombre_individus(),
                            INDIVIDUS.Tableau_nombre_individus(),
                            INDIVIDUS.Graphe_nombre_individus(),
                            ]},

                    {"nom" : _(u"Ancienneté"), "code" : "individus_anciennete", "image" : None, "ctrl_html" : None, "visible" : True, "objets" : [
                            INDIVIDUS.Tableau_nouveaux_individus(),
                            INDIVIDUS.Graphe_nouveaux_individus(),
                            INDIVIDUS.Graphe_arrivee_individus(),
                            INDIVIDUS.Tableau_anciens_individus(),
                            ]},

                    {"nom" : _(u"Genre"), "code" : "individus_genre", "image" : None, "ctrl_html" : None, "visible" : True, "objets" : [
                            INDIVIDUS.Tableau_repartition_genre(),
                            INDIVIDUS.Graphe_repartition_genre(),
                            ]},

                    {"nom" : _(u"Âge"), "code" : "individus_age", "image" : None, "ctrl_html" : None, "visible" : True, "objets" : [
                            INDIVIDUS.Tableau_repartition_ages(),
                            INDIVIDUS.Graphe_repartition_ages(),
                            INDIVIDUS.Tableau_repartition_annees_naiss(),
                            INDIVIDUS.Graphe_repartition_annees_naiss(),
                            INDIVIDUS.Tableau_repartition_tranches_ages(),
                            ]},

                    {"nom" : _(u"Coordonnées"), "code" : "individus_coordonnees", "image" : None, "ctrl_html" : None, "visible" : True, "objets" : [
                            INDIVIDUS.Tableau_repartition_villes(),
                            INDIVIDUS.Graphe_repartition_villes(),
                            ]},

                    {"nom" : _(u"Scolarité"), "code" : "individus_scolarite", "image" : None, "ctrl_html" : None, "visible" : True, "objets" : [
                            INDIVIDUS.Tableau_repartition_ecoles(),
                            INDIVIDUS.Graphe_repartition_ecoles(),
                            INDIVIDUS.Tableau_repartition_niveaux_scolaires(),
                            INDIVIDUS.Graphe_repartition_niveaux_scolaires(),
                            ]},

                    {"nom" : _(u"Profession"), "code" : "individus_profession", "image" : None, "ctrl_html" : None, "visible" : True, "objets" : [
                            INDIVIDUS.Tableau_activites_professionnelles(),
                            INDIVIDUS.Graphe_activites_professionnelles(),
                            ]},

                    ]},

            {"nom" : _(u"Familles"), "code" : "familles", "image" : None, "ctrl_notebook" : None, "visible" : True, "pages" : [

                    {"nom" : _(u"Nombre"), "code" : "familles_nombre", "image" : None, "ctrl_html" : None, "visible" : True, "objets" : [
                            FAMILLES.Texte_nombre_familles(),
                            FAMILLES.Tableau_nombre_familles(),
                            FAMILLES.Graphe_nombre_familles(),
                            ]},

                    {"nom" : _(u"Caisse"), "code" : "familles_caisse", "image" : None, "ctrl_html" : None, "visible" : True, "objets" : [
                            FAMILLES.Tableau_repartition_caisses(),
                            FAMILLES.Graphe_repartition_caisses(),
                            ]},

                    {"nom" : _(u"Composition"), "code" : "familles_composition", "image" : None, "ctrl_html" : None, "visible" : True, "objets" : [
                            FAMILLES.Tableau_nombre_membres(),
                            FAMILLES.Graphe_nombre_membres(),
                            ]},

                    {"nom" : _(u"Quotient familial"), "code" : "familles_qf", "image" : None, "ctrl_html" : None, "visible" : True, "objets" : [
                            FAMILLES.Tableau_qf_tarifs(),
                            FAMILLES.Graphe_qf_tarifs(),
                            FAMILLES.Tableau_qf_defaut(),
                            FAMILLES.Graphe_qf_defaut(),
                            ]},

                    ]},

            ]

        if self._q442_configuration is not None:
            from Utils import UTILS_Stats_qf_objets as Q442
            Q442.preparer_pages(MODELES, self.listeObjets,
                               configuration=self._q442_configuration,
                               mode="presents")

        # Bandeau
        intro = _(u"Vous pouvez ici consulter des statistiques complètes sur les activités et la période de votre choix. Ces informations sont présentées sous forme de rubrique, de pages et d'items que vous pouvez choisir d'afficher ou non. Vous pouvez ensuite imprimer ces informations sous forme de rapport hierarchisé. Cliquez sur les graphes pour accéder aux outils spécifiques.")
        titre = _(u"Statistiques")
        self.SetTitle(titre)
        self.ctrl_bandeau = CTRL_Bandeau.Bandeau(self, titre=titre, texte=intro, hauteurHtml=30, nomImage="Images/32x32/Barres.png")
        
        # Labelbook
        self.box_informations_staticbox = wx.StaticBox(self, -1, _(u"Informations"))
        self.ctrl_labelbook = LB.LabelBook(self, -1, agwStyle=LB.INB_DRAW_SHADOW | LB.INB_LEFT)

        self.baseHTML = MODELES.HTML(liste_objets=self.listeObjets) 
        self.InitLabelbook() 
        self.ctrl_labelbook.SetSelection(0) 

        # Paramètres
        self.box_parametres_staticbox = wx.StaticBox(self, -1, _(u"Paramètres"))
        self.ctrl_parametres = CTRL_Parametres(self)
        self.ctrl_parametres.MAJ() 
        self.hyper_parametres = Hyperlien(self, label=_(u"Modifier les paramètres"), infobulle=_(u"Modifier les paramètres"), URL="parametres")

        # impression
        self.box_impression_staticbox = wx.StaticBox(self, -1, _(u"Impression"))
        self.ctrl_impression = CTRL_Stats_objets.CTRL_Objets(self, liste_objets=self.listeObjets)
        self.ctrl_impression.MAJ() 
        
        self.hyper_selectionner = Hyperlien(self, label=_(u"Tout sélectionner"), infobulle=_(u"Tout sélectionner"), URL="selectionner")
        self.label_separation = wx.StaticText(self, -1, u"|")
        self.hyper_deselectionner = Hyperlien(self, label=_(u"Tout dé-sélectionner"), infobulle=_(u"Tout dé-sélectionner"), URL="deselectionner")
        
        self.bouton_imprimer = CTRL_Bouton_image.CTRL(self, texte=_(u"Imprimer"), cheminImage="Images/32x32/Imprimante.png")
        
        # Boutons
        self.bouton_export_q442 = (wx.Button(self, -1, _(u"Exporter QF (Excel / CSV)"))
                                 if self._q442_configuration is not None else None)
        self.bouton_aide = CTRL_Bouton_image.CTRL(self, texte=_(u"Aide"), cheminImage="Images/32x32/Aide.png")
        self.bouton_fermer = CTRL_Bouton_image.CTRL(self, texte=_(u"Fermer"), cheminImage="Images/32x32/Fermer.png")

        self.__set_properties()
        self.__do_layout()
        
        # Binds
        self.Bind(LB.EVT_IMAGENOTEBOOK_PAGE_CHANGED, self.OnChangeLabelbook, self.ctrl_labelbook)
        
        self.Bind(wx.EVT_BUTTON, self.OnBoutonAide, self.bouton_aide)
        self.Bind(wx.EVT_BUTTON, self.OnBoutonImprimer, self.bouton_imprimer)
        self.Bind(wx.EVT_BUTTON, self.OnBoutonFermer, self.bouton_fermer)
        if self.bouton_export_q442 is not None:
            self.Bind(wx.EVT_BUTTON, self.OnBoutonExporterQ442, self.bouton_export_q442)
                

    def __set_properties(self):
        self.ctrl_impression.SetMinSize((250, -1))
        self.bouton_aide.SetToolTip(wx.ToolTip(_(u"Cliquez ici pour obtenir de l'aide")))
        self.bouton_imprimer.SetToolTip(wx.ToolTip(_(u"Cliquez ici pour imprimer")))
        if self.bouton_export_q442 is not None:
            self.bouton_export_q442.SetToolTip(wx.ToolTip(
                _(u"Statistiques agregees sans noms : Excel ou ZIP de CSV par site")))
        self.bouton_fermer.SetToolTip(wx.ToolTip(_(u"Cliquez ici pour fermer")))
        self.SetMinSize((950, 700))

    def __do_layout(self):
        grid_sizer_base = wx.FlexGridSizer(rows=3, cols=1, vgap=10, hgap=10)
        grid_sizer_base.Add(self.ctrl_bandeau, 0, wx.EXPAND, 0)
        
        grid_sizer_contenu = wx.FlexGridSizer(rows=1, cols=2, vgap=10, hgap=10)
        
        # Labelbook
        box_informations = wx.StaticBoxSizer(self.box_informations_staticbox, wx.VERTICAL)
        box_informations.Add(self.ctrl_labelbook, 1, wx.ALL|wx.EXPAND, 5)
        grid_sizer_contenu.Add(box_informations, 0, wx.EXPAND, 0)
        
        grid_sizer_droite = wx.FlexGridSizer(rows=2, cols=1, vgap=10, hgap=10)
        
        # Paramètres
        box_parametres = wx.StaticBoxSizer(self.box_parametres_staticbox, wx.VERTICAL)
        grid_sizer_parametres = wx.FlexGridSizer(rows=2, cols=1, vgap=2, hgap=2)
        grid_sizer_parametres.Add(self.ctrl_parametres, 0, wx.EXPAND, 0)
        grid_sizer_parametres.Add(self.hyper_parametres, 0, wx.ALIGN_RIGHT, 0)
        grid_sizer_parametres.AddGrowableRow(0)
        grid_sizer_parametres.AddGrowableCol(0)
        box_parametres.Add(grid_sizer_parametres, 1, wx.ALL|wx.EXPAND, 5)
        grid_sizer_droite.Add(box_parametres, 1, wx.EXPAND, 0)
        
        # Impression
        box_impression = wx.StaticBoxSizer(self.box_impression_staticbox, wx.VERTICAL)
        grid_sizer_impression = wx.FlexGridSizer(rows=3, cols=1, vgap=2, hgap=2)
        grid_sizer_impression.Add(self.ctrl_impression, 0, wx.EXPAND, 0)
        
        grid_sizer_hyperliens = wx.FlexGridSizer(rows=1, cols=4, vgap=2, hgap=2)
        grid_sizer_hyperliens.Add( (2, 2), 0, 0, 0)
        grid_sizer_hyperliens.Add(self.hyper_selectionner, 0, 0, 0)
        grid_sizer_hyperliens.Add(self.label_separation, 0, 0, 0)
        grid_sizer_hyperliens.Add(self.hyper_deselectionner, 0, 0, 0)
        grid_sizer_hyperliens.AddGrowableCol(0)
        grid_sizer_impression.Add(grid_sizer_hyperliens, 0, wx.EXPAND, 0)
        
        grid_sizer_impression.Add(self.bouton_imprimer, 0, wx.EXPAND|wx.TOP, 5)
        grid_sizer_impression.AddGrowableRow(0)
        grid_sizer_impression.AddGrowableCol(0)
        box_impression.Add(grid_sizer_impression, 1, wx.ALL|wx.EXPAND, 5)
        grid_sizer_droite.Add(box_impression, 1, wx.EXPAND, 0)
        
        grid_sizer_droite.AddGrowableRow(1)
        grid_sizer_droite.AddGrowableCol(0)
        grid_sizer_contenu.Add(grid_sizer_droite, 1, wx.EXPAND, 0)
        
        grid_sizer_contenu.AddGrowableRow(0)
        grid_sizer_contenu.AddGrowableCol(0)
        grid_sizer_base.Add(grid_sizer_contenu, 1, wx.LEFT|wx.RIGHT|wx.EXPAND, 10)
        
        # Boutons
        grid_sizer_boutons = wx.FlexGridSizer(rows=1, cols=5, vgap=10, hgap=10)
        grid_sizer_boutons.Add(self.bouton_aide, 0, 0, 0)
        grid_sizer_boutons.Add((20, 20), 0, wx.EXPAND, 0)
        if self.bouton_export_q442 is not None:
            grid_sizer_boutons.Add(self.bouton_export_q442, 0, 0, 0)
        grid_sizer_boutons.Add(self.bouton_fermer, 0, 0, 0)
        grid_sizer_boutons.AddGrowableCol(1)
        grid_sizer_base.Add(grid_sizer_boutons, 1, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND, 10)
        
        self.SetSizer(grid_sizer_base)
        grid_sizer_base.Fit(self)
        grid_sizer_base.AddGrowableRow(1)
        grid_sizer_base.AddGrowableCol(0)
        self.Layout()
        self.CenterOnScreen() 

    def OnBoutonAide(self, event):
        from Utils import UTILS_Aide
        UTILS_Aide.Aide("Statistiques")

    def OnBoutonImprimer(self, event): 
        # Demande le type d'impression
        menuPop = UTILS_Adaptations.Menu()

        item = wx.MenuItem(menuPop, 10, _(u"Tout"))
        item.SetBitmap(wx.Bitmap(Chemins.GetStaticPath("Images/16x16/Imprimante.png"), wx.BITMAP_TYPE_PNG))
        menuPop.AppendItem(item)
        self.Bind(wx.EVT_MENU, self.Imprimer, id=10)
        
        menuPop.AppendSeparator()

        item = wx.MenuItem(menuPop, 20, _(u"La rubrique affichée"))
        item.SetBitmap(wx.Bitmap(Chemins.GetStaticPath("Images/16x16/Imprimante.png"), wx.BITMAP_TYPE_PNG))
        menuPop.AppendItem(item)
        self.Bind(wx.EVT_MENU, self.Imprimer, id=20)

        item = wx.MenuItem(menuPop, 30, _(u"La page affichée"))
        item.SetBitmap(wx.Bitmap(Chemins.GetStaticPath("Images/16x16/Imprimante.png"), wx.BITMAP_TYPE_PNG))
        menuPop.AppendItem(item)
        self.Bind(wx.EVT_MENU, self.Imprimer, id=30)
            
        self.PopupMenu(menuPop)
        menuPop.Destroy()

    def Imprimer(self, event=None):
        ID = event.GetId() 
        listeCodes = self.ctrl_impression.GetCoches() 
        
        # Imprimer tout
        with UTILS_Attente.BusyInfo(_(u"Création du rapport..."), self):
            html = u""
            if ID == 10:
                html = self.baseHTML.GetHTML(
                    mode="impression", selectionsCodes=listeCodes)
            elif ID == 20:
                indexRubrique = self.ctrl_labelbook.GetSelection()
                codeRubrique = self.RechercherElement(
                    indexRubrique=indexRubrique)[0]
                html = self.baseHTML.GetHTML(
                    mode="impression", rubrique=codeRubrique,
                    selectionsCodes=listeCodes)
            elif ID == 30:
                codeRubrique, codePage = self.RecherchePageAffichee()
                html = self.baseHTML.GetHTML(
                    mode="impression", rubrique=codeRubrique, page=codePage,
                    selectionsCodes=listeCodes)

        if len(listeCodes) == 0 or len(html) <= 50:
            dlg = wx.MessageDialog(
                self, _(u"Vous n'avez sélectionné aucune information à imprimer !"),
                _(u"Erreur"), wx.OK | wx.ICON_EXCLAMATION)
            try:
                dlg.ShowModal()
            finally:
                dlg.Destroy()
            return

        # Impression
        printout = HtmlPrintout(html)
        printout2 = HtmlPrintout(html)
        preview = wx.PrintPreview(printout, printout2)
        
##        from Utils import UTILS_Printer
##        preview_window = UTILS_Printer.PreviewFrame(preview, None, _(u"Aperçu avant impression"))
##        preview_window.Initialize()
##        preview_window.MakeModal(False)
##        preview_window.Show(True)

        preview.SetZoom(100)
        frame = wx.GetApp().GetTopWindow() 
        preview_window = wx.PreviewFrame(preview, None, _(u"Aperçu avant impression"))
        # L'aperçu conserve les images jusqu'a sa propre fermeture.
        preview_window._stats_html_owner = self.baseHTML
        preview_window.Initialize()
        # preview_window.Show(False)
        preview_window.SetPosition(frame.GetPosition())
        preview_window.SetSize(frame.GetSize())
        preview_window.Show(True)


    def _AfficherErreurQ442(self, message):
        dlg = wx.MessageDialog(self, message, _(u"Statistiques QF"),
                               wx.OK | wx.ICON_EXCLAMATION)
        try:
            dlg.ShowModal()
        finally:
            dlg.Destroy()

    def OnBoutonExporterQ442(self, event):
        """Exporter des agregats QF et tarifs sans recalculer la facturation.

        Aucune base n'est modifiee. Le mapping doit venir d'un appelant
        explicitement qualifie ; les modes Inscrits sont exclus.
        """
        if self._q442_configuration is None:
            return
        from Utils import UTILS_Stats_qf_objets as Q442
        if not Q442.est_disponible(self.dictParametres):
            self._AfficherErreurQ442(_(u"QF disponible uniquement en mode Presents "
                                      u"avec les activites du perimetre valide."))
            return

        dlg = wx.FileDialog(
            self, _(u"Exporter les statistiques QF agregees"),
            defaultFile="statistiques_qf.xlsx",
            wildcard="Classeur Excel (*.xlsx)|*.xlsx|Archive CSV par site (*.zip)|*.zip",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            destination = dlg.GetPath()
            extension = ".xlsx" if dlg.GetFilterIndex() == 0 else ".zip"
        finally:
            dlg.Destroy()
        if not destination:
            return

        from pathlib import Path
        import os
        import tempfile
        from GestionDB import DB
        cible = Path(destination)
        if cible.suffix.lower() != extension:
            cible = cible.with_suffix(extension)
        # L'ajustement d'extension peut contourner le prompt natif :
        # confirmer explicitement tout remplacement du chemin final.
        if cible.exists():
            confirmation = wx.MessageDialog(
                self, _(u"Remplacer le fichier deja present ?"),
                _(u"Confirmation"), wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)
            try:
                if confirmation.ShowModal() != wx.ID_YES:
                    return
            finally:
                confirmation.Destroy()

        temporaire = None
        try:
            connexion = DB()
            try:
                donnees = Q442.obtenir_resultat(connexion, self.dictParametres)
            finally:
                connexion.Close()

            descripteur, temporaire = tempfile.mkstemp(
                prefix=".q442-", suffix=extension, dir=str(cible.parent))
            os.close(descripteur)
            if extension == ".xlsx":
                Q442.export_xlsx_aggreges(donnees, temporaire)
            else:
                Q442.export_csv_lot_aggreges(donnees, temporaire)
            os.replace(temporaire, str(cible))
            temporaire = None
        except Exception as erreur:
            self._AfficherErreurQ442(_(u"Export QF non effectue : ") + str(erreur))
        finally:
            if temporaire is not None and os.path.exists(temporaire):
                os.unlink(temporaire)

    def OnBoutonFermer(self, event): 
        self.EndModal(wx.ID_CANCEL)
    
    def InitLabelbook(self):
        self.ctrl_labelbook.SetColour(LB.INB_TAB_AREA_BACKGROUND_COLOUR, self.couleurFond)
        self.ctrl_labelbook.SetColour(LB.INB_ACTIVE_TAB_COLOUR, (255, 255, 255) )

        # Création de l'ImageList
        self.dictImages = {
            "individus" : {"img" : wx.Bitmap(Chemins.GetStaticPath('Images/16x16/Personnes.png'), wx.BITMAP_TYPE_PNG), "index" : None},
            "familles" : {"img" : wx.Bitmap(Chemins.GetStaticPath('Images/16x16/Famille.png'), wx.BITMAP_TYPE_PNG), "index" : None},
            }
        
        il = wx.ImageList(16, 16)
        index =0
        for code, dictImage in self.dictImages.items() :
            il.Add(dictImage["img"])
            dictImage["index"] = index
            index += 1
        self.ctrl_labelbook.AssignImageList(il)

        self.listeContenu = []
        indexRubrique = 0
        for dictRubrique in self.listeObjets :
            if dictRubrique["visible"] == True :
                self.AjouterRubrique(dictRubrique["code"])
                indexRubrique += 1
    
    def AjouterRubrique(self, code=""):
        # Recherche du dictRubrique
        indexRubrique = 0
        for dictRubrique in self.listeObjets :
            if dictRubrique["visible"] == True :
                if dictRubrique["code"] == code :
                    dictRubrique["visible"] = True
                    break
                indexRubrique += 1

        # Création du notebook
        flatNoteBook = FNB.FlatNotebook(self.ctrl_labelbook, -1, agwStyle=FNB.FNB_BOTTOM 
                                                                                                            | FNB.FNB_NO_TAB_FOCUS
                                                                                                            | FNB.FNB_NO_X_BUTTON
                                                                                                            )
        flatNoteBook.SetTabAreaColour(self.couleurFond)
        
        # Mémorise le ctrl flatNoteBook
        self.listeObjets[indexRubrique]["ctrl_notebook"] = flatNoteBook
        
        # Création des pages
        listePages = []
        indexPage = 0
        for dictPage in dictRubrique["pages"] :
            if dictPage["visible"] == True :
                
                ctrl_html = MyHtml(flatNoteBook)
                flatNoteBook.AddPage(ctrl_html, dictPage["nom"])
                self.listeObjets[indexRubrique]["pages"][indexPage]["ctrl_html"] = ctrl_html
                listePages.append(dictPage["code"])
                indexPage += 1
        
        # Ajoute le notebook au labelbook
        self.Bind(FNB.EVT_FLATNOTEBOOK_PAGE_CHANGED, self.OnChangeNotebook, flatNoteBook)
        if dictRubrique["code"] in self.dictImages:
            indexImage = self.dictImages[dictRubrique["code"]]["index"]
        else:
            indexImage = -1
        self.ctrl_labelbook.AddPage(flatNoteBook, dictRubrique["nom"], imageId=indexImage)
##        self.ctrl_labelbook.InsertPage(indexRubrique, flatNoteBook, dictRubrique["nom"], imageId=-1)
        
        self.listeContenu.append((dictRubrique["code"], listePages))
    
##    def SupprimerRubrique(self, code=""):
##        global self.listeObjets
##        indexRubrique = 0
##        for dictRubrique in self.listeObjets :
##            if dictRubrique["visible"] == True :
##                if dictRubrique["code"] == code :
##                    # Suppression du notebook
##                    del dictRubrique["ctrl_notebook"]
##                    dictRubrique["ctrl_notebook"] = None
##                    dictRubrique["visible"] = False
##                    for page in dictRubrique["pages"] :
##                        page["ctrl_html"] = None
##                    # Suppression de la page du labelbook
##                    self.ctrl_labelbook.DeletePage(indexRubrique)
##                indexRubrique += 1
##        print self.listeObjets

    def MAJpageAffichee(self):
        indexRubrique = self.ctrl_labelbook.GetSelection()
        # Recherche la page à MAJ
        indexR = 0
        for dictRubrique in self.listeObjets :
            if dictRubrique["visible"] == True :
                if indexR == indexRubrique :
                    ctrl_notebook = dictRubrique["ctrl_notebook"]
                    indexPage = ctrl_notebook.GetSelection() 
                    self.MAJpage(indexRubrique, indexPage)
                indexR += 1

    def MAJpage(self, indexRubrique=None, indexPage=None):
        """Actualise une page en cedant la boucle wx entre objets statistiques."""
        codePage = None
        ctrl_html = None
        indexR = 0
        for dictRubrique in self.listeObjets:
            if dictRubrique["visible"]:
                if indexR == indexRubrique:
                    indexP = 0
                    for dictPage in dictRubrique["pages"]:
                        if dictPage["visible"]:
                            if indexP == indexPage:
                                codePage = dictPage["code"]
                                ctrl_html = dictPage["ctrl_html"]
                                break
                            indexP += 1
                    break
                indexR += 1
        if codePage is None or ctrl_html is None:
            return None

        app = wx.GetApp()
        principale = app.GetTopWindow() if app is not None else None
        with UTILS_Diagnostic_ui.mesurer(principale, "statistiques.actualisation"):
            if wx.IsMainThread() and self.IsShownOnScreen():
                # Graphiques, SQL et objets wx restent sur le thread graphique.
                # Le dialogue modal, rattache a Stats, permet les evenements
                # entre chaque calcul d'objet.
                UTILS_Etapes_ui.Executer(
                    self, self.baseHTML.MAJ_etapes(page=codePage, parent=self),
                    titre=_(u"Statistiques"),
                    texte=_(u"Actualisation des données..."))
            else:
                with UTILS_Attente.BusyInfo(
                        _(u"Actualisation des données..."), self):
                    self.baseHTML.MAJ(page=codePage)
            with UTILS_Diagnostic_ui.mesurer(principale, "statistiques.rendu_html"):
                pageHTML = self.baseHTML.GetHTML(page=codePage)
                ctrl_html.SetPage(pageHTML)

    def RechercherElement(self, indexRubrique=None, indexPage=None):
        """ retourne le codeRubrique et codePage par rapport aux index """
        codeRubrique = None
        codePage = None
        indexR = 0
        for dictRubrique in self.listeObjets :
            if dictRubrique["visible"] == True :
                if indexR == indexRubrique or indexRubrique == None :
                    codeRubrique = dictRubrique["code"]
                    ctrl_notebook = dictRubrique["ctrl_notebook"]
                    # Recherche de la page
                    indexP = 0
                    for dictPage in dictRubrique["pages"] :
                        if dictPage["visible"] == True :
                            if indexP == indexPage :
                                codePage = dictPage["code"]
                                ctrl_html = dictPage["ctrl_html"]
                            indexP += 1
                indexR += 1
        return codeRubrique, codePage
    
    def RecherchePageAffichee(self):
        indexRubrique = self.ctrl_labelbook.GetSelection()
        codeRubrique = None
        codePage = None
        # Recherche la page à MAJ
        indexR = 0
        for dictRubrique in self.listeObjets :
            if dictRubrique["visible"] == True :
                if indexR == indexRubrique :
                    ctrl_notebook = dictRubrique["ctrl_notebook"]
                    indexPage = ctrl_notebook.GetSelection() 
                    indexP = 0
                    for dictPage in dictRubrique["pages"] :
                        if dictPage["visible"] == True :
                            if indexP == indexPage :
                                codeRubrique = dictRubrique["code"]
                                codePage = dictPage["code"]
                                ctrl_html = dictPage["ctrl_html"]
                                return codeRubrique, codePage
                            indexP += 1
                indexR += 1
        return codeRubrique, codePage
        
    def OnChangeLabelbook(self, event):
        self.MAJpageAffichee() 
##        indexRubrique = self.ctrl_labelbook.GetSelection()
##        # Recherche la page à MAJ
##        indexR = 0
##        for dictRubrique in self.listeObjets :
##            if dictRubrique["visible"] == True :
##                if indexR == indexRubrique :
##                    ctrl_notebook = dictRubrique["ctrl_notebook"]
##                    indexPage = ctrl_notebook.GetSelection() 
##                    self.MAJpage(indexRubrique, indexPage)
##                indexR += 1
        
    def OnChangeNotebook(self, event):
        indexRubrique = self.ctrl_labelbook.GetSelection()
        indexPage = event.GetSelection()
        self.MAJpage(indexRubrique, indexPage)
    
    def AjouterElement(self, code="", afficher=True):
        """ Ajoute une rubrique, une page ou un objet """
        indexR = 0
        for dictRubrique in self.listeObjets :
            if dictRubrique["code"] == code :
                # Affiche la rubrique
                if etat == True and dictRubrique["visible"] == False :
                    pass
    
    def Coche(self, etat=True):
        self.ctrl_impression.Coche(etat)
    
    def ModificationParametres(self, premiere=False):
        if premiere == True :
            dateJour = datetime.date.today() 
            annee = dateJour.year
            self.dictParametres = {"mode":"presents", "periode":{"type":"annee", "annee":annee, "date_debut":datetime.date(annee, 1, 1), "date_fin":datetime.date(annee, 12, 31)}, "listeActivites":[], "dictActivites":{} }
        
        # A la premiere ouverture, Stats n'est pas encore affichee.
        # Un dialogue modal ne doit jamais appartenir a une fenetre cachee :
        # prendre le proprietaire visible, puis reprendre Stats une fois ouverte.
        parent_parametres = self if self.IsShownOnScreen() else (self.GetParent() or self)
        dlg = DLG_Stats_parametres.Dialog(parent_parametres)
        dlg.SetParametres(self.dictParametres)
        if dlg.ShowModal() == wx.ID_OK:
            self.dictParametres = dlg.GetDictParametres()
            if self._q442_configuration is not None:
                # Le dialogue de parametres historique ignore ces options.
                # Les reinjecter sans les enregistrer dans les preferences.
                self.dictParametres["q442_configuration"] = self._q442_configuration
                self.dictParametres["q442_sites"] = self._q442_sites
                self.dictParametres["q442_vue"] = "global"
            dlg.Destroy()
        else:
            dlg.Destroy()
            return False
        
        # Envoi des paramètres à l'afficheur HTML
        self.ctrl_parametres.SetParametres(self.dictParametres)
        self.ctrl_parametres.MAJ() 
        
        # Envoi des paramètres à la baseHTML
        self.baseHTML.SetParametres(self.dictParametres)
        
        # Premiere ouverture : attendre ShowModal avant de charger la page.
        # wx.CallAfter est execute au debut de la boucle de dialogue.
        if premiere:
            wx.CallAfter(self.MAJpageAffichee)
        else:
            self.MAJpageAffichee()
        return True



if __name__ == u"__main__":
    app = wx.App(0)
    #wx.InitAllImageHandlers()
    dialog_1 = Dialog(None)
    app.SetTopWindow(dialog_1)
    
    dialog_1.ModificationParametres(premiere=True) 
    
    dialog_1.ShowModal()
    app.MainLoop()
