#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q442/J4: UI-adapter candidates for existing MODELES.Tableau/Graphe.

This does NOT register these objects in DLG_Stats or import wx by itself.
Each object delegates to one shared, read-only result on a single DB connection.
The physical-site configuration MUST have been validated externally.
"""
from __future__ import annotations

import csv
from html import escape as html_escape
from datetime import date

from Utils.UTILS_Stats_qf_sites import ConfigurationMultisite, LecteurMultisite

POPULATIONS = {'familles':'familles','individus':'enfants'}
NATURES = {'qf':'qf','tarifs':'tarifs_indicatifs'}


def _periode(dictParametres):
    if dictParametres.get('mode') != 'presents':
        raise ValueError('Q442 only available in Presents mode')
    periode = dictParametres.get('periode')
    if not isinstance(periode, dict):
        raise ValueError('Explicit statistical period required')
    a,b = periode.get('date_debut'), periode.get('date_fin')
    a = a.isoformat() if isinstance(a,date) else a
    b = b.isoformat() if isinstance(b,date) else b
    if not isinstance(a,str) or not isinstance(b,str):
        raise ValueError('Invalid statistical dates')
    return a,b


def est_disponible(dictParametres):
    """No QF in Inscrits and no implicit activity/site mapping."""
    conf=dictParametres.get('q442_configuration')
    return (dictParametres.get('mode') == 'presents'
            and isinstance(conf, ConfigurationMultisite)
            and set(dictParametres.get('listeActivites', ())) == set(conf.activities))


def obtenir_resultat(db, dictParametres):
    """Single connection-scoped cache, no re-run of facture calculations.

    If database content changes mid-dialog, callers must invalidate this
    cache, e.g. by re-opening the stats screen/connection. No cross-DB cache.
    """
    conf=dictParametres.get('q442_configuration')
    if not isinstance(conf, ConfigurationMultisite):
        raise ValueError('Q442 explicit multisite mapping not provided or validated')
    if set(dictParametres.get('listeActivites',[])) != set(conf.activities):
        raise ValueError('Activities selected differ from validated Q442 mapping')
    a,b=_periode(dictParametres)
    selected=dictParametres.get('q442_sites')
    cache_key=(a,b,repr(conf),repr(selected),tuple(sorted(conf.activities)))
    cache=getattr(db,'_q442_j4_cache',None)
    if isinstance(cache,dict) and cache.get('key')==cache_key:
        return cache['result']
    data=LecteurMultisite(db,conf).lire(a,b,selection_sites=selected)
    try:
        db._q442_j4_cache={'key':cache_key,'result':data}
    except (AttributeError,TypeError):
        pass
    return data


def _vue(db,dictParametres,population,nature):
    if population not in POPULATIONS or nature not in NATURES:
        raise ValueError('Unknown Q442 category')
    r=obtenir_resultat(db,dictParametres)
    choix=dictParametres.get('q442_vue','global')
    if choix=='global':
        scope=r['global']
    else:
        if choix not in r['sites']:
            raise ValueError('Selected site outside the Q442 report')
        scope=r['sites'][choix]
    values=scope[POPULATIONS[population]]
    return r, values, values[NATURES[nature]],values[
        'pourcentages_qf' if nature=='qf' else 'pourcentages_tarifs_indicatifs']


def construire_classes(MODELES):
    """Factory for genuine MODELES.Tableau and MODELES.Graphe bases.

    In the repository, pass Utils.UTILS_Stats_modeles directly; isolated
    tests supply a headless surrogate because wx is unavailable here.
    """
    class TableauQ442(MODELES.Tableau):
        def __init__(self,population,nature):
            MODELES.Tableau.__init__(self)
            self.population=population
            self.nature=nature
            self.code='q442_tableau_'+population+'_'+nature
            self.categorie='tableau'
            self.nom='QF / tarifs - '+population+' - '+nature
            self.largeur='540'

        def MAJ(self, DB=None, dictParametres=None):
            self.dictParametres=dictParametres or {}
            if not est_disponible(self.dictParametres):
                self.nom='QF : disponible uniquement en mode Presents, avec le perimetre valide'
                self.colonnes=[]
                self.lignes=[]
                self.totaux=[]
                return self
            r,obs,counts,pcts=_vue(DB,self.dictParametres,self.population,self.nature)
            self.nom=('QF connus / non communiques' if self.nature=='qf'
                      else 'Categories tarifaires INDICATIVES (historique non certifie)')
            unite='familles' if self.population=='familles' else 'enfants'
            self.colonnes=[('Categorie', '260'),('Nombre de '+unite,'120'),('Part du total','120')]
            self.lignes=[(html_escape(str(label)),count,'%.2f %%' % pcts[label])
                         for label,count in counts.items()]
            self.totaux=[('TOTAL',obs['total'],'100 %' if obs['total'] else '0 %')]
            return self

    class GrapheBarresQ442(MODELES.Graphe):
        def __init__(self,population,nature):
            MODELES.Graphe.__init__(self)
            self.population=population
            self.nature=nature
            self.code='q442_barres_'+population+'_'+nature
            self.categorie='graphe'
            self.taille=(650,400)
            self.nom='Categories QF - barres'

        def MAJ(self,figure=None,DB=None,dictParametres=None):
            self.dictParametres=dictParametres or {}
            if not est_disponible(self.dictParametres):
                ax=figure.add_subplot(111)
                ax.text(.5,.5,'QF uniquement en mode Presents\navec un perimetre valide',
                        ha='center',va='center',transform=ax.transAxes)
                ax.set_axis_off()
                return figure
            r,obs,counts,pcts=_vue(DB,self.dictParametres,self.population,self.nature)
            ax=figure.add_subplot(111)
            labels=list(counts)
            values=list(counts.values())
            bars=ax.bar(range(len(labels)),values)
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels,rotation=38,ha='right',fontsize=8)
            ax.set_ylabel('Nombre de '+ ('familles' if self.population=='familles' else 'enfants'))
            for bar,v in zip(bars,values):
                ax.annotate(str(v),(bar.get_x()+bar.get_width()/2,v),
                            ha='center',va='bottom',fontsize=8)
            titre='QF' if self.nature=='qf' else 'Tarifs indicatifs (non attestes)'
            ax.set_title(titre+' - total '+str(obs['total']))
            ax.set_ylim(bottom=0,top=max([1]+values)*1.22)
            figure.subplots_adjust(bottom=0.32)
            return figure

    class GrapheSecteursQ442(MODELES.Graphe):
        def __init__(self,population,nature):
            MODELES.Graphe.__init__(self)
            self.population=population
            self.nature=nature
            self.code='q442_secteurs_'+population+'_'+nature
            self.categorie='graphe'
            self.taille=(650,430)
            self.nom='Categories QF - secteurs'

        def MAJ(self,figure=None,DB=None,dictParametres=None):
            self.dictParametres=dictParametres or {}
            if not est_disponible(self.dictParametres):
                ax=figure.add_subplot(111)
                ax.text(.5,.5,'QF uniquement en mode Presents\navec un perimetre valide',
                        ha='center',va='center',transform=ax.transAxes)
                ax.set_axis_off()
                return figure
            r,obs,counts,pcts=_vue(DB,self.dictParametres,self.population,self.nature)
            ax=figure.add_subplot(111)
            present=[(label,val) for label,val in counts.items() if val>0]
            if present:
                wedges, _=ax.pie([v for _,v in present],startangle=90)
                ax.axis('equal')
            else:
                ax.text(.5,.5,'Aucune presence',ha='center',va='center',transform=ax.transAxes)
                wedges=[]
            from matplotlib.patches import Patch
            # Legend colors must match real wedges; zero categories stay
            # visible with a neutral legend swatch, never fake pie slices.
            wedge_colors={label:w.get_facecolor() for (label,_),w in zip(present,wedges)}
            keys=list(counts)
            handles=[Patch(facecolor=wedge_colors.get(k,(.82,.82,.82,1))) for k in keys]
            legend_labels=['%s : %d (%.2f %%)' % (k,counts[k],pcts[k]) for k in keys]
            ax.legend(handles,legend_labels,loc='center left',bbox_to_anchor=(1,.5),fontsize=7)
            ax.set_title(('QF' if self.nature=='qf' else 'Tarifs indicatifs')+' - '+str(obs['total']))
            figure.subplots_adjust(right=.56)
            return figure

    return TableauQ442,GrapheBarresQ442,GrapheSecteursQ442


def preparer_pages(MODELES, liste_objets, configuration=None, mode='presents'):
    """Opt-in UI page blueprint. No live wx page/production change.

    Requires verified configuration and mode. Appending is idempotent.
    """
    if configuration is None or mode!='presents':
        return liste_objets
    if not isinstance(configuration, ConfigurationMultisite):
        raise ValueError('Configuration sites not verified')
    T,B,C=construire_classes(MODELES)
    for rubrique in liste_objets:
        if rubrique.get('code') not in ('individus','familles'):
            continue
        nom=rubrique['code']
        existing={page['code'] for page in rubrique.get('pages',[])}
        for nature,desc in [('qf','Quotient familial'),('tarifs','Categories tarifaires')]:
            code='q442_'+nom+'_'+nature
            if code in existing:
                continue
            rubrique['pages'].append({
                'nom':desc,'code':code,'image':None,'ctrl_html':None,
                'visible':True,'objets':[T(nom,nature),B(nom,nature),C(nom,nature)],
            })
    return liste_objets


def export_xlsx_aggreges(data, filename):
    """Aggregated XLSX (general + selected sites) using existing XlsxWriter.

    No personal identifiers, monetary amounts or individual QF values. The
    historical tariff categories remain explicitly marked as INDICATIVE.
    Text is written as strings (never spreadsheet formulas or URLs).
    """
    try:
        import xlsxwriter
    except ImportError as exc:
        raise RuntimeError('Export Excel indisponible : XlsxWriter absent du paquet') from exc

    if 'global' not in data or 'sites' not in data:
        raise ValueError('Resultat Q442 incomplet pour export Excel')
    used_names = set()
    total_rows = 0

    def sheet_name(location):
        clean = ''.join('_' if ch in '[]:*?/\\' else ch for ch in str(location)).strip()
        clean = (clean or 'Site')[:31]
        name = clean
        counter = 2
        while name.casefold() in used_names:
            suffix = ' (%s)' % counter
            name = clean[:31-len(suffix)]+suffix
            counter += 1
        used_names.add(name.casefold())
        return name

    with xlsxwriter.Workbook(str(filename), {
            'strings_to_formulas': False,
            'strings_to_urls': False,
            'default_date_format': 'dd/mm/yyyy',
            }) as workbook:
        header = workbook.add_format({'bold':True,'font_color':'white',
                                      'bg_color':'#34465D'})
        pct_format=workbook.add_format({'num_format':'0.00%'})
        for location, view in [('Synthese generale',data['global']), *list(data['sites'].items())]:
            sheet=sheet_name(location)
            ws=workbook.add_worksheet(sheet)
            ws.write_string(0,0,'Statistiques QF / categories tarifaires')
            ws.write_string(1,0,'Periode')
            ws.write_string(1,1,' au '.join(map(str,data.get('dates',['?','?']))))
            ws.write_string(2,0,'Limite')
            ws.write_string(2,1,'Tarifs : categories indicatives, historiques non attestes')
            ws.write_row(3,0,('Site','Population','Representation','Categorie','Effectif',
                               'Pourcentage','Statut'),header)
            row=4
            charts=[]
            for population in ('familles','enfants'):
                record=view[population]
                total=record['total']
                for nature in ('qf','tarifs_indicatifs'):
                    counts=record[nature]
                    pct_key=('pourcentages_qf' if nature=='qf'
                             else 'pourcentages_tarifs_indicatifs')
                    pcts=record[pct_key]
                    if sum(counts.values())!=total or set(counts)!=set(pcts):
                        raise ValueError('Totaux Q442 incoherents : %s/%s' % (location,population))
                    first=row
                    for category,num in counts.items():
                        if not isinstance(num,int) or num<0:
                            raise ValueError('Effectif Q442 invalide')
                        status=('QF connu ou non communique' if nature=='qf'
                                else 'Tarif indicatif : non atteste historiquement')
                        for col,text in ((0,location),(1,population),(2,nature),
                                         (3,category),(6,status)):
                            ws.write_string(row,col,str(text))
                        ws.write_number(row,4,num)
                        ws.write_number(row,5,pcts[category]/100.0,pct_format)
                        row += 1
                        total_rows += 1
                    if row>first:
                        charts.append((population,nature,first,row-1))
            ws.freeze_panes(4,4)
            ws.autofilter(3,0,row-1,6)
            for c,width in ((0,24),(1,14),(2,22),(3,38),(4,12),(5,16),(6,48)):
                ws.set_column(c,c,width)
            for index,(pop,nature,first,last) in enumerate(charts):
                bar=workbook.add_chart({'type':'column'})
                bar.add_series({'name':'Effectifs',
                    'categories':[sheet,first,3,last,3],
                    'values':[sheet,first,4,last,4]})
                bar.set_title({'name':'%s - %s (categories a zero comprises)' % (pop,nature)})
                bar.set_y_axis({'name':'Effectif'})
                bar.set_legend({'none':True})
                bar.set_size({'width':680,'height':300})
                ws.insert_chart(4+18*index,8,bar)
                pie=workbook.add_chart({'type':'pie'})
                pie.add_series({'name':'Proportions',
                    'categories':[sheet,first,3,last,3],
                    'values':[sheet,first,4,last,4]})
                pie.set_title({'name':'%s - %s (proportions)' % (pop,nature)})
                pie.set_legend({'position':'right'})
                pie.set_size({'width':560,'height':300})
                ws.insert_chart(4+18*index,20,pie)
    return total_rows


def export_csv_aggreges(data, filename):
    """Non-nominative CSV, general and selected sites, all categories including zeros."""
    def csv_safe(value):
        # Spreadsheet importers may interpret formulas from CSV text.
        s=str(value)
        return "'"+s if s.lstrip().startswith(('=','+','-','@')) or s.startswith(('\t','\r','\n')) else s
    rows=[]
    for location,view in [('Synthese generale',data['global']),*list(data['sites'].items())]:
        for pop in ('familles','enfants'):
            record=view[pop]
            for nature in ('qf','tarifs_indicatifs'):
                percent_key=('pourcentages_qf' if nature=='qf'
                             else 'pourcentages_tarifs_indicatifs')
                for category,num in record[nature].items():
                    rows.append({'site':csv_safe(location),'population':pop,'representation':nature,
                                 'categorie':csv_safe(category),'effectif':num,
                                 'pourcentage':record[percent_key][category],
                                 'statut':'indicatif_non_atteste' if nature=='tarifs_indicatifs'
                                          else 'QF_reconstitue_date_presence'})
    with open(filename,'w',encoding='utf-8',newline='') as stream:
        wr=csv.DictWriter(stream,fieldnames=('site','population','representation',
                          'categorie','effectif','pourcentage','statut'),delimiter=';')
        wr.writeheader()
        wr.writerows(rows)
    return len(rows)

def export_csv_lot_aggreges(data, fichier_zip):
    """ZIP of non-nominative CSV files: one global, one per selected site.

    Reuse the already qualified `export_csv_aggreges` to ensure that the
    original percentages and categories remain exactly the same in each file.
    """
    import tempfile
    import zipfile
    import io
    import re
    from pathlib import Path
    with tempfile.TemporaryDirectory(prefix='noethys-q442-csv-') as rep:
        combined=Path(rep)/'statistiques_qf.csv'
        export_csv_aggreges(data,combined)
        with combined.open('r',encoding='utf-8',newline='') as source:
            reader=csv.DictReader(source,delimiter=';')
            fields=tuple(reader.fieldnames or ())
            rows=list(reader)
        if not fields or not rows:
            raise ValueError('Absence de categories Q442 pour export')
        locations=['Synthese generale',*list(data['sites'])]
        with zipfile.ZipFile(fichier_zip,'w',compression=zipfile.ZIP_DEFLATED) as output:
            for ix,location in enumerate(locations):
                selected=[r for r in rows if r['site']==location]
                if not selected:
                    raise ValueError('Aucune ligne pour un site selectionne: '+str(location))
                short=re.sub(r'[^A-Za-z0-9_-]+','_',location).strip('_')[:42] or 'site'
                out=io.StringIO(newline='')
                writer=csv.DictWriter(out,fieldnames=fields,delimiter=';')
                writer.writeheader()
                writer.writerows(selected)
                output.writestr('%02d_%s.csv' % (ix+1,short),out.getvalue().encode('utf-8-sig'))
    return len(rows)


# Bind to the original wx statistical object types, once this candidate is deployed.
from Utils import UTILS_Stats_modeles as MODELES
TableauQ442, GrapheBarresQ442, GrapheSecteursQ442 = construire_classes(MODELES)
