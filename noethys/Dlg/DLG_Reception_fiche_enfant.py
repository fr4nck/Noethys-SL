# -*- coding: utf-8 -*-
"""Relecture manuelle d'une fiche enfant Pêle-Mêle deja recue (#436).

Aucune lecture de document ni ecriture SQL : la fiche originale est consultee
auparavant dans l'onglet Pieces. La proposition AEEH est appliquee au controle
d'Identite SEULEMENT ; le bouton Ok de la fiche individuelle garde la maitrise
de l'enregistrement. Les informations medicales sont a verifier dans l'onglet
Medical, jamais extraire d'un PDF automatiquement.
"""
import wx
from Utils import UTILS_Reception_fiches as reception


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
            panneau, label=u"Périodes AEEH déjà enregistrées : %d (non modifiées ici)." % len(periodes)
        ), 0, wx.ALL, 8)
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
        self.bouton_reporter = wx.Button(panneau, wx.ID_OK, u"Reporter la réponse AEEH")
        boutons.Add(bouton_annuler, 0, wx.RIGHT, 8)
        boutons.Add(self.bouton_reporter, 0)
        vertical.Add(boutons, 0, wx.EXPAND | wx.ALL, 8)
        panneau.SetSizer(vertical)
        enveloppe = wx.BoxSizer(wx.VERTICAL)
        enveloppe.Add(panneau, 1, wx.EXPAND)
        self.SetSizerAndFit(enveloppe)
        self.SetMinSize((560, 320))
        self.Bind(wx.EVT_BUTTON, self.OnReporter, self.bouton_reporter)

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
        self._valeur_proposee = resultat["valeur_proposee"]
        self.EndModal(wx.ID_OK)

    def GetValeurProposee(self):
        return self._valeur_proposee
