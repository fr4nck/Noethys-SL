# -*- coding: utf-8 -*-
"""Lot ALSH-C1 : domiciles dates et frequentation par commune, hors facturation.

Lit directement les consommations Noethys. N'utilise ni prestations ni factures.
Aucun tarif ou droit communal n'est infere d'une adresse actuelle ou d'une
reservation. L'historique de residence est valide manuellement et audite.

Le lecteur expose un brouillon explicatif, jamais un ordre de facturation.
SQLite et MySQL 5.7 via connexions DB-API dediees ; migration explicite.
"""
import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import io
import json
import re


class ALSHErreur(ValueError):
    pass


class ALSHConflit(ALSHErreur):
    pass


class ALSHAcces(ALSHErreur):
    pass


def _id(nom, x):
    if type(x) is not int or x < 1:
        raise ALSHErreur('%s : identifiant entier positif attendu' % nom)
    return x


def _date(nom, x):
    if isinstance(x, date) and not isinstance(x, datetime):
        return x.isoformat()
    if not isinstance(x, str):
        raise ALSHErreur('%s : date ISO requise' % nom)
    try:
        v = date.fromisoformat(x)
    except ValueError as error:
        raise ALSHErreur('%s : date invalide' % nom) from error
    if v.isoformat() != x:
        raise ALSHErreur('%s : format YYYY-MM-DD requis' % nom)
    return x


def _texte(nom, x, limite=255, facultatif=False):
    if not isinstance(x, str):
        raise ALSHErreur('%s : texte attendu' % nom)
    value = x.strip()
    if (not value and not facultatif) or len(value) > limite or '\x00' in value:
        raise ALSHErreur('%s : valeur absente ou invalide' % nom)
    return value


def _commune(x):
    value = _texte('Code INSEE', x, 5).upper()
    if not re.fullmatch(r'[0-9A-Z]{5}', value):
        raise ALSHErreur('Code INSEE de commune a cinq caracteres requis')
    return value


def _prix(x):
    if isinstance(x, bool) or not isinstance(x, (int, str, Decimal)):
        raise ALSHErreur('Tarif monetaire exact : texte, entier ou Decimal (pas float)')
    try:
        v = Decimal(str(x).replace(',', '.'))
    except InvalidOperation as exc:
        raise ALSHErreur('Tarif non numerique') from exc
    if not v.is_finite() or v < 0 or v > 100000 or v != v.quantize(Decimal('0.01')):
        raise ALSHErreur('Tarif negatif, excessif ou trop precis')
    return v


def _date_db(x):
    return x.isoformat() if isinstance(x, date) else x


def _horodatage():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def _csv_safe(x):
    # Evite l'execution de formules dans Excel/LibreOffice lors d'exports.
    value = '' if x is None else str(x)
    if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')):
        return "'" + value
    return value


