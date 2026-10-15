# -*- coding: utf-8 -*-
"""Consultation volontaire Mailjet : aucun envoi, aucune relance automatique."""
import queue
import threading
import datetime

import wx

from Utils import UTILS_Suivi_mailjet as Suivi


def DateLocale(valeur):
    if not valeur:
        return 'Jamais'
    try:
        date = datetime.datetime.fromisoformat(valeur)
        return date.astimezone().strftime('%d/%m/%Y %H:%M')
    except (ValueError, TypeError):
        return valeur


def Ouvrir(parent, historiques=()):
    from Utils import UTILS_Utilisateurs
    if not UTILS_Utilisateurs.VerificationDroitsUtilisateurActuel('outils_historique', 'consulter'):
        return
    try:
        journal = Suivi.Journal(Suivi.BaseCourante())
        comptes = journal.Comptes()
        if not comptes:
            raise Suivi.ErreurSuivi("Configurez d'abord un compte d'expédition Mailjet avec ses identifiants API.")
        anciens = Suivi.AnciensMessages(historiques)
    except Exception as error:
        texte = str(error) if isinstance(error, Suivi.ErreurSuivi) else 'Le journal de suivi est inaccessible.'
        wx.MessageBox(texte, 'Suivi Mailjet', wx.OK | wx.ICON_EXCLAMATION, parent)
        return
    dlg = Dialog(parent, journal, comptes, anciens)
    try:
        dlg.ShowModal()
    finally:
        dlg.Arreter()
        dlg.Destroy()


