# -*- coding: utf-8 -*-
"""UI-432K : lecture longue sur worker sans manipulation wx depuis le worker.

Uniquement pour des lectures/calculs. Les connexions SQL sont creees et
fermees dans leur propre thread. Une annulation ignore le resultat sans tuer
le thread ou interrompre la requete SQL en cours.
"""
import queue
import sys
import threading
import wx
from Utils.UTILS_Traduction import _


class LectureAnnulee(Exception):
    """Le resultat de cette lecture ne doit plus etre utilise."""


class DialogueLecture(wx.Dialog):
    def __init__(self, parent, resultats, titre, texte):
        super().__init__(parent, title=titre, style=wx.DEFAULT_DIALOG_STYLE)
        self.resultats = resultats
        self.resultat = None
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(self, label=texte), 0, wx.ALL, 15)
        self.gauge = wx.Gauge(self, range=100, size=(320, -1))
        sizer.Add(self.gauge, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        self.bouton_annuler = wx.Button(self, wx.ID_CANCEL, _(u"Annuler"))
        sizer.Add(self.bouton_annuler, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 15)
        self.SetSizerAndFit(sizer)
        self.CentreOnParent()
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._tick, self.timer)
        self.Bind(wx.EVT_BUTTON, self._annuler, self.bouton_annuler)
        self.Bind(wx.EVT_CLOSE, self._fermer)

    def _tick(self, event):
        try:
            self.resultat = self.resultats.get_nowait()
        except queue.Empty:
            self.gauge.Pulse()
        else:
            self.timer.Stop()
            if self.IsModal():
                self.EndModal(wx.ID_OK)

    def _annuler(self, event):
        if self.IsModal():
            self.EndModal(wx.ID_CANCEL)

    def _fermer(self, event):
        if self.IsModal():
            self.EndModal(wx.ID_CANCEL)
        else:
            event.Skip()


def ExecuterLecture(parent, travail, *, titre, texte):
    """Lecture asynchrone avec modale reactive et proprietaire explicite.

    Le worker ne connait aucun widget ; meme la communication de resultat
    n'utilise pas wx.CallAfter. Seule la GUI interroge la file via son timer.
    Apres annulation, le worker termine et ferme ses ressources en interne.
    Ne jamais passer une operation d'ecriture ou un objet wx a ce moteur.
    """
    if not wx.IsMainThread():
        raise RuntimeError("Lecture longue appelee hors du thread wx")
    if parent is None or not parent.IsShownOnScreen():
        raise RuntimeError("Un proprietaire affiche est necessaire")

    resultats = queue.Queue(maxsize=1)
    dialogue = DialogueLecture(parent, resultats, titre, texte)

    def calculer():
        try:
            valeur = travail()
        except BaseException:
            fin = ("erreur", sys.exc_info())
        else:
            fin = ("ok", valeur)
        resultats.put_nowait(fin)

    worker = threading.Thread(target=calculer,
                              name="Noethys-Lecture-UI432K", daemon=True)
    try:
        worker.start()
        dialogue.timer.Start(40)
        code = dialogue.ShowModal()
        if code != wx.ID_OK:
            raise LectureAnnulee()
        if dialogue.resultat is None:
            raise RuntimeError("Fin de lecture sans resultat")
        etat, valeur = dialogue.resultat
        if etat == "erreur":
            _, erreur, trace = valeur
            raise erreur.with_traceback(trace)
        return valeur
    finally:
        dialogue.timer.Stop()
        dialogue.Destroy()
