# -*- coding: utf-8 -*-
"""Lot D3-D4 : programmation et constat d'interventions des partenaires.

Aucun acces implicite a GestionDB, aucune migration ni facture. La connexion
DB-API est fournie et reservee a ce moteur. Les calendriers sont saisis et
valides explicitement : vacances, jours feries et exceptions ne sont JAMAIS
inventes. Une intervention prevue ne devient jamais realisee ou facturable
sans decisions humaines separees. Les versions D2 doivent etre signees.
"""

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import re

from Utils.UTILS_Partenaires_D1 import AutorisationRefusee, Introuvable, PartenairesErreur
from Utils.UTILS_Partenaires_D2 import (
    RegistreConventions, CATEGORIES_TARIF, ConventionIntegrite,
)

EXCLUSIONS = frozenset(('vacances', 'ferie', 'fermeture', 'autre'))
ORIGINES_ANNULATION = frozenset(('partenaire', 'educateur', 'organisation', 'autre'))
DECISIONS = frozenset(('a_arbitrer', 'eligible', 'non_facturable'))
MAX_SEANCES = 3000


class PlanningInvalide(PartenairesErreur):
    pass


class PlanningConflit(PlanningInvalide):
    pass


def _id(valeur):
    if type(valeur) is not int or valeur < 1:
        raise PlanningInvalide('Identifiant entier strictement positif obligatoire')
    return valeur


def _texte(valeur, champ, taille=255, *, requis=True):
    if not isinstance(valeur, str):
        if valeur is None and not requis:
            return None
        raise PlanningInvalide('%s : texte attendu' % champ)
    valeur = valeur.strip()
    if len(valeur) > taille or (requis and not valeur):
        raise PlanningInvalide('%s : valeur absente ou trop longue' % champ)
    return valeur or None


def _date(valeur):
    if not isinstance(valeur, str):
        raise PlanningInvalide('Date ISO YYYY-MM-DD obligatoire')
    try:
        parsed = date.fromisoformat(valeur)
    except ValueError as erreur:
        raise PlanningInvalide('Date ISO invalide') from erreur
    if parsed.isoformat() != valeur:
        raise PlanningInvalide('Date non canonique')
    return parsed


def _iso(valeur):
    return valeur.isoformat() if isinstance(valeur, date) else str(valeur)


def _horaire(valeur):
    if not isinstance(valeur, str) or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', valeur):
        raise PlanningInvalide('Horaire HH:MM entre 00:00 et 23:59 attendu')
    return int(valeur[:2]) * 60 + int(valeur[3:])


def _duree(debut, fin):
    minutes = _horaire(fin) - _horaire(debut)
    if minutes < 1 or minutes > 12 * 60:
        raise PlanningInvalide('Horaire non croissant ou duree superieure a 12 heures')
    return minutes


