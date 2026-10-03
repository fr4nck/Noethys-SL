#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Dialogue de génération d'une convention depuis la fiche Famille.

Réutilise les composants existants (CTRL_Choix_modele.CTRL_Choice pour
le choix du modèle, CTRL_Grille_periode.MyDatePickerCtrl pour les
dates) : aucun nouveau composant visuel n'est créé. Aucune saison ni
type de structure n'est rendu obligatoire ici : c'est une saisie
ponctuelle facultative qui préremplit {CONVENTION_SAISON}, laissée
vide si l'utilisateur ne la renseigne pas.

Ce dialogue permet aussi de renseigner les champs qui ne peuvent JAMAIS
être déterminés automatiquement depuis Noethys (fonction du
représentant, date/lieu de signature), et de corriger les valeurs
préremplies automatiquement (nom du représentant, tarif horaire)
lorsque l'auto-détection est absente ou ambiguë. Ces saisies ne sont
que des overrides de génération transmis à
Utils.UTILS_Convention_champs.GetChampsConvention : rien n'est jamais
enregistré dans les données Noethys (prestations, tarifs,
consommations, individus, familles).

Un bouton "Imprimer le planning" permet, depuis le même écran, de
générer le Planning séparé (moteur Réservations historique, inchangé)
pour la même famille et la même période : Convention et Planning
restent deux fichiers PDF distincts, aucune fusion n'est faite ici.
"""

from __future__ import annotations

import datetime

import wx

from Utils.UTILS_Traduction import _
from Ctrl.CTRL_Choix_modele import CTRL_Choice
from Ctrl.CTRL_Grille_periode import MyDatePickerCtrl


def _CalculerTailleDialogue(taille_contenu, taille_boutons, taille_ecran, taille_naturelle=None):
    """Calcule la taille initiale depuis la taille naturelle du dialogue.

    Tant que la taille naturelle tient dans la zone de travail de l'écran,
    elle est conservée telle quelle. Le scroll n'intervient qu'en repli :
    si la hauteur naturelle dépasse l'écran, elle est bornée à 88 % de la
    work area. Toutes les valeurs restent exprimées en unités wx afin de
    conserver le comportement DPI/scaling de la plateforme.
    """
    largeur_ecran, hauteur_ecran = (int(taille_ecran[0]), int(taille_ecran[1]))
    if taille_naturelle is None:
        # Repli utilisé notamment par les tests unitaires : l'appelant réel
        # fournit ci-dessous la taille calculée par ComputeFittingWindowSize(),
        # qui tient compte des décorations de la fenêtre.
        largeur_naturelle = max(int(taille_contenu[0]), int(taille_boutons[0])) + 30
        hauteur_naturelle = int(taille_contenu[1]) + int(taille_boutons[1]) + 30
    else:
        largeur_naturelle = int(taille_naturelle[0])
        hauteur_naturelle = int(taille_naturelle[1])

    largeur = largeur_naturelle
    hauteur = hauteur_naturelle
    if largeur > largeur_ecran:
        largeur = max(1, int(largeur_ecran * 0.95))
    if hauteur > hauteur_ecran:
        hauteur = max(1, int(hauteur_ecran * 0.88))
    return largeur, hauteur


class _ZoneConventionScrollable(wx.ScrolledWindow):
    """Zone centrale scrollable qui relaie le changement de dates au dialogue."""

    def __init__(self, parent):
        wx.ScrolledWindow.__init__(
            self, parent, -1, style=wx.VSCROLL | wx.TAB_TRAVERSAL | wx.BORDER_NONE
        )
        self.SetScrollRate(0, 10)

    def OnSelection(self):
        self.GetParent().OnSelection()


class Dialog(wx.Dialog):
    def __init__(self, parent, IDfamille=None, date_debut=None, date_fin=None, saison=""):
        wx.Dialog.__init__(self, parent, -1, _(u"Générer une convention"),
                            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.IDfamille = IDfamille

        # Valeurs automatiques actuellement affichées (pour savoir si
        # l'utilisateur a corrigé manuellement une valeur préremplie --
        # voir RecalculerValeursAutomatiques ci-dessous).
        self._auto_representant = u""
        self._auto_tarif = u""
        self._auto_tarif_adulte = u""
        self._auto_tarif_enfant = u""

        # Les champs sont placés dans une zone centrale scrollable. La
        # barre de boutons reste directement dans le dialogue afin d'être
        # toujours visible, même sous scaling/DPI Windows élevé.
        self.zone_contenu = _ZoneConventionScrollable(self)
        parent_contenu = self.zone_contenu

        # --- Modèle -----------------------------------------------------
        label_modele = wx.StaticText(parent_contenu, -1, _(u"Modèle de convention :"))
        # Une installation neuve doit être immédiatement exploitable : si
        # aucun modèle Convention n'existe, installe idempotemment les
        # exemples embarqués (associatifs + scolaire). Aucun modèle existant
        # n'est jamais écrasé par ce chemin.
        try:
            from Utils import UTILS_Convention_modeles
            UTILS_Convention_modeles.AssurerModelesDisponibles()
        except Exception:
            # Le bouton de gestion permet de retenter explicitement ; ne pas
            # rendre tout le dialogue inutilisable sur une erreur de ressource.
            pass
        self.ctrl_modele = CTRL_Choice(parent_contenu, categorie="convention")
        # CTRL_Choice conserve en priorité le modèle marqué par défaut. Si
        # des modèles existent mais qu'aucun n'est marqué "defaut", wx peut
        # laisser le Choice sans sélection initiale : garder alors le premier
        # modèle visible, comme avant la reconstruction responsive du layout.
        if self.ctrl_modele.GetID() is None and self.ctrl_modele.GetCount() > 0:
            self.ctrl_modele.SetSelection(0)
        self.bouton_modeles = wx.Button(parent_contenu, -1, _(u"Gérer les modèles..."))
        self.bouton_modeles.SetToolTip(wx.ToolTip(
            _(u"Modifier, dupliquer, renommer, supprimer ou installer les modèles Noedoc de convention.")))
        sizer_modele = wx.BoxSizer(wx.HORIZONTAL)
        sizer_modele.Add(self.ctrl_modele, 1, wx.EXPAND | wx.RIGHT, 5)
        sizer_modele.Add(self.bouton_modeles, 0)

        self.ctrl_format = wx.Choice(parent_contenu, choices=[_(u"Noedoc → PDF"), _(u"Word → DOCX")])
        self.ctrl_format.SetSelection(0)
        self.ctrl_docx = wx.FilePickerCtrl(parent_contenu, message=_(u"Choisir le modèle Word"),
                                         wildcard="Document Word (*.docx)|*.docx",
                                         style=wx.FLP_OPEN | wx.FLP_FILE_MUST_EXIST | wx.FLP_USE_TEXTCTRL)
        self.ctrl_docx.Enable(False)
        self.ctrl_docx.SetToolTip(_(u"Modèle Word contenant les mêmes mots-clés {CODE} que Noedoc."))
        self.Bind(wx.EVT_CHOICE, self.OnFormatDocument, self.ctrl_format)

        # --- Période ------------------------------------------------------
        label_periode = wx.StaticText(parent_contenu, -1, _(u"Période concernée :"))
        self.ctrl_date_debut = MyDatePickerCtrl(parent_contenu)
        self.ctrl_date_fin = MyDatePickerCtrl(parent_contenu)
        aujourdhui = datetime.date.today()
        periode_auto = (None, None)
        if self.IDfamille is not None and (date_debut is None or date_fin is None):
            try:
                from Utils import UTILS_Convention_champs as CC
                periode_auto = CC.GetPeriodeParDefaut(self.IDfamille, date_reference=aujourdhui)
            except Exception:
                periode_auto = (None, None)
        debut_initial = date_debut or periode_auto[0] or aujourdhui
        fin_initiale = date_fin or periode_auto[1] or debut_initial
        self.ctrl_date_debut.SetDate(debut_initial)
        self.ctrl_date_fin.SetDate(fin_initiale)
        self.label_periode_info = wx.StaticText(parent_contenu, -1, u"")
        if periode_auto[0] is not None and periode_auto[1] is not None:
            self.label_periode_info.SetLabel(_(u"Période préremplie depuis les séances enregistrées."))
        elif date_debut is None and date_fin is None:
            self.label_periode_info.SetLabel(_(u"Aucune séance trouvée : vérifiez la période manuellement."))
            self.label_periode_info.SetForegroundColour(wx.Colour(180, 70, 0))
        label_saison = wx.StaticText(parent_contenu, -1, _(u"Saison (facultatif, ex. 2026-2027) :"))
        saison_initiale = saison
        if not saison_initiale and periode_auto[0] is not None and periode_auto[1] is not None:
            try:
                from Utils import UTILS_Convention_champs as CC
                saison_initiale = CC.SaisonDepuisPeriode(periode_auto[0], periode_auto[1])
            except Exception:
                saison_initiale = u""
        self.ctrl_saison = wx.TextCtrl(parent_contenu, -1, saison_initiale)

        # --- Représentant ---------------------------------------------
        label_representant = wx.StaticText(parent_contenu, -1, _(u"Représentant de la structure :"))
        self.ctrl_representant_nom_complet = wx.TextCtrl(parent_contenu, -1, u"")
        self.ctrl_representant_nom_complet.SetToolTip(wx.ToolTip(
            _(u"Préremplit automatiquement depuis le représentant rattaché à la famille. Corrigez uniquement si nécessaire.")))

        label_fonction = wx.StaticText(parent_contenu, -1, _(u"Fonction (facultatif) :"))
        self.ctrl_representant_fonction = wx.TextCtrl(parent_contenu, -1, u"")

        # --- Signature ------------------------------------------------
        label_date_signature = wx.StaticText(parent_contenu, -1, _(u"Date et lieu de signature :"))
        self.ctrl_date_signature = MyDatePickerCtrl(parent_contenu)
        self.ctrl_date_signature.SetDate(aujourdhui)

        self.ctrl_lieu_signature = wx.TextCtrl(parent_contenu, -1, u"")
        self.ctrl_lieu_signature.SetToolTip(wx.ToolTip(_(u"Lieu de signature (ex. LANNILIS)")))

        # --- Tarifs ------------------------------------------------------
        label_tarifs = wx.StaticText(parent_contenu, -1, _(u"Tarifs horaires détectés (€) :"))
        self.ctrl_tarif_horaire = wx.TextCtrl(parent_contenu, -1, u"")
        self.ctrl_tarif_adulte = wx.TextCtrl(parent_contenu, -1, u"")
        self.ctrl_tarif_enfant = wx.TextCtrl(parent_contenu, -1, u"")
        self.label_tarif_horaire_provenance = wx.StaticText(parent_contenu, -1, u"", size=(390, -1))
        self.label_tarif_adulte_provenance = wx.StaticText(parent_contenu, -1, u"", size=(390, -1))
        self.label_tarif_enfant_provenance = wx.StaticText(parent_contenu, -1, u"", size=(390, -1))
        sizer_tarifs = wx.FlexGridSizer(rows=3, cols=3, vgap=5, hgap=8)
        for libelle, ctrl, provenance in (
            (_(u"Unique :"), self.ctrl_tarif_horaire, self.label_tarif_horaire_provenance),
            (_(u"Adultes :"), self.ctrl_tarif_adulte, self.label_tarif_adulte_provenance),
            (_(u"Enfants :"), self.ctrl_tarif_enfant, self.label_tarif_enfant_provenance),
        ):
            sizer_tarifs.Add(wx.StaticText(parent_contenu, -1, libelle), 0, wx.ALIGN_CENTER_VERTICAL)
            sizer_tarifs.Add(ctrl, 0, wx.EXPAND)
            sizer_tarifs.Add(provenance, 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        sizer_tarifs.AddGrowableCol(2)
        self.ctrl_tarif_horaire.SetToolTip(wx.ToolTip(_(u"Utilisé seulement quand un taux unique est démontré sur la période.")))
        self.ctrl_tarif_adulte.SetToolTip(wx.ToolTip(_(u"Prérempli quand les données démontrent un taux adulte stable.")))
        self.ctrl_tarif_enfant.SetToolTip(wx.ToolTip(_(u"Prérempli quand les données démontrent un taux enfant stable.")))

        # --- Boutons ------------------------------------------------------
        self.bouton_planning = wx.Button(self, -1, _(u"Imprimer le planning"))
        self.bouton_planning.SetToolTip(wx.ToolTip(
            _(u"Génère, pour la même famille et la même période, le Planning séparé (document distinct de la Convention).")))
        self.bouton_ok = wx.Button(self, wx.ID_OK, _(u"Générer la convention"))
        self.bouton_ok.SetDefault()
        self.bouton_annuler = wx.Button(self, wx.ID_CANCEL, _(u"Annuler"))

        self.Bind(wx.EVT_BUTTON, self.OnBoutonModeles, self.bouton_modeles)
        self.Bind(wx.EVT_BUTTON, self.OnBoutonPlanning, self.bouton_planning)
        self.Bind(wx.EVT_BUTTON, self.OnBoutonOk, self.bouton_ok)

        # --- Mise en page ------------------------------------------------
        sizer_periode_ligne = wx.BoxSizer(wx.HORIZONTAL)
        sizer_periode_ligne.Add(self.ctrl_date_debut, 0, wx.RIGHT, 5)
        sizer_periode_ligne.Add(wx.StaticText(parent_contenu, -1, _(u"au")), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 5)
        sizer_periode_ligne.Add(self.ctrl_date_fin, 0)
        sizer_periode = wx.BoxSizer(wx.VERTICAL)
        sizer_periode.Add(sizer_periode_ligne, 0)
        sizer_periode.Add(self.label_periode_info, 0, wx.TOP, 4)

        sizer_signature = wx.BoxSizer(wx.HORIZONTAL)
        sizer_signature.Add(self.ctrl_date_signature, 0, wx.RIGHT, 10)
        sizer_signature.Add(self.ctrl_lieu_signature, 1, wx.EXPAND)

        sizer_boutons = wx.StdDialogButtonSizer()
        sizer_boutons.AddButton(self.bouton_ok)
        sizer_boutons.AddButton(self.bouton_annuler)
        sizer_boutons.Realize()

        sizer_bas = wx.BoxSizer(wx.HORIZONTAL)
        sizer_bas.Add(self.bouton_planning, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer_bas.AddStretchSpacer()
        sizer_bas.Add(sizer_boutons, 0)

        sizer_contenu = wx.BoxSizer(wx.VERTICAL)
        for label, ctrl in (
            (wx.StaticText(parent_contenu, -1, _(u"Format du document :")), self.ctrl_format),
            (label_modele, sizer_modele),
            (wx.StaticText(parent_contenu, -1, _(u"Modèle Word (.docx) :")), self.ctrl_docx),
            (label_periode, sizer_periode),
            (label_saison, self.ctrl_saison),
            (label_representant, self.ctrl_representant_nom_complet),
            (label_fonction, self.ctrl_representant_fonction),
            (label_date_signature, sizer_signature),
            (label_tarifs, sizer_tarifs),
        ):
            sizer_contenu.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
            if isinstance(ctrl, wx.Sizer):
                sizer_contenu.Add(ctrl, 0, wx.ALL | wx.EXPAND, 10)
            else:
                sizer_contenu.Add(ctrl, 0, wx.ALL | wx.EXPAND, 10)

        self.zone_contenu.SetSizer(sizer_contenu)
        self.zone_contenu.SetAutoLayout(True)
        self.zone_contenu.FitInside()

        sizer_general = wx.BoxSizer(wx.VERTICAL)
        sizer_general.Add(self.zone_contenu, 1, wx.EXPAND)
        sizer_general.Add(sizer_bas, 0, wx.ALL | wx.EXPAND, 10)
        self.SetSizer(sizer_general)

        # Pour la taille d'ouverture, demander d'abord au ScrolledWindow de
        # réserver la place de tout son contenu. ComputeFittingWindowSize()
        # donne alors la vraie taille naturelle de la fenêtre, décorations
        # comprises. On libère ensuite cette contrainte : si l'utilisateur
        # réduit la fenêtre (ou si l'écran est trop petit), le scroll reprend
        # immédiatement son rôle et les boutons restent hors de la zone.
        taille_contenu = sizer_contenu.CalcMin()
        self.zone_contenu.SetMinSize(taille_contenu)
        taille_naturelle = sizer_general.ComputeFittingWindowSize(self)
        self.zone_contenu.SetMinSize(wx.DefaultSize)

        index_ecran = wx.Display.GetFromWindow(self)
        if index_ecran != wx.NOT_FOUND:
            zone_ecran = wx.Display(index_ecran).GetClientArea()
        else:
            zone_ecran = wx.GetClientDisplayRect()
        taille = _CalculerTailleDialogue(
            taille_contenu, sizer_bas.CalcMin(), zone_ecran.GetSize(), taille_naturelle
        )
        self.SetSize(taille)
        self.SetMinSize((min(520, taille[0]), min(380, taille[1])))
        self.Layout()
        self.zone_contenu.FitInside()
        self.CentreOnParent()

        # Préremplissage initial des valeurs automatiques (représentant,
        # tarif) pour la période sélectionnée par défaut.
        self.RecalculerValeursAutomatiques()

    # ------------------------------------------------------------------
    # Gestion des modèles Convention / Noedoc
    # ------------------------------------------------------------------

    def OnFormatDocument(self, event):
        word = self.ctrl_format.GetSelection() == 1
        self.ctrl_modele.Enable(not word)
        self.bouton_modeles.Enable(not word)
        self.ctrl_docx.Enable(word)

    def GetModeleWord(self):
        if self.ctrl_format.GetSelection() == 1:
            return self.ctrl_docx.GetPath()
        return None

    def RafraichirModeles(self, IDmodele=None, selectionPremier=False):
        self.ctrl_modele.MAJ()
        if IDmodele is not None:
            self.ctrl_modele.SetID(IDmodele)
        if selectionPremier and self.ctrl_modele.GetSelection() == wx.NOT_FOUND and self.ctrl_modele.GetCount() > 0:
            self.ctrl_modele.SetSelection(0)

    def OnBoutonModeles(self, event):
        IDmodele = self.GetIDmodele()
        menu = wx.Menu()
        ID_MODIFIER = wx.Window.NewControlId()
        ID_DUPLIQUER = wx.Window.NewControlId()
        ID_RENOMMER = wx.Window.NewControlId()
        ID_DEFAUT = wx.Window.NewControlId()
        ID_SUPPRIMER = wx.Window.NewControlId()
        ID_INSTALLER = wx.Window.NewControlId()

        menu.Append(ID_MODIFIER, _(u"Modifier dans Noedoc..."))
        menu.Append(ID_DUPLIQUER, _(u"Dupliquer..."))
        menu.Append(ID_RENOMMER, _(u"Renommer..."))
        menu.Append(ID_DEFAUT, _(u"Définir comme modèle par défaut"))
        menu.Append(ID_SUPPRIMER, _(u"Supprimer..."))
        menu.AppendSeparator()
        menu.Append(ID_INSTALLER, _(u"Installer les modèles d'exemple"))

        for identifiant in (ID_MODIFIER, ID_DUPLIQUER, ID_RENOMMER, ID_DEFAUT, ID_SUPPRIMER):
            menu.Enable(identifiant, IDmodele is not None)

        self.Bind(wx.EVT_MENU, self.OnModifierModele, id=ID_MODIFIER)
        self.Bind(wx.EVT_MENU, self.OnDupliquerModele, id=ID_DUPLIQUER)
        self.Bind(wx.EVT_MENU, self.OnRenommerModele, id=ID_RENOMMER)
        self.Bind(wx.EVT_MENU, self.OnDefinirModeleDefaut, id=ID_DEFAUT)
        self.Bind(wx.EVT_MENU, self.OnSupprimerModele, id=ID_SUPPRIMER)
        self.Bind(wx.EVT_MENU, self.OnInstallerModelesExemples, id=ID_INSTALLER)
        self.PopupMenu(menu, self.bouton_modeles.GetPosition())
        menu.Destroy()

    def OnModifierModele(self, event=None):
        IDmodele = self.GetIDmodele()
        if IDmodele is None:
            return
        from Utils import UTILS_Convention_modeles
        from Dlg import DLG_Noedoc
        infos = UTILS_Convention_modeles.GetModele(IDmodele)
        if infos is None:
            self._Informer(_(u"Le modèle sélectionné n'existe plus."), erreur=True)
            self.RafraichirModeles(selectionPremier=True)
            return
        largeur = infos["largeur"] or 210
        hauteur = infos["hauteur"] or 297
        dlg = DLG_Noedoc.Dialog(
            self,
            IDmodele=IDmodele,
            nom=infos["nom"],
            observations=infos["observations"],
            IDfond=infos["IDfond"],
            categorie="convention",
            taille_page=(largeur, hauteur),
        )
        dlg.ShowModal()
        IDfinal = dlg.GetIDmodele()
        dlg.Destroy()
        self.RafraichirModeles(IDmodele=IDfinal or IDmodele, selectionPremier=True)

    def OnDupliquerModele(self, event=None):
        IDmodele = self.GetIDmodele()
        if IDmodele is None:
            return
        nomActuel = self.ctrl_modele.GetStringSelection()
        dlg = wx.TextEntryDialog(
            self, _(u"Nom de la copie :"), _(u"Dupliquer le modèle"),
            _(u"Copie de %s") % nomActuel,
        )
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        nom = dlg.GetValue()
        dlg.Destroy()
        try:
            from Utils import UTILS_Convention_modeles
            newID = UTILS_Convention_modeles.DupliquerModele(IDmodele, nom)
            self.RafraichirModeles(IDmodele=newID, selectionPremier=True)
        except Exception as err:
            self._Informer(_(u"Le modèle n'a pas pu être dupliqué.\n\n%s") % err, erreur=True)

    def OnRenommerModele(self, event=None):
        IDmodele = self.GetIDmodele()
        if IDmodele is None:
            return
        dlg = wx.TextEntryDialog(
            self, _(u"Nouveau nom du modèle :"), _(u"Renommer le modèle"),
            self.ctrl_modele.GetStringSelection(),
        )
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        nom = dlg.GetValue()
        dlg.Destroy()
        try:
            from Utils import UTILS_Convention_modeles
            UTILS_Convention_modeles.RenommerModele(IDmodele, nom)
            self.RafraichirModeles(IDmodele=IDmodele, selectionPremier=True)
        except Exception as err:
            self._Informer(_(u"Le modèle n'a pas pu être renommé.\n\n%s") % err, erreur=True)

    def OnDefinirModeleDefaut(self, event=None):
        IDmodele = self.GetIDmodele()
        if IDmodele is None:
            return
        try:
            from Utils import UTILS_Convention_modeles
            UTILS_Convention_modeles.DefinirModeleDefaut(IDmodele)
            self.RafraichirModeles(IDmodele=IDmodele, selectionPremier=True)
        except Exception as err:
            self._Informer(_(u"Le modèle par défaut n'a pas pu être enregistré.\n\n%s") % err, erreur=True)

    def OnSupprimerModele(self, event=None):
        IDmodele = self.GetIDmodele()
        if IDmodele is None:
            return
        nom = self.ctrl_modele.GetStringSelection()
        dlg = wx.MessageDialog(
            self,
            _(u"Supprimer définitivement le modèle « %s » et tous ses objets ?") % nom,
            _(u"Supprimer le modèle"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
        )
        confirmer = dlg.ShowModal() == wx.ID_YES
        dlg.Destroy()
        if not confirmer:
            return
        try:
            from Utils import UTILS_Convention_modeles
            UTILS_Convention_modeles.SupprimerModele(IDmodele)
            self.RafraichirModeles(selectionPremier=True)
        except Exception as err:
            self._Informer(_(u"Le modèle n'a pas pu être supprimé.\n\n%s") % err, erreur=True)

    def OnInstallerModelesExemples(self, event=None):
        IDselection = self.GetIDmodele()
        try:
            from Utils import UTILS_Convention_modeles
            IDs = UTILS_Convention_modeles.InstallerModelesExemples()
            self.RafraichirModeles(IDmodele=IDselection, selectionPremier=True)
            self._Informer(
                _(u"Les modèles d'exemple embarqués sont disponibles, y compris le modèle scolaire.\n\n"
                  u"Un modèle déjà présent n'a pas été écrasé.")
            )
        except Exception as err:
            self._Informer(_(u"Les modèles d'exemple n'ont pas pu être installés.\n\n%s") % err, erreur=True)

    # ------------------------------------------------------------------
    # Rafraîchissement des valeurs automatiques (représentant, tarif)
    # ------------------------------------------------------------------

    def OnSelection(self):
        """ Appelée par CTRL_Grille_periode.MyDatePickerCtrl.OnDateChanged
        lorsque l'utilisateur change une date : les dates de début/fin
        étant des enfants directs de ce dialogue, elles utilisent son
        parent (donc self) comme cible de rappel. Un changement de
        période peut changer le tarif horaire détectable (le
        représentant, lui, ne dépend pas de la période). """
        self.RecalculerValeursAutomatiques()

    def RecalculerValeursAutomatiques(self):
        """ Recalcule le représentant et le tarif horaire automatiques
        pour la période actuellement sélectionnée, et met à jour les
        champs correspondants -- SAUF si l'utilisateur les a déjà
        corrigés manuellement (la valeur affichée ne correspond plus à
        la dernière valeur automatique connue). Ne modifie jamais aucune
        donnée Noethys : lecture seule. """
        if self.IDfamille is None:
            return
        try:
            from Utils import UTILS_Convention_champs as CC
            champs, _donnees = CC.GetChampsConvention(
                IDfamille=self.IDfamille,
                date_debut=str(self.ctrl_date_debut.GetDate()),
                date_fin=str(self.ctrl_date_fin.GetDate()),
            )
        except Exception:
            # Lecture seule, best-effort : une erreur ici ne doit jamais
            # empêcher l'utilisateur de continuer à saisir manuellement.
            return

        nouveau_representant = champs.get("{CONVENTION_REPRESENTANT_NOM_COMPLET}") or u""
        valeurActuelle = self.ctrl_representant_nom_complet.GetValue().strip()
        if valeurActuelle in (u"", self._auto_representant):
            self.ctrl_representant_nom_complet.SetValue(nouveau_representant)
        self._auto_representant = nouveau_representant

        def MajTarif(ctrl, attribut, code):
            tarif = champs.get(code)
            nouveau = (u"%.2f" % tarif) if isinstance(tarif, (int, float)) else u""
            valeurActuelle = ctrl.GetValue().strip()
            precedente = getattr(self, attribut)
            if valeurActuelle in (u"", precedente):
                ctrl.SetValue(nouveau)
            setattr(self, attribut, nouveau)
        MajTarif(self.ctrl_tarif_horaire, "_auto_tarif", "{CONVENTION_TARIF_HORAIRE}")
        MajTarif(self.ctrl_tarif_adulte, "_auto_tarif_adulte", "{CONVENTION_TARIF_ADULTE}")
        MajTarif(self.ctrl_tarif_enfant, "_auto_tarif_enfant", "{CONVENTION_TARIF_ENFANT}")
        for label, code in (
            (self.label_tarif_horaire_provenance, "{CONVENTION_TARIF_HORAIRE_PROVENANCE}"),
            (self.label_tarif_adulte_provenance, "{CONVENTION_TARIF_ADULTE_PROVENANCE}"),
            (self.label_tarif_enfant_provenance, "{CONVENTION_TARIF_ENFANT_PROVENANCE}"),
        ):
            label.SetLabel(champs.get(code) or u"")
            label.Wrap(390)

    # ------------------------------------------------------------------
    # Planning séparé (moteur Réservations historique, inchangé)
    # ------------------------------------------------------------------

    def OnBoutonPlanning(self, event):
        """ Génère le Planning séparé pour la même famille et la même
        période que la Convention en cours de préparation. Ne ferme pas
        le dialogue : l'utilisateur peut ensuite toujours générer la
        Convention. Deux documents PDF distincts, aucune fusion. """
        if self.IDfamille is None:
            return
        from Utils import UTILS_Convention_champs as CC
        from Utils import UTILS_Impression_reservations as RESA

        date_debut = str(self.ctrl_date_debut.GetDate())
        date_fin = str(self.ctrl_date_fin.GetDate())
        try:
            listeIDindividus = CC.GetIndividusRattaches(self.IDfamille)
            dictDonnees = RESA.GetDonnees(
                listeIDindividus=listeIDindividus, date_debut=date_debut, date_fin=date_fin,
            )
            if not dictDonnees:
                dlg = wx.MessageDialog(
                    self, _(u"Aucune donnée de planning trouvée pour cette période."),
                    _(u"Planning"), wx.OK | wx.ICON_INFORMATION,
                )
                dlg.ShowModal()
                dlg.Destroy()
                return
            choix = wx.SingleChoiceDialog(
                self, _(u"Présentation du planning :"), _(u"Imprimer le planning"),
                [_(u"Détail des séances"), _(u"Synthèse : heures et coût par activité")])
            try:
                if choix.ShowModal() != wx.ID_OK:
                    return
                synthese = choix.GetSelection() == 1
            finally:
                choix.Destroy()
            if synthese:
                RESA.Impression(dictDonnees, synthese=True)
            else:
                RESA.Impression(dictDonnees)
        except Exception as err:
            dlg = wx.MessageDialog(
                self, _(u"Impossible de générer le planning.\n\n%s") % err,
                _(u"Planning"), wx.OK | wx.ICON_ERROR,
            )
            dlg.ShowModal()
            dlg.Destroy()

    # ------------------------------------------------------------------
    # Modèle mal encodé : récupération par copie propre d'un modèle fourni
    # ------------------------------------------------------------------

    def OnBoutonOk(self, event):
        """ Avant de fermer, vérifie que le modèle choisi n'a pas été
        enregistré avec un mauvais encodage (ancien import Windows) : la
        génération serait de toute façon refusée par
        UTILS_Impression_convention._ValideEncodageModele. Dans ce cas, le
        dialogue reste ouvert (saisies conservées) et propose d'installer
        une copie propre d'un modèle fourni. """
        if hasattr(self, "ctrl_format") and self.ctrl_format.GetSelection() == 1:
            import os
            path = self.GetModeleWord()
            if not path or not path.lower().endswith(".docx") or not os.path.isfile(path):
                self._Informer(_(u"Choisissez un modèle Word au format .docx."), erreur=True)
                return
            self.EndModal(wx.ID_OK)
            return
        IDmodele = self.GetIDmodele()
        if IDmodele is not None:
            from Utils import UTILS_Export_documents
            try:
                suspects = UTILS_Export_documents.GetObjetsMalEncodes(IDmodele)
            except Exception:
                # Best-effort : la validation de génération reste le garde-fou.
                suspects = []
            if suspects:
                self.ProposerCopiePropre(IDmodele, suspects)
                return
        self.EndModal(wx.ID_OK)

    def ProposerCopiePropre(self, IDmodele, suspects):
        """ Ne modifie ni ne supprime jamais le modèle IDmodele : installe
        seulement, après confirmation, une copie propre du modèle fourni
        choisi par l'utilisateur, puis la sélectionne. """
        from Utils import UTILS_Export_documents
        nomModele = self.ctrl_modele.GetStringSelection()
        exemples = UTILS_Export_documents.GetModelesExemplesConvention()
        if not exemples:
            self._Informer(_(u"Le modèle « %s » semble avoir été enregistré avec un mauvais encodage "
                             u"(%s), et aucun modèle fourni n'est disponible pour le remplacer.")
                           % (nomModele, u", ".join(suspects)), erreur=True)
            return

        fichierCorrespondant = UTILS_Export_documents.TrouverModeleExempleCorrespondant(IDmodele)
        selection = -1
        for index, exemple in enumerate(exemples):
            if exemple["fichier"] == fichierCorrespondant:
                selection = index
        message = _(
            u"Le modèle « %s » semble avoir été enregistré avec un mauvais encodage "
            u"(textes concernés : %s).\n\n"
            u"Une copie propre du modèle fourni peut être installée sans modifier l'original. "
            u"Elle reprend le texte d'origine du modèle fourni : vos éventuelles "
            u"personnalisations du modèle actuel n'y figureront pas.\n\n"
            u"Choisissez le modèle fourni à installer :"
        ) % (nomModele, u", ".join(suspects))
        index = self._DemanderModeleExemple(message, [e["nom"] for e in exemples], selection)
        if index is None:
            return

        try:
            IDcopie, nomCopie, cree = UTILS_Export_documents.InstallerCopiePropreModeleExemple(
                exemples[index]["fichier"])
        except Exception as err:
            self._Informer(_(u"La copie propre n'a pas pu être installée.\n\n%s") % err, erreur=True)
            return

        self.ctrl_modele.MAJ()
        self.ctrl_modele.SetID(IDcopie)
        if cree:
            debut = _(u"La copie propre « %s » a été installée et sélectionnée.") % nomCopie
        else:
            debut = _(u"Le modèle propre « %s », déjà installé, a été sélectionné.") % nomCopie
        self._Informer(debut + u"\n\n" + _(
            u"Le modèle d'origine « %s » n'a pas été modifié : vous pouvez désormais le gérer "
            u"directement avec le bouton « Gérer les modèles... ».\n\n"
            u"Vérifiez les informations puis cliquez à nouveau sur « Générer la convention »."
        ) % nomModele)

    def _DemanderModeleExemple(self, message, noms, selection):
        """ Renvoie l'index choisi, ou None si l'utilisateur annule. """
        dlg = wx.SingleChoiceDialog(self, message, _(u"Modèle mal encodé"), noms, wx.CHOICEDLG_STYLE)
        if selection >= 0:
            dlg.SetSelection(selection)
        index = dlg.GetSelection() if dlg.ShowModal() == wx.ID_OK else None
        dlg.Destroy()
        return index

    def _Informer(self, message, erreur=False):
        dlg = wx.MessageDialog(self, message, _(u"Convention"),
                               wx.OK | (wx.ICON_ERROR if erreur else wx.ICON_INFORMATION))
        dlg.ShowModal()
        dlg.Destroy()

    # ------------------------------------------------------------------
    # Accesseurs
    # ------------------------------------------------------------------

    def GetIDmodele(self):
        return self.ctrl_modele.GetID()

    def GetDateDebut(self):
        return self.ctrl_date_debut.GetDate()

    def GetDateFin(self):
        return self.ctrl_date_fin.GetDate()

    def GetSaison(self):
        return self.ctrl_saison.GetValue().strip() or None

    def GetOverrides(self):
        """ Dict {"{CODE}": valeur} à transmettre tel quel à
        UTILS_Impression_convention.Impression(overrides=...). Reflète
        exactement ce qui est affiché dans le dialogue (valeur
        automatique non touchée, ou correction manuelle de
        l'utilisateur) : jamais écrit dans Noethys, seulement utilisé
        pour la génération de ce PDF. """
        overrides = {
            "{CONVENTION_REPRESENTANT_NOM_COMPLET}": self.ctrl_representant_nom_complet.GetValue().strip(),
            "{CONVENTION_REPRESENTANT_FONCTION}": self.ctrl_representant_fonction.GetValue().strip(),
            "{CONVENTION_DATE_SIGNATURE}": self.ctrl_date_signature.GetDate().strftime("%d/%m/%Y"),
            "{CONVENTION_LIEU_SIGNATURE}": self.ctrl_lieu_signature.GetValue().strip(),
        }
        for code, ctrl in (
            ("{CONVENTION_TARIF_HORAIRE}", self.ctrl_tarif_horaire),
            ("{CONVENTION_TARIF_ADULTE}", self.ctrl_tarif_adulte),
            ("{CONVENTION_TARIF_ENFANT}", self.ctrl_tarif_enfant),
        ):
            tarif_saisi = ctrl.GetValue().strip().replace(",", ".")
            if tarif_saisi:
                try:
                    overrides[code] = float(tarif_saisi)
                except ValueError:
                    pass
        return overrides
