#!/usr/bin/env python
# -*- coding: utf-8 -*-
#-----------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Auteur:           Ivan LUCAS
# Copyright:       (c) 2010-11 Ivan LUCAS
# Licence:         Licence GNU GPL
#-----------------------------------------------------------


import Chemins
from Utils import UTILS_Adaptations
from Utils import UTILS_Dates
from Utils import UTILS_PeriodesSaison
from Utils.UTILS_Traduction import _
import wx
from Ctrl import CTRL_Bouton_image
import datetime
import calendar
import GestionDB
if 'phoenix' in wx.PlatformInfo:
    from wx.adv import DatePickerCtrl, DP_DROPDOWN, EVT_DATE_CHANGED
else :
    from wx import DatePickerCtrl, DP_DROPDOWN, EVT_DATE_CHANGED



class MyDatePickerCtrl(DatePickerCtrl):
    def __init__(self, parent):
        DatePickerCtrl.__init__(self, parent, -1, style=DP_DROPDOWN)
        self.parent = parent
        self.Bind(EVT_DATE_CHANGED, self.OnDateChanged)
        self.Bind(wx.EVT_CHILD_FOCUS, self.OnFocus)
            
    def OnFocus(self,event):
        event.Skip(False)       #évite la propagation vers le 'PySwigObject' object    

    def SetDate(self, dateDD=None):
        jour = dateDD.day
        mois = dateDD.month-1
        annee = dateDD.year
        date = wx.DateTime()
        date.Set(jour, mois, annee)
        self.SetValue(date)
    
    def GetDate(self):
        date = self.GetValue()
        dateDD = datetime.date(date.GetYear(), date.GetMonth()+1, date.GetDay())
        return dateDD
    
    def OnDateChanged(self, event):
        self.GetParent().OnSelection()


class CTRL_Annee(wx.SpinCtrl):
    def __init__(self, parent):
        wx.SpinCtrl.__init__(self, parent, -1, min=1977, max=2999) 
        self.parent = parent
        self.SetMinSize((60, -1))
        self.SetToolTip(wx.ToolTip(_(u"Sélectionnez une année")))
        annee_actuelle = datetime.date.today().year
        self.SetAnnee(annee_actuelle)
    
    def SetAnnee(self, annee=None):
        self.SetValue(annee)
    
    def GetAnnee(self):
        return self.GetValue()

    def GetDatesSelections(self):
        annee = self.GetAnnee()
        return [(datetime.date(annee, 1, 1), datetime.date(annee, 12, 31))]


class CTRL_ListBox(wx.ListBox):
    def __init__(self, parent, selection_multiple=True):
        self.selection_multiple = selection_multiple
        style = wx.LB_EXTENDED if selection_multiple else wx.LB_SINGLE
        wx.ListBox.__init__(self, parent, -1, style=style)
        self.parent = parent
        if selection_multiple:
            self.SetToolTip(wx.ToolTip(_(u"Sélectionnez une ou plusieurs périodes avec les touches SHIFT ou CTRL")))
        else:
            self.SetToolTip(wx.ToolTip(_(u"Sélectionnez une période")))
        self.listeChoix = []

    def GetSelectionIndices(self):
        """Retourne les index sélectionnés sans surcharger l'API wx native."""
        if self.selection_multiple:
            return list(wx.ListBox.GetSelections(self))
        index = wx.ListBox.GetSelection(self)
        if index == wx.NOT_FOUND:
            return []
        return [index]
    
    def SetListeChoix(self, listeChoix=[], conserveSelections=False):
        # Format : (nomItem, date_debut, date_fin)
        self.listeChoix = listeChoix
        listeSelections = self.GetSelectionIndices()
        self.Clear()
        listeItems = []
        for nomItem, date_debut, date_fin in listeChoix :
            listeItems.append(nomItem)
        self.Set(listeItems)
        if conserveSelections == True :
            for indexSelection in listeSelections :
                self.Select(indexSelection)
    
    def GetDatesSelections(self):
        listeSelections = self.GetSelectionIndices()
        listeDatesSelections = []
        for indexSelection in listeSelections :
            date_debut = self.listeChoix[indexSelection][1]
            date_fin = self.listeChoix[indexSelection][2]
            listeDatesSelections.append((date_debut, date_fin))
        return listeDatesSelections
    
    def SetSelectionIndex(self, indexSelection=None):
        try :
            self.Select(indexSelection)
            self.EnsureVisible(indexSelection)
        except Exception as err :
            pass
    
    def SetVisibleSelection(self):
        try :
            indexSelection = self.GetSelectionIndices()[0]
            self.Select(indexSelection)
            self.EnsureVisible(indexSelection)
        except Exception as err :
            pass
        

