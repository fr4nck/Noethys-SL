# -*- coding: utf-8 -*-
"""#436 - Fiche enfant Pêle-Mêle, selon le document papier en deux pages.

Aucune nouvelle zone medicale : le bouton ouvre l'onglet Medical existant.
Le registre d'autorisations est append-only et inactif sans creation
explicite, sauvegarde et autorisation de l'operateur.
"""
from datetime import date

import wx
import GestionDB
from Utils import UTILS_Accueil_autorisations as registre
from Utils import UTILS_Accueil_sources as sources
from Utils import UTILS_Accueil_impression as impression
from Utils import UTILS_Fiche_accueil_enfant as regles
from Utils.UTILS_Traduction import _


PRINCIPALES = (
    ("photos_site_imprimes", u"Photos (site internet : pelemele.org)"),
    ("maquillage", u"Maquillage"),
    ("piscine_baignade", u"Baignade"),
    ("activites_physiques", u"Activités physiques"),
)
COMPLEMENTAIRES = (
    ("photos_prise", u"Prise de photos / vidéos"),
    ("photos_usage_interne", u"Photos : usage interne uniquement"),
    ("photos_reseaux_sociaux", u"Photos : réseaux sociaux"),
)
CHOIX = (u"Non renseigné", u"Oui", u"Non")
ETAT = {"oui": 1, "non": 2}


def UtilisateurCourant():
    """Pas de repli implicite sur l'ancienne VerificationDroits permissive."""
    try:
        top = wx.GetApp().GetTopWindow()
        if top.GetName() == "general":
            return getattr(top, "dictUtilisateur", None)
    except Exception:
        pass
    return None


def LireEntete(IDindividu, aeeh_autorisee=False):
    """Uniquement l'identite; AEEH lue si habilitation explicite."""
    if type(IDindividu) is not int or IDindividu <= 0:
        raise ValueError("Identifiant enfant invalide")
    db = GestionDB.DB()
    try:
        if getattr(db, "echec", 0):
            raise RuntimeError("Base inaccessible")
        colonnes = "nom, prenom, date_naiss, ville_naiss"
        if aeeh_autorisee is True:
            colonnes += ", aeeh"
        sql = "SELECT %s FROM individus WHERE IDindividu=%s" % (
            colonnes, "%s" if db.isNetwork else "?")
        db.cursor.execute(sql, (IDindividu,))
        ligne = db.cursor.fetchone()
        if ligne is None:
            raise RuntimeError("Enfant introuvable")
        resultat = dict(zip(("nom", "prenom", "date_naiss", "ville_naiss"), ligne[:4]))
        if aeeh_autorisee is True:
            etat = ligne[4]
            resultat["aeeh"] = (
                u"Oui" if etat == 1 else
                u"Non" if etat == 0 else u"Non renseigné")
        return resultat
    finally:
        db.Close()


def ListerResponsables(IDindividu):
    """Suggestions de signataires, PAS preuve d'autorite parentale."""
    db = GestionDB.DB()
    try:
        if getattr(db, "echec", 0):
            return []
        sql = """SELECT DISTINCT i.IDindividu, i.nom, i.prenom
            FROM liens l JOIN individus i ON i.IDindividu=l.IDindividu_sujet
            WHERE l.IDindividu_objet=? AND l.responsable=1
            ORDER BY i.nom, i.prenom, i.IDindividu"""
        if db.isNetwork:
            sql = sql.replace("?", "%s")
        db.cursor.execute(sql, (IDindividu,))
        return [(int(i), ("%s %s" % (nom or "", prenom or "")).strip())
                for i, nom, prenom in db.cursor.fetchall()]
    finally:
        db.Close()


def EtatChoix(historique, IDindividu, code, perimetre, au):
    etat = regles.EtatAutorisation(
        historique, IDindividu, code, au, perimetre)["etat"]
    return ETAT.get(etat, 0), etat


