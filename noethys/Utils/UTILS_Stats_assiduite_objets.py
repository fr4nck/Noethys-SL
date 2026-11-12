# -*- coding: utf-8 -*-
"""Adapter for existing Noethys MODELES.Texte/Tableau/Graphe objects."""
from __future__ import annotations

from html import escape
from datetime import date
from Utils.UTILS_Stats_assiduite import Configuration, Lecteur

LABELS = (('present', 'Presents'), ('absentj', 'Absences justifiees'),
          ('absenti', 'Absences injustifiees'), ('mixte', 'Journees mixtes'))


def est_disponible(params):
    return (params.get('mode') == 'presents' and
            bool(params.get('listeActivites')) and
            isinstance(params.get('periode'),dict))


def obtenir_resultat(db, params):
    if not est_disponible(params):
        raise ValueError('Attendance report requires activity and dated Presents mode')
    conf = params.get('assiduite_configuration')
    selected = tuple(sorted(set(params['listeActivites'])))
    if conf is None:
        conf = Configuration(selected)
    if not isinstance(conf, Configuration) or set(conf.activites) != set(selected):
        raise ValueError('Selected activities and validated scope do not match')
    periode = params['periode']
    start, end = periode.get('date_debut'), periode.get('date_fin')
    if start is None or end is None:
        raise ValueError('A complete attendance period is required')
    as_str = lambda d: d.isoformat() if isinstance(d,date) else str(d)
    key = (as_str(start), as_str(end), repr(conf), selected)
    cache = getattr(db,'_assiduite_stats_cache',None)
    if cache is not None and cache[0] == key:
        return cache[1]
    data = Lecteur(db, conf).lire(start, end)
    try:
        db._assiduite_stats_cache = (key, data)
    except (AttributeError, TypeError):
        pass
    return data


