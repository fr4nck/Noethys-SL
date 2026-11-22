#!/usr/bin/env python3
# -*- coding: ascii -*-
"""Q442 J3. Prototype reader ONLY. No Noethys production import or write.

Interface to existing Noethys DB: ExecuterReq(sql) and ResultatReq().
The only database statements issued by this module begin with SELECT.
The returned 'indicative' categories are NEVER proof of historical billing tiers.
The original billing engine is not called, patched, or replaced.

Pinned source: fr4nck/Noethys-SL wx e86fabedece82f6cc1cade70074207291f8d9dfb.
Not installed in wx. For independent audit on synthetic databases only.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Mapping, Optional

SRC_WX = 'e86fabedece82f6cc1cade70074207291f8d9dfb'
QF_UNKNOWN = 'QF non communique'
QF_REVIEW = 'QF a verifier'
QF_OUTSIDE = 'QF hors bareme'
TARIF_UNKNOWN = 'Tarif non determinable'
TARIF_TIE = 'Tarifs concurrents meme date'
TARIF_UNPROVEN = 'Categorie historique non attestee'


def _int(x, what):
    if isinstance(x, bool) or not isinstance(x, int) or x <= 0:
        raise ValueError('Invalid positive integer for ' + what)
    return x


def _iso(x):
    if isinstance(x, date):
        return x.isoformat()
    if not isinstance(x, str) or len(x) != 10:
        raise ValueError('Date must be ISO YYYY-MM-DD')
    return date.fromisoformat(x).isoformat()


def _csv_ints(xs):
    values = sorted(set(_int(x, 'sql identifier') for x in xs))
    if not values:
        raise ValueError('Empty identifier set')
    return '(' + ','.join(map(str, values)) + ')'


@dataclass(frozen=True)
class Configuration:
    """Explicit site and accueil boundaries; never infer a site from SQL.

    'unites_accueil' is a strict whitelist of unit IDs. 'tarifs_accueil'
    is a per-activity whitelist of IDtarif. 'libelles' maps saved
    tarifs_lignes.tranche to a label (e.g. '1' -> 'A'). No EUR labels.
    'categories_historiques' adds codes that vanished from today's tariff.
    """
    sites: Mapping[int, str]
    unites_accueil: Mapping[int, tuple[int, ...]]
    tarifs_accueil: Mapping[int, tuple[int, ...]]
    libelles: Mapping[str, str] = field(default_factory=dict)
    categories_historiques: tuple[str, ...] = ()
    exiger_grille_commune: bool = True

    def __post_init__(self):
        if not self.sites or set(self.sites) != set(self.unites_accueil) or set(self.sites) != set(self.tarifs_accueil):
            raise ValueError('Sites, accueil units, tariffs: identical activity keys required')
        for act, site in self.sites.items():
            _int(act, 'activity')
            if not isinstance(site, str) or not site.strip():
                raise ValueError('Empty site name')
            _csv_ints(self.unites_accueil[act])
            _csv_ints(self.tarifs_accueil[act])
        if len(set(self.categories_historiques)) != len(self.categories_historiques):
            raise ValueError('Duplicate historical labels')
        for code, label in self.libelles.items():
            if not isinstance(code, str) or not isinstance(label, str) or not label.strip():
                raise ValueError('Bad label')


class Lecteur:
    def __init__(self, db, configuration: Configuration):
        self.db = db
        self.conf = configuration
        self.requetes = []

    def _read(self, sql):
        # Defensively prevent accidental DML in this new reader.
        if not isinstance(sql, str) or not sql.lstrip().upper().startswith('SELECT '):
            raise ValueError('Reader only permits SELECT queries')
        self.requetes.append(sql)
        status = self.db.ExecuterReq(sql)
        if status is False:
            raise RuntimeError('SELECT failed')
        result = self.db.ResultatReq()
        if result is None:
            raise RuntimeError('SELECT returned no result collection')
        return [tuple(row) for row in result]

    def _presences(self, debut, fin):
        aids = _csv_ints(self.conf.sites)
        sql = """SELECT c.IDconso,c.date,c.IDindividu,c.IDactivite,c.IDunite,
                    c.IDprestation,c.IDcategorie_tarif,cp.IDfamille,
                    p.IDprestation,p.IDtarif,p.IDcategorie_tarif,p.IDfamille,
                    p.IDindividu,p.IDactivite,p.date,p.categorie,p.IDfacture,
                    t.methode,t.IDtype_quotient
                 FROM consommations AS c
                 LEFT JOIN comptes_payeurs AS cp ON cp.IDcompte_payeur=c.IDcompte_payeur
                 LEFT JOIN prestations AS p ON p.IDprestation=c.IDprestation
                 LEFT JOIN tarifs AS t ON t.IDtarif=p.IDtarif
                 WHERE c.etat='present' AND c.date>='%s' AND c.date<='%s'
                   AND c.IDactivite IN %s
                 ORDER BY c.date,c.IDconso""" % (debut, fin, aids)
        rows = self._read(sql)
        result = []
        for r in rows:
            (idconso,jour,child,act,unit,prestid,catconso,family,
             realprestid,tariff,catprest,pfam,pchild,pact,pdate,ptype,invoice,
             method,typeqf) = r
            if unit not in self.conf.unites_accueil[act]:
                continue
            if child is None or family is None:
                # Cannot safely determine de-duplicated family or child.
                raise RuntimeError('Encountered presence without person/family linkage; no silent omission')
            consistency = []
            if prestid is not None and realprestid is None:
                consistency.append('PRESTATION_ORPHELINE')
            if realprestid is not None:
                if (pfam != family or pchild != child or pact != act or pdate != jour):
                    consistency.append('LIEN_PRESTATION_INCOHERENT')
                if catconso != catprest:
                    consistency.append('CATEGORIE_INSCRIPTION_INCOHERENTE')
                if ptype != 'consommation':
                    consistency.append('PRESTATION_NON_CONSOMMATION')
                if tariff not in self.conf.tarifs_accueil[act]:
                    consistency.append('TARIF_HORS_ACCUEIL')
            else:
                consistency.append('PRESTATION_ABSENTE')
            result.append({'id':idconso,'date':jour,'enfant':child,'famille':family,
                           'activite':act,'site':self.conf.sites[act],
                           'IDprestation':realprestid,'IDtarif':tariff,
                           'IDtype_quotient':typeqf,'methode':method,
                           'anomalies':consistency,'invoice_exists':invoice is not None})
        return result

    def _tarifs(self):
        ids = {t for seq in self.conf.tarifs_accueil.values() for t in seq}
        sql = """SELECT t.IDtarif,t.IDactivite,t.IDtype_quotient,t.methode,
                     l.IDligne,l.tranche,l.num_ligne,l.qf_min,l.qf_max
                 FROM tarifs t LEFT JOIN tarifs_lignes l ON l.IDtarif=t.IDtarif
                 WHERE t.IDtarif IN %s ORDER BY t.IDtarif,l.num_ligne,l.IDligne""" % _csv_ints(ids)
        byid = {}
        for t, act, typ, meth, lid, tranche, n, mi, ma in self._read(sql):
            if t not in byid:
                byid[t] = {'activite':act, 'type':typ, 'methode':meth, 'lignes':[]}
            if lid is not None:
                byid[t]['lignes'].append((str(tranche), mi, ma, lid, n))
        if ids != set(byid):
            raise RuntimeError('Unknown accueil tariffs: ' + repr(ids - set(byid)))
        for act, tariffs in self.conf.tarifs_accueil.items():
            for tid in tariffs:
                if byid[tid]['activite'] != act:
                    raise RuntimeError('Tariff does not belong to expected activity')
        return byid

    def _verifier_grille_commune(self, tarifs):
        if not self.conf.exiger_grille_commune:
            return
        signatures = {}
        for tid, t in tarifs.items():
            sig = tuple(sorted(set((code, str(mi), str(ma))
                                   for code, mi, ma, lid, n in t['lignes'])))
            if not sig:
                raise RuntimeError('Tariff without QF lines: IDtarif=%s' % tid)
            signatures[tid] = sig
        if len(set(signatures.values())) > 1:
            raise RuntimeError('Divergent QF grids: global category merge forbidden; explicit historical mapping needed')

    def _quotients(self, families):
        byfamily = defaultdict(list)
        sortedids = sorted(families)
        for offset in range(0,len(sortedids),200):
            chunk = sortedids[offset:offset+200]
            sql = """SELECT IDfamille,IDquotient,IDtype_quotient,date_debut,date_fin,quotient
                 FROM quotients WHERE IDfamille IN %s
                 ORDER BY IDfamille,date_debut,IDquotient""" % _csv_ints(chunk)
            for fam, qid, typ, a, b, qf in self._read(sql):
                byfamily[fam].append((qid,typ,a,b,qf))
        return byfamily

    def _qf(self, lines, day, typ):
        """Return real QF without billing's substitute-high-QF fallback."""
        matched = []
        type_set = set()
        invalid = False
        for qid, qt, d0, d1, q in lines:
            try:
                if d0 is None or d1 is None:
                    invalid = True
                    continue
                aa,bb = _iso(str(d0)[:10]),_iso(str(d1)[:10])
                if aa > bb:
                    invalid = True
                    continue
            except (ValueError,TypeError):
                invalid = True
                continue
            if not (aa <= day <= bb):
                continue
            if typ is not None and typ != qt:
                continue
            try:
                v = Decimal(str(q))
                if not v.is_finite() or v < 0:
                    invalid = True
                    continue
            except (InvalidOperation,TypeError):
                invalid = True
                continue
            matched.append(v)
            type_set.add(qt)
        if invalid:
            return None, QF_REVIEW, 'INVALID_QF_RECORD'
        if not matched:
            return None, QF_UNKNOWN, 'NO_VALID_QF_ON_PRESENCE'
        if len(set(matched)) > 1:
            return None, QF_REVIEW, 'OVERLAPPING_QF'
        if typ is None and len(type_set) > 1:
            # Same QF number but different QF types is not a reference selection.
            return None, QF_REVIEW, 'MULTIPLE_TYPES_WITHOUT_REFERENCE'
        return matched[0], None, 'RECORDED_QF_VALID_AT_DATE'

    def _tranche(self, lines, value):
        if value is None:
            return None, 'NO_REAL_QF'
        candidates = set()
        for tr, mi, ma, lid, n in lines:
            if mi is None or ma is None:
                continue
            try:
                if Decimal(str(mi)) <= value <= Decimal(str(ma)):
                    candidates.add(tr)
            except (InvalidOperation,TypeError):
                return None, 'INVALID_CURRENT_TARIFF_LINES'
        if len(candidates) != 1:
            return None, 'CURRENT_GRID_GAP_OR_CONFLICT'
        return next(iter(candidates)), 'CURRENT_GRID_RECONSTRUCTION_ONLY'

    def _observations(self, rows, tarifs, quotients, mode):
        all_groups = defaultdict(list)
        for row in rows:
            groupid = row['famille'] if mode == 'familles' else row['enfant']
            all_groups[groupid].append(row)
        indicative_counts = Counter()
        qf_counts = Counter()
        status_counts = Counter()
        examples = Counter()
        for groupid, group in all_groups.items():
            max_day = max(r['date'] for r in group)
            last = [r for r in group if r['date'] == max_day]
            per_presence = []
            for r in last:
                provenance = list(r['anomalies'])
                ids = self.conf.tarifs_accueil[r['activite']]
                tid = r['IDtarif']
                # Never let a broken prestation link invalidate otherwise
                # reliable family QF data. Derive its reference independently
                # only when the activity has exactly one approved QF tariff.
                invalid_link = any(x not in ('PRESTATION_ABSENTE', 'HYPOTHESE_TARIF_ACTIVITE')
                                   for x in provenance)
                if invalid_link and len(ids) == 1:
                    tid = ids[0]
                    provenance.append('REFERENTIEL_QF_UNIQUE_ACTIVITE')
                elif invalid_link and len(ids) > 1:
                    # A broken prestation must not erase a valid family QF:
                    # use a common *current* QF reference only if every
                    # approved tariff has exactly the same type and bands.
                    # The applied tariff remains unknown (see provenance).
                    candidats = [tarifs[x] for x in ids if x in tarifs]
                    signatures = {
                        (t['type'], tuple(sorted(
                            (code, str(mi), str(ma))
                            for code, mi, ma, lid, n in t['lignes'])))
                        for t in candidats
                    }
                    if (len(candidats) == len(ids) and len(signatures) == 1
                            and candidats[0]['type'] is not None
                            and candidats[0]['lignes']):
                        tid = min(ids)
                        provenance.append('REFERENTIEL_QF_GRILLE_COMMUNE')
                if tid is None and len(ids) == 1:
                    tid = ids[0]
                    provenance.append('HYPOTHESE_TARIF_ACTIVITE')
                if tid not in tarifs or tid not in ids:
                    provenance.append('TARIF_NON_RESOLU')
                    inferred_type = None
                    lines = []
                else:
                    inferred_type = tarifs[tid]['type']
                    lines = tarifs[tid]['lignes']
                q, qflag, qstatus = self._qf(quotients.get(r['famille'],[]),max_day,inferred_type)
                if qflag is None:
                    tier, reason = self._tranche(lines,q)
                    qfcat = self.conf.libelles.get(tier, 'Tranche '+str(tier)) if tier is not None else QF_OUTSIDE
                else:
                    qfcat = qflag
                    # A missing QF does not turn into a documented QF of 99999.
                    tier, reason = (None, 'MISSING_QF_CANNOT_ATTEST_MAX_TIER')
                    if qflag == QF_UNKNOWN and lines:
                        valid_max=[]
                        for tr, mi, ma, lid, n in lines:
                            if ma is not None:
                                try:valid_max.append((Decimal(str(ma)),tr))
                                except (InvalidOperation, TypeError):pass
                        if valid_max:
                            maximum = max(x[0] for x in valid_max)
                            matches = {tr for ma,tr in valid_max if ma == maximum}
                            if len(matches) == 1:
                                tier = next(iter(matches))
                                reason='BILLING_FALLBACK_QF_MAX_INFERRED_NOT_PROVEN_MAX_PRICE'
                if tier is not None:
                    tarcat = self.conf.libelles.get(tier,'Tranche '+str(tier))
                else:
                    tarcat = TARIF_UNKNOWN
                if provenance:
                    # A presence is valid and counted, but a non-QF service,
                    # missing prestation or wrong join does NOT attest tariff.
                    if any(x not in ('PRESTATION_ABSENTE','HYPOTHESE_TARIF_ACTIVITE') for x in provenance):
                        tarcat = TARIF_UNKNOWN
                        reason='INCONSISTENT_BILLING_LINK'
                per_presence.append((qfcat,tarcat,tuple(provenance),reason,qstatus))
            qcats={x[0] for x in per_presence}
            tcats={x[1] for x in per_presence}
            qfcat=next(iter(qcats)) if len(qcats)==1 else QF_REVIEW
            if len(tcats)==1:
                tarcat=next(iter(tcats))
            else:
                tarcat=TARIF_TIE
            qf_counts[qfcat]+=1
            indicative_counts[tarcat]+=1
            if len(tcats)>1:
                status_counts['CONFLIT_TARIF_MEME_DATE']+=1
            for r in {x[3] for x in per_presence}:
                status_counts[r]+=1
            for prov in set(x for p in per_presence for x in p[2]):
                examples[prov]+=1
            for qs in {x[4] for x in per_presence}:
                status_counts[qs]+=1
        return len(all_groups),qf_counts,indicative_counts,status_counts,examples

    def lire(self, date_debut, date_fin):
        a,b=_iso(date_debut),_iso(date_fin)
        if b<a:
            raise ValueError('End before start')
        records=self._presences(a,b)
        tarifs=self._tarifs()
        self._verifier_grille_commune(tarifs)
        quotients=self._quotients({r['famille'] for r in records}) if records else {}
        categories={self.conf.libelles.get(line[0],'Tranche '+line[0])
                    for t in tarifs.values() for line in t['lignes']}
        categories.update(self.conf.categories_historiques)
        # Do not silently merge two source categories with identical display labels.
        if len(set(self.conf.libelles.values()))!=len(self.conf.libelles):
            raise ValueError('Same display label for two distinct tariff codes')
        result={'source_sha':SRC_WX,'dates':[a,b],
                'statut':'PROTOTYPE_NON_HOMOLOGUE',
                'precautions':['Tariff tier is inferred from CURRENT lignes, never historical attestation',
                               'QF receipt date not available in inspected schema',
                               'Physical site mapping is explicitly supplied, not inferred',
                               'Valid present is counted, without waiting for invoice',
                               'Prices do not identify categories'],
                'global':{},'sites':{}}
        def build(rows):
            rep={}
            for mode in ('familles','enfants'):
                total,qf,tarif,status,probs=self._observations(rows,tarifs,quotients,mode)
                qc={x:0 for x in sorted(categories)}
                qc[QF_UNKNOWN]=0
                qc[QF_REVIEW]=0
                qc.update(qf)
                tc={x:0 for x in sorted(categories)}
                tc.update(tarif)
                if sum(qc.values())!=total or sum(tc.values())!=total:
                    raise AssertionError('Denominator lost')
                # Exact percentages always use the complete de-duplicated population.
                pq={k:round(v*100.0/total,2) if total else 0.0 for k,v in qc.items()}
                pt={k:round(v*100.0/total,2) if total else 0.0 for k,v in tc.items()}
                rep[mode]={'total':total,'qf':qc,'tarifs_indicatifs':tc,
                           'pourcentages_qf':pq,'pourcentages_tarifs_indicatifs':pt,
                           'statuts':dict(sorted(status.items())),
                           'anomalies':dict(sorted(probs.items())),
                           'categories_tarif_attestees':0,
                           'categories_historiques_non_attestees':total}
            return rep
        result['global']=build(records)
        for site in sorted(set(self.conf.sites.values())):
            result['sites'][site]=build([r for r in records if r['site']==site])
        result['lectures_sql']=len(self.requetes)
        return result
