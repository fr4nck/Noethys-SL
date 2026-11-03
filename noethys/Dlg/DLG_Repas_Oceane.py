# -*- coding: utf-8 -*-
"""Dialogues locaux de préparation Océane et de suivi des restes.

Ne manipulent aucune fiche nominative, inscription, facture ou email.
"""
import wx
import wx.grid as gridlib

from Utils import UTILS_Repas_oceane as O
from Utils import UTILS_Repas_oceane_export as Export
from Utils import UTILS_Repas_oceane_menus as Menus
from Utils import UTILS_Repas_oceane_restes as Restes

NOMS = {
    "entree": u"Entrée",
    "plat": u"Plat principal",
    "garniture": u"Garniture",
    "laitage": u"Laitage / fromage",
    "dessert": u"Dessert",
    "sans_porc": u"Dont sans porc",
    "sans_viande": u"Dont sans viande (poisson admis)",
    "vegetarien": u"Dont végétarien",
    "sans_allergene": u"Dont sans allergène",
}


def _nombre(valeur, etiquette, facultatif=False):
    texte = str(valeur).strip()
    if facultatif and not texte:
        return 0
    if not texte or not texte.isdigit():
        raise ValueError(u"Renseignez %s avec un entier positif ou nul" % etiquette)
    n = int(texte)
    if n > 10000:
        raise ValueError(u"Quantité excessive : %s" % etiquette)
    return n


