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
from Utils import UTILS_Ephemerides as data
from Utils import UTILS_VacancesScolaires as school

JOURS = ('Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche')
MOIS = ('janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
        'septembre', 'octobre', 'novembre', 'décembre')


def DateDDEnDateFR(date):
    return '%s %d %s %d' % (JOURS[date.weekday()], date.day, MOIS[date.month - 1], date.year)


def link(parent, label, url):
    control = wx.adv.HyperlinkCtrl(parent, label=label if len(label) <= 46 else label[:43] + '…', url=url)
    control.SetToolTip(label + '\n' + url)
    return control


def section(parent, title):
    return wx.StaticBoxSizer(wx.VERTICAL, parent, title)


class Settings(wx.Dialog):
    def __init__(self, parent, settings):
        super().__init__(parent, title='Réglages des éphémérides', style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.events = copy.deepcopy(settings.get('events', []))
        self.fields = {}
        base = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(cols=2, vgap=6, hgap=10)
        grid.AddGrowableCol(1)
        for key, label in (('city', 'Ville'), ('postcode', 'Code postal'), ('latitude', 'Latitude (facultatif)'),
                           ('longitude', 'Longitude (facultatif)'), ('prefecture', 'Source préfectorale HTTPS (.gouv.fr)'),
                           ('agenda', 'Agenda local HTTPS'), ('territories', 'Territoires à afficher (séparés par des virgules)')):
            grid.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            control = wx.TextCtrl(self, value=str(settings.get(key, '')))
            self.fields[key] = control
            grid.Add(control, 1, wx.EXPAND)
        grid.Add(wx.StaticText(self, label='Zone scolaire'))
        self.zone = wx.Choice(self, choices=['Automatique', 'A', 'B', 'C'])
        self.zone.SetStringSelection(settings.get('zone', '') or 'Automatique')
        grid.Add(self.zone)
        base.Add(grid, 0, wx.EXPAND | wx.ALL, 12)
        base.Add(wx.StaticText(self, label='Événements : vérifier la date et la source avant de les ajouter.'), 0, wx.LEFT | wx.RIGHT, 12)
        self.list = wx.ListBox(self)
        base.Add(self.list, 1, wx.EXPAND | wx.ALL, 12)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        add = wx.Button(self, label='Ajouter…')
        remove = wx.Button(self, label='Retirer')
        buttons.Add(add)
        buttons.Add(remove, 0, wx.LEFT, 8)
        base.Add(buttons, 0, wx.LEFT | wx.RIGHT, 12)
        base.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 12)
        self.SetSizer(base)
        self.SetMinSize((640, 480))
        self.SetSize((700, 550))
        self.refresh_events()
        add.Bind(wx.EVT_BUTTON, self.add_event)
        remove.Bind(wx.EVT_BUTTON, self.remove_event)
        self.Bind(wx.EVT_BUTTON, self.accept, id=wx.ID_OK)

    def refresh_events(self):
        self.list.Set(['%s · %s · %s · %s' % (e['date'], e['kind'], e['title'], e.get('territory', '')) for e in self.events])

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
        self.weather_box = section(self, 'Météo · matin et après-midi')
        self.weather = wx.StaticText(self, label='Chargement…')
        self.weather_box.Add(self.weather, 0, wx.EXPAND | wx.ALL, 8)
        self.detail = wx.Button(self, label='Voir les prévisions sur 7 ou 10 jours…')
        self.detail.Enable(False)
        self.weather_box.Add(self.detail, 0, wx.ALL, 6)
        self.weather_box.Add(link(self, 'Source : Open-Meteo', data.WEATHER_SOURCE), 0, wx.ALL, 6)
        self.base.Add(self.weather_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.alert_box = section(self, 'Préfecture · bulletins récents à vérifier')
        self.alert_content = wx.BoxSizer(wx.VERTICAL)
        self.alert_box.Add(self.alert_content, 0, wx.EXPAND | wx.ALL, 8)
        self.base.Add(self.alert_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.vacation = wx.StaticText(self, label='Vacances scolaires : chargement…')
        self.base.Add(self.vacation, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.base.Add(link(self, 'Calendrier scolaire officiel 2026–2027', data.SCHOOL_SOURCE), 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.book = wx.Notebook(self)
        self.pages = {}
        for kind in data.KINDS:
            page = wx.Panel(self.book)
            sizer = wx.BoxSizer(wx.VERTICAL)
            page.SetSizer(sizer)
            self.book.AddPage(page, kind)
            self.pages[kind] = (page, sizer)
        self.base.Add(self.book, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.SetSizer(self.base)
        self.SetupScrolling(scroll_x=False)
        settings.Bind(wx.EVT_BUTTON, self.OnSettings)
        refresh.Bind(wx.EVT_BUTTON, lambda event: self.Initialisation(force=True))
        self.detail.Bind(wx.EVT_BUTTON, self.OnDetails)
        self.Bind(wx.EVT_TIMER, lambda event: self.Initialisation(), self._timer)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.Bind(wx.EVT_SIZE, self.OnSize)

    def OnDestroy(self, event):
        if event.GetEventObject() is self:
            self._alive = False
            self._generation += 1
            self._timer.Stop()
        event.Skip()

    def OnSize(self, event):
        # Repartir du texte original : Wrap ne sait pas défaire ses retours.
        if hasattr(self, '_weather_text'):
            self.weather.SetLabel(self._weather_text)
            self.weather.Wrap(max(180, self.GetClientSize().width - 48))
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
        self.title.SetLabel(DateDDEnDateFR(dt.date.today()))
        self._key = 'ephemerides:' + hashlib.sha256(database.encode('utf-8')).hexdigest()
        saved = copy.deepcopy(UTILS_Config.GetParametre(self._key, {}))
        self._generation += 1
        generation = self._generation
        self._busy = True
        self._timer.Start(30 * 60 * 1000)
        threading.Thread(target=self._load, args=(generation, saved, force, database), daemon=True).start()

    def _load(self, generation, saved, force, database):
        result = dict(settings=saved.get('settings', {}), weather_error='', alert_error='', rows=[], bulletins=[])
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
        try:
            lat, lon = (data.coordinates(settings['latitude'], settings['longitude']) if settings.get('latitude')
                        else data.geocode(settings.get('city', ''), settings.get('postcode', '')))
            settings['latitude'], settings['longitude'] = str(lat), str(lon)
            key = json.dumps([lat, lon, dt.date.today().isoformat()])
            old = saved.get('cache', {})
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
        self.weather.Wrap(max(180, self.GetClientSize().width - 48))
        self.detail.Enable(bool(rows))
        self.alert_content.Clear(delete_windows=True)
        notice = result['alert_error'] or ('Aucun bulletin correspondant publié ces 7 derniers jours. Cela ne garantit pas l’absence de vigilance.'
                                           if not result['bulletins'] else 'Vérifier dans chaque source la validité et le territoire concernés.')
        text = wx.StaticText(self, label=notice + '\nConsultation : ' + result['checked'])
        text.Wrap(max(180, self.GetClientSize().width - 48))
        self.alert_content.Add(text, 0, wx.EXPAND)
        for bulletin in result['bulletins']:
            self.alert_content.Add(link(self, bulletin['date'] + ' · ' + bulletin['title'], bulletin['source']), 0, wx.TOP, 5)
        if self._settings.get('prefecture'):
            self.alert_content.Add(link(self, 'Ouvrir la source préfectorale', self._settings['prefecture']), 0, wx.TOP, 5)
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
        self.vacation.Wrap(max(180, self.GetClientSize().width - 40))

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
            wx.MessageBox('Le chargement est en cours. Les réglages seront disponibles dans quelques secondes.', 'Éphémérides', wx.OK, self)
            return
        dialog = Settings(self, self._settings)
        try:
            if dialog.ShowModal() == wx.ID_OK:
                UTILS_Config.SetParametre(self._key, dict(settings=dialog.values()))
                self.Initialisation(force=True)
        finally:
            dialog.Destroy()

    def OnDetails(self, event):
        dialog = WeatherDetails(self, self._result['rows'], self._result.get('cache', {}).get('fetched', ''))
        try:
            dialog.ShowModal()
        finally:
            dialog.Destroy()
