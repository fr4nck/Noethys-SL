# -*- coding: utf-8 -*-
"""Journal Mailjet partage et consultation HTTP GET uniquement.

Stockage versionne dans une categorie reservee de la table native parametres
(VARCHAR(30000)), une entree par message/destinataire. Aucune migration, cle,
corps de mail ni piece jointe. Les lectures HTTP ne changent jamais l'envoi.
"""
import datetime
import hashlib
import json
import re

CATEGORIE = 'noethys_sl_suivi_mailjet_v1'
ETATS = {
    'accepted': 'Accepté par Mailjet', 'processed': 'En préparation',
    'queued': "En attente d'expédition", 'deferred': 'Livraison différée',
    'retrying': 'Nouvelle tentative en cours', 'sent': 'Livré au serveur destinataire',
    'delivered': 'Livré au serveur destinataire', 'opened': 'Ouverture signalée',
    'clicked': 'Clic signalé', 'bounce': 'Non livré', 'bounced': 'Non livré',
    'softbounced': 'Échec temporaire', 'hardbounced': 'Échec définitif',
    'softbounce': 'Échec temporaire', 'hardbounce': 'Échec définitif',
    'blocked': 'Bloqué', 'spam': 'Signalé comme indésirable',
    'unsub': 'Désabonnement signalé', 'unsubscribed': 'Désabonnement signalé',
}
ERREURS_LIVRAISON = {'bounce', 'bounced', 'softbounced', 'hardbounced', 'softbounce', 'hardbounce', 'blocked'}


class ErreurSuivi(Exception):
    def __init__(self, texte, arret_lot=False):
        super().__init__(texte)
        self.arret_lot = arret_lot


def Maintenant():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def MessageID(value):
    if isinstance(value, bool) or not re.fullmatch(r'[0-9]{1,20}', str(value or '')):
        raise ErreurSuivi('Identifiant Mailjet invalide.')
    value = int(value)
    if not 0 < value <= 18446744073709551615:
        raise ErreurSuivi('Identifiant Mailjet invalide.')
    return str(value)


def Compte(api_key):
    if not isinstance(api_key, str) or not api_key:
        raise ErreurSuivi('Compte Mailjet non configuré.')
    return hashlib.sha256(api_key.encode('utf-8')).hexdigest()


def Parametres(texte):
    return dict(part.split('==', 1) for part in (texte or '').split('##') if '==' in part)


def Libelle(etat):
    return ETATS.get(etat, 'État fournisseur non reconnu')


def BaseCourante():
    """A appeler sur le thread UI, avant de demarrer un travail HTTP."""
    import GestionDB
    db = GestionDB.DB()
    try:
        if db.echec:
            raise ErreurSuivi('Ouvrez un fichier Noethys pour utiliser le suivi Mailjet.')
        return db.nomFichier
    finally:
        db.Close()


def _encoder(record):
    # JSON ASCII : conserver egalement les emojis sur les anciens serveurs
    # MySQL utf8 (3 octets), sans toucher au charset du fichier Noethys.
    value = json.dumps(record, ensure_ascii=True, sort_keys=True)
    if len(value) > 30000:
        raise ErreurSuivi('Entrée de suivi trop volumineuse.')
    return value