class Dialog(wx.Dialog):
    def __init__(self, parent, IDindividu):
        wx.Dialog.__init__(self, parent,
            title=_(u"Fiche enfant - Accueil de loisirs Pêle-Mêle"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.IDindividu = IDindividu
        self.parent_individu = parent
        self.utilisateur = UtilisateurCourant()
        self.acces = registre.AccesUtilisateur(self.utilisateur, "consulter")
        self.ecriture = registre.AccesUtilisateur(self.utilisateur, "modifier")
        self.administrateur = (
            self.ecriture and
            str((self.utilisateur or {}).get("profil") or "").startswith("administrateur"))
        self.historique = []
        self.attendus = {}
        self.etats_initiaux = {}
        self.perimetre_charge = None
        self.registre_pret = False
        self.lecture_medicale = sources.AdministrateurActuel(self.utilisateur)
        self.medical = None
        try:
            self.entete = LireEntete(IDindividu, aeeh_autorisee=self.lecture_medicale)
        except Exception:
            self.entete = {"nom": u"", "prenom": u"", "date_naiss": None}

        panneau = wx.ScrolledWindow(self)
        panneau.SetScrollRate(0, 15)
        colonne = wx.BoxSizer(wx.VERTICAL)

        titre = wx.StaticText(panneau, label=(
            u"ACCUEIL DE LOISIRS PÊLE-MÊLE\nFICHE ENFANT"))
        titre.SetFont(wx.Font(15, wx.FONTFAMILY_DEFAULT,
                            wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        colonne.Add(titre, 0, wx.ALIGN_CENTER | wx.ALL, 12)
        self._section(panneau, colonne, u"IDENTITÉ",
             u"%s %s     Naissance : %s     Ville : %s" % (
                self.entete.get("nom") or u"",
                self.entete.get("prenom") or u"",
                self.entete.get("date_naiss") or u"Non renseignée",
                self.entete.get("ville_naiss") or u"Non renseignée"))
        self._section(panneau, colonne, u"RESPONSABLE LÉGAL n°1",
             u"Informations conservées dans l'onglet Liens de la fiche individuelle.")
        self._section(panneau, colonne, u"RESPONSABLE LÉGAL n°2",
             u"Vérifier les titulaires et les coordonnées dans les fiches existantes.")
        self._section(panneau, colonne, u"ACCOMPAGNANTS",
             u"Conserver la liste des accompagnants et les liens dans Noethys.")
        # Les donnees restent dans les tables Medical de Noethys. On lit
        # uniquement pour afficher, sous permission stricte admin.
        if self.lecture_medicale:
            try:
                self.medical = sources.LireMedicalExistant(
                    IDindividu, self.utilisateur)
            except Exception:
                self.medical = None
        vaccinations = (u"%d vaccination(s) enregistrée(s) dans Noethys." %
                       self.medical["vaccins_enregistres"]
                       if self.medical else u"Consulter les vaccins dans l'onglet Médical.")
        medecin = self.medical.get("medecin") if self.medical else None
        nom_medecin = (u"%s %s — %s" % (
            medecin.get("nom") or "", medecin.get("prenom") or "",
            medecin.get("telephone") or "")).strip() if medecin else (
            u"Consulter le médecin traitant dans l'onglet Médical.")
        problemes = self.medical.get("problemes", []) if self.medical else []
        libelles = [p.get("intitule") or u"Information enregistrée" for p in problemes]
        contenu_medical = (u"Informations déjà enregistrées : %s. "
                           u"Consignes et PAI à consulter dans Médical." %
                           (u" ; ".join(libelles) or u"Aucune fiche signalée")
                           if self.medical else
                           u"Traitements, PAI, allergies et consignes : onglet Médical existant.")
        self._section(panneau, colonne, u"VACCINATIONS", vaccinations)
        self._section(panneau, colonne, u"MÉDECIN TRAITANT", nom_medecin)
        self._section(panneau, colonne, u"MALADIES ET ALLERGIES", contenu_medical)
        self.bouton_medical = wx.Button(
            panneau, label=_(u"Consulter les informations médicales déjà enregistrées"))
        colonne.Add(self.bouton_medical, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        if self.lecture_medicale:
            self._section(panneau, colonne, u"AEEH",
                u"Statut existant dans l'Identité : %s" %
                self.entete.get("aeeh", u"Non renseigné"))
        libelles_repas = {
            "standard": u"Standard", "sans_porc": u"Sans porc",
            "vegetarien": u"Végétarien",
            "sans_repas_pmsl": u"Repas apporté par la famille",
            "non_renseigne": u"Non renseigné",
            "non_configure": u"Questionnaire repas non préparé",
            "a_verifier": u"Réponse alimentaire à vérifier",
        }
        self.repas_existant = "non_renseigne"
        if self.acces:
            try:
                self.repas_existant = sources.LireRepasExistant(
                    IDindividu, self.utilisateur)
            except Exception:
                self.repas_existant = "a_verifier"
        self._section(panneau, colonne, u"REPAS",
             u"Choix dans le questionnaire individuel : %s." %
             libelles_repas.get(self.repas_existant, u"À vérifier"))
        self.bouton_repas = wx.Button(panneau, label=_(u"Consulter le questionnaire repas"))
        colonne.Add(self.bouton_repas, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        self._bandeau(panneau, colonne, u"AUTORISATIONS DIVERSES")
        self.etat_registre = wx.StaticText(
            panneau, label=_(u"Registre : vérification en cours"))
        colonne.Add(self.etat_registre, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        aide = wx.StaticText(panneau, label=_(
            u"Les quatre premières autorisations reprennent exactement la fiche "
            u"papier. Chaque Oui ou Non doit provenir d'un document signé. "
            u"Une absence de réponse ne signifie jamais Oui."))
        aide.Wrap(670)
        colonne.Add(aide, 0, wx.ALL, 12)

        self.perimetre = wx.TextCtrl(panneau, value=u"ALSH 2026-2027")
        self._champ(panneau, colonne, u"ALSH / année / périmètre :", self.perimetre)
        self.choix_autorisations = {}
        for code, libelle in PRINCIPALES + COMPLEMENTAIRES:
            ligne = wx.BoxSizer(wx.HORIZONTAL)
            etiquette = wx.StaticText(panneau, label=libelle)
            etiquette.SetMinSize((315, -1))
            choix = wx.Choice(panneau, choices=CHOIX)
            choix.SetSelection(0)
            ligne.Add(etiquette, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
            ligne.Add(choix, 0, wx.RIGHT, 10)
            self.choix_autorisations[code] = choix
            colonne.Add(ligne, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        self._bandeau(panneau, colonne, u"SIGNATURE ET JUSTIFICATIF")
        try:
            self.signataires = ListerResponsables(IDindividu) if self.acces else []
        except Exception:
            self.signataires = []
        self.signataire = wx.Choice(panneau, choices=[
            u"Sélectionner le responsable signataire"] + [
            u"%s (fiche n°%d)" % (nom, ident)
            for ident, nom in self.signataires])
        self.signataire.SetSelection(0)
        self._champ(panneau, colonne, u"Responsable ayant signé :", self.signataire)
        self.date_signature = wx.TextCtrl(panneau, value=u"")
        self._champ(panneau, colonne, u"Date de signature (AAAA-MM-JJ) :", self.date_signature)
        self.date_debut = wx.TextCtrl(panneau, value=u"2026-09-01")
        self._champ(panneau, colonne, u"Début de validité :", self.date_debut)
        self.date_fin = wx.TextCtrl(panneau, value=u"2027-08-31")
        self._champ(panneau, colonne, u"Fin de validité :", self.date_fin)
        self.source = wx.Choice(panneau, choices=(u"Fiche papier", u"Pièce enregistrée"))
        self.source.SetSelection(0)
        self._champ(panneau, colonne, u"Support signé :", self.source)
        self.reference_preuve = wx.TextCtrl(panneau, value=u"")
        self._champ(panneau, colonne, u"Référence de la fiche ou pièce :", self.reference_preuve)
        self.texte_version = wx.TextCtrl(panneau, value=u"Fiche Enfant 2026-06")
        self._champ(panneau, colonne, u"Modèle signé :", self.texte_version)
        self.autorite = wx.CheckBox(panneau, label=_(
            u"J'ai vérifié l'identité et l'autorité parentale du signataire."))
        colonne.Add(self.autorite, 0, wx.ALL, 12)

        self.inclure_medical = wx.CheckBox(
            panneau, label=_(u"Inclure les informations médicales déjà enregistrées dans le PDF (confidentiel)"))
        self.inclure_medical.Enable(self.lecture_medicale and self.medical is not None)
        colonne.Add(self.inclure_medical, 0, wx.ALL, 12)
        self.bouton_imprimer = wx.Button(
            panneau, label=_(u"Éditer la fiche enfant PDF (2 pages)"))
        self.bouton_imprimer.Enable(self.acces)
        colonne.Add(self.bouton_imprimer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        outils = wx.BoxSizer(wx.HORIZONTAL)
        self.bouton_initialiser = wx.Button(
            panneau, label=_(u"Préparer le registre (administrateur)"))
        self.bouton_actualiser = wx.Button(panneau, label=_(u"Actualiser les autorisations"))
        self.bouton_sauver = wx.Button(panneau, label=_(u"Enregistrer les changements signés"))
        outils.Add(self.bouton_initialiser, 0, wx.RIGHT, 9)
        outils.Add(self.bouton_actualiser, 0, wx.RIGHT, 9)
        outils.Add(self.bouton_sauver, 0, wx.RIGHT, 9)
        colonne.Add(outils, 0, wx.ALL, 12)
        bas = wx.BoxSizer(wx.HORIZONTAL)
        bas.AddStretchSpacer()
        self.bouton_fermer = wx.Button(panneau, wx.ID_CANCEL, _(u"Fermer"))
        bas.Add(self.bouton_fermer, 0, wx.ALL, 12)
        colonne.Add(bas, 0, wx.EXPAND)
        panneau.SetSizer(colonne)
        panneau.FitInside()
        enveloppe = wx.BoxSizer(wx.VERTICAL)
        enveloppe.Add(panneau, 1, wx.EXPAND)
        self.SetSizer(enveloppe)
        self.SetMinSize((720, 550))
        self.SetSize((800, 710))
        self.CentreOnParent()
        self.Bind(wx.EVT_BUTTON, self.OnMedical, self.bouton_medical)
        self.Bind(wx.EVT_BUTTON, self.OnRepas, self.bouton_repas)
        self.Bind(wx.EVT_BUTTON, self.OnInitialiser, self.bouton_initialiser)
        self.Bind(wx.EVT_BUTTON, self.OnActualiser, self.bouton_actualiser)
        self.Bind(wx.EVT_BUTTON, self.OnEnregistrer, self.bouton_sauver)
        self.Bind(wx.EVT_BUTTON, self.OnImprimer, self.bouton_imprimer)
        self.OnActualiser()

    @staticmethod
    def _bandeau(panneau, colonne, texte):
        label = wx.StaticText(panneau, label=texte)
        label.SetBackgroundColour(wx.Colour(190, 190, 190))
        label.SetForegroundColour(wx.BLACK)
        label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT,
                              wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        colonne.Add(label, 0, wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, 8)

    @classmethod
    def _section(cls, panneau, colonne, titre, contenu):
        cls._bandeau(panneau, colonne, titre)
        ligne = wx.StaticText(panneau, label=contenu)
        ligne.Wrap(660)
        colonne.Add(ligne, 0, wx.ALL, 10)

    @staticmethod
    def _champ(panneau, colonne, titre, control):
        ligne = wx.BoxSizer(wx.HORIZONTAL)
        label = wx.StaticText(panneau, label=titre)
        label.SetMinSize((265, -1))
        ligne.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 9)
        ligne.Add(control, 1, wx.EXPAND)
        colonne.Add(ligne, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

    def OnMedical(self, event=None):
        # L'onglet medical existant seul demeure l'editeur des donnees.
        self.EndModal(wx.ID_APPLY)

    def OnRepas(self, event=None):
        self.EndModal(wx.ID_YES)

    def OnActualiser(self, event=None):
        self.registre_pret = False
        self.historique = []
        self.attendus = {}
        self.perimetre_charge = None
        if not self.acces:
            self.etat_registre.SetLabel(_(u"Registre réservé aux utilisateurs habilités"))
        else:
            try:
                registre.VerifierRegistre(autorise=True)
                self.historique = registre.LireHistorique(
                    self.IDindividu, autorise=True)
                # Capture les revisions dans la même connexion qu'une lecture
                # normale : un changement concurrent reste controle a l'ecriture.
                self.registre_pret = True
                self.etat_registre.SetLabel(_(u"Registre prêt - historique conservé"))
            except registre.RegistreAbsent:
                self.etat_registre.SetLabel(_(
                    u"Registre absent : un administrateur doit le préparer après sauvegarde"))
            except Exception:
                self.etat_registre.SetLabel(_(
                    u"Lecture des autorisations impossible : aucune écriture autorisée"))
        perimetre = self.perimetre.GetValue().strip()
        self.perimetre_charge = perimetre
        self.etats_initiaux = {}
        for code, control in self.choix_autorisations.items():
            if self.registre_pret:
                choix, etat = EtatChoix(
                    self.historique, self.IDindividu, code, perimetre,
                    date.today().isoformat())
                # Un conflit ou une expiration ne doit jamais etre vu comme Non.
                if etat in ("a_verifier", "expire"):
                    self.etat_registre.SetLabel(_(
                        u"Des autorisations sont à vérifier ou expirées"))
            else:
                choix = 0
            control.SetSelection(choix)
            self.etats_initiaux[code] = choix
            self.attendus[(code, perimetre)] = next((
                d["IDautorisation"] for d in reversed(self.historique)
                if d["type"] == code and d["perimetre"] == perimetre), None)
            control.Enable(self.ecriture and self.registre_pret)
        self.bouton_initialiser.Enable(self.administrateur and not self.registre_pret)
        self.bouton_sauver.Enable(
            self.ecriture and self.registre_pret and bool(self.signataires))
        return self.registre_pret

    def OnInitialiser(self, event=None):
        if not self.administrateur:
            return False
        message = _(u"Cette opération ajoute uniquement le registre des "
                    u"autorisations à la base courante. Avez-vous effectué "
                    u"et vérifié une sauvegarde complète de cette base ?")
        if wx.MessageBox(message, _(u"Préparation après sauvegarde"),
                         wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
                         self) != wx.YES:
            return False
        try:
            registre.InitialiserRegistre(
                administrateur=True, sauvegarde_confirmee=True)
            return self.OnActualiser()
        except Exception as exc:
            wx.MessageBox(_(u"Registre non préparé : %s") % exc,
                          _(u"Opération refusée"), wx.OK | wx.ICON_WARNING, self)
            return False

    def OnImprimer(self, event=None):
        """Édition locale sur le modèle papier, aucun envoi ni nouvelle donnée."""
        if not self.acces:
            return False
        perimetre = self.perimetre.GetValue().strip()
        if perimetre != self.perimetre_charge:
            wx.MessageBox(
                _(u"Actualisez le périmètre avant d'imprimer."),
                _(u"Fiche enfant"), wx.OK | wx.ICON_WARNING, self)
            return False
        inclure = (self.lecture_medicale and self.medical is not None
                   and self.inclure_medical.GetValue() is True)
        if inclure:
            if wx.MessageBox(_(
                    u"Ce PDF contiendra des informations médicales sensibles "
                    u"issues de la fiche existante. Il sera enregistré sur "
                    u"l'ordinateur choisi, sans protection automatique. "
                    u"Confirmez-vous cet export confidentiel ?"),
                    _(u"Export de données médicales"),
                    wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
                    self) != wx.YES:
                return False
        choix = wx.FileDialog(
            self, _(u"Enregistrer la fiche enfant au format PDF"),
            defaultFile=u"Fiche_Enfant_%d.pdf" % self.IDindividu,
            wildcard=u"Documents PDF (*.pdf)|*.pdf",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        try:
            if choix.ShowModal() != wx.ID_OK:
                return False
            destination = choix.GetPath()
        finally:
            choix.Destroy()
        info = dict(self.entete)
        info["annee"] = perimetre
        info["responsables"] = [
            {"identite": nom} for identifiant, nom in self.signataires[:2]]
        info["aeeh"] = self.entete.get("aeeh", "")
        info["repas"] = {
            "standard": u"Standard", "sans_porc": u"Sans porc",
            "vegetarien": u"Végétarien",
            "sans_repas_pmsl": u"Repas apporté par la famille",
            "non_renseigne": u"Non renseigné",
        }.get(getattr(self, "repas_existant", None),
              u"À vérifier dans le questionnaire Noethys")
        # Le consentement a l'export s'applique a TOUS les champs medicaux,
        # pas seulement a la liste des problemes. Aucune fuite par defaut.
        info["vaccinations"] = u""
        info["medecin"] = u""
        info["medical"] = []
        info["traitement"] = u"Non renseigné"
        if inclure:
            info["vaccinations"] = (
                u"%d vaccination(s) enregistrée(s) dans Noethys ; "
                u"date du dernier DT Polio non vérifiée" %
                self.medical["vaccins_enregistres"])
            medecin = self.medical.get("medecin")
            if medecin:
                info["medecin"] = u"%s %s (%s)" % (
                    medecin.get("nom", ""), medecin.get("prenom", ""),
                    medecin.get("telephone", ""))
            traitements = [
                item for item in self.medical["problemes"]
                if item.get("traitement_medical") is True
            ]
            info["traitement"] = (
                u"Traitement signalé dans Noethys : vérifier ordonnance"
                if traitements else u"Aucun traitement signalé dans les fiches consultées"
            )
            for item in self.medical["problemes"]:
                details = [
                    item.get("intitule") or u"Information médicale",
                    item.get("description") or u"",
                    item.get("description_traitement") or u"",
                ]
                info["medical"].append(u" — ".join(x for x in details if x))
        # PAI/AESH/allergies : ne jamais inférer Oui ou Non depuis un
        # problème de santé générique ou depuis l'absence de saisie.
        info["autorisation_modele"] = u"Fiche Enfant 2026-06"
        info["autorisations"] = {}
        for code, _libelle in PRINCIPALES:
            if self.registre_pret:
                _index, etat = EtatChoix(
                    self.historique, self.IDindividu, code, perimetre,
                    date.today().isoformat())
                info["autorisations"][code] = etat
        if self.signataire.GetSelection() > 0:
            info["signataire"] = self.signataires[
                self.signataire.GetSelection() - 1][1]
        info["date_signature"] = self.date_signature.GetValue()
        try:
            impression.GenererPDF(destination, info)
        except Exception as exc:
            wx.MessageBox(
                _(u"Le PDF n'a pas pu être généré : %s") % exc,
                _(u"Édition impossible"), wx.OK | wx.ICON_WARNING, self)
            return False
        wx.MessageBox(
            _(u"Fiche PDF créée localement. Conservez séparément la fiche "
              u"originale signée et les justificatifs."),
            _(u"Fiche enfant"), wx.OK | wx.ICON_INFORMATION, self)
        return True

    def OnEnregistrer(self, event=None):
        if not self.ecriture or not self.registre_pret:
            return False
        perimetre = self.perimetre.GetValue().strip()
        if not perimetre or perimetre != self.perimetre_charge:
            wx.MessageBox(_(
                u"Le périmètre a changé. Actualisez la fiche avant d'enregistrer."),
                _(u"Vérification obligatoire"), wx.OK | wx.ICON_WARNING, self)
            return False
        if self.signataire.GetSelection() <= 0:
            wx.MessageBox(_(u"Identifiez le responsable légal signataire "
                             u"dans l'onglet Liens avant d'enregistrer."),
                          _(u"Signature requise"), wx.OK | wx.ICON_WARNING, self)
            return False
        differents = [
            (code, ctrl.GetSelection()) for code, ctrl in
            self.choix_autorisations.items()
            if ctrl.GetSelection() != self.etats_initiaux.get(code)
            and ctrl.GetSelection() in (1, 2)]
        if not differents:
            wx.MessageBox(_(u"Aucun changement signé à enregistrer."),
                          _(u"Fiche enfant"), wx.OK | wx.ICON_INFORMATION, self)
            return False
        source = "papier" if self.source.GetSelection() == 0 else "pieces"
        signataire = self.signataires[self.signataire.GetSelection() - 1][0]
        decisions = [{
            "type": code, "valeur": 1 if choix == 1 else 0,
            "perimetre": perimetre,
            "date_debut": self.date_debut.GetValue(),
            "date_fin": self.date_fin.GetValue(),
            "date_signature": self.date_signature.GetValue(),
            "IDsignataire": signataire,
            "autorite_verifiee": self.autorite.GetValue() is True,
            "texte_version": self.texte_version.GetValue(),
            "source": source,
            "reference_preuve": self.reference_preuve.GetValue(),
        } for code, choix in differents]
        avant = {cle: self.attendus[cle] for cle in
                 ((code, perimetre) for code, _choix in differents)}
        if wx.MessageBox(_(
              u"Enregistrer %d réponse(s) signée(s) et conserver les "
              u"anciennes décisions dans l'historique ?") % len(decisions),
              _(u"Valider les autorisations de l'enfant"),
              wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
              self) != wx.YES:
            return False
        try:
            IDutilisateur = (self.utilisateur or {}).get("IDutilisateur")
            registre.EnregistrerLot(
                self.IDindividu, IDutilisateur, decisions, avant,
                autorise=True)
        except Exception as exc:
            wx.MessageBox(_(u"Aucune autorisation enregistrée : %s") % exc,
                          _(u"Enregistrement refusé"), wx.OK | wx.ICON_WARNING, self)
            return False
        self.OnActualiser()
        return True