# --------------------------------------------------------------------------------------------------------
class Mois(wx.Panel):
    def __init__(self, parent, selection_multiple=True):
        wx.Panel.__init__(self, parent, id=-1, style=wx.TAB_TRAVERSAL)
        self.parent = parent
        self.listeMois = [_(u"Janvier"), _(u"Février"), _(u"Mars"), _(u"Avril"), _(u"Mai"), _(u"Juin"), _(u"Juillet"), _(u"Août"), _(u"Septembre"), _(u"Octobre"), _(u"Novembre"), _(u"Décembre")]
        # Controles
        self.label_annee = wx.StaticText(self, -1, _(u"Année :"))
        self.ctrl_annee = CTRL_Annee(self)
        self.label_mois = wx.StaticText(self, -1, _(u"Mois :"))
        self.ctrl_mois = CTRL_ListBox(self, selection_multiple=selection_multiple)
        # Layout
        grid_sizer_mois = wx.FlexGridSizer(rows=2, cols=2, vgap=5, hgap=5)
        grid_sizer_mois.Add(self.label_annee, 0, wx.LEFT|wx.TOP|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)
        grid_sizer_mois.Add(self.ctrl_annee, 0, wx.TOP, 5)
        grid_sizer_mois.Add(self.label_mois, 0, wx.ALIGN_RIGHT, 0)
        grid_sizer_mois.Add(self.ctrl_mois, 0, wx.RIGHT|wx.BOTTOM|wx.EXPAND, 5)
        self.SetSizer(grid_sizer_mois)
        grid_sizer_mois.AddGrowableRow(1)
        grid_sizer_mois.AddGrowableCol(1)
        # Binds
        self.ctrl_annee.Bind(wx.EVT_SPINCTRL, self.OnSelectionAnnee)
        self.ctrl_mois.Bind(wx.EVT_LISTBOX, self.OnSelectionMois)
        # Commandes
        self.MAJ()
        mois_actuel = datetime.date.today().month
        self.ctrl_mois.SetSelectionIndex(mois_actuel-1)
        self.ctrl_mois.EnsureVisible(True)

    def OnSelectionAnnee(self, event):
        self.MAJ()
        self.GetGrandParent().OnSelection()
    
    def OnSelectionMois(self, event):
        self.GetGrandParent().OnSelection()
    
    def GetDatesSelections(self):
        return self.ctrl_mois.GetDatesSelections()

    def MAJ(self):
        annee = self.ctrl_annee.GetAnnee()
        listeChoix = []
        index = 0
        for nomMois in self.listeMois :
            nbreJoursMois = calendar.monthrange(annee, index+1)[1]
            date_debut = datetime.date(annee, index+1, 1)
            date_fin = datetime.date(annee, index+1, nbreJoursMois)
            listeChoix.append( (nomMois, date_debut, date_fin) )
            index += 1
        self.ctrl_mois.SetListeChoix(listeChoix, conserveSelections=True)
    
    def SetVisibleSelection(self):
        self.ctrl_mois.SetVisibleSelection()

