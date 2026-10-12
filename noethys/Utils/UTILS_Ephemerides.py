# -*- coding: utf-8 -*-
"""Données des éphémérides, sans dépendance graphique. Licence GNU GPL.

Les prévisions ne sont pas une vigilance officielle. Les articles préfectoraux
ne donnent pas à eux seuls la durée de validité d'un arrêté.
"""
import datetime as dt
import json
import math
import unicodedata
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit, urljoin
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

WEATHER_SOURCE = 'https://open-meteo.com/'
SCHOOL_SOURCE = 'https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000052416058'
PREFECTURE_35 = 'https://www.ille-et-vilaine.gouv.fr/syndication/listexport'
AGENDA_35 = 'https://www.vitrecommunaute.org/systeme/agenda/?display=liste'
FIELDS = ('temperature_2m', 'precipitation', 'precipitation_probability',
          'wind_speed_10m', 'wind_gusts_10m', 'relative_humidity_2m', 'weather_code')
PERIODS = (('Matin · 6–12 h', 6, 12), ('Après-midi · 12–18 h', 12, 18))
KINDS = ('Officiel', 'Local', 'Insolite')

DASHBOARD_BLOCKS = ('weather', 'vacations', 'events')
DEFAULT_DASHBOARD_LAYOUT = {
    'columns': 3,
    'blocks': {
        'weather': {'visible': True, 'column': 1, 'order': 1},
        'vacations': {'visible': True, 'column': 2, 'order': 1},
        'events': {'visible': True, 'column': 3, 'order': 1},
    },
}


def normalize_dashboard_layout(layout=None):
    """Retourne une disposition personnelle bornée et complète, sans modifier l'entrée."""
    source = layout if isinstance(layout, dict) else {}
    try:
        columns = int(source.get('columns', DEFAULT_DASHBOARD_LAYOUT['columns']))
    except (TypeError, ValueError):
        columns = DEFAULT_DASHBOARD_LAYOUT['columns']
    columns = min(4, max(1, columns))
    source_blocks = source.get('blocks', {}) if isinstance(source.get('blocks', {}), dict) else {}
    blocks = {}
    for key in DASHBOARD_BLOCKS:
        default = DEFAULT_DASHBOARD_LAYOUT['blocks'][key]
        value = source_blocks.get(key, {}) if isinstance(source_blocks.get(key, {}), dict) else {}
        try:
            column = int(value.get('column', default['column']))
        except (TypeError, ValueError):
            column = default['column']
        try:
            order = int(value.get('order', default['order']))
        except (TypeError, ValueError):
            order = default['order']
        blocks[key] = {
            'visible': bool(value.get('visible', default['visible'])),
            'column': min(columns, max(1, column)),
            'order': max(1, order),
        }
    return {'columns': columns, 'blocks': blocks}


def dashboard_columns(layout=None):
    """Liste ordonnée des blocs visibles pour chaque colonne."""
    layout = normalize_dashboard_layout(layout)
    result = [[] for _ in range(layout['columns'])]
    for index, key in enumerate(DASHBOARD_BLOCKS):
        block = layout['blocks'][key]
        if block['visible']:
            result[block['column'] - 1].append((block['order'], index, key))
    return [[key for _, _, key in sorted(column)] for column in result]

