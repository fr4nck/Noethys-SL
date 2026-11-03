# -*- coding: utf-8 -*-
"""ALSH-C2: observed Noethys address edits -> automatic municipal attendance.

The migrations install DB triggers. The effective date defaults to the UTC
DATE OF EDIT (not proof of the true move date). Earlier residence is unknown.
The C1 financial totals remain DRAFT: no bill, entitlement or paid state.
The same existing individual and consumption IDs are reused throughout.
"""
import json
import unicodedata
from collections import defaultdict
from datetime import date

try:
    from Utils.UTILS_ALSH_Commune import (
        ALSHErreur, ALSHConflit, _id, _date, _texte, _commune, _horodatage,
        SituationCommunesALSH,
    )
except ImportError:  # standalone qualification / test outside a Noethys package
    from UTILS_ALSH_Commune import (
        ALSHErreur, ALSHConflit, _id, _date, _texte, _commune, _horodatage,
        SituationCommunesALSH,
    )


def _nom_ville(value):
    text = _texte('Ville', value, 150)
    fold = unicodedata.normalize('NFKD', text).casefold()
    return ' '.join(''.join(c for c in fold if not unicodedata.combining(c)).split()).upper()


def _cp(value):
    text = _texte('Code postal', value, 12)
    if not text.isdigit() or len(text) != 5:
        raise ALSHErreur('Code postal francais a cinq chiffres requis')
    return text


def _date_observation(value):
    return value.isoformat() if isinstance(value, date) else value


class _DomicilesParObservation:
    """As-of resolution of inherited addresses, including parent edits.

    An address is never derived from the CURRENT person table for an earlier
    consumption. Only observed snapshots available as of the attendance date
    can be selected. Missing/ambiguous history returns no address (C1 flags).
    """

    def __init__(self, moteur):
        self.events = defaultdict(list)
        self.aliases = {}
        self.manual = defaultdict(list)
        self.cache = {}
        # Previously verified C1 periods may predate trigger installation.
        # Never silently replace a contradictory signed-off domicile.
        for row in moteur._lire('SELECT * FROM alsh_communes_domiciles'):
            self.manual[row['IDindividu']].append(row)
        q = ('SELECT o.IDobservation, o.IDindividu, o.jour_constat, o.source, '
             'o.adresse_auto, o.rue_resid, o.cp_resid, o.ville_resid, '
             'v.date_effet AS effet_valide '
             'FROM alsh_communes_c2_observations o '
             'LEFT JOIN alsh_communes_c2_dates_validees v '
             'ON v.IDobservation=o.IDobservation '
             'ORDER BY o.IDindividu, o.IDobservation')
        for event in moteur._lire(q):
            event['effet'] = (_date_observation(event['effet_valide']) if event['effet_valide']
                              else _date_observation(event['jour_constat']))
            event['effet'] = _date('date residence observee', event['effet'])
            self.events[event['IDindividu']].append(event)
        for items in self.events.values():
            items.sort(key=lambda e: (e['effet'], e['IDobservation']))
        for row in moteur._lire('SELECT code_postal, ville_normalisee, code_insee, libelle_commune '
                               'FROM alsh_communes_c2_correspondances'):
            self.aliases[(row['code_postal'], row['ville_normalisee'])] = row

    def _suivi(self, personne, jour, chemin):
        _id('IDindividu', personne)
        if personne in chemin or len(chemin) >= 20:
            raise ALSHConflit('Reference adresse_auto circulaire')
        events = self.events.get(personne, [])
        candidats = [e for e in events if e['effet'] <= jour]
        if not candidats:
            raise ALSHConflit('Aucune adresse observee a cette date')
        derniere_date = candidats[-1]['effet']
        memes_jour = [e for e in candidats if e['effet'] == derniere_date]
        # Several edits on the same calendar day cannot be ordered against
        # an attendance event that has only a date. Reject if different.
        def signature(e):
            return (e['adresse_auto'], e['rue_resid'] or '',
                    e['cp_resid'] or '', e['ville_resid'] or '')
        if len({signature(e) for e in memes_jour}) > 1 and derniere_date == jour:
            raise ALSHConflit('Plusieurs adresses constatees le meme jour')
        event = memes_jour[-1]
        nexts = [e['effet'] for e in events if e['effet'] > jour]
        parcours = [event]
        if event['adresse_auto'] is None:
            return event, parcours, nexts
        parent, ancetres, futurs = self._suivi(event['adresse_auto'], jour,
                                               chemin | {personne})
        return parent, parcours + ancetres, nexts + futurs

    def chercher(self, ident, jour):
        key = (ident, jour)
        if key in self.cache:
            return self.cache[key]
        try:
            leaf, chain, nexts = self._suivi(ident, jour, set())
            rue = _texte('Rue de residence', leaf['rue_resid'])
            cp = _cp(leaf['cp_resid'])
            ville = _texte('Ville de residence', leaf['ville_resid'], 150)
            alias = self.aliases.get((cp, _nom_ville(ville)))
            if not alias:
                raise ALSHConflit('Commune non associee a un code INSEE')
            # An event can be retroactively dated (on proof), but its
            # chronology remains explicit. No hidden inference before seed.
            debut = max(e['effet'] for e in chain)
            fin = min(nexts) if nexts else None
            latest_id = max(e['IDobservation'] for e in chain)
            result = [{
                'IDdomicile': 'AUTO-%d-%d' % (ident, latest_id),
                'IDindividu': ident,
                'date_debut': debut,
                'date_fin': fin,
                'rue': rue,
                'complement': '',
                'code_postal': cp,
                'ville': alias['libelle_commune'],
                'code_insee': alias['code_insee'],
                'pays': 'France',
            }]
        except (ALSHErreur, ALSHConflit, TypeError, ValueError):
            result = []
        manual = [d for d in self.manual.get(ident, ())
                  if _date_observation(d['date_debut']) <= jour and
                  (d['date_fin'] is None or jour < _date_observation(d['date_fin']))]
        if len(manual) > 1:
            result = []
        elif manual:
            if not result:
                result = manual
            else:
                auto = result[0]
                signed = manual[0]
                # A signed/manual period takes priority only when compatible.
                # A disagreement is a review item, never an automatic move.
                if (signed['code_insee'] != auto['code_insee'] or
                    _nom_ville(signed['ville']) != _nom_ville(auto['ville']) or
                    (signed['rue'] or '').strip().casefold() !=
                     (auto['rue'] or '').strip().casefold()):
                    result = []
        self.cache[key] = result
        return result


