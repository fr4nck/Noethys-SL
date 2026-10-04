# -*- coding: utf-8 -*-
"""Paramétrage des parts repas incluses dans les prestations."""
import datetime
import wx
import wx.grid
import GestionDB
from Utils import UTILS_Attestations_repas
from Utils.UTILS_Traduction import _


class Dialog(wx.Dialog):
    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, title=_(u"Repas à déduire des attestations"),
                           style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER, size=(760, 430))
        DB = GestionDB.DB()
        try:
            DB.cursor.execute('SELECT unites.IDunite, activites.nom, unites.nom FROM unites LEFT JOIN activites ON activites.IDactivite=unites.IDactivite ORDER BY activites.nom, unites.ordre, unites.IDunite')
            self.unites = {}
            for ID, activite, nom in DB.cursor.fetchall():
                label = '%s / %s' % (activite or '', nom or '')
                while label in self.unites:
                    label += ' *'
                self.unites[label] = ID
            regles = UTILS_Attestations_repas.Charger(DB)
        finally:
            DB.Close()
        base = wx.BoxSizer(wx.VERTICAL)
        texte = wx.StaticText(self, label=_(u"Sélectionnez la réservation « Repas » et la part repas incluse dans le prix facturé à la famille.\nUne ligne par période de prix. Les réglages sont conservés dans ce fichier Noethys.\nSeuls les repas liés à une prestation sont déduits ; aucune facture n'est modifiée."))
        base.Add(texte, 0, wx.ALL, 10)
        self.grille = wx.grid.Grid(self)
        self.grille.CreateGrid(0, 4)
        for col, label in enumerate([_(u"Réservation repas"), _(u"Du"), _(u"Au inclus"), _(u"Part repas (€)")]):
            self.grille.SetColLabelValue(col, label)
        for col, largeur in enumerate([310, 100, 100, 120]):
            self.grille.SetColSize(col, largeur)
        base.Add(self.grille, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        self.labels = list(self.unites)
        for regle in regles:
            labels = [label for label, ID in self.unites.items() if ID == regle['IDunite']]
            if not labels:
                label = _(u"Réservation supprimée (%s)") % regle['IDunite']
                self.unites[label] = regle['IDunite']
                self.labels.append(label)
            else:
                label = labels[0]
            self.AjouterLigne(label, regle)
        boutons = wx.BoxSizer(wx.HORIZONTAL)
        ajouter = wx.Button(self, label=_(u"Ajouter une période"))
        supprimer = wx.Button(self, label=_(u"Supprimer la période sélectionnée"))
        boutons.Add(ajouter, 0, wx.RIGHT, 8)
        boutons.Add(supprimer)
        base.Add(boutons, 0, wx.ALL, 10)
        base.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        self.SetSizer(base)
        self.Bind(wx.EVT_BUTTON, self.OnAjouter, ajouter)
        self.Bind(wx.EVT_BUTTON, self.OnSupprimer, supprimer)
        self.Bind(wx.EVT_BUTTON, self.OnValider, id=wx.ID_OK)
        self.CentreOnParent()

    def AjouterLigne(self, label='', regle=None):
        self.grille.AppendRows()
        row = self.grille.GetNumberRows() - 1
        self.grille.SetCellEditor(row, 0, wx.grid.GridCellChoiceEditor(self.labels, allowOthers=False))
        self.grille.SetCellValue(row, 0, label)
        if regle:
            for col, cle in ((1, 'date_debut'), (2, 'date_fin')):
                date = datetime.date.fromisoformat(regle[cle])
                self.grille.SetCellValue(row, col, date.strftime('%d/%m/%Y'))
            self.grille.SetCellValue(row, 3, regle['montant'])

    def OnAjouter(self, event):
        self.AjouterLigne()

    def OnSupprimer(self, event):
        if self.grille.GetNumberRows():
            self.grille.DeleteRows(self.grille.GetGridCursorRow(), 1)

    def LireRegles(self):
        if self.grille.IsCellEditControlEnabled():
            self.grille.SaveEditControlValue()
            self.grille.DisableCellEditControl()
        regles = []
        for row in range(self.grille.GetNumberRows()):
            valeurs = [self.grille.GetCellValue(row, col).strip() for col in range(4)]
            if not any(valeurs):
                continue
            if valeurs[0] not in self.unites:
                raise ValueError('Sélectionnez la réservation repas pour chaque période.')
            try:
                debut, fin = [datetime.datetime.strptime(v, '%d/%m/%Y').date() for v in valeurs[1:3]]
            except ValueError:
                raise ValueError('Saisissez les dates au format jj/mm/aaaa.')
            regles.append(dict(IDunite=self.unites[valeurs[0]], date_debut=str(debut), date_fin=str(fin), montant=valeurs[3]))
        return UTILS_Attestations_repas.ValiderRegles(regles)

    def OnValider(self, event):
        try:
            regles = self.LireRegles()
            DB = GestionDB.DB()
            try:
                UTILS_Attestations_repas.Sauver(DB, regles)
            finally:
                DB.Close()
        except Exception as erreur:
            wx.MessageBox(str(erreur), _(u"Réglages à vérifier"), wx.OK | wx.ICON_EXCLAMATION, self)
            return
        self.EndModal(wx.ID_OK)
