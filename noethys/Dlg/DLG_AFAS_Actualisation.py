# -*- coding: utf-8 -*-
"""Préparation de la déclaration d'activité AFAS actualisée de septembre."""
import datetime

import wx
import GestionDB
from Ctrl import CTRL_Profil
from Utils import UTILS_AFAS
from Utils import UTILS_AFAS_Actualisation as AFAS


class Profil(CTRL_Profil.CTRL):
    def __init__(self, parent):
        super().__init__(parent, categorie="afas_equipement")

    def Recevoir_parametres(self):
        self.Enregistrer(self.GetParent().GetConfiguration())

    def Envoyer_parametres(self, configuration=None):
        if configuration:
            self.GetParent().SetConfiguration(configuration)


class Dialog(wx.Dialog):
    def __init__(self, parent, activites, unites, options):
        super().__init__(parent, title="CAF / AFAS — Déclarations par équipement",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.unites, self.options = unites, options
        self.valeurs_par_declaration = {}
        self.cle_declaration = None
        db = GestionDB.DB()
        try:
            db.ExecuterReq("SELECT activites.IDactivite, groupes.IDgroupe, activites.nom, groupes.nom "
                           "FROM groupes INNER JOIN activites ON activites.IDactivite=groupes.IDactivite "
                           "ORDER BY activites.nom, groupes.nom;")
            self.perimetres = list(db.ResultatReq())
        finally:
            db.Close()
        self.annee = wx.SpinCtrl(self, min=2000, max=2100, initial=datetime.date.today().year)
        self.equipement = wx.TextCtrl(self)
        self.profil = Profil(self)
        self.phase = wx.Choice(self, choices=[label for cle, label in AFAS.PHASES])
        self.phase.SetSelection(2)
        self.groupes = wx.CheckListBox(self, choices=["%s / %s" % (row[2], row[3]) for row in self.perimetres])
        self.groupes.SetMinSize((-1, 120))
        self.methode = wx.Choice(self, choices=["Même période de N-1 ajustée aux jours ouverts",
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
        self.phase.Bind(wx.EVT_CHOICE, self.OnPhase)
        self.annee.Bind(wx.EVT_SPINCTRL, self.OnPhase)
        self.annee.Bind(wx.EVT_TEXT, self.OnPhase)
        sizer = wx.BoxSizer(wx.VERTICAL)
        intro = wx.StaticText(self, label="Une configuration par équipement, réutilisable pour les quatre déclarations de l’année.\n"
                              "Sélectionnez uniquement les activités/groupes du même équipement CAF.\n"
                              "Les calculs reprennent le profil et les filtres de l'état global. Les données financières restent à compléter.")
        sizer.Add(intro, 0, wx.ALL, 10)
        grille = wx.FlexGridSizer(cols=2, vgap=6, hgap=10)
        for label, controle in (("Configuration enregistrée", self.profil), ("Année", self.annee), ("Déclaration", self.phase), ("Nom de l'équipement CAF", self.equipement),
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
        self.OnPhase(None)

    def GetConfiguration(self):
        self.MemoriserValeurs()
        return dict(nom=self.equipement.GetValue(),
                    perimetres=[(row[0], row[1]) for i, row in enumerate(self.perimetres) if self.groupes.IsChecked(i)],
                    unites=self.unites, options=self.options, methode=self.methode.GetSelection(),
                    valeurs_par_declaration=self.valeurs_par_declaration)

    def SetConfiguration(self, configuration):
        self.equipement.SetValue(configuration.get("nom", ""))
        selection = configuration.get("perimetres", [])
        for i, row in enumerate(self.perimetres):
            self.groupes.Check(i, (row[0], row[1]) in selection)
        manquants = set(map(tuple, selection)) - {(r[0], r[1]) for r in self.perimetres}
        self.unites = configuration["unites"]
        self.options = configuration["options"]
        self.methode.SetSelection(configuration.get("methode", 0))
        self.valeurs_par_declaration = configuration.get("valeurs_par_declaration", {})
        self.cle_declaration = None
        self.OnPhase(None)
        if manquants:
            wx.MessageBox("Certains groupes enregistrés n'existent plus : vérifiez le périmètre avant de calculer.",
                          "Configuration AFAS", wx.OK | wx.ICON_INFORMATION, self)

    def MemoriserValeurs(self):
        if self.cle_declaration is not None:
            self.valeurs_par_declaration[self.cle_declaration] = {
                cle: controle.GetValue() for cle, controle in self.manuels.items()}

    def OnPhase(self, event):
        self.MemoriserValeurs()
        phase = AFAS.PHASES[self.phase.GetSelection()][0]
        self.cle_declaration = "%s:%s" % (self.annee.GetValue(), phase)
        valeurs = self.valeurs_par_declaration.get(self.cle_declaration, {})
        for cle, controle in self.manuels.items():
            controle.SetValue(valeurs.get(cle, ""))
        debut, fin_reel, restant, fin, situation = AFAS.Periodes(self.annee.GetValue(), phase)
        self.resultats.SetColumnWidth(1, 190)
        for col, label in ((1, "Réalisé " + AFAS.LabelPeriode(debut, fin_reel)),
                           (2, "Prévision " + AFAS.LabelPeriode(restant, fin))):
            item = self.resultats.GetColumn(col)
            item.SetText(label)
            self.resultats.SetColumn(col, item)
        self.conditions.SetLabel("États retenus : %s. AEEH : droits actifs au %s pour le réalisé.\n"
                                 "Vérifiez les présences, la facturation, les droits AEEH et le calendrier avant de déclarer."
                                 % (", ".join(self.options.get("etat_consommations", [])), situation.strftime("%d/%m")))
        self.OnMethode(None)

    def OnMethode(self, event):
        for controle in self.manuels.values():
            controle.Enable(self.methode.GetSelection() == 1 and self.phase.GetSelection() != 3)
        self.resultats.DeleteAllItems()

    def Calculer(self):
        self.resultats.DeleteAllItems()
        selection = [(row[0], row[1]) for i, row in enumerate(self.perimetres) if self.groupes.IsChecked(i)]
        rapport = AFAS.PreparerActualisation(self.annee.GetValue(), selection, self.unites, self.options,
            methode=UTILS_AFAS.METHODE_MANUEL if self.methode.GetSelection() == 1 else UTILS_AFAS.METHODE_N1_AJUSTE,
            valeurs_manuelles={cle: controle.GetValue() for cle, controle in self.manuels.items()},
            phase=AFAS.PHASES[self.phase.GetSelection()][0])
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
        with wx.FileDialog(self, "Exporter la préparation AFAS", defaultFile="AFAS-%s-%s.csv" % (rapport["phase"], rapport["annee"]),
                           wildcard="CSV (*.csv)|*.csv", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialogue:
            if dialogue.ShowModal() == wx.ID_OK:
                try:
                    AFAS.ExporterCSV(dialogue.GetPath(), rapport, self.equipement.GetValue().strip())
                except OSError as erreur:
                    wx.MessageBox(str(erreur), "Export impossible", wx.OK | wx.ICON_ERROR, self)