class Dialog(wx.Dialog):
    def __init__(self, parent, journal, comptes, anciens=(), get=None):
        wx.Dialog.__init__(self, parent, title='Suivi Mailjet',
                           style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
        self.journal, self.comptes, self.anciens, self.get = journal, comptes, anciens, get
        self.records = []
        self.resultats = queue.Queue()
        self.arret = threading.Event()
        self.occupe = False
        self.ferme = False
        self.compte = wx.Choice(self, choices=[c['adresse'] for c in comptes])
        self.compte.SetSelection(0)
        self.recherche = wx.SearchCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.recherche.SetDescriptiveText('Rechercher un destinataire ou un sujet')
        self.liste = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_HRULES)
        for titre, largeur in [('Envoi', 155), ('Destinataire', 210), ('Sujet', 240),
                               ('État', 210), ('Dernière vérification', 155)]:
            self.liste.InsertColumn(self.liste.GetColumnCount(), titre, width=largeur)
        self.details = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.details.SetMinSize((-1, 75))
        self.actualiser = wx.Button(self, label='Vérifier la sélection')
        self.recharger = wx.Button(self, label='Recharger le journal')
        self.importer = wx.Button(self, label="Ajouter l'envoi de l'historique")
        self.importer.Show(bool(anciens))
        self.fermer = wx.Button(self, wx.ID_CANCEL, 'Fermer')
        self.info = wx.StaticText(self, label='')
        explication = wx.StaticText(self, label=(
            'Vérification à la demande, par destinataire. « Livré » signifie accepté par le serveur destinataire.\n'
            'Une ouverture signalée ne prouve pas la lecture du message. Aucun renvoi automatique.'))
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(explication, 0, wx.ALL, 12)
        haut = wx.BoxSizer(wx.HORIZONTAL)
        haut.Add(wx.StaticText(self, label="Compte d'expédition :"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        haut.Add(self.compte, 1, wx.RIGHT, 12)
        haut.Add(self.recherche, 1)
        sizer.Add(haut, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 12)
        sizer.Add(self.liste, 1, wx.EXPAND | wx.ALL, 12)
        sizer.Add(self.details, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 12)
        sizer.Add(self.info, 0, wx.ALL, 12)
        boutons = wx.BoxSizer(wx.HORIZONTAL)
        boutons.Add(self.actualiser, 0, wx.RIGHT, 8)
        boutons.Add(self.recharger, 0, wx.RIGHT, 8)
        boutons.Add(self.importer, 0, wx.RIGHT, 8)
        boutons.AddStretchSpacer()
        boutons.Add(self.fermer)
        sizer.Add(boutons, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        self.SetSizer(sizer)
        self.SetMinSize((850, 500))
        self.SetSize((1120, 650))
        self.CenterOnParent()
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.Recevoir, self.timer)
        self.Bind(wx.EVT_BUTTON, self.Verifier, self.actualiser)
        self.Bind(wx.EVT_BUTTON, self.Recharger, self.recharger)
        self.Bind(wx.EVT_BUTTON, self.Importer, self.importer)
        self.Bind(wx.EVT_BUTTON, self.Fermer, self.fermer)
        self.Bind(wx.EVT_CLOSE, self.Fermer)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.Bind(wx.EVT_CHOICE, self.Recharger, self.compte)
        self.Bind(wx.EVT_TEXT, self.Filtrer, self.recherche)
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.Details, self.liste)
        self.Recharger()

    def Compte(self):
        return self.comptes[self.compte.GetSelection()]

    def Recharger(self, event=None):
        try:
            self.records = self.journal.Lister(self.Compte()['compte'])
            self.Filtrer()
            self.info.SetLabel('%d envoi(s) récent(s), au plus 500. Sélectionnez jusqu’à 50 lignes pour vérifier.' % len(self.records))
        except Exception:
            self.info.SetLabel('Lecture du journal impossible. Aucune donnée effacée.')

    def Filtrer(self, event=None):
        terme = self.recherche.GetValue().casefold()
        self.visibles = [r for r in self.records if terme in (r['destinataire'] + ' ' + r['sujet']).casefold()]
        self.liste.DeleteAllItems()
        self.details.SetValue('')
        for r in self.visibles:
            index = self.liste.InsertItem(self.liste.GetItemCount(), DateLocale(r['date_envoi']))
            for col, texte in enumerate((r['destinataire'] or 'À retrouver auprès de Mailjet', r['sujet'],
                                          Suivi.Libelle(r['etat']) + (' — vérification impossible' if r['erreur_consultation'] else ''),
                                          DateLocale(r['verifie_le'])), 1):
                self.liste.SetItem(index, col, texte)

    def Details(self, event=None):
        index = self.liste.GetFirstSelected()
        if index < 0:
            return
        r = self.visibles[index]
        self.details.SetValue('Message Mailjet : %s\nÉvénement observé : %s\n%s\n%s' % (
            r['message_id'], DateLocale(r['evenement_le']) if r['evenement_le'] else 'Non consulté',
            r['detail'], r['erreur_consultation']))

    def Verifier(self, event=None):
        if self.occupe or self.ferme:
            return
        indices, index = [], self.liste.GetFirstSelected()
        while index != -1:
            indices.append(index)
            index = self.liste.GetNextSelected(index)
        if not 1 <= len(indices) <= 50:
            self.info.SetLabel('Sélectionnez entre 1 et 50 envois à vérifier.')
            return
        self.occupe = True
        self.erreur_ecriture = False
        for ctrl in (self.actualiser, self.recharger, self.importer, self.compte, self.recherche):
            ctrl.Disable()
        self.info.SetLabel('Consultation de Mailjet en cours… Vous pouvez fermer cette fenêtre.')
        self.timer.Start(150)
        threading.Thread(target=Suivi.Actualiser,
                         args=([self.visibles[i] for i in indices], self.Compte()['auth'], self.resultats, self.arret),
                         kwargs={'get': self.get}, daemon=True).start()

    def Recevoir(self, event=None):
        if self.ferme:
            return
        while True:
            try:
                item = self.resultats.get_nowait()
            except queue.Empty:
                return
            if item is None:
                self.timer.Stop()
                self.occupe = False
                for ctrl in (self.actualiser, self.recharger, self.importer, self.compte, self.recherche):
                    ctrl.Enable()
                self.Recharger()
                if getattr(self, 'erreur_ecriture', False):
                    self.info.SetLabel('Résultats partiellement enregistrés : journal indisponible. Recharger avant de vérifier à nouveau.')
                return
            record, resultat, erreur = item
            try:
                # CAS : une consultation concurrente ne doit pas etre ecrasee.
                self.journal.SauverResultat(record, resultat, erreur)
            except Exception:
                self.erreur_ecriture = True

    def Importer(self, event=None):
        if self.occupe:
            return
        # L'historique ancien n'identifie pas le compte : choix explicite requis.
        texte = ("Associer les identifiants de l'historique au compte « %s » ?\n"
                 'Choisissez le compte qui a réellement envoyé ces messages. Le destinataire sera vérifié auprès de Mailjet.') % self.Compte()['adresse']
        if wx.MessageBox(texte, 'Reprise du suivi', wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self) != wx.YES:
            return
        try:
            for r in self.anciens:
                self.journal.Enregistrer(self.Compte()['auth'][0], self.Compte()['adresse'], r['sujet'],
                                         [('', '', r['message_id'])], date_envoi=r['date_envoi'], ancien=True)
            self.Recharger()
        except Exception:
            self.info.SetLabel("Reprise interrompue. Les messages déjà repris sont conservés ; aucun email n'a été envoyé.")

    def Arreter(self):
        self.ferme = True
        self.arret.set()
        self.timer.Stop()

    def Fermer(self, event=None):
        self.Arreter()
        if self.IsModal():
            self.EndModal(wx.ID_CANCEL)
        else:
            self.Destroy()

    def OnDestroy(self, event):
        if event.GetEventObject() is self:
            self.Arreter()
        event.Skip()
