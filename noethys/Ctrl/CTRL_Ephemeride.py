# -*- coding: utf-8 -*-
"""Éphémérides de l'accueil. Licence GNU GPL.

Le réseau et les lectures DB travaillent hors du thread wx. Aucun contrôle wx
ni paramètre utilisateur n'est consulté par ces tâches.
"""
import copy
import datetime as dt
import json
import hashlib
import threading

import wx
import wx.adv
import wx.lib.scrolledpanel
import wx.grid
from Ctrl import CTRL_Accueil_compact as compact
from Utils import UTILS_Accueil_jour as programme

import GestionDB
from Utils import UTILS_Config
from Utils import UTILS_Parametres
from Utils import UTILS_Ephemerides as data
from Utils import UTILS_VacancesScolaires as school

JOURS = ('Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche')
MOIS = ('janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
        'septembre', 'octobre', 'novembre', 'décembre')
BLOCK_LABELS = {
    'weather': 'Météo',
    'vacations': 'Vacances scolaires',
    'events': 'Événements',
}


def DateDDEnDateFR(date):
    return '%s %d %s %d' % (JOURS[date.weekday()], date.day, MOIS[date.month - 1], date.year)


def link(parent, label, url):
    control = wx.adv.HyperlinkCtrl(parent, label=label if len(label) <= 46 else label[:43] + '…', url=url)
    control.SetToolTip(label + '\n' + url)
    control.SetNormalColour(compact.TEAL)
    control.SetVisitedColour(compact.TEAL)
    link_font = control.GetFont()
    link_font.SetUnderlined(False)
    control.SetFont(link_font)
    return control


def section(parent, title):
    box = wx.BoxSizer(wx.VERTICAL)
    heading = wx.StaticText(parent, label=title)
    heading.SetForegroundColour(compact.MUTED)
    heading.SetFont(compact.font(heading, -1, True))
    heading.SetMinSize((-1, parent.FromDIP(24)))
    parent.heading = heading
    box.Add(heading, 0, wx.EXPAND | wx.LEFT | wx.TOP, 8)
    return box


