# -*- coding: utf-8 -*-
"""Aggregate-only attendance exports: no names, IDs, amounts or QF values."""
from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
import zipfile

HEADER = ('Perimetre', 'Periode', 'Jours presents', 'Absences justifiees',
          'Absences injustifiees', 'Jours mixtes', 'Jours pointes',
          'Reservations non pointees (lignes)', 'Attentes (lignes)',
          'Refus (lignes)', 'Taux absence (%) hors mixtes',
          'Part injustifiee (%)', 'Annulations', 'Couverture')


def _safe(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else value


def _check(data):
    if 'global' not in data or 'annees' not in data or 'sites' not in data:
        raise ValueError('Incomplete aggregate attendance report')
    if data.get('annulations', {}).get('nombre') is not None:
        raise ValueError('Cancellation evidence is not yet sufficient')
    if 'annees_scolaires' not in data or 'sites_annees_scolaires' not in data:
        raise ValueError('Missing school year aggregates')
    for scope in [data['global'], *data['annees'].values(),
                  *data['annees_scolaires'].values(), *data['mois'].values(),
                  *data['activites'].values(), *data['sites'].values(),
                  *(v for scopes in data['sites_annees'].values() for v in scopes.values()),
                  *(v for scopes in data['sites_annees_scolaires'].values()
                    for v in scopes.values())]:
        days = scope['journees_enfants']
        rows = scope['lignes']
        if (any(not isinstance(v, int) or v < 0 for v in (*days.values(), *rows.values()))
                or sum(days.values()) != scope['journees_pointees']
                or sum(rows.values()) != scope['lignes_total']):
            raise ValueError('Inconsistent attendance aggregate')
    return True


def _row(name, period, value):
    d = value['journees_enfants']
    l = value['lignes']
    if 'annee_scolaire_complete_dans_periode' in value:
        coverage = ('Partielle' if not value['annee_scolaire_complete_dans_periode']
                    else ('Complete' if value['annee_scolaire_terminee'] else 'En cours'))
    elif 'annee_complete_dans_periode' in value:
        coverage = ('Partielle' if not value['annee_complete_dans_periode']
                    else ('Complete' if value['annee_terminee'] else 'En cours'))
    else:
        coverage = ''
    return (_safe(name), period, d['present'], d['absentj'], d['absenti'], d['mixte'],
            value['journees_pointees'], l['reservation'], l['attente'], l['refus'],
            value['taux_absence_pct'], value['part_injustifiee_pct'],
            'Non reconstructibles', coverage)


def lignes(data):
    _check(data)
    result = [_row('Synthese generale', ' au '.join(data['periode']), data['global'])]
    result.extend(_row('Annee', year, value) for year, value in data['annees'].items())
    result.extend(_row('Annee scolaire', year, value)
                  for year, value in data['annees_scolaires'].items())
    result.extend(_row('Mois', month, value) for month, value in data['mois'].items())
    result.extend(_row('Activite ' + code, ' au '.join(data['periode']), value)
                  for code, value in data['activites'].items())
    result.extend(_row('Site ' + site, ' au '.join(data['periode']), value)
                  for site, value in data['sites'].items())
    for site, annual in data['sites_annees'].items():
        result.extend(_row('Site ' + site, year, value) for year, value in annual.items())
    for site, annual in data['sites_annees_scolaires'].items():
        result.extend(_row('Site ' + site + ' (scolaire)', year, value)
                      for year, value in annual.items())
    return result


def export_csv(data, filename):
    content = StringIO(newline='')
    writer = csv.writer(content, delimiter=';')
    writer.writerow(HEADER)
    writer.writerows(lignes(data))
    Path(filename).write_bytes(('\ufeff' + content.getvalue()).encode('utf-8'))
    return len(lignes(data))


def export_xlsx(data, filename):
    _check(data)
    try:
        import xlsxwriter
    except ImportError as error:
        raise RuntimeError('XlsxWriter missing from application package') from error
    categories = [
        ('Bilan', [('Synthese generale', ' au '.join(data['periode']), data['global'])]),
        ('Annees', [('Annee', key, value) for key, value in data['annees'].items()]),
        ('Annees scolaires', [('Annee scolaire', key, value)
                             for key, value in data['annees_scolaires'].items()]),
        ('Mois', [('Mois', key, value) for key, value in data['mois'].items()]),
        ('Activites', [('Activite ' + key, ' au '.join(data['periode']), value)
                       for key, value in data['activites'].items()]),
        ('Sites', [('Site ' + key, ' au '.join(data['periode']), value)
                   for key, value in data['sites'].items()]),
        ('Sites par an', [ ('Site ' + site, year, value)
                           for site, annual in data['sites_annees'].items()
                           for year, value in annual.items()]),
        ('Sites scolaires', [('Site ' + site, year, value)
                             for site, annual in data['sites_annees_scolaires'].items()
                             for year, value in annual.items()]),
    ]
    with xlsxwriter.Workbook(str(filename), {'strings_to_formulas':False,
                                              'strings_to_urls':False}) as wb:
        head = wb.add_format({'bold':True, 'bg_color':'#345', 'font_color':'white'})
        for name, scopes in categories:
            ws = wb.add_worksheet(name)
            ws.set_column(0, 0, 23)
            ws.set_column(1, 1, 30)
            ws.set_column(2, 13, 22)
            for column, title in enumerate(HEADER):
                ws.write_string(0, column, title, head)
            for index, (scope, period, values) in enumerate(scopes, 1):
                for col, val in enumerate(_row(scope,period,values)):
                    if isinstance(val,(float,int)):
                        ws.write_number(index,col,val)
                    elif val is None:
                        ws.write_blank(index,col,None)
                    else:
                        ws.write_string(index,col,str(val))
            ws.freeze_panes(1,2)
            if scopes:
                ws.autofilter(0,0,len(scopes),len(HEADER)-1)
            if name in ('Annees', 'Annees scolaires', 'Mois') and scopes:
                chart=wb.add_chart({'type':'column','subtype':'stacked'})
                for col in (2,3,4,5):
                    chart.add_series({'name':[name,0,col],
                        'categories':[name,1,1,len(scopes),1],
                        'values':[name,1,col,len(scopes),col]})
                chart.set_title({'name':'Presence, absences et jours mixtes'})
                chart.set_y_axis({'name':'Journees-enfants'})
                chart.set_size({'width':790,'height':365})
                ws.insert_chart('O3', chart)
                rate=wb.add_chart({'type':'line'})
                rate.add_series({'name':[name,0,10],
                    'categories':[name,1,1,len(scopes),1],
                    'values':[name,1,10,len(scopes),10]})
                rate.set_title({'name':'Taux absence (hors jours mixtes)'})
                rate.set_y_axis({'name':'%'})
                ws.insert_chart('O24',rate)
    return len(lignes(data))


def export_zip_csv(data, filename):
    """A summary and separate per-site CSVs when physical sites were certified."""
    _check(data)
    source = StringIO(newline='')
    writer = csv.writer(source,delimiter=';')
    writer.writerow(HEADER)
    writer.writerows(lignes(data))
    names=set()
    with zipfile.ZipFile(str(filename), 'w', compression=zipfile.ZIP_DEFLATED) as pack:
        pack.writestr('01_synthese.csv', ('\ufeff' + source.getvalue()).encode('utf-8'))
        for index, (site, values) in enumerate(sorted(data['sites'].items()),2):
            import re
            short = re.sub('[^A-Za-z0-9_-]+','_',site).strip('_')[:35] or 'site'
            filename = '%02d_%s.csv' % (index,short)
            if filename.lower() in names:
                filename = '%02d_site.csv' % index
            names.add(filename.lower())
            stream = StringIO(newline='')
            part = csv.writer(stream,delimiter=';')
            part.writerow(HEADER)
            part.writerow(_row('Site ' + site, ' au '.join(data['periode']), values))
            for year, value in data['sites_annees'][site].items():
                part.writerow(_row('Site ' + site,year,value))
            for school_year, value in data['sites_annees_scolaires'][site].items():
                part.writerow(_row('Site ' + site + ' (scolaire)',school_year,value))
            pack.writestr(filename,('\ufeff'+stream.getvalue()).encode('utf-8'))
    return 1 + len(data['sites'])
