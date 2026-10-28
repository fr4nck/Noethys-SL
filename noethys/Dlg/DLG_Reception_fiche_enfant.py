# -*- coding: utf-8 -*-
"""Relecture manuelle d'une fiche enfant Pêle-Mêle deja recue (#436).

Aucune lecture de document ni ecriture SQL : la fiche originale est consultee
auparavant dans l'onglet Pieces. La proposition AEEH est appliquee au controle
d'Identite SEULEMENT ; le bouton Ok de la fiche individuelle garde la maitrise
de l'enregistrement. Les informations medicales sont a verifier dans l'onglet
Medical, jamais extraire d'un PDF automatiquement.
"""
import wx
from datetime import date as date_calendrier
from Ctrl import CTRL_Saisie_date
from Utils import UTILS_Reception_fiches as reception


def _FormaterDatePeriode(valeur):
    """Affiche les dates déjà stockées ; ne prétend pas les valider."""
    if valeur is None:
        return u"date non indiquée"
    try:
        if isinstance(valeur, date_calendrier):
            return valeur.strftime("%d/%m/%Y")
        return date_calendrier.fromisoformat(str(valeur)).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return u"date à vérifier"


LIBELLES_AEEH = (
    u"Non renseigné sur la fiche reçue",
    u"Oui - bénéficiaire AEEH",
    u"Non - ne bénéficie pas de l'AEEH",
)
VALEURS_AEEH = ("absent", "oui", "non")
RUBRIQUES_SANTE = (
    ("vaccinations", u"Vaccinations (déclaration parentale)"),
    ("allergies", u"Allergies"),
    ("traitements", u"Traitements"),
    ("pai", u"PAI"),
    ("consignes_sortie", u"Consignes pour les sorties"),
)


