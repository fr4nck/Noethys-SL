# -*- coding: utf-8 -*-
"""Préparation de la déclaration d'activité AFAS actualisée de septembre."""
import datetime

import wx
import GestionDB
from Utils import UTILS_AFAS
from Utils import UTILS_AFAS_Actualisation as AFAS


class Dialog(wx.Dialog):
    def __init__(self, parent, activites, unites, options):
        super().__init__(parent, title="CAF / AFAS — Actualisée (Septembre)",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.unites, self.options = unites, options
        db = GestionDB.DB()
        try:
            db.ExecuterReq("SELECT activites.IDactivite, groupes.IDgroupe, activites.nom, groupes.nom "
                           "FROM groupes INNER JOIN activites ON activites.IDactivite=groupes.IDactivite "
                           "ORDER BY activites.nom, groupes.nom;")
            self.perimetres = [row for row in db.ResultatReq() if row[0] in activites]
        finally:
            db.Close()
        self.annee = wx.SpinCtrl(self, min=2000, max=2100, initial=datetime.date.today().year)
        self.equipement = wx.TextCtrl(self)
        self.groupes = wx.CheckListBox(self, choices=["%s / %s" % (row[2], row[3]) for row in self.perimetres])
        self.groupes.SetMinSize((-1, 120))
        self.methode = wx.Choice(self, choices=["Octobre-décembre N-1 ajusté aux jours ouverts",
                                               "Prévisionnel saisi manuellement"])
        self.methode.SetSelection(0)
        self.manuels = {cle: wx.TextCtrl(self) for cle, label in AFAS.METRIQUES}
        self.resultats = wx.ListCtrl(self, style=wx.LC_REPORT)
        for indice, (titre, largeur) in enumerate((("Heures", 240), ("Réalisé janvier–septembre", 190),
                                                   ("Prévision octobre–décembre", 200), ("Total annuel", 130))):
            self.resultats.InsertColumn(indice, titre, width=largeur)
        self.resultats.SetMinSize((-1, 145))
        calculer = wx.Button(self, label="Calculer")
        exporter = wx.Button(self, label="Exporter CSV")
        fermer = wx.Button(self, wx.ID_CANCEL, "Fermer")
        calculer.Bind(wx.EVT_BUTTON, self.OnCalculer)
        exporter.Bind(wx.EVT_BUTTON, self.OnExporter)
        self.methode.Bind(wx.EVT_CHOICE, self.OnMethode)
        sizer = wx.BoxSizer(wx.VERTICAL)
        intro = wx.StaticText(self, label="Réalisé du 1er janvier au 30 septembre, puis prévisionnel du 1er octobre au 31 décembre.\n"
                              "Sélectionnez uniquement les activités/groupes du même équipement CAF.\n"
                              "Les calculs reprennent le profil et les filtres de l'état global. Les données financières restent à compléter.")
        sizer.Add(intro, 0, wx.ALL, 10)
        grille = wx.FlexGridSizer(cols=2, vgap=6, hgap=10)
        for label, controle in (("Année", self.annee), ("Nom de l'équipement CAF", self.equipement),
                                ("Activités / groupes à réunir", self.groupes), ("Méthode de prévision", self.methode)):
            grille.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            grille.Add(controle, 1, wx.EXPAND)
        for cle, label in AFAS.METRIQUES:
            grille.Add(wx.StaticText(self, label=label + " prévisionnelles"), 0, wx.ALIGN_CENTER_VERTICAL)
            grille.Add(self.manuels[cle], 1, wx.EXPAND)
        grille.AddGrowableCol(1)
        sizer.Add(grille, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        self.conditions = wx.StaticText(self, label="États retenus : %s. AEEH : droits au 30/09 pour le réalisé.\n"
                                        "Vérifiez les présences, la facturation, les droits AEEH et le calendrier avant de déclarer."
                                        % ", ".join(options.get("etat_consommations", [])))
        sizer.Add(self.conditions, 0, wx.ALL, 10)
        sizer.Add(self.resultats, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        boutons = wx.BoxSizer(wx.HORIZONTAL)
        boutons.Add(calculer, 0, wx.RIGHT, 8)
        boutons.Add(exporter, 0, wx.RIGHT, 8)
        boutons.AddStretchSpacer()
        boutons.Add(fermer)
        sizer.Add(boutons, 0, wx.EXPAND | wx.ALL, 10)
        self.SetSizerAndFit(sizer)
        self.SetMinSize((800, 650))
        self.CenterOnParent()
        self.OnMethode(None)

    def OnMethode(self, event):
        for controle in self.manuels.values():
            controle.Enable(self.methode.GetSelection() == 1)
        self.resultats.DeleteAllItems()

    def Calculer(self):
        self.resultats.DeleteAllItems()
        selection = [(row[0], row[1]) for i, row in enumerate(self.perimetres) if self.groupes.IsChecked(i)]
        rapport = AFAS.PreparerActualisation(self.annee.GetValue(), selection, self.unites, self.options,
            methode=UTILS_AFAS.METHODE_MANUEL if self.methode.GetSelection() == 1 else UTILS_AFAS.METHODE_N1_AJUSTE,
            valeurs_manuelles={cle: controle.GetValue() for cle, controle in self.manuels.items()})
        for cle, label in AFAS.METRIQUES:
            index = self.resultats.InsertItem(self.resultats.GetItemCount(), label)
            for colonne, champ in enumerate(("realise", "prevision_restant", "total_actualise"), 1):
                self.resultats.SetItem(index, colonne, "%.2f" % rapport["lignes"][cle][champ])
        return rapport

    def OnCalculer(self, event):
        try:
            return self.Calculer()
        except Exception as erreur:
            wx.MessageBox(str(erreur), "Calcul AFAS impossible", wx.OK | wx.ICON_ERROR, self)
            return None

    def OnExporter(self, event):
        if not self.equipement.GetValue().strip():
            wx.MessageBox("Indiquez le nom de l'équipement CAF.", "Export AFAS", wx.OK | wx.ICON_INFORMATION, self)
            return
        rapport = self.OnCalculer(event)
        if rapport is None:
            return
        with wx.FileDialog(self, "Exporter la préparation AFAS", defaultFile="AFAS-septembre-%s.csv" % rapport["annee"],
                           wildcard="CSV (*.csv)|*.csv", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialogue:
            if dialogue.ShowModal() == wx.ID_OK:
                try:
                    AFAS.ExporterCSV(dialogue.GetPath(), rapport, self.equipement.GetValue().strip())
                except OSError as erreur:
                    wx.MessageBox(str(erreur), "Export impossible", wx.OK | wx.ICON_ERROR, self)