def _maintenant():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def _empreinte(objet):
    texte = json.dumps(objet, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return sha256(texte.encode('utf-8')).hexdigest()


def _chevauchent(a, b):
    return a['date_prevue'] == b['date_prevue'] and (
        _horaire(a['heure_debut_prevue']) < _horaire(b['heure_fin_prevue'])
        and _horaire(b['heure_debut_prevue']) < _horaire(a['heure_fin_prevue'])
    )


class InterventionsPartenaires:
    """API D3-D4. ``autoriser(acteur, operation) is True`` pour chaque appel.

    SQLite : PRAGMA foreign_keys=ON. MySQL : connexion InnoDB dediee,
    autocommit desactive, aucun test sur la production. Les operations
    d'ecriture sont transactionnelles et refusent une transaction SQLite
    etrangere deja ouverte.
    """

    def __init__(self, connexion, *, dialecte='sqlite', autoriser=None):
        if connexion is None or dialecte not in ('sqlite', 'mysql'):
            raise PlanningInvalide('Connexion DB-API et dialecte explicites requis')
        # Le controle de session est identique au registre D2.
        self.registre = RegistreConventions(connexion, dialecte=dialecte, autoriser=autoriser)
        self.connexion = connexion
        self.dialecte = dialecte
        self.param = '?' if dialecte == 'sqlite' else '%s'
        self.autoriser = autoriser

    def _droit(self, acteur, operation):
        acteur = _texte(acteur, 'acteur', 100)
        if not callable(self.autoriser) or self.autoriser(acteur, operation) is not True:
            raise AutorisationRefusee('D3-D4 : acces non autorise')
        return acteur

    def _sql(self, requete, parametres=(), *, lecture=False):
        curseur = self.connexion.cursor()
        try:
            curseur.execute(requete, tuple(parametres))
            if lecture:
                return [dict(zip((c[0] for c in curseur.description), ligne))
                        for ligne in curseur.fetchall()]
            return curseur.lastrowid
        finally:
            curseur.close()

    def _lire(self, requete, parametres=()):
        return self._sql(requete, parametres, lecture=True)

    def _unique(self, requete, parametres=()):
        lignes = self._lire(requete, parametres)
        if not lignes:
            raise Introuvable('Planning, creneau ou intervention absent')
        return lignes[0]

    def _ecrire(self, fonction):
        if self.dialecte == 'sqlite':
            if self.connexion.in_transaction:
                raise PlanningConflit('Transaction externe deja en cours')
            self.connexion.execute('BEGIN IMMEDIATE')
        try:
            resultat = fonction()
            self.connexion.commit()
            return resultat
        except Exception as erreur:
            self.connexion.rollback()
            if erreur.__class__.__name__ == 'IntegrityError':
                raise PlanningConflit('Doublon ou contrainte d integrite D3-D4') from erreur
            raise

    def _inserer(self, table, valeurs):
        cles = sorted(valeurs)
        return self._sql('INSERT INTO %s (%s) VALUES (%s)' % (
            table, ', '.join(cles), ', '.join([self.param] * len(cles))),
            [valeurs[cle] for cle in cles])

    def _modifier(self, table, id_colonne, identifiant, valeurs):
        cles = sorted(valeurs)
        return self._sql('UPDATE %s SET %s WHERE %s=%s' % (
            table, ', '.join('%s=%s' % (cle, self.param) for cle in cles), id_colonne, self.param),
            [valeurs[cle] for cle in cles] + [identifiant])

    def _evenement(self, nature, identifiant, action, acteur):
        self._inserer('partenaires_plan_evenements', {
            'nature': nature, 'IDobjet': identifiant, 'action': action,
            'acteur': acteur, 'date_action': _maintenant(), 'champs': '',
        })

    def _historique(self, ligne, action, acteur, motif, *, nouvelles, reference_ecrite=None):
        ancien = {'etat': ligne['etat'], 'date_prevue': _iso(ligne['date_prevue']),
                  'heure_debut_prevue': ligne['heure_debut_prevue'],
                  'heure_fin_prevue': ligne['heure_fin_prevue'],
                  'intervenant_reel': ligne['intervenant_reel'],
                  'decision_facturation': ligne['decision_facturation']}
        actuel = dict(ancien, **nouvelles)
        self._inserer('partenaires_interventions_historique', {
            'IDintervention': ligne['IDintervention'], 'action': action,
            'ancien_etat': ancien['etat'], 'nouvel_etat': actuel['etat'],
            'date_precedente': ancien['date_prevue'], 'date_suivante': actuel['date_prevue'],
            'horaire_precedent': '%s-%s' % (ancien['heure_debut_prevue'], ancien['heure_fin_prevue']),
            'horaire_suivant': '%s-%s' % (actuel['heure_debut_prevue'], actuel['heure_fin_prevue']),
            'intervenant_precedent': ancien['intervenant_reel'],
            'intervenant_suivant': actuel['intervenant_reel'],
            'decision_precedente': ancien['decision_facturation'],
            'decision_suivante': actuel['decision_facturation'],
            'motif': motif, 'acteur': acteur, 'date_action': _maintenant(),
            'reference_ecrite': reference_ecrite,
        })

    def _programme(self, identifiant, *, brouillon=False, verrou=False):
        suffixe = ' FOR UPDATE' if verrou and self.dialecte == 'mysql' else ''
        ligne = self._unique('SELECT * FROM partenaires_programmations WHERE IDprogrammation=%s%s'
                             % (self.param, suffixe), (_id(identifiant),))
        if brouillon and ligne['etat'] != 'brouillon':
            raise PlanningConflit('Programmation validee : calendrier immuable')
        for champ in ('date_debut', 'date_fin'):
            ligne[champ] = _iso(ligne[champ])
        return ligne

    def _creneau(self, identifiant):
        ligne = self._unique('SELECT * FROM partenaires_creneaux WHERE IDcreneau=%s'
                             % self.param, (_id(identifiant),))
        for champ in ('date_debut', 'date_fin'):
            ligne[champ] = _iso(ligne[champ])
        return ligne

    def _intervention(self, identifiant, *, verrou=False):
        suffixe = ' FOR UPDATE' if verrou and self.dialecte == 'mysql' else ''
        ligne = self._unique('SELECT * FROM partenaires_interventions WHERE IDintervention=%s%s'
                             % (self.param, suffixe), (_id(identifiant),))
        for champ in ('date_origine', 'date_prevue', 'date_reelle'):
            if ligne[champ] is not None:
                ligne[champ] = _iso(ligne[champ])
        return ligne

    def _version_applicable(self, IDversion, debut, fin, *, exiger_ouverte):
        donnees = self.registre._obtenir_version(_id(IDversion))
        version, convention = donnees['version'], donnees['convention']
        if version['statut'] != 'signee':
            raise PlanningInvalide('Une version contractuelle signee est obligatoire')
        if exiger_ouverte and convention['etat'] != 'ouverte':
            raise PlanningInvalide('Convention cloturee : nouveau planning interdit')
        debut, fin = _date(debut).isoformat(), _date(fin).isoformat()
        if not (convention['date_debut'] <= debut <= fin <= convention['date_fin']
                and version['date_effet'] <= debut):
            raise PlanningInvalide('Planning hors periode de la version signee')
        autres = self._lire('SELECT date_effet FROM partenaires_conventions_versions '
                            "WHERE IDconvention_partenaire=%s AND statut='signee' AND date_effet>%s "
                            'ORDER BY date_effet ASC LIMIT 1' % (self.param, self.param),
                            (convention['IDconvention_partenaire'], version['date_effet']))
        if autres and fin >= _iso(autres[0]['date_effet']):
            raise PlanningInvalide('Avenant applicable : scinder le planning par version')
        return donnees

    def creer_programmation(self, IDversion, reference, libelle, date_debut, date_fin, *, acteur):
        acteur = self._droit(acteur, 'creer_programmation')
        reference = _texte(reference, 'reference', 100)
        libelle = _texte(libelle, 'libelle', 255)
        debut, fin = _date(date_debut), _date(date_fin)
        if fin < debut or (fin - debut).days > 3 * 366:
            raise PlanningInvalide('Plage du planning invalide ou superieure a trois ans')
        def action():
            self._version_applicable(IDversion, date_debut, date_fin, exiger_ouverte=True)
            maintenant = _maintenant()
            identifiant = self._inserer('partenaires_programmations', {
                'IDversion': IDversion, 'reference': reference, 'libelle': libelle,
                'date_debut': date_debut, 'date_fin': date_fin,
                'etat': 'brouillon', 'empreinte_calendrier': None,
                'valide_par': None, 'valide_le': None,
                'cree_le': maintenant, 'modifie_le': maintenant,
            })
            self._evenement('programmation', identifiant, 'creation', acteur)
            return identifiant
        return self._ecrire(action)

    def ajouter_creneau(self, IDprogrammation, recurrence, date_debut, date_fin,
                        heure_debut, heure_fin, groupe, activite, categorie_tarif,
                        *, acteur, jour_semaine=None, lieu=None, intervenant=None):
        acteur = self._droit(acteur, 'ajouter_creneau')
        debut, fin = _date(date_debut), _date(date_fin)
        _duree(heure_debut, heure_fin)
        if recurrence not in ('hebdomadaire', 'ponctuel'):
            raise PlanningInvalide('Recurrence hebdomadaire ou ponctuelle obligatoire')
        if recurrence == 'hebdomadaire':
            if type(jour_semaine) is not int or jour_semaine not in range(7):
                raise PlanningInvalide('Jour de semaine obligatoire : 0=lundi a 6=dimanche')
        elif jour_semaine is not None or debut != fin:
            raise PlanningInvalide('Une seance ponctuelle correspond a une date unique')
        if fin < debut or categorie_tarif not in CATEGORIES_TARIF:
            raise PlanningInvalide('Plage ou categorie tarifaire invalide')
        groupe = _texte(groupe, 'groupe', 120)
        activite = _texte(activite, 'activite', 160)
        lieu = _texte(lieu, 'lieu', 200, requis=False)
        intervenant = _texte(intervenant, 'intervenant', 160, requis=False)

        def action():
            programme = self._programme(IDprogrammation, brouillon=True, verrou=True)
            if not programme['date_debut'] <= date_debut <= date_fin <= programme['date_fin']:
                raise PlanningInvalide('Creneau hors dates du planning')
            ident = self._inserer('partenaires_creneaux', {
                'IDprogrammation': IDprogrammation, 'recurrence': recurrence,
                'jour_semaine': jour_semaine, 'date_debut': date_debut,
                'date_fin': date_fin, 'heure_debut': heure_debut, 'heure_fin': heure_fin,
                'groupe': groupe, 'activite': activite, 'lieu': lieu,
                'intervenant': intervenant, 'categorie_tarif': categorie_tarif,
            })
            self._evenement('creneau', ident, 'creation', acteur)
            return ident
        return self._ecrire(action)

    def ajouter_exclusion(self, IDprogrammation, date_debut, date_fin, categorie, motif, *, acteur):
        acteur = self._droit(acteur, 'ajouter_exclusion')
        debut, fin = _date(date_debut), _date(date_fin)
        if fin < debut or categorie not in EXCLUSIONS:
            raise PlanningInvalide('Exclusion ou periode invalide')
        motif = _texte(motif, 'motif exclusion', 500)
        def action():
            programme = self._programme(IDprogrammation, brouillon=True, verrou=True)
            if not programme['date_debut'] <= date_debut <= date_fin <= programme['date_fin']:
                raise PlanningInvalide('Exclusion hors calendrier')
            existantes = self._lire('SELECT date_debut,date_fin FROM partenaires_exclusions '
                                    'WHERE IDprogrammation=%s' % self.param, (IDprogrammation,))
            if any(date_debut <= _iso(x['date_fin']) and _iso(x['date_debut']) <= date_fin
                   for x in existantes):
                raise PlanningConflit('Deux exclusions de calendrier se chevauchent')
            ident = self._inserer('partenaires_exclusions', {
                'IDprogrammation': IDprogrammation, 'date_debut': date_debut,
                'date_fin': date_fin, 'categorie': categorie, 'motif': motif,
            })
            self._evenement('exclusion', ident, 'creation', acteur)
            return ident
        return self._ecrire(action)

    def _dates_creneau(self, creneau):
        debut = _date(creneau['date_debut'])
        fin = _date(creneau['date_fin'])
        if creneau['recurrence'] == 'ponctuel':
            return [debut]
        offset = (int(creneau['jour_semaine']) - debut.weekday()) % 7
        premier = debut + timedelta(days=offset)
        dates = []
        jour = premier
        while jour <= fin:
            dates.append(jour)
            if len(dates) > MAX_SEANCES:
                raise PlanningInvalide('Trop de seances dans un creneau')
            jour += timedelta(days=7)
        return dates

    def ajouter_exception(self, IDcreneau, date_origine, nature, motif, *, acteur,
                          date_remplacement=None, heure_debut=None, heure_fin=None, lieu=None):
        acteur = self._droit(acteur, 'ajouter_exception')
        _date(date_origine)
        if nature not in ('supprimer', 'deplacer'):
            raise PlanningInvalide('Exception : supprimer ou deplacer')
        motif = _texte(motif, 'motif exception', 500)
        if nature == 'supprimer':
            if any(val is not None for val in (date_remplacement, heure_debut, heure_fin, lieu)):
                raise PlanningInvalide('Suppression : aucune date/horaire de remplacement')
        else:
            _date(date_remplacement)
            _duree(heure_debut, heure_fin)
        lieu = _texte(lieu, 'lieu', 200, requis=False)

        def action():
            creneau = self._creneau(IDcreneau)
            programme = self._programme(creneau['IDprogrammation'], brouillon=True, verrou=True)
            if date_origine not in {jour.isoformat() for jour in self._dates_creneau(creneau)}:
                raise PlanningInvalide('Date originale sans occurrence de ce creneau')
            if nature == 'deplacer':
                self._version_applicable(programme['IDversion'], date_remplacement,
                                         date_remplacement, exiger_ouverte=True)
                if not programme['date_debut'] <= date_remplacement <= programme['date_fin']:
                    raise PlanningInvalide('Exception hors planning : utiliser un creneau ponctuel motive')
            ident = self._inserer('partenaires_exceptions', {
                'IDcreneau': IDcreneau, 'date_origine': date_origine,
                'nature': nature, 'date_remplacement': date_remplacement,
                'heure_debut': heure_debut, 'heure_fin': heure_fin,
                'lieu': lieu, 'motif': motif,
            })
            self._evenement('exception', ident, 'creation', acteur)
            return ident
        return self._ecrire(action)

    def _calendrier(self, programme):
        ident = programme['IDprogrammation']
        creneaux = self._lire('SELECT * FROM partenaires_creneaux WHERE IDprogrammation=%s '
                             'ORDER BY IDcreneau' % self.param, (ident,))
        exclusions = self._lire('SELECT * FROM partenaires_exclusions WHERE IDprogrammation=%s '
                               'ORDER BY date_debut,IDexclusion' % self.param, (ident,))
        exceptions = self._lire('SELECT e.* FROM partenaires_exceptions e '
                                'JOIN partenaires_creneaux c ON e.IDcreneau=c.IDcreneau '
                                'WHERE c.IDprogrammation=%s ORDER BY e.IDexception'
                                % self.param, (ident,))
        regles = {(e['IDcreneau'], _iso(e['date_origine'])): e for e in exceptions}
        lignes, retraits = [], []
        for c in creneaux:
            for jour in self._dates_creneau(c):
                origine = jour.isoformat()
                exception = regles.get((c['IDcreneau'], origine))
                if exception and exception['nature'] == 'supprimer':
                    retraits.append({'IDcreneau': c['IDcreneau'], 'date_origine': origine,
                                     'raison': 'exception', 'motif': exception['motif']})
                    continue
                if exception and exception['nature'] == 'deplacer':
                    date_prevue = _iso(exception['date_remplacement'])
                    heure_debut, heure_fin = exception['heure_debut'], exception['heure_fin']
                    lieu = exception['lieu'] if exception['lieu'] is not None else c['lieu']
                else:
                    date_prevue = origine
                    heure_debut, heure_fin, lieu = c['heure_debut'], c['heure_fin'], c['lieu']
                    exclu = next((exc for exc in exclusions if _iso(exc['date_debut']) <= origine
                                 <= _iso(exc['date_fin'])), None)
                    if exclu:
                        retraits.append({'IDcreneau': c['IDcreneau'], 'date_origine': origine,
                                         'raison': exclu['categorie'], 'motif': exclu['motif']})
                        continue
                # Une exception de deplacement peut sortir d'une semaine de vacances,
                # mais jamais tomber sur un jour exclu sans arbitrage explicite.
                if exception and exception['nature'] == 'deplacer':
                    exclu_dest = next((exc for exc in exclusions if _iso(exc['date_debut']) <= date_prevue
                                      <= _iso(exc['date_fin'])), None)
                    if exclu_dest:
                        raise PlanningConflit('Deplacement vers une date exclue : refus')
                lignes.append({
                    'IDprogrammation': ident, 'IDversion': programme['IDversion'],
                    'IDcreneau': c['IDcreneau'], 'date_origine': origine,
                    'date_prevue': date_prevue,
                    'heure_debut_prevue': heure_debut, 'heure_fin_prevue': heure_fin,
                    'minutes_prevues': _duree(heure_debut, heure_fin),
                    'groupe': c['groupe'], 'activite': c['activite'],
                    'lieu_prevu': lieu, 'intervenant_prevu': c['intervenant'],
                    'categorie_tarif': c['categorie_tarif'],
                })
                if len(lignes) + len(retraits) > MAX_SEANCES:
                    raise PlanningInvalide('Plus de %d seances : scinder la programmation' % MAX_SEANCES)
        lignes.sort(key=lambda r: (r['date_prevue'], r['heure_debut_prevue'], r['groupe'],
                                   r['IDcreneau'], r['date_origine']))
        for pos, ligne in enumerate(lignes):
            for autre in lignes[pos + 1:]:
                if autre['date_prevue'] != ligne['date_prevue']:
                    break
                if _chevauchent(ligne, autre) and (
                    ligne['groupe'] == autre['groupe'] or (
                        ligne['intervenant_prevu'] and ligne['intervenant_prevu'] == autre['intervenant_prevu']
                    )
                ):
                    raise PlanningConflit('Chevauchement groupe ou intervenant dans le calendrier')
        return {'seances': lignes, 'exclusions': retraits,
                'total_minutes': sum(x['minutes_prevues'] for x in lignes)}

    def apercu_programmation(self, IDprogrammation, *, acteur):
        self._droit(acteur, 'apercu_programmation')
        programme = self._programme(IDprogrammation)
        self._version_applicable(programme['IDversion'], programme['date_debut'],
                                 programme['date_fin'], exiger_ouverte=False)
        preview = self._calendrier(programme)
        if programme['etat'] == 'validee' and _empreinte(preview) != programme['empreinte_calendrier']:
            raise PlanningConflit('Calendrier valide modifie hors API')
        return preview

    def valider_programmation(self, IDprogrammation, *, acteur):
        acteur = self._droit(acteur, 'valider_programmation')
        def action():
            programme = self._programme(IDprogrammation, verrou=True)
            self._version_applicable(programme['IDversion'], programme['date_debut'],
                                     programme['date_fin'], exiger_ouverte=True)
            preview = self._calendrier(programme)
            empreinte = _empreinte(preview)
            if programme['etat'] == 'validee':
                if empreinte != programme['empreinte_calendrier']:
                    raise PlanningConflit('Planning valide modifie hors API')
                return {'nombre_seances': len(preview['seances']), 'empreinte': empreinte,
                        'deja_validee': True}
            if not preview['seances']:
                raise PlanningInvalide('Impossible de valider un planning sans intervention')
            maintenant = _maintenant()
            for ligne in preview['seances']:
                self._inserer('partenaires_interventions', dict(
                    ligne, minutes_initiales=ligne['minutes_prevues'], date_reelle=None, heure_debut_reelle=None, heure_fin_reelle=None,
                    minutes_reelles=None, lieu_reel=None, intervenant_reel=None,
                    etat='prevue', decision_facturation='a_arbitrer',
                    origine_annulation=None, justification_annulation=None,
                    motif=None, valide_par=None, valide_le=None,
                    cree_le=maintenant, modifie_le=maintenant))
            self._modifier('partenaires_programmations', 'IDprogrammation', IDprogrammation, {
                'etat': 'validee', 'empreinte_calendrier': empreinte,
                'valide_par': acteur, 'valide_le': maintenant, 'modifie_le': maintenant,
            })
            self._evenement('programmation', IDprogrammation, 'validation', acteur)
            return {'nombre_seances': len(preview['seances']), 'empreinte': empreinte,
                    'deja_validee': False}
        return self._ecrire(action)

    def preparer_annexe(self, IDprogrammation, *, acteur):
        """Donnees pures du calendrier VALIDE a fournir plus tard a Noedoc/Word.

        Aucun fichier signe / aucune ecriture dans Noethys. Les modifications
        ulterieures des interventions n'ecrasent jamais l'annexe initiale.
        """
        self._droit(acteur, 'preparer_annexe')
        programme = self._programme(IDprogrammation)
        if programme['etat'] != 'validee':
            raise PlanningInvalide('Annexe contractuelle : planning non valide')
        self._version_applicable(programme['IDversion'], programme['date_debut'],
                                 programme['date_fin'], exiger_ouverte=False)
        calendrier = self._calendrier(programme)
        if _empreinte(calendrier) != programme['empreinte_calendrier']:
            raise PlanningConflit('Annexe : empreinte de calendrier modifiee')
        return {
            'IDprogrammation': IDprogrammation, 'IDversion': programme['IDversion'],
            'reference': programme['reference'], 'libelle': programme['libelle'],
            'date_debut': programme['date_debut'], 'date_fin': programme['date_fin'],
            'etat': 'previsionnel_valide', 'nombre': len(calendrier['seances']),
            'minutes': calendrier['total_minutes'], 'lignes': calendrier['seances'],
            'exclusions': calendrier['exclusions'],
            'empreinte': programme['empreinte_calendrier'],
            'document_genere': False, 'signature_partenaire_verifiee': False,
        }

    def lister_interventions(self, IDprogrammation, *, acteur):
        self._droit(acteur, 'lister_interventions')
        self._programme(IDprogrammation)
        lignes = self._lire('SELECT * FROM partenaires_interventions WHERE IDprogrammation=%s '
                            'ORDER BY date_prevue,heure_debut_prevue,IDintervention'
                            % self.param, (IDprogrammation,))
        for ligne in lignes:
            for champ in ('date_origine', 'date_prevue', 'date_reelle'):
                if ligne[champ] is not None:
                    ligne[champ] = _iso(ligne[champ])
        return lignes

    def _intervention_editable(self, IDintervention, *, verrou=True):
        ligne = self._intervention(IDintervention, verrou=verrou)
        programme = self._programme(ligne['IDprogrammation'], verrou=verrou)
        if programme['etat'] != 'validee':
            raise PlanningInvalide('Intervention issue de programmation non validee')
        self._version_applicable(ligne['IDversion'], ligne['date_prevue'],
                                 ligne['date_prevue'], exiger_ouverte=False)
        return ligne, programme

    def reporter_intervention(self, IDintervention, date_prevue, heure_debut,
                              heure_fin, motif, *, acteur, lieu=None, reference_ecrite=None):
        acteur = self._droit(acteur, 'reporter_intervention')
        _date(date_prevue)
        _duree(heure_debut, heure_fin)
        motif = _texte(motif, 'motif report', 500)
        lieu = _texte(lieu, 'lieu', 200, requis=False)
        reference_ecrite = _texte(reference_ecrite, 'reference ecrite', 200, requis=False)
        def action():
            ligne, programme = self._intervention_editable(IDintervention)
            if ligne['etat'] not in ('prevue', 'reportee'):
                raise PlanningConflit('Une intervention realisee ou annulee ne se reporte pas')
            if not programme['date_debut'] <= date_prevue <= programme['date_fin'] and not reference_ecrite:
                raise PlanningInvalide('Hors programmation : reference de demande ecrite obligatoire')
            self._version_applicable(programme['IDversion'], date_prevue,
                                     date_prevue, exiger_ouverte=True)
            # Une nouvelle date ne peut pas tomber sur une fermeture connue.
            exclusions = self._lire('SELECT date_debut,date_fin FROM partenaires_exclusions '
                'WHERE IDprogrammation=%s' % self.param, (programme['IDprogrammation'],))
            if any(_iso(x['date_debut']) <= date_prevue <= _iso(x['date_fin']) for x in exclusions):
                raise PlanningConflit('Report sur jour exclu : ajouter un autre jour')
            if (date_prevue, heure_debut, heure_fin) == (
                ligne['date_prevue'], ligne['heure_debut_prevue'], ligne['heure_fin_prevue']):
                raise PlanningInvalide('Report sans changement de date ou d horaire')
            futur = dict(ligne, date_prevue=date_prevue,
                         heure_debut_prevue=heure_debut, heure_fin_prevue=heure_fin)
            self._verifier_conflits_intervention(futur, hors=IDintervention)
            self._historique(ligne, 'report', acteur, motif, nouvelles={
                'etat': 'reportee', 'date_prevue': date_prevue,
                'heure_debut_prevue': heure_debut, 'heure_fin_prevue': heure_fin},
                reference_ecrite=reference_ecrite)
            self._modifier('partenaires_interventions', 'IDintervention', IDintervention, {
                'date_prevue': date_prevue, 'heure_debut_prevue': heure_debut,
                'heure_fin_prevue': heure_fin, 'minutes_prevues': _duree(heure_debut, heure_fin),
                'lieu_prevu': lieu if lieu is not None else ligne['lieu_prevu'],
                'etat': 'reportee', 'motif': motif, 'modifie_le': _maintenant(),
            })
        return self._ecrire(action)

    def _verifier_conflits_intervention(self, candidate, *, hors=None):
        ident = candidate['IDprogrammation']
        date_cible = candidate['date_prevue']
        lignes = self._lire('SELECT * FROM partenaires_interventions '
            "WHERE IDprogrammation=%s AND date_prevue=%s AND etat<>'annulee'" % (
                self.param, self.param), (ident, date_cible))
        for autre in lignes:
            if hors is not None and autre['IDintervention'] == hors:
                continue
            if _chevauchent(candidate, {**autre, 'date_prevue': _iso(autre['date_prevue'])}) and (
                candidate['groupe'] == autre['groupe'] or (
                    candidate['intervenant_prevu'] is not None
                    and candidate['intervenant_prevu'] == autre['intervenant_prevu'])):
                raise PlanningConflit('Intervenant ou groupe deja occupe')

    def annuler_intervention(self, IDintervention, motif, origine, justifiee, *, acteur):
        acteur = self._droit(acteur, 'annuler_intervention')
        motif = _texte(motif, 'motif annulation', 500)
        if origine not in ORIGINES_ANNULATION or type(justifiee) is not bool:
            raise PlanningInvalide('Origine et caractere justifie obligatoire')
        def action():
            ligne, _ = self._intervention_editable(IDintervention)
            if ligne['etat'] not in ('prevue', 'reportee'):
                raise PlanningConflit('Intervention deja finalisee')
            self._historique(ligne, 'annulation', acteur, motif, nouvelles={'etat': 'annulee'})
            self._modifier('partenaires_interventions', 'IDintervention', IDintervention, {
                'etat': 'annulee', 'origine_annulation': origine,
                'justification_annulation': 1 if justifiee else 0,
                'motif': motif, 'modifie_le': _maintenant(),
            })
        return self._ecrire(action)

    def remplacer_intervenant(self, IDintervention, intervenant, motif, *, acteur):
        acteur = self._droit(acteur, 'remplacer_intervenant')
        intervenant = _texte(intervenant, 'nouvel intervenant', 160)
        motif = _texte(motif, 'motif remplacement', 500)
        def action():
            ligne, _ = self._intervention_editable(IDintervention)
            if ligne['etat'] == 'annulee' or ligne['decision_facturation'] == 'eligible':
                raise PlanningConflit('Remplacement sur intervention finalisee interdit')
            ancien = ligne['intervenant_reel'] or ligne['intervenant_prevu']
            if ancien == intervenant:
                raise PlanningInvalide('Remplacement identique a l intervenant precedent')
            self._historique(ligne, 'remplacement', acteur, motif, nouvelles={
                'intervenant_reel': intervenant})
            self._modifier('partenaires_interventions', 'IDintervention', IDintervention, {
                'intervenant_reel': intervenant, 'modifie_le': _maintenant(),
            })
        return self._ecrire(action)

    def marquer_realisee(self, IDintervention, date_reelle, heure_debut, heure_fin,
                         intervenant, *, acteur, lieu=None):
        acteur = self._droit(acteur, 'marquer_realisee')
        _date(date_reelle)
        minutes = _duree(heure_debut, heure_fin)
        intervenant = _texte(intervenant, 'intervenant reel', 160)
        lieu = _texte(lieu, 'lieu reel', 200, requis=False)
        def action():
            ligne, _ = self._intervention_editable(IDintervention)
            if ligne['etat'] not in ('prevue', 'reportee'):
                raise PlanningConflit('Intervention deja realisee ou annulee')
            if date_reelle != ligne['date_prevue']:
                raise PlanningInvalide('Date reelle differente : enregistrer un report avant')
            self._historique(ligne, 'realisation', acteur, 'realisation constatee',
                              nouvelles={'etat': 'realisee', 'intervenant_reel': intervenant})
            self._modifier('partenaires_interventions', 'IDintervention', IDintervention, {
                'date_reelle': date_reelle, 'heure_debut_reelle': heure_debut,
                'heure_fin_reelle': heure_fin, 'minutes_reelles': minutes,
                'lieu_reel': lieu if lieu is not None else ligne['lieu_prevu'],
                'intervenant_reel': intervenant,
                'etat': 'realisee', 'valide_par': acteur, 'valide_le': _maintenant(),
                'modifie_le': _maintenant(),
            })
        return self._ecrire(action)

    def decider_facturation(self, IDintervention, decision, motif, *, acteur):
        acteur = self._droit(acteur, 'decider_facturation')
        if decision not in DECISIONS:
            raise PlanningInvalide('Decision : a_arbitrer, eligible ou non_facturable')
        motif = _texte(motif, 'motif decision', 500)
        def action():
            ligne, _ = self._intervention_editable(IDintervention)
            if decision == 'eligible':
                if ligne['etat'] != 'realisee':
                    raise PlanningInvalide('Seule une intervention realisee peut etre eligible')
                donnees = self._version_applicable(ligne['IDversion'], ligne['date_reelle'],
                                                   ligne['date_reelle'], exiger_ouverte=False)
                if donnees['version']['mode_facturation'] != 'payante' or not any(
                    t['categorie'] == ligne['categorie_tarif']
                    and _iso(t['date_debut']) <= ligne['date_reelle'] <= _iso(t['date_fin'])
                    for t in donnees['tarifs']):
                    raise PlanningInvalide('Aucun tarif explicite compatible : decision refusee')
            if ligne['decision_facturation'] == decision:
                raise PlanningInvalide('Decision inchangee')
            self._historique(ligne, 'decision', acteur, motif, nouvelles={
                'decision_facturation': decision})
            self._modifier('partenaires_interventions', 'IDintervention', IDintervention, {
                'decision_facturation': decision, 'modifie_le': _maintenant(),
            })
        return self._ecrire(action)

    def resume_programmation(self, IDprogrammation, *, acteur):
        self._droit(acteur, 'resume_programmation')
        lignes = self.lister_interventions(IDprogrammation, acteur=acteur)
        return {
            'nombre': len(lignes),
            'prevues': sum(x['etat'] in ('prevue', 'reportee') for x in lignes),
            'realisees': sum(x['etat'] == 'realisee' for x in lignes),
            'annulees': sum(x['etat'] == 'annulee' for x in lignes),
            'minutes_initialement_prevues': sum(int(x['minutes_initiales']) for x in lignes),
            'minutes_planifiees_actuelles': sum(int(x['minutes_prevues']) for x in lignes),
            'minutes_realisees': sum(int(x['minutes_reelles'] or 0) for x in lignes),
            'a_arbitrer': sum(x['decision_facturation'] == 'a_arbitrer' for x in lignes),
            'eligibles': sum(x['decision_facturation'] == 'eligible' for x in lignes),
        }

    def lister_historique(self, IDintervention, *, acteur):
        self._droit(acteur, 'lister_historique')
        self._intervention(IDintervention)
        return self._lire('SELECT * FROM partenaires_interventions_historique '
                          'WHERE IDintervention=%s ORDER BY IDhistorique' % self.param,
                          (IDintervention,))

    def lister_evenements(self, IDprogrammation, *, acteur):
        self._droit(acteur, 'lister_evenements')
        self._programme(IDprogrammation)
        return self._lire('SELECT * FROM partenaires_plan_evenements WHERE '
                          "(nature='programmation' AND IDobjet=%s) OR "
                          "(nature='creneau' AND IDobjet IN "
                          '(SELECT IDcreneau FROM partenaires_creneaux WHERE IDprogrammation=%s)) OR '
                          "(nature='exclusion' AND IDobjet IN "
                          '(SELECT IDexclusion FROM partenaires_exclusions WHERE IDprogrammation=%s)) OR '
                          "(nature='exception' AND IDobjet IN "
                          '(SELECT e.IDexception FROM partenaires_exceptions e JOIN partenaires_creneaux c '
                          'ON e.IDcreneau=c.IDcreneau WHERE c.IDprogrammation=%s)) '
                          'ORDER BY IDevenement' % ((self.param,)*4),
                          (IDprogrammation,)*4)
