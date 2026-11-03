# -*- coding: utf-8 -*-
"""D6 : registre de factures partenaires d'une association loi 1901, sans gestion de TVA.

Un bordereau D5 valide devient au plus une facture numerotee et figee.
Aucun champ de taux / montant de TVA, aucun compte payeur famille, aucun encaissement.
Ce moteur n'edite ni PDF, ni facture electronique, ni ecriture comptable historique.
Toutes les operations acceptent une connexion DB-API explicite ; aucun schema n'est cree.
"""

from datetime import date
from decimal import Decimal
import json
import re

from Utils.UTILS_Partenaires_D1 import AutorisationRefusee, Introuvable, PartenairesErreur
from Utils.UTILS_Partenaires_D5 import (
    BordereauxPartenaires, BordereauConflit, BordereauIntegrite,
    _date, _digest, _id, _iso, _now, _texte,
)


class FactureInvalide(PartenairesErreur):
    pass


class FactureConflit(FactureInvalide):
    pass


class FactureIntegrite(FactureInvalide):
    pass


def _champ(data, cle, longueur=255):
    valeur = data.get(cle)
    if valeur is None or valeur == '':
        return None
    return _texte(valeur, cle, longueur)


def _json(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _emetteur(profil):
    if not isinstance(profil, dict):
        raise FactureInvalide('Profil emetteur obligatoire')
    champs = {'raison_sociale', 'adresse_ligne1', 'code_postal', 'commune',
              'siret', 'mention_fiscale', 'conditions_paiement',
              'penalites_retard', 'indemnite_recouvrement', 'email_general'}
    if set(profil) - champs:
        raise FactureInvalide('Champ emetteur inconnu ou gestion de taxe interdite')
    obli = ('raison_sociale', 'adresse_ligne1', 'code_postal', 'commune',
            'siret', 'mention_fiscale', 'conditions_paiement', 'penalites_retard')
    valeurs = {c: _champ(profil, c, 350 if c in ('conditions_paiement',
                  'penalites_retard', 'mention_fiscale') else 255)
               for c in champs}
    if any(not valeurs[c] for c in obli):
        raise FactureInvalide('Profil emetteur incomplet : facture interdite')
    if not re.fullmatch(r'[0-9]{14}', valeurs['siret']):
        raise FactureInvalide('SIRET emetteur a 14 chiffres requis')
    # L'article legal exact n'est pas deduit de la seule forme association 1901.
    # La mention fiscale est sous la responsabilite de la direction.
    return dict(sorted(valeurs.items()), forme='Association loi 1901')


def _client(donnees):
    valeurs = {c: _champ(donnees, c) for c in (
        'raison_sociale', 'adresse_ligne1', 'code_postal', 'commune',
        'pays', 'siret')}
    if any(not valeurs[c] for c in ('raison_sociale', 'adresse_ligne1',
                                     'code_postal', 'commune')):
        raise FactureInvalide('Adresse du partenaire incomplete dans D1')
    if valeurs['siret'] and not re.fullmatch(r'[0-9]{14}', valeurs['siret']):
        raise FactureInvalide('SIRET destinataire invalide')
    valeurs['pays'] = valeurs['pays'] or 'France'
    return dict(sorted(valeurs.items()))


class FacturesPartenaires:
    def __init__(self, connexion, *, dialecte='sqlite', autoriser=None):
        if connexion is None or dialecte not in ('sqlite', 'mysql'):
            raise FactureInvalide('Connexion DB-API et dialecte valides requis')
        self.connexion = connexion
        self.dialecte = dialecte
        self.param = '?' if dialecte == 'sqlite' else '%s'
        self.autoriser = autoriser
        self.bordereaux = BordereauxPartenaires(
            connexion, dialecte=dialecte, autoriser=autoriser)

    def _droit(self, acteur, action):
        acteur = _texte(acteur, 'acteur', 100)
        if not callable(self.autoriser) or self.autoriser(acteur, action) is not True:
            raise AutorisationRefusee('D6 : operation refusee')
        return acteur

    def _lire(self, sql, args=()):
        return self.bordereaux._lire(sql, args)

    def _inserer(self, table, valeurs):
        return self.bordereaux._inserer(table, valeurs)

    def _preparer(self, bid, emetteur, date_emission, date_echeance, *, acteur):
        _id(bid)
        date_emission, date_echeance = _date(date_emission), _date(date_echeance)
        if date_echeance < date_emission:
            raise FactureInvalide('Echeance avant emission')
        profil = _emetteur(emetteur)
        lot = self.bordereaux.lire_bordereau(bid, acteur=acteur, verifier_sources=True)
        b, lignes = lot['bordereau'], lot['lignes']
        if b['etat'] != 'valide' or lot['reference']:
            raise FactureConflit('Bordereau non valide ou deja lie a une facture externe')
        if not lignes:
            raise FactureInvalide('Bordereau vide')
        if self._lire('SELECT IDfacture_partenaire FROM partenaires_factures_officielles '
                      'WHERE IDbordereau=%s' % self.param, (bid,)):
            raise FactureConflit('Bordereau deja enregistre en facture D6')
        c = self._lire('SELECT * FROM partenaires_structures WHERE IDpartenaire=%s'
                       % self.param, (b['IDpartenaire'],))
        if len(c) != 1 or c[0]['statut'] != 'actif':
            raise FactureInvalide('Partenaire absent ou archive')
        client = _client(c[0])
        last = max(_iso(ligne['date_reelle']) for ligne in lignes)
        if date_emission < last:
            raise FactureInvalide('Date emission anterieure a la prestation')
        montant = str(b['total'])
        if not re.fullmatch(r'(?:0|[1-9][0-9]{0,9})\.[0-9]{2}', montant) or Decimal(montant) <= 0:
            raise FactureIntegrite('Montant D5 non canonique')
        details = [{k:ligne[k] for k in ('IDintervention','date_reelle','categorie',
                    'libelle','minutes_reelles','unite','prix_unitaire','montant')}
                   for ligne in lignes]
        donnees = {
            'type_document': 'facture_partenaire',
            'emetteur': profil,
            'destinataire': client,
            'IDpartenaire': b['IDpartenaire'],
            'IDbordereau': bid,
            'reference_bordereau': b['reference'],
            'empreinte_bordereau': b['empreinte'],
            'date_emission': date_emission,
            'date_echeance': date_echeance,
            'date_prestation': last,
            'periode_debut': b['date_debut'],
            'periode_fin': b['date_fin'],
            'lignes': details,
            'total_eur': montant,
            'devise': 'EUR',
            # Ni taux, ni assiette, ni montant de TVA.
        }
        return {'donnees': donnees, 'empreinte_preparation': _digest(donnees)}

    def preparer_facture(self, bid, emetteur, date_emission, date_echeance, *, acteur):
        self._droit(acteur, 'preparer_facture')
        return self._preparer(bid, emetteur, date_emission, date_echeance, acteur=acteur)

    def _numero(self, date_emission):
        suffix = ' FOR UPDATE' if self.dialecte == 'mysql' else ''
        rows = self._lire('SELECT * FROM partenaires_factures_sequence WHERE singleton=1' + suffix)
        if len(rows) != 1:
            raise FactureIntegrite('Compteur numerotation absent')
        seq = rows[0]
        exercice = int(date_emission[:4])
        precedent = int(seq['exercice'])
        dernier = int(seq['dernier_numero'])
        if precedent > exercice or (seq['derniere_date'] and
                                    date_emission < _iso(seq['derniere_date'])):
            raise FactureConflit('Numerotation chronologique : antidatage refuse')
        if precedent and (dernier < 1 or precedent > 9999):
            raise FactureIntegrite('Compteur D6 incoherent')
        # Denombrement supplementaire pour reperer un compteur local altere.
        historique = self._lire('SELECT exercice, ordre, date_emission FROM '
                                'partenaires_factures_officielles ORDER BY '
                                'date_emission DESC, IDfacture_partenaire DESC LIMIT 1')
        if precedent == 0 and (dernier != 0 or historique):
            raise FactureIntegrite('Compteur initial incoherent')
        if precedent and (not historique or int(historique[0]['exercice']) != precedent
                          or int(historique[0]['ordre']) != dernier
                          or _iso(historique[0]['date_emission']) != _iso(seq['derniere_date'])):
            raise FactureIntegrite('Compteur different du journal des factures')
        numero = dernier + 1 if exercice == precedent else 1
        reference = 'PMSL-%04d-%06d' % (exercice, numero)
        if len(reference) > 40:
            raise FactureInvalide('Numero hors limites')
        self.bordereaux._modifier('partenaires_factures_sequence', 'singleton', 1, {
            'exercice': exercice, 'dernier_numero': numero, 'derniere_date':date_emission,
        })
        return exercice, numero, reference

    def enregistrer_facture(self, bid, emetteur, date_emission, date_echeance,
                           empreinte_preparation, *, acteur):
        acteur = self._droit(acteur, 'enregistrer_facture')
        if not isinstance(empreinte_preparation, str) or not re.fullmatch('[0-9a-f]{64}', empreinte_preparation):
            raise FactureInvalide('Empreinte de preparation requise')
        def action():
            # BEGIN IMMEDIATE (SQLite) ou transaction InnoDB explicite (MySQL).
            # L'original D5 est relu integralement dans cette transaction.
            prep = self._preparer(bid, emetteur, date_emission, date_echeance, acteur=acteur)
            if prep['empreinte_preparation'] != empreinte_preparation:
                raise FactureConflit('Apercu obsolete : emission annulee')
            exercice, ordre, reference = self._numero(date_emission)
            doc = dict(prep['donnees'], numero=reference, etat='enregistree')
            digest = _digest(doc)
            ident = self._inserer('partenaires_factures_officielles', {
                'IDbordereau': bid, 'IDpartenaire': doc['IDpartenaire'],
                'numero':reference,'exercice':exercice,'ordre':ordre,
                'date_emission': date_emission, 'date_echeance':date_echeance,
                'date_prestation': doc['date_prestation'],
                'periode_debut':doc['periode_debut'], 'periode_fin':doc['periode_fin'],
                'total':doc['total_eur'],
                'empreinte_bordereau': doc['empreinte_bordereau'],
                'donnees_json': _json(doc), 'empreinte_document':digest,
                'etat':'enregistree', 'cree_le':_now(), 'cree_par':acteur,
            })
            self._inserer('partenaires_factures_evenements', {
                'IDfacture_partenaire':ident, 'action':'enregistrement',
                'acteur':acteur, 'date_action':_now(),
            })
            return {'IDfacture_partenaire':ident, 'numero':reference,
                    'montant_a_regler_eur':doc['total_eur'],
                    'empreinte_document':digest,'transmise':False,
                    'pdf_genere':False}
        try:
            return self.bordereaux._transaction(action)
        except BordereauConflit as exc:
            raise FactureConflit('Echec atomique : conflit de numerotation ou doublon') from exc

    def lire_facture(self, IDfacture_partenaire, *, acteur, verifier_source=True):
        self._droit(acteur, 'lire_facture')
        rows = self._lire('SELECT * FROM partenaires_factures_officielles '
                          'WHERE IDfacture_partenaire=%s' % self.param,
                          (_id(IDfacture_partenaire),))
        if not rows:
            raise Introuvable('Facture partenaire absente')
        record = rows[0]
        try:
            doc = json.loads(record['donnees_json'])
        except (TypeError, ValueError) as exc:
            raise FactureIntegrite('Document serialise illisible') from exc
        if not isinstance(doc, dict) or _digest(doc) != record['empreinte_document']:
            raise FactureIntegrite('Empreinte de la facture invalide')
        for pair in (('numero','numero'),('IDbordereau','IDbordereau'),
                     ('IDpartenaire','IDpartenaire'),('date_emission','date_emission'),
                     ('date_echeance','date_echeance'),('date_prestation','date_prestation'),
                     ('periode_debut','periode_debut'),('periode_fin','periode_fin'),
                     ('total_eur','total'),('empreinte_bordereau','empreinte_bordereau'),
                     ('etat','etat')):
            if str(doc.get(pair[0])) != str(_iso(record[pair[1]])):
                raise FactureIntegrite('Incoherence document / index : %s' % pair[0])
        if record['etat'] != 'enregistree' or int(record['ordre']) < 1:
            raise FactureIntegrite('Etat ou numero invalide')
        if record['numero'] != 'PMSL-%04d-%06d' % (record['exercice'],record['ordre']):
            raise FactureIntegrite('Numerotation alteree')
        if verifier_source:
            lot = self.bordereaux.lire_bordereau(record['IDbordereau'], acteur=acteur)
            if lot['bordereau']['empreinte'] != record['empreinte_bordereau'] or \
                    lot['bordereau']['total'] != doc['total_eur']:
                raise FactureIntegrite('Source D5 incoherente')
        return {'facture':doc, 'IDfacture_partenaire':record['IDfacture_partenaire'],
                'empreinte_document':record['empreinte_document'], 'transmise':False,
                'pdf_genere':False}

    def modele_noedoc(self, IDfacture_partenaire, *, acteur):
        """Valeurs structurees pour un futur moteur de modele, sans rendu ni envoi."""
        self._droit(acteur, 'modele_noedoc')
        return self.lire_facture(IDfacture_partenaire, acteur=acteur)
