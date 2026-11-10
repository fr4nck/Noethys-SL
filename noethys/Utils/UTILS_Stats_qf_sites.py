#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q442/J4: read-only QF statistics, explicit real-site mapping.

Research candidate; NEVER import into deployed Noethys-SL without validation.
Sources are the wx tables in DATA_Tables.py at
  e86fabedece82f6cc1cade70074207291f8d9dfb.
No data modification, invoice issuance, tariff calculation, or migration.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Mapping, Optional

from Utils.UTILS_Stats_qf_lecture import (
    Configuration, Lecteur, SRC_WX,
    QF_UNKNOWN, QF_REVIEW,
)
from Utils.UTILS_Stats_qf_lecture import TARIF_UNKNOWN
from Utils.UTILS_Stats_qf_lecture import _int, _iso, _csv_ints


@dataclass(frozen=True)
class SiteRegle:
    """Explicit activity + accueil unit + optional group -> named physical site.

    If ``groupes`` is None, ALL groups for these units are accepted; this
    can only be used if there is no conflicting rule for another site.
    """
    site: str
    activite: int
    unites: tuple[int, ...]
    groupes: Optional[tuple[int | None, ...]] = None

    def __post_init__(self):
        if not isinstance(self.site, str) or not self.site.strip():
            raise ValueError('SiteRegle: blank site name')
        _int(self.activite, 'activity')
        if not self.unites:
            raise ValueError('SiteRegle: empty accueil units')
        for v in self.unites:
            _int(v, 'unit')
        if len(set(self.unites)) != len(self.unites):
            raise ValueError('SiteRegle: duplicate units')
        if self.groupes is not None:
            if not self.groupes or len(set(self.groupes)) != len(self.groupes):
                raise ValueError('SiteRegle: empty/duplicate group condition')
            for v in self.groupes:
                if v is not None:
                    _int(v, 'group')

    def accepte(self, act, unite, groupe):
        return (act == self.activite and unite in self.unites
                and (self.groupes is None or groupe in self.groupes))


def _regles_chevauchent(a, b):
    return (a.activite == b.activite
            and bool(set(a.unites) & set(b.unites))
            and (a.groupes is None or b.groupes is None
                 or bool(set(a.groupes) & set(b.groupes))))


@dataclass(frozen=True)
class ConfigurationMultisite:
    regles: tuple[SiteRegle, ...]
    tarifs_accueil: Mapping[int, tuple[int, ...]]
    libelles: Mapping[str, str]
    categories_historiques: tuple[str, ...] = ()
    exiger_grille_commune: bool = True

    def __post_init__(self):
        if not self.regles:
            raise ValueError('Explicit real-site mapping required')
        acts = {r.activite for r in self.regles}
        if acts != set(self.tarifs_accueil):
            raise ValueError('Accueil tariffs must cover exactly mapped activities')
        for act, ids in self.tarifs_accueil.items():
            _int(act, 'activity')
            _csv_ints(ids)
            if len(ids) != len(set(ids)):
                raise ValueError('Duplicate approved tariff IDs')
        for i, a in enumerate(self.regles):
            for b in self.regles[i + 1:]:
                if _regles_chevauchent(a, b):
                    raise ValueError('Overlapping/ambiguous rules, including same-site duplicates')
        if len(set(self.libelles.values())) != len(self.libelles):
            raise ValueError('Distinct tariff codes must not share a display label')
        if not self.exiger_grille_commune:
            raise ValueError('Different grids are not allowed for a single multisite ALSH')
        if any(x in ('', None) for x in self.categories_historiques):
            raise ValueError('Empty historical category')
        if len(set(self.categories_historiques)) != len(self.categories_historiques):
            raise ValueError('Duplicate historical category')
        if set(self.categories_historiques) & set(self.libelles.values()):
            raise ValueError('Historical and current categories collide: mapping must be explicit')

    @property
    def site_names(self):
        return tuple(sorted({r.site for r in self.regles}))

    @property
    def activities(self):
        return tuple(sorted(self.tarifs_accueil))

    def base_configuration(self):
        byact = defaultdict(set)
        for r in self.regles:
            byact[r.activite].update(r.unites)
        return Configuration(
            sites={act: '_ACTIVITE_%s_' % act for act in self.activities},
            unites_accueil={act: tuple(sorted(byact[act])) for act in self.activities},
            tarifs_accueil=self.tarifs_accueil,
            libelles=self.libelles,
            categories_historiques=self.categories_historiques,
            exiger_grille_commune=True,
        )