def construire_classes(MODELES):
    class TextePrecautions(MODELES.Texte):
        def __init__(self):
            super().__init__()
            self.code = 'assiduite_precautions'
            self.nom = 'Perimetre et limites'
        def MAJ(self, DB=None, dictParametres=None):
            self.dictParametres = dictParametres or {}
            if not est_disponible(self.dictParametres):
                self.texte = '<P>Choisissez le mode Presents et une periode.</P>'
                return self
            v = obtenir_resultat(DB,self.dictParametres)
            self.texte = ('<P><B>Perimetre :</B> ' + escape(v['perimetre_unites']) +
                '. Les journees-enfants sont dedoublonnees. Les jours mixtes ne '
                'sont pas forces dans une categorie. Le taux exclut ces jours.</P>' +
                '<P><B>Annulations :</B> ' + escape(v['annulations']['explication']) +
                '</P>' +
                ('<P><B>Attention :</B> %d statut(s) inconnu(s) a examiner.</P>' %
                 sum(v['etats_non_reconnus'].values()) if v['etats_non_reconnus'] else ''))
            return self

    class TableauAnnees(MODELES.Tableau):
        def __init__(self):
            super().__init__()
            self.code = 'assiduite_annees'
            self.nom = 'Presence et absences - par annee'
            self.largeur = '900'
        def MAJ(self, DB=None, dictParametres=None):
            self.dictParametres = dictParametres or {}
            self.lignes=[];self.totaux=[]
            self.colonnes=[('Annee','65'),('Presents','90'),('Justifiees','90'),
                           ('Injustifiees','90'),('Mixtes','75'),('Reservations','95'),
                           ('Taux absence hors mixtes','150'),('Periode','90')]
            if not est_disponible(self.dictParametres):return self
            data=obtenir_resultat(DB,self.dictParametres)
            for year,value in data['annees'].items():
                j=value['journees_enfants']
                pct=value['taux_absence_pct']
                self.lignes.append((year,j['present'],j['absentj'],j['absenti'],j['mixte'],
                                    value['lignes']['reservation'],
                                    'n.d.' if pct is None else '%.2f %%' % pct,
                                    ('Partielle' if not value['annee_complete_dans_periode'] else
                                     ('Complete' if value.get('annee_terminee') else 'En cours')))
            return self

    class TableauMois(MODELES.Tableau):
        def __init__(self):
            super().__init__()
            self.code='assiduite_mois'
            self.nom='Presence et absences - par mois'
            self.largeur='780'
        def MAJ(self, DB=None, dictParametres=None):
            self.dictParametres=dictParametres or {}
            self.colonnes=[('Mois','110'),('Presents','80'),('Justifiees','85'),
                           ('Injustifiees','85'),('Mixtes','80'),('Reservations','85'),
                           ('Taux absence','130')]
            self.lignes=[];self.totaux=[]
            if not est_disponible(self.dictParametres):return self
            v=obtenir_resultat(DB,self.dictParametres)
            for month,row in v['mois'].items():
                j=row['journees_enfants'];p=row['taux_absence_pct']
                self.lignes.append((month,j['present'],j['absentj'],j['absenti'],j['mixte'],
                                    row['lignes']['reservation'],
                                    'n.d.' if p is None else '%.2f %%' % p))
            return self

    class TableauRepartition(MODELES.Tableau):
        def __init__(self):
            super().__init__()
            self.code='assiduite_repartition'
            self.nom='Repartition de la presence et des absences'
            self.colonnes=[('Etat','245'),('Journees-enfants','120')]
            self.largeur='420'
        def MAJ(self, DB=None, dictParametres=None):
            self.dictParametres=dictParametres or {}
            self.lignes=[];self.totaux=[]
            if not est_disponible(self.dictParametres):return self
            v=obtenir_resultat(DB,self.dictParametres)['global']
            self.lignes=[(label,v['journees_enfants'][code]) for code,label in LABELS]
            self.totaux=[('Journees pointees',v['journees_pointees'])]
            return self

    class TableauSites(MODELES.Tableau):
        def __init__(self):
            super().__init__()
            self.code='assiduite_sites'
            self.nom='Par site : exige un rattachement valide'
            self.colonnes=[('Site','180'),('Presents','90'),('Justifiees','90'),
                           ('Injustifiees','90'),('Mixtes','80'),('Taux absence','125')]
            self.largeur='750'
        def MAJ(self, DB=None, dictParametres=None):
            self.dictParametres=dictParametres or {}
            self.lignes=[];self.totaux=[]
            if not est_disponible(self.dictParametres):return self
            v=obtenir_resultat(DB,self.dictParametres)
            for site,record in v['sites'].items():
                d=record['journees_enfants'];pct=record['taux_absence_pct']
                self.lignes.append((escape(site),d['present'],d['absentj'],d['absenti'],
                                    d['mixte'],'n.d.' if pct is None else '%.2f %%' % pct))
            return self

    class GrapheAnnees(MODELES.Graphe):
        def __init__(self):
            super().__init__()
            self.code='assiduite_graphe_annees'
            self.nom='Evolution annuelle des absences'
            self.taille=(800,430)
        def MAJ(self, figure=None, DB=None, dictParametres=None):
            self.dictParametres=dictParametres or {}
            ax=figure.add_subplot(111)
            if not est_disponible(self.dictParametres):
                ax.set_axis_off();return figure
            v=obtenir_resultat(DB,self.dictParametres)
            keys=list(v['annees'])
            bottom=[0]*len(keys)
            for state,label in LABELS:
                values=[v['annees'][year]['journees_enfants'][state] for year in keys]
                ax.bar(keys,values,bottom=bottom,label=label)
                bottom=[a+b for a,b in zip(bottom,values)]
            ax.legend(loc='upper left',fontsize=8)
            ax.set_ylabel('Journees-enfants (pointage)')
            ax.set_title('Frequentation annuelle - annees partielles signalees au tableau')
            figure.tight_layout()
            return figure

    class GrapheMois(MODELES.Graphe):
        def __init__(self):
            super().__init__()
            self.code='assiduite_graphe_mois'
            self.nom='Evolution mensuelle des absences'
            self.taille=(900,430)
        def MAJ(self, figure=None, DB=None, dictParametres=None):
            self.dictParametres=dictParametres or {}
            ax=figure.add_subplot(111)
            if not est_disponible(self.dictParametres):
                ax.set_axis_off();return figure
            v=obtenir_resultat(DB,self.dictParametres)
            months=list(v['mois']);step=max(1,len(months)//18)
            xs=list(range(len(months)))
            for state,label in LABELS[:3]:
                vals=[v['mois'][m]['journees_enfants'][state] for m in months]
                ax.plot(xs,vals,marker='o',label=label,markersize=2)
            ax.set_xticks(xs[::step])
            ax.set_xticklabels(months[::step],rotation=45,ha='right',fontsize=8)
            ax.set_ylabel('Journees-enfants')
            ax.set_title('Evolution mensuelle des pointages')
            ax.legend(loc='upper left',fontsize=8)
            figure.tight_layout()
            return figure

    class GrapheSecteurs(MODELES.Graphe):
        def __init__(self):
            super().__init__()
            self.code='assiduite_graphe_secteurs'
            self.nom='Presence et absences - parts'
            self.taille=(690,410)
        def MAJ(self, figure=None, DB=None, dictParametres=None):
            self.dictParametres=dictParametres or {}
            ax=figure.add_subplot(111)
            if not est_disponible(self.dictParametres):
                ax.set_axis_off();return figure
            v=obtenir_resultat(DB,self.dictParametres)['global']
            rows=[(code,label,v['journees_enfants'][code]) for code,label in LABELS]
            nonzero=[r for r in rows if r[2]>0]
            if nonzero:
                wedges,_=ax.pie([x[2] for x in nonzero],startangle=90)
                colors={x[0]:p.get_facecolor() for x,p in zip(nonzero,wedges)}
                ax.axis('equal')
            else:
                colors={}
                ax.text(.5,.5,'Aucune journee pointee',ha='center',va='center',transform=ax.transAxes)
            from matplotlib.patches import Patch
            handles=[Patch(facecolor=colors.get(code,(.82,.82,.82,1))) for code,_,v in rows]
            legend=[('%s : %d' % (label,number)) for _,label,number in rows]
            ax.legend(handles,legend,loc='center left',bbox_to_anchor=(1,.5))
            figure.subplots_adjust(right=.62)
            return figure

    class TableauAnneesScolaires(MODELES.Tableau):
        def __init__(self):
            super().__init__()
            self.code = 'assiduite_annees_scolaires'
            self.nom = 'Presence et absences - annees scolaires (septembre-aout)'
            self.largeur = '900'
        def MAJ(self, DB=None, dictParametres=None):
            self.dictParametres = dictParametres or {}
            self.lignes = []; self.totaux = []
            self.colonnes = [('Annee scolaire','105'),('Presents','90'),
                            ('Justifiees','90'),('Injustifiees','90'),
                            ('Mixtes','75'),('Reservations','95'),
                            ('Taux absence hors mixtes','150'),('Couverture','90')]
            if not est_disponible(self.dictParametres):
                return self
            data = obtenir_resultat(DB, self.dictParametres)
            for label, value in data['annees_scolaires'].items():
                j = value['journees_enfants']
                pct = value['taux_absence_pct']
                coverage = ('Partielle' if not value['annee_scolaire_complete_dans_periode']
                            else ('Complete' if value['annee_scolaire_terminee'] else 'En cours'))
                self.lignes.append((label,j['present'],j['absentj'],j['absenti'],
                                   j['mixte'],value['lignes']['reservation'],
                                   'n.d.' if pct is None else '%.2f %%' % pct,coverage))
            return self

    class GrapheAnneesScolaires(MODELES.Graphe):
        def __init__(self):
            super().__init__()
            self.code = 'assiduite_graphe_annees_scolaires'
            self.nom = 'Comparaison des annees scolaires'
            self.taille = (820,430)
        def MAJ(self, figure=None, DB=None, dictParametres=None):
            self.dictParametres = dictParametres or {}
            ax = figure.add_subplot(111)
            if not est_disponible(self.dictParametres):
                ax.set_axis_off(); return figure
            data = obtenir_resultat(DB, self.dictParametres)
            years = list(data['annees_scolaires'])
            bottom = [0] * len(years)
            for state, label in LABELS:
                values = [data['annees_scolaires'][year]['journees_enfants'][state]
                          for year in years]
                ax.bar(years, values, bottom=bottom, label=label)
                bottom = [a+b for a,b in zip(bottom,values)]
            ax.legend(loc='upper left', fontsize=8)
            ax.set_ylabel('Journees-enfants')
            ax.set_title('Annees scolaires : consulter la couverture dans le tableau')
            figure.tight_layout()
            return figure

    return (TextePrecautions,TableauAnnees,TableauMois,TableauRepartition,
            TableauSites,GrapheAnnees,GrapheMois,GrapheSecteurs,
            TableauAnneesScolaires,GrapheAnneesScolaires)


def preparer_pages(MODELES, rubriques):
    """Append a dedicated attendance rubric, without altering old pages."""
    if any(row.get('code') == 'assiduite' for row in rubriques):
        return rubriques
    (T,A,M,R,S,G,H,P,AS,GS)=construire_classes(MODELES)
    rubriques.append({
        'nom': 'Frequentation', 'code':'assiduite', 'image':None,
        'ctrl_notebook':None,'visible':True,
        'pages':[
            {'nom':'Bilan annuel', 'code':'assiduite_bilan', 'image':None,
             'ctrl_html':None, 'visible':True,'objets':[T(),A(),G()]},
            {'nom':'Evolution mensuelle', 'code':'assiduite_evolution', 'image':None,
             'ctrl_html':None, 'visible':True,'objets':[M(),H()]},
            {'nom':'Repartition et sites', 'code':'assiduite_sites', 'image':None,
             'ctrl_html':None, 'visible':True,'objets':[R(),P(),S()]},
            {'nom':'Annees scolaires', 'code':'assiduite_scolaires', 'image':None,
             'ctrl_html':None, 'visible':True,'objets':[AS(),GS()]},
        ]})
    return rubriques


from Utils import UTILS_Stats_modeles as MODELES
(TextePrecautions,TableauAnnees,TableauMois,TableauRepartition,TableauSites,
 GrapheAnnees,GrapheMois,GrapheSecteurs,
 TableauAnneesScolaires,GrapheAnneesScolaires)=construire_classes(MODELES)
