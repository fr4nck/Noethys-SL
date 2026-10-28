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

        panneau = wx.Panel(self)
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
        liste_periodes = wx.ListBox(panneau, choices=lignes, size=(-1, 65))
        vertical.Add(liste_periodes, 0, wx.ALL | wx.EXPAND, 8)

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
        enveloppe = wx.BoxSizer(wx.VERTICAL)
        enveloppe.Add(panneau, 1, wx.EXPAND)
        self.SetSizerAndFit(enveloppe)
        self.SetMinSize((660, 495))
        self.Bind(wx.EVT_BUTTON, self.OnReporter, self.bouton_reporter)
        self.Bind(wx.EVT_BUTTON, self.OnOuvrirMedical, self.bouton_medical)

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
