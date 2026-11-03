# -*- coding: utf-8 -*-
"""ALSH-C3: adapter securise pour l'interface wx de situation communale.

Toutes les presences et domiciliations viennent des moteurs C1/C2 et des
consommations Noethys. Pas de famille, prestation ou facture supplementaire.
Aucune connexion n'est creee implicitement et aucune migration n'est lancee.
"""

from pathlib import Path

try:
    from .UTILS_ALSH_Commune import (
        ALSHErreur, ALSHAcces, SituationCommunesALSH, _commune,
    )
    from .UTILS_ALSH_AdresseAuto import FrequentationCommunesAuto
except ImportError:  # scripts de recette sans import de package
    from UTILS_ALSH_Commune import (
        ALSHErreur, ALSHAcces, SituationCommunesALSH, _commune,
    )
    from UTILS_ALSH_AdresseAuto import FrequentationCommunesAuto


CATEGORIE_DROITS = 'facturation_situation_collectivites_alsh'
DROITS_ACTIONS = {
    'frequentation_lire_nominatif': 'consulter',
    'domicile_lire': 'consulter',
    'frequentation_export_anonyme': 'consulter',
    'frequentation_export_nominatif': 'exporter',
    'domicile_ecrire': 'modifier',
    'communes_parametrer': 'modifier',
}


class DroitsSituation:
    """La permission est explicite. Le manque d'identite n'est pas un admin.

    Noethys traite souvent un droit absent comme autorise : pour une exportation
    nominative communale, cette fonction fait deliberement l'inverse.
    """

    def __init__(self, utilisateur):
        if not isinstance(utilisateur, dict) or type(utilisateur.get('IDutilisateur')) is not int:
            raise ALSHAcces('Utilisateur Noethys identifie requis')
        if utilisateur['IDutilisateur'] <= 0 or not utilisateur.get('actif') or not utilisateur.get('profil'):
            raise ALSHAcces('Compte utilisateur inactif ou invalide')
        self.identifiant = 'noethys:%d' % utilisateur['IDutilisateur']
        self.admin = str(utilisateur.get('profil') or '').startswith('administrateur')
        droits = utilisateur.get('droits')
        self.droits = droits if isinstance(droits, dict) else {}

    def autoriser(self, acteur, action):
        if acteur != self.identifiant or action not in DROITS_ACTIONS:
            return False
        if self.admin:
            return True
        etat = self.droits.get((CATEGORIE_DROITS, DROITS_ACTIONS[action]))
        return isinstance(etat, str) and etat.startswith('autorisation')

    def imposer(self, action):
        if not self.autoriser(self.identifiant, action):
            raise ALSHAcces('Droit refuse pour %s' % action)


