# -*- coding: utf-8 -*-
"""D5: bordereaux financiers partenaires, sans emission comptable automatique.

Entree: interventions D3-D4 constatees ET eligibles et tarifs d'une version
D2 signee. Sortie: instantane monetise, CSV preparatoire et declaration
facultative de reference d'une facture externe, JAMAIS une facture Noethys.

Pas d'acces implicite a GestionDB, pas de migration, pas d'ecriture historique.
Connexion DB-API explicite. Autorisation refusee par defaut.
"""

import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
from io import StringIO
import json
import re

from Utils.UTILS_Partenaires_D1 import PartenairesErreur, AutorisationRefusee, Introuvable
from Utils.UTILS_Partenaires_D34 import InterventionsPartenaires

CENT = Decimal('0.01')
MONTANT_MAX = Decimal('9999999999.99')
NB_LIGNES_MAX = 2000


class BordereauInvalide(PartenairesErreur):
    pass


class BordereauConflit(BordereauInvalide):
    pass


class BordereauIntegrite(BordereauInvalide):
    pass


def _id(valeur):
    if type(valeur) is not int or valeur <= 0:
        raise BordereauInvalide('Identifiant entier positif obligatoire')
    return valeur


def _texte(valeur, nom, longueur=150):
    if not isinstance(valeur, str) or not valeur.strip() or len(valeur.strip()) > longueur:
        raise BordereauInvalide('%s : texte obligatoire ou trop long' % nom)
    return valeur.strip()


def _reference(valeur, champ, longueur):
    texte = _texte(valeur, champ, longueur)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*', texte):
        raise BordereauInvalide('%s : reference ASCII sans espaces requise' % champ)
    return texte


def _date(valeur):
    if not isinstance(valeur, str):
        raise BordereauInvalide('Date ISO YYYY-MM-DD obligatoire')
    try:
        d = date.fromisoformat(valeur)
    except ValueError as e:
        raise BordereauInvalide('Date ISO invalide') from e
    if d.isoformat() != valeur:
        raise BordereauInvalide('Date non canonique')
    return valeur


def _iso(valeur):
    return valeur.isoformat() if isinstance(valeur, date) else valeur


def _now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def _digest(d):
    return sha256(json.dumps(d, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False).encode('utf-8')).hexdigest()


def _prix(valeur):
    if isinstance(valeur, float) or isinstance(valeur, bool) or valeur is None:
        raise BordereauInvalide('Les montants float, bool et NULL sont interdits')
    txt = str(valeur)
    if not re.fullmatch(r'(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{1,2})?', txt):
        raise BordereauInvalide('Montant non canonique : deux decimales maximum')
    try:
        d = Decimal(txt)
    except InvalidOperation as err:
        raise BordereauInvalide('Montant invalide') from err
    if not CENT <= d <= MONTANT_MAX:
        raise BordereauInvalide('Montant strictement positif hors plage')
    return d.quantize(CENT)


def _arrondir(valeur):
    try:
        montant = valeur.quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation as err:
        raise BordereauInvalide('Montant hors plage') from err
    if montant < CENT or montant > MONTANT_MAX:
        raise BordereauInvalide('Montant de ligne nul ou hors plage')
    return montant