# Catalogue volontairement court : chaque entrée renvoie à son organisateur.
CATALOGUE = [
    dict(title='Journée internationale de l’éducation', kind='Officiel', month=1, day=24,
         source='https://www.un.org/en/observances/education-day'),
    dict(title='Journée internationale des droits des femmes', kind='Officiel', month=3, day=8,
         source='https://www.un.org/en/observances/womens-day'),
    dict(title='Journée mondiale de la santé', kind='Officiel', month=4, day=7,
         source='https://www.who.int/campaigns/world-health-day'),
    dict(title='Star Wars Day', kind='Insolite', month=5, day=4,
         source='https://www.starwars.com/news/the-history-of-may-the-4th'),
    dict(title='Journée internationale des familles', kind='Officiel', month=5, day=15,
         source='https://www.un.org/en/observances/international-day-of-families'),
    dict(title='Journée mondiale de l’environnement', kind='Officiel', month=6, day=5,
         source='https://www.worldenvironmentday.global/'),
    dict(title='Journée internationale de la jeunesse', kind='Officiel', month=8, day=12,
         source='https://www.un.org/en/observances/youth-day'),
    dict(title='Journée mondiale des enseignants', kind='Officiel', month=10, day=5,
         source='https://www.unesco.org/en/days/teachers'),
    dict(title='Journée mondiale de la santé mentale', kind='Officiel', month=10, day=10,
         source='https://www.un.org/en/healthy-workforce/world-mental-health-day'),
    dict(title='Journée mondiale de l’alimentation', kind='Officiel', month=10, day=16,
         source='https://www.fao.org/world-food-day/en'),
    dict(title='Journée des Nations Unies', kind='Officiel', month=10, day=24,
         source='https://www.un.org/en/observances/un-day'),
    dict(title='Journée mondiale des pâtes', kind='Insolite', month=10, day=25,
         source='https://internationalpasta.org/news/world-pasta-day-the-world-is-hungry-for-pasta-1-million-tons-more-pasta-is-consumed-in-a-year/'),
    dict(title='World Smile Day', kind='Insolite', month=10, weekday=4,
         source='https://www.worldsmile.org/about'),
    dict(title='Journée des droits de l’homme', kind='Officiel', month=12, day=10,
         source='https://www.un.org/en/observances/human-rights-day'),
]


def safe_url(url):
    parts = urlsplit(str(url))
    return (parts.scheme == 'https' and bool(parts.hostname) and
            not parts.username and not parts.password and parts.port in (None, 443))


def official_url(url):
    if not safe_url(url):
        return False
    host = urlsplit(url).hostname.lower()
    return host.endswith('.gouv.fr')


def read_url(url, official=False):
    if not (official_url(url) if official else safe_url(url)):
        raise ValueError('Source HTTPS non valide')
    request = Request(url, headers={'User-Agent': 'Noethys-SL Ephemerides/1.0'})
    with urlopen(request, timeout=8) as response:
        if not (official_url(response.url) if official else safe_url(response.url)):
            raise ValueError('Redirection non autorisée')
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('Réponse trop volumineuse')
    return raw


def coordinates(latitude, longitude):
    lat, lon = float(latitude), float(longitude)
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('Coordonnées GPS hors limites')
    return lat, lon


def _normalize_place(value):
    """Normalise un nom de commune sans confondre accents, espaces et tirets."""
    value = ''.join(c for c in unicodedata.normalize('NFD', str(value).lower())
                    if not unicodedata.combining(c))
    return ' '.join(''.join(c if c.isalnum() else ' ' for c in value).split())


def _geocode_fr(city, postcode):
    """Résout d'abord une commune française par son code postal officiel."""
    url = 'https://geo.api.gouv.fr/communes?' + urlencode(dict(
        codePostal=str(postcode), fields='nom,centre,codesPostaux',
        format='json', geometry='centre'))
    candidates = json.loads(read_url(url))
    if not isinstance(candidates, list):
        raise ValueError('Réponse de localisation française invalide')
    wanted = _normalize_place(city)
    matching = [item for item in candidates if _normalize_place(item.get('nom', '')) == wanted]
    if not matching and len(candidates) == 1:
        matching = candidates
    if len(matching) != 1:
        raise ValueError('Commune introuvable ou ambiguë pour ce code postal')
    centre = matching[0].get('centre') or {}
    coords = centre.get('coordinates') or []
    if len(coords) != 2:
        raise ValueError('Coordonnées de la commune indisponibles')
    lon, lat = coords
    return coordinates(lat, lon)