class FrequentationCommunesAuto:
    """Profiles are stored once; recomputation is an always-current READ.

    Triggered observations are transactional with existing edits, including
    updates that go through GestionDB.ReqMAJ, imports and direct SQL writes.
    No creation of activities, families, invoices or payment entries.
    """

    def __init__(self, moteur):
        if not isinstance(moteur, SituationCommunesALSH):
            raise ALSHErreur('SituationCommunesALSH requise')
        self.moteur = moteur

    def _journal(self, actor, action, key, payload):
        p = self.moteur.param
        self.moteur._executer('INSERT INTO alsh_communes_c2_audit '
                              '(acteur,action,reference,donnees_json,date_action) '
                              'VALUES (%s)' % ','.join([p]*5),
                              (actor, action, str(key), json.dumps(payload, ensure_ascii=False,
                               sort_keys=True), _horodatage()))

    def correspondance(self, code_postal, ville, code_insee, libelle, *, acteur):
        actor = self.moteur._droit(acteur, 'communes_parametrer')
        cp, normal, code = _cp(code_postal), _nom_ville(ville), _commune(code_insee)
        libelle = _texte('Nom de commune', libelle, 150)
        p = self.moteur.param

        def run():
            present = self.moteur._lire('SELECT code_insee,libelle_commune '
                'FROM alsh_communes_c2_correspondances WHERE code_postal=%s AND ville_normalisee=%s'
                % (p, p), (cp, normal))
            if present:
                if present[0]['code_insee'] != code:
                    raise ALSHConflit('Code INSEE deja attribue: correction explicite requise')
                return False
            self.moteur._executer('INSERT INTO alsh_communes_c2_correspondances '
                '(code_postal,ville_normalisee,code_insee,libelle_commune) VALUES (%s)'
                % ','.join([p]*4), (cp, normal, code, libelle))
            self._journal(actor, 'correspondance', cp+':'+normal,
                          dict(code_insee=code, libelle=libelle))
            return True
        return self.moteur._transaction(run)

    def enregistrer_profil(self, nom, perimetres, unites, tarifs, *, acteur):
        actor = self.moteur._droit(acteur, 'communes_parametrer')
        nom = _texte('Nom du profil', nom, 140)
        if not isinstance(perimetres, list) or not perimetres:
            raise ALSHErreur('Couples activite/groupe explicites requis')
        couples = []
        for pair in perimetres:
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise ALSHErreur('Couple activite/groupe invalide')
            pair = [_id('IDactivite', pair[0]), _id('IDgroupe', pair[1])]
            if pair in couples:
                raise ALSHErreur('Couple en double')
            couples.append(pair)
        config = self.moteur._configurer_unites(unites)
        clauses = self.moteur._tarifs(tarifs)
        # Decimal is transformed from pre-validated prices, never float.
        tarifs_json = [dict(x, prix_jour=format(x['prix_jour'], '.2f')) for x in clauses]
        contenu = json.dumps(dict(perimetres=couples,
                                  unites={str(k): v for k, v in config.items()},
                                  tarifs=tarifs_json), sort_keys=True, ensure_ascii=False)
        p = self.moteur.param

        def run():
            exists = self.moteur._lire('SELECT IDprofil FROM alsh_communes_c2_profils WHERE nom=%s' % p,
                                       (nom,))
            if exists:
                raise ALSHConflit('Profil existant: une revision explicite est requise')
            ident, _ = self.moteur._executer('INSERT INTO alsh_communes_c2_profils '
                        '(nom,config_json,maj_utc,acteur) VALUES (%s)' % ','.join([p]*4),
                        (nom, contenu, _horodatage(), actor))
            self._journal(actor, 'profil_creation', ident, dict(nom=nom))
            return ident
        return self.moteur._transaction(run)

    def valider_date_effet(self, observation, date_effet, justificatif, *, acteur):
        """Explicit correction only when the real move day differs from edit day."""
        actor = self.moteur._droit(acteur, 'domicile_ecrire')
        ident = _id('IDobservation', observation)
        jour = _date('date_effet', date_effet)
        proof = _texte('Justificatif', justificatif, 255)
        p = self.moteur.param

        def run():
            row = self.moteur._lire('SELECT IDindividu,jour_constat,source FROM '
               'alsh_communes_c2_observations WHERE IDobservation=%s' % p, (ident,))
            if not row:
                raise ALSHErreur('Observation introuvable')
            if self.moteur._lire('SELECT IDobservation FROM alsh_communes_c2_dates_validees '
                                'WHERE IDobservation=%s' % p, (ident,)):
                raise ALSHConflit('Date deja validee: revision explicite requise')
            # Reject an override that reverses the effective chronology for
            # a particular individual. Other records may already be dated.
            events = self.moteur._lire('SELECT o.IDobservation,o.jour_constat,v.date_effet '
                 'FROM alsh_communes_c2_observations o LEFT JOIN alsh_communes_c2_dates_validees v '
                 'ON v.IDobservation=o.IDobservation WHERE o.IDindividu=%s '
                 'ORDER BY o.IDobservation' % p, (row[0]['IDindividu'],))
            for event in events:
                if event['IDobservation'] == ident:
                    continue
                original = _date_observation(event['date_effet'] or event['jour_constat'])
                if event['IDobservation'] < ident and jour < original:
                    raise ALSHConflit('Date anterieure a une observation precedente')
                if event['IDobservation'] > ident and jour > original:
                    raise ALSHConflit('Date posterieure a une observation suivante')
            self.moteur._executer('INSERT INTO alsh_communes_c2_dates_validees '
                      '(IDobservation,date_effet,justificatif,acteur,date_validation) '
                      'VALUES (%s)' % ','.join([p]*5),
                      (ident, jour, proof, actor, _horodatage()))
            self._journal(actor, 'date_effet_confirmee', ident,
                          dict(date_effet=jour, preuve=proof))
            return True
        return self.moteur._transaction(run)

    def calculer_automatiquement(self, debut, fin, profil, *, acteur):
        """Recompute from current Noethys consumptions + complete address log.

        No manual entry of moved children, domiciliation periods or attendance.
        The activity/unit and signed-convention mappings are configured once.
        Unsure address dates stay a DRAFT and must be checked before invoicing.
        """
        self.moteur._droit(acteur, 'frequentation_lire_nominatif')
        nom = _texte('Profil ALSH', profil, 140)
        p = self.moteur.param
        rows = self.moteur._lire('SELECT config_json FROM alsh_communes_c2_profils '
                                'WHERE nom=%s' % p, (nom,))
        if len(rows) != 1:
            raise ALSHErreur('Profil ALSH non configure')
        cfg = json.loads(rows[0]['config_json'])
        units = {int(k): v for k, v in cfg['unites'].items()}
        resolver = _DomicilesParObservation(self.moteur)
        result = self.moteur.calculer(
            debut, fin, cfg['perimetres'], units, tarifs=cfg['tarifs'],
            acteur=acteur, fournisseur_domiciles=resolver.chercher)
        result['source_domiciles'] = 'observations_automatiques_noethys'
        result['controle_dates_de_demenagement'] = 'dates de modification, a confirmer si decalage'
        result['calcul_complet'] = result['liquidable']
        # A plausible automatic allocation is still not evidence of
        # real municipal entitlement; no automatic bill may be generated.
        result['liquidable'] = False
        return result