class Annee(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, id=-1, style=wx.TAB_TRAVERSAL)
        self.parent = parent
        # Controles
        self.label_annee = wx.StaticText(self, -1, _(u"Année :"))
        self.ctrl_annee = CTRL_Annee(self)
        # Layout
        grid_sizer_annee = wx.FlexGridSizer(rows=2, cols=2, vgap=5, hgap=5)
        grid_sizer_annee.Add(self.label_annee, 0, wx.LEFT|wx.TOP|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)
        grid_sizer_annee.Add(self.ctrl_annee, 0, wx.TOP, 5)
        self.SetSizer(grid_sizer_annee)
        grid_sizer_annee.AddGrowableRow(1)
        grid_sizer_annee.AddGrowableCol(1)
        # Binds
        self.ctrl_annee.Bind(wx.EVT_SPINCTRL, self.OnSelectionAnnee)
        
    def OnSelectionAnnee(self, event):
        self.GetGrandParent().OnSelection()
    
    def GetDatesSelections(self):
        return self.ctrl_annee.GetDatesSelections()
        

class Vacances(wx.Panel):
    def __init__(self, parent, selection_multiple=True):
        wx.Panel.__init__(self, parent, id=-1, style=wx.TAB_TRAVERSAL)
        self.parent = parent
        # Controles
        self.label_annee = wx.StaticText(self, -1, _(u"Année :"))
        self.ctrl_annee = CTRL_Annee(self)
        self.label_periode = wx.StaticText(self, -1, _(u"Période :"))
        self.ctrl_periode = CTRL_ListBox(self, selection_multiple=selection_multiple)
        # Layout
        grid_sizer_vacances = wx.FlexGridSizer(rows=2, cols=2, vgap=5, hgap=5)
        grid_sizer_vacances.Add(self.label_annee, 0, wx.LEFT|wx.TOP|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)
        grid_sizer_vacances.Add(self.ctrl_annee, 0, wx.TOP, 5)
        grid_sizer_vacances.Add(self.label_periode, 0, wx.ALIGN_RIGHT, 0)
        grid_sizer_vacances.Add(self.ctrl_periode, 0, wx.RIGHT|wx.BOTTOM|wx.EXPAND, 5)
        self.SetSizer(grid_sizer_vacances)
        grid_sizer_vacances.AddGrowableRow(1)
        grid_sizer_vacances.AddGrowableCol(1)
        # Binds
        self.ctrl_annee.Bind(wx.EVT_SPINCTRL, self.OnSelectionAnnee)
        self.ctrl_periode.Bind(wx.EVT_LISTBOX, self.OnSelectionPeriode)
        # Commandes
        self.MAJ()
    
    def OnSelectionAnnee(self, event):
        self.MAJ()
        self.GetGrandParent().OnSelection()
    
    def OnSelectionPeriode(self, event):
        self.GetGrandParent().OnSelection()

    def GetDatesSelections(self):
        return self.ctrl_periode.GetDatesSelections()
    
    def MAJ(self):
        annee = self.ctrl_annee.GetAnnee()
        # Récupération des périodes de vacances
        DB = GestionDB.DB()
        req = """SELECT nom, date_debut, date_fin
        FROM vacances 
        WHERE annee=%d
        ORDER BY date_debut
        ;""" % annee
        DB.ExecuterReq(req)
        listeVacances = DB.ResultatReq()
        DB.Close()
        # Création de la liste de choix pour le listBox
        listeChoix = []
        index = 0
        for nom, date_debut, date_fin in listeVacances :
            date_debutDD = UTILS_Dates.DateEngEnDateDD(date_debut)
            date_finDD = UTILS_Dates.DateEngEnDateDD(date_fin)
            listeChoix.append( (nom, date_debutDD, date_finDD) )
            index += 1
        self.ctrl_periode.SetListeChoix(listeChoix, conserveSelections=False)

    def SetVisibleSelection(self):
        self.ctrl_periode.SetVisibleSelection()