class Journal:
    def __init__(self, fichier, fabrique=None):
        if not fichier:
            raise ErreurSuivi('Fichier de suivi non défini.')
        self.fichier = fichier
        self.fabrique = fabrique

    def _ouvrir(self):
        if self.fabrique is None:
            import GestionDB
            db = GestionDB.DB(nomFichier=self.fichier, suffixe=None)
        else:
            db = self.fabrique(self.fichier)
        if getattr(db, 'echec', 0):
            db.Close()
            raise ErreurSuivi('Journal Mailjet inaccessible.')
        return db

    @staticmethod
    def _execute(db, req, args=()):
        db.cursor.execute(req.replace('?', '%s') if db.isNetwork else req, args)

    def Enregistrer(self, api_key, expediteur, sujet, identifiants, date_envoi=None, ancien=False):
        compte = Compte(api_key)
        rows = {}
        for adresse, guid, mid in identifiants:
            mid = MessageID(mid)
            if not isinstance(adresse, str) or len(adresse) > 320:
                raise ErreurSuivi('Destinataire de suivi invalide.')
            nom = compte + ':' + mid
            record = dict(version=1, compte=compte, message_id=mid, uuid=str(guid or '')[:64],
                          destinataire=adresse, expediteur=str(expediteur or '')[:320],
                          sujet=str(sujet or '')[:500], date_envoi=date_envoi or Maintenant(),
                          etat='accepted', verifie_le='', evenement_le='', detail='',
                          erreur_consultation='', ancien=bool(ancien))
            if nom in rows and rows[nom]['destinataire'].casefold() != adresse.casefold():
                raise ErreurSuivi('Identifiant Mailjet associé à plusieurs destinataires.')
            rows[nom] = record
        if not rows:
            raise ErreurSuivi("Mailjet n'a pas fourni d'identifiant exploitable pour le suivi.")
        db = self._ouvrir()
        verrou = None
        try:
            if db.isNetwork:
                nom_verrou = 'noethys-mailjet-' + compte[:40]
                self._execute(db, 'SELECT GET_LOCK(?, 5)', (nom_verrou,))
                if db.cursor.fetchone()[0] != 1:
                    raise ErreurSuivi('Journal Mailjet occupé par un autre poste.')
                verrou = nom_verrou
            else:
                self._execute(db, 'BEGIN IMMEDIATE')
            for nom, record in rows.items():
                self._execute(db, 'SELECT IDparametre FROM parametres WHERE categorie=? AND nom=? LIMIT 1', (CATEGORIE, nom))
                if db.cursor.fetchone() is None:
                    self._execute(db, 'INSERT INTO parametres (categorie, nom, parametre) VALUES (?, ?, ?)',
                                  (CATEGORIE, nom, _encoder(record)))
            db.Commit()
        except Exception:
            db.connexion.rollback()
            raise
        finally:
            try:
                if verrou:
                    self._execute(db, 'SELECT RELEASE_LOCK(?)', (verrou,))
                    # Les curseurs MySQL non buffers doivent consommer le
                    # resultat avant de rendre la connexion au pool.
                    db.cursor.fetchone()
            finally:
                db.Close()

    def Lister(self, compte=None, limite=500):
        db = self._ouvrir()
        try:
            args = [CATEGORIE]
            req = 'SELECT IDparametre, nom, parametre FROM parametres WHERE categorie=?'
            if compte:
                req += ' AND nom LIKE ?'
                args.append(compte + ':%')
            # Doublons possibles si deux callbacks identiques ont ete executes
            # simultanement : dedoublonner l'identite fournisseur a la lecture.
            req += ' ORDER BY IDparametre DESC LIMIT %d' % min(max(int(limite), 1), 2000)
            self._execute(db, req, tuple(args))
            records = {}
            for ID, nom, raw in db.cursor.fetchall():
                try:
                    record = json.loads(raw)
                    valid = (record['version'] == 1 and record['compte'] + ':' + MessageID(record['message_id']) == nom)
                    if (not valid or not re.fullmatch('[0-9a-f]{64}', record['compte']) or
                            any(not isinstance(record.get(key), str) for key in (
                                'destinataire', 'sujet', 'date_envoi', 'etat', 'verifie_le',
                                'evenement_le', 'detail', 'erreur_consultation'))):
                        raise ValueError()
                except Exception:
                    raise ErreurSuivi('Une entrée du journal Mailjet est illisible ; aucune donnée ne sera effacée.')
                record['_id'], record['_nom'], record['_raw'] = ID, nom, raw
                prior = records.get(nom)
                if prior is None or record.get('verifie_le', '') > prior.get('verifie_le', ''):
                    records[nom] = record
            return list(records.values())
        finally:
            db.Close()

    def SauverResultat(self, record, resultat=None, erreur=''):
        updated = {key: value for key, value in record.items() if not key.startswith('_')}
        if resultat:
            for key in ('etat', 'verifie_le', 'evenement_le', 'detail', 'destinataire'):
                if key in resultat:
                    updated[key] = resultat[key]
            updated['erreur_consultation'] = ''
        else:
            # Une panne de consultation ne remplace jamais le dernier etat connu.
            updated['erreur_consultation'] = str(erreur)[:600]
        db = self._ouvrir()
        try:
            comparaison = 'BINARY parametre=?' if db.isNetwork else 'parametre=?'
            self._execute(db, 'UPDATE parametres SET parametre=? WHERE IDparametre=? AND categorie=? AND ' + comparaison,
                          (_encoder(updated), record['_id'], CATEGORIE, record['_raw']))
            changed = db.cursor.rowcount == 1
            db.Commit()
            return changed  # False : un autre poste a actualise depuis la lecture.
        except Exception:
            db.connexion.rollback()
            raise
        finally:
            db.Close()

    def Comptes(self):
        db = self._ouvrir()
        try:
            self._execute(db, "SELECT IDadresse, adresse, nom_adresse, parametres FROM adresses_mail WHERE moteur=? ORDER BY adresse", ('mailjet',))
            comptes = []
            for ID, adresse, nom, texte in db.cursor.fetchall():
                params = Parametres(texte)
                key, secret = params.get('api_key'), params.get('api_secret')
                if key and secret:
                    comptes.append(dict(id=ID, adresse=adresse, nom=nom, compte=Compte(key), auth=(key, secret)))
            return comptes
        finally:
            db.Close()


