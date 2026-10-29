# -*- coding: utf-8 -*-
"""Noethys SL wx : situation de frequentation communale par journee-enfant.

Importation en lecture seule des presences, jamais des factures des familles.
"""
import json
import os
import sys
from datetime import date
from pathlib import Path

import wx
from Utils import UTILS_Attente
from Utils.UTILS_Frequentation_collectivites import (
    CONTROLES, ErreurFrequentation, calculer, exporter_csv, exporter_pdf, exporter_xlsx,
    modele, _fr_centimes, _fr_jours,
)
from Utils.UTILS_Frequentation_collectivites_db import lister_unites, importer_journees


def champ(parent, grid, nom, val=""):
    grid.Add(wx.StaticText(parent, label=nom), 0, wx.ALIGN_CENTER_VERTICAL)
    ctrl = wx.TextCtrl(parent, value=str(val))
    grid.Add(ctrl, 1, wx.EXPAND)
    return ctrl


def grille(parent):
    grille = wx.FlexGridSizer(rows=0, cols=2, vgap=8, hgap=12)
    grille.AddGrowableCol(1, 1)
    return grille


class SaisieConvention(wx.Dialog):
    def __init__(self, parent, data=None):
        wx.Dialog.__init__(self, parent, title="Convention de financement ALSH",
                           style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        d = data or {}
        s = wx.BoxSizer(wx.VERTICAL)
        g = grille(self)
        self.id = champ(self, g, "Reference convention", d.get("id", ""))
        self.accueil = champ(self, g, "Accueil (ALSH classique / ALSH Ados)", d.get("accueil", ""))
        self.debut = champ(self, g, "Debut (AAAA-MM-JJ)", d.get("debut", ""))
        self.fin = champ(self, g, "Fin (AAAA-MM-JJ)", d.get("fin", ""))
        self.tarif = champ(self, g, "Participation / journee-enfant (EUR)", d.get("tarif_jour", ""))
        self.justif = champ(self, g, "Reference de la convention", d.get("justificatif_tarif", ""))
        s.Add(g, 1, wx.EXPAND | wx.ALL, 12)
        self.confirme = wx.CheckBox(self, label="Convention applicable et montant verifies sur le document signe")
        self.confirme.SetValue(d.get("tarif_confirme", False))
        s.Add(self.confirme, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        self.demi = wx.CheckBox(self, label="Equivalence demi-journee validee explicitement (0,5 journee)")
        self.demi.SetValue(d.get("demi_journee_autorisee", False))
        s.Add(self.demi, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        s.Add(self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL), 0, wx.ALL | wx.EXPAND, 10)
        self.SetSizerAndFit(s)
        self.SetMinSize((710, 420))
        self.CenterOnParent()

    def valeurs(self):
        return {"id": self.id.GetValue().strip(), "accueil": self.accueil.GetValue().strip(),
                "debut": self.debut.GetValue().strip(), "fin": self.fin.GetValue().strip(),
                "tarif_jour": self.tarif.GetValue().strip(),
                "justificatif_tarif": self.justif.GetValue().strip(),
                "tarif_confirme": self.confirme.GetValue(),
                "demi_journee_autorisee": self.demi.GetValue()}


class SaisieJours(wx.Dialog):
    def __init__(self, parent, conventions, ident, data=None):
        wx.Dialog.__init__(self, parent, title="Frequentation : journees-enfants",
                           style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        d = data or {}
        self.conventions = list(conventions)
        s = wx.BoxSizer(wx.VERTICAL)
        g = grille(self)
        self.id = champ(self, g, "Reference du releve", d.get("id", ident))
        g.Add(wx.StaticText(self, label="Accueil / convention"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.convention = wx.Choice(self, choices=self.conventions)
        self.convention.SetSelection(self.conventions.index(d.get("convention"))
                                     if d.get("convention") in self.conventions else 0)
        g.Add(self.convention, 1, wx.EXPAND)
        g.Add(wx.StaticText(self, label="Mois civil"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.mois = wx.SpinCtrl(self, min=1, max=12, initial=int(d.get("mois", date.today().month)))
        g.Add(self.mois, 1, wx.EXPAND)
        g.Add(wx.StaticText(self, label="Nature"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.nature = wx.Choice(self, choices=["Frequentation realisee", "Frequentation prevue"])
        self.nature.SetSelection(1 if d.get("nature") == "prevision" else 0)
        g.Add(self.nature, 1, wx.EXPAND)
        self.nombre = champ(self, g, "Nombre de journees-enfants", d.get("nombre", ""))
        self.justif = champ(self, g, "Etat de frequentation / justificatif", d.get("justificatif", ""))
        s.Add(g, 1, wx.EXPAND | wx.ALL, 12)
        s.Add(wx.StaticText(self, label="Une ligne par accueil, mois et nature. Ne pas ajouter repas, garderie ou paiements des familles."),
              0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        s.Add(self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 10)
        self.SetSizerAndFit(s)
        self.SetMinSize((660, 350))
        self.CenterOnParent()

    def valeurs(self):
        return {"id": self.id.GetValue().strip(),
                "convention": self.conventions[self.convention.GetSelection()],
                "mois": self.mois.GetValue(),
                "nature": "prevision" if self.nature.GetSelection() == 1 else "realise",
                "nombre": self.nombre.GetValue().strip(),
                "justificatif": self.justif.GetValue().strip()}


class SaisieAcompte(wx.Dialog):
    def __init__(self, parent, conventions, ident, annee, data=None):
        wx.Dialog.__init__(self, parent, title="Acompte verse par la commune",
                           style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        d = data or {}
        self.conventions = list(conventions)
        self.annee = annee
        s = wx.BoxSizer(wx.VERTICAL)
        g = grille(self)
        self.id = champ(self, g, "Reference du versement", d.get("id", ident))
        g.Add(wx.StaticText(self, label="Accueil concerne"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.convention = wx.Choice(self, choices=self.conventions)
        self.convention.SetSelection(self.conventions.index(d.get("convention"))
                                     if d.get("convention") in self.conventions else 0)
        g.Add(self.convention, 1, wx.EXPAND)
        self.jour = champ(self, g, "Date de perception (AAAA-MM-JJ)", d.get("date", date.today().isoformat()))
        self.montant = champ(self, g, "Montant recu (EUR)", d.get("montant", ""))
        self.justif = champ(self, g, "Reference bancaire / comptable", d.get("justificatif", ""))
        s.Add(g, 1, wx.EXPAND | wx.ALL, 12)
        s.Add(wx.StaticText(self, label="Uniquement les versements de la mairie imputes a l'exercice %d. Pas de reglements familiaux." % annee),
              0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        s.Add(self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL), 0, wx.ALL | wx.EXPAND, 10)
        self.SetSizerAndFit(s)
        self.SetMinSize((610, 340))
        self.CenterOnParent()

    def valeurs(self):
        return {"id": self.id.GetValue().strip(),
                "convention": self.conventions[self.convention.GetSelection()],
                "date": self.jour.GetValue().strip(), "montant": self.montant.GetValue().strip(),
                "exercice": self.annee, "justificatif": self.justif.GetValue().strip()}



class ChoixUnites(wx.Dialog):
    """Qualification volontaire des unites: aucun libelle n'est devine."""

    def __init__(self, parent, unites, conventions):
        wx.Dialog.__init__(self, parent, title="Selection des unites ALSH",
                           style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.unites = unites
        self.conventions = conventions
        self.listes = {}
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(self, label=(
            "Selectionner UNIQUEMENT les unites representant une journee-enfant entiere.\n"
            "Ne pas cocher repas, garderie, activites supplementaires ou une unite\n"
            "qui doublerait une autre unite pour le meme enfant et le meme jour.\n"
            "Les unites non cochees ne seront pas comptees.")),
            0, wx.ALL, 12)
        choix = ["%s / %s  (%d occurrences, #%d:%d)" %
                 (x["activite"], x["unite"], x["nombre"],
                  x["IDactivite"], x["IDunite"]) for x in unites]
        for conv in conventions:
            if conv["accueil"] not in ("ALSH classique", "ALSH Ados"):
                continue
            label = "%s - %s" % (conv["accueil"], conv["id"])
            sizer.Add(wx.StaticText(self, label=label), 0,
                      wx.LEFT | wx.TOP, 12)
            ctrl = wx.CheckListBox(self, choices=choix)
            ctrl.SetMinSize((780, 130))
            sizer.Add(ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
            self.listes[conv["id"]] = ctrl
        self.exhaustif = wx.CheckBox(self, label=(
            "Je confirme que toutes les unites de journee ALSH/Ados concernes sont selectionnees"))
        sizer.Add(self.exhaustif, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        sizer.Add(wx.StaticText(self, label=(
            "Adresses actuelles uniquement : les changements de domicile en 2026\n"
            "et les presences reelles devront etre verifies avant l'etat definitif.")),
            0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        sizer.Add(self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL),
                  0, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(sizer)
        self.SetMinSize((830, 530))
        self.SetSize((900, 640))
        self.CenterOnParent()

    def mapping(self):
        selection = {}
        for convention, ctrl in self.listes.items():
            for i, unite in enumerate(self.unites):
                if ctrl.IsChecked(i):
                    cle = "%d:%d" % (unite["IDactivite"], unite["IDunite"])
                    if cle in selection:
                        raise ErreurFrequentation(
                            "La meme unite est selectionnee pour deux accueils : %s" % cle)
                    selection[cle] = {"convention": convention, "poids": "1"}
        if not selection:
            raise ErreurFrequentation("Selectionnez au moins une unite de journee")
        return selection


class Dialog(wx.Dialog):
    """Ecran unique wx, import SQL en lecture seule et stockage JSON prive."""
    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, title="Noethys-SL - Frequentation et participations communales",
                           style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        today = date.today()
        self.fichier = None
        self.dossier = modele("Bais", today.year, today.isoformat())
        self.root = wx.BoxSizer(wx.VERTICAL)
        bande = wx.BoxSizer(wx.HORIZONTAL)
        self.commune = wx.ComboBox(self, value="Bais", choices=["Bais", "Moutiers", "La Guerche-de-Bretagne",
                           "Availles-sur-Seiche", "Drouges", "Moussé", "Rannée", "La Selle-Guerchaise", "Visseiche"],
                           style=wx.CB_DROPDOWN)
        self.annee = wx.SpinCtrl(self, min=2000, max=2100, initial=today.year)
        self.commune.Bind(wx.EVT_COMBOBOX, self.OnSelectionPerimetre)
        self.annee.Bind(wx.EVT_SPINCTRL, self.OnSelectionPerimetre)
        self.arrete = wx.TextCtrl(self, value=today.isoformat())
        for nom, ctrl, prop in (("Commune", self.commune, 2), ("Annee civile", self.annee, 0),
                                ("Arrete (AAAA-MM-JJ)", self.arrete, 1)):
            bande.Add(wx.StaticText(self, label=nom), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
            bande.Add(ctrl, prop, wx.RIGHT | wx.EXPAND, 14)
        self.root.Add(bande, 0, wx.ALL | wx.EXPAND, 12)
        org = wx.BoxSizer(wx.HORIZONTAL)
        org.Add(wx.StaticText(self, label="Organisme"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 7)
        self.emetteur = wx.TextCtrl(self, value="")
        org.Add(self.emetteur, 1, wx.EXPAND)
        self.root.Add(org, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        self.root.Add(wx.StaticText(self, label="Conventions et tarifs a la journee :"),
                      0, wx.LEFT | wx.BOTTOM, 12)
        conv = wx.BoxSizer(wx.HORIZONTAL)
        self.choix_conv = wx.Choice(self)
        conv.Add(self.choix_conv, 1, wx.RIGHT, 8)
        for titre, callback in (("Ajouter", self.OnAjouterConvention),
                                 ("Modifier", self.OnModifierConvention),
                                 ("Supprimer", self.OnSupprimerConvention)):
            b = wx.Button(self, label=titre)
            b.Bind(wx.EVT_BUTTON, callback)
            conv.Add(b, 0, wx.RIGHT, 6)
        self.root.Add(conv, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        barre_import = wx.BoxSizer(wx.HORIZONTAL)
        barre_import.Add(wx.StaticText(self, label="Frequentation en journees-enfants (par mois et accueil) :"),
                         0, wx.ALIGN_CENTER_VERTICAL)
        barre_import.AddStretchSpacer(1)
        importer = wx.Button(self, label="Charger les presences Noethys...")
        importer.Bind(wx.EVT_BUTTON, self.OnImporterNoethys)
        barre_import.Add(importer)
        self.root.Add(barre_import, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        self.liste_jours = self._liste([("Reference", 125), ("Mois", 70), ("Accueil", 145),
                                      ("Nature", 130), ("Jours-enfants", 125), ("Source", 285)])
        self.liste_jours.SetMinSize((-1, 145))
        self.liste_jours.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnModifierJours)
        self.root.Add(self.liste_jours, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 12)
        self._barre(("Ajouter un mois", self.OnAjouterJours), ("Modifier", self.OnModifierJours),
                    ("Supprimer", self.OnSupprimerJours))
        self.root.Add(wx.StaticText(self, label="Acomptes effectivement verses par la commune :"),
                      0, wx.LEFT | wx.BOTTOM, 12)
        self.liste_acomptes = self._liste([("Reference", 125), ("Date", 100), ("Accueil", 150),
                                          ("Montant EUR", 125), ("Justificatif", 380)])
        self.liste_acomptes.SetMinSize((-1, 100))
        self.liste_acomptes.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnModifierAcompte)
        self.root.Add(self.liste_acomptes, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 12)
        self._barre(("Ajouter un acompte", self.OnAjouterAcompte), ("Modifier", self.OnModifierAcompte),
                    ("Supprimer", self.OnSupprimerAcompte))
        self.verifs = {}
        cadres = wx.StaticBoxSizer(wx.StaticBox(self, label="Controles a valider sur pieces"), wx.HORIZONTAL)
        for cle, nom in (("frequentation", "Presences reelles"), ("prevision", "Reservations futures"),
                         ("domiciliation", "Communes de domicile"), ("acomptes", "Acomptes de la mairie")):
            cb = wx.CheckBox(self, label=nom)
            cb.Bind(wx.EVT_CHECKBOX, self.OnActualiser)
            self.verifs[cle] = cb
            cadres.Add(cb, 0, wx.ALL, 7)
        self.root.Add(cadres, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        self.resume = wx.TextCtrl(self, style=wx.TE_READONLY | wx.TE_MULTILINE)
        self.resume.SetMinSize((-1, 100))
        self.root.Add(self.resume, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        actions = wx.BoxSizer(wx.HORIZONTAL)
        for titre, callback in (("Nouveau", self.OnNouveau), ("Ouvrir", self.OnOuvrir),
                                 ("Enregistrer", self.OnEnregistrer), ("Actualiser", self.OnActualiser),
                                 ("Exporter PDF", self.OnPDF), ("Exporter CSV", self.OnCSV),
                                 ("Exporter Excel", self.OnExcel)):
            b = wx.Button(self, label=titre)
            b.Bind(wx.EVT_BUTTON, callback)
            actions.Add(b, 0, wx.RIGHT, 7)
        actions.AddStretchSpacer(1)
        actions.Add(wx.Button(self, id=wx.ID_CANCEL, label="Fermer"), 0)
        self.root.Add(actions, 0, wx.ALL | wx.EXPAND, 12)
        self.SetSizer(self.root)
        self.SetMinSize((1010, 780))
        self.SetSize((1140, 890))
        self.CenterOnParent()
        self.Rafraichir()

    def _liste(self, cols):
        l = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN)
        for i, (nom, largeur) in enumerate(cols):
            l.InsertColumn(i, nom, width=largeur)
        return l

    def _barre(self, *items):
        ligne = wx.BoxSizer(wx.HORIZONTAL)
        for titre, fn in items:
            b = wx.Button(self, label=titre)
            b.Bind(wx.EVT_BUTTON, fn)
            ligne.Add(b, 0, wx.RIGHT, 8)
        self.root.Add(ligne, 0, wx.ALL, 10)

    def _message(self, info, erreur=True):
        wx.MessageBox(str(info), "Situation de frequentation",
                      wx.OK | (wx.ICON_ERROR if erreur else wx.ICON_INFORMATION), self)

    def _sync(self):
        nom = self.commune.GetValue().strip()
        if (self.dossier.get("jours") or self.dossier.get("acomptes")) and nom.casefold() != self.dossier["commune"].casefold():
            raise ErreurFrequentation("Pour changer de commune avec des lignes saisies, creer un nouveau dossier.")
        if self.dossier.get("jours") and self.annee.GetValue() != self.dossier["annee"]:
            raise ErreurFrequentation("Pour changer d'annee, creer un nouveau dossier.")
        self.dossier["commune"] = nom
        self.dossier["annee"] = self.annee.GetValue()
        self.dossier["arrete"] = self.arrete.GetValue().strip()
        self.dossier["emetteur"] = self.emetteur.GetValue().strip()
        self.dossier["controles"] = {k: w.GetValue() for k, w in self.verifs.items()}
        origine = self.dossier.get("import_noethys")
        if isinstance(origine, dict):
            origine["domiciliation_historique_verifiee"] = bool(
                self.verifs["domiciliation"].GetValue())

    def _calculer(self):
        self._sync()
        return calculer(self.dossier)

    def Rafraichir(self):
        d = self.dossier
        self.commune.SetValue(d["commune"])
        self.annee.SetValue(d["annee"])
        self.arrete.SetValue(d["arrete"])
        self.emetteur.SetValue(d.get("emetteur", ""))
        self.choix_conv.Set(["%s  -  %s  (%s EUR/j)" % (c["id"], c["accueil"], c["tarif_jour"])
                             for c in d["conventions"]])
        if d["conventions"]:
            self.choix_conv.SetSelection(0)
        self.liste_jours.DeleteAllItems()
        for l in d["jours"]:
            self._ajouter_ligne(self.liste_jours, [l["id"], "%02d" % l["mois"], l["convention"],
                              "Realise" if l["nature"] == "realise" else "Prevision",
                              str(l["nombre"]), l.get("justificatif", "")])
        self.liste_acomptes.DeleteAllItems()
        for l in d["acomptes"]:
            self._ajouter_ligne(self.liste_acomptes, [l["id"], l["date"], l["convention"],
                              str(l["montant"]), l.get("justificatif", "")])
        for k, cb in self.verifs.items():
            cb.SetValue(d["controles"].get(k, False))
        self.OnActualiser(None)

    @staticmethod
    def _ajouter_ligne(liste, values):
        pos = liste.InsertItem(liste.GetItemCount(), str(values[0]))
        for i, val in enumerate(values[1:], 1):
            liste.SetItem(pos, i, str(val))

    def _id(self, prefix):
        vus = {l["id"] for l in self.dossier["jours"] + self.dossier["acomptes"]}
        n = 1
        while "%s-%03d" % (prefix, n) in vus:
            n += 1
        return "%s-%03d" % (prefix, n)

    def _ids_conventions(self):
        return [c["id"] for c in self.dossier["conventions"]]

    def _selection(self, liste):
        index = liste.GetFirstSelected()
        return index if index >= 0 else None

    def OnSelectionPerimetre(self, event):
        """Change de commune/annee sans reutiliser une convention d'une autre commune."""
        if self.dossier.get("jours") or self.dossier.get("acomptes"):
            self._message("Des donnees sont deja saisies. Enregistrer le dossier puis cliquer sur Nouveau pour changer de commune ou d'annee.")
            self.commune.SetValue(self.dossier["commune"])
            self.annee.SetValue(self.dossier["annee"])
            return
        try:
            self.dossier = modele(self.commune.GetValue().strip() or "Bais",
                                 self.annee.GetValue(),
                                 "%04d-%s" % (self.annee.GetValue(), self.arrete.GetValue()[5:]))
        except (ValueError, ErreurFrequentation) as e:
            self._message(e)
            return
        self.Rafraichir()

    def OnNouveau(self, event):
        self.fichier = None
        self.dossier = modele(self.commune.GetValue().strip() or "Bais",
                             self.annee.GetValue(), self.arrete.GetValue().strip())
        self.Rafraichir()

    def OnAjouterConvention(self, event):
        try:
            self._sync()
        except ErreurFrequentation as e:
            return self._message(e)
        dlg = SaisieConvention(self)
        if dlg.ShowModal() == wx.ID_OK:
            new = dlg.valeurs()
            if new["id"] in self._ids_conventions():
                self._message("Reference de convention deja utilisee")
            else:
                self.dossier["conventions"].append(new)
                self.Rafraichir()
        dlg.Destroy()

    def OnModifierConvention(self, event):
        index = self.choix_conv.GetSelection()
        if index < 0:
            return
        old = self.dossier["conventions"][index]
        dlg = SaisieConvention(self, old)
        if dlg.ShowModal() == wx.ID_OK:
            new = dlg.valeurs()
            if new["id"] != old["id"] and new["id"] in self._ids_conventions():
                self._message("Reference de convention deja utilisee")
            else:
                self.dossier["conventions"][index] = new
                for ligne in self.dossier["jours"] + self.dossier["acomptes"]:
                    if ligne["convention"] == old["id"]:
                        ligne["convention"] = new["id"]
                self.Rafraichir()
        dlg.Destroy()

    def OnSupprimerConvention(self, event):
        index = self.choix_conv.GetSelection()
        if index < 0:
            return
        old = self.dossier["conventions"][index]["id"]
        if any(l["convention"] == old for l in self.dossier["jours"] + self.dossier["acomptes"]):
            return self._message("La convention comporte des journees ou acomptes : les retirer d'abord.")
        self.dossier["conventions"].pop(index)
        self.Rafraichir()

    def OnImporterNoethys(self, event):
        """Lit les consommations du fichier ouvert sans modifier la base."""
        try:
            self._sync()
            if not self.dossier["conventions"]:
                return self._message("Aucune convention applicable pour cette annee")
            annee = self.dossier["annee"]
            unites = UTILS_Attente.LireSQL(lambda db: lister_unites(annee, db=db),
                                          self, "Recherche des données...")
            if not unites:
                return self._message("Aucune consommation presente ou reservee pour cet exercice")
        except (ErreurFrequentation, ValueError) as erreur:
            return self._message(erreur)
        choix = ChoixUnites(self, unites, self.dossier["conventions"])
        try:
            if choix.ShowModal() != wx.ID_OK:
                return
            mapping = choix.mapping()
            exhaustif = choix.exhaustif.GetValue()
        except ErreurFrequentation as erreur:
            return self._message(erreur)
        finally:
            choix.Destroy()
        if self.dossier["jours"]:
            message = ("Remplacer toutes les lignes mensuelles actuelles par "
                       "le nouveau calcul de frequentation Noethys ?\n"
                       "Les acomptes ne seront pas modifies.")
            if wx.MessageBox(message, "Remplacer la frequentation ?",
                             wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
                             self) != wx.YES:
                return
        try:
            annee, arrete, commune = (self.dossier[k] for k in ("annee", "arrete", "commune"))
            resultat = UTILS_Attente.LireSQL(lambda db: importer_journees(
                annee, arrete, commune, mapping, db=db), self, "Recherche des données...")
            # Aucun identifiant ou nom d'enfant n'entre dans le dossier sauvegarde.
            nouveau = list(resultat["jours"])
            self.dossier["jours"] = nouveau
            self.dossier["import_noethys"] = {
                "annee": self.dossier["annee"],
                "arrete": self.dossier["arrete"],
                "perimetre_unites_confirme": exhaustif,
                "domiciles_indetermines": resultat["exclusions"].get("domiciles_indetermines", 0),
                "domiciliation_historique_verifiee": False,
                "unites_selectionnees": len(mapping),
            }
            self.dossier["controles"]["frequentation"] = False
            self.dossier["controles"]["prevision"] = False
            self.dossier["controles"]["domiciliation"] = False
            self.Rafraichir()
            self._message("Import effectue : %d lignes mensuelles, %d unites.\n"
                          "%d domiciles non resolus (non comptabilises).\n"
                          "Verifier les adresses a la date de chaque accueil."
                          % (len(nouveau), len(mapping),
                             resultat["exclusions"].get("domiciles_indetermines", 0)),
                          erreur=False)
        except (ErreurFrequentation, ValueError) as erreur:
            self._message(erreur)

    def OnAjouterJours(self, event):
        if not self._ids_conventions():
            return self._message("Ajouter une convention d'abord.")
        dlg = SaisieJours(self, self._ids_conventions(), self._id("J"))
        if dlg.ShowModal() == wx.ID_OK:
            self.dossier["jours"].append(dlg.valeurs())
            self.dossier.pop("import_noethys", None)
            self.Rafraichir()
        dlg.Destroy()

    def OnModifierJours(self, event):
        pos = self._selection(self.liste_jours)
        if pos is None:
            return
        old = self.dossier["jours"][pos]
        dlg = SaisieJours(self, self._ids_conventions(), old["id"], old)
        if dlg.ShowModal() == wx.ID_OK:
            self.dossier["jours"][pos] = dlg.valeurs()
            self.dossier.pop("import_noethys", None)
            self.Rafraichir()
        dlg.Destroy()

    def OnSupprimerJours(self, event):
        self._supprimer(self.liste_jours, "jours")

    def OnAjouterAcompte(self, event):
        if not self._ids_conventions():
            return self._message("Ajouter une convention d'abord.")
        dlg = SaisieAcompte(self, self._ids_conventions(), self._id("A"), self.annee.GetValue())
        if dlg.ShowModal() == wx.ID_OK:
            self.dossier["acomptes"].append(dlg.valeurs())
            self.Rafraichir()
        dlg.Destroy()

    def OnModifierAcompte(self, event):
        pos = self._selection(self.liste_acomptes)
        if pos is None:
            return
        old = self.dossier["acomptes"][pos]
        dlg = SaisieAcompte(self, self._ids_conventions(), old["id"], self.annee.GetValue(), old)
        if dlg.ShowModal() == wx.ID_OK:
            self.dossier["acomptes"][pos] = dlg.valeurs()
            self.Rafraichir()
        dlg.Destroy()

    def OnSupprimerAcompte(self, event):
        self._supprimer(self.liste_acomptes, "acomptes")

    def _supprimer(self, liste, key):
        pos = self._selection(liste)
        if pos is not None and wx.MessageBox("Supprimer cette ligne ?", "Confirmation",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self) == wx.YES:
            if key == "jours":
                self.dossier.pop("import_noethys", None)
            self.dossier[key].pop(pos)
            self.Rafraichir()

    def OnActualiser(self, event):
        try:
            r = self._calculer()
            t = r["totaux"]
            lines = [r["statut"],
                     "Journées réalisées : %s  |  Prévisions : %s" % (
                         _fr_jours(t["journees_reelles"]), _fr_jours(t["journees_prevues"])),
                     "Participation réalisée : %s  |  Future : %s  |  Annuelle : %s" % (
                         _fr_centimes(t["participation_reelle"]), _fr_centimes(t["participation_prevue"]),
                         _fr_centimes(t["participation_estimee"])),
                     "Acomptes : %s  |  Solde indicatif : %s" % (
                         _fr_centimes(t["acomptes_recus"]), _fr_centimes(t["solde_indicatif"]))]
            lines.extend("A VERIFIER : %s" % s for s in r["alertes"])
            self.resume.SetValue("\n".join(lines))
        except (ErreurFrequentation, ValueError) as e:
            self.resume.SetValue("SITUATION A RECTIFIER : %s" % e)

    def OnOuvrir(self, event):
        with wx.FileDialog(self, "Ouvrir une situation", wildcard="JSON (*.json)|*.json",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as d:
            if d.ShowModal() != wx.ID_OK:
                return
            path = Path(d.GetPath())
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            calculer(data)
            self.dossier, self.fichier = data, path
            self.Rafraichir()
        except (OSError, ValueError, ErreurFrequentation) as e:
            self._message(e)

    def OnEnregistrer(self, event):
        try:
            self._calculer()
        except (ErreurFrequentation, ValueError) as e:
            return self._message(e)
        path = self.fichier
        if path is None:
            with wx.FileDialog(self, "Enregistrer la situation", wildcard="JSON (*.json)|*.json",
                               style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as d:
                if d.ShowModal() != wx.ID_OK:
                    return
                path = Path(d.GetPath())
        tempo = path.with_name(path.name + ".new")
        try:
            with tempo.open("x", encoding="utf-8") as f:
                json.dump(self.dossier, f, indent=2, ensure_ascii=False)
                f.write("\n")
            os.replace(str(tempo), str(path))
            self.fichier = path
            self._message("Dossier local enregistre : %s" % path, erreur=False)
        except OSError as e:
            self._message(e)

    def _exporter(self, ext, callback):
        try:
            result = self._calculer()
        except (ErreurFrequentation, ValueError) as e:
            return self._message(e)
        if result["totaux"]["solde_verifie"] is None:
            self._message("Le rapport reste PROVISOIRE tant que les controles sont incomplets.", erreur=False)
        with wx.FileDialog(self, "Exporter le rapport", wildcard="%s (*.%s)|*.%s" % (ext.upper(), ext, ext),
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as d:
            if d.ShowModal() != wx.ID_OK:
                return
            path = Path(d.GetPath())
        if path.exists():
            return self._message("Un rapport de ce nom existe deja : choisissez un autre nom pour conserver l'ancien.")
        try:
            callback(result, path)
            self._message("Rapport cree : %s" % path, erreur=False)
        except (OSError, ValueError) as e:
            self._message(e)

    def OnPDF(self, event):
        self._exporter("pdf", exporter_pdf)

    def OnCSV(self, event):
        self._exporter("csv", exporter_csv)

    def OnExcel(self, event):
        self._exporter("xlsx", lambda resultat, chemin: exporter_xlsx(resultat, chemin, self.dossier))


def main():
    app = wx.App(False)
    dlg = Dialog(None)
    dlg.ShowModal()
    dlg.Destroy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
