# -*- coding: utf-8 -*-
"""Attente visuellement historique, rattachée à sa fenêtre et sans activation.

wxBusyInfo construit un wxFrame STAY_ON_TOP sans FRAME_FLOAT_ON_PARENT :
son parent Python n'est pas son owner Win32 (wxWidgets 3.2 busyinfo.cpp et
msw/toplevel.cpp). Conserver la même fenêtre simple et son agencement,
mais lui donner un propriétaire et la montrer sans changer le focus.
"""
import wx
import weakref
import threading


def Executer(travail, fenetre_attente=None, nom_thread="Noethys-Travail-attente"):
    """Exécute un travail sans widgets pendant que wx traite les événements."""
    if not wx.IsMainThread():
        raise RuntimeError("Attente reactive hors du thread wx")
    termine = threading.Event()
    erreurs, resultats = [], []
    def effectuer():
        try:
            resultats.append(travail())
        except BaseException as erreur:
            erreurs.append(erreur)
        finally:
            termine.set()
    boucle = wx.GUIEventLoop()
    timer = wx.Timer()
    timer.Bind(wx.EVT_TIMER, lambda event: boucle.Exit() if termine.is_set() else None)
    thread = threading.Thread(target=effectuer, name=nom_thread, daemon=False)
    try:
        with wx.EventLoopActivator(boucle), wx.WindowDisabler(fenetre_attente):
            timer.Start(25)
            thread.start()
            while not termine.is_set():
                boucle.Run()
    finally:
        timer.Stop()
        timer.Unbind(wx.EVT_TIMER)
        if thread.ident is not None:
            thread.join()
    del timer, boucle
    if erreurs:
        raise erreurs.pop()
    return resultats[0]


def LireSQL(lecture, parent, message):
    """Capture le fichier sur wx ; ouvre, lit et ferme la connexion dans le worker."""
    import GestionDB
    from Utils import UTILS_Fichiers
    if not wx.IsMainThread():
        raise RuntimeError("Lecture SQL avec attente hors du thread wx")
    nom = GestionDB.DB.GetNomFichierDefaut(None)
    options = {}
    if "[RESEAU]" not in nom:
        suffixe = "TDATA" if GestionDB.MODE_TEAMWORKS else "DATA"
        nom = UTILS_Fichiers.GetRepData(u"%s_%s.dat" % (nom, suffixe))
        options["suffixe"] = None
    def effectuer():
        db = GestionDB.DB(nomFichier=nom, **options)
        try:
            return lecture(db)
        finally:
            db.Close()
    with BusyInfo(message, parent) as attente:
        return Executer(effectuer, attente.GetWindow())


def _ParentVisible(parent):
    if parent is None:
        parent = wx.GetActiveWindow()
        if parent is None and wx.GetApp() is not None:
            parent = wx.GetApp().GetTopWindow()
    while parent is not None:
        fenetre = wx.GetTopLevelParent(parent)
        if fenetre.IsShownOnScreen():
            return fenetre
        parent = fenetre.GetParent()
    return None


class BusyInfo:
    """Même API message/parent et même présentation que les attentes existantes."""
    def __init__(self, msg, parent=None):
        self._fenetre = None
        self._fermee = False
        if wx.IsMainThread():
            self._CreerFenetre(msg, parent)
        else:
            reference = weakref.ref(self)
            def creer():
                attente = reference()
                if attente is not None:
                    attente._CreerFenetre(msg, parent)
            wx.CallAfter(creer)

    def _CreerFenetre(self, msg, parent):
        if self._fermee:
            return
        if parent is not None and not parent:
            return
        owner = _ParentVisible(parent)
        style = wx.SIMPLE_BORDER | wx.FRAME_TOOL_WINDOW | wx.FRAME_NO_TASKBAR
        if owner is not None:
            style |= wx.FRAME_FLOAT_ON_PARENT
        fenetre = wx.Frame(owner, title='', style=style)
        self._fenetre = fenetre
        try:
            panneau = wx.Panel(fenetre)
            boite = wx.BoxSizer(wx.VERTICAL)
            boite.AddStretchSpacer()
            self._texte = wx.StaticText(panneau, label='', style=wx.ALIGN_CENTRE)
            self._texte.SetLabelText(msg)
            boite.Add(self._texte, wx.SizerFlags().DoubleBorder().Centre())
            boite.AddStretchSpacer()
            panneau.SetSizer(boite)
            taille = panneau.GetBestSize()
            fenetre.SetClientSize((max(400, taille.width), max(80, taille.height)))
            fenetre.Layout()
            fenetre.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
            if parent is None:
                fenetre.CentreOnScreen()
            else:
                rectangle = parent.GetScreenRect()
                taille = fenetre.GetSize()
                fenetre.SetPosition((rectangle.x + (rectangle.width - taille.width) // 2,
                                     rectangle.y + (rectangle.height - taille.height) // 2))
            fenetre.ShowWithoutActivating()
            fenetre.Refresh()
            fenetre.Update()
        except BaseException:
            self.Destroy()
            raise

    def UpdateLabel(self, texte):
        self._Actualiser(texte, False)

    def GetWindow(self):
        return self._fenetre

    def UpdateText(self, texte):
        self._Actualiser(texte, True)

    def _Actualiser(self, texte, markup):
        if not wx.IsMainThread():
            wx.CallAfter(self._Actualiser, texte, markup)
        elif not self._fermee:
            if markup:
                self._texte.SetLabelMarkup(texte)
            else:
                self._texte.SetLabelText(texte)

    def Destroy(self):
        if self._fermee:
            return
        self._fermee = True
        if wx.IsMainThread():
            self._DetruireFenetre()
        else:
            wx.CallAfter(self._DetruireFenetre)

    def _DetruireFenetre(self):
        fenetre = self._fenetre
        self._fenetre = None
        if fenetre:
            fenetre.Hide()
            fenetre.Destroy()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.Destroy()

    def __del__(self):
        try:
            self.Destroy()
        except RuntimeError:
            # Le parent peut déjà avoir détruit son enfant à la fermeture.
            pass
