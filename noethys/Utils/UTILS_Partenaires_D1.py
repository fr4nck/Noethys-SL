# -*- coding: utf-8 -*-
"""Lot D1 : annuaire des partenaires, sans dependance wx ni connexion implicite.

La connexion DB-API est fournie par l'appelant, exclusivement pour ce depot.
Les migrations ne sont JAMAIS lancees ici. Chaque mutation commit/rollback
sa propre transaction ; ne pas partager la connexion avec une transaction
externe. L'autorisation est refusee par defaut. Les liens vers Noethys
requierent une verification explicite de la reference existante.
"""

from datetime import datetime, timezone


CATEGORIES = frozenset(("association", "ecole", "collectivite", "etablissement", "autre"))
TYPES_REFERENCES = frozenset(("famille", "compte_payeur", "tiers_comptable"))
CHAMPS_STRUCTURE = frozenset((
    "categorie", "raison_sociale", "nom_usage", "siret", "adresse_ligne1",
    "code_postal", "commune", "pays", "email_general", "telephone_general",
    "observations",
))
CHAMPS_CONTACT = frozenset(("nom", "prenom", "fonction", "email", "telephone", "principal"))


class PartenairesErreur(ValueError):
    pass


class AutorisationRefusee(PartenairesErreur):
    pass


class ConflitPartenaire(PartenairesErreur):
    pass


class Introuvable(PartenairesErreur):
    pass


def _horodatage():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _identifiant(valeur):
    if type(valeur) is not int or valeur < 1:
        raise PartenairesErreur("Identifiant positif obligatoire")
    return valeur


def _texte(valeur, champ, longueur=255, obligatoire=False):
    if valeur is None and not obligatoire:
        return None
    if not isinstance(valeur, str):
        raise PartenairesErreur("Champ %s invalide" % champ)
    valeur = valeur.strip()
    if not valeur and obligatoire:
        raise PartenairesErreur("Champ %s obligatoire" % champ)
    if not valeur:
        return None
    if len(valeur) > longueur:
        raise PartenairesErreur("Champ %s trop long" % champ)
    return valeur


def _champs_structure(champs, creation=False):
    if not champs or set(champs) - CHAMPS_STRUCTURE:
        raise PartenairesErreur("Champs partenaire non autorises ou absents")
    resultat = {}
    for cle, valeur in champs.items():
        if cle == "categorie":
            if valeur not in CATEGORIES:
                raise PartenairesErreur("Categorie partenaire invalide")
            resultat[cle] = valeur
        elif cle == "siret":
            valeur = _texte(valeur, cle, 14)
            if valeur is not None and (len(valeur) != 14 or not valeur.isascii() or not valeur.isdigit()):
                raise PartenairesErreur("SIRET invalide")
            resultat[cle] = valeur
        else:
            longueurs = {"raison_sociale": 255, "nom_usage": 255, "adresse_ligne1": 255,
                         "code_postal": 12, "commune": 120, "pays": 80,
                         "email_general": 254, "telephone_general": 40, "observations": 20000}
            resultat[cle] = _texte(valeur, cle, longueurs[cle], obligatoire=cle == "raison_sociale")
    if creation and ("categorie" not in resultat or "raison_sociale" not in resultat):
        raise PartenairesErreur("Categorie et raison sociale obligatoires")
    return resultat


def _champs_contact(champs, creation=False):
    if not champs or set(champs) - CHAMPS_CONTACT:
        raise PartenairesErreur("Champs contact non autorises ou absents")
    resultat = {}
    for cle, valeur in champs.items():
        if cle == "principal":
            if type(valeur) is not bool:
                raise PartenairesErreur("Principal doit etre un booleen")
            resultat[cle] = 1 if valeur else None
        else:
            tailles = {"nom": 120, "prenom": 120, "fonction": 160, "email": 254, "telephone": 40}
            resultat[cle] = _texte(valeur, cle, tailles[cle], obligatoire=cle == "nom")
    if creation and "nom" not in resultat:
        raise PartenairesErreur("Nom du contact obligatoire")
    return resultat