class DialogExport(wx.Dialog):
    """Table d'édition par site/date/composante, révision explicite avant export."""

    def __init__(self, parent, lignes, menus=None):
        wx.Dialog.__init__(self, parent, -1,
                           title=u"Préparation du bordereau Océane",
                           style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.lignes = Export.AffecterBlocs(lignes)
        self.menus = menus or {}
        self.resultat = None
        self.lignes_grille = []
        panneau = wx.Panel(self)
        base = wx.BoxSizer(wx.VERTICAL)
        description = wx.StaticText(
            panneau, -1,
            u"Océane : M = moins de 6 ans ; P = 6 ans et plus, PERSONNEL INCLUS ; "
            u"A = toujours vide.\n"
            u"Contrôlez les 5 composantes. Saisissez explicitement les 4 variantes "
            u"alimentaires, M et P (0 si aucune).")
        base.Add(description, 0, wx.ALL | wx.EXPAND, 10)

        self.grille = gridlib.Grid(panneau, -1)
        self.grille.CreateGrid(len(self.lignes) * (len(O.COMPOSANTES)
                                                  + len(O.VARIANTES)), 7)
        for i, (titre, largeur) in enumerate((
                (u"Date / site", 174), (u"Composante", 193),
                (u"Menu Océane / choix précis", 327),
                (u"M", 60), (u"P", 60),
                (u"g par M", 72), (u"g par P", 72))):
            self.grille.SetColLabelValue(i, titre)
            self.grille.SetColSize(i, largeur)
        self.grille.SetRowLabelSize(42)
        self.grille.SetMinSize((1010, 365))
        ligne_grille = 0
        for position, item in enumerate(self.lignes):
            repart = O.RepartitionFournisseur(item["totaux"])
            menu = self.menus.get(O._mercredi(item["date"])) or {}
            for cle in O.COMPOSANTES + O.VARIANTES:
                self.lignes_grille.append((position, cle))
                self.grille.SetCellValue(
                    ligne_grille, 0, u"%s / %s" % (
                        O._mercredi(item["date"]).strftime("%d/%m/%Y"),
                        item["site"]))
                self.grille.SetCellValue(ligne_grille, 1, NOMS[cle])
                nom = " / ".join(menu.get(cle) or []) if cle in O.COMPOSANTES else ""
                self.grille.SetCellValue(ligne_grille, 2, nom)
                if cle in O.COMPOSANTES:
                    self.grille.SetCellValue(ligne_grille, 3, str(repart["M"]))
                    self.grille.SetCellValue(ligne_grille, 4, str(repart["P"]))
                for col in (0, 1):
                    self.grille.SetReadOnly(ligne_grille, col, True)
                if cle in O.VARIANTES:
                    for col in (2, 5, 6):
                        self.grille.SetReadOnly(ligne_grille, col, True)
                ligne_grille += 1
        base.Add(self.grille, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)

        resume = u"\n\n".join(
            u"%s / %s — %s\n%s" % (
                O._mercredi(e["date"]).strftime("%d/%m/%Y"), e["site"],
                (self.menus.get(O._mercredi(e["date"])) or {}).get(
                    "source", u"Menu non fourni"),
                Menus.PresentationMenu(self.menus.get(O._mercredi(e["date"]))))
            for e in self.lignes)
        self.apercu = wx.TextCtrl(
            panneau, -1, resume, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.apercu.SetMinSize((-1, 95))
        base.Add(self.apercu, 0, wx.ALL | wx.EXPAND, 10)

        self.allergenes = wx.CheckBox(
            panneau, -1,
            u"Dossiers « sans allergène » acceptés par la diététicienne d'Océane")
        base.Add(self.allergenes, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.revue = wx.CheckBox(
            panneau, -1,
            u"J'ai vérifié les quantités, les variantes et les portions du personnel.")
        base.Add(self.revue, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        boutons = wx.StdDialogButtonSizer()
        btn_ok = wx.Button(panneau, wx.ID_OK, u"Valider pour l'export Excel")
        btn_annuler = wx.Button(panneau, wx.ID_CANCEL)
        boutons.AddButton(btn_ok)
        boutons.AddButton(btn_annuler)
        boutons.Realize()
        base.Add(boutons, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        panneau.SetSizer(base)
        cadrage = wx.BoxSizer(wx.VERTICAL)
        cadrage.Add(panneau, 1, wx.EXPAND)
        self.SetSizer(cadrage)
        self.SetSize((1200, 710))
        self.SetMinSize((1060, 550))
        self.CentreOnParent()
        self.Bind(wx.EVT_BUTTON, self.OnValider, btn_ok)

    def LireLignes(self):
        resultat = []
        for ligne in self.lignes:
            copie = dict(ligne)
            copie["composantes"] = {}
            copie["variantes"] = {}
            copie["grammages"] = {}
            copie["intitules"] = {}
            copie["allergenes_valides"] = self.allergenes.GetValue()
            resultat.append(copie)
        for index, (position, cle) in enumerate(self.lignes_grille):
            objet = resultat[position]
            M = _nombre(self.grille.GetCellValue(index, 3),
                        u"M pour %s" % NOMS[cle])
            P = _nombre(self.grille.GetCellValue(index, 4),
                        u"P pour %s" % NOMS[cle])
            if cle in O.COMPOSANTES:
                objet["composantes"][cle] = {"M": M, "P": P}
                objet["intitules"][cle] = self.grille.GetCellValue(index, 2).strip()
                objet["grammages"][cle] = {
                    "M": _nombre(self.grille.GetCellValue(index, 5),
                                 u"grammage M", facultatif=True),
                    "P": _nombre(self.grille.GetCellValue(index, 6),
                                 u"grammage P", facultatif=True),
                }
            else:
                objet["variantes"][cle] = {"M": M, "P": P}
        for item in resultat:
            O.PreparerMercredi(
                item, item["bloc"], item["composantes"],
                item["variantes"], item["allergenes_valides"])
        return resultat

    def OnValider(self, event):
        if not self.revue.GetValue():
            wx.MessageBox(
                u"Confirmez la vérification des quantités et des régimes.",
                u"Validation Océane", wx.OK | wx.ICON_WARNING, self)
            return
        try:
            self.resultat = self.LireLignes()
        except ValueError as exc:
            wx.MessageBox(str(exc), u"Quantités Océane",
                          wx.OK | wx.ICON_WARNING, self)
            return
        self.EndModal(wx.ID_OK)


class DialogRestes(wx.Dialog):
    """Saisie des quantités effectivement livrées/servies et restes pesés."""

    def __init__(self, parent, annexe):
        wx.Dialog.__init__(self, parent, -1, title=u"Suivi des restes Océane",
                           style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.annexe = list(annexe)
        self.resultat = None
        self.grille = gridlib.Grid(self)
        self.grille.CreateGrid(len(self.annexe), 9)
        titres = (u"Date / site", u"Composante", u"Menu", u"M/P",
                  u"Commandées", u"Livrées", u"Servies",
                  u"Restes assiette g", u"g / portion")
        tailles = (160, 150, 260, 50, 90, 78, 78, 130, 115)
        for col, (nom, largeur) in enumerate(zip(titres, tailles)):
            self.grille.SetColLabelValue(col, nom)
            self.grille.SetColSize(col, largeur)
        self.grille.SetRowLabelSize(43)
        for i, item in enumerate(self.annexe):
            values = (
                u"%s / %s" % (item["date"], item["site"]),
                NOMS[item["composante"]], item["plat"],
                item["tranche"], str(item["commandes"]),
                "", "", "",
                str(item["grammes_par_portion"]) if item["grammes_par_portion"] else "",
            )
            for j, val in enumerate(values):
                self.grille.SetCellValue(i, j, val)
                if j < 5:
                    self.grille.SetReadOnly(i, j, True)
        info = wx.StaticText(self, -1,
            u"Saisissez les valeurs constatées (0 est autorisé). "
            u"Les lignes entièrement vides sont ignorées.\n"
            u"Les restes d'assiette sont pesés en grammes ; "
            u"les portions non servies sont déduites de livré - servi.")
        buttons = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(info, 0, wx.ALL | wx.EXPAND, 10)
        sizer.Add(self.grille, 1, wx.ALL | wx.EXPAND, 10)
        sizer.Add(buttons, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        self.SetSizer(sizer)
        self.SetMinSize((1150, 550))
        self.SetSize((1240, 700))
        self.CentreOnParent()
        self.Bind(wx.EVT_BUTTON, self.OnValider, id=wx.ID_OK)

    def LireObservations(self):
        resultat = []
        for index, e in enumerate(self.annexe):
            libres = [self.grille.GetCellValue(index, col).strip()
                      for col in (5, 6, 7)]
            if all(not texte for texte in libres):
                continue
            if any(not texte for texte in libres):
                raise ValueError(
                    u"Ligne %d : livrées, servies et restes pesés "
                    u"doivent tous être renseignés (0 possible)" % (index + 1))
            observation = dict(
                date=e["date"], site=e["site"],
                composante=e["composante"], plat=e["plat"],
                tranche=e["tranche"], commandes=e["commandes"],
                livrees=_nombre(libres[0], "livrées"),
                servies=_nombre(libres[1], "servies"),
                restes_assiettes_g=libres[2],
                grammes_par_portion=self.grille.GetCellValue(index, 8),
            )
            resultat.append(Restes.ValiderObservation(observation))
        if not resultat:
            raise ValueError("Saisissez au moins une observation complète")
        return resultat

    def OnValider(self, event):
        try:
            self.resultat = self.LireObservations()
        except ValueError as exc:
            wx.MessageBox(str(exc), u"Restes Océane",
                          wx.OK | wx.ICON_WARNING, self)
            return
        self.EndModal(wx.ID_OK)
