# -*- coding: utf-8 -*-
"""Lot D2 : conventions partenaires et avenants, hors interface et hors production.

DB-API explicite et connexion dediee (SQLite ou MySQL). Aucune ouverture de
GestionDB, migration automatique, facturation ou ecriture dans les tables
historiques. L'autorisation de lecture et d'ecriture est refusee par defaut.

Une version signee est un instantane complet. Un avenant produit une nouvelle
version et ne remplace jamais les clauses ni les tarifs de l'ancienne.
L'empreinte SHA256 controle des changements accidentels, PAS l'identite du
signataire ni l'authenticite cryptographique du document transmis.
"""

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

from Utils.UTILS_Partenaires_D1 import (
    AutorisationRefusee, ConflitPartenaire, Introuvable, PartenairesErreur,
)

TYPES_CONVENTION = frozenset(('scolaire', 'associative', 'collectivite', 'autre'))
TYPES_PAR_PARTENAIRE = {
    'ecole': frozenset(('scolaire',)),
    'association': frozenset(('associative',)),
    'collectivite': frozenset(('collectivite',)),
    'etablissement': frozenset(('scolaire', 'autre')),
    'autre': frozenset(('autre',)),
}
SUPPORTS_MODELES = frozenset(('noedoc', 'word'))
MODES_FACTURATION = frozenset(('payante', 'gratuite'))
CATEGORIES_TARIF = frozenset(('adultes', 'enfants', 'scolaires', 'autre'))
UNITES_TARIF = frozenset(('heure', 'seance', 'forfait'))
CHAMPS_BROUILLON = frozenset((
    'date_effet', 'clauses', 'support_modele', 'reference_modele', 'mode_facturation',
))
CHAMPS_PARTENAIRE_SIGNE = (
    'IDpartenaire', 'categorie', 'raison_sociale', 'nom_usage', 'siret',
    'adresse_ligne1', 'code_postal', 'commune', 'pays',
)
CHAMPS_CONVENTION_SIGNES = (
    'IDconvention_partenaire', 'IDpartenaire', 'reference', 'libelle',
    'type_convention', 'date_debut', 'date_fin',
)
CHAMPS_VERSION_SIGNES = (
    'IDversion', 'IDconvention_partenaire', 'numero_version', 'nature',
    'date_effet', 'clauses', 'support_modele', 'reference_modele',
    'mode_facturation', 'date_signature', 'signataire', 'empreinte_document_signe',
)
CHAMPS_TARIF_SIGNES = (
    'IDtarif_convention', 'categorie', 'libelle', 'unite', 'montant',
    'date_debut', 'date_fin',
)


class ConventionInvalide(PartenairesErreur):
    pass


class ConventionConflit(ConflitPartenaire):
    pass


class ConventionIntegrite(ConventionInvalide):
    pass


def _maintenant():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def _id(valeur):
    if type(valeur) is not int or valeur <= 0:
        raise ConventionInvalide('Identifiant entier positif obligatoire')
    return valeur


def _texte(valeur, nom, limite=255, *, obligatoire=True):
    if not isinstance(valeur, str):
        raise ConventionInvalide('%s doit etre un texte' % nom)
    contenu = valeur.strip()
    if obligatoire and not contenu:
        raise ConventionInvalide('%s obligatoire' % nom)
    if len(contenu) > limite:
        raise ConventionInvalide('%s trop long' % nom)
    return contenu


def _date(valeur, nom):
    if not isinstance(valeur, str):
        raise ConventionInvalide('%s : date ISO YYYY-MM-DD obligatoire' % nom)
    try:
        d = date.fromisoformat(valeur)
    except ValueError as erreur:
        raise ConventionInvalide('%s : date invalide' % nom) from erreur
    if d.isoformat() != valeur:
        raise ConventionInvalide('%s : format YYYY-MM-DD obligatoire' % nom)
    return valeur