def AnciensMessages(tracks):
    """Reprise volontaire des seules traces completes produites par le Mailer.
    Ne pas deviner un MessageID depuis un sujet, une trace tronquee ou une adresse.
    """
    records = []
    for track in tracks:
        if getattr(track, 'IDcategorie', None) != 33:
            continue
        match = re.search(r" \(accepté par Mailjet, MessageID ([0-9]+(?:, [0-9]+)*)\)$", track.action or '')
        if match:
            for mid in match.group(1).split(', '):
                records.append(dict(message_id=MessageID(mid), sujet=track.action[:match.start()],
                                    date_envoi=str(track.date) + 'T' + str(track.heure)))
    return records


def _date_evenement(value):
    try:
        return datetime.datetime.fromtimestamp(int(value), datetime.timezone.utc).isoformat(timespec='seconds')
    except (ValueError, TypeError, OverflowError, OSError):
        return ''


class Consultation:
    """Le transport injecte ne recoit que des requetes GET vers api.mailjet.com."""
    def __init__(self, auth, get=None):
        if not isinstance(auth, (tuple, list)) or len(auth) != 2 or not all(isinstance(x, str) and x for x in auth):
            raise ErreurSuivi('Identifiants Mailjet non configurés.')
        self.auth = auth
        if get is None:
            import requests
            get = requests.get
        self.get = get

    def _texte(self, value):
        value = str(value or '')
        for secret in self.auth:
            value = value.replace(secret, '[masqué]')
        return re.sub(r'[\x00-\x1f]', ' ', value)[:600]

    def _lire(self, resource, mid, params=None):
        if resource not in ('message', 'messagehistory', 'bouncestatistics'):
            raise ErreurSuivi('Ressource de suivi non autorisée.')
        try:
            response = self.get('https://api.mailjet.com/v3/REST/%s/%s' % (resource, MessageID(mid)),
                                auth=self.auth, timeout=(5, 10), params=params or {}, allow_redirects=False)
        except Exception:
            raise ErreurSuivi('Consultation Mailjet impossible : connexion ou délai dépassé.') from None
        status = response.status_code
        if status in (401, 403):
            raise ErreurSuivi("Accès Mailjet refusé : vérifiez le compte d'expédition et ses droits.", arret_lot=True)
        if status == 404:
            raise ErreurSuivi('Message introuvable sur ce compte Mailjet, ou historique expiré.')
        if status == 429:
            raise ErreurSuivi('Limite de consultations Mailjet atteinte ; réessayez plus tard.', arret_lot=True)
        if status != 200:
            raise ErreurSuivi('Consultation Mailjet indisponible (HTTP %s).' % status)
        try:
            body = response.json()
            data = body['Data']
            if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
                raise ValueError()
            return data
        except Exception:
            raise ErreurSuivi('Réponse de suivi Mailjet inexploitable.') from None

    def Verifier(self, record):
        if record.get('compte') != Compte(self.auth[0]):
            raise ErreurSuivi("Ce message appartient à un autre compte Mailjet.")
        mid = MessageID(record['message_id'])
        data = self._lire('message', mid, {'ShowContactAlt': 'true'})
        if len(data) != 1 or MessageID(data[0].get('ID')) != mid or not isinstance(data[0].get('Status'), str):
            raise ErreurSuivi('Réponse Mailjet incompatible avec le message demandé.')
        row = data[0]
        destinataire = row.get('ContactAlt') or record.get('destinataire', '')
        if not isinstance(destinataire, str) or not destinataire or len(destinataire) > 320:
            raise ErreurSuivi('Destinataire Mailjet absent ou inexploitable.')
        if record.get('destinataire') and destinataire.casefold() != record['destinataire'].casefold():
            raise ErreurSuivi('Le destinataire retourné par Mailjet ne correspond pas au message mémorisé.')
        result = dict(etat=self._texte(row['Status'].lower()), destinataire=self._texte(destinataire),
                      verifie_le=Maintenant(), evenement_le='', detail='')
        try:
            events = self._lire('messagehistory', mid, {'Limit': 100})
            dates = [_date_evenement(event.get('EventAt')) for event in events]
            result['evenement_le'] = max(dates, default='')
            details = [self._texte(event.get('Comment') or event.get('State') or event.get('Error') or event.get('SMTPReply'))
                       for event in events if str(event.get('EventType', '')).lower() in ERREURS_LIVRAISON]
            if result['etat'] in ERREURS_LIVRAISON:
                result['detail'] = '; '.join(value for value in details if value)[-600:]
            if result['etat'] in ERREURS_LIVRAISON:
                bounces = self._lire('bouncestatistics', mid)
                reasons = [self._texte(b.get('Comment') or b.get('Error') or b.get('Reason') or
                                      ('Code Mailjet %s' % b['StateID'] if b.get('StateID') else '')) for b in bounces]
                if any(reasons):
                    result['detail'] = '; '.join(x for x in reasons if x)[-600:]
        except ErreurSuivi as error:
            result['detail'] = (result['detail'] + ' ' + str(error)).strip()[:600]
            result['_arreter_lot'] = error.arret_lot
        return result


def Actualiser(records, auth, resultats, arret, get=None):
    """Travailleur sans wx et sans DB : le thread UI conserve les resultats."""
    try:
        try:
            client = Consultation(auth, get=get)
        except ErreurSuivi as error:
            for record in records:
                resultats.put((record, None, str(error)))
            return
        for record in records:
            if arret.is_set():
                break
            try:
                resultat = client.Verifier(record)
                resultats.put((record, resultat, ''))
                if resultat.get('_arreter_lot'):
                    break
            except ErreurSuivi as error:
                resultats.put((record, None, str(error)))
                if error.arret_lot:
                    break
            except Exception:
                resultats.put((record, None, 'Erreur inattendue de consultation Mailjet.'))
    finally:
        resultats.put(None)
