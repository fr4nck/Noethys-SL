# -*- coding: utf-8 -*-
"""Consultation volontaire et activation explicite du suivi d'assiduité."""
import datetime as dt
import wx
import GestionDB
from Ctrl import CTRL_Saisie_date, CTRL_Selection_activites
from Utils import UTILS_Assiduite as stats
from Utils import UTILS_Identification, UTILS_Titulaires


EXPLANATION = (
    "Une journée = un enfant, une date et une activité (matin, repas et après-midi regroupés).\n"
    "Annulations = journées suivies dont toutes les réservations confirmées ont été supprimées / journées réservées suivies.\n"
    "Absences = journées entièrement absentes / journées entièrement pointées. Les absences partielles restent séparées.\n"
    "Les annulations tardives transformées en absence suivent l'état Noethys. Les suppressions administratives sont incluses."
)


def percent(value):
    return '—' if value is None else ('%.1f %%' % value).replace('.', ',')


class Dialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title='Annulations et absences par famille et enfant',
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.report = None
        self.rows = []
        self.names = {}
        self.families = {}
        self.start = CTRL_Saisie_date.Date2(self)
        self.end = CTRL_Saisie_date.Date2(self)
        today = dt.date.today()
        self.start.SetDate(today.replace(day=1))
        self.end.SetDate(today)
        self.activities = CTRL_Selection_activites.CTRL(self)
        self.activities.SetMinSize((220, 100))
        self.group = wx.Choice(self, choices=['Par enfant', 'Par famille'])
        self.group.SetSelection(0)
        self.refresh = wx.Button(self, label='Afficher')
        self.enable = wx.Button(self, label='Activer le suivi des nouvelles réservations…')
        self.notice = wx.StaticText(self, label='Annulations : historique non suivi. Choisissez une période et les activités.')
        self.list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        columns = [('Famille / enfant', 260), ('Réservées suivies', 115), ('Annulées', 80),
                   ('Annulations %', 100), ('Pointées', 75), ('Abs. just.', 75),
                   ('Abs. injust.', 80), ('Absences %', 95), ('Abs. partielles', 100), ('Non pointées', 100)]
        for i, (label, width) in enumerate(columns):
            self.list.InsertColumn(i, label, width=width)
        self.detail = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.detail.SetMinSize((-1, 110))
        help_text = wx.StaticText(self, label=EXPLANATION)
        sizer = wx.BoxSizer(wx.VERTICAL)
        filters = wx.BoxSizer(wx.HORIZONTAL)
        for label, control in [('Du', self.start), ('au', self.end), ('Affichage', self.group)]:
            filters.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
            filters.Add(control, 0, wx.RIGHT, 12)
        filters.Add(self.refresh)
        sizer.Add(filters, 0, wx.ALL, 8)
        sizer.Add(self.activities, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        sizer.Add(self.notice, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        sizer.Add(self.detail, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(help_text, 0, wx.ALL, 8)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        buttons.Add(self.enable)
        buttons.AddStretchSpacer()
        buttons.Add(wx.Button(self, wx.ID_CANCEL, 'Fermer'))
        sizer.Add(buttons, 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(sizer)
        self.SetSize((1220, 760))
        self.SetMinSize((950, 650))
        self.Bind(wx.EVT_BUTTON, self.OnRefresh, self.refresh)
        self.Bind(wx.EVT_BUTTON, self.OnEnable, self.enable)
        self.Bind(wx.EVT_CHOICE, self.OnGroup, self.group)
        self.list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnDetail)
        # Modifier le schéma demande un profil administrateur, pas le simple droit de consultation.
        self.enable.Enable(self.is_admin())

    @staticmethod
    def is_admin():
        return str((UTILS_Identification.GetDictUtilisateur() or {}).get('profil', '')).startswith('administrateur')

    def OnRefresh(self, event=None):
        self.report = None
        self.rows = []
        self.list.DeleteAllItems()
        self.detail.Clear()
        db = None
        try:
            start, end = self.start.GetDate(), self.end.GetDate()
            ids = self.activities.GetActivites()
            stats.period(start, end, ids)
            db = GestionDB.DB()
            report = stats.read(db, start, end, ids)
            self.names = {ident: ' '.join(str(v or '') for v in (nom, prenom)).strip()
                          for ident, nom, prenom in stats.query(db, 'SELECT IDindividu, nom, prenom FROM individus')}
            self.families = UTILS_Titulaires.GetTitulaires()
            self.report = report
            enabled = report['enabled']
            self.notice.SetLabel(('Annulations : nouvelles réservations suivies depuis le %s UTC. Historique antérieur non couvert.' % enabled[1])
                                 if enabled else 'Annulations : non disponibles avant activation du suivi. Absences : pointages existants.')
            self.OnGroup()
        except Exception as exc:
            self.notice.SetLabel('Résultats indisponibles : vérifiez la période et la connexion.')
            wx.MessageBox(str(exc), 'Assiduité', wx.OK | wx.ICON_ERROR, self)
        finally:
            if db is not None:
                db.Close()

    def label(self, row):
        family = self.families.get(row['family'], {}).get('titulairesSansCivilite') or 'Famille %s' % row['family']
        if row['child'] is not None:
            return '%s — %s' % (self.names.get(row['child'], 'Enfant %s' % row['child']), family)
        return family

    def OnGroup(self, event=None):
        self.list.DeleteAllItems()
        self.detail.Clear()
        if self.report is None:
            return
        self.rows = sorted(self.report['families' if self.group.GetSelection() else 'children'], key=self.label)
        for row in self.rows:
            i = self.list.InsertItem(self.list.GetItemCount(), self.label(row))
            values = [row['reserved'] if self.report['enabled'] else '—', row['cancelled'] if self.report['enabled'] else '—',
                      percent(row['cancellation_rate']), row['pointed'], row['justified'], row['unjustified'],
                      percent(row['absence_rate']), row['partial'], row['pending']]
            for col, value in enumerate(values, 1):
                self.list.SetItem(i, col, str(value))

    def OnDetail(self, event):
        row = self.rows[event.GetIndex()]
        lines = []
        for d in sorted(row['details'], key=lambda v: (v['date'], v['activity'])):
            child = self.names.get(d.get('child', row['child']), '')
            lines.append('%s | %s | Activité %s | %s | Annulations : %s' %
                         (d['date'], child, d['activity'], d['category'], 'suivie' if d['tracked'] else 'hors historique suivi'))
        self.detail.SetValue('\n'.join(lines))

    def OnEnable(self, event=None):
        if not self.is_admin():
            return
        message = (
            "Activer le suivi sur ce fichier ?\n\n"
            "Cette action ajoute un journal et trois déclencheurs à la base. Ils enregistreront les nouvelles réservations "
            "et leurs changements, y compris depuis d'autres postes. Aucune réservation existante n'est modifiée.\n\n"
            "L'ancien historique ne sera pas reconstitué. Une panne du journal empêchera la modification concernée "
            "de s'enregistrer plutôt que de perdre son historique. À qualifier d'abord sur une copie isolée."
        )
        if wx.MessageBox(message, 'Activer le suivi — modification explicite du schéma', wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self) != wx.YES:
            return
        db = None
        try:
            db = GestionDB.DB()
            marker = stats.activate(db)
            self.notice.SetLabel('Suivi activé depuis le %s UTC. Cliquez sur Afficher.' % marker[1])
        except Exception as exc:
            wx.MessageBox(str(exc), 'Activation impossible', wx.OK | wx.ICON_ERROR, self)
        finally:
            if db is not None:
                db.Close()
