# -*- coding: utf-8 -*-
"""Confirmation explicite des effectifs avant tout PDF / email de repas."""

import wx
import wx.grid as gridlib
from Utils.UTILS_Traduction import _
from Utils import UTILS_Repas_validation, UTILS_Repas_totaux

ENTREES = [
    ("enfants_moins_6", u"Enfants < 6"),
    ("enfants_6_et_plus", u"Enfants 6+"),
    ("animateurs_repas", u"Animateurs repas"),
    ("direction_repas", u"Direction repas"),
    ("autres_adultes_repas", u"Autres adultes"),
    ("sans_porc", u"Dont sans porc"),
]
SORTIES = [
    ("total_adultes", u"Total adultes"),
    ("repas_6_et_plus", u"6+ avec adultes"),
    ("total_repas", u"TOTAL REPAS"),
]


class Dialog(wx.Dialog):
    def __init__(self, parent, donnees):
        wx.Dialog.__init__(self, parent, -1, _(u"Verification des effectifs et des repas"),
                           style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.lignes = UTILS_Repas_validation.ConstruireControle(donnees)
        self.sans_reponse = [
            (ligne["date"], ligne["site"], ligne["service"], ligne.get("non_renseignes", 0))
            for ligne in self.lignes if ligne.get("non_renseignes", 0) > 0
        ]
        sizer = wx.BoxSizer(wx.VERTICAL)
        texte = _(u"Confirmez les quantites de chaque service. Les repas sans porc sont un sous-total, pas un supplement.")
        sizer.Add(wx.StaticText(self, -1, texte), 0, wx.EXPAND | wx.ALL, 8)
        if any(item["colonnes_non_classees"] for item in self.lignes):
            sizer.Add(wx.StaticText(self, -1,
                _(u"ATTENTION : certaines colonnes numeriques ne sont pas classees dans ce controle.")),
                0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        if self.sans_reponse:
            sizer.Add(wx.StaticText(self, -1, _(u"ALERTE : %d reponse(s) alimentaires manquante(s). Verifiez avant validation.") %
                sum(entree[3] for entree in self.sans_reponse)), 0,
                wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        self.grid = gridlib.Grid(self, -1)
        self.grid.CreateGrid(len(self.lignes), 3 + len(ENTREES) + len(SORTIES))
        for index, label in enumerate([u"Date", u"Site", u"Service"] +
                                       [name for _, name in ENTREES] +
                                       [name for _, name in SORTIES]):
            self.grid.SetColLabelValue(index, label)
            self.grid.SetColSize(index, 112 if index < 3 else 105)
        for i, line in enumerate(self.lignes):
            for j, valeur in enumerate((line["date"].isoformat(), line["site"], line["service"])):
                self.grid.SetCellValue(i, j, str(valeur))
                self.grid.SetReadOnly(i, j, True)
            for j, (champ, _label) in enumerate(ENTREES, 3):
                self.grid.SetCellValue(i, j, str(line["valeurs"][champ]))
                self.grid.SetCellAlignment(i, j, wx.ALIGN_RIGHT, wx.ALIGN_CENTER)
            for j, (champ, _label) in enumerate(SORTIES, 3 + len(ENTREES)):
                self.grid.SetReadOnly(i, j, True)
                self.grid.SetCellAlignment(i, j, wx.ALIGN_RIGHT, wx.ALIGN_CENTER)
            self.Recalculer(i)
        self.grid.Bind(gridlib.EVT_GRID_CELL_CHANGED, self.OnValeurModifiee)
        sizer.Add(self.grid, 1, wx.EXPAND | wx.ALL, 8)
        boutons = wx.BoxSizer(wx.HORIZONTAL)
        bouton_maj = wx.Button(self, -1, _(u"Recalculer les totaux"))
        self.Bind(wx.EVT_BUTTON, self.OnRecalculer, bouton_maj)
        boutons.Add(bouton_maj, 0, wx.RIGHT, 8)
        bouton_valider = wx.Button(self, wx.ID_OK, _(u"Valider les effectifs"))
        bouton_retour = wx.Button(self, wx.ID_CANCEL, _(u"Retourner a la commande"))
        boutons.Add(bouton_valider, 0, wx.RIGHT, 8)
        boutons.Add(bouton_retour, 0)
        self.Bind(wx.EVT_BUTTON, self.OnValider, bouton_valider)
        sizer.Add(boutons, 0, wx.ALIGN_RIGHT | wx.ALL, 8)
        self.SetSizer(sizer)
        self.SetSize((1120, 540))
        self.SetMinSize((800, 360))
        self.CenterOnScreen()

    def Recalculer(self, index):
        ligne = self.lignes[index]
        for j, (champ, _label) in enumerate(SORTIES, 3 + len(ENTREES)):
            self.grid.SetCellValue(index, j, str(ligne["totaux"][champ]))

    def LireValeurs(self):
        for row, line in enumerate(self.lignes):
            nouvelles = {}
            for index, (champ, _label) in enumerate(ENTREES, 3):
                nouvelles[champ] = UTILS_Repas_totaux.EntierNaturel(
                    self.grid.GetCellValue(row, index), champ)
            line["totaux"] = UTILS_Repas_totaux.TotauxRepas(**nouvelles)
            line["valeurs"] = nouvelles
            self.Recalculer(row)

    def OnValeurModifiee(self, event):
        try:
            self.LireValeurs()
        except ValueError:
            # La valeur est signalee au moment de la validation.
            pass
        event.Skip()

    def OnRecalculer(self, event):
        try:
            self.LireValeurs()
        except ValueError as exc:
            wx.MessageBox(str(exc), _(u"Quantites invalides"),
                          wx.OK | wx.ICON_WARNING, self)

    def OnValider(self, event):
        try:
            self.LireValeurs()
        except ValueError as exc:
            wx.MessageBox(str(exc), _(u"Quantites invalides"),
                          wx.OK | wx.ICON_WARNING, self)
            return
        erreurs_regimes = UTILS_Repas_validation.ErreursRegimes(self.lignes)
        if erreurs_regimes:
            # Une repartition alimentaire incomplete n'est jamais validee.
            wx.MessageBox(_(u"Repartition alimentaire incoherente :\n%s\n\n"
                            u"Corrigez les colonnes de regime de la commande.") % u"\n".join(erreurs_regimes),
                          _(u"Repartition alimentaire"), wx.OK | wx.ICON_WARNING, self)
            return
        if self.sans_reponse:
            total = sum(ligne[3] for ligne in self.sans_reponse)
            texte = _(u"%d repas correspondent a des enfants sans reponse alimentaire. "
                      u"Le comptage sans porc peut etre incomplet. "
                      u"Avez-vous verifie ou corrige manuellement les quantites ?") % total
            confirmation = wx.MessageBox(texte, _(u"Preferences alimentaires non renseignees"),
                                          wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self)
            if confirmation != wx.YES:
                return
        self.EndModal(wx.ID_OK)

    def Appliquer(self):
        UTILS_Repas_validation.AppliquerControle(self.lignes)