class SiteNonResoluble(RuntimeError):
    pass


class LecteurMultisite(Lecteur):
    """Uses J3 tariff/QF logic without recalculating prestations.

    Site selection requires the real `consommations.IDgroupe` or disjoint
    `IDunite` and refuses to infer a physical location from IDactivite alone.
    """
    def __init__(self, db, configuration: ConfigurationMultisite):
        self.config_multisite = configuration
        super().__init__(db, configuration.base_configuration())
        self.exclus_hors_unites_accueil = 0

    def _presences(self, debut, fin):
        sql = """SELECT c.IDconso,c.date,c.IDindividu,c.IDactivite,c.IDunite,c.IDgroupe,
                      c.IDprestation,c.IDcategorie_tarif,cp.IDfamille,
                      p.IDprestation,p.IDtarif,p.IDcategorie_tarif,p.IDfamille,
                      p.IDindividu,p.IDactivite,p.date,p.categorie,p.IDfacture,
                      t.methode,t.IDtype_quotient,
                      u.IDactivite,g.IDactivite,i.IDfamille
                 FROM consommations c
                 LEFT JOIN comptes_payeurs cp ON cp.IDcompte_payeur=c.IDcompte_payeur
                 LEFT JOIN prestations p ON p.IDprestation=c.IDprestation
                 LEFT JOIN tarifs t ON t.IDtarif=p.IDtarif
                 LEFT JOIN unites u ON u.IDunite=c.IDunite
                 LEFT JOIN groupes g ON g.IDgroupe=c.IDgroupe
                 LEFT JOIN inscriptions i ON i.IDinscription=c.IDinscription
                 WHERE c.etat='present' AND c.date>='%s' AND c.date<='%s'
                   AND c.IDactivite IN %s
                 ORDER BY c.date,c.IDconso""" % (
                     debut,fin,_csv_ints(self.config_multisite.activities))
        expected_units = {act: set(self.conf.unites_accueil[act])
                          for act in self.config_multisite.activities}
        observations = []
        for row in self._read(sql):
            (idconso, jour, child, act, unit, group, prestation, cat_conso,
             family, idprestation, tariff, cat_prestation, pfam, pchild,
             pact, pdate, ptype, invoice, methode, typeqf,
             unit_act, group_act, inscrit_family) = row
            # SQLite commonly returns ISO TEXT whereas the MySQL connector
            # may return datetime.date objects. Normalize before grouping.
            jour = _iso(jour)
            pdate = _iso(pdate) if pdate is not None else None
            if unit not in expected_units[act]:
                self.exclus_hors_unites_accueil += 1
                continue
            matching = [r.site for r in self.config_multisite.regles
                        if r.accepte(act,unit,group)]
            if len(matching) != 1:
                raise SiteNonResoluble('PRESENCE_SITE_NON_RESOLU: accueil row=%s activity=%s unit=%s group=%s candidates=%s' %
                                       (idconso,act,unit,group,len(matching)))
            if child is None or family is None:
                raise SiteNonResoluble('Family/child linkage missing in selected accueil presence')
            if unit_act != act or (group is not None and group_act != act):
                raise SiteNonResoluble('Group or unit belongs to another activity')
            anomalies = []
            if inscrit_family is not None and inscrit_family != family:
                anomalies.append('FAMILLE_INSCRIPTION_PAYEUR_DIFFERENTE')
            if prestation is not None and idprestation is None:
                anomalies.append('PRESTATION_ORPHELINE')
            if idprestation is not None:
                if (pfam != family or pchild != child or pact != act or pdate != jour):
                    anomalies.append('LIEN_PRESTATION_INCOHERENT')
                if cat_conso != cat_prestation:
                    anomalies.append('CATEGORIE_INSCRIPTION_INCOHERENTE')
                if ptype != 'consommation':
                    anomalies.append('PRESTATION_NON_CONSOMMATION')
                if tariff not in self.conf.tarifs_accueil[act]:
                    anomalies.append('TARIF_HORS_ACCUEIL')
            else:
                anomalies.append('PRESTATION_ABSENTE')
            observations.append({
                'id':idconso,'date':jour,'enfant':child,'famille':family,
                'activite':act,'site':matching[0],
                'IDprestation':idprestation,'IDtarif':tariff,
                'IDtype_quotient':typeqf,'methode':methode,
                'anomalies':anomalies,'invoice_exists':invoice is not None,
            })
        return observations

    def lire(self, date_debut, date_fin, selection_sites=None):
        a,b = _iso(date_debut),_iso(date_fin)
        if b<a:
            raise ValueError('End before start')
        sites = (self.config_multisite.site_names if selection_sites is None
                 else tuple(sorted(set(selection_sites))))
        if not sites or not set(sites).issubset(self.config_multisite.site_names):
            raise ValueError('Invalid selected sites')
        records = self._presences(a,b)
        tarifs = self._tarifs()
        self._verifier_grille_commune(tarifs)
        qf_types={tarif['type'] for tarif in tarifs.values()}
        if len(qf_types)!=1 or None in qf_types:
            raise RuntimeError('REFERENTIEL_QF_UNIQUE_REQUIRED: different or unspecified QF types')
        # A validated shared grid+QF reference permits CURRENT-grid QF
        # classification even when a presence has no prestation yet. It
        # NEVER certifies a historical tariff or an invoiced price.
        # If candidate tariffs have different QF types, do not guess.
        for record in records:
            if (record['IDprestation'] is None and record['IDtarif'] is None
                    and record['anomalies'] == ['PRESTATION_ABSENTE']):
                allowed=self.conf.tarifs_accueil[record['activite']]
                types={tarifs[tid]['type'] for tid in allowed}
                if len(types)==1 and None not in types:
                    record['IDtarif']=min(allowed)
                    record['anomalies'].append('HYPOTHESE_TARIF_ACTIVITE')
        selection = [r for r in records if r['site'] in sites]
        quotients = self._quotients({r['famille'] for r in selection}) if selection else {}
        categories={self.conf.libelles.get(line[0],'Tranche '+line[0])
                    for t in tarifs.values() for line in t['lignes']}
        categories.update(self.conf.categories_historiques)
        def rep(rows):
            results={}
            for population in ('familles','enfants'):
                count,qf,tarif,statuts,anomalies=self._observations(
                    rows, tarifs, quotients, population)
                cq={name:0 for name in sorted(categories)}
                cq[QF_UNKNOWN]=0
                cq[QF_REVIEW]=0
                cq.update(qf)
                ct={name:0 for name in sorted(categories)}
                ct.update(tarif)
                if sum(cq.values())!=count or sum(ct.values())!=count:
                    raise AssertionError('Broken statistical denominators')
                pct_qf={key:round(n*100.0/count,2) if count else 0.0
                        for key,n in cq.items()}
                pct_t={key:round(n*100.0/count,2) if count else 0.0
                       for key,n in ct.items()}
                results[population]={
                    'total':count,'qf':cq,'tarifs_indicatifs':ct,
                    'pourcentages_qf':pct_qf,
                    'pourcentages_tarifs_indicatifs':pct_t,
                    'statuts':dict(sorted(statuts.items())),
                    'anomalies':dict(sorted(anomalies.items())),
                    'categories_tarif_attestees':0,
                    'categories_historiques_non_attestees':count,
                }
            return results
        return {
            'source_sha':SRC_WX,
            'statut':'CANDIDAT_J4_NON_INTEGRE_NON_HOMOLOGUE',
            'dates':[a,b],
            'sites_selectionnes':list(sites),
            'exclus_hors_unites_accueil':self.exclus_hors_unites_accueil,
            'precautions':[
              'Physical sites resolved via explicitly validated activity+unit+group mapping',
              'Tier values inferred from CURRENT saved QF lines; not historical evidence',
              'No receipt date for QF in DATA_Tables schema',
              'No IDligne recorded on prestation/consommation',
              'All valid present accueil attendances counted regardless of invoice',
              'Tariffs are indicative categories, never monetary amount keys',
              'Historical categories missing from current schema require explicit catalogue',
            ],
            'global':rep(selection),
            'sites':{site:rep([r for r in selection if r['site']==site])
                     for site in sites},
            'lectures_sql':len(self.requetes),
        }