class Settings(wx.Dialog):
    def __init__(self, parent, settings, layout, activities=None):
        super().__init__(parent, title="Réglages d’Aujourd’hui",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.events = copy.deepcopy(settings.get('events', []))
        self.fields = {}
        self.layout = data.normalize_dashboard_layout(layout)
        self.layout_controls = {}

        base = wx.BoxSizer(wx.VERTICAL)
        book = wx.Notebook(self)

        # Affichage personnel -------------------------------------------------
        display = wx.Panel(book)
        display_sizer = wx.BoxSizer(wx.VERTICAL)
        display_sizer.Add(wx.StaticText(
            display,
            label="Cet affichage est mémorisé pour l’identifiant utilisateur connecté et suit la base Noethys."
        ), 0, wx.EXPAND | wx.ALL, 10)

        line = wx.BoxSizer(wx.HORIZONTAL)
        line.Add(wx.StaticText(display, label='Nombre de colonnes'), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self.columns = wx.Choice(display, choices=['1', '2', '3', '4'])
        self.columns.SetSelection(self.layout['columns'] - 1)
        line.Add(self.columns)
        display_sizer.Add(line, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        grid = wx.FlexGridSizer(cols=4, vgap=6, hgap=10)
        grid.Add(wx.StaticText(display, label='Bloc'))
        grid.Add(wx.StaticText(display, label='Afficher'))
        grid.Add(wx.StaticText(display, label='Colonne'))
        grid.Add(wx.StaticText(display, label='Ordre'))
        for key in data.DASHBOARD_BLOCKS:
            block = self.layout['blocks'][key]
            grid.Add(wx.StaticText(display, label=BLOCK_LABELS[key]), 0, wx.ALIGN_CENTER_VERTICAL)
            visible = wx.CheckBox(display)
            visible.SetValue(block['visible'])
            column = wx.SpinCtrl(display, min=1, max=4, initial=block['column'], size=(70, -1))
            order = wx.SpinCtrl(display, min=1, max=20, initial=block['order'], size=(70, -1))
            self.layout_controls[key] = (visible, column, order)
            grid.Add(visible, 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(column, 0)
            grid.Add(order, 0)
        display_sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 10)
        display_sizer.Add(wx.StaticText(
            display,
            label="Chaque bloc visible peut être placé dans la colonne choisie. L’ordre départage les blocs d’une même colonne."
        ), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        display.SetSizer(display_sizer)
        book.AddPage(display, 'Mon affichage')

        day_page = wx.Panel(book)
        day_sizer = wx.BoxSizer(wx.VERTICAL)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(day_page, label='Événements : nombre à afficher (0 = tous)'), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.event_count = wx.TextCtrl(day_page, value=str(self.layout['day']['event_count']), size=(80, -1))
        row.Add(self.event_count)
        day_sizer.Add(row, 0, wx.ALL, 10)
        day_sizer.Add(wx.StaticText(day_page, label='Bandeau : activités actives avec une ouverture, une séance ou une consommation ce jour.\nM/A : accueil de loisirs, effectifs réservés ou présents par demi-journée.\nOrdre 0 : accueils de loisirs prioritaires. Un ordre personnel passe en premier.'), 0, wx.ALL, 10)
        self.activities = activities or []
        self.activity_grid = wx.grid.Grid(day_page)
        self.activity_grid.CreateGrid(len(self.activities), 6)
        for col, label in enumerate(('Afficher', 'M/A', 'Ordre', 'Activité', 'Unité matin', 'Unité après-midi')):
            self.activity_grid.SetColLabelValue(col, label)
        for index, item in enumerate(self.activities):
            option = self.layout['day']['activities'].get(str(item['id']), item)
            for col, key in ((0, 'visible'), (1, 'alsh')):
                self.activity_grid.SetCellRenderer(index, col, wx.grid.GridCellBoolRenderer())
                self.activity_grid.SetCellEditor(index, col, wx.grid.GridCellBoolEditor())
                self.activity_grid.SetCellValue(index, col, '1' if option[key] else '')
            self.activity_grid.SetCellEditor(index, 2, wx.grid.GridCellNumberEditor(0, 1000000))
            self.activity_grid.SetCellValue(index, 2, str(option['order']))
            self.activity_grid.SetCellValue(index, 3, item['name'])
            self.activity_grid.SetReadOnly(index, 3)
            for col,key in ((4,'morning_unit'),(5,'afternoon_unit')):
                choices = item.get('slot_choices', [])
                self.activity_grid.SetCellEditor(index,col,wx.grid.GridCellChoiceEditor(['Automatique']+[s['label'] for s in choices]))
                selected = next((s['label'] for s in choices if s['id']==option.get(key)), 'Automatique')
                self.activity_grid.SetCellValue(index,col,selected)
        self.activity_grid.SetColSize(3, 220)
        self.activity_grid.SetColSize(4, 140)
        self.activity_grid.SetColSize(5, 160)
        day_sizer.Add(self.activity_grid, 1, wx.EXPAND | wx.ALL, 10)
        day_page.SetSizer(day_sizer)
        book.AddPage(day_page, 'Programme et agenda')

        # Sources et contenu commun ------------------------------------------
        sources = wx.Panel(book)
        sources_sizer = wx.BoxSizer(wx.VERTICAL)
        source_grid = wx.FlexGridSizer(cols=2, vgap=6, hgap=10)
        source_grid.AddGrowableCol(1)
        for key, label in (('city', 'Ville'), ('postcode', 'Code postal'), ('latitude', 'Latitude (facultatif)'),
                           ('longitude', 'Longitude (facultatif)'),
                           ('agenda', 'Agenda local HTTPS'), ('territories', 'Territoires à afficher (séparés par des virgules)')):
            source_grid.Add(wx.StaticText(sources, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            control = wx.TextCtrl(sources, value=str(settings.get(key, '')))
            self.fields[key] = control
            source_grid.Add(control, 1, wx.EXPAND)
        source_grid.Add(wx.StaticText(sources, label='Zone scolaire'))
        self.zone = wx.Choice(sources, choices=['Automatique', 'A', 'B', 'C'])
        self.zone.SetStringSelection(settings.get('zone', '') or 'Automatique')
        source_grid.Add(self.zone)
        sources_sizer.Add(source_grid, 0, wx.EXPAND | wx.ALL, 12)
        sources_sizer.Add(wx.StaticText(
            sources, label='Événements : vérifier la date et la source avant de les ajouter.'
        ), 0, wx.LEFT | wx.RIGHT, 12)
        self.list = wx.ListBox(sources)
        sources_sizer.Add(self.list, 1, wx.EXPAND | wx.ALL, 12)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        add = wx.Button(sources, label='Ajouter…')
        remove = wx.Button(sources, label='Retirer')
        buttons.Add(add)
        buttons.Add(remove, 0, wx.LEFT, 8)
        sources_sizer.Add(buttons, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        sources.SetSizer(sources_sizer)
        book.AddPage(sources, 'Sources et contenu')

        base.Add(book, 1, wx.EXPAND | wx.ALL, 8)
        base.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 12)
        self.SetSizer(base)
        self.SetMinSize((680, 520))
        self.SetSize((760, 610))
        self.refresh_events()
        self._sync_columns()

        add.Bind(wx.EVT_BUTTON, self.add_event)
        remove.Bind(wx.EVT_BUTTON, self.remove_event)
        self.columns.Bind(wx.EVT_CHOICE, self._sync_columns)
        self.Bind(wx.EVT_BUTTON, self.accept, id=wx.ID_OK)

    def _sync_columns(self, event=None):
        maximum = self.columns.GetSelection() + 1
        for visible, column, order in self.layout_controls.values():
            column.SetMax(maximum)
            if column.GetValue() > maximum:
                column.SetValue(maximum)
        if event:
            event.Skip()

    def refresh_events(self):
        self.list.Set(['%s · %s · %s · %s' % (e['date'], e['kind'], e['title'], e.get('territory', ''))
                       for e in self.events])

    def remove_event(self, event):
        index = self.list.GetSelection()
        if index != wx.NOT_FOUND:
            del self.events[index]
            self.refresh_events()

    def add_event(self, event):
        dialog = wx.Dialog(self, title='Ajouter un événement vérifié')
        base = wx.BoxSizer(wx.VERTICAL)
        controls = {}
        for key, label, default in (('title', 'Titre', ''), ('date', 'Date (AAAA-MM-JJ)', dt.date.today().isoformat()),
                                    ('territory', 'Territoire (commune ou secteur)', ''), ('source', 'Source HTTPS consultée', '')):
            base.Add(wx.StaticText(dialog, label=label), 0, wx.LEFT | wx.TOP, 10)
            controls[key] = wx.TextCtrl(dialog, value=default)
            base.Add(controls[key], 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        kind = wx.Choice(dialog, choices=list(data.KINDS))
        kind.SetStringSelection('Local')
        base.Add(kind, 0, wx.ALL, 10)
        base.Add(dialog.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 10)
        dialog.SetSizerAndFit(base)
        dialog.SetSize((500, dialog.GetSize().height))
        try:
            while dialog.ShowModal() == wx.ID_OK:
                try:
                    value = {key: control.GetValue() for key, control in controls.items()}
                    value['kind'] = kind.GetStringSelection()
                    self.events.append(data.validate_event(value))
                    self.refresh_events()
                    break
                except ValueError as error:
                    wx.MessageBox(str(error), 'Événement incomplet', wx.OK | wx.ICON_INFORMATION, self)
        finally:
            dialog.Destroy()

    def values(self):
        result = {key: control.GetValue().strip() for key, control in self.fields.items()}
        result['zone'] = '' if self.zone.GetSelection() == 0 else self.zone.GetStringSelection()
        result['events'] = self.events
        return result

    def layout_values(self):
        self.activity_grid.SaveEditControlValue()
        try:
            count = int(self.event_count.GetValue())
            if count < 0:
                raise ValueError()
        except ValueError:
            raise ValueError('Le nombre d’événements doit être un entier positif, ou 0 pour tous.')
        activities = dict(self.layout['day']['activities'])
        for index, item in enumerate(self.activities):
            activities[str(item['id'])] = dict(
                visible=self.activity_grid.GetCellValue(index, 0) == '1',
                alsh=self.activity_grid.GetCellValue(index, 1) == '1',
                order=int(self.activity_grid.GetCellValue(index, 2) or 0))
            for col,key in ((4,'morning_unit'),(5,'afternoon_unit')):
                selected=self.activity_grid.GetCellValue(index,col)
                matches=[s['id'] for s in item.get('slot_choices',[]) if s['label']==selected]
                activities[str(item['id'])][key]=matches[0] if len(matches)==1 else None
        blocks = {}
        for key, (visible, column, order) in self.layout_controls.items():
            blocks[key] = {
                'visible': visible.GetValue(),
                'column': column.GetValue(),
                'order': order.GetValue(),
            }
        return data.normalize_dashboard_layout({
            'columns': self.columns.GetSelection() + 1,
            'blocks': blocks,
            'day': dict(event_count=count, activities=activities),
        })

    def accept(self, event):
        values = self.values()
        try:
            self.layout_values()
            if values['latitude'] or values['longitude']:
                data.coordinates(values['latitude'], values['longitude'])
            if values['agenda'] and not data.safe_url(values['agenda']):
                raise ValueError('L’agenda doit être une adresse HTTPS')
        except ValueError as error:
            wx.MessageBox(str(error), 'Réglages à corriger', wx.OK | wx.ICON_INFORMATION, self)
            return
        self.EndModal(wx.ID_OK)


class WeatherDetails(wx.Dialog):
    def __init__(self, parent, rows, stamp):
        super().__init__(parent, title='Prévisions météo · Europe/Paris', style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.rows = rows
        base = wx.BoxSizer(wx.VERTICAL)
        self.days = wx.Choice(self, choices=['7 jours', '10 jours'])
        self.days.SetSelection(0)
        base.Add(self.days, 0, wx.ALL, 10)
        self.text = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP)
        base.Add(self.text, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        base.Add(wx.StaticText(self, label='Open-Meteo · relevé ' + stamp + ' · Prévisions, sans valeur de vigilance officielle.'), 0, wx.ALL, 10)
        base.Add(self.CreateButtonSizer(wx.CLOSE), 0, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(base)
        self.SetSize((800, 550))
        self.days.Bind(wx.EVT_CHOICE, self.render)
        self.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_CLOSE), id=wx.ID_CLOSE)
        self.render()

    def render(self, event=None):
        dates = sorted({row['date'] for row in self.rows})[:7 if self.days.GetSelection() == 0 else 10]
        self.text.SetValue('\n\n'.join('%s · %s\n%s' % (row['date'], row['period'], data.weather_text(row))
                                       for row in self.rows if row['date'] in dates))


class CTRL(wx.lib.scrolledpanel.ScrolledPanel):
    def __init__(self, parent):
        super().__init__(parent, style=wx.TAB_TRAVERSAL)
        # AUI positionne ce panneau avant de l'afficher : évite le flash au démarrage.
        self.Hide()
        self._generation = 0
        self._alive = True
        self._active = True
        self._busy = False
        self._result = {}
        self._settings = {}
        self._layout = data.normalize_dashboard_layout()
        self._layout_signature = None
        self._timer = wx.Timer(self)
        self.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))

        self.base = wx.BoxSizer(wx.VERTICAL)
        self.banner = compact.Bandeau(self)
        self.base.Add(self.banner, 0, wx.EXPAND | wx.BOTTOM, 6)
        self.title = wx.StaticText(self, label=DateDDEnDateFR(dt.date.today()))
        self.title.SetFont(self.title.GetFont().Bold())
        self.title.Hide()  # Libellé accessible historique ; date peinte dans le bandeau.

        self.block_panels = {}

        weather_panel = wx.Panel(self)
        weather_box = section(weather_panel, 'Météo')
        self.weather = compact.Meteo(weather_panel, self.OnDetails)
        weather_box.Add(self.weather, 0, wx.EXPAND | wx.ALL, 8)
        self.detail = self.weather  # Détail au clic / clavier sur tout le bloc.
        self.detail.Enable(False)
        weather_panel.SetSizer(weather_box)
        self.block_panels['weather'] = weather_panel

        vacation_panel = wx.Panel(self)
        vacation_box = section(vacation_panel, 'Vacances')
        self.vacation = wx.StaticText(vacation_panel, label='Chargement…')
        self.vacation.SetMinSize((140, -1))
        vacation_box.Add(self.vacation, 0, wx.EXPAND | wx.ALL, 8)
        vacation_box.Add(link(vacation_panel, 'Calendrier scolaire officiel 2026–2027', data.SCHOOL_SOURCE),
                         0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        vacation_panel.SetSizer(vacation_box)
        self.block_panels['vacations'] = vacation_panel

        events_panel = wx.Panel(self)
        events_box = section(events_panel, 'Agenda')
        self.events_scroll = wx.lib.scrolledpanel.ScrolledPanel(events_panel, size=(-1, self.FromDIP(216)))
        self.events_scroll.SetMinSize((150, self.FromDIP(216)))
        self.events_content = wx.BoxSizer(wx.VERTICAL)
        self.events_scroll.SetSizer(self.events_content)
        events_box.Add(self.events_scroll, 1, wx.EXPAND | wx.ALL, 6)
        events_panel.SetSizer(events_box)
        self.block_panels['events'] = events_panel

        self.dashboard = wx.BoxSizer(wx.HORIZONTAL)
        self.body = wx.BoxSizer(wx.HORIZONTAL)
        self.body.Add(self.dashboard, 1, wx.EXPAND)
        self.connect_box = wx.BoxSizer(wx.VERTICAL)
        self.body.Add(self.connect_box, 0, wx.EXPAND | wx.LEFT, 8)
        self.base.Add(self.body, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.SetSizer(self.base)
        self._apply_layout()
        self.SetupScrolling(scroll_x=False)

        self.Bind(wx.EVT_TIMER, lambda event: self.Initialisation(), self._timer)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.Bind(wx.EVT_SIZE, self.OnSize)

    def AttachConnecthys(self, panel):
        self.connect_box.Add(panel, 0, wx.EXPAND)
        self.Layout()

    def UpdateProgramme(self):
        """Recharge après une modification sans déclencher un appel météo."""
        self.Initialisation()

    def _current_user_id(self):
        try:
            top = wx.GetTopLevelParent(self)
            user = getattr(top, 'dictUtilisateur', None) or {}
            value = user.get('IDutilisateur')
            return int(value) if value is not None else None
        except (AttributeError, TypeError, ValueError):
            return None

    def _load_layout(self, database):
        layout = data.normalize_dashboard_layout()
        user_id = self._current_user_id()
        if not database or user_id is None:
            return layout
        try:
            raw = UTILS_Parametres.Parametres(
                mode='get', categorie='accueil_aujourdhui',
                nom='utilisateur_%s' % user_id, valeur='', nomFichier=database)
            if raw:
                layout = json.loads(raw)
        except Exception:
            # Une préférence personnelle illisible ne doit jamais bloquer l'accueil.
            return data.normalize_dashboard_layout()
        return data.normalize_dashboard_layout(layout)

    def _save_layout(self, layout):
        database = str(UTILS_Config.GetParametre('nomFichier', '') or '')
        user_id = self._current_user_id()
        if not database or user_id is None:
            return False
        layout = data.normalize_dashboard_layout(layout)
        payload = json.dumps(layout, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        try:
            UTILS_Parametres.Parametres(
                mode='set', categorie='accueil_aujourdhui',
                nom='utilisateur_%s' % user_id, valeur=payload, nomFichier=database)
            return True
        except Exception:
            return False

    def _apply_layout(self):
        self._layout = data.normalize_dashboard_layout(self._layout)
        self.dashboard.Clear(delete_windows=False)
        for panel in self.block_panels.values():
            panel.Hide()
        columns = []
        ordered = data.dashboard_columns(self._layout)
        for index in range(self._layout['columns']):
            column = wx.BoxSizer(wx.VERTICAL)
            border = wx.LEFT if index else 0
            self.dashboard.Add(column, 0 if 'weather' in ordered[index] else 1, wx.EXPAND | border, 8 if index else 0)
            columns.append(column)
        for index, keys in enumerate(data.dashboard_columns(self._layout)):
            for key in keys:
                panel = self.block_panels[key]
                panel.Show()
                columns[index].Add(panel, 0, wx.EXPAND | wx.BOTTOM, 8)
        self._wrap_contents()
        self.Layout()
        if self._alive:
            self.SetupScrolling(scroll_x=False)

    def _column_text_width(self):
        columns = max(1, self._layout.get('columns', 1))
        available = max(220, self.GetClientSize().width - 20 - (columns - 1) * 8)
        return max(160, available // columns - 30)

    def _wrap_contents(self):
        width = max(140, self.block_panels['vacations'].GetClientSize().width - 16)
        self.vacation.Wrap(width)

    def OnUserChanged(self):
        """Recharge uniquement la disposition personnelle lors d'un changement d'identifiant."""
        database = str(UTILS_Config.GetParametre('nomFichier', '') or '')
        self._layout = self._load_layout(database)
        self._layout_signature = (database, self._current_user_id())
        self._generation += 1
        self._busy = False
        self.banner.update(dt.date.today(), [])
        self._apply_layout()
        self.Initialisation()

    def OnDestroy(self, event):
        if event.GetEventObject() is self:
            self._alive = False
            self._generation += 1
            self._timer.Stop()
        event.Skip()

    def OnSize(self, event):
        self._wrap_contents()
        event.Skip()

    def StartTicker(self):
        self._active = True
        self._timer.Start(5 * 60 * 1000)
        self.Initialisation()

    def StopTicker(self):
        self._active = False
        self._generation += 1
        self._busy = False
        self._timer.Stop()

    def Initialisation(self, force=False):
        database = str(UTILS_Config.GetParametre('nomFichier', '') or '')
        if not self._alive or not self._active or (self._busy and database == getattr(self, '_database', None)):
            return
        if database != getattr(self, '_database', None):
            self.banner.update(dt.date.today(), [])
        self._database = database
        signature = (database, self._current_user_id())
        if signature != self._layout_signature:
            self._layout = self._load_layout(database)
            self._layout_signature = signature
            self._apply_layout()
        self.title.SetLabel(DateDDEnDateFR(dt.date.today()))
        self._key = 'ephemerides:' + hashlib.sha256(database.encode('utf-8')).hexdigest()
        saved = copy.deepcopy(UTILS_Config.GetParametre(self._key, {}))
        self._generation += 1
        generation = self._generation
        self._busy = True
        self._timer.Start(5 * 60 * 1000)
        layout = copy.deepcopy(self._layout)
        threading.Thread(target=self._load, args=(generation, saved, force, database, layout), daemon=True).start()

    def _load(self, generation, saved, force, database, layout):
        layout = data.normalize_dashboard_layout(layout)
        result = dict(settings=saved.get('settings', {}), cache=copy.deepcopy(saved.get('cache', {})),
                      weather_error='', rows=[])
        try:
            if not database:
                raise ValueError('Aucune base ouverte')
            db = GestionDB.DB(nomFichier=database)
            try:
                if not db.ExecuterReq('SELECT cp, ville, gps FROM organisateur WHERE IDorganisateur=1;'):
                    raise ValueError('Lecture de l’organisateur impossible')
                organiser = db.ResultatReq()
                if not db.ExecuterReq('SELECT nom, date_debut, date_fin FROM vacances ORDER BY date_debut;'):
                    raise ValueError('Lecture du calendrier Noethys impossible')
                result['planning'] = db.ResultatReq()
                try:
                    result['programme'], result['activities'] = programme.read_day(db, dt.date.today(), layout['day'])
                except Exception:
                    result['programme_error'] = 'Programme du jour indisponible · réessayer ou consulter le planning.'
                    result['programme'], result['activities'] = [], []
            finally:
                db.Close()
            cp, city, gps = organiser[0] if organiser else ('', '', '')
            settings = dict(city=city or '', postcode=str(cp or ''), latitude='', longitude='', zone='',
                            agenda=data.AGENDA_35 if str(cp).startswith('35') else '', territories='', events=[])
            if gps and ';' in gps:
                settings['latitude'], settings['longitude'] = gps.split(';', 1)
            settings.update(result['settings'])
            result['settings'] = settings
        except Exception as error:
            result['db_error'] = str(error)
            result['planning'] = []
            settings = result['settings']
        if layout['blocks']['weather']['visible']:
            try:
                lat, lon = (data.coordinates(settings['latitude'], settings['longitude']) if settings.get('latitude')
                            else data.geocode(settings.get('city', ''), settings.get('postcode', '')))
                settings['latitude'], settings['longitude'] = str(lat), str(lon)
                key = json.dumps([lat, lon, dt.date.today().isoformat()])
                old = result.get('cache', {})
                if not force and data.cache_valid(old, key):
                    cache = old
                else:
                    try:
                        payload = json.loads(data.read_url(data.weather_url(lat, lon)))
                        data.aggregate_weather(payload)
                        cache = dict(key=key, payload=payload, fetched=dt.datetime.now(dt.timezone.utc).isoformat())
                    except Exception:
                        if old.get('key') != key:
                            raise
                        cache = old
                        result['weather_error'] = 'Actualisation impossible · données en cache à vérifier'
                result['cache'] = cache
                result['rows'] = data.aggregate_weather(cache['payload'])
            except Exception as error:
                result['weather_error'] = 'Météo indisponible : ' + str(error)

        result['checked'] = dt.datetime.now().strftime('%d/%m/%Y %H:%M')
        if self._alive:
            try:
                wx.CallAfter(self._publish, generation, result)
            except RuntimeError:
                # L’application peut avoir quitté entre le contrôle et le post.
                pass

    def _publish(self, generation, result):
        if not self._alive or generation != self._generation or not self._active:
            return
        self._busy = False
        self._result = result
        self._settings = result['settings']
        saved = dict(settings=self._settings, cache=result.get('cache', {}))
        UTILS_Config.SetParametre(self._key, saved)
        rows = result['rows']
        stamp = result.get('cache', {}).get('fetched', '')
        self.weather.set_forecast(rows, result['weather_error'], stamp)
        self.banner.update(dt.date.today(), result.get('programme', []),
                           result.get('programme_error', result.get('db_error', '')))
        self.detail.Enable(bool(rows))
        self.render_calendar(result)
        self.render_events()
        self.Layout()
        self.SetupScrolling(scroll_x=False)

    def render_calendar(self, result, today=None):
        today = today or dt.date.today()
        zone = self._settings.get('zone') or school.GetZoneDepuisCodePostal(self._settings.get('postcode'))
        self.block_panels['vacations'].heading.SetLabel('Vacances · %s' % zone if zone else 'Vacances')
        period = school.GetProchainePeriode(zone, today)
        if period:
            days = (period['debut'] - today).days
            text = '%s · zone %s\n%s\nDépart : %s après la classe' % (
                period['nom'], zone, ('Demain' if days == 1 else 'Dans %d jours' % days) if days > 0 else 'En cours',
                period['debut'].strftime('%d/%m/%Y'))
            if period['reprise']:
                text += '\nReprise : ' + period['reprise'].strftime('%d/%m/%Y')
        else:
            text = 'Calendrier scolaire : zone inconnue ou période hors du calendrier 2026–2027.'
        for name, start, end in result.get('planning', []):
            try:
                start, end = dt.date.fromisoformat(str(start)[:10]), dt.date.fromisoformat(str(end)[:10])
                if end >= today:
                    text += '\n\nPlanning Noethys\n%s : %s – %s' % (name, start.strftime('%d/%m/%Y'), end.strftime('%d/%m/%Y'))
                    break
            except (ValueError, TypeError):
                continue
        if result.get('db_error'):
            text += '\nCalendrier de la base indisponible : ' + result['db_error']
        self.vacation.SetLabel(text)
        self.vacation.Wrap(self._column_text_width())

    def render_events(self):
        parent = self.events_scroll
        self.events_content.Clear(delete_windows=True)
        events = data.upcoming_events(self._settings.get('events', []), self._settings.get('territories', ''),
                                      today=dt.date.today(), days=370)
        limit = self._layout['day']['event_count']
        if limit:
            events = events[:limit]
        for item in events:
            try:
                date_label = dt.date.fromisoformat(item['date']).strftime('%d %b')
            except (TypeError, ValueError):
                date_label = item['date']
            self.events_content.Add(
                link(parent, '%s · %s' % (date_label, item['title']), item['source']),
                0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6,
            )
        if not events:
            self.events_content.Add(wx.StaticText(parent, label='Aucune date officielle ou insolite renseignée.'), 0, wx.ALL, 6)

        if data.safe_url(self._settings.get('agenda', '')):
            self.events_content.Add(link(parent, 'Agenda local', self._settings['agenda']), 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        self.events_scroll.Layout()
        self.events_scroll.SetupScrolling(scroll_x=False)

    def OnSettings(self, event):
        if self._busy:
            wx.MessageBox("Le chargement est en cours. Les réglages seront disponibles dans quelques secondes.",
                          "Aujourd’hui", wx.OK, self)
            return
        dialog = Settings(self, self._settings, self._layout, self._result.get('activities', []))
        try:
            if dialog.ShowModal() == wx.ID_OK:
                old_layout = data.normalize_dashboard_layout(self._layout)
                new_layout = dialog.layout_values()
                new_settings = dialog.values()
                settings_changed = new_settings != self._settings
                needs_data = (
                    settings_changed or
                    (new_layout['blocks']['weather']['visible'] and not old_layout['blocks']['weather']['visible'])
                )

                saved = copy.deepcopy(UTILS_Config.GetParametre(self._key, {}))
                saved['settings'] = new_settings
                UTILS_Config.SetParametre(self._key, saved)

                persisted = self._save_layout(new_layout)
                self._layout = new_layout
                self._layout_signature = (
                    str(UTILS_Config.GetParametre('nomFichier', '') or ''),
                    self._current_user_id())
                self._apply_layout()
                self.render_events()

                if not persisted and self._current_user_id() is not None:
                    wx.MessageBox(
                        "La disposition est appliquée pour cette session mais n’a pas pu être enregistrée dans la base.",
                        "Aujourd’hui", wx.OK | wx.ICON_WARNING, self)

                if needs_data or new_layout['day'] != old_layout['day']:
                    self.Initialisation(force=settings_changed)
        finally:
            dialog.Destroy()

    def OnDetails(self, event):
        dialog = WeatherDetails(self, self._result['rows'], self._result.get('cache', {}).get('fetched', ''))
        try:
            dialog.ShowModal()
        finally:
            dialog.Destroy()
