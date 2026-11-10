#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Auteur:           Ivan LUCAS
# Copyright:       (c) 2010-11 Ivan LUCAS
# Licence:         Licence GNU GPL
#------------------------------------------------------------------------


import Chemins
from Utils import UTILS_Adaptations
from Utils.UTILS_Traduction import _
import wx
from Ctrl import CTRL_Bouton_image
import datetime
import GestionDB
from Ctrl import CTRL_Bandeau

from Dlg.DLG_Factures_generation_parametres import Panel as Page1
from Dlg.DLG_Factures_generation_selection import Panel as Page2
from Dlg.DLG_Factures_generation_actions import Panel as Page3


class Dialog(wx.Dialog):
    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, -1, name="DLG_Facturation", style=wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER|wx.MAXIMIZE_BOX|wx.MINIMIZE_BOX)
        self.parent = parent
        
        intro = _(u"Vous pouvez ici générer des factures. Page 1 : Sélectionnez des paramètres puis cliquez sur Suite pour afficher les factures disponibles. Page 2 : Cochez les factures à générer puis cliquez sur Suite. Page 3 : Vous pouvez effectuer d'autres actions sur les factures générées.")
        titre = _(u"Génération de factures")
        self.SetTitle(titre)
        self.ctrl_bandeau = CTRL_Bandeau.Bandeau(self, titre=titre, texte=intro, hauteurHtml=30, nomImage="Images/32x32/Generation.png")
        
        self.listePages = ("Page1", "Page2", "Page3")
        self.nbrePages = len(self.listePages)

        self.static_line = wx.StaticLine(self, -1)
        
        self.bouton_aide = CTRL_Bouton_image.CTRL(self, texte=_(u"Aide"), cheminImage="Images/32x32/Aide.png")
        self.bouton_retour = CTRL_Bouton_image.CTRL(self, texte=_(u"Retour"), cheminImage="Images/32x32/Fleche_gauche.png")
        self.bouton_suite = CTRL_Bouton_image.CTRL(self, texte=_(u"Suite"), cheminImage="Images/32x32/Fleche_droite.png", margesImage=(0, 0, 4, 0), positionImage=wx.RIGHT)
        self.bouton_annuler = CTRL_Bouton_image.CTRL(self, id=wx.ID_CANCEL, texte=_(u"Annuler"), cheminImage="Images/32x32/Annuler.png")
        
        self.__set_properties()
        self.__do_layout()
                
        self.Bind(wx.EVT_BUTTON, self.Onbouton_aide, self.bouton_aide)
        self.Bind(wx.EVT_BUTTON, self.Onbouton_retour, self.bouton_retour)
        self.Bind(wx.EVT_BUTTON, self.Onbouton_suite, self.bouton_suite)
        
        self.bouton_retour.Enable(False)
        self.pageVisible = 1
                        

    def Creation_Pages(self):
        """ Creation des pages """
        for numPage in range(1, self.nbrePages+1) :
            setattr(self, "page%d" % numPage, eval(self.listePages[numPage-1] + "(self)"))
            self.sizer_pages.Add(getattr(self, "page%d" % numPage), 1, wx.EXPAND, 0)
            self.sizer_pages.Layout()
            getattr(self, "page%d" % numPage).Show(False)
        self.page1.Show(True)
        self.sizer_pages.Layout()

    def __set_properties(self):
        self.bouton_aide.SetToolTip(wx.ToolTip(_(u"Cliquez ici pour obtenir de l'aide")))
        self.bouton_retour.SetToolTip(wx.ToolTip(_(u"Cliquez ici pour revenir à la page précédente")))
        self.bouton_suite.SetToolTip(wx.ToolTip(_(u"Cliquez ici pour passer à l'étape suivante")))
        self.bouton_annuler.SetToolTip(wx.ToolTip(_(u"Cliquez pour annuler")))

    def __do_layout(self):
        grid_sizer_base = wx.FlexGridSizer(rows=4, cols=1, vgap=0, hgap=0)
        # Bandeau
        grid_sizer_base.Add(self.ctrl_bandeau, 1, wx.EXPAND, 0)
        
        # Contenu
        sizer_base = wx.BoxSizer(wx.VERTICAL)
        sizer_pages = wx.BoxSizer(wx.VERTICAL)
        self.sizer_pages = sizer_pages

        grid_sizer_base.Add(sizer_pages, 1, wx.EXPAND|wx.ALL, 10)
        grid_sizer_base.Add(self.static_line, 0, wx.LEFT|wx.RIGHT|wx.EXPAND, 10)
        
        # Boutons
        grid_sizer_boutons = wx.FlexGridSizer(rows=1, cols=6, vgap=10, hgap=10)
        grid_sizer_boutons.Add(self.bouton_aide, 0, 0, 0)
        grid_sizer_boutons.Add((20, 20), 0, wx.EXPAND, 0)
        grid_sizer_boutons.Add(self.bouton_retour, 0, 0, 0)
        grid_sizer_boutons.Add(self.bouton_suite, 0, 0, 0)
        grid_sizer_boutons.Add(self.bouton_annuler, 0, wx.LEFT, 10)
        grid_sizer_boutons.AddGrowableCol(1)
        grid_sizer_base.Add(grid_sizer_boutons, 1, wx.ALL|wx.EXPAND, 10)
        grid_sizer_base.AddGrowableRow(1)
        grid_sizer_base.AddGrowableCol(0)

        self.Creation_Pages()

        self.SetSizer(grid_sizer_base)
        grid_sizer_base.Fit(self)
        self.Layout()
        self.SetMinSize(self.GetSize())
        self.CenterOnScreen()

    def Onbouton_aide(self, event):
        from Utils import UTILS_Aide
        UTILS_Aide.Aide("Gnration")

    def Onbouton_retour(self, event):
        # rend invisible la page affichée
        pageCible = eval("self.page"+str(self.pageVisible))
        pageCible.Show(False)
        # Fait apparaître nouvelle page
        self.pageVisible -= 1
        pageCible = eval("self.page"+str(self.pageVisible))
        pageCible.Show(True)
        self.sizer_pages.Layout()
        # Si on quitte l'avant-dernière page, on active le bouton Suivant
        if self.pageVisible == self.nbrePages :
            self.bouton_suite.Enable(True)
            self.bouton_suite.SetImage(Chemins.GetStaticPath("Images/32x32/Fermer.png"))
        else:
            self.bouton_suite.Enable(True)
            self.bouton_suite.SetImage(Chemins.GetStaticPath("Images/32x32/Fleche_droite.png"))
        # Si on revient à la première page, on désactive le bouton Retour
        if self.pageVisible == 1 :
            self.bouton_retour.Enable(False)
        # On active le bouton annuler
        self.bouton_annuler.Enable(True)

    def PreparerCotisationsPourApercu(self):
        """Controle et choix humain des cotisations, avant le calcul des factures.

        Une proposition est un signal, pas une obligation de paiement :
        chaque titulaire peut etre decoche par l'operateur. Aucun motif
        personnel n'est impose ni enregistre par ce parcours.
        """
        self._controle_cotisations = None
        params = self.dictParametres
        if "cotisation" not in params.get("prestations", []):
            return True
        from Utils import UTILS_Adhesions_echeances as echeances
        from Utils import UTILS_Identification
        date_debut = params.get("date_anterieure") or params["date_debut"]
        perimetre = (
            str(date_debut), str(params["date_fin"]),
            tuple(sorted(int(x) for x in params["listeActivites"])),
            params["IDcompte_payeur"],
        )

        try:
            propo = echeances.Proposer(
                date_debut=date_debut, date_fin=params["date_fin"],
                date_reference=datetime.date.today(),
                liste_activites=params["listeActivites"],
                IDcompte_payeur=params["IDcompte_payeur"])
        except Exception as err:
            # Un echec n'equivaut jamais a zero cotisation due.
            # Aucun acces financier ne doit etre tente ici.
            import traceback
            pile = traceback.extract_tb(err.__traceback__)
            origine = pile[-1] if pile else None
            lieu = (u" (%s:%d)" % (
                origine.filename.replace("\\", "/").split("/")[-1],
                origine.lineno)) if origine else ""
            message = _(
                u"La vérification des cotisations automatiques a échoué. "
                u"AUCUNE nouvelle cotisation n'a été créée.\n\n"
                u"Oui : préparer les factures avec les prestations déjà "
                u"enregistrées uniquement. Certaines cotisations peuvent "
                u"manquer et devront être vérifiées avant émission.\n"
                u"Non : rester sur cette page pour corriger le problème.\n\n"
                u"Cause technique : %s%s") % (err, lieu)
            choix = wx.MessageBox(
                message, _(u"Cotisations automatiques non vérifiées"),
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self)
            if choix != wx.YES:
                return False
            self._controle_cotisations = {
                "statut": "indisponible", "perimetre": perimetre,
                "date_reference": datetime.date.today(),
            }
            return True

        if propo["a_verifier"]:
            message = _(
                u"%d situation(s) de cotisation nécessitent un examen manuel "
                u"(dates, chevauchements ou payeur).\n"
                u"Elles ne seront PAS créées automatiquement.\n\n"
                u"Vous pouvez poursuivre pour les autres cotisations, "
                u"ou revenir aux paramètres.\n"
                u"Continuer la préparation ?") % len(propo["a_verifier"])
            if wx.MessageBox(
                    message, _(u"Cotisations à vérifier"),
                    wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self) != wx.YES:
                return False

        selection_titulaires = set()
        if propo["propositions"]:
            # Les noms sont lus uniquement pour l'affichage local de la
            # decision. Aucune liste nominative n'est journalisee/exportee.
            noms = {}
            try:
                from Utils import UTILS_Adhesions as adhesions
                ids = sorted({int(p["IDtitulaire"]) for p in propo["propositions"]})
                lignes = adhesions._lire(
                    "SELECT IDindividu, nom, prenom FROM individus "
                    "WHERE IDindividu IN %s;" % adhesions._liste_sql(ids))
                noms = {int(ID): u"%s %s" % (nom or u"", prenom or u"")
                        for ID, nom, prenom in lignes}
            except Exception:
                # Une indisponibilite de l'annuaire n'autorise pas a
                # creer automatiquement les cotisations sans confirmation.
                noms = {}

            labels = []
            for p in propo["propositions"]:
                titulaire = int(p["IDtitulaire"])
                nom = noms.get(titulaire, u"Titulaire n°%d" % titulaire)
                labels.append(
                    u"%s — %.2f € — depuis le %s" % (
                        nom, float(p["montant"]),
                        p["date_debut"].strftime("%d/%m/%Y")))
            texte = _(
                u"Cochez uniquement les cotisations que vous souhaitez créer "
                u"et facturer. Décochez les personnes dispensées ou dont la "
                u"situation doit être traitée manuellement.\n\n"
                u"Les choix non retenus ne créent aucune cotisation. "
                u"Cette décision vaut pour ce lot, sans dispense permanente.\n"
                u"Vous pourrez toujours saisir une cotisation manuelle non facturée.")
            dlg = wx.MultiChoiceDialog(
                self, texte, _(u"Choix des cotisations à créer"), labels)
            try:
                # Choix initial habituel, librement modifiable.
                dlg.SetSelections(list(range(len(labels))))
                if dlg.ShowModal() != wx.ID_OK:
                    return False
                indices = [int(x) for x in dlg.GetSelections()]
            finally:
                dlg.Destroy()
            selection_titulaires = {
                int(propo["propositions"][index]["IDtitulaire"])
                for index in indices
            }

            if selection_titulaires:
                try:
                    reponses = echeances.Executer(
                        propo, confirmation=True,
                        selection_titulaires=selection_titulaires,
                        liste_activites=params["listeActivites"],
                        IDcompte_payeur=params["IDcompte_payeur"],
                        IDutilisateur=UTILS_Identification.GetIDutilisateur())
                except Exception as err:
                    wx.MessageBox(
                        _(u"La proposition a changé ou sa création a échoué. "
                          u"Reprenez le contrôle avant de facturer.\n\n%s") % err,
                        _(u"Facturation interrompue"), wx.OK | wx.ICON_ERROR, self)
                    return False
                erreurs = [r for r in reponses
                           if r.get("statut") not in ("cree", "rien_a_faire")]
                if erreurs or len(reponses) != len(selection_titulaires):
                    wx.MessageBox(
                        _(u"Certaines cotisations n'ont pas pu être créées. "
                          u"Des écritures précédentes peuvent exister. "
                          u"Revenez aux paramètres avant de facturer."),
                        _(u"Facturation interrompue"),
                        wx.OK | wx.ICON_ERROR, self)
                    return False

        # Relecture APRES les eventuelles creations : ce sont les
        # propositions residuelles qui seront reverifiees a l'emission.
        try:
            apres = echeances.Proposer(
                date_debut=date_debut, date_fin=params["date_fin"],
                date_reference=datetime.date.today(),
                liste_activites=params["listeActivites"],
                IDcompte_payeur=params["IDcompte_payeur"])
        except Exception as err:
            wx.MessageBox(
                _(u"Relecture des cotisations impossible après préparation. "
                  u"Revenez aux paramètres ; aucune facture n'a été émise.\n\n%s") % err,
                _(u"Contrôle incomplet"), wx.OK | wx.ICON_ERROR, self)
            return False
        self._controle_cotisations = {
            "statut": "verifie", "perimetre": perimetre,
            "date_reference": datetime.date.today(),
            "propositions": apres["propositions"],
            "a_verifier": apres["a_verifier"],
        }
        return True

    def VerifierCotisationsAvantEmission(self, comptes_payeurs):
        """Stoppe une emission si le controle a change depuis l'apercu.

        Une panne de relecture peut etre derrogee explicitement par
        l'operateur, sans creer d'adhesion ni inventer une cotisation due.
        """
        params = self.dictParametres
        if "cotisation" not in params.get("prestations", []):
            return True
        from Utils import UTILS_Adhesions_echeances as echeances
        controle = getattr(self, "_controle_cotisations", None)
        date_debut = params.get("date_anterieure") or params["date_debut"]
        perimetre = (
            str(date_debut), str(params["date_fin"]),
            tuple(sorted(int(x) for x in params["listeActivites"])),
            params["IDcompte_payeur"],
        )
        if not controle or controle["perimetre"] != perimetre:
            wx.MessageBox(
                _(u"Les paramètres ont changé. Revenez à la première étape "
                  u"pour contrôler les cotisations avant l'émission."),
                _(u"Contrôle à refaire"), wx.OK | wx.ICON_WARNING, self)
            return False
        try:
            actuel = echeances.Proposer(
                date_debut=date_debut, date_fin=params["date_fin"],
                date_reference=datetime.date.today(),
                liste_activites=params["listeActivites"],
                IDcompte_payeur=params["IDcompte_payeur"])
        except Exception as err:
            # Un choix humain exceptionnel demeure possible, mais jamais
            # implicitement au clic "Generer".
            message = _(
                u"Le contrôle des cotisations est indisponible au moment "
                u"de l'émission des %d facture(s).\n\n"
                u"Certaines cotisations peuvent manquer. "
                u"Voulez-vous émettre les factures sélectionnées avec les "
                u"seules prestations déjà enregistrées, en assumant "
                u"explicitement cette exception ?\n\n"
                u"Non : revenir à la sélection. Cause : %s") % (
                    len(comptes_payeurs), err)
            return wx.MessageBox(
                message, _(u"Émission sans contrôle complet"),
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self) == wx.YES

        # Une erreur initiale ne vaut pas absence de cotisations : si
        # l'acces est retabli, il faut faire les choix sur cet inventaire.
        if controle["statut"] == "indisponible":
            if actuel["propositions"] or actuel["a_verifier"]:
                wx.MessageBox(
                    _(u"Le contrôle des cotisations fonctionne de nouveau "
                      u"et révèle des situations à examiner. Revenez à "
                      u"la première étape pour choisir les cotisations "
                      u"à créer ou à dispenser avant d'émettre."),
                    _(u"Contrôle rétabli"), wx.OK | wx.ICON_WARNING, self)
                return False
            return True
        payeurs = {int(p) for p in comptes_payeurs}
        anciennes = echeances.Empreinte(
            [p for p in controle["propositions"]
             if int(p["IDcompte_payeur"]) in payeurs])
        nouvelles = echeances.Empreinte(
            [p for p in actuel["propositions"]
             if int(p["IDcompte_payeur"]) in payeurs])
        if (anciennes != nouvelles or
                controle["a_verifier"] != actuel["a_verifier"] or
                controle["date_reference"] != datetime.date.today()):
            wx.MessageBox(
                _(u"Les cotisations à contrôler ont changé depuis "
                  u"l'aperçu. Reprenez la première étape pour actualiser "
                  u"les prestations avant l'émission. "
                  u"Aucune facture n'a été créée."),
                _(u"Contrôle à actualiser"), wx.OK | wx.ICON_WARNING, self)
            return False
        return True

    def Onbouton_suite(self, event):
        # Vérifie que les données de la page en cours sont valides
        validation = self.ValidationPages()
        if validation == False : return
        if self.pageVisible == 1 and not self.PreparerCotisationsPourApercu():
            return
        # Si on est déjà sur la dernière page : on termine
        if self.pageVisible == self.nbrePages :
            self.Terminer()
            return
        # Rend invisible la page affichée
        pageCible = eval("self.page"+str(self.pageVisible))
        pageCible.Show(False)
        # Fait apparaître nouvelle page
        self.pageVisible += 1
        pageCible = eval("self.page"+str(self.pageVisible))
        pageCible.MAJ() 
        pageCible.Show(True)
        self.sizer_pages.Layout()
        # Si on arrive à la dernière page, on désactive le bouton Suivant
        if self.pageVisible == self.nbrePages :
            self.bouton_suite.SetImage(Chemins.GetStaticPath("Images/32x32/Fermer.png"))
            self.bouton_suite.SetTexte(_(u"Fermer"))
            self.bouton_annuler.Enable(False)
        # Si on quitte la première page, on active le bouton Retour
        if self.pageVisible > 1 :
            self.bouton_retour.Enable(True)
        
        # Désactivation du bouton Retour si dernière page > SPECIAL FACTURATION !!!
        if self.pageVisible == self.nbrePages :            
            self.bouton_retour.Enable(False)

    def ValidationPages(self) :
        """ Validation des données avant changement de pages """
        validation = getattr(self, "page%s" % self.pageVisible).Validation()
        return validation
    
    def Terminer(self):
        # Fermeture
        self.EndModal(wx.ID_OK)
        
    def SetFamille(self, IDfamille=None):
        self.page1.SetFamille(IDfamille)
        
        
        
if __name__ == "__main__":
    app = wx.App(0)
    #wx.InitAllImageHandlers()
    IDactivite = 1
    frame_1 = Dialog(None) 
    # TESTS
    frame_1.page1.ctrl_date_debut.SetDate(datetime.date(2017, 1, 1))
    frame_1.page1.ctrl_date_fin.SetDate(datetime.date(2017, 1, 31))
    
    app.SetTopWindow(frame_1)
    frame_1.ShowModal()
    app.MainLoop()