class AnnuairePartenaires:
    """Moteur D1. ``autoriser(acteur, action)`` doit approuver les mutations.

    ``reference_existe(type_reference, IDreference)`` verifie les donnees
    historiques sur une connexion fiable. Le module ne les ouvre jamais.
    ``dialecte`` vaut ``sqlite`` ou ``mysql`` (requêtes parametrees).
    """

    def __init__(self, connexion, *, dialecte="sqlite", autoriser=None,
                 reference_existe=None):
        if dialecte not in ("sqlite", "mysql") or connexion is None:
            raise PartenairesErreur("Connexion ou dialecte invalide")
        self.connexion = connexion
        self.param = "?" if dialecte == "sqlite" else "%s"
        self.autoriser = autoriser
        self.reference_existe = reference_existe

    def _executer(self, sql, params=(), lecture=False):
        curseur = self.connexion.cursor()
        try:
            curseur.execute(sql, tuple(params))
            if lecture:
                colonnes = [col[0] for col in curseur.description]
                return [dict(zip(colonnes, ligne)) for ligne in curseur.fetchall()]
            return curseur.lastrowid
        finally:
            curseur.close()

    def _lire(self, sql, params=()):
        return self._executer(sql, params, lecture=True)

    def _mutation(self, operation):
        try:
            resultat = operation()
            self.connexion.commit()
            return resultat
        except Exception as erreur:
            self.connexion.rollback()
            if erreur.__class__.__name__ == "IntegrityError":
                raise ConflitPartenaire("Contrainte de liaison ou d'unicite non respectee") from erreur
            raise

    def _droit(self, acteur, action):
        acteur = _texte(acteur, "acteur", 100, obligatoire=True)
        if not callable(self.autoriser) or self.autoriser(acteur, action) is not True:
            raise AutorisationRefusee("Operation partenaire non autorisee")
        return acteur

    def _evenement(self, nature, identifiant, action, acteur, champs=""):
        self._executer(
            "INSERT INTO partenaires_evenements (nature, IDobjet, action, acteur, champs, date_action) "
            "VALUES (%s)" % ", ".join((self.param,) * 6),
            (nature, identifiant, action, acteur, champs, _horodatage()))

    def _exiger(self, table, colonne, identifiant, actif=False):
        _identifiant(identifiant)
        condition = " AND statut='actif'" if actif else ""
        lignes = self._lire("SELECT * FROM %s WHERE %s=%s%s" % (
            table, colonne, self.param, condition), (identifiant,))
        if not lignes:
            raise Introuvable("Objet partenaire absent ou indisponible")
        return lignes[0]

    def creer_structure(self, champs, *, acteur):
        acteur = self._droit(acteur, "creer_structure")
        champs = _champs_structure(champs, creation=True)
        maintenant = _horodatage()
        donnees = dict(champs, statut="actif", cree_le=maintenant, modifie_le=maintenant)
        def action():
            ident = self._inserer("partenaires_structures", donnees)
            self._evenement("structure", ident, "creation", acteur)
            return ident
        return self._mutation(action)

    def _inserer(self, table, champs):
        cles = sorted(champs)
        return self._executer(
            "INSERT INTO %s (%s) VALUES (%s)" % (table, ", ".join(cles),
                                                   ", ".join((self.param,) * len(cles))),
            [champs[cle] for cle in cles])

    def _modifier(self, table, champ_id, identifiant, champs):
        cles = sorted(champs)
        self._executer("UPDATE %s SET %s WHERE %s=%s" % (
            table, ", ".join("%s=%s" % (cle, self.param) for cle in cles),
            champ_id, self.param), [champs[cle] for cle in cles] + [identifiant])

    def modifier_structure(self, identifiant, champs, *, acteur):
        acteur = self._droit(acteur, "modifier_structure")
        champs = _champs_structure(champs)
        def action():
            self._exiger("partenaires_structures", "IDpartenaire", identifiant, actif=True)
            self._modifier("partenaires_structures", "IDpartenaire", identifiant,
                           dict(champs, modifie_le=_horodatage()))
            self._evenement("structure", identifiant, "modification", acteur, ",".join(sorted(champs)))
        self._mutation(action)

    def lister_structures(self, *, acteur, categorie=None, inclure_archivees=False):
        self._droit(acteur, "lister_structures")
        if categorie is not None and categorie not in CATEGORIES:
            raise PartenairesErreur("Categorie invalide")
        if type(inclure_archivees) is not bool:
            raise PartenairesErreur("Choix d'archives invalide")
        filtres, params = [], []
        if categorie:
            filtres.append("categorie=%s" % self.param)
            params.append(categorie)
        if not inclure_archivees:
            filtres.append("statut='actif'")
        clause = " WHERE " + " AND ".join(filtres) if filtres else ""
        return self._lire("SELECT * FROM partenaires_structures%s ORDER BY raison_sociale, IDpartenaire" % clause, params)

    def creer_contact(self, IDpartenaire, champs, *, acteur):
        acteur = self._droit(acteur, "creer_contact")
        champs = _champs_contact(champs, creation=True)
        def action():
            self._exiger("partenaires_structures", "IDpartenaire", IDpartenaire, actif=True)
            maintenant = _horodatage()
            donnees = dict(champs, IDpartenaire=IDpartenaire, statut="actif",
                           cree_le=maintenant, modifie_le=maintenant)
            ident = self._inserer("partenaires_contacts", donnees)
            self._evenement("contact", ident, "creation", acteur)
            return ident
        return self._mutation(action)

    def modifier_contact(self, identifiant, champs, *, acteur):
        acteur = self._droit(acteur, "modifier_contact")
        champs = _champs_contact(champs)
        def action():
            contact = self._exiger("partenaires_contacts", "IDcontact_partenaire", identifiant, actif=True)
            self._exiger("partenaires_structures", "IDpartenaire", contact["IDpartenaire"], actif=True)
            self._modifier("partenaires_contacts", "IDcontact_partenaire", identifiant,
                           dict(champs, modifie_le=_horodatage()))
            self._evenement("contact", identifiant, "modification", acteur, ",".join(sorted(champs)))
        self._mutation(action)

    def archiver_contact(self, identifiant, *, acteur):
        acteur = self._droit(acteur, "archiver_contact")
        def action():
            self._exiger("partenaires_contacts", "IDcontact_partenaire", identifiant, actif=True)
            self._modifier("partenaires_contacts", "IDcontact_partenaire", identifiant,
                           {"statut": "archive", "principal": None, "modifie_le": _horodatage()})
            self._evenement("contact", identifiant, "archivage", acteur)
        self._mutation(action)

    def lister_contacts(self, IDpartenaire, *, acteur, inclure_archives=False):
        self._droit(acteur, "lister_contacts")
        _identifiant(IDpartenaire)
        if type(inclure_archives) is not bool:
            raise PartenairesErreur("Choix d'archives invalide")
        clause = "" if inclure_archives else " AND statut='actif'"
        return self._lire("SELECT * FROM partenaires_contacts WHERE IDpartenaire=%s%s "
                          "ORDER BY nom, prenom, IDcontact_partenaire" % (self.param, clause),
                          (IDpartenaire,))

    def lier_reference(self, IDpartenaire, type_reference, IDreference, *, acteur):
        acteur = self._droit(acteur, "lier_reference")
        _identifiant(IDpartenaire)
        _identifiant(IDreference)
        if type_reference not in TYPES_REFERENCES:
            raise PartenairesErreur("Type de reference historique invalide")
        if not callable(self.reference_existe) or self.reference_existe(type_reference, IDreference) is not True:
            raise PartenairesErreur("Reference historique non verifiee")
        def action():
            self._exiger("partenaires_structures", "IDpartenaire", IDpartenaire, actif=True)
            deja = self._lire("SELECT * FROM partenaires_liens_noethys "
                             "WHERE IDpartenaire=%s AND type_reference=%s AND actif=1" %
                             (self.param, self.param), (IDpartenaire, type_reference))
            if deja:
                if deja[0]["IDreference"] == IDreference:
                    return deja[0]["IDlien"]  # reprise idempotente
                raise ConflitPartenaire("Rapprochement existant : delier d'abord")
            ident = self._inserer("partenaires_liens_noethys", dict(
                IDpartenaire=IDpartenaire, type_reference=type_reference, IDreference=IDreference,
                actif=1, date_debut=_horodatage(), date_fin=None))
            self._evenement("lien", ident, "creation", acteur)
            return ident
        return self._mutation(action)

    def delier_reference(self, IDlien, *, acteur):
        acteur = self._droit(acteur, "delier_reference")
        def action():
            lien = self._exiger("partenaires_liens_noethys", "IDlien", IDlien)
            if lien["actif"] is None:
                return  # reprise idempotente
            self._modifier("partenaires_liens_noethys", "IDlien", IDlien,
                           {"actif": None, "date_fin": _horodatage()})
            self._evenement("lien", IDlien, "revocation", acteur)
        self._mutation(action)

    def lister_liens(self, IDpartenaire, *, acteur, inclure_revoques=False):
        self._droit(acteur, "lister_liens")
        _identifiant(IDpartenaire)
        if type(inclure_revoques) is not bool:
            raise PartenairesErreur("Choix d'historique invalide")
        clause = "" if inclure_revoques else " AND actif=1"
        return self._lire("SELECT * FROM partenaires_liens_noethys WHERE IDpartenaire=%s%s "
                          "ORDER BY IDlien" % (self.param, clause), (IDpartenaire,))

    def archiver_structure(self, IDpartenaire, *, acteur):
        acteur = self._droit(acteur, "archiver_structure")
        def action():
            self._exiger("partenaires_structures", "IDpartenaire", IDpartenaire, actif=True)
            liens = self._lire("SELECT IDlien FROM partenaires_liens_noethys "
                               "WHERE IDpartenaire=%s AND actif=1" % self.param, (IDpartenaire,))
            if liens:
                raise ConflitPartenaire("Revoquer les liens avant archivage")
            self._modifier("partenaires_structures", "IDpartenaire", IDpartenaire,
                           {"statut": "archive", "modifie_le": _horodatage()})
            self._evenement("structure", IDpartenaire, "archivage", acteur)
        self._mutation(action)

    def lister_evenements(self, *, acteur, nature=None, IDobjet=None):
        self._droit(acteur, "lister_evenements")
        if nature is not None and nature not in ("structure", "contact", "lien"):
            raise PartenairesErreur("Nature d'evenement invalide")
        conditions, valeurs = [], []
        if nature:
            conditions.append("nature=%s" % self.param)
            valeurs.append(nature)
        if IDobjet is not None:
            _identifiant(IDobjet)
            conditions.append("IDobjet=%s" % self.param)
            valeurs.append(IDobjet)
        filtre = " WHERE " + " AND ".join(conditions) if conditions else ""
        return self._lire("SELECT * FROM partenaires_evenements%s ORDER BY IDevenement" % filtre, valeurs)