class BordereauxPartenaires:
    def __init__(self, connexion, *, dialecte='sqlite', autoriser=None):
        if connexion is None or dialecte not in ('sqlite','mysql'):
            raise BordereauInvalide('Connexion DB-API et dialecte requis')
        self.connexion = connexion
        self.dialecte = dialecte
        self.param = '?' if dialecte == 'sqlite' else '%s'
        self.autoriser = autoriser
        self.interventions = InterventionsPartenaires(connexion, dialecte=dialecte,
                                                      autoriser=autoriser)

    def _droit(self, acteur, action):
        acteur = _texte(acteur, 'acteur', 100)
        if not callable(self.autoriser) or self.autoriser(acteur, action) is not True:
            raise AutorisationRefusee('D5 : acces refuse')
        return acteur

    def _sql(self, requete, valeurs=(), *, lire=False):
        cur = self.connexion.cursor()
        try:
            cur.execute(requete, tuple(valeurs))
            if lire:
                return [dict(zip((x[0] for x in cur.description), row))
                        for row in cur.fetchall()]
            return cur.lastrowid
        finally:
            cur.close()

    def _lire(self, requete, valeurs=()):
        return self._sql(requete, valeurs, lire=True)

    def _unique(self, requete, valeurs=()):
        resultats = self._lire(requete, valeurs)
        if not resultats:
            raise Introuvable('Bordereau ou donnee absente')
        return resultats[0]

    def _transaction(self, f):
        if self.dialecte == 'sqlite':
            if self.connexion.in_transaction:
                raise BordereauConflit('Transaction externe deja ouverte')
            if self.connexion.execute('PRAGMA foreign_keys').fetchone()[0] != 1:
                raise BordereauConflit('PRAGMA foreign_keys obligatoire')
            self.connexion.execute('BEGIN IMMEDIATE')
        else:
            getter = getattr(self.connexion, 'get_autocommit', None)
            if getter is None or getter():
                raise BordereauConflit('Connexion MySQL transactionnelle requise')
            demarrer = getattr(self.connexion, 'begin', None)
            if not callable(demarrer):
                raise BordereauConflit('begin() MySQL obligatoire')
            demarrer()
        try:
            resultat = f()
            self.connexion.commit()
            return resultat
        except Exception as e:
            self.connexion.rollback()
            if e.__class__.__name__ == 'IntegrityError':
                raise BordereauConflit('Doublon ou contrainte D5 : aucune ligne inseree') from e
            raise

    def _inserer(self, table, donnees):
        cols = sorted(donnees)
        sql = ('INSERT INTO %s (%s) VALUES (%s)' %
               (table, ','.join(cols), ','.join([self.param]*len(cols))))
        return self._sql(sql, [donnees[c] for c in cols])

    def _modifier(self, table, col_id, identifiant, valeurs):
        cols = sorted(valeurs)
        sql = 'UPDATE %s SET %s WHERE %s=%s' % (
            table, ','.join(c+'='+self.param for c in cols), col_id, self.param)
        self._sql(sql, [valeurs[c] for c in cols]+[identifiant])

    def _evenement(self, bid, action, acteur, informations=''):
        self._inserer('partenaires_bordereaux_evenements', {
            'IDbordereau': bid, 'action': action, 'acteur': acteur,
            'date_action': _now(), 'informations': informations,
        })

    def _bordereau(self, bid, *, verrou=False):
        s = ' FOR UPDATE' if verrou and self.dialecte == 'mysql' else ''
        b = self._unique('SELECT * FROM partenaires_bordereaux WHERE IDbordereau=%s%s'
                         % (self.param,s), (_id(bid),))
        for c in ('date_debut','date_fin'):
            b[c] = _iso(b[c])
        return b

    def creer_bordereau(self, IDpartenaire, IDconvention, reference, date_debut,
                        date_fin, *, acteur):
        acteur = self._droit(acteur, 'creer_bordereau')
        _id(IDpartenaire); _id(IDconvention)
        reference = _reference(reference, 'reference', 100)
        debut, fin = _date(date_debut), _date(date_fin)
        if fin < debut or debut[:7] != fin[:7]:
            raise BordereauInvalide('Bordereau limite a un meme mois civil')
        def action():
            c = self.interventions.registre._convention(IDconvention)
            if c['IDpartenaire'] != IDpartenaire:
                raise BordereauInvalide('Partenaire et convention differents')
            if not _iso(c['date_debut']) <= debut <= fin <= _iso(c['date_fin']):
                raise BordereauInvalide('Periode hors convention')
            if not self._lire('SELECT IDversion FROM partenaires_conventions_versions '
                              "WHERE IDconvention_partenaire=%s AND statut='signee' LIMIT 1"
                              % self.param, (IDconvention,)):
                raise BordereauInvalide('Version signee absente')
            bid = self._inserer('partenaires_bordereaux', {
                'IDpartenaire': IDpartenaire, 'IDconvention_partenaire': IDconvention,
                'reference': reference, 'date_debut': debut, 'date_fin': fin,
                'etat': 'brouillon', 'empreinte': None, 'total': None,
                'nombre_lignes': None, 'valide_le': None, 'valide_par': None,
                'cree_le': _now(),
            })
            self._evenement(bid, 'creation', acteur)
            return bid
        return self._transaction(action)

    def _choix(self, choix):
        if not isinstance(choix, list) or not 1 <= len(choix) <= NB_LIGNES_MAX:
            raise BordereauInvalide('Selection de 1 a 2000 lignes obligatoire')
        valides = []
        for x in choix:
            if not isinstance(x, dict) or set(x) != {'IDintervention','IDtarif_convention'}:
                raise BordereauInvalide('Chaque ligne exige intervention et tarif explicites')
            valides.append((_id(x['IDintervention']), _id(x['IDtarif_convention'])))
        if len({p[0] for p in valides}) != len(valides):
            raise BordereauConflit('Intervention selectionnee plusieurs fois')
        return sorted(valides)

    def _source(self, b, iid, tid, *, verrou=False, verifier_doublon=True):
        i = self.interventions._intervention(iid, verrou=verrou)
        if i['etat'] != 'realisee' or i['decision_facturation'] != 'eligible':
            raise BordereauInvalide('Seule une intervention realisee et eligible est facturable')
        d = _date(i['date_reelle'])
        if not b['date_debut'] <= d <= b['date_fin']:
            raise BordereauInvalide('Intervention hors mois du bordereau')
        p = self.interventions._programme(i['IDprogrammation'])
        if p['etat'] != 'validee' or p['IDversion'] != i['IDversion']:
            raise BordereauIntegrite('Programmation ou version incoherente')
        v = self.interventions._version_applicable(i['IDversion'], d, d,
                                                    exiger_ouverte=False)
        if v['convention']['IDconvention_partenaire'] != b['IDconvention_partenaire'] or \
                v['convention']['IDpartenaire'] != b['IDpartenaire']:
            raise BordereauInvalide('L intervention appartient a une autre convention')
        if v['version']['mode_facturation'] != 'payante':
            raise BordereauInvalide('Convention gratuite')
        t = next((x for x in v['tarifs'] if x['IDtarif_convention']==tid), None)
        if not t or t['categorie'] != i['categorie_tarif'] or \
                not _iso(t['date_debut']) <= d <= _iso(t['date_fin']):
            raise BordereauInvalide('Tarif non applicable a cette intervention')
        if t['unite'] not in ('heure','seance'):
            raise BordereauInvalide('Tarif forfait : allocation manuelle hors D5')
        mins = i['minutes_reelles']
        if type(mins) is not int or not 1 <= mins <= 720:
            raise BordereauInvalide('Minutes realisees non qualifiees')
        prix = _prix(t['montant'])
        montant = _arrondir(prix * (Decimal(mins)/Decimal(60)
                                    if t['unite']=='heure' else Decimal(1)))
        if verifier_doublon and self._lire('SELECT IDligne FROM partenaires_bordereaux_lignes '
                                          'WHERE IDintervention=%s' % self.param,(iid,)):
            raise BordereauConflit('Intervention deja engagee dans un autre bordereau')
        # Only financially meaningful source fields, no personal data or claims of proof.
        source = dict(IDintervention=iid, IDversion=i['IDversion'], IDtarif_convention=tid,
                      IDprogrammation=i['IDprogrammation'], date_reelle=d,
                      heure_debut_reelle=i['heure_debut_reelle'],
                      heure_fin_reelle=i['heure_fin_reelle'], minutes_reelles=mins,
                      categorie=i['categorie_tarif'], etat=i['etat'],
                      decision=i['decision_facturation'], signature=v['version']['empreinte_contenu'],
                      prix_unitaire=str(prix), montant=str(montant))
        return dict(IDintervention=iid, IDversion=i['IDversion'], IDtarif_convention=tid,
                    date_reelle=d, minutes_reelles=mins, categorie=i['categorie_tarif'],
                    libelle=t['libelle'], unite=t['unite'], prix_unitaire=str(prix),
                    montant=str(montant), empreinte_source=_digest(source))

    def _preparer(self, b, choix, *, verrou=False):
        if b['etat'] != 'brouillon':
            raise BordereauConflit('Bordereau deja valide, aucune modification')
        selection = self._choix(choix)
        lignes = [self._source(b, iid, tid, verrou=verrou) for iid, tid in selection]
        total = sum((Decimal(x['montant']) for x in lignes), Decimal('0.00'))
        if total > MONTANT_MAX:
            raise BordereauInvalide('Total hors plafond du schema')
        entete = {k:b[k] for k in ('IDbordereau','IDpartenaire',
                                     'IDconvention_partenaire','reference','date_debut','date_fin')}
        contenu = {'entete': entete, 'lignes': lignes, 'total': str(total.quantize(CENT))}
        return dict(contenu, empreinte=_digest(contenu), nombre_lignes=len(lignes))

    def proposer_bordereau(self, bid, choix, *, acteur):
        self._droit(acteur, 'proposer_bordereau')
        b = self._bordereau(bid)
        return self._preparer(b, choix)

    def valider_bordereau(self, bid, choix, empreinte_attendue, *, acteur):
        acteur = self._droit(acteur, 'valider_bordereau')
        if not isinstance(empreinte_attendue, str) or not re.fullmatch('[0-9a-f]{64}',empreinte_attendue):
            raise BordereauInvalide('Empreinte de validation obligatoire')
        def action():
            b = self._bordereau(bid, verrou=True)
            apercu = self._preparer(b, choix, verrou=True)
            if apercu['empreinte'] != empreinte_attendue:
                raise BordereauConflit('Apercu obsolete, validation refusee')
            for ligne in apercu['lignes']:
                self._inserer('partenaires_bordereaux_lignes', dict(ligne, IDbordereau=bid))
            self._modifier('partenaires_bordereaux', 'IDbordereau', bid, {
                'etat':'valide','empreinte':apercu['empreinte'],
                'total':apercu['total'],'nombre_lignes':apercu['nombre_lignes'],
                'valide_le':_now(),'valide_par':acteur,
            })
            self._evenement(bid, 'validation', acteur, 'nombre=%d' % apercu['nombre_lignes'])
            return {'IDbordereau':bid,'empreinte':apercu['empreinte'],
                    'total':apercu['total'],'nombre_lignes':apercu['nombre_lignes']}
        return self._transaction(action)

    def lire_bordereau(self, bid, *, acteur, verifier_sources=True):
        self._droit(acteur, 'lire_bordereau')
        b = self._bordereau(bid)
        lignes = self._lire('SELECT * FROM partenaires_bordereaux_lignes '
                            'WHERE IDbordereau=%s ORDER BY IDintervention' % self.param, (bid,))
        if b['etat'] != 'brouillon':
            canon = []
            for x in lignes:
                y = {k:x[k] for k in ('IDintervention','IDversion','IDtarif_convention',
                   'date_reelle','minutes_reelles','categorie','libelle','unite',
                   'prix_unitaire','montant','empreinte_source')}
                y['date_reelle'] = _iso(y['date_reelle'])
                for monetary in ('prix_unitaire', 'montant'):
                    brut = str(y[monetary])
                    try:
                        canonical = str(Decimal(brut).quantize(CENT))
                    except (InvalidOperation, ValueError) as err:
                        raise BordereauIntegrite('Montant stocke illisible') from err
                    if brut != canonical or Decimal(canonical) <= 0:
                        raise BordereauIntegrite('Montant stocke non canonique')
                    y[monetary] = canonical
                canon.append(y)
            entete = {k:b[k] for k in ('IDbordereau','IDpartenaire',
                   'IDconvention_partenaire','reference','date_debut','date_fin')}
            contenu = {'entete':entete,'lignes':canon, 'total': str(Decimal(str(b['total'])).quantize(CENT))}
            if len(canon)!=b['nombre_lignes'] or _digest(contenu)!=b['empreinte'] or \
                    sum((Decimal(y['montant']) for y in canon), Decimal('0'))!=Decimal(str(b['total'])):
                raise BordereauIntegrite('Instantane du bordereau modifie')
            if verifier_sources:
                for x in canon:
                    source = self._source(b, x['IDintervention'], x['IDtarif_convention'],
                                          verifier_doublon=False)
                    if source != x:
                        raise BordereauIntegrite('Intervention ou tarif modifie apres validation')
            lignes = canon
        return {'bordereau': b, 'lignes': lignes,
                'reference': self._lire('SELECT * FROM partenaires_bordereaux_references '
                   'WHERE IDbordereau=%s' % self.param, (bid,))}

    def preparer_csv(self, bid, *, acteur):
        self._droit(acteur, 'preparer_csv')
        data = self.lire_bordereau(bid, acteur=acteur)
        b = data['bordereau']
        if b['etat']=='brouillon':
            raise BordereauInvalide('CSV interdit avant validation')
        sortie = StringIO(newline='')
        writer = csv.writer(sortie, delimiter=';')
        # CSV spreadsheet injection guard for externally supplied tariff labels.
        def cellule(valeur):
            if not isinstance(valeur, str):
                return valeur
            valeur = valeur.replace('\r', ' ').replace('\n', ' ').replace('\t', ' ')
            if valeur.lstrip().startswith(('=', '+', '-', '@')):
                valeur = "'" + valeur
            return valeur
        writer.writerow(['DOCUMENT PREPARATOIRE - PAS UNE FACTURE'])
        writer.writerow(['MONTANT CONTRACTUEL EN EUR - TVA A VERIFIER'])
        writer.writerow(['Bordereau',b['reference'],'Partenaire ID',b['IDpartenaire'],
                         'Convention ID',b['IDconvention_partenaire']])
        writer.writerow(['Periode',b['date_debut'],b['date_fin']])
        writer.writerow(['Intervention','Date reelle','Categorie','Libelle','Minutes',
                         'Unite','Prix unitaire EUR','Montant EUR'])
        for x in data['lignes']:
            writer.writerow([cellule(x[c]) for c in ('IDintervention','date_reelle','categorie',
                            'libelle','minutes_reelles','unite','prix_unitaire','montant')])
        writer.writerow(['TOTAL','','','','','','',str(Decimal(str(b['total'])).quantize(CENT))])
        return sortie.getvalue()

    def declarer_facture_externe(self, bid, reference_externe, montant_declare,
                                empreinte_document, *, acteur):
        acteur = self._droit(acteur, 'declarer_facture_externe')
        ref = _reference(reference_externe, 'reference facture externe', 150)
        montant = _prix(montant_declare)
        if not isinstance(empreinte_document, str) or not re.fullmatch('[0-9a-f]{64}',empreinte_document):
            raise BordereauInvalide('SHA-256 du document externe obligatoire')
        def action():
            b = self._bordereau(bid, verrou=True)
            if b['etat'] != 'valide':
                raise BordereauConflit('Seul un bordereau valide non rapproche est eligible')
            # Confirm source and snapshot remain unchanged before declaring any link.
            self.lire_bordereau(bid, acteur=acteur)
            if montant != Decimal(str(b['total'])):
                raise BordereauInvalide('Montant facture externe different du bordereau')
            self._inserer('partenaires_bordereaux_references', {
                'IDbordereau':bid,'IDpartenaire':b['IDpartenaire'],
                'nature':'facture_externe','reference_externe':ref,
                'montant_declare':str(montant), 'empreinte_document':empreinte_document,
                'declare_le':_now(),'declare_par':acteur,
            })
            self._modifier('partenaires_bordereaux','IDbordereau',bid,{'etat':'reference_externe'})
            self._evenement(bid, 'declaration_document', acteur)
            return {'reference_externe':ref,'montant_declare':str(montant),
                    'facture_emise_automatiquement':False,
                    'signature_verifiee':False,'paiement_verifie':False}
        return self._transaction(action)

    def lister_evenements(self, bid, *, acteur):
        self._droit(acteur, 'lister_evenements')
        self._bordereau(bid)
        return self._lire('SELECT * FROM partenaires_bordereaux_evenements '
                          'WHERE IDbordereau=%s ORDER BY IDevenement' % self.param,(bid,))