def _iso(valeur):
    return valeur.isoformat() if isinstance(valeur, date) else str(valeur)


def _montant(valeur):
    # float non admis, y compris pour les montants deja arrondis.
    if isinstance(valeur, bool) or not isinstance(valeur, (str, int, Decimal)):
        raise ConventionInvalide('Tarif : utiliser Decimal, entier ou texte, jamais float')
    try:
        nombre = Decimal(str(valeur).strip().replace(',', '.'))
    except (InvalidOperation, ValueError):
        raise ConventionInvalide('Montant de tarif non numerique')
    if not nombre.is_finite() or nombre < 0 or nombre > Decimal('9999999999.99'):
        raise ConventionInvalide('Montant hors limites')
    if nombre != nombre.quantize(Decimal('0.01')):
        raise ConventionInvalide('Un tarif ne comporte pas plus de deux decimales')
    return format(nombre.quantize(Decimal('0.01')), '.2f')


def _json_canonique(valeur):
    return json.dumps(valeur, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _digest(valeur):
    return hashlib.sha256(_json_canonique(valeur).encode('utf-8')).hexdigest()


def _champ_date(d):
    return d.strftime('%d/%m/%Y')


class RegistreConventions:
    """Registre D2. Fournir une connexion DB-API DEDIEE et une politique fiable.

    Pour SQLite activer PRAGMA foreign_keys=ON avant l'initialisation.
    Pour MySQL fournir une connexion InnoDB avec autocommit desactive.
    ``autoriser(acteur, action)`` doit retourner exactement True.
    """

    def __init__(self, connexion, *, dialecte='sqlite', autoriser=None):
        if connexion is None or dialecte not in ('sqlite', 'mysql'):
            raise ConventionInvalide('Connexion et dialecte explicites obligatoires')
        if dialecte == 'sqlite':
            try:
                if connexion.execute('PRAGMA foreign_keys').fetchone()[0] != 1:
                    raise ConventionInvalide('SQLite : PRAGMA foreign_keys=ON obligatoire')
            except AttributeError as erreur:
                raise ConventionInvalide('Connexion SQLite invalide') from erreur
        else:
            get_auto = getattr(connexion, 'get_autocommit', None)
            if callable(get_auto) and get_auto():
                raise ConventionInvalide('MySQL : autocommit desactive obligatoire')
            if getattr(connexion, 'autocommit', False) is True:
                raise ConventionInvalide('MySQL : autocommit desactive obligatoire')
        self.connexion = connexion
        self.dialecte = dialecte
        self.param = '?' if dialecte == 'sqlite' else '%s'
        self.autoriser = autoriser

    def _droit(self, acteur, action):
        acteur = _texte(acteur, 'acteur', 100)
        if not callable(self.autoriser) or self.autoriser(acteur, action) is not True:
            raise AutorisationRefusee('Acces aux conventions partenaires non autorise')
        return acteur

    def _sql(self, requete, args=(), *, lire=False):
        curseur = self.connexion.cursor()
        try:
            curseur.execute(requete, tuple(args))
            if lire:
                noms = [desc[0] for desc in curseur.description]
                return [dict(zip(noms, ligne)) for ligne in curseur.fetchall()]
            return curseur.lastrowid
        finally:
            curseur.close()

    def _lire(self, requete, args=()):
        return self._sql(requete, args, lire=True)

    def _ecrire(self, operation):
        if self.dialecte == 'sqlite':
            # Interdit de committer une transaction de l'appelant par surprise.
            if self.connexion.in_transaction:
                raise ConventionConflit('Une connexion reservee hors transaction est necessaire')
            self.connexion.execute('BEGIN IMMEDIATE')
        try:
            valeur = operation()
            self.connexion.commit()
            return valeur
        except Exception as erreur:
            self.connexion.rollback()
            if erreur.__class__.__name__ == 'IntegrityError':
                raise ConventionConflit('Contrainte ou doublon sur le registre D2') from erreur
            raise

    def _inserer(self, table, champs):
        noms = sorted(champs)
        sql = 'INSERT INTO %s (%s) VALUES (%s)' % (
            table, ', '.join(noms), ', '.join([self.param] * len(noms)))
        return self._sql(sql, [champs[nom] for nom in noms])

    def _modifier(self, table, colonne, ident, champs):
        noms = sorted(champs)
        sql = 'UPDATE %s SET %s WHERE %s=%s' % (
            table, ', '.join('%s=%s' % (nom, self.param) for nom in noms),
            colonne, self.param)
        self._sql(sql, [champs[n] for n in noms] + [ident])

    def _unique(self, requete, args=()):
        lignes = self._lire(requete, args)
        if not lignes:
            raise Introuvable('Convention ou version introuvable')
        return lignes[0]

    def _partenaire(self, ident, *, actif=False):
        condition = " AND statut='actif'" if actif else ''
        return self._unique('SELECT * FROM partenaires_structures WHERE IDpartenaire=%s%s' % (
            self.param, condition), (_id(ident),))

    def _convention(self, ident, *, ouverte=False, verrou=False):
        suffixe = ' FOR UPDATE' if verrou and self.dialecte == 'mysql' else ''
        ligne = self._unique('SELECT * FROM partenaires_conventions '
                             'WHERE IDconvention_partenaire=%s%s' % (
                                 self.param, suffixe), (_id(ident),))
        if ouverte and ligne['etat'] != 'ouverte':
            raise ConventionInvalide('Convention cloturee : modification interdite')
        return ligne

    def _version(self, ident, *, brouillon=False):
        ligne = self._unique('SELECT * FROM partenaires_conventions_versions WHERE IDversion=%s'
                             % self.param, (_id(ident),))
        if brouillon and ligne['statut'] != 'brouillon':
            raise ConventionInvalide('Version signee : toute modification est interdite')
        return ligne

    def _tarifs(self, ident):
        lignes = self._lire('SELECT * FROM partenaires_conventions_tarifs '
                            'WHERE IDversion=%s ORDER BY categorie, libelle, unite, date_debut, IDtarif_convention'
                            % self.param, (_id(ident),))
        for ligne in lignes:
            ligne['date_debut'] = _iso(ligne['date_debut'])
            ligne['date_fin'] = _iso(ligne['date_fin'])
            ligne['montant'] = _montant(ligne['montant'])
        return lignes

    def _evenement(self, nature, ident, action, acteur, champs=''):
        self._inserer('partenaires_conventions_evenements', {
            'nature': nature, 'IDobjet': ident, 'action': action, 'acteur': acteur,
            'champs': champs, 'date_action': _maintenant(),
        })

    def creer_convention(self, IDpartenaire, reference, libelle, type_convention,
                         date_debut, date_fin, *, acteur):
        acteur = self._droit(acteur, 'creer_convention')
        reference = _texte(reference, 'reference', 100)
        libelle = _texte(libelle, 'libelle', 255)
        date_debut = _date(date_debut, 'date_debut')
        date_fin = _date(date_fin, 'date_fin')
        if date_fin < date_debut:
            raise ConventionInvalide('Fin avant debut de convention')
        if not isinstance(type_convention, str) or type_convention not in TYPES_CONVENTION:
            raise ConventionInvalide('Type de convention invalide')

        def action():
            partenaire = self._partenaire(IDpartenaire, actif=True)
            if type_convention not in TYPES_PAR_PARTENAIRE[partenaire['categorie']]:
                raise ConventionInvalide('Type de convention incompatible avec le partenaire')
            date_heure = _maintenant()
            ident = self._inserer('partenaires_conventions', dict(
                IDpartenaire=IDpartenaire, reference=reference, libelle=libelle,
                type_convention=type_convention, date_debut=date_debut,
                date_fin=date_fin, etat='ouverte', cree_le=date_heure,
                modifie_le=date_heure,
            ))
            self._evenement('convention', ident, 'creation', acteur)
            return ident
        return self._ecrire(action)

    def lister_conventions(self, IDpartenaire, *, acteur, inclure_cloturees=False):
        self._droit(acteur, 'lister_conventions')
        _id(IDpartenaire)
        if type(inclure_cloturees) is not bool:
            raise ConventionInvalide('Filtre des conventions invalide')
        suffixe = '' if inclure_cloturees else " AND etat='ouverte'"
        lignes = self._lire('SELECT * FROM partenaires_conventions WHERE IDpartenaire=%s%s '
                            'ORDER BY date_debut, IDconvention_partenaire' % (self.param, suffixe),
                            (IDpartenaire,))
        for ligne in lignes:
            ligne['date_debut'], ligne['date_fin'] = _iso(ligne['date_debut']), _iso(ligne['date_fin'])
        return lignes

    def _contenu_brouillon(self, champs):
        if not isinstance(champs, dict) or set(champs) - CHAMPS_BROUILLON or not champs:
            raise ConventionInvalide('Champs de brouillon invalides')
        valeurs = {}
        for nom, valeur in champs.items():
            if nom == 'date_effet':
                valeurs[nom] = _date(valeur, nom)
            elif nom == 'clauses':
                valeurs[nom] = _texte(valeur, nom, 20000, obligatoire=False)
            elif nom == 'reference_modele':
                valeurs[nom] = _texte(valeur, nom, 200)
            elif nom == 'support_modele':
                if not isinstance(valeur, str) or valeur not in SUPPORTS_MODELES:
                    raise ConventionInvalide('Support Noedoc ou Word obligatoire')
                valeurs[nom] = valeur
            elif nom == 'mode_facturation':
                if not isinstance(valeur, str) or valeur not in MODES_FACTURATION:
                    raise ConventionInvalide('Mode de facturation invalide')
                valeurs[nom] = valeur
        return valeurs

    def _date_effet_autorisee(self, convention, date_effet, precedente=None):
        date_effet = _iso(date_effet)
        if not _iso(convention['date_debut']) <= date_effet <= _iso(convention['date_fin']):
            raise ConventionInvalide('Date d effet hors periode de convention')
        if precedente is not None and date_effet <= _iso(precedente['date_effet']):
            raise ConventionConflit('Avenant effectif strictement apres la version signee precedente')

    def ouvrir_version(self, IDconvention, date_effet, clauses, support_modele,
                       reference_modele, mode_facturation, *, acteur):
        acteur = self._droit(acteur, 'ouvrir_version')
        champs = self._contenu_brouillon(dict(date_effet=date_effet, clauses=clauses,
            support_modele=support_modele, reference_modele=reference_modele,
            mode_facturation=mode_facturation))
        def action():
            convention = self._convention(IDconvention, ouverte=True, verrou=True)
            partenaire = self._partenaire(convention['IDpartenaire'], actif=True)
            if convention['type_convention'] not in TYPES_PAR_PARTENAIRE[partenaire['categorie']]:
                raise ConventionInvalide('Categorie du partenaire changee : nouvelle convention a verifier')
            dernier = self._lire('SELECT * FROM partenaires_conventions_versions '
                'WHERE IDconvention_partenaire=%s ORDER BY numero_version DESC LIMIT 1'
                % self.param, (IDconvention,))
            precedent = dernier[0] if dernier else None
            if precedent and precedent['statut'] != 'signee':
                raise ConventionConflit('Un brouillon existe deja')
            self._date_effet_autorisee(convention, champs['date_effet'], precedent)
            maintenant = _maintenant()
            ident = self._inserer('partenaires_conventions_versions', dict(
                champs, IDconvention_partenaire=IDconvention,
                numero_version=1 if precedent is None else int(precedent['numero_version']) + 1,
                nature='initiale' if precedent is None else 'avenant', statut='brouillon',
                brouillon_marker=1, date_signature=None, signataire=None,
                empreinte_document_signe=None, partenaire_snapshot=None,
                empreinte_contenu=None, cree_le=maintenant, modifie_le=maintenant,
            ))
            self._evenement('version', ident, 'ouverture', acteur)
            return ident
        return self._ecrire(action)

    def modifier_brouillon(self, IDversion, champs, *, acteur):
        acteur = self._droit(acteur, 'modifier_brouillon')
        valeurs = self._contenu_brouillon(champs)
        def action():
            version = self._version(IDversion, brouillon=True)
            convention = self._convention(version['IDconvention_partenaire'], ouverte=True, verrou=True)
            if 'date_effet' in valeurs:
                dernier = self._lire('SELECT * FROM partenaires_conventions_versions '
                    "WHERE IDconvention_partenaire=%s AND statut='signee' "
                    'ORDER BY numero_version DESC LIMIT 1' % self.param,
                    (version['IDconvention_partenaire'],))
                self._date_effet_autorisee(convention, valeurs['date_effet'],
                                           dernier[0] if dernier else None)
            prochain = dict(version, **valeurs)
            tarifs = self._tarifs(IDversion)
            if prochain['mode_facturation'] == 'gratuite' and tarifs:
                raise ConventionInvalide('Retirer les tarifs avant de passer en gratuite')
            for tarif in tarifs:
                self._valider_tarif({cle: tarif[cle] for cle in (
                    'categorie', 'libelle', 'unite', 'montant', 'date_debut', 'date_fin')},
                    prochain, convention)
            self._modifier('partenaires_conventions_versions', 'IDversion', IDversion,
                           dict(valeurs, modifie_le=_maintenant()))
            self._evenement('version', IDversion, 'modification', acteur, ','.join(sorted(valeurs)))
        return self._ecrire(action)

    def _valider_tarif(self, tarif, version, convention):
        requis = {'categorie', 'libelle', 'unite', 'montant', 'date_debut', 'date_fin'}
        if not isinstance(tarif, dict) or set(tarif) != requis:
            raise ConventionInvalide('Tarif : champs obligatoires non conformes')
        if not isinstance(tarif['categorie'], str) or tarif['categorie'] not in CATEGORIES_TARIF \
                or not isinstance(tarif['unite'], str) or tarif['unite'] not in UNITES_TARIF:
            raise ConventionInvalide('Categorie/unite de tarif invalide')
        debut = _date(tarif['date_debut'], 'tarif.date_debut')
        fin = _date(tarif['date_fin'], 'tarif.date_fin')
        if not _iso(version['date_effet']) <= debut <= fin <= _iso(convention['date_fin']):
            raise ConventionInvalide('Periode de tarif hors version ou convention')
        return dict(categorie=tarif['categorie'], libelle=_texte(tarif['libelle'], 'libelle tarif', 120),
            unite=tarif['unite'], montant=_montant(tarif['montant']),
            date_debut=debut, date_fin=fin)

    def remplacer_tarifs(self, IDversion, tarifs, *, acteur):
        acteur = self._droit(acteur, 'remplacer_tarifs')
        if not isinstance(tarifs, list) or len(tarifs) > 100:
            raise ConventionInvalide('Une liste de 0 a 100 tarifs est attendue')
        def action():
            version = self._version(IDversion, brouillon=True)
            convention = self._convention(version['IDconvention_partenaire'], ouverte=True, verrou=True)
            if version['mode_facturation'] == 'gratuite' and tarifs:
                raise ConventionInvalide('Convention gratuite : aucun tarif facturable')
            valides = [self._valider_tarif(t, version, convention) for t in tarifs]
            periodes = {}
            for t in valides:
                cle = (t['categorie'], t['libelle'].casefold(), t['unite'])
                for precedent in periodes.get(cle, []):
                    if t['date_debut'] <= precedent[1] and precedent[0] <= t['date_fin']:
                        raise ConventionConflit('Tarifs chevauchants pour la meme prestation')
                periodes.setdefault(cle, []).append((t['date_debut'], t['date_fin']))
            self._sql('DELETE FROM partenaires_conventions_tarifs WHERE IDversion=%s' % self.param,
                      (IDversion,))
            for tarif in valides:
                self._inserer('partenaires_conventions_tarifs', dict(tarif, IDversion=IDversion))
            self._evenement('tarifs', IDversion, 'remplacement', acteur, 'nombre=%d' % len(valides))
            return len(valides)
        return self._ecrire(action)

    def _contenu_signe(self, convention, version, tarifs, partenaire):
        def extrait(dico, noms):
            return {nom: _iso(dico[nom]) if isinstance(dico[nom], date) else dico[nom]
                    for nom in noms}
        return dict(
            convention=extrait(convention, CHAMPS_CONVENTION_SIGNES),
            version=extrait(version, CHAMPS_VERSION_SIGNES),
            tarifs=[extrait(t, CHAMPS_TARIF_SIGNES) for t in tarifs],
            partenaire=partenaire,
        )

    def signer_version(self, IDversion, date_signature, signataire,
                       empreinte_document_signe, *, acteur):
        acteur = self._droit(acteur, 'signer_version')
        date_signature = _date(date_signature, 'date_signature')
        signataire = _texte(signataire, 'signataire', 200)
        if not isinstance(empreinte_document_signe, str) or not re.fullmatch(
                '[0-9a-f]{64}', empreinte_document_signe):
            raise ConventionInvalide('Empreinte SHA256 du document signe obligatoire')

        def action():
            version = self._version(IDversion, brouillon=True)
            convention = self._convention(version['IDconvention_partenaire'], ouverte=True, verrou=True)
            partenaire = self._partenaire(convention['IDpartenaire'], actif=True)
            if convention['type_convention'] not in TYPES_PAR_PARTENAIRE[partenaire['categorie']]:
                raise ConventionInvalide('Categorie du partenaire incompatible avec la convention')
            if not version['clauses'].strip():
                raise ConventionInvalide('Clauses non renseignees')
            tarifs = self._tarifs(IDversion)
            for tarif in tarifs:
                self._valider_tarif({cle: tarif[cle] for cle in (
                    'categorie', 'libelle', 'unite', 'montant', 'date_debut', 'date_fin')},
                    version, convention)
            if version['mode_facturation'] == 'payante':
                if not tarifs or not any(Decimal(t['montant']) > 0 for t in tarifs):
                    raise ConventionInvalide('Convention payante : tarif positif obligatoire')
            elif tarifs:
                raise ConventionInvalide('Convention gratuite : tarifs incompatibles')
            precedent = self._lire('SELECT date_effet FROM partenaires_conventions_versions '
                "WHERE IDconvention_partenaire=%s AND statut='signee' "
                'ORDER BY numero_version DESC LIMIT 1' % self.param,
                (version['IDconvention_partenaire'],))
            self._date_effet_autorisee(convention, version['date_effet'],
                                      precedent[0] if precedent else None)
            identite = {nom: partenaire[nom] for nom in CHAMPS_PARTENAIRE_SIGNE}
            snapshot = _json_canonique(identite)
            now = _maintenant()
            champs_signature = dict(statut='signee', brouillon_marker=None,
                date_signature=date_signature, signataire=signataire,
                empreinte_document_signe=empreinte_document_signe,
                partenaire_snapshot=snapshot, modifie_le=now)
            version_signee = dict(version, **champs_signature)
            empreinte_contenu = _digest(self._contenu_signe(
                convention, version_signee, tarifs, identite))
            self._modifier('partenaires_conventions_versions', 'IDversion', IDversion,
                dict(champs_signature, empreinte_contenu=empreinte_contenu))
            self._evenement('version', IDversion, 'signature_declaree', acteur)
            return empreinte_contenu
        return self._ecrire(action)

    def _obtenir_version(self, IDversion):
        version = self._version(IDversion)
        convention = self._convention(version['IDconvention_partenaire'])
        tarifs = self._tarifs(IDversion)
        for champ in ('date_effet', 'date_signature'):
            if version[champ] is not None:
                version[champ] = _iso(version[champ])
        for champ in ('date_debut', 'date_fin'):
            convention[champ] = _iso(convention[champ])
        if version['statut'] == 'signee':
            try:
                partenaire = json.loads(version['partenaire_snapshot'])
                empreinte = _digest(self._contenu_signe(convention, version, tarifs, partenaire))
            except (TypeError, ValueError, KeyError) as erreur:
                raise ConventionIntegrite('Instantane signe illisible') from erreur
            if empreinte != version['empreinte_contenu']:
                raise ConventionIntegrite('Modification detectee dans une version signee')
        else:
            structure = self._partenaire(convention['IDpartenaire'])
            partenaire = {nom: structure[nom] for nom in CHAMPS_PARTENAIRE_SIGNE}
        return {'convention': convention, 'version': version,
                'tarifs': tarifs, 'partenaire': partenaire}

    def obtenir_version(self, IDversion, *, acteur):
        self._droit(acteur, 'obtenir_version')
        return self._obtenir_version(IDversion)

    def lister_versions(self, IDconvention, *, acteur):
        self._droit(acteur, 'lister_versions')
        _id(IDconvention)
        versions = self._lire('SELECT IDversion FROM partenaires_conventions_versions '
            'WHERE IDconvention_partenaire=%s ORDER BY numero_version' % self.param,
            (IDconvention,))
        # Controle d'integrite de chaque version signee, pas de raccourci.
        return [self._obtenir_version(v['IDversion']) for v in versions]

    def tarifs_applicables(self, IDconvention, jour, *, acteur, categorie=None):
        self._droit(acteur, 'tarifs_applicables')
        jour = _date(jour, 'date_intervention')
        if categorie is not None and (not isinstance(categorie, str) or categorie not in CATEGORIES_TARIF):
            raise ConventionInvalide('Categorie de tarif invalide')
        convention = self._convention(IDconvention)
        if not _iso(convention['date_debut']) <= jour <= _iso(convention['date_fin']):
            raise ConventionInvalide('Date hors periode contractuelle')
        versions = self._lire('SELECT IDversion FROM partenaires_conventions_versions '
            "WHERE IDconvention_partenaire=%s AND statut='signee' AND date_effet<=%s "
            'ORDER BY date_effet DESC, numero_version DESC LIMIT 1' % (self.param, self.param),
            (IDconvention, jour))
        if not versions:
            raise ConventionInvalide('Aucune version signee applicable')
        donnees = self._obtenir_version(versions[0]['IDversion'])
        tarifs = [t for t in donnees['tarifs']
            if t['date_debut'] <= jour <= t['date_fin']
            and (categorie is None or t['categorie'] == categorie)]
        if donnees['version']['mode_facturation'] == 'payante' and not tarifs:
            raise ConventionInvalide('Aucun tarif conventionnel explicite a cette date')
        return {'IDversion': donnees['version']['IDversion'],
                'numero_version': donnees['version']['numero_version'],
                'mode_facturation': donnees['version']['mode_facturation'],
                'tarifs': tarifs}

    def preparer_export(self, IDversion, *, acteur):
        """Instantane documentaire sans lancer Noedoc ni reecrire la fiche Famille.

        Une version en brouillon peut etre previsualisee mais reste marquee
        BROUILLON. Le raccordement au generateur UI est un lot separe.
        """
        self._droit(acteur, 'preparer_export')
        donnees = self._obtenir_version(IDversion)
        convention, version = donnees['convention'], donnees['version']
        tarifs = donnees['tarifs']
        nom = donnees['partenaire']['raison_sociale']
        def tarif_unique(categorie=None):
            # Un seul tarif ne suffit pas s'il ne couvre qu'une partie de
            # la saison : le modele ne doit pas afficher un prix trompeur.
            candidats = [t for t in tarifs if t['unite'] == 'heure'
                         and (categorie is None or t['categorie'] == categorie)]
            if len(candidats) != 1:
                return ''
            t = candidats[0]
            if t['date_debut'] > version['date_effet'] or t['date_fin'] < convention['date_fin']:
                return ''
            return t['montant']
        debut_annee, fin_annee = convention['date_debut'][:4], convention['date_fin'][:4]
        periode = debut_annee if debut_annee == fin_annee else '%s-%s' % (debut_annee, fin_annee)
        adresse = ', '.join(filter(None, (donnees['partenaire'].get('adresse_ligne1'),
            ' '.join(filter(None, (donnees['partenaire'].get('code_postal'),
                                   donnees['partenaire'].get('commune')))).strip())))
        champs = {
            '{CONVENTION_SAISON}': periode,
            '{CONVENTION_DATE_DEBUT}': _champ_date(date.fromisoformat(convention['date_debut'])),
            '{CONVENTION_DATE_FIN}': _champ_date(date.fromisoformat(convention['date_fin'])),
            '{CONVENTION_TARIF_HORAIRE}': tarif_unique(),
            '{CONVENTION_TARIF_ADULTE}': tarif_unique('adultes'),
            '{CONVENTION_TARIF_ENFANT}': tarif_unique('enfants'),
            '{CONVENTION_ADRESSE_STRUCTURE}': adresse,
            # Aucun planning ou representant n'est invente dans D2.
            '{CONVENTION_LIEU_INTERVENTION}': '',
            '{CONVENTION_REPRESENTANT_NOM_COMPLET}': '',
        }
        return {'etat': version['statut'], 'identite_partenaire': nom,
                'type_convention': convention['type_convention'],
                'support_modele': version['support_modele'],
                'reference_modele': version['reference_modele'],
                'clauses': version['clauses'], 'tarifs': tarifs,
                'champs_compatibles': champs,
                'document_signe_sha256': version['empreinte_document_signe'],
                'instantane_sha256': version['empreinte_contenu']}

    def cloturer_convention(self, IDconvention, *, acteur):
        acteur = self._droit(acteur, 'cloturer_convention')
        def action():
            convention = self._convention(IDconvention, ouverte=True, verrou=True)
            brouillons = self._lire('SELECT IDversion FROM partenaires_conventions_versions '
                'WHERE IDconvention_partenaire=%s AND brouillon_marker=1' % self.param,
                (IDconvention,))
            if brouillons:
                raise ConventionConflit('Signer ou annuler le brouillon avant cloture')
            self._modifier('partenaires_conventions', 'IDconvention_partenaire', IDconvention,
                           dict(etat='cloturee', modifie_le=_maintenant()))
            self._evenement('convention', IDconvention, 'cloture', acteur)
        return self._ecrire(action)

    def lister_evenements(self, *, acteur, nature=None, IDobjet=None):
        self._droit(acteur, 'lister_evenements')
        if nature is not None and nature not in ('convention', 'version', 'tarifs'):
            raise ConventionInvalide('Nature d evenement invalide')
        clauses, args = [], []
        if nature is not None:
            clauses.append('nature=%s' % self.param)
            args.append(nature)
        if IDobjet is not None:
            clauses.append('IDobjet=%s' % self.param)
            args.append(_id(IDobjet))
        suite = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
        return self._lire('SELECT * FROM partenaires_conventions_evenements%s ORDER BY IDevenement'
                          % suite, args)