class CTRL_Saison(wx.ComboBox):
    """Choix compact d'une saison sans table préchargée de milliers d'années."""

    NB_SAISONS_AUTOUR = 10

    def __init__(self, parent):
        wx.ComboBox.__init__(
            self,
            parent,
            -1,
            choices=[],
            style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER,
        )
        self.annee_min_choix = None
        self.annee_max_choix = None
        self.SetMinSize((110, -1))
        self.SetToolTip(wx.ToolTip(
            _(u"Sélectionnez une saison ou saisissez directement son année de début")
        ))
        self.SetAnnee(UTILS_PeriodesSaison.GetAnneeDebutSaison())

    def _Formater(self, annee):
        return u"%d - %d" % (annee, annee + 1)

    def _Parser(self, valeur):
        try:
            texte = str(valeur).strip()
            annee = int(texte.split("-")[0].strip())
        except Exception:
            return None
        if annee < 1 or annee >= datetime.MAXYEAR:
            return None
        return annee

    def _ChoixContiennent(self, annee):
        return (
            self.annee_min_choix is not None
            and self.annee_min_choix <= annee <= self.annee_max_choix
        )

    def _RafraichirChoix(self, annee_centre):
        debut = max(1, annee_centre - self.NB_SAISONS_AUTOUR)
        fin = min(datetime.MAXYEAR - 1, annee_centre + self.NB_SAISONS_AUTOUR)

        # wx.ComboBox.Set() efface brièvement la zone texte sous Windows.
        # On ne reconstruit donc la petite liste dynamique que si la saison
        # demandée sort réellement de la fenêtre déjà chargée.
        if self._ChoixContiennent(annee_centre):
            return

        self.Freeze()
        try:
            self.Set([self._Formater(annee) for annee in range(debut, fin + 1)])
            self.annee_min_choix = debut
            self.annee_max_choix = fin
        finally:
            self.Thaw()

    def SetAnnee(self, annee):
        try:
            annee = int(annee)
        except Exception:
            annee = UTILS_PeriodesSaison.GetAnneeDebutSaison()

        annee = max(1, min(datetime.MAXYEAR - 1, annee))
        self._RafraichirChoix(annee)
        wx.ComboBox.SetValue(self, self._Formater(annee))

    def GetAnnee(self):
        annee = self._Parser(wx.ComboBox.GetValue(self))
        if annee is None:
            annee = UTILS_PeriodesSaison.GetAnneeDebutSaison()
            self.SetAnnee(annee)
        return annee

    def Normaliser(self):
        annee = self.GetAnnee()
        self.SetAnnee(annee)
        return annee


