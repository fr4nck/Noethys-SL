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
    'alerts': 'Infos officielles',
    'vacations': 'Vacances scolaires',
    'events': 'Événements',
}


def DateDDEnDateFR(date):
    return '%s %d %s %d' % (JOURS[date.weekday()], date.day, MOIS[date.month - 1], date.year)


def link(parent, label, url):
    control = wx.adv.HyperlinkCtrl(parent, label=label if len(label) <= 46 else label[:43] + '…', url=url)
    control.SetToolTip(label + '\n' + url)
    return control


def section(parent, title):
    return wx.StaticBoxSizer(wx.VERTICAL, parent, title)


class Settings(wx.Dialog):
    def __init__(self, parent, settings, layout):
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

        # Sources et contenu commun ------------------------------------------
        sources = wx.Panel(book)
        sources_sizer = wx.BoxSizer(wx.VERTICAL)
        source_grid = wx.FlexGridSizer(cols=2, vgap=6, hgap=10)
        source_grid.AddGrowableCol(1)
        for key, label in (('city', 'Ville'), ('postcode', 'Code postal'), ('latitude', 'Latitude (facultatif)'),
                           ('longitude', 'Longitude (facultatif)'), ('prefecture', 'Source préfectorale HTTPS (.gouv.fr)'),
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
        })

    def accept(self, event):
        values = self.values()
        try:
            if values['latitude'] or values['longitude']:
                data.coordinates(values['latitude'], values['longitude'])
            if values['prefecture'] and not data.official_url(values['prefecture']):
                raise ValueError('La source préfectorale doit être une adresse HTTPS .gouv.fr')
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
        header = wx.BoxSizer(wx.VERTICAL)
        self.title = wx.StaticText(self, label=DateDDEnDateFR(dt.date.today()))
        self.title.SetFont(self.title.GetFont().Bold())
        header.Add(self.title, 0, wx.EXPAND)
        settings = wx.Button(self, label='Réglages…')
        refresh = wx.Button(self, label='Actualiser')
        toolbar = wx.BoxSizer(wx.HORIZONTAL)
        toolbar.Add(settings)
        toolbar.Add(refresh, 0, wx.LEFT, 6)
        header.Add(toolbar, 0, wx.TOP, 6)
        self.base.Add(header, 0, wx.EXPAND | wx.ALL, 10)

        self.place = wx.StaticText(self, label='Localisation de l’organisateur')
        self.base.Add(self.place, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.block_panels = {}

        weather_panel = wx.Panel(self)
        weather_box = section(weather_panel, 'Météo · matin et après-midi')
        self.weather = wx.StaticText(weather_panel, label='Chargement…')
        weather_box.Add(self.weather, 0, wx.EXPAND | wx.ALL, 8)
        self.detail = wx.Button(weather_panel, label='Voir les prévisions sur 7 ou 10 jours…')
        self.detail.Enable(False)
        weather_box.Add(self.detail, 0, wx.ALL, 6)
        weather_box.Add(link(weather_panel, 'Source : Open-Meteo', data.WEATHER_SOURCE), 0, wx.ALL, 6)
        weather_panel.SetSizer(weather_box)
        self.block_panels['weather'] = weather_panel

        alert_panel = wx.Panel(self)
        alert_box = section(alert_panel, 'Infos officielles · bulletins récents à vérifier')
        self.alert_content = wx.BoxSizer(wx.VERTICAL)
        alert_box.Add(self.alert_content, 0, wx.EXPAND | wx.ALL, 8)
        alert_panel.SetSizer(alert_box)
        self.block_panels['alerts'] = alert_panel

        vacation_panel = wx.Panel(self)
        vacation_box = section(vacation_panel, 'Vacances scolaires')
        self.vacation = wx.StaticText(vacation_panel, label='Chargement…')
        vacation_box.Add(self.vacation, 0, wx.EXPAND | wx.ALL, 8)
        vacation_box.Add(link(vacation_panel, 'Calendrier scolaire officiel 2026–2027', data.SCHOOL_SOURCE),
                         0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        vacation_panel.SetSizer(vacation_box)
        self.block_panels['vacations'] = vacation_panel

        events_panel = wx.Panel(self)
        events_box = section(events_panel, 'Événements à venir')
        self.book = wx.Notebook(events_panel)
        self.pages = {}
        for kind in data.KINDS:
            page = wx.Panel(self.book)
            sizer = wx.BoxSizer(wx.VERTICAL)
            page.SetSizer(sizer)
            self.book.AddPage(page, kind)
            self.pages[kind] = (page, sizer)
        events_box.Add(self.book, 1, wx.EXPAND | wx.ALL, 6)
        events_panel.SetSizer(events_box)
        self.block_panels['events'] = events_panel

        self.dashboard = wx.BoxSizer(wx.HORIZONTAL)
        self.base.Add(self.dashboard, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.SetSizer(self.base)
        self._apply_layout()
        self.SetupScrolling(scroll_x=False)

        settings.Bind(wx.EVT_BUTTON, self.OnSettings)
        refresh.Bind(wx.EVT_BUTTON, lambda event: self.Initialisation(force=True))
        self.detail.Bind(wx.EVT_BUTTON, self.OnDetails)
        self.Bind(wx.EVT_TIMER, lambda event: self.Initialisation(), self._timer)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.Bind(wx.EVT_SIZE, self.OnSize)

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
        for index in range(self._layout['columns']):
            column = wx.BoxSizer(wx.VERTICAL)
            border = wx.LEFT if index else 0
            self.dashboard.Add(column, 1, wx.EXPAND | border, 8 if index else 0)
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
        width = self._column_text_width()
        if hasattr(self, '_weather_text'):
            self.weather.SetLabel(self._weather_text)
        self.weather.Wrap(width)
        self.vacation.Wrap(width)
        for item in self.alert_content.GetChildren():
            control = item.GetWindow()
            if isinstance(control, wx.StaticText):
                control.Wrap(width)

    def OnUserChanged(self):
        """Recharge uniquement la disposition personnelle lors d'un changement d'identifiant."""
        database = str(UTILS_Config.GetParametre('nomFichier', '') or '')
        self._layout = self._load_layout(database)
        self._layout_signature = (database, self._current_user_id())
        self._apply_layout()

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
        self._timer.Start(30 * 60 * 1000)
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
        self._timer.Start(30 * 60 * 1000)
        layout = copy.deepcopy(self._layout)
        threading.Thread(target=self._load, args=(generation, saved, force, database, layout), daemon=True).start()

    def _load(self, generation, saved, force, database, layout):
        layout = data.normalize_dashboard_layout(layout)
        result = dict(settings=saved.get('settings', {}), cache=copy.deepcopy(saved.get('cache', {})),
                      weather_error='', alert_error='', rows=[], bulletins=[])
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
            finally:
                db.Close()
            cp, city, gps = organiser[0] if organiser else ('', '', '')
            settings = dict(city=city or '', postcode=str(cp or ''), latitude='', longitude='', zone='',
                            prefecture=data.PREFECTURE_35 if str(cp).startswith('35') else '',
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

        if layout['blocks']['alerts']['visible']:
            if settings.get('prefecture'):
                try:
                    result['bulletins'] = data.fetch_bulletins(settings['prefecture'])
                except Exception as error:
                    result['alert_error'] = 'Source préfectorale indisponible : ' + str(error)
            else:
                result['alert_error'] = 'Choisir la source de votre préfecture dans les réglages.'
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
        self.place.SetLabel('%s %s' % (self._settings.get('city', ''), self._settings.get('postcode', '')))
        rows = result['rows']
        dates = sorted({row['date'] for row in rows})[:3]
        stamp = result.get('cache', {}).get('fetched', '')
        self._weather_text = '\n\n'.join('%s · %s\n%s' % (row['date'], row['period'], data.weather_text(row))
                                           for row in rows if row['date'] in dates)
        if stamp:
            self._weather_text += '\n\nRelevé : ' + stamp[:16].replace('T', ' ') + ' UTC'
        if result['weather_error']:
            self._weather_text += '\n' + result['weather_error']
        self.weather.SetLabel(self._weather_text)
        self.weather.Wrap(self._column_text_width())
        self.detail.Enable(bool(rows))
        self.alert_content.Clear(delete_windows=True)
        notice = result['alert_error'] or ('Aucun bulletin correspondant publié ces 7 derniers jours. Cela ne garantit pas l’absence de vigilance.'
                                           if not result['bulletins'] else 'Vérifier dans chaque source la validité et le territoire concernés.')
        alert_parent = self.block_panels['alerts']
        text = wx.StaticText(alert_parent, label=notice + '\nConsultation : ' + result['checked'])
        text.Wrap(self._column_text_width())
        self.alert_content.Add(text, 0, wx.EXPAND)
        for bulletin in result['bulletins']:
            self.alert_content.Add(link(alert_parent, bulletin['date'] + ' · ' + bulletin['title'], bulletin['source']), 0, wx.TOP, 5)
        if self._settings.get('prefecture'):
            self.alert_content.Add(link(alert_parent, 'Ouvrir la source préfectorale', self._settings['prefecture']), 0, wx.TOP, 5)
        self.render_calendar(result)
        self.render_events()
        self.Layout()
        self.SetupScrolling(scroll_x=False)

    def render_calendar(self, result, today=None):
        today = today or dt.date.today()
        zone = self._settings.get('zone') or school.GetZoneDepuisCodePostal(self._settings.get('postcode'))
        period = school.GetProchainePeriode(zone, today)
        if period:
            days = (period['debut'] - today).days
            text = ('%s · dans %d jours' % (period['nom'], days) if days > 0 else period['nom'] + ' · période scolaire en cours')
            text += ' · zone %s · départ après la classe le %s' % (zone, period['debut'].strftime('%d/%m/%Y'))
            if period['reprise']:
                text += ' · reprise le ' + period['reprise'].strftime('%d/%m/%Y')
        else:
            text = 'Calendrier scolaire : zone inconnue ou période hors du calendrier 2026–2027.'
        for name, start, end in result.get('planning', []):
            try:
                start, end = dt.date.fromisoformat(str(start)[:10]), dt.date.fromisoformat(str(end)[:10])
                if end >= today:
                    text += '\nCalendrier Noethys : %s · %s au %s (dates de votre base)' % (name, start.strftime('%d/%m/%Y'), end.strftime('%d/%m/%Y'))
                    break
            except (ValueError, TypeError):
                continue
        if result.get('db_error'):
            text += '\nCalendrier de la base indisponible : ' + result['db_error']
        self.vacation.SetLabel(text)
        self.vacation.Wrap(self._column_text_width())

    def render_events(self):
        events = data.upcoming_events(self._settings.get('events', []), self._settings.get('territories', ''))
        for kind, (page, sizer) in self.pages.items():
            sizer.Clear(delete_windows=True)
            selected = [item for item in events if item['kind'] == kind]
            notice = ('Dates vérifiées auprès des organismes · 30 prochains jours' if kind != 'Local'
                      else 'Événements saisis après vérification · 30 prochains jours')
            sizer.Add(wx.StaticText(page, label=notice), 0, wx.ALL, 8)
            for item in selected[:10]:
                sizer.Add(link(page, '%s · %s %s' % (item['date'], item['title'], item.get('territory', '')), item['source']), 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
            if not selected:
                sizer.Add(wx.StaticText(page, label='Aucun événement renseigné pour cette période et ce territoire.'), 0, wx.ALL, 8)
            if kind == 'Local' and data.safe_url(self._settings.get('agenda', '')):
                sizer.Add(link(page, 'Consulter l’agenda local et ajouter les dates utiles dans les réglages', self._settings['agenda']), 0, wx.ALL, 8)
            page.Layout()
        self.book.SetMinSize((-1, max(150, max(page.GetSizer().GetMinSize().height for page, _ in self.pages.values()) + 35)))

    def OnSettings(self, event):
        if self._busy:
            wx.MessageBox("Le chargement est en cours. Les réglages seront disponibles dans quelques secondes.",
                          "Aujourd’hui", wx.OK, self)
            return
        dialog = Settings(self, self._settings, self._layout)
        try:
            if dialog.ShowModal() == wx.ID_OK:
                old_layout = data.normalize_dashboard_layout(self._layout)
                new_layout = dialog.layout_values()
                new_settings = dialog.values()
                settings_changed = new_settings != self._settings
                needs_data = (
                    settings_changed or
                    (new_layout['blocks']['weather']['visible'] and not old_layout['blocks']['weather']['visible']) or
                    (new_layout['blocks']['alerts']['visible'] and not old_layout['blocks']['alerts']['visible'])
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

                if not persisted and self._current_user_id() is not None:
                    wx.MessageBox(
                        "La disposition est appliquée pour cette session mais n’a pas pu être enregistrée dans la base.",
                        "Aujourd’hui", wx.OK | wx.ICON_WARNING, self)

                if needs_data:
                    self.Initialisation(force=settings_changed)
        finally:
            dialog.Destroy()

    def OnDetails(self, event):
        dialog = WeatherDetails(self, self._result['rows'], self._result.get('cache', {}).get('fetched', ''))
        try:
            dialog.ShowModal()
        finally:
            dialog.Destroy()
