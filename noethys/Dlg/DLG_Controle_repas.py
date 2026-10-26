# -*- coding: utf-8 -*-
"""Confirmation explicite des effectifs avant tout PDF / email de repas."""

import wx
import wx.grid as gridlib
from Utils.UTILS_Traduction import _
from Utils import UTILS_Repas_validation, UTILS_Repas_totaux, UTILS_Repas_regimes

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
# Repartition exclusive : decompose le total, ne s'y ajoute jamais.
REGIMES = [
    ("standard", u"Standard"),
    ("sans_porc", u"Sans porc"),
    ("vegetarien", u"Végétarien"),
    ("non_renseignes", u"Non renseigné"),
]
COL_REGIMES = 3 + len(ENTREES) + len(SORTIES)
COL_ECART = COL_REGIMES + len(REGIMES)
SANS_OBJET = u"—"


class Dialog(wx.Dialog):
    def __init__(self, parent, donnees):
        wx.Dialog.__init__(self, parent, -1, _(u"Verification des effectifs et des repas"),
                           style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.lignes = UTILS_Repas_validation.ConstruireControle(donnees)
        self.avec_regimes = any(ligne["regimes"] for ligne in self.lignes)
        self.sans_reponse = [
            (ligne["date"], ligne["site"], ligne["service"], ligne.get("non_renseignes", 0))
            for ligne in self.lignes if ligne.get("non_renseignes", 0) > 0
        ]
        sizer = wx.BoxSizer(wx.VERTICAL)
        if self.avec_regimes:
            texte = _(u"Confirmez les quantites de chaque service. Standard + sans porc + vegetarien + "
                      u"non renseigne doit egaler le total des repas ; un effectif corrige n'est jamais "
                      u"reporte automatiquement sur les regimes.")
        else:
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
        alertes = sorted(set(a for ligne in self.lignes for a in ligne.get("alertes_regimes", [])))
        if alertes:
            sizer.Add(wx.StaticText(self, -1, _(u"ALERTES REGIMES : %s") % u" ; ".join(alertes)),
                      0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        self.grid = gridlib.Grid(self, -1)
        self.grid.CreateGrid(len(self.lignes), COL_ECART + 1)
        for index, label in enumerate([u"Date", u"Site", u"Service"] +
                                       [name for _, name in ENTREES] +
                                       [name for _, name in SORTIES] +
                                       [name for _, name in REGIMES] + [u"Ecart repartition"]):
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
            for j, (champ, _label) in enumerate(REGIMES, COL_REGIMES):
                self.grid.SetCellAlignment(i, j, wx.ALIGN_RIGHT, wx.ALIGN_CENTER)
                if line["regimes"]:
                    self.grid.SetCellValue(i, j, str(line["regimes"].get(champ, 0)))
                else:
                    self.grid.SetCellValue(i, j, SANS_OBJET)
                    self.grid.SetReadOnly(i, j, True)
            self.grid.SetReadOnly(i, COL_ECART, True)
            self.grid.SetCellAlignment(i, COL_ECART, wx.ALIGN_RIGHT, wx.ALIGN_CENTER)
            self.Recalculer(i)
        # Un seul « sans porc » visible : l'ancien sous-total ou la categorie exclusive.
        if self.avec_regimes:
            self.grid.HideCol(3 + [c for c, _l in ENTREES].index("sans_porc"))
        else:
            for j in range(COL_REGIMES, COL_ECART + 1):
                self.grid.HideCol(j)
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
        if ligne["regimes"]:
            # Ecart affiche, jamais corrige : repartis - total.
            ecart = sum(int(ligne["regimes"].get(c, 0)) for c in UTILS_Repas_regimes.CHAMPS) - ligne["totaux"]["total_repas"]
            self.grid.SetCellValue(index, COL_ECART, u"0" if ecart == 0 else u"%+d" % ecart)
        else:
            self.grid.SetCellValue(index, COL_ECART, SANS_OBJET)

    def LireValeurs(self):
        for row, line in enumerate(self.lignes):
            nouvelles = {}
            for index, (champ, _label) in enumerate(ENTREES, 3):
                nouvelles[champ] = UTILS_Repas_totaux.EntierNaturel(
                    self.grid.GetCellValue(row, index), champ)
            if line["regimes"]:
                line["regimes"] = dict(
                    (champ, UTILS_Repas_totaux.EntierNaturel(self.grid.GetCellValue(row, index), champ))
                    for index, (champ, _label) in enumerate(REGIMES, COL_REGIMES))
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
                            u"Corrigez explicitement les colonnes de regime.") % u"\n".join(erreurs_regimes),
                          _(u"Repartition alimentaire"), wx.OK | wx.ICON_WARNING, self)
            return
        acquittements = UTILS_Repas_validation.AcquittementsRegimes(self.lignes)
        if acquittements:
            texte = _(u"Points a verifier avant validation :\n%s\n\n"
                      u"Confirmez-vous ces quantites ?") % u"\n".join(acquittements)
            if wx.MessageBox(texte, _(u"Repartition alimentaire"),
                             wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self) != wx.YES:
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