class Dialog(wx.Dialog):
    def __init__(self, parent, IDindividu, aeeh_actuelle, periodes=()):
        wx.Dialog.__init__(
            self, parent, title=u"Contrôle d'une fiche enfant reçue",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.IDindividu = IDindividu
        self.aeeh_actuelle = aeeh_actuelle
        self.periodes = periodes
        self._valeur_proposee = None
        self._controle_periode = None
        self._controle_medical = reception.PreparerControlesMedicaux()

        # Une seule fenêtre, défilante si la hauteur de l'écran est réduite.
        panneau = wx.ScrolledWindow(self)
        panneau.SetScrollRate(0, 16)
        vertical = wx.BoxSizer(wx.VERTICAL)
        intro = wx.StaticText(panneau, label=(
            u"Comparez la fiche Pêle-Mêle reçue avec les informations de "
            u"l'enfant, après lecture du document dans l'onglet Pièces."
        ))
        intro.Wrap(520)
        vertical.Add(intro, 0, wx.ALL | wx.EXPAND, 8)
        libelle_actuel = (
            u"Non renseigné" if aeeh_actuelle is None else
            (u"Oui" if aeeh_actuelle == 1 else u"Non")
        )
        vertical.Add(wx.StaticText(
            panneau, label=u"Enfant n°%d — AEEH dans Noethys : %s" % (
                IDindividu, libelle_actuel)
        ), 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        vertical.Add(wx.StaticText(
            panneau, label=u"Réponse AEEH indiquée par les parents :"
        ), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        self.choix = wx.Choice(panneau, choices=LIBELLES_AEEH)
        self.choix.SetSelection(0)
        vertical.Add(self.choix, 0, wx.ALL | wx.EXPAND, 8)

        vertical.Add(wx.StaticText(
            panneau, label=u"Périodes AEEH existantes dans Noethys (lecture seule) :"
        ), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        lignes = [
            u"Du %s au %s" % (
                _FormaterDatePeriode(periode.get("date_debut")),
                _FormaterDatePeriode(periode.get("date_fin"))
                if periode.get("date_fin") is not None else u"terme non indiqué",
            )
            for periode in periodes
        ]
        if not lignes:
            lignes = [u"Aucune période AEEH enregistrée"]
        self.liste_periodes = wx.ListBox(panneau, choices=lignes, size=(-1, 70))
        vertical.Add(self.liste_periodes, 0, wx.ALL | wx.EXPAND, 8)

        vertical.Add(wx.StaticText(
            panneau, label=u"Dates communiquées sur la fiche ou le justificatif (facultatif) :"
        ), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        ligne_dates = wx.BoxSizer(wx.HORIZONTAL)
        self.date_debut = CTRL_Saisie_date.Date(panneau)
        self.date_fin = CTRL_Saisie_date.Date(panneau)
        ligne_dates.Add(wx.StaticText(panneau, label=u"Début :"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        ligne_dates.Add(self.date_debut, 0, wx.RIGHT, 15)
        ligne_dates.Add(wx.StaticText(panneau, label=u"Fin :"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        ligne_dates.Add(self.date_fin, 0)
        vertical.Add(ligne_dates, 0, wx.ALL, 8)
        vertical.Add(wx.StaticText(
            panneau, label=u"Les dates sont comparées, jamais enregistrées par cet assistant."
        ), 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        medical = wx.StaticText(panneau, label=(
            u"À examiner dans l'onglet Médical : vaccinations et justificatifs, "
            u"allergies, traitements, PAI et consignes de sortie. "
            u"Aucun de ces points n'est validé automatiquement."
        ))
        medical.Wrap(520)
        vertical.Add(medical, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.relecture = wx.CheckBox(
            panneau, label=u"J'ai vérifié l'enfant concerné et relu la fiche reçue."
        )
        vertical.Add(self.relecture, 0, wx.ALL, 8)

        vertical.Add(wx.StaticText(panneau, label=u"Support du document examiné :"),
                     0, wx.LEFT | wx.TOP | wx.RIGHT, 8)
        self.source = wx.Choice(panneau, choices=(
            u"Choisir le support", u"Fiche papier", u"Document reçu dans Pièces"
        ))
        self.source.SetSelection(0)
        vertical.Add(self.source, 0, wx.ALL | wx.EXPAND, 8)

        self.justificatif = wx.CheckBox(
            panneau, label=u"J'ai vérifié le justificatif AEEH et les dates du droit."
        )
        self.fin_non_precisee = wx.CheckBox(
            panneau, label=u"Le justificatif atteste explicitement un droit sans échéance."
        )
        vertical.Add(self.justificatif, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        vertical.Add(self.fin_non_precisee, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.bouton_periode = wx.Button(
            panneau, label=u"Enregistrer cette période AEEH vérifiée"
        )
        vertical.Add(self.bouton_periode, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        vertical.Add(wx.StaticText(
            panneau, label=u"Rubriques réellement confirmées sur la fiche parentale :"
        ), 0, wx.ALL, 8)
        self.rubriques_sante = wx.CheckListBox(
            panneau, choices=[label for code, label in RUBRIQUES_SANTE],
            size=(-1, 108)
        )
        vertical.Add(self.rubriques_sante, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)
        self.fiche_signee = wx.CheckBox(
            panneau, label=u"Les parents ont complété et signé la fiche consultée."
        )
        vertical.Add(self.fiche_signee, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        signature_ligne = wx.BoxSizer(wx.HORIZONTAL)
        signature_ligne.Add(
            wx.StaticText(panneau, label=u"Date de signature des parents (si connue) :"),
            0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8
        )
        self.date_signature = CTRL_Saisie_date.Date(panneau)
        signature_ligne.Add(self.date_signature, 0)
        vertical.Add(signature_ligne, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.bouton_parent = wx.Button(
            panneau, label=u"Historiser cette confirmation parentale"
        )
        vertical.Add(self.bouton_parent, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.label_derniere = wx.StaticText(
            panneau, label=u"Dernière confirmation parentale : non chargée"
        )
        vertical.Add(self.label_derniere, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        boutons = wx.BoxSizer(wx.HORIZONTAL)
        boutons.AddStretchSpacer()
        bouton_annuler = wx.Button(panneau, wx.ID_CANCEL, u"Fermer")
        self.bouton_medical = wx.Button(panneau, wx.ID_APPLY, u"Ouvrir l'onglet Médical")
        self.bouton_reporter = wx.Button(panneau, wx.ID_OK, u"Reporter la réponse AEEH")
        boutons.Add(bouton_annuler, 0, wx.RIGHT, 8)
        boutons.Add(self.bouton_medical, 0, wx.RIGHT, 8)
        boutons.Add(self.bouton_reporter, 0)
        vertical.Add(boutons, 0, wx.EXPAND | wx.ALL, 8)
        panneau.SetSizer(vertical)
        panneau.FitInside()
        enveloppe = wx.BoxSizer(wx.VERTICAL)
        enveloppe.Add(panneau, 1, wx.EXPAND)
        self.SetSizer(enveloppe)
        self.SetMinSize((700, 570))
        self.SetSize((760, 670))
        self.CentreOnParent()
        self.Bind(wx.EVT_BUTTON, self.OnReporter, self.bouton_reporter)
        self.Bind(wx.EVT_BUTTON, self.OnOuvrirMedical, self.bouton_medical)
        self.Bind(wx.EVT_BUTTON, self.OnEnregistrerPeriode, self.bouton_periode)
        self.Bind(wx.EVT_BUTTON, self.OnHistoriserParent, self.bouton_parent)
        self._RafraichirConfirmation()

    def OnOuvrirMedical(self, event):
        """Ouvre le panneau médical existant, sans créer un autre formulaire."""
        self.EndModal(wx.ID_APPLY)

    @staticmethod
    def _DateSaisie(champ):
        """Date masquée vide != date invalide partiellement renseignée."""
        valeur = champ.GetDate()
        if valeur is None and any(c.isdigit() for c in champ.GetValue()):
            raise reception.ReceptionFicheInvalide(
                "Date incomplète ou invalide, renseignez JJ/MM/AAAA."
            )
        return valeur

    def OnReporter(self, event):
        index = self.choix.GetSelection()
        if index < 0 or index >= len(VALEURS_AEEH):
            wx.MessageBox(
                u"Choisissez une réponse AEEH explicite.",
                u"Contrôle incomplet", wx.OK | wx.ICON_WARNING, self,
            )
            return
        try:
            resultat = reception.EvaluerDeclarationAEEH(
                self.IDindividu, self.aeeh_actuelle,
                VALEURS_AEEH[index],
                document_relu=self.relecture.GetValue(),
            )
        except (IndexError, reception.ReceptionFicheInvalide) as err:
            wx.MessageBox(str(err), u"Fiche à vérifier", wx.OK | wx.ICON_WARNING, self)
            return
        if resultat["action"] == "relecture_requise":
            wx.MessageBox(
                u"Vérifiez d'abord l'identité de l'enfant et le document reçu.",
                u"Contrôle incomplet", wx.OK | wx.ICON_WARNING, self,
            )
            return
        try:
            debut = self._DateSaisie(self.date_debut)
            fin = self._DateSaisie(self.date_fin)
            if (debut is not None or fin is not None) and not self.relecture.GetValue():
                wx.MessageBox(
                    u"Confirmez la relecture du document avant de comparer les dates.",
                    u"Contrôle incomplet", wx.OK | wx.ICON_WARNING, self,
                )
                return
            comparaison = reception.ComparerPeriodeAEEH(
                date_debut=debut, date_fin=fin, periodes_existantes=self.periodes,
            )
        except reception.ReceptionFicheInvalide as err:
            wx.MessageBox(str(err), u"Dates AEEH à vérifier",
                          wx.OK | wx.ICON_WARNING, self)
            return

        self._controle_periode = comparaison
        self._valeur_proposee = resultat["valeur_proposee"]
        self.EndModal(wx.ID_OK)

    def GetValeurProposee(self):
        return self._valeur_proposee

    def GetControlePeriode(self):
        return self._controle_periode

    def _Source(self):
        return {1: "papier", 2: "pieces"}.get(self.source.GetSelection())

    def _RafraichirConfirmation(self):
        from Utils import UTILS_Suivi_fiches
        try:
            derniere = UTILS_Suivi_fiches.GetDerniereConfirmationParentale(self.IDindividu)
        except Exception:
            self.label_derniere.SetLabel(u"Historique parental indisponible.")
            return
        if derniere is None:
            self.label_derniere.SetLabel(u"Aucune réception parentale historisée.")
        else:
            self.label_derniere.SetLabel(
                u"Dernière réception contrôlée : %s à %s" % (
                    _FormaterDatePeriode(derniere["date_reception"]),
                    derniere["heure"])
            )

    def OnEnregistrerPeriode(self, event):
        """Ajout immédiat dans aeeh_periodes après justificatif et confirmation."""
        from Utils import UTILS_Suivi_fiches, UTILS_Identification, UTILS_AEEH_Periodes
        if not self.relecture.GetValue() or not self.justificatif.GetValue():
            wx.MessageBox(u"Relisez la fiche et vérifiez le justificatif AEEH.",
                          u"Vérification requise", wx.OK | wx.ICON_WARNING, self)
            return
        try:
            debut = self._DateSaisie(self.date_debut)
            fin = self._DateSaisie(self.date_fin)
            if debut is None:
                raise UTILS_Suivi_fiches.ControleFicheInvalide(
                    u"Renseignez la date de début indiquée sur le justificatif."
                )
            source = self._Source()
            if source is None:
                raise UTILS_Suivi_fiches.ControleFicheInvalide(
                    u"Indiquez si le document vient de Pièces ou du papier."
                )
            utilisateur = UTILS_Identification.GetIDutilisateur()
            if type(utilisateur) is not int or utilisateur <= 0:
                raise UTILS_Suivi_fiches.ControleFicheInvalide(
                    u"Impossible d'identifier l'utilisateur actif."
                )
        except (reception.ReceptionFicheInvalide,
                UTILS_Suivi_fiches.ControleFicheInvalide) as err:
            wx.MessageBox(str(err), u"Contrôle AEEH", wx.OK | wx.ICON_WARNING, self)
            return
        texte = (
            u"Le justificatif AEEH a-t-il été vérifié ?\n"
            u"La période sera enregistrée immédiatement dans Noethys "
            u"avec son historique, indépendamment du bouton Ok de la fiche."
        )
        if wx.MessageBox(texte, u"Confirmer l'enregistrement AEEH",
                         wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
            return
        try:
            IDperiode = UTILS_Suivi_fiches.EnregistrerPeriodeVerifiee(
                self.IDindividu, utilisateur, debut, fin,
                justificatif_verifie=True, source=source,
                fin_non_precisee_confirmee=self.fin_non_precisee.GetValue(),
            )
        except (UTILS_Suivi_fiches.ControleFicheInvalide,
                UTILS_AEEH_Periodes.PeriodeAEEHInvalide) as err:
            wx.MessageBox(str(err), u"Période AEEH non enregistrée",
                          wx.OK | wx.ICON_WARNING, self)
            return
        except Exception:
            wx.MessageBox(u"Échec de l'enregistrement. Aucun succès n'est présumé : "
                          u"vérifiez l'historique des périodes.",
                          u"Période AEEH à vérifier", wx.OK | wx.ICON_ERROR, self)
            return
        try:
            self.periodes = UTILS_AEEH_Periodes.GetPeriodes(self.IDindividu)
            self.liste_periodes.Set([
                u"Du %s au %s" % (
                    _FormaterDatePeriode(periode["date_debut"]),
                    _FormaterDatePeriode(periode["date_fin"])
                    if periode["date_fin"] is not None else u"terme non indiqué")
                for periode in self.periodes
            ])
        except Exception:
            wx.MessageBox(u"Période enregistrée, mais impossible de rafraîchir "
                          u"la liste. Rouvrez la fiche avant un nouvel ajout.",
                          u"Relecture nécessaire", wx.OK | wx.ICON_WARNING, self)
            self.bouton_periode.Enable(False)
            return
        wx.MessageBox(u"Période AEEH n°%d enregistrée et historisée. "
                      u"Le statut Oui/Non reste indépendant." % IDperiode,
                      u"Période AEEH", wx.OK | wx.ICON_INFORMATION, self)

    def OnHistoriserParent(self, event):
        """Historique de réception, jamais validation vaccinale ou de PAI."""
        from Utils import UTILS_Suivi_fiches, UTILS_Identification
        if not self.relecture.GetValue() or not self.fiche_signee.GetValue():
            wx.MessageBox(u"Vérifiez que la fiche a été relue et signée.",
                          u"Contrôle incomplet", wx.OK | wx.ICON_WARNING, self)
            return
        rubriques = [
            code for i, (code, label) in enumerate(RUBRIQUES_SANTE)
            if self.rubriques_sante.IsChecked(i)
        ]
        try:
            source = self._Source()
            if source is None:
                raise UTILS_Suivi_fiches.ControleFicheInvalide(
                    u"Indiquez le support du document."
                )
            date_parent = self._DateSaisie(self.date_signature)
            utilisateur = UTILS_Identification.GetIDutilisateur()
            if type(utilisateur) is not int or utilisateur <= 0:
                raise UTILS_Suivi_fiches.ControleFicheInvalide(
                    u"Impossible d'identifier l'utilisateur actif."
                )
            if not rubriques:
                raise UTILS_Suivi_fiches.ControleFicheInvalide(
                    u"Cochez les rubriques réellement confirmées par la famille."
                )
        except (reception.ReceptionFicheInvalide,
                UTILS_Suivi_fiches.ControleFicheInvalide) as err:
            wx.MessageBox(str(err), u"Confirmation parentale",
                          wx.OK | wx.ICON_WARNING, self)
            return
        if wx.MessageBox(
                u"Historiser cette réception parentale ?\n"
                u"Cela ne valide ni les vaccinations obligatoires ni le PAI.",
                u"Confirmer la réception", wx.YES_NO | wx.ICON_QUESTION,
                self) != wx.YES:
            return
        try:
            UTILS_Suivi_fiches.EnregistrerConfirmationParentale(
                self.IDindividu, utilisateur, rubriques,
                source=source, fiche_signee=True, document_relu=True,
                date_parent=date_parent,
            )
        except UTILS_Suivi_fiches.ControleFicheInvalide as err:
            wx.MessageBox(str(err), u"Confirmation refusée",
                          wx.OK | wx.ICON_WARNING, self)
            return
        except Exception:
            wx.MessageBox(u"Enregistrement incertain : vérifiez l'historique "
                          u"de la fiche avant de recommencer.",
                          u"Confirmation à vérifier", wx.OK | wx.ICON_ERROR, self)
            return
        self._RafraichirConfirmation()
        wx.MessageBox(u"Réception parentale historisée. "
                      u"Les informations médicales restent à vérifier "
                      u"dans l'onglet Médical.", u"Confirmation parentale",
                      wx.OK | wx.ICON_INFORMATION, self)