class SituationCommunesALSH:
    """Moteur autonome : aucune ouverture implicite de la base MAD.

    Pour SQLite, PRAGMA foreign_keys=ON et connexion hors transaction en
    debut de mutation. Pour MySQL, InnoDB autocommit OFF + begin().
    autoriser(acteur, action) doit retourner exactement True, sans exception.
    """

    def __init__(self, connexion, *, dialecte='sqlite', autoriser=None):
        if connexion is None or dialecte not in ('sqlite', 'mysql'):
            raise ALSHErreur('Connexion et dialecte explicites requis')
        if not callable(autoriser):
            raise ALSHAcces('Politique de droits explicite obligatoire')
        if dialecte == 'sqlite':
            if connexion.execute('PRAGMA foreign_keys').fetchone()[0] != 1:
                raise ALSHErreur('Activer PRAGMA foreign_keys=ON')
        else:
            demarrer = (getattr(connexion, 'begin', None) or
                        getattr(connexion, 'start_transaction', None))
            if not callable(getattr(connexion, 'get_autocommit', None)) or \
                    connexion.get_autocommit() is not False or not callable(demarrer):
                raise ALSHErreur('MySQL exige autocommit OFF et demarrage explicite')
        self.cn = connexion
        self._demarrer_mysql = demarrer if dialecte == 'mysql' else None
        self.dialecte = dialecte
        self.param = '?' if dialecte == 'sqlite' else '%s'
        self.autoriser = autoriser

    def _droit(self, acteur, action):
        if not isinstance(acteur, str) or not acteur.strip() or \
                self.autoriser(acteur, action) is not True:
            raise ALSHAcces('Droit %s refuse' % action)
        return acteur.strip()

    def _lire(self, sql, args=()):
        cur = self.cn.cursor()
        try:
            cur.execute(sql, tuple(args))
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row)) if not isinstance(row, dict) else row
                    for row in cur.fetchall()]
        finally:
            cur.close()

    def _executer(self, sql, args=()):
        cur = self.cn.cursor()
        try:
            cur.execute(sql, tuple(args))
            return cur.lastrowid, cur.rowcount
        finally:
            cur.close()

    def _transaction(self, fonction):
        if self.dialecte == 'sqlite':
            if self.cn.in_transaction:
                raise ALSHConflit('Transaction exterieure : session dediee requise')
            self.cn.execute('BEGIN IMMEDIATE')
        else:
            self._demarrer_mysql()
        try:
            resultat = fonction()
            self.cn.commit()
            return resultat
        except Exception:
            self.cn.rollback()
            raise

    def _auditer(self, ident, acteur, action, donnees):
        texte = json.dumps(donnees, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        self._executer('INSERT INTO alsh_communes_domiciles_audit '
                       '(IDdomicile, acteur, action, donnees_json, date_action) '
                       'VALUES (%s)' % ','.join([self.param]*5),
                       (ident, acteur, action, texte, _horodatage()))

    def _verifier_absence_chevauchement(self, ident, debut, fin, ignorer=None):
        # Comparaison exacte de bornes [debut, fin[ ; pas de choix arbitraire.
        sql = 'SELECT IDdomicile, date_debut, date_fin FROM alsh_communes_domiciles WHERE IDindividu=%s' % self.param
        params = [ident]
        if ignorer is not None:
            sql += ' AND IDdomicile<>%s' % self.param
            params.append(ignorer)
        for ligne in self._lire(sql, params):
            d, f = _date_db(ligne['date_debut']), _date_db(ligne['date_fin'])
            if (fin is None or d < fin) and (f is None or debut < f):
                raise ALSHConflit('Domiciles qui se chevauchent pour cet enfant')

    def ajouter_domicile(self, IDindividu, date_debut, date_fin, rue, code_postal,
                         ville, code_insee, *, acteur, complement='', pays='France',
                         justificatif=''):
        acteur = self._droit(acteur, 'domicile_ecrire')
        ident = _id('IDindividu', IDindividu)
        debut = _date('date_debut', date_debut)
        fin = _date('date_fin', date_fin) if date_fin is not None else None
        if fin is not None and fin <= debut:
            raise ALSHErreur('Fin exclusive strictement apres debut')
        champs = dict(IDindividu=ident, date_debut=debut, date_fin=fin,
                      rue=_texte('Rue', rue), complement=_texte('Complement', complement, 150, True),
                      code_postal=_texte('Code postal', code_postal, 12),
                      ville=_texte('Ville', ville, 120), code_insee=_commune(code_insee),
                      pays=_texte('Pays', pays, 80),
                      justificatif=_texte('Justificatif', justificatif, 255))

        def operation():
            # Verrouille la ligne de l'enfant en MySQL pour serialiser les
            # modifications paralleles a ses periodes de domicile.
            lock = ' FOR UPDATE' if self.dialecte == 'mysql' else ''
            if not self._lire('SELECT IDindividu FROM individus WHERE IDindividu=%s' % self.param + lock,
                              (ident,)):
                raise ALSHErreur('Enfant introuvable dans individus')
            self._verifier_absence_chevauchement(ident, debut, fin)
            colonnes = sorted(champs)
            sql = 'INSERT INTO alsh_communes_domiciles (%s) VALUES (%s)' % (
                ','.join(colonnes), ','.join([self.param]*len(colonnes)))
            ident_dom, _ = self._executer(sql, [champs[k] for k in colonnes])
            self._auditer(ident_dom, acteur, 'creation', champs)
            return ident_dom
        return self._transaction(operation)

    def cloturer_domicile(self, IDdomicile, date_fin, *, acteur):
        acteur = self._droit(acteur, 'domicile_ecrire')
        ident = _id('IDdomicile', IDdomicile)
        fin = _date('date_fin', date_fin)

        def operation():
            # Verrouillage de l'enfant pour utiliser le meme ordre de
            # serialisation qu'ajouter_domicile, puis la periode cible.
            donnees = self._lire('SELECT * FROM alsh_communes_domiciles WHERE IDdomicile=%s'
                                 % self.param, (ident,))
            if not donnees:
                raise ALSHErreur('Domicile introuvable')
            avant = donnees[0]
            lock = ' FOR UPDATE' if self.dialecte == 'mysql' else ''
            self._lire('SELECT IDindividu FROM individus WHERE IDindividu=%s' % self.param + lock,
                       (avant['IDindividu'],))
            if avant['date_fin'] is not None:
                raise ALSHConflit('Domicile deja cloture : correction explicite a concevoir')
            if fin <= _date_db(avant['date_debut']):
                raise ALSHErreur('Fin exclusive strictement apres debut')
            self._verifier_absence_chevauchement(avant['IDindividu'],
                                                  _date_db(avant['date_debut']), fin, ignorer=ident)
            _, count = self._executer('UPDATE alsh_communes_domiciles SET date_fin=%s '
                                      'WHERE IDdomicile=%s AND date_fin IS NULL' % (self.param, self.param),
                                      (fin, ident))
            if count != 1:
                raise ALSHConflit('Domicile modifie concurremment')
            self._auditer(ident, acteur, 'cloture', {'date_fin': fin, 'ancienne_fin': None})
            return ident
        return self._transaction(operation)

    def domiciles(self, IDindividu, *, acteur):
        self._droit(acteur, 'domicile_lire')
        return self._lire('SELECT * FROM alsh_communes_domiciles WHERE IDindividu=%s '
                          'ORDER BY date_debut, IDdomicile' % self.param,
                          (_id('IDindividu', IDindividu),))

    @staticmethod
    def _configurer_unites(unites):
        if not isinstance(unites, dict) or not unites:
            raise ALSHErreur('Correspondance explicite IDunite -> J/M/A/exclu requise')
        choix = {}
        for k, v in unites.items():
            _id('IDunite', k)
            if v not in ('J', 'M', 'A', 'exclu'):
                raise ALSHErreur('Unite %d : choisir J, M, A ou exclu' % k)
            choix[k] = v
        return choix

    @staticmethod
    def _tarifs(tarifs):
        if tarifs is None:
            return []
        if not isinstance(tarifs, list):
            raise ALSHErreur('Tarifs : liste de clauses contractuelles attendue')
        result = []
        for x in tarifs:
            if not isinstance(x, dict) or set(x) != {
                    'code_insee', 'IDactivite', 'IDgroupe', 'date_debut',
                    'date_fin', 'prix_jour', 'reference'}:
                raise ALSHErreur('Tarif : code INSEE, activite, groupe, dates, prix, reference requis')
            code = _commune(x['code_insee'])
            debut, fin = _date('tarif.date_debut', x['date_debut']), _date('tarif.date_fin', x['date_fin'])
            if fin <= debut:
                raise ALSHErreur('Fin de tarif doit suivre son debut')
            reference = _texte('Reference de convention', x['reference'], 180)
            result.append(dict(code_insee=code,
                               IDactivite=_id('tarif.IDactivite', x['IDactivite']),
                               IDgroupe=_id('tarif.IDgroupe', x['IDgroupe']),
                               date_debut=debut, date_fin=fin,
                               prix_jour=_prix(x['prix_jour']), reference=reference))
        for i, x in enumerate(result):
            for y in result[i+1:]:
                if (x['code_insee'], x['IDactivite'], x['IDgroupe']) == \
                        (y['code_insee'], y['IDactivite'], y['IDgroupe']) and \
                        x['date_debut'] < y['date_fin'] and y['date_debut'] < x['date_fin']:
                    raise ALSHConflit('Tarifs contractuels chevauchants pour la meme commune')
        return result

    def calculer(self, debut, fin, perimetres, unites, *, acteur, tarifs=None, fournisseur_domiciles=None):
        """Brouillon sans ecriture : total, recap enfant et annexe nominative.

        perimetres : couples (IDactivite, IDgroupe) selectionnes MANUELLEMENT.
        unites : {IDunite: 'J'|'M'|'A'|'exclu'} (J=1, M/A=0.5).
        tarifs : clauses explicites de la convention, facultatives, en euros.
        """
        self._droit(acteur, 'frequentation_lire_nominatif')
        debut, fin = _date('debut', debut), _date('fin', fin)
        if fin < debut:
            raise ALSHErreur('Periode inversee')
        if not isinstance(perimetres, (tuple, list)) or not perimetres or len(perimetres) > 100:
            raise ALSHErreur('Selectionner les couples exacts activite/groupe ALSH')
        couples = []
        for pair in perimetres:
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise ALSHErreur('Couple activite/groupe invalide')
            a, g = _id('IDactivite', pair[0]), _id('IDgroupe', pair[1])
            if (a, g) in couples:
                raise ALSHErreur('Couple activite/groupe repete')
            couples.append((a, g))
        config = self._configurer_unites(unites)
        regles = self._tarifs(tarifs)
        p = self.param
        cond = ' OR '.join('(c.IDactivite=%s AND c.IDgroupe=%s)' % (p, p) for _ in couples)
        sql = ('SELECT c.IDconso, c.IDindividu, c.IDactivite, c.IDgroupe, c.IDunite, '
               'c.date AS jour, c.etat, c.quantite, i.nom, i.prenom, '
               'a.nom AS activite, g.nom AS groupe, u.nom AS unite '
               'FROM consommations c INNER JOIN individus i ON i.IDindividu=c.IDindividu '
               'INNER JOIN activites a ON a.IDactivite=c.IDactivite '
               'INNER JOIN groupes g ON g.IDgroupe=c.IDgroupe AND g.IDactivite=c.IDactivite '
               'INNER JOIN unites u ON u.IDunite=c.IDunite AND u.IDactivite=c.IDactivite '
               'WHERE c.date >= %s AND c.date <= %s AND (%s) '
               'ORDER BY c.date, c.IDindividu, c.IDconso' % (p, p, cond))
        args = [debut, fin]
        for a, g in couples:
            args.extend((a, g))
        sources = self._lire(sql, args)
        enfants = sorted({x['IDindividu'] for x in sources})
        if fournisseur_domiciles is not None and not callable(fournisseur_domiciles):
            raise ALSHErreur('Fournisseur de domiciles invalide')
        residences = {}
        # Requetes segmentees : ne dependre ni de la limite 999 parametres
        # de certains SQLite, ni de celle du transport MySQL.
        for i in range(0, len(enfants), 300) if fournisseur_domiciles is None else ():
            groupe_enfants = enfants[i:i+300]
            sql_res = ('SELECT * FROM alsh_communes_domiciles WHERE IDindividu IN (%s) '
                       'AND date_debut<=%s AND (date_fin IS NULL OR date_fin>%s) '
                       'ORDER BY IDindividu, date_debut, IDdomicile' % (
                           ','.join([p]*len(groupe_enfants)), p, p))
            for x in self._lire(sql_res, groupe_enfants+[fin, debut]):
                residences.setdefault(x['IDindividu'], []).append(x)
        seen = set()
        details = []
        buckets = {}
        jours_invalides = set()
        anomalies = []
        for src in sources:
            conso = src['IDconso']
            if conso in seen:
                raise ALSHConflit('Jointure multiple pour IDconso %s' % conso)
            seen.add(conso)
            jour = _date('consommation.date', _date_db(src['jour']))
            ligne = dict(IDconso=conso, IDindividu=src['IDindividu'], nom=src['nom'],
                         prenom=src['prenom'], date=jour, IDactivite=src['IDactivite'],
                         IDgroupe=src['IDgroupe'], IDunite=src['IDunite'],
                         activite=src['activite'], groupe=src['groupe'], unite=src['unite'],
                         etat=src['etat'], quantite=src['quantite'], commune=None,
                         code_insee=None, adresse_complete=None, IDdomicile=None,
                         domicile_date_debut=None, domicile_date_fin=None,
                         reference_convention=None, unite_jour='0', montant_eur=None,
                         statut='non_present', motif='Etat non present')
            details.append(ligne)
            if src['etat'] != 'present':
                continue
            choix = config.get(src['IDunite'])
            if choix == 'exclu':
                ligne.update(statut='hors_perimetre', motif='Unite explicitement exclue')
                continue
            if choix is None:
                ligne.update(statut='a_verifier', motif='Unite non parametree')
                anomalies.append({'IDconso': conso, 'motif': ligne['motif']})
                jours_invalides.add((src['IDindividu'], jour))
                continue
            if src['quantite'] not in (None, 1):
                ligne.update(statut='a_verifier', motif='Quantite differente de un')
                anomalies.append({'IDconso': conso, 'motif': ligne['motif']})
                jours_invalides.add((src['IDindividu'], jour))
                continue
            # C2 supplies a read-only resolver built from Noethys address changes.
            # C1 keeps its original verified manual-history path by default.
            candidats = (fournisseur_domiciles(src['IDindividu'], jour)
                         if fournisseur_domiciles is not None else
                         [d for d in residences.get(src['IDindividu'], ())
                          if _date_db(d['date_debut']) <= jour and
                          (d['date_fin'] is None or jour < _date_db(d['date_fin']))])
            if len(candidats) != 1:
                ligne.update(statut='a_verifier', motif=('Domicile non renseigne' if not candidats
                                                         else 'Plusieurs domiciles'))
                anomalies.append({'IDconso': conso, 'motif': ligne['motif']})
                jours_invalides.add((src['IDindividu'], jour))
                continue
            domicile = candidats[0]
            adr = ', '.join(x for x in (domicile['rue'], domicile['complement'],
                                       domicile['code_postal']+' '+domicile['ville'],
                                       domicile['pays']) if x)
            ligne.update(commune=domicile['ville'], code_insee=domicile['code_insee'],
                         adresse_complete=adr, IDdomicile=domicile['IDdomicile'],
                         domicile_date_debut=_date_db(domicile['date_debut']),
                         domicile_date_fin=_date_db(domicile['date_fin']),
                         statut='provisoire', motif='',
                         unite_jour=('1' if choix == 'J' else '0.5'))
            buckets.setdefault((src['IDindividu'], jour), []).append((choix, ligne))
        for cle, valeurs in buckets.items():
            # Si une autre presence du meme enfant/jour est ambigue, aucune
            # fraction de ce jour ne peut etre attribuee partiellement.
            if cle in jours_invalides:
                for _choix, ligne in valeurs:
                    ligne.update(statut='a_verifier', motif='Autre presence du jour non qualifiee',
                                 unite_jour='0')
                    anomalies.append({'IDconso': ligne['IDconso'], 'motif': ligne['motif']})
                continue
            # Un seul J, ou au plus un M et un A, quels que soient les sites.
            parties = [c for c, _ in valeurs]
            if parties.count('J') > 1 or (('J' in parties) and len(parties) > 1) or \
                    parties.count('M') > 1 or parties.count('A') > 1:
                for _choix, ligne in valeurs:
                    ligne.update(statut='a_verifier', motif='Unites chevauchantes le meme jour',
                                 unite_jour='0')
                    anomalies.append({'IDconso': ligne['IDconso'], 'motif': ligne['motif']})
        for ligne in details:
            if ligne['statut'] != 'provisoire':
                continue
            jour, commune = ligne['date'], ligne['code_insee']
            candidats = [r for r in regles if r['code_insee'] == commune and
                         r['IDactivite'] == ligne['IDactivite'] and
                         r['IDgroupe'] == ligne['IDgroupe'] and
                         r['date_debut'] <= jour < r['date_fin']]
            if len(candidats) == 1:
                r = candidats[0]
                ligne['reference_convention'] = r['reference']
                ligne['tarif_jour_eur'] = format(r['prix_jour'], '.2f')
                ligne['statut'] = 'chiffre'
            elif not regles:
                ligne['statut'] = 'presence_sans_tarif'
            else:
                ligne.update(statut='a_verifier', motif='Tarif de convention manquant')
                anomalies.append({'IDconso': ligne['IDconso'], 'motif': ligne['motif']})
        # Arrondi par (enfant, date, commune, tarif et convention). Deux
        # demi-journees a 11,55 EUR totalisent 11,55, pas 11,56 : le reste
        # de centime est attribue de facon deterministe a la derniere ligne.
        groupes_argent = {}
        for ligne in details:
            if ligne['statut'] == 'chiffre':
                cle = (ligne['IDindividu'], ligne['date'], ligne['code_insee'],
                       ligne['tarif_jour_eur'], ligne['reference_convention'])
                groupes_argent.setdefault(cle, []).append(ligne)
        for cle, lignes_groupe in groupes_argent.items():
            prix = Decimal(cle[3])
            cumul = (prix * sum((Decimal(x['unite_jour']) for x in lignes_groupe),
                                Decimal('0'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            restant = cumul
            for ligne in lignes_groupe[:-1]:
                montant = (prix * Decimal(ligne['unite_jour'])).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP)
                ligne['montant_eur'] = format(montant, '.2f')
                restant -= montant
            lignes_groupe[-1]['montant_eur'] = format(restant, '.2f')
        recap = {}
        total = Decimal('0')
        for ligne in details:
            if ligne['statut'] not in ('chiffre', 'presence_sans_tarif'):
                continue
            key = (ligne['code_insee'], ligne['IDindividu'], ligne['IDdomicile'])
            r = recap.setdefault(key, dict(code_insee=ligne['code_insee'], commune=ligne['commune'],
                                           IDindividu=ligne['IDindividu'], nom=ligne['nom'],
                                           prenom=ligne['prenom'], adresse_complete=ligne['adresse_complete'],
                                           IDdomicile=ligne['IDdomicile'],
                                           domicile_date_debut=ligne['domicile_date_debut'],
                                           domicile_date_fin=ligne['domicile_date_fin'],
                                           nombre_lignes=0,
                                           journees='0', montant_eur=None, dates=[]))
            r['nombre_lignes'] += 1
            r['dates'].append(ligne['date'])
            r['journees'] = str(Decimal(r['journees'])+Decimal(ligne['unite_jour']))
            if ligne['montant_eur'] is not None:
                r['montant_eur'] = format(Decimal(r['montant_eur'] or '0')+
                                          Decimal(ligne['montant_eur']), '.2f')
                total += Decimal(ligne['montant_eur'])
        synth = {}
        for r in recap.values():
            code = r['code_insee']
            stat = synth.setdefault(code, dict(code_insee=code, commune=r['commune'],
                                               enfants_distincts=set(), journees=Decimal('0'),
                                               montant=Decimal('0')))
            stat['enfants_distincts'].add(r['IDindividu'])
            stat['journees'] += Decimal(r['journees'])
            if r['montant_eur'] is not None:
                stat['montant'] += Decimal(r['montant_eur'])
            r['date_debut'], r['date_fin'] = min(r['dates']), max(r['dates'])
            del r['dates']
        resume = []
        for stat in sorted(synth.values(), key=lambda x: x['code_insee']):
            resume.append(dict(code_insee=stat['code_insee'], commune=stat['commune'],
                               enfants_distincts=len(stat['enfants_distincts']),
                               journees=str(stat['journees']), montant_eur=format(stat['montant'], '.2f')
                               if regles else None))
        distincts_global = len({r['IDindividu'] for r in recap.values()})
        journees = sum((Decimal(r['journees']) for r in recap.values()), Decimal('0'))
        if journees != sum((Decimal(x['journees']) for x in resume), Decimal('0')):
            raise ALSHConflit('Ecart de reconciliation interne par commune')
        return dict(periode=(debut, fin), etat='BROUILLON NON FACTURABLE',
                    liquidable=bool(regles) and not anomalies and bool(recap),
                    enfants_distincts_global=distincts_global,
                    journees_global=str(journees),
                    montant_total_eur=format(total, '.2f') if regles else None,
                    communes=resume, enfants=sorted(recap.values(), key=lambda x: (
                        x['commune'], x['nom'] or '', x['prenom'] or '', x['date_debut'])),
                    lignes=details, anomalies=anomalies)

    def csv_nominatif(self, resultat, *, acteur, code_insee=None):
        """CSV compatible Excel, filtre commune obligatoire et audit d'edition.

        Aucune adresse d'une autre commune n'est presente dans le document.
        """
        acteur = self._droit(acteur, 'frequentation_export_nominatif')
        if not isinstance(resultat, dict) or resultat.get('etat') != 'BROUILLON NON FACTURABLE':
            raise ALSHErreur('Etat brut de SituationCommunesALSH attendu')
        if resultat['anomalies']:
            raise ALSHConflit('Annexe nominative bloquee : anomalies a corriger')
        code = _commune(code_insee)
        lignes = [x for x in resultat['lignes'] if x['code_insee'] == code]
        colonnes = ('IDindividu', 'nom', 'prenom', 'adresse_complete', 'commune',
                    'code_insee', 'domicile_date_debut', 'domicile_date_fin',
                    'date', 'activite', 'groupe', 'unite', 'etat',
                    'unite_jour', 'montant_eur', 'statut', 'motif', 'IDconso')
        sortie = io.StringIO(newline='')
        writer = csv.writer(sortie, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(('DOCUMENT PREPARATOIRE - PAS UNE FACTURE',))
        writer.writerow(colonnes)
        for ligne in lignes:
            writer.writerow([_csv_safe(ligne.get(k)) for k in colonnes])
        texte = '\ufeff' + sortie.getvalue()
        # Controle et journal de la sortie nominative, sans stockage de donnees
        # supplementaires relatives aux enfants dans le journal des exports.
        def operation():
            self._executer('INSERT INTO alsh_communes_exports '
                           '(date_export, acteur, code_insee, periode_debut, periode_fin, nombre_lignes) '
                           'VALUES (%s)' % ','.join([self.param]*6),
                           (_horodatage(), acteur, code, resultat['periode'][0],
                            resultat['periode'][1], len(lignes)))
        self._transaction(operation)
        return texte

    def csv_recap_enfants(self, resultat, *, acteur, code_insee=None):
        """CSV enfant/commune/domicile : donnees strictement de cette commune."""
        acteur = self._droit(acteur, 'frequentation_export_nominatif')
        if not isinstance(resultat, dict) or resultat.get('etat') != 'BROUILLON NON FACTURABLE':
            raise ALSHErreur('Etat brut de SituationCommunesALSH attendu')
        if resultat['anomalies']:
            raise ALSHConflit('Recapitulatif nominatif bloque : anomalies a corriger')
        code = _commune(code_insee)
        lignes = [x for x in resultat['enfants'] if x['code_insee'] == code]
        colonnes = ('IDindividu', 'nom', 'prenom', 'adresse_complete', 'commune',
                    'code_insee', 'domicile_date_debut', 'domicile_date_fin',
                    'date_debut', 'date_fin', 'nombre_lignes', 'journees', 'montant_eur')
        sortie = io.StringIO(newline='')
        writer = csv.writer(sortie, delimiter=';')
        writer.writerow(('DOCUMENT PREPARATOIRE - PAS UNE FACTURE',))
        writer.writerow(colonnes)
        for ligne in lignes:
            writer.writerow([_csv_safe(ligne.get(k)) for k in colonnes])
        def operation():
            self._executer('INSERT INTO alsh_communes_exports '
                           '(date_export, acteur, code_insee, periode_debut, periode_fin, nombre_lignes) '
                           'VALUES (%s)' % ','.join([self.param]*6),
                           (_horodatage(), acteur, code, resultat['periode'][0],
                            resultat['periode'][1], len(lignes)))
        self._transaction(operation)
        return '\ufeff' + sortie.getvalue()

    def csv_anonyme(self, resultat, *, acteur):
        self._droit(acteur, 'frequentation_export_anonyme')
        if not isinstance(resultat, dict) or resultat.get('etat') != 'BROUILLON NON FACTURABLE':
            raise ALSHErreur('Etat brut de SituationCommunesALSH attendu')
        sortie = io.StringIO(newline='')
        w = csv.writer(sortie, delimiter=';')
        w.writerow(('Commune', 'Code INSEE', 'Enfants distincts', 'Journees', 'Montant EUR'))
        for x in resultat['communes']:
            w.writerow([_csv_safe(x.get(k)) for k in ('commune', 'code_insee',
                                                      'enfants_distincts', 'journees',
                                                      'montant_eur')])
        return '\ufeff' + sortie.getvalue()