def _geocode_open_meteo(city, postcode):
    """Repli : géocodage Open-Meteo avec concordance explicite du code postal."""
    url = 'https://geocoding-api.open-meteo.com/v1/search?' + urlencode(
        dict(name=city, count=100, language='fr', countryCode='FR'))
    candidates = json.loads(read_url(url)).get('results', [])
    matching = [item for item in candidates if item.get('country_code') == 'FR'
                and str(postcode) in [str(cp) for cp in item.get('postcodes', [])]]
    if len(matching) != 1:
        raise ValueError('Localisation ambiguë')
    return coordinates(matching[0]['latitude'], matching[0]['longitude'])


def geocode(city, postcode):
    """Localise sans deviner : référentiel français, puis repli Open-Meteo."""
    if not city or not postcode:
        raise ValueError('Renseigner la ville et le code postal de l’organisateur, ou les coordonnées GPS')
    try:
        return _geocode_fr(city, postcode)
    except Exception as first_error:
        try:
            return _geocode_open_meteo(city, postcode)
        except Exception:
            raise ValueError(
                'Localisation impossible pour %s %s : renseigner latitude et longitude dans les réglages'
                % (postcode, city)) from first_error


def weather_url(lat, lon):
    lat, lon = coordinates(lat, lon)
    return 'https://api.open-meteo.com/v1/forecast?' + urlencode(dict(
        latitude=lat, longitude=lon, hourly=','.join(FIELDS), daily='sunrise,sunset',
        forecast_days=10, timezone='Europe/Paris', wind_speed_unit='kmh'))


def category(code):
    if code is None:
        return (0, '—', 'Indisponible')
    if code >= 95:
        return (6, '⚡', 'Orage')
    if code in (56, 57, 66, 67, 71, 73, 75, 77, 85, 86):
        return (5, '❄', 'Neige / gel')
    if code in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        return (4, '☂', 'Pluie')
    if code in (45, 48):
        return (3, '≋', 'Brouillard')
    if code in (2, 3):
        return (2, '☁', 'Nuageux')
    if code in (0, 1):
        return (1, '☀', 'Ensoleillé')
    return (0, '—', 'Indisponible')


def aggregate_weather(payload):
    hourly = payload.get('hourly', {})
    groups = {}
    for index, stamp in enumerate(hourly.get('time', [])):
        moment = dt.datetime.fromisoformat(stamp)
        for label, start, end in PERIODS:
            if start <= moment.hour < end:
                groups.setdefault((moment.date().isoformat(), label), []).append(index)
    result = []
    for (date, label), indexes in sorted(groups.items(), key=lambda x: (x[0][0], PERIODS[0][0] != x[0][1])):
        row = dict(date=date, period=label, samples=len(indexes))
        for field in FIELDS:
            source = hourly.get(field, [])
            values = [source[i] for i in indexes if i < len(source) and
                      isinstance(source[i], (int, float)) and math.isfinite(source[i])]
            # Un total de pluie incomplet ne doit jamais ressembler à zéro mm.
            if len(values) != 6 or len(indexes) != 6:
                row[field] = None
            elif field in ('temperature_2m', 'relative_humidity_2m'):
                row[field] = (min(values), max(values))
            elif field == 'precipitation':
                row[field] = sum(values)
            elif field == 'weather_code':
                row[field] = max(values, key=lambda v: category(v)[0])
            else:
                row[field] = max(values)
        result.append(row)
    if not result:
        raise ValueError('Prévisions horaires absentes')
    return result


def weather_text(row):
    def number(value, unit):
        if value is None:
            return '—'
        if isinstance(value, (tuple, list)):
            return '%g–%g %s' % (value[0], value[1], unit)
        return '%g %s' % (round(value, 1), unit)
    _, icon, label = category(row['weather_code'])
    return '%s %s · %s\nPluie %s (max. %s) · Vent %s / rafales %s · Humidité %s' % (
        icon, label, number(row['temperature_2m'], '°C'), number(row['precipitation'], 'mm'),
        number(row['precipitation_probability'], '%'), number(row['wind_speed_10m'], 'km/h'),
        number(row['wind_gusts_10m'], 'km/h'), number(row['relative_humidity_2m'], '%'))


class FeedLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        href = attrs.get('href', '')
        if tag in ('a', 'link') and (attrs.get('type') in ('application/rss+xml', 'application/atom+xml')
                                    or 'syndication/export' in href or href.endswith('.rss')):
            self.links.append(href)


def parse_bulletins(raw, source, now=None):
    if not official_url(source):
        raise ValueError('Les bulletins doivent provenir d’un site préfectoral .gouv.fr')
    now = now or dt.datetime.now(dt.timezone.utc)
    root = ET.fromstring(raw)
    # Un document HTML ou un flux Atom non pris en charge n'est pas un flux vide.
    if root.tag.lower() not in ('rss', 'rdf', '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}rdf'):
        raise ValueError('Flux RSS non reconnu')
    result = []
    for item in root.iter('item'):
        title = item.findtext('title', '').strip()
        url = urljoin(source, item.findtext('link', ''))
        try:
            published = parsedate_to_datetime(item.findtext('pubDate', ''))
            if published.tzinfo is None:
                published = published.replace(tzinfo=dt.timezone.utc)
        except (ValueError, TypeError):
            continue
        age = (now - published).total_seconds()
        normalized = ''.join(c for c in unicodedata.normalize('NFD', title.lower()) if not unicodedata.combining(c))
        if 0 <= age <= 7 * 86400 and official_url(url) and urlsplit(url).hostname == urlsplit(source).hostname:
            if any(word in normalized for word in ('vigilance', 'alerte', 'arrete', 'restriction',
                                                   'canicule', 'crue', 'incendie', 'tempete', 'orage')):
                result.append(dict(title=title, source=url, date=published.date().isoformat()))
    return sorted(result, key=lambda r: r['date'], reverse=True)[:5]


def fetch_bulletins(source):
    raw = read_url(source, official=True)
    if b'<rss' not in raw.lower() and b'<rdf' not in raw.lower():
        parser = FeedLinks()
        parser.feed(raw.decode('utf-8', errors='replace'))
        urls = [urljoin(source, link) for link in parser.links]
        urls = [url for url in urls if official_url(url) and urlsplit(url).hostname == urlsplit(source).hostname]
        if not urls:
            raise ValueError('Flux préfectoral introuvable : ouvrir les actualités officielles')
        source = urls[0]
        raw = read_url(source, official=True)
    return parse_bulletins(raw, source)


def validate_event(event):
    title = str(event.get('title', '')).strip()
    date = dt.date.fromisoformat(event['date'])
    if not title or event.get('kind') not in KINDS or not safe_url(event.get('source', '')):
        raise ValueError('Renseigner un titre, une catégorie, une date et une source HTTPS')
    return dict(title=title, date=date.isoformat(), kind=event['kind'], source=event['source'],
                territory=str(event.get('territory', '')).strip())


def upcoming_events(custom, territories='', today=None, days=30):
    today = today or dt.date.today()
    end = today + dt.timedelta(days=days)
    result = []
    for item in CATALOGUE:
        for year in (today.year, today.year + 1):
            date = dt.date(year, item['month'], item.get('day', 1))
            if 'weekday' in item:
                date += dt.timedelta(days=(item['weekday'] - date.weekday()) % 7)
            if today <= date <= end:
                result.append(dict(item, date=date.isoformat(), territory=''))
    filters = {value.strip().casefold() for value in territories.split(',') if value.strip()}
    for raw in custom:
        try:
            item = validate_event(raw)
        except (ValueError, KeyError, TypeError):
            continue
        if today.isoformat() <= item['date'] <= end.isoformat():
            if item['kind'] != 'Local' or not filters or item['territory'].casefold() in filters:
                result.append(item)
    return sorted(result, key=lambda r: (r['date'], r['title']))


def cache_valid(cache, key, now=None, max_age=1800):
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        stamp = dt.datetime.fromisoformat(cache['fetched'])
        return cache['key'] == key and 0 <= (now - stamp).total_seconds() < max_age
    except (KeyError, ValueError, TypeError):
        return False