class Saison(wx.Panel):
    """Raccourcis de période basés sur une saison de septembre à août."""

    def __init__(self, parent):
        wx.Panel.__init__(self, parent, id=-1, style=wx.TAB_TRAVERSAL)
        self.parent = parent

        self.listePeriodes = [
            ("saison", _(u"Saison complète (sept.-août)")),
            ("trimestre_1", _(u"1er trimestre (sept.-déc.)")),
            ("trimestre_2", _(u"2e trimestre (janv.-mars)")),
            ("trimestre_3", _(u"3e trimestre (avr.-août)")),
            ("semestre_1", _(u"1er semestre (sept.-févr.)")),
            ("semestre_2", _(u"2e semestre (mars-août)")),
        ]

        self.label_saison = wx.StaticText(self, -1, _(u"Saison :"))
        self.ctrl_annee = CTRL_Saison(self)
        self.label_periode = wx.StaticText(self, -1, _(u"Période :"))
        self.ctrl_periode = wx.ListBox(
            self,
            -1,
            choices=[label for code, label in self.listePeriodes],
            style=wx.LB_SINGLE,
        )
        self.ctrl_periode.SetToolTip(
            wx.ToolTip(_(u"Sélectionnez une saison, un trimestre ou un semestre"))
        )

        grid_sizer_saison = wx.FlexGridSizer(rows=2, cols=2, vgap=5, hgap=5)
        grid_sizer_saison.Add(
            self.label_saison,
            0,
            wx.LEFT | wx.TOP | wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        grid_sizer_saison.Add(
            self.ctrl_annee,
            0,
            wx.TOP | wx.RIGHT,
            5,
        )
        grid_sizer_saison.Add(self.label_periode, 0, wx.ALIGN_RIGHT, 0)
        grid_sizer_saison.Add(
            self.ctrl_periode,
            0,
            wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            5,
        )
        self.SetSizer(grid_sizer_saison)
        grid_sizer_saison.AddGrowableRow(1)
        grid_sizer_saison.AddGrowableCol(1)

        self.ctrl_annee.Bind(wx.EVT_COMBOBOX, self.OnSelectionAnnee)
        self.ctrl_annee.Bind(wx.EVT_TEXT_ENTER, self.OnSelectionAnnee)
        self.ctrl_periode.Bind(wx.EVT_LISTBOX, self.OnSelectionPeriode)

        self.ctrl_annee.SetAnnee(UTILS_PeriodesSaison.GetAnneeDebutSaison())
        self.ctrl_periode.SetSelection(0)

    def _GetCodeSelectionne(self):
        index = self.ctrl_periode.GetSelection()
        if index == wx.NOT_FOUND:
            return None
        return self.listePeriodes[index][0]

    def OnSelectionAnnee(self, event):
        self.ctrl_annee.Normaliser()
        self.GetGrandParent().OnSelection()
        if event is not None:
            event.Skip()

    def OnSelectionPeriode(self, event):
        self.GetGrandParent().OnSelection()

    def SetSelectionIndex(self, indexSelection=None):
        try:
            if indexSelection is not None and 0 <= indexSelection < len(self.listePeriodes):
                self.ctrl_periode.SetSelection(indexSelection)
                self.ctrl_periode.EnsureVisible(indexSelection)
        except Exception:
            pass

    def SetVisibleSelection(self):
        try:
            index = self.ctrl_periode.GetSelection()
            if index != wx.NOT_FOUND:
                self.ctrl_periode.EnsureVisible(index)
        except Exception:
            pass

    def GetDatesSelections(self):
        code = self._GetCodeSelectionne()
        if code is None:
            return []
        return [
            UTILS_PeriodesSaison.GetPeriodeSaison(
                code,
                annee_debut=self.ctrl_annee.GetAnnee(),
            )
        ]


class Dates(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, id=-1, style=wx.TAB_TRAVERSAL)
        self.parent = parent
        # Controles
        self.label_date_debut = wx.StaticText(self, -1, u"Du :")
        self.ctrl_date_debut = MyDatePickerCtrl(self)
        self.label_date_fin = wx.StaticText(self, -1, _(u"Au :"))
        self.ctrl_date_fin = MyDatePickerCtrl(self)
        # Propriétés
        self.ctrl_date_debut.SetToolTip(wx.ToolTip(_(u"Saisissez une date de début")))
        self.ctrl_date_fin.SetToolTip(wx.ToolTip(_(u"Saisissez une date de fin")))
        # Layout
        grid_sizer_dates = wx.FlexGridSizer(rows=3, cols=2, vgap=5, hgap=5)
        grid_sizer_dates.Add(self.label_date_debut, 0, wx.LEFT|wx.TOP|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)
        grid_sizer_dates.Add(self.ctrl_date_debut, 0, wx.TOP, 5)
        grid_sizer_dates.Add(self.label_date_fin, 0, wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_dates.Add(self.ctrl_date_fin, 0, wx.RIGHT|wx.BOTTOM, 5)
        self.SetSizer(grid_sizer_dates)
        grid_sizer_dates.AddGrowableCol(1)
    
    def GetDates(self):
        date_debut = self.ctrl_date_debut.GetDate()
        date_fin = self.ctrl_date_fin.GetDate()
        return [(date_debut, date_fin),]

    def OnSelection(self):
##        listeDates = self.GetDates()[0]
##        if listeDates[0] > listeDates[1] :
##            self.ctrl_date_debut.SetDate(listeDates[1])
##            listeDates = self.GetDates()
        self.GetGrandParent().OnSelection()
    
    def GetDatesSelections(self):
        return self.GetDates()


# -----------------------------------------------------------------------------------------------------------------------

class CTRL(wx.Panel):
    def __init__(self, parent, selection_multiple=True, callback_selection=None):
        u""" Sélection d'une période réutilisable dans les écrans Noethys SL. """
        wx.Panel.__init__(self, parent, id=-1, style=wx.TAB_TRAVERSAL)
        self.parent = parent
        self.nomParent = self.GetParent().GetName()
        self.callback_selection = callback_selection
        
        self.evtActif = True
        
        self.notebook = wx.Notebook(self, -1, style=wx.BK_TOP)
        # Largeur minimale pour afficher simultanément :
        # Mois | Vacances | Année | Dates | Saison, sans flèches de navigation.
        self.notebook.SetMinSize((300, -1))
        self.SetMinSize((300, -1))
        
        self.page_dates = Dates(self.notebook)
        self.page_annee = Annee(self.notebook)
        self.page_vacances = Vacances(self.notebook, selection_multiple=selection_multiple)
        self.page_mois = Mois(self.notebook, selection_multiple=selection_multiple)
        self.page_saison = Saison(self.notebook)
        
        self.notebook.AddPage(self.page_mois, _(u"Mois"))
        self.notebook.AddPage(self.page_vacances, _(u"Vacances"))
        self.notebook.AddPage(self.page_annee, _(u"Année"))
        self.notebook.AddPage(self.page_dates, _(u"Dates"))
        self.notebook.AddPage(self.page_saison, _(u"Saison"))

        self.__do_layout()
        
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnPageChanged)
        
    def __do_layout(self):
        grid_sizer_base = wx.GridSizer(rows=1, cols=1, vgap=0, hgap=0)
        grid_sizer_base.Add(self.notebook, 1, wx.EXPAND, 0)
        self.SetSizer(grid_sizer_base)
        grid_sizer_base.Fit(self)
    
    
    def OnSelection(self):
        """ Quand une sélection de période est effectuée dans l'une des pages du notebook """
        self.evtActif = False
        
        if self.nomParent == "grille" :
            listeSelections = self.GetDatesSelections()
            self.parent.SetListesPeriodes(listeSelections)
            self.parent.MAJ_grille()
        
        if self.nomParent == "informations_medicales" :
            listeSelections = self.GetDatesSelections()
            self.parent.SetListesPeriodes(listeSelections) 
        
        self.evtActif = True
        if self.callback_selection is not None:
            self.callback_selection()
            
    
    def OnPageChanged(self, event):
        """ Quand une page du notebook est sélectionnée """
        old = event.GetOldSelection()
        if old==-1:
            return
        if self.nomParent == "grille" and self.evtActif == True :
            indexPage = event.GetSelection()
            page = self.notebook.GetPage(indexPage)
            listeSelections = page.GetDatesSelections()
            self.parent.SetListesPeriodes(listeSelections)
            self.parent.MAJ_grille()
        if self.evtActif == True and self.callback_selection is not None:
            self.callback_selection()
        event.Skip()
    
    def GetDatesSelections(self):
        indexPage = self.notebook.GetSelection()
        page = self.notebook.GetPage(indexPage)
        return page.GetDatesSelections()
    
    def SetVisibleSelection(self):
        """ Si on est sur un listBox, on fait défiler jusqu'à l'item sélectionné """
        try :
            indexPage = self.notebook.GetSelection()
            page = self.notebook.GetPage(indexPage)
            if hasattr(page, "SetVisibleSelection"):
                page.SetVisibleSelection()
        except : 
            pass
    
    def SetDictDonnees(self, dictDonnees={}):
        if dictDonnees == None : return
        self.evtActif = False
        numPage = dictDonnees["page"]
        # Tolère une préférence mémorisée par une version possédant davantage
        # d'onglets (par exemple Saison) sans faire planter wx.Notebook.
        try:
            numPage = int(numPage)
        except Exception:
            numPage = 0
        if numPage < 0 or numPage >= self.notebook.GetPageCount():
            numPage = 0

        annee = dictDonnees["annee"]
        listeSelections = dictDonnees["listeSelections"]
        dateDebut = dictDonnees["dateDebut"]
        dateFin = dictDonnees["dateFin"]
        
        # Recherche la page du notebook
        self.notebook.SetSelection(numPage)
        page = self.notebook.GetPage(numPage)

        if numPage == 0 :
            # Mois
            if annee != None :
                page.ctrl_annee.SetValue(annee)
                page.MAJ()
            if 'phoenix' in wx.PlatformInfo:
                page.ctrl_mois.SetSelection(-1)
            else :
                page.ctrl_mois.DeselectAll()
            for index in listeSelections :
                page.ctrl_mois.SetSelectionIndex(index)
        
        if numPage == 1 :
            # Vacances
            if annee != None :
                page.ctrl_annee.SetValue(annee)
                page.MAJ()
            if 'phoenix' in wx.PlatformInfo:
                page.ctrl_periode.SetSelection(-1)
            else :
                page.ctrl_periode.DeselectAll()
            for index in listeSelections :
                page.ctrl_periode.SetSelectionIndex(index)
        
        if numPage == 2 :
            # Année
            if annee != None :
                page.ctrl_annee.SetValue(annee)
        
        if numPage == 3 :
            # Dates
            if dateDebut != None : page.ctrl_date_debut.SetDate(dateDebut)
            if dateFin != None : page.ctrl_date_fin.SetDate(dateFin)

        if numPage == 4 :
            # Saison
            if annee != None :
                page.ctrl_annee.SetAnnee(annee)
            if len(listeSelections) > 0 :
                page.SetSelectionIndex(listeSelections[0])
        
        self.evtActif = True
        
##        "page" : 0,
##        "listeSelections" : [2, 3, 5],
##        "annee" : 2010,
##        "dateDebut" : None,
##        "dateFin" : None,

    def GetDictDonnees(self):
        dictDonnees = {}
        numPage = self.notebook.GetSelection()
        page = self.notebook.GetPage(numPage)
        
        # Mois
        if numPage == 0 :
            dictDonnees["page"] = 0
            dictDonnees["listeSelections"] = page.ctrl_mois.GetSelectionIndices()
            dictDonnees["annee"] = page.ctrl_annee.GetValue()
            dictDonnees["dateDebut"] = None
            dictDonnees["dateFin"] = None
        
        # Vacances
        if numPage == 1 :
            dictDonnees["page"] = 1
            dictDonnees["listeSelections"] = page.ctrl_periode.GetSelectionIndices()
            dictDonnees["annee"] = page.ctrl_annee.GetValue()
            dictDonnees["dateDebut"] = None
            dictDonnees["dateFin"] = None
        
        # Année
        if numPage == 2 :
            dictDonnees["page"] = 2
            dictDonnees["listeSelections"] = []
            dictDonnees["annee"] = page.ctrl_annee.GetValue()
            dictDonnees["dateDebut"] = None
            dictDonnees["dateFin"] = None
        
        # Dates
        if numPage == 3 :
            dictDonnees["page"] = 3
            dictDonnees["listeSelections"] = []
            dictDonnees["annee"] = None
            dictDonnees["dateDebut"] = page.ctrl_date_debut.GetDate()
            dictDonnees["dateFin"] = page.ctrl_date_fin.GetDate()

        # Saison
        if numPage == 4 :
            dictDonnees["page"] = 4
            indexSelection = page.ctrl_periode.GetSelection()
            if indexSelection == wx.NOT_FOUND :
                dictDonnees["listeSelections"] = []
            else :
                dictDonnees["listeSelections"] = [indexSelection]
            dictDonnees["annee"] = page.ctrl_annee.GetAnnee()
            dictDonnees["dateDebut"] = None
            dictDonnees["dateFin"] = None
        
        dictDonnees["listePeriodes"] = self.GetDatesSelections()
        return dictDonnees
        
        
# --------------------------------------------------------------------------------------------------------------------

class MyFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        wx.Frame.__init__(self, *args, **kwds)
        panel = wx.Panel(self, -1)
        sizer_1 = wx.BoxSizer(wx.VERTICAL)
        sizer_1.Add(panel, 1, wx.ALL|wx.EXPAND)
        self.SetSizer(sizer_1)
        self.ctrl= CTRL(panel)
        sizer_2 = wx.BoxSizer(wx.VERTICAL)
        sizer_2.Add(self.ctrl, 1, wx.ALL|wx.EXPAND, 4)
        panel.SetSizer(sizer_2)
        self.Layout()
        self.CentreOnScreen()

if __name__ == '__main__':
    app = wx.App(0)
    #wx.InitAllImageHandlers()
    frame_1 = MyFrame(None, -1, _(u"TEST"), size=(800, 400))
    app.SetTopWindow(frame_1)
    frame_1.Show()
    app.MainLoop()