class SituationC3:
    """Facade du moteur date C2 et filtrage nominatif par UNE commune."""

    def __init__(self, connexion, utilisateur, dialecte='sqlite'):
        self.droits = DroitsSituation(utilisateur)
        self.droits.imposer('frequentation_lire_nominatif')
        self.moteur = SituationCommunesALSH(
            connexion, dialecte=dialecte, autoriser=self.droits.autoriser)
        self.auto = FrequentationCommunesAuto(self.moteur)
        self.acteur = self.droits.identifiant

    def _lire(self, sql, params=(), droit='frequentation_lire_nominatif'):
        self.droits.imposer(droit)
        return self.moteur._lire(sql, params)

    def profils(self):
        """Profil C2 cree prealablement ; jamais de valeurs implicites."""
        return [r['nom'] for r in self._lire(
            'SELECT nom FROM alsh_communes_c2_profils ORDER BY nom')]

    def communes(self):
        """Communes disposant d'une correspondance CP/ville verifiee."""
        return self._lire(
            'SELECT DISTINCT code_insee, libelle_commune FROM '
            'alsh_communes_c2_correspondances ORDER BY libelle_commune, code_insee')

    def perimetres(self):
        return self._lire(
            'SELECT a.IDactivite, a.nom AS activite, g.IDgroupe, g.nom AS groupe '
            'FROM activites a INNER JOIN groupes g ON g.IDactivite=a.IDactivite '
            'ORDER BY a.nom, g.nom, g.IDgroupe')

    def unites(self, activites):
        ids = sorted(set(activites))
        if not ids or any(type(x) is not int or x <= 0 for x in ids):
            raise ALSHErreur('Selectionner des activites valides pour lister les unites')
        p = self.moteur.param
        return self._lire(
            'SELECT IDunite, IDactivite, nom FROM unites WHERE IDactivite IN (%s) '
            'ORDER BY IDactivite, nom, IDunite' % ','.join([p]*len(ids)), ids)

    def ajouter_correspondance(self, cp, ville, code, libelle):
        self.droits.imposer('communes_parametrer')
        return self.auto.correspondance(cp, ville, code, libelle, acteur=self.acteur)

    def creer_profil(self, nom, perimetres, unites, tarifs):
        self.droits.imposer('communes_parametrer')
        return self.auto.enregistrer_profil(nom, perimetres, unites, tarifs,
                                           acteur=self.acteur)

    def observations(self, enfant):
        self.droits.imposer('domicile_lire')
        if type(enfant) is not int or enfant <= 0:
            raise ALSHErreur('Identifiant enfant invalide')
        return self._lire('SELECT o.IDobservation, o.IDindividu, o.jour_constat, '
                          'o.source, o.adresse_auto, o.rue_resid, o.cp_resid, '
                          'o.ville_resid, v.date_effet, v.justificatif '
                          'FROM alsh_communes_c2_observations o '
                          'LEFT JOIN alsh_communes_c2_dates_validees v '
                          'ON v.IDobservation=o.IDobservation '
                          'WHERE o.IDindividu=%s ORDER BY o.IDobservation' %
                          self.moteur.param, (enfant,))

    def confirmer_demenagement(self, observation, effet, justificatif):
        self.droits.imposer('domicile_ecrire')
        return self.auto.valider_date_effet(observation, effet, justificatif,
                                           acteur=self.acteur)

    def recalculer(self, debut, fin, profil):
        self.droits.imposer('frequentation_lire_nominatif')
        # Relecture des donnees a chaque demande, sans cache d'un precedent calcul.
        return self.auto.calculer_automatiquement(debut, fin, profil,
                                                 acteur=self.acteur)

    def vue(self, resultat, code_insee=None):
        """Sans commune : uniquement chiffres anonymes. Avec : une commune.

        Toutes les anomalies globales sont signalees en NOMBRE sans divulguer
        le nom d'enfants appartenant a d'autres communes.
        """
        self.droits.imposer('frequentation_lire_nominatif')
        if not isinstance(resultat, dict) or resultat.get('etat') != 'BROUILLON NON FACTURABLE':
            raise ALSHErreur('Resultat C2 attendu')
        if code_insee is None:
            return {'communes': list(resultat['communes']), 'enfants': [], 'lignes': [],
                    'anomalies': len(resultat['anomalies']), 'code_insee': None}
        code = _commune(code_insee)
        return {'communes': [x for x in resultat['communes'] if x['code_insee'] == code],
                'enfants': [x for x in resultat['enfants'] if x['code_insee'] == code],
                'lignes': [x for x in resultat['lignes'] if x['code_insee'] == code],
                'anomalies': len(resultat['anomalies']), 'code_insee': code}

    def csv(self, resultat, nature, code_insee=None):
        """Audit via C1 pour chaque export nominatif, filtre communal obligatoire."""
        if nature == 'anonyme':
            return self.moteur.csv_anonyme(resultat, acteur=self.acteur)
        if nature == 'recap':
            return self.moteur.csv_recap_enfants(resultat, acteur=self.acteur,
                                                code_insee=code_insee)
        if nature == 'detail':
            return self.moteur.csv_nominatif(resultat, acteur=self.acteur,
                                             code_insee=code_insee)
        raise ALSHErreur('Export inconnu')


def enregistrer_csv_nouveau(destination, contenu):
    """N'ecrase jamais une piece transmise. Contenu BOM produit par C1."""
    chemin = Path(destination)
    if not isinstance(contenu, str) or not contenu.startswith('\ufeff'):
        raise ALSHErreur('CSV prepare par le moteur attendu')
    with chemin.open('x', encoding='utf-8', newline='') as f:
        f.write(contenu)
    return chemin
