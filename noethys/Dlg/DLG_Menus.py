#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Auteur:          Ivan LUCAS
# Copyright:       (c) 2010-18 Ivan LUCAS
# Licence:         Licence GNU GPL
#------------------------------------------------------------------------


import Chemins
from Utils import UTILS_Adaptations
from Utils.UTILS_Traduction import _
import wx
from Ctrl import CTRL_Bouton_image
import datetime
import calendar
import GestionDB
from Utils import UTILS_Dialogs
from Utils import UTILS_Images
from Ctrl import CTRL_Menus
from Ctrl import CTRL_Bandeau


class CTRL_Restaurateur(wx.Choice):
    def __init__(self, parent):
        wx.Choice.__init__(self, parent, -1)
        self.parent = parent
        self.MAJlisteDonnees()

    def MAJlisteDonnees(self):
        self.SetItems(self.GetListeDonnees())
        if len(self.GetListeDonnees()) > 0 :
            self.Select(0)
            self.Enable(True)
        else :
            self.Enable(False)

    def GetListeDonnees(self):
        db = GestionDB.DB()
        req = """SELECT IDrestaurateur, nom
        FROM restaurateurs
        ORDER BY nom;"""
        db.ExecuterReq(req)
        listeDonnees = db.ResultatReq()
        db.Close()
        listeItems = []
        self.dictDonnees = {}
        index = 0
        for IDrestaurateur, nom in listeDonnees:
            self.dictDonnees[index] = {"ID": IDrestaurateur}
            listeItems.append(nom)
            index += 1
        return listeItems

    def SetID(self, ID=0):
        for index, values in self.dictDonnees.items():
            if values["ID"] == ID:
                self.SetSelection(index)

    def GetID(self):
        index = self.GetSelection()
        if index == -1: return None
        return self.dictDonnees[index]["ID"]


class CibleFichierOceane(wx.FileDropTarget):
    """Déposer un XLSX lance uniquement la prévisualisation, jamais un import."""

    def __init__(self, parent):
        wx.FileDropTarget.__init__(self)
        self.parent = parent

    def OnDropFiles(self, x, y, fichiers):
        if len(fichiers) != 1 or not fichiers[0].lower().endswith(".xlsx"):
            wx.MessageBox(
                _(u"Déposez un unique classeur Excel .xlsx d'Océane."),
                _(u"Fichier de menus invalide"),
                wx.OK | wx.ICON_WARNING, self.parent)
            return False
        # La fenêtre doit s'ouvrir après la fin de l'événement de dépôt.
        wx.CallAfter(self.parent.OnImporterOceane, None, fichiers[0])
        return True


