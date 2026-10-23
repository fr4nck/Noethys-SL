# -*- coding: utf-8 -*-
"""Déclarations AFAS (V2) -- module autonome du menu Consommations.

Parcours : preset → activité → mode → sites → options → année → phase →
calcul → résultats et anomalies → export. Toute la logique métier est dans
les modules Utils/UTILS_AFAS2_* (testables sans fenêtre) ; ce dialogue ne
fait que la saisie et l'affichage. Indépendant de l'état global.
"""
import datetime
import os

import wx

from Utils import UTILS_AFAS2_Calcul as Calcul
from Utils import UTILS_AFAS2_Calendrier as Calendrier
from Utils import UTILS_AFAS2_Conventions as Conventions
from Utils import UTILS_AFAS2_Declaration as Declaration
from Utils import UTILS_AFAS2_Donnees as Donnees
from Utils import UTILS_AFAS2_Presets as Presets
from Utils import UTILS_AFAS2_Referentiel as Referentiel

MODES = ((Conventions.PERISCOLAIRE, "Périscolaire"), (Conventions.EXTRASCOLAIRE, "Extrascolaire"))
EQUIPEMENTS = tuple((code, valeur["libelle"]) for code, valeur in sorted(Conventions.EQUIPEMENTS.items()))
LIBELLES_CATEGORIES = dict(Calcul.CATEGORIES)


class Dialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Déclarations AFAS — ALSH", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.IDprofil = None
        self.preset_courant = None
        self.unites_classees = {}
        self.rapport = None
        self.referentiel = Referentiel.ReferentielVide()
        self.erreur_referentiel = None

        # A. Preset
        self.ctrl_preset = wx.Choice(self)
        boutons_preset = []
        for libelle, methode in (("Nouveau", self.OnNouveau), ("Enregistrer", self.OnEnregistrer), ("Dupliquer", self.OnDupliquer),
                                 ("Renommer", self.OnRenommer), ("Supprimer", self.OnSupprimer), ("Recharger", self.OnRecharger)):
            bouton = wx.Button(self, label=libelle)
            bouton.Bind(wx.EVT_BUTTON, methode)
            boutons_preset.append(bouton)
        self.ctrl_preset.Bind(wx.EVT_CHOICE, self.OnChoixPreset)
        self.ctrl_nom = wx.TextCtrl(self)

        # B-D. Activité, mode, équipement, sites
        self.ctrl_activite = wx.Choice(self, choices=list(Referentiel.ACTIVITES))
        self.ctrl_activite.SetSelection(0)
        self.ctrl_mode = wx.RadioBox(self, choices=[libelle for code, libelle in MODES], majorDimension=2)
        self.ctrl_equipement = wx.Choice(self, choices=[libelle for code, libelle in EQUIPEMENTS])
        self.ctrl_equipement.SetSelection(0)
        self.ctrl_sites = wx.CheckListBox(self, choices=[])
        self.ctrl_sites.SetMinSize((-1, 110))
        self.ctrl_mode.Bind(wx.EVT_RADIOBOX, self.OnContexte)
        self.ctrl_equipement.Bind(wx.EVT_CHOICE, self.OnContexte)
        self.ctrl_activite.Bind(wx.EVT_CHOICE, self.OnContexte)

        # G. Options
        self.bouton_unites = wx.Button(self, label="Classer les unités…")
        self.bouton_unites.Bind(wx.EVT_BUTTON, self.OnUnites)
        self.label_unites = wx.StaticText(self, label="")
        self.ctrl_realise = wx.CheckListBox(self, choices=[libelle for code, libelle in Calendrier.STATUTS])
        self.ctrl_facture = wx.CheckListBox(self, choices=[libelle for code, libelle in Calendrier.STATUTS])
        self.ctrl_samedis = wx.CheckBox(self, label="Samedis avec école (sinon : samedis sans école, extrascolaires)")
        self.ctrl_repas = wx.CheckBox(self, label="Inclure le temps de repas méridien (conventions périscolaires, art. 1.5)")
        self.ctrl_garderie = wx.CheckBox(self, label="Ajouter les garderies aux heures CAF (choix explicite)")

        # E-F. Exécution
        self.ctrl_annee = wx.SpinCtrl(self, min=2000, max=2100, initial=datetime.date.today().year)
        self.ctrl_phase = wx.Choice(self, choices=[libelle for code, libelle in Declaration.PHASES])
        self.ctrl_phase.SetSelection(3)
        self.ctrl_methode = wx.Choice(self, choices=["Même période de N-1 ajustée aux jours d'ouverture", "Prévision saisie manuellement"])
        self.ctrl_methode.SetSelection(0)
        self.manuels = {cle: wx.TextCtrl(self, size=(80, -1)) for cle in Declaration.INDICATEURS_PREVISION_MANUELLE}

        # H. Résultats
        self.label_statut = wx.StaticText(self, label="Aucun calcul.")
        self.ctrl_resultats = wx.ListCtrl(self, style=wx.LC_REPORT)
        for indice, (titre, largeur) in enumerate((("Indicateur", 330), ("Réalisé", 110), ("Prévision", 110), ("Total", 110))):
            self.ctrl_resultats.InsertColumn(indice, titre, width=largeur)
        self.ctrl_resultats.SetMinSize((-1, 230))
        self.ctrl_anomalies = wx.ListCtrl(self, style=wx.LC_REPORT)
        for indice, (titre, largeur) in enumerate((("Date", 85), ("Individu", 150), ("IDconso", 70), ("Site", 130), ("Unité", 120),
                                                   ("Nature", 330), ("Conséquence", 300), ("Bloquante", 70))):
            self.ctrl_anomalies.InsertColumn(indice, titre, width=largeur)
        self.ctrl_anomalies.SetMinSize((-1, 150))

        actions = []
        for libelle, methode in (("Référentiel…", self.OnReferentiel), ("Calculer", self.OnCalculer),
                                 ("Exporter la déclaration…", self.OnExporterDeclaration), ("Exporter le contrôle…", self.OnExporterControle),
                                 ("Historique…", self.OnHistorique)):
            bouton = wx.Button(self, label=libelle)
            bouton.Bind(wx.EVT_BUTTON, methode)
            actions.append(bouton)
        fermer = wx.Button(self, wx.ID_CANCEL, "Fermer")

        # Mise en page
        sizer = wx.BoxSizer(wx.VERTICAL)
        ligne = wx.BoxSizer(wx.HORIZONTAL)
        ligne.Add(wx.StaticText(self, label="Preset"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        ligne.Add(self.ctrl_preset, 1, wx.RIGHT, 6)
        for bouton in boutons_preset:
            ligne.Add(bouton, 0, wx.RIGHT, 4)
        sizer.Add(ligne, 0, wx.EXPAND | wx.ALL, 8)
        grille = wx.FlexGridSizer(cols=4, vgap=6, hgap=8)
        for libelle, ctrl in (("Nom du preset", self.ctrl_nom), ("Activité", self.ctrl_activite), ("Mode d'accueil", self.ctrl_mode),
                              ("Équipement", self.ctrl_equipement), ("Sites et groupes", self.ctrl_sites)):
            grille.Add(wx.StaticText(self, label=libelle), 0, wx.ALIGN_TOP)
            grille.Add(ctrl, 1, wx.EXPAND)
        grille.Add(wx.StaticText(self, label="Unités"), 0, wx.ALIGN_TOP)
        grille.Add(self.bouton_unites, 0)
        for libelle, ctrl in (("Statuts — heures réalisées", self.ctrl_realise), ("Statuts — heures facturées CAF", self.ctrl_facture)):
            grille.Add(wx.StaticText(self, label=libelle), 0, wx.ALIGN_TOP)
            grille.Add(ctrl, 1, wx.EXPAND)
        grille.Add((1, 1))
        grille.Add(self.label_unites)
        grille.AddGrowableCol(1)
        grille.AddGrowableCol(3)
        sizer.Add(grille, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        for case in (self.ctrl_samedis, self.ctrl_repas, self.ctrl_garderie):
            sizer.Add(case, 0, wx.LEFT | wx.TOP, 8)
        ligne = wx.BoxSizer(wx.HORIZONTAL)
        for libelle, ctrl in (("Année", self.ctrl_annee), ("Phase", self.ctrl_phase), ("Prévision", self.ctrl_methode)):
            ligne.Add(wx.StaticText(self, label=libelle), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
            ligne.Add(ctrl, 0, wx.RIGHT, 12)
        sizer.Add(ligne, 0, wx.ALL, 8)
        ligne = wx.BoxSizer(wx.HORIZONTAL)
        for cle, ctrl in self.manuels.items():
            ligne.Add(wx.StaticText(self, label=dict(Calcul.INDICATEURS)[cle] + " (h)"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
            ligne.Add(ctrl, 0, wx.RIGHT, 10)
        sizer.Add(ligne, 0, wx.LEFT | wx.RIGHT, 8)
        sizer.Add(self.label_statut, 0, wx.ALL, 8)
        sizer.Add(self.ctrl_resultats, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        sizer.Add(wx.StaticText(self, label="Anomalies (à corriger dans Noethys, aucune correction automatique)"), 0, wx.ALL, 8)
        sizer.Add(self.ctrl_anomalies, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        ligne = wx.BoxSizer(wx.HORIZONTAL)
        for bouton in actions:
            ligne.Add(bouton, 0, wx.RIGHT, 6)
        ligne.AddStretchSpacer()
        ligne.Add(fermer)
        sizer.Add(ligne, 0, wx.EXPAND | wx.ALL, 8)
        self.ctrl_methode.Bind(wx.EVT_CHOICE, self.OnMethode)
        self.ctrl_phase.Bind(wx.EVT_CHOICE, self.OnMethode)
        self.SetSizerAndFit(sizer)
        self.SetMinSize((1000, 760))
        self.CenterOnParent()

        self.ChargerReferentiel()
        self.MajListePresets()
        self.AppliquerPreset(None)

    # ------------------------------------------------------------------ outils
    def Message(self, texte, titre="Déclarations AFAS", style=wx.OK | wx.ICON_INFORMATION):
        wx.MessageBox(texte, titre, style, self)

    def Confirmer(self, texte):
        return wx.MessageBox(texte, "Déclarations AFAS", wx.YES_NO | wx.ICON_QUESTION, self) == wx.YES

    def Saisir(self, texte, valeur=""):
        with wx.TextEntryDialog(self, texte, "Déclarations AFAS", valeur) as dlg:
            return dlg.GetValue().strip() if dlg.ShowModal() == wx.ID_OK else None

    def Erreur(self, erreur):
        self.Message(str(erreur), "Déclarations AFAS", wx.OK | wx.ICON_ERROR)

    def ChargerReferentiel(self):
        try:
            self.referentiel = Referentiel.ChargerReferentiel()
            self.erreur_referentiel = None
        except (ValueError, Referentiel.ReferentielInvalide) as erreur:
            self.referentiel = Referentiel.ReferentielVide()
            self.erreur_referentiel = str(erreur)
            self.label_statut.SetLabel("Référentiel invalide : %s" % erreur)

    def Mode(self):
        return MODES[self.ctrl_mode.GetSelection()][0]

    def Equipement(self):
        return EQUIPEMENTS[self.ctrl_equipement.GetSelection()][0]

    def SitesProposes(self):
        """Sites admissibles du mode, appartenant à l'équipement choisi (jamais le groupe générique Bais)."""
        sites = []
        for site in Referentiel.SitesAdmissibles(self.ctrl_activite.GetStringSelection() or Referentiel.ACTIVITE_ALSH, self.Mode()):
            documente = Referentiel.EQUIPEMENT_DOCUMENTE.get(site)
            if documente is None:
                lien = self.referentiel["sites"].get(site)
                if lien and lien["equipement"] not in (None, self.Equipement()):
                    continue
            elif documente != self.Equipement():
                continue
            sites.append(site)
        return sites

    def SitesCoches(self):
        return [self.ctrl_sites.GetString(i) for i in range(self.ctrl_sites.GetCount()) if self.ctrl_sites.IsChecked(i)]

    def CocherSites(self, sites):
        proposes = self.SitesProposes()
        self.ctrl_sites.Set(proposes)
        for i, site in enumerate(proposes):
            self.ctrl_sites.Check(i, site in sites)

    def _cocher(self, ctrl, codes):
        for i, (code, libelle) in enumerate(Calendrier.STATUTS):
            ctrl.Check(i, code in codes)

    def _codes(self, ctrl):
        return [code for i, (code, libelle) in enumerate(Calendrier.STATUTS) if ctrl.IsChecked(i)]

    # ------------------------------------------------------------------ preset <-> interface
    def AppliquerPreset(self, preset):
        self.preset_courant = preset
        if preset is None:
            preset = Presets.NouveauPreset("", Conventions.PERISCOLAIRE, Conventions.EQUIPEMENT_BAIS)
        self.ctrl_nom.SetValue(preset["nom"])
        self.ctrl_mode.SetSelection([code for code, libelle in MODES].index(preset["mode"]))
        self.ctrl_equipement.SetSelection([code for code, libelle in EQUIPEMENTS].index(preset["equipement"]))
        self.CocherSites(preset["sites"])
        self.unites_classees = {int(cle): categorie for cle, categorie in preset["unites"].items()}
        self._cocher(self.ctrl_realise, preset["etats_realise"])
        self._cocher(self.ctrl_facture, preset["etats_facture"])
        self.ctrl_samedis.SetValue(preset["criteres_periodes"]["samedis_avec_ecole"])
        self.ctrl_repas.SetValue(preset["choix_conventionnels"]["inclure_repas_meridien"])
        self.ctrl_garderie.SetValue(preset["choix_conventionnels"]["inclure_garderie_caf"])
        self.MajLabelUnites()
        self.OnMethode(None)

    def LirePreset(self):
        """Preset construit depuis l'interface (identifiant et version du preset chargé conservés)."""
        base = self.preset_courant or Presets.NouveauPreset("", self.Mode(), self.Equipement())
        preset = dict(base)
        preset.update(nom=self.ctrl_nom.GetValue().strip(), mode=self.Mode(), equipement=self.Equipement(),
                      activite=self.ctrl_activite.GetStringSelection(), sites=self.SitesCoches(),
                      unites={str(ID): categorie for ID, categorie in sorted(self.unites_classees.items())},
                      etats_realise=self._codes(self.ctrl_realise), etats_facture=self._codes(self.ctrl_facture),
                      criteres_periodes={"samedis_avec_ecole": self.ctrl_samedis.GetValue()},
                      choix_conventionnels={"inclure_repas_meridien": self.ctrl_repas.GetValue(),
                                            "inclure_garderie_caf": self.ctrl_garderie.GetValue()})
        return Presets.ValiderPreset(preset)

    def MajLabelUnites(self):
        nombre = len(self.unites_classees)
        a_qualifier = sum(1 for c in self.unites_classees.values() if c == "a_qualifier")
        self.label_unites.SetLabel("%d unité(s) classée(s)%s" % (nombre, " dont %d à qualifier" % a_qualifier if a_qualifier else ""))

    def MajListePresets(self, IDselection=None):
        self.presets = Presets.ListerPresets()
        self.ctrl_preset.Set(["(nouveau preset)"] + [nom for ID, nom in self.presets])
        index = 0
        for i, (ID, nom) in enumerate(self.presets, 1):
            if ID == IDselection:
                index = i
        self.ctrl_preset.SetSelection(index)

    # ------------------------------------------------------------------ actions preset
    def OnChoixPreset(self, event):
        index = self.ctrl_preset.GetSelection()
        if index <= 0:
            self.IDprofil = None
            self.AppliquerPreset(None)
            return
        self.ChargerPreset(self.presets[index - 1][0])

    def ChargerPreset(self, IDprofil):
        try:
            preset = Presets.ChargerPreset(IDprofil)
        except ValueError as erreur:
            self.Erreur("Preset illisible ou invalide : %s" % erreur)
            return False
        self.IDprofil = IDprofil
        self.AppliquerPreset(preset)
        self.MajListePresets(IDprofil)
        return True

    def OnNouveau(self, event):
        self.IDprofil = None
        self.AppliquerPreset(None)
        self.MajListePresets(None)

    def OnEnregistrer(self, event):
        try:
            self.IDprofil, preset = Presets.EnregistrerPreset(self.LirePreset(), self.IDprofil)
        except ValueError as erreur:
            self.Erreur(erreur)
            return False
        self.AppliquerPreset(preset)
        self.MajListePresets(self.IDprofil)
        return True

    def OnDupliquer(self, event, nom=None):
        if self.IDprofil is None:
            return self.Message("Enregistrer d'abord le preset.")
        nom = nom if nom is not None else self.Saisir("Nom de la copie :", self.ctrl_nom.GetValue() + " (copie)")
        if not nom:
            return False
        try:
            self.IDprofil, preset = Presets.DupliquerPreset(self.IDprofil, nom)
        except ValueError as erreur:
            self.Erreur(erreur)
            return False
        self.AppliquerPreset(preset)
        self.MajListePresets(self.IDprofil)
        return True

    def OnRenommer(self, event, nom=None):
        if self.IDprofil is None:
            return self.Message("Enregistrer d'abord le preset.")
        nom = nom if nom is not None else self.Saisir("Nouveau nom :", self.ctrl_nom.GetValue())
        if not nom:
            return False
        try:
            self.IDprofil, preset = Presets.RenommerPreset(self.IDprofil, nom)
        except ValueError as erreur:
            self.Erreur(erreur)
            return False
        self.AppliquerPreset(preset)
        self.MajListePresets(self.IDprofil)
        return True

    def OnSupprimer(self, event):
        if self.IDprofil is None:
            return False
        if not self.Confirmer("Supprimer définitivement le preset « %s » ? Les déclarations archivées sont conservées."
                              % self.ctrl_nom.GetValue()):
            return False
        Presets.SupprimerPreset(self.IDprofil)
        self.OnNouveau(None)
        return True

    def OnRecharger(self, event):
        if self.IDprofil is not None:
            self.ChargerPreset(self.IDprofil)
        self.ChargerReferentiel()

    def OnContexte(self, event):
        # Changement d'activité, de mode ou d'équipement : seules les sélections compatibles sont conservées.
        self.CocherSites([site for site in self.SitesCoches() if site in self.SitesProposes()])

    def OnMethode(self, event):
        manuel = self.ctrl_methode.GetSelection() == 1 and Declaration.PHASES[self.ctrl_phase.GetSelection()][0] != Declaration.UTILS_AFAS.PHASE_REEL
        for ctrl in self.manuels.values():
            ctrl.Enable(manuel)

    # ------------------------------------------------------------------ unités et référentiel
    def UnitesNoethys(self):
        couples = Referentiel.Couples(self.referentiel, [s for s in self.SitesCoches() if s in self.referentiel["sites"]])
        activites = sorted({a for a, g in couples})
        return Donnees.ChargerUnites(activites) if activites else {}

    def OnUnites(self, event):
        unites = self.UnitesNoethys()
        if not unites:
            return self.Message("Sélectionner des sites reliés au référentiel pour classer leurs unités.")
        with DialogUnites(self, unites, self.unites_classees) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.unites_classees = dlg.GetClassement()
                self.MajLabelUnites()

    def OnReferentiel(self, event):
        with DialogReferentiel(self, self.referentiel) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.ChargerReferentiel()
                self.OnContexte(None)

    # ------------------------------------------------------------------ calcul et exports
    def Calculer(self):
        if self.erreur_referentiel:
            raise Declaration.DeclarationImpossible("Référentiel invalide : " + self.erreur_referentiel)
        preset = self.LirePreset()
        methode = Declaration.METHODE_MANUELLE if self.ctrl_methode.GetSelection() == 1 else Declaration.METHODE_N1
        return Declaration.Executer(preset, self.referentiel, self.ctrl_annee.GetValue(),
                                    Declaration.PHASES[self.ctrl_phase.GetSelection()][0], methode=methode,
                                    valeurs_manuelles={cle: ctrl.GetValue() for cle, ctrl in self.manuels.items()})

    def OnCalculer(self, event):
        self.rapport = None
        self.ctrl_resultats.DeleteAllItems()
        self.ctrl_anomalies.DeleteAllItems()
        try:
            self.rapport = self.Calculer()
        except (ValueError, Calcul.ContexteInvalide) as erreur:
            self.label_statut.SetLabel("Calcul impossible.")
            self.Erreur(erreur)
            return None
        self.AfficherRapport(self.rapport)
        return self.rapport

    def AfficherRapport(self, rapport):
        for ligne in rapport["indicateurs"]:
            index = self.ctrl_resultats.InsertItem(self.ctrl_resultats.GetItemCount(), ligne["libelle"])
            for colonne, champ in enumerate(("realise", "prevision", "total"), 1):
                self.ctrl_resultats.SetItem(index, colonne, Declaration.Heures(ligne[champ]))
        for anomalie in rapport["anomalies"]:
            index = self.ctrl_anomalies.InsertItem(self.ctrl_anomalies.GetItemCount(), str(anomalie["date"]))
            for colonne, champ in enumerate(("individu", "IDconso", "site", "unite", "nature", "consequence"), 1):
                self.ctrl_anomalies.SetItem(index, colonne, str(anomalie[champ] if anomalie[champ] is not None else ""))
            self.ctrl_anomalies.SetItem(index, 7, "oui" if anomalie["bloquante"] else "non")
        periodes = []
        if rapport["periode_realise"]:
            periodes.append("réalisé %s → %s" % tuple(rapport["periode_realise"]))
        if rapport["periode_prevision"]:
            periodes.append("prévision %s → %s" % tuple(rapport["periode_prevision"]))
        etat = "VALIDABLE" if rapport["validable"] else "NON VALIDABLE : " + " ; ".join(rapport["motifs_non_validable"])
        self.label_statut.SetLabel("%s — %s — convention %s — %s" % (rapport["libelle_phase"], ", ".join(periodes),
                                                                     rapport["convention"] or "aucune", etat))
        self.Layout()

    def _prefixe(self):
        return "AFAS_%s_%s_%d" % (self.rapport["preset"]["equipement"], self.rapport["preset"]["mode"], self.rapport["annee"])

    def _dossier(self):
        with wx.DirDialog(self, "Dossier d'export") as dlg:
            return dlg.GetPath() if dlg.ShowModal() == wx.ID_OK else None

    def OnExporterDeclaration(self, event, dossier=None):
        if self.rapport is None and self.OnCalculer(None) is None:
            return None
        if not self.rapport["validable"]:
            self.Erreur("Déclaration non validable : " + " ; ".join(self.rapport["motifs_non_validable"]))
            return None
        dossier = dossier or self._dossier()
        if not dossier:
            return None
        try:
            chemins = Declaration.ExporterDeclaration(dossier, self.rapport, self._prefixe())
            Declaration.EnregistrerHistorique(self.rapport)
        except (OSError, ValueError) as erreur:
            self.Erreur(erreur)
            return None
        self.Message("Déclaration exportée et archivée :\n" + "\n".join(os.path.basename(c) for c in chemins.values()))
        return chemins

    def OnExporterControle(self, event, dossier=None):
        if self.rapport is None and self.OnCalculer(None) is None:
            return None
        dossier = dossier or self._dossier()
        if not dossier:
            return None
        try:
            chemins = Declaration.ExporterControle(dossier, self.rapport, self._prefixe() + "_controle")
        except OSError as erreur:
            self.Erreur(erreur)
            return None
        self.Message("Export de contrôle :\n" + "\n".join(os.path.basename(c) for c in chemins.values()))
        return chemins

    def OnHistorique(self, event):
        with DialogHistorique(self) as dlg:
            dlg.ShowModal()


class DialogUnites(wx.Dialog):
    """Classement explicite des unités Noethys (jamais déduit du libellé)."""

    def __init__(self, parent, unites, classement):
        super().__init__(parent, title="Classement des unités", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.choix = {}
        panneau = wx.ScrolledWindow(self)
        panneau.SetScrollRate(0, 20)
        grille = wx.FlexGridSizer(cols=3, vgap=4, hgap=10)
        for IDunite, unite in sorted(unites.items(), key=lambda x: (x[1]["IDactivite"], x[1]["nom"])):
            grille.Add(wx.StaticText(panneau, label="%s (%d)" % (unite["nom"], IDunite)), 0, wx.ALIGN_CENTER_VERTICAL)
            grille.Add(wx.StaticText(panneau, label="%s, %s → %s" % (unite.get("type") or "?", unite.get("heure_debut") or "--:--",
                                                                   unite.get("heure_fin") or "--:--")), 0, wx.ALIGN_CENTER_VERTICAL)
            choix = wx.Choice(panneau, choices=[libelle for code, libelle in Calcul.CATEGORIES])
            choix.SetSelection(Calcul.CODES_CATEGORIES.index(classement.get(IDunite, "a_qualifier")))
            grille.Add(choix)
            self.choix[IDunite] = choix
        panneau.SetSizer(grille)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(panneau, 1, wx.EXPAND | wx.ALL, 8)
        sizer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(sizer)
        self.SetSize((720, 520))

    def GetClassement(self):
        return {IDunite: Calcul.CODES_CATEGORIES[choix.GetSelection()] for IDunite, choix in self.choix.items()}


class DialogReferentiel(wx.Dialog):
    """Correspondance site → groupe Noethys vérifié, équipement, Moutiers, séjours qualifiés."""

    def __init__(self, parent, referentiel):
        super().__init__(parent, title="Référentiel AFAS — sites, équipements et séjours", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.parent = parent
        self.referentiel = dict(referentiel)
        self.sejours = list(referentiel["sejours"])
        groupes = Referentiel.ChargerGroupes()
        self.groupes = sorted(groupes.items(), key=lambda x: (x[1][0], x[1][1]))
        libelles = ["(non relié)"] + ["Activité %d — %s (groupe %d)" % (a, nom, g) for g, (a, nom) in self.groupes]
        grille = wx.FlexGridSizer(cols=3, vgap=4, hgap=10)
        self.ctrl_groupes, self.ctrl_equipements = {}, {}
        for site in Referentiel.SITES:
            grille.Add(wx.StaticText(self, label=site), 0, wx.ALIGN_CENTER_VERTICAL)
            choix = wx.Choice(self, choices=libelles)
            lien = referentiel["sites"].get(site)
            index = 0
            for i, (g, (a, nom)) in enumerate(self.groupes, 1):
                if lien and lien["IDgroupe"] == g:
                    index = i
            choix.SetSelection(index)
            grille.Add(choix, 1, wx.EXPAND)
            self.ctrl_groupes[site] = choix
            if site in Referentiel.EQUIPEMENT_DOCUMENTE:
                grille.Add(wx.StaticText(self, label=Conventions.EQUIPEMENTS[Referentiel.EQUIPEMENT_DOCUMENTE[site]]["libelle"]))
            else:
                equipement = wx.Choice(self, choices=["(à choisir)"] + [libelle for code, libelle in EQUIPEMENTS])
                codes = [code for code, libelle in EQUIPEMENTS]
                equipement.SetSelection(codes.index(lien["equipement"]) + 1 if lien and lien["equipement"] in codes else 0)
                grille.Add(equipement)
                self.ctrl_equipements[site] = equipement
        grille.AddGrowableCol(1)
        self.ctrl_moutiers = wx.CheckBox(self, label="Rattachement de Moutiers à la convention « La Guerche-Moutiers » confirmé "
                                                     "(formulaire d'implantation vérifié)")
        self.ctrl_moutiers.SetValue(referentiel["moutiers_rattachement_confirme"])
        self.ctrl_sejours = wx.ListBox(self)
        self.ctrl_sejours.SetMinSize((-1, 100))
        ajouter = wx.Button(self, label="Ajouter un séjour qualifié…")
        retirer = wx.Button(self, label="Retirer")
        ajouter.Bind(wx.EVT_BUTTON, self.OnAjouterSejour)
        retirer.Bind(wx.EVT_BUTTON, self.OnRetirerSejour)
        self.MajSejours()
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(grille, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(self.ctrl_moutiers, 0, wx.ALL, 8)
        sizer.Add(wx.StaticText(self, label="Séjours qualifiés (1 à 4 nuits, ou 5 nuits / 6 jours sous conditions) — 10 h par journée réalisée"), 0, wx.LEFT, 8)
        sizer.Add(self.ctrl_sejours, 1, wx.EXPAND | wx.ALL, 8)
        boutons = wx.BoxSizer(wx.HORIZONTAL)
        boutons.Add(ajouter, 0, wx.RIGHT, 6)
        boutons.Add(retirer)
        sizer.Add(boutons, 0, wx.LEFT, 8)
        sizer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizerAndFit(sizer)
        self.Bind(wx.EVT_BUTTON, self.OnOk, id=wx.ID_OK)

    def MajSejours(self):
        self.ctrl_sejours.Set(["%s — %s du %s au %s (%d nuit(s))" % (s["libelle"], s["site"], s["date_debut"], s["date_fin"], s["nuits"])
                               for s in self.sejours])

    def LireReferentiel(self):
        sites = {}
        for site, choix in self.ctrl_groupes.items():
            index = choix.GetSelection()
            if index <= 0:
                continue
            IDgroupe, (IDactivite, nom) = self.groupes[index - 1]
            equipement = Referentiel.EQUIPEMENT_DOCUMENTE.get(site)
            if site in self.ctrl_equipements:
                selection = self.ctrl_equipements[site].GetSelection()
                equipement = EQUIPEMENTS[selection - 1][0] if selection > 0 else None
            sites[site] = {"IDactivite": IDactivite, "IDgroupe": IDgroupe, "nom_groupe": nom, "equipement": equipement}
        return {"format": Referentiel.FORMAT_REFERENTIEL, "sites": sites,
                "moutiers_rattachement_confirme": self.ctrl_moutiers.GetValue(), "sejours": list(self.sejours)}

    def OnAjouterSejour(self, event):
        with DialogSejour(self, self.LireReferentiel()["sites"]) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.sejours.append(dlg.sejour)
                self.MajSejours()

    def OnRetirerSejour(self, event):
        index = self.ctrl_sejours.GetSelection()
        if index != wx.NOT_FOUND:
            del self.sejours[index]
            self.MajSejours()

    def OnOk(self, event):
        try:
            Referentiel.EnregistrerReferentiel(self.LireReferentiel())
        except (ValueError, Referentiel.ReferentielInvalide) as erreur:
            wx.MessageBox(str(erreur), "Référentiel AFAS", wx.OK | wx.ICON_ERROR, self)
            return
        self.EndModal(wx.ID_OK)


class DialogSejour(wx.Dialog):
    def __init__(self, parent, sites):
        super().__init__(parent, title="Séjour qualifié")
        self.sites = sites
        self.sejour = None
        self.ctrl_libelle = wx.TextCtrl(self)
        self.ctrl_site = wx.Choice(self, choices=sorted(sites))
        self.ctrl_debut = wx.TextCtrl(self, value="AAAA-MM-JJ")
        self.ctrl_fin = wx.TextCtrl(self, value="AAAA-MM-JJ")
        self.ctrl_nuits = wx.SpinCtrl(self, min=1, max=5, initial=1)
        self.ctrl_prevu = wx.CheckBox(self, label="Prévu dès la déclaration annuelle de l'accueil")
        self.ctrl_projet = wx.CheckBox(self, label="Intégré au projet éducatif de l'accueil de loisirs")
        self.ctrl_declare = wx.CheckBox(self, label="Déclaré en tant que séjour de vacances")
        grille = wx.FlexGridSizer(cols=2, vgap=4, hgap=8)
        for libelle, ctrl in (("Libellé", self.ctrl_libelle), ("Site", self.ctrl_site), ("Début", self.ctrl_debut),
                              ("Fin", self.ctrl_fin), ("Nuits", self.ctrl_nuits)):
            grille.Add(wx.StaticText(self, label=libelle), 0, wx.ALIGN_CENTER_VERTICAL)
            grille.Add(ctrl, 1, wx.EXPAND)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(grille, 0, wx.EXPAND | wx.ALL, 8)
        for case in (self.ctrl_prevu, self.ctrl_projet, self.ctrl_declare):
            sizer.Add(case, 0, wx.LEFT | wx.BOTTOM, 8)
        sizer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizerAndFit(sizer)
        self.Bind(wx.EVT_BUTTON, self.OnOk, id=wx.ID_OK)

    def OnOk(self, event):
        sejour = {"id": "%s-%s" % (self.ctrl_debut.GetValue().strip(), datetime.datetime.now().strftime("%H%M%S%f")),
                  "libelle": self.ctrl_libelle.GetValue().strip() or "Séjour", "site": self.ctrl_site.GetStringSelection(),
                  "date_debut": self.ctrl_debut.GetValue().strip(), "date_fin": self.ctrl_fin.GetValue().strip(),
                  "nuits": self.ctrl_nuits.GetValue(), "prevu_declaration_annuelle": self.ctrl_prevu.GetValue(),
                  "integre_projet_educatif": self.ctrl_projet.GetValue(), "declare_sejour_vacances": self.ctrl_declare.GetValue()}
        try:
            Referentiel.ValiderSejour(sejour, self.sites)
        except Referentiel.ReferentielInvalide as erreur:
            wx.MessageBox(str(erreur), "Séjour qualifié", wx.OK | wx.ICON_ERROR, self)
            return
        self.sejour = sejour
        self.EndModal(wx.ID_OK)


class DialogHistorique(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Déclarations AFAS archivées", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.entrees = Declaration.ListerHistorique()
        self.ctrl_liste = wx.ListBox(self, choices=[libelle for ID, libelle in self.entrees])
        self.ctrl_detail = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.ctrl_liste.Bind(wx.EVT_LISTBOX, self.OnSelection)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.ctrl_liste, 1, wx.EXPAND | wx.ALL, 8)
        sizer.Add(self.ctrl_detail, 2, wx.EXPAND | wx.ALL, 8)
        principal = wx.BoxSizer(wx.VERTICAL)
        principal.Add(sizer, 1, wx.EXPAND)
        principal.Add(self.CreateButtonSizer(wx.CLOSE), 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(principal)
        self.SetSize((900, 520))
        self.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_CLOSE), id=wx.ID_CLOSE)

    def OnSelection(self, event):
        index = self.ctrl_liste.GetSelection()
        if index == wx.NOT_FOUND:
            return
        try:
            archive = Declaration.ChargerHistorique(self.entrees[index][0])
        except ValueError as erreur:
            self.ctrl_detail.SetValue(str(erreur))
            return
        lignes = ["Intégrité : %s" % ("vérifiée" if archive["integrite"] else "ALTÉRÉE"),
                  "Preset : %s (version %s, empreinte %s)" % (archive["preset"]["nom"], archive["preset"]["version"], archive["empreinte_preset"]),
                  "Année / phase : %s — %s" % (archive["annee"], archive["libelle_phase"]),
                  "Convention : %s ; règles %s" % (archive["convention"], archive["version_regles"]),
                  "Exécution : %s ; empreinte %s" % (archive["date_execution"], archive["empreinte"]), ""]
        for ligne in archive["indicateurs"]:
            lignes.append("%s : %s / %s / %s" % (ligne["libelle"], Declaration.Heures(ligne["realise"]),
                                                 Declaration.Heures(ligne["prevision"]), Declaration.Heures(ligne["total"])))
        self.ctrl_detail.SetValue("\n".join(lignes))
