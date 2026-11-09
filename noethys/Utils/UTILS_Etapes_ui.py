# -*- coding: utf-8 -*-
"""Etapes cooperatives wx, sans worker ni yield au milieu d'une ecriture SQL."""
import os
import sys
import time
import wx
from Utils.UTILS_Traduction import _


class Attente(wx.Dialog):
    def __init__(self, parent, etapes, *, titre=None, texte=None, total=None):
        super().__init__(
            parent, title=titre if titre is not None else _(u"Traitement des demandes"),
            style=wx.DEFAULT_DIALOG_STYLE & ~wx.CLOSE_BOX)
        self.etapes = iter(etapes)
        self.total = max(1, int(total)) if total is not None else None
        self.progression = 0
        self.erreur = None
        self.termine = False
        self.en_cours = False
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(
            self, label=texte if texte is not None
            else _(u"Chargement de la grille en cours…")),
            0, wx.ALL, 18)
        self.gauge = wx.Gauge(self, range=self.total or 100, size=(320, -1))
        sizer.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 18)
        self.SetSizerAndFit(sizer)
        self.CentreOnParent()
        self.Bind(wx.EVT_CLOSE, self._refuser_fermeture)
        self.Bind(wx.EVT_CHAR_HOOK, self._touche)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._etape, self.timer)

    def _refuser_fermeture(self, event):
        if event.CanVeto():
            event.Veto()

    def _touche(self, event):
        if event.GetKeyCode() != wx.WXK_ESCAPE:
            event.Skip()

    def _etape(self, event):
        if self.en_cours:
            return
        self.en_cours = True
        termine = False
        debut = time.monotonic() if os.environ.get("NOETHYS_SL_UI_DIAG") == "1" else None
        etape = "grille.finalisation"
        try:
            etape = next(self.etapes)
            if self.total is None:
                self.gauge.Pulse()
            else:
                self.progression += 1
                self.gauge.SetValue(min(self.total, self.progression))
        except StopIteration:
            self.termine = True
            termine = True
        except BaseException:
            etape = "grille.erreur"
            self.erreur = sys.exc_info()
            termine = True
        finally:
            self.en_cours = False
            if debut is not None:
                try:
                    from Utils import UTILS_Diagnostic_ui as diagnostic
                    if etape == "factures.generation_pdf":
                        diagnostic.tracer_etape_facture(
                            etape, (time.monotonic() - debut) * 1000)
                    elif etape == "statistiques.objet":
                        diagnostic.tracer_etape_statistiques(
                            etape, (time.monotonic() - debut) * 1000)
                    else:
                        diagnostic.tracer_etape_grille(
                            etape, (time.monotonic() - debut) * 1000)
                except Exception:
                    pass
        if termine:
            self.timer.Stop()
            self.EndModal(wx.ID_OK)


def Executer(parent, etapes, *, titre=None, texte=None, total=None):
    """Retourne entre deux traitements; toutes les etapes restent sur le thread wx.

    Le generateur ferme ses connexions en finally. La fenetre modale desactive
    ses proprietaires : pas de navigation/envoi pendant la grille incomplete.
    Ne jamais fournir une sequence qui coupe une sauvegarde ou un commit.
    """
    if not wx.IsMainThread():
        raise RuntimeError("Etapes UI hors du thread wx")
    if titre is None and texte is None and total is None:
        # Garder l'appel a deux arguments pour les fixtures wx historiques.
        dialogue = Attente(parent, etapes)
    else:
        dialogue = Attente(parent, etapes, titre=titre, texte=texte, total=total)
    try:
        dialogue.timer.Start(15)
        dialogue.ShowModal()
        if dialogue.erreur is not None:
            _, erreur, trace = dialogue.erreur
            raise erreur.with_traceback(trace)
        if not dialogue.termine:
            raise RuntimeError("Chargement de la grille interrompu")
    finally:
        dialogue.timer.Stop()
        try:
            dialogue.etapes.close()
        finally:
            dialogue.Destroy()