class Dialog(wx.Dialog):
    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, -1, name="DLG_Menus", style=wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER|wx.MAXIMIZE_BOX|wx.MINIMIZE_BOX)
        self.parent = parent

        # Bandeau
        intro = _(u"Vous pouvez ici saisir les menus de votre restaurateur. Sélectionnez un restaurateur et un mois puis double-cliquez sur une case pour saisir un menu. Vous pouvez paramétrer un restaurateur en cliquant sur le bouton 'Gestion des restaurateurs' à droite de la liste déroulante. N'oubliez pas de paramétrer également les catégories de repas depuis le menu Paramétrage > Restauration.")
        titre = _(u"Gestion des menus")
        self.SetTitle(titre)
        self.ctrl_bandeau = CTRL_Bandeau.Bandeau(self, titre=titre, texte=intro, hauteurHtml=30, nomImage="Images/32x32/Menu.png")

        # Selection période
        self.staticbox_periode_staticbox = wx.StaticBox(self, -1, _(u"Période"))
        self.label_mois = wx.StaticText(self, -1, _(u"Mois :"))
        self.ctrl_mois = wx.Choice(self, -1, choices=[_(u"Janvier"), _(u"Février"), _(u"Mars"), _(u"Avril"), _(u"Mai"), _(u"Juin"), _(u"Juillet"), _(u"Août"), _(u"Septembre"), _(u"Octobre"), _(u"Novembre"), _(u"Décembre")])
        self.spin_mois = wx.SpinButton(self, -1, size=(18, 20),  style=wx.SP_VERTICAL)
        self.spin_mois.SetRange(-1, 1)
        self.label_annee = wx.StaticText(self, -1, _(u"Année :"))
        self.ctrl_annee = wx.SpinCtrl(self, -1, "", min=1977, max=2999)
        dateDuJour = datetime.date.today()
        self.ctrl_annee.SetValue(dateDuJour.year)
        self.ctrl_mois.SetSelection(dateDuJour.month-1)

        # Restaurateur
        self.staticbox_restaurateur_staticbox = wx.StaticBox(self, -1, _(u"Restaurateur"))
        self.label_restaurateur = wx.StaticText(self, -1, _(u"Restaurateur :"))
        self.ctrl_restaurateur = CTRL_Restaurateur(self)
        self.bouton_restaurateur = wx.BitmapButton(self, -1, wx.Bitmap(Chemins.GetStaticPath(u"Images/16x16/Mecanisme.png"), wx.BITMAP_TYPE_ANY))

        # Menus
        self.box_menus_staticbox = wx.StaticBox(self, wx.ID_ANY, _(u"Menus"))
        self.ctrl_menus = CTRL_Menus.CTRL(self)
        self.ctrl_menus.SetMinSize((100, 380))

        # Légende
        self.listeLegende = [
            {"label": _(u"Cases avec contenu"), "couleur": CTRL_Menus.COULEUR_CASES_OUVERTES, "ctrl_label": None, "ctrl_img": None},
            {"label": _(u"Cases vides"), "couleur": CTRL_Menus.COULEUR_CASES_FERMEES, "ctrl_label": None, "ctrl_img": None},
            ]
        index = 0
        for dictTemp in self.listeLegende :
            img = wx.StaticBitmap(self, -1, UTILS_Images.CreationCarreCouleur(12, 12, dictTemp["couleur"], contour=True))
            label = wx.StaticText(self, -1, dictTemp["label"])
            label.SetFont(wx.Font(8, wx.SWISS, wx.NORMAL, wx.NORMAL))
            self.listeLegende[index]["ctrl_img"] = img
            self.listeLegende[index]["ctrl_label"] = label
            index += 1

        self.image_info = wx.StaticBitmap(self, -1, wx.Bitmap(Chemins.GetStaticPath(u"Images/16x16/Astuce.png"), wx.BITMAP_TYPE_ANY))
        self.label_info = wx.StaticText(self, -1, _(u"Double-cliquez pour modifier ou faites un clic droit pour ouvrir le menu contextuel ou utilisez le copier-coller (Ctrl+C puis Ctrl+V)"))
        self.label_info.SetFont(wx.Font(8, wx.SWISS, wx.NORMAL, wx.NORMAL))

        # Boutons
        self.bouton_aide = CTRL_Bouton_image.CTRL(self, texte=_(u"Aide"), cheminImage="Images/32x32/Aide.png")
        self.bouton_imprimer = CTRL_Bouton_image.CTRL(self, texte=_(u"Imprimer"), cheminImage="Images/32x32/Imprimante.png")
        self.bouton_import_oceane = wx.Button(
            self, wx.ID_ANY, _(u"Importer menus Océane (ou déposer XLSX)..."))
        self.bouton_import_oceane.SetDropTarget(CibleFichierOceane(self))
        self.bouton_fermer = CTRL_Bouton_image.CTRL(self, texte=_(u"Fermer"), cheminImage="Images/32x32/Annuler.png")

        self.__set_properties()
        self.__do_layout()

        self.Bind(wx.EVT_SPIN, self.OnSpinMois, self.spin_mois)
        self.Bind(wx.EVT_CHOICE, self.MAJ, self.ctrl_mois)
        self.Bind(wx.EVT_SPINCTRL, self.MAJ, self.ctrl_annee)
        self.Bind(wx.EVT_CHOICE, self.MAJ, self.ctrl_restaurateur)
        self.Bind(wx.EVT_BUTTON, self.OnBoutonRestaurateur, self.bouton_restaurateur)
        self.Bind(wx.EVT_BUTTON, self.OnBoutonAide, self.bouton_aide)
        self.Bind(wx.EVT_BUTTON, self.Imprimer, self.bouton_imprimer)
        self.Bind(wx.EVT_BUTTON, self.OnImporterOceane, self.bouton_import_oceane)
        self.Bind(wx.EVT_BUTTON, self.OnBoutonFermer, self.bouton_fermer)
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        # Init
        self.MAJ()

    def __set_properties(self):
        self.ctrl_mois.SetToolTip(wx.ToolTip(_(u"Sélectionnez un mois")))
        self.ctrl_annee.SetMinSize((70, -1))
        self.ctrl_annee.SetToolTip(wx.ToolTip(_(u"Sélectionnez une année")))
        self.bouton_restaurateur.SetToolTip(wx.ToolTip(_(u"Cliquez ici pour accéder à la gestion des restaurateurs")))
        self.bouton_aide.SetToolTip(wx.ToolTip(_(u"Cliquez ici pour obtenir de l'aide")))
        self.bouton_imprimer.SetToolTip(wx.ToolTip(_(u"Cliquez ici pour imprimer la commande au format PDF")))
        self.bouton_import_oceane.SetToolTip(wx.ToolTip(
            _(u"Choisir un Excel Océane, vérifier les menus, les enregistrer "
              u"puis préparer un bloc du portail famille")))
        self.bouton_fermer.SetToolTip(wx.ToolTip(_(u"Cliquez ici pour fermer")))

    def __do_layout(self):
        grid_sizer_base = wx.FlexGridSizer(rows=4, cols=1, vgap=10, hgap=10)
        grid_sizer_base.Add(self.ctrl_bandeau, 0, wx.EXPAND, 0)

        grid_sizer_haut = wx.FlexGridSizer(rows=1, cols=3, vgap=10, hgap=10)

        # Selection Mois
        staticbox_periode = wx.StaticBoxSizer(self.staticbox_periode_staticbox, wx.VERTICAL)
        grid_sizer_periode = wx.FlexGridSizer(rows=1, cols=5, vgap=0, hgap=0)
        grid_sizer_periode.Add(self.label_mois, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_periode.Add(self.ctrl_mois, 0, wx.LEFT, 5)
        grid_sizer_periode.Add(self.spin_mois, 0, wx.EXPAND, 0)
        grid_sizer_periode.Add(self.label_annee, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        grid_sizer_periode.Add(self.ctrl_annee, 0, wx.LEFT, 5)
        staticbox_periode.Add(grid_sizer_periode, 1, wx.ALL | wx.EXPAND, 10)
        grid_sizer_haut.Add(staticbox_periode, 1, wx.EXPAND, 0)

        # Restaurateur
        box_restaurateur = wx.StaticBoxSizer(self.staticbox_restaurateur_staticbox, wx.HORIZONTAL)
        grid_sizer_restaurateur = wx.FlexGridSizer(rows=1, cols=3, vgap=5, hgap=5)
        grid_sizer_restaurateur.Add(self.label_restaurateur, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_restaurateur.Add(self.ctrl_restaurateur, 1, wx.EXPAND)
        grid_sizer_restaurateur.Add(self.bouton_restaurateur, 0, 0, 0)
        grid_sizer_restaurateur.AddGrowableCol(1)
        box_restaurateur.Add(grid_sizer_restaurateur, 1, wx.ALL | wx.EXPAND, 10)
        grid_sizer_haut.Add(box_restaurateur, 1, wx.EXPAND, 0)

        grid_sizer_haut.AddGrowableCol(1)

        grid_sizer_base.Add(grid_sizer_haut, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)

        # Menus
        box_menus = wx.StaticBoxSizer(self.box_menus_staticbox, wx.VERTICAL)
        grid_sizer_menus = wx.FlexGridSizer(rows=2, cols=1, vgap=5, hgap=5)
        grid_sizer_menus.Add(self.ctrl_menus, 1, wx.EXPAND, 0)

        # Légende
        grid_sizer_legende = wx.FlexGridSizer(rows=1, cols=len(self.listeLegende)*3 + 3, vgap=4, hgap=4)

        grid_sizer_legende.Add(self.image_info, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_legende.Add(self.label_info, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        for dictTemp in self.listeLegende :
            grid_sizer_legende.Add((5, 5), 0, 0, 0)
            grid_sizer_legende.Add(dictTemp["ctrl_img"], 0, wx.ALIGN_CENTER_VERTICAL, 0)
            grid_sizer_legende.Add(dictTemp["ctrl_label"], 0, wx.ALIGN_CENTER_VERTICAL, 0)

        grid_sizer_legende.AddGrowableCol(2)
        grid_sizer_menus.Add(grid_sizer_legende, 1, wx.ALIGN_CENTER_VERTICAL|wx.EXPAND, 0)

        grid_sizer_menus.AddGrowableRow(0)
        grid_sizer_menus.AddGrowableCol(0)
        box_menus.Add(grid_sizer_menus, 1, wx.ALL | wx.EXPAND, 10)
        grid_sizer_base.Add(box_menus, 0, wx.LEFT|wx.RIGHT|wx.EXPAND, 10)

        grid_sizer_base.AddGrowableCol(0)
        grid_sizer_base.AddGrowableRow(2)

        # Boutons
        grid_sizer_boutons = wx.FlexGridSizer(rows=1, cols=5, vgap=10, hgap=10)
        grid_sizer_boutons.Add(self.bouton_aide, 0, 0, 0)
        grid_sizer_boutons.Add(self.bouton_imprimer, 0, 0, 0)
        grid_sizer_boutons.Add(self.bouton_import_oceane, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_boutons.Add((20, 20), 0, wx.EXPAND, 0)
        grid_sizer_boutons.Add(self.bouton_fermer, 0, 0, 0)
        grid_sizer_boutons.AddGrowableCol(3)
        grid_sizer_base.Add(grid_sizer_boutons, 1, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND, 10)

        self.SetSizer(grid_sizer_base)
        grid_sizer_base.Fit(self)
        self.Layout()
        self.SetMinSize(self.GetSize())
        UTILS_Dialogs.AjusteSizePerso(self, __file__)
        self.CenterOnScreen()

    def OnSpinMois(self, event):
        x = event.GetPosition()
        mois = self.ctrl_mois.GetSelection()+x
        if mois != -1 and mois < 12 :
            self.ctrl_mois.SetSelection(mois)
            self.MAJ()
        self.spin_mois.SetValue(0)

    def OnBoutonRestaurateur(self, event):
        IDrestaurateur = self.ctrl_restaurateur.GetID()
        from Dlg import DLG_Restaurateurs
        dlg = DLG_Restaurateurs.Dialog(self)
        dlg.ShowModal()
        dlg.Destroy()
        self.ctrl_restaurateur.MAJlisteDonnees()
        self.ctrl_restaurateur.SetID(IDrestaurateur)
        self.MAJ()

    def OnBoutonAide(self, event): 
        from Utils import UTILS_Aide
        UTILS_Aide.Aide("Menusdesrepas")

    def GetPeriode(self):
        return {"mois" : self.ctrl_mois.GetSelection()+1, "annee" : self.ctrl_annee.GetValue()}

    def MAJ(self, event=None):
        periode = self.GetPeriode()
        IDrestaurateur = self.ctrl_restaurateur.GetID()
        self.ctrl_menus.MAJ(periode=periode, IDrestaurateur=IDrestaurateur)

    def OnClose(self, event):
        UTILS_Dialogs.SaveSizePerso(self, __file__)
        event.Skip()

    def OnBoutonFermer(self, event):
        UTILS_Dialogs.SaveSizePerso(self, __file__)
        self.EndModal(wx.ID_CANCEL)

    def OnImporterOceane(self, event=None, fichier=None):
        """Import autonome des menus et préparation facultative du portail.

        Import uniquement dans les tables natives menus/menus_categories après
        vérification et accord explicites. Aucune commande fournisseur.
        """
        from Utils import UTILS_Repas_oceane_menus as lecture
        from Utils import UTILS_Repas_oceane_publication as publication
        from Utils import UTILS_Repas_oceane_import_db as import_db

        restaurateur = self.ctrl_restaurateur.GetID()
        if restaurateur is None:
            wx.MessageBox(
                _(u"Choisissez d'abord le restaurateur Océane dans Noethys."),
                _(u"Import des menus"), wx.OK | wx.ICON_WARNING, self)
            return False

        if fichier is None:
            dlg = wx.FileDialog(
                self, _(u"Choisissez le classeur de menus reçu d'Océane"),
                wildcard=u"Classeur Excel (*.xlsx)|*.xlsx",
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
            try:
                if dlg.ShowModal() != wx.ID_OK:
                    return False
                chemin = dlg.GetPath()
            finally:
                dlg.Destroy()
        else:
            chemin = fichier
        try:
            menus = lecture.ChargerMenus(chemin)
        except (ValueError, OSError, KeyError) as exc:
            wx.MessageBox(
                _(u"Import Excel Océane refusé : %s") % exc,
                _(u"Menus Océane"), wx.OK | wx.ICON_WARNING, self)
            return False

        dates = sorted(menus)
        choix = [u"%s — %s" % (
            jour.strftime("%d/%m/%Y"),
            " / ".join((menus[jour].get("plat") or
                        menus[jour].get("entree") or [u"Menu à vérifier"]))[:100])
            for jour in dates]
        dlg = wx.MultiChoiceDialog(
            self, _(u"Sélectionnez uniquement les mercredis à importer "
                    u"et éventuellement publier :"),
            _(u"Menus Océane"), choix)
        try:
            prochains = [i for i, jour in enumerate(dates)
                         if jour >= datetime.date.today()][:8]
            if prochains:
                dlg.SetSelections(prochains)
            if dlg.ShowModal() != wx.ID_OK:
                return False
            selection = [dates[i] for i in dlg.GetSelections()]
        finally:
            dlg.Destroy()
        if not selection:
            wx.MessageBox(_(u"Aucun mercredi sélectionné."),
                          _(u"Menus Océane"), wx.OK | wx.ICON_WARNING, self)
            return False
        try:
            retenus = publication.PreparerMenus(menus, selection)
        except ValueError as exc:
            wx.MessageBox(str(exc), _(u"Menus Océane"),
                          wx.OK | wx.ICON_WARNING, self)
            return False

        # Prévol sans aucune écriture en base ni publication.
        DB = GestionDB.DB()
        try:
            plan = import_db.LireEtat(DB, restaurateur, retenus)
        except Exception as exc:
            wx.MessageBox(_(u"Contrôle des menus impossible : %s") % exc,
                          _(u"Menus Océane"), wx.OK | wx.ICON_WARNING, self)
            return False
        finally:
            DB.Close()
        if plan["conflits"]:
            txt = "\n".join(
                u"%s : %s" % (jour.strftime("%d/%m/%Y"),
                              publication.LIBELLES[cle])
                for cle, jour, ancien, nouveau in plan["conflits"][:8])
            wx.MessageBox(
                _(u"%d valeurs diffèrent de menus déjà saisis dans Noethys. "
                  u"Aucune donnée existante ne sera écrasée :\n%s") %
                  (len(plan["conflits"]), txt),
                _(u"Conflit de menus"), wx.OK | wx.ICON_WARNING, self)
            return False

        apercu = publication.TextePortail(retenus)
        texte = _(u"%d mercredis sélectionnés\n"
                  u"%d valeurs à ajouter, %d déjà identiques, %d catégories à créer.\n"
                  u"\nAperçu :\n%s\n\n"
                  u"Importer ces menus dans les données de restauration de Noethys ?") % (
                      len(retenus), len(plan["ajouter"]),
                      len(plan["identiques"]), len(plan["creer_categories"]),
                      apercu[:4000])
        accord = wx.MessageBox(
            texte, _(u"Contrôle des menus Océane"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self)
        if accord != wx.YES:
            return False

        DB = GestionDB.DB()
        try:
            bilan = import_db.Enregistrer(DB, restaurateur, retenus)
        except Exception as exc:
            wx.MessageBox(_(u"Enregistrement des menus refusé : %s") % exc,
                          _(u"Menus Océane"), wx.OK | wx.ICON_ERROR, self)
            return False
        finally:
            DB.Close()
        self.MAJ()
        choix = wx.MessageBox(
            _(u"%d menus enregistrés, %d valeurs déjà identiques.\n"
              u"Voulez-vous aussi préparer leur publication sur le portail famille ?\n"
              u"La publication sera vérifiée dans l'éditeur de blocs "
              u"et ne déclenchera pas de synchronisation automatique.") %
              (bilan["ajoutes"], bilan["identiques"]),
            _(u"Publication des menus Océane"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self)
        if choix == wx.YES:
            return self._PreparerPublicationOceane(retenus)
        return True

    def _PreparerPublicationOceane(self, menus):
        """Préremplit le vrai bloc Blog Connecthys et laisse l'opérateur sauver."""
        from Dlg import DLG_Saisie_portail_bloc
        from Ctrl import CTRL_Editeur_email
        from Utils import UTILS_Repas_oceane_publication as P
        from Utils import UTILS_Parametres

        titre = P.TitrePortail(menus)
        DB = GestionDB.DB()
        try:
            DB.cursor.execute(
                "SELECT IDbloc, titre FROM portail_blocs WHERE categorie=" +
                ("%s" if DB.isNetwork else "?"),
                ("bloc_blog",))
            doublon = any(t == titre for _ident, t in DB.cursor.fetchall())
            DB.cursor.execute("SELECT IDpage FROM portail_pages")
            pages = DB.cursor.fetchall()
        except Exception as exc:
            wx.MessageBox(str(exc), _(u"Portail famille"),
                          wx.OK | wx.ICON_WARNING, self)
            return False
        finally:
            DB.Close()
        if doublon:
            wx.MessageBox(
                _(u"Un bloc du portail porte déjà ce titre. Ouvrez-le dans "
                  u"la configuration du portail pour éviter une publication "
                  u"en double."),
                _(u"Publication déjà préparée"),
                wx.OK | wx.ICON_WARNING, self)
            return False
        if not pages:
            wx.MessageBox(
                _(u"Créez d'abord une page dans la configuration du "
                  u"portail famille Connecthys."),
                _(u"Portail non configuré"), wx.OK | wx.ICON_WARNING, self)
            return False

        # L'éditeur natif est utilisé pour un XML RichText rouvrable.
        # Le HTML public est construit séparément avec échappement strict.
        dlg = DLG_Saisie_portail_bloc.Dialog(self, IDbloc=None)
        editeur = None
        try:
            dlg.ctrl_titre.SetValue(titre)
            dlg.ctrl_parametres.SetPageByCode("bloc_blog")
            editeur = CTRL_Editeur_email.Editeur(dlg)
            editeur.Hide()
            editeur.WriteText(P.TextePortail(menus))
            donnees = [{
                "IDelement": None,
                "titre": titre,
                "date_debut": datetime.datetime.now(),
                "date_fin": P.DateFinPublication(menus),
                "texte_xml": editeur.GetXML(),
                "texte_html": P.HTMLPortail(menus).encode("utf-8"),
                "parametres": None,
            }]
            dlg.ctrl_parametres.GetPageByCode(
                "bloc_blog").ctrl_elements.SetDonnees(donnees)
            resultat = dlg.ShowModal()
        finally:
            if editeur is not None:
                editeur.Destroy()
            dlg.Destroy()
        if resultat != wx.ID_OK:
            return False
        UTILS_Parametres.Parametres(
            mode="set", categorie="portail", nom="last_update_pages",
            valeur=str(datetime.datetime.now()))
        wx.MessageBox(
            _(u"Bloc de menus enregistré dans les pages du portail. "
              u"Vérifiez-le puis lancez la synchronisation habituelle "
              u"de Connecthys pour le rendre visible aux familles."),
            _(u"Menus préparés pour le portail"),
            wx.OK | wx.ICON_INFORMATION, self)
        return True

    def Imprimer(self, event=None):
        if self.ctrl_restaurateur.GetID() == None :
            dlg = wx.MessageDialog(self, _(u"Vous devez d'abord sélectionner un restaurateur dans la liste !"), _(u"Avertissement"), wx.OK | wx.ICON_EXCLAMATION)
            dlg.ShowModal()
            dlg.Destroy()
            return False

        # Récupération des dates extrêmes affichées
        annee = self.ctrl_annee.GetValue()
        mois = self.ctrl_mois.GetSelection()+1
        tmp, nbreJours = calendar.monthrange(annee, mois)
        date_min = datetime.date(annee, mois, 1)
        date_max = datetime.date(annee, mois, nbreJours)
        periode = (date_min, date_max)

        # Ouvre la fenêtre des options
        from Dlg import DLG_Options_impression_menu
        dlg = DLG_Options_impression_menu.Dialog(self, periode=periode, IDrestaurateur=self.ctrl_restaurateur.GetID())
        if dlg.ShowModal() == wx.ID_OK:
            dlg.Destroy()
        else :
            dlg.Destroy()
            return





if __name__ == u"__main__":
    app = wx.App(0)
    #wx.InitAllImageHandlers()
    dialog_1 = Dialog(None)
    app.SetTopWindow(dialog_1)
    dialog_1.ShowModal()
    app.MainLoop()
