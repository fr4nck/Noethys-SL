#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Licence:         Licence GNU GPL
#------------------------------------------------------------------------
""" Réconciliation idempotente des adhésions annuelles, sans dépendance wx.

Règle métier :
- titulaire de l'adhésion :
  * structure adhérente (association, collectivité, organisme, entreprise) :
    famille dont un titulaire rattaché est une personne morale (individu de
    civilité « AUTRE » de DATA_Civilites). UNE adhésion pour la structure,
    portée par cet individu personne morale, quelles que soient les
    sections, activités ou représentants qui participent ;
  * sinon (famille de personnes physiques) : UNE adhésion par personne qui
    participe (enfant ou adulte), couvrant toutes ses activités ; jamais
    commune à toute la famille ;
- une seule adhésion (table `cotisations`, type individuel par défaut) valide
  à la fois par titulaire, toutes activités, sites, ateliers, classes,
  sections et séances confondus ;
- la première participation réelle sans adhésion valide crée l'adhésion,
  qui démarre à la date de cette participation ;
- convention native Noethys : validité INCLUSIVE, `date_debut <= date <=
  date_fin`, avec `date_fin = date_debut + durée de l'unité` (début
  15/06/2026 => fin 15/06/2027 incluse ; une nouvelle adhésion est donc
  possible dès le 16/06/2027) ;
- aucun renouvellement automatique : après expiration on attend la
  prochaine participation réelle ;
- jamais de chevauchement : si la période à créer recouvre une adhésion
  existante du même type (y compris future), rien n'est créé et la
  situation est `a_verifier` (motif "chevauchement") ;
- au plus une adhésion à venir (début postérieur à la date de
  réconciliation) : une participation plus lointaine n'est traitée qu'à
  une réconciliation ultérieure (motif "adhesion_a_venir_existante") ;
- tarif, durée et libellé viennent de `unites_cotisations`, jamais codés
  en dur ; le type/l'unité sont résolus par configuration (type
  "individu" par défaut, unité à durée par défaut), sans ID codé en dur.

Participation réelle = consommation `reservation` ou `present` sur une
activité liée au type d'adhésion (`cotisations_activites`), ou prestation
de consommation (IDindividu + IDactivite) sans consommation équivalente
(même individu, même activité, même date). Une simple inscription sans
consommation ni prestation n'est PAS une participation.

Annulation : ce module ne supprime JAMAIS rien. Voir
EvaluerAdhesionsAutomatiques(). """

import datetime
import re
import traceback

from dateutil import relativedelta

import GestionDB


STATUT_CREE = "cree"
STATUT_RIEN = "rien_a_faire"
STATUT_A_VERIFIER = "a_verifier"
STATUT_CONFIG_INVALIDE = "configuration_invalide"
STATUT_ERREUR = "erreur"

# Marque posée dans cotisations.observations : seules les adhésions portant
# cette marque sont évaluées par EvaluerAdhesionsAutomatiques().
MARQUEUR_AUTO = u"[adhesion-auto]"

_MAX_CREATIONS_PAR_APPEL = 50

# Clé du résultat de ReconcilierSansEchec portant une exception inattendue.
CLE_ERREUR = "erreur"


class ConfigurationAdhesionInvalide(Exception):
    """ `ambigue` : plusieurs choix possibles (erreur de paramétrage à signaler),
    par opposition à une adhésion automatique simplement non configurée. """

    def __init__(self, message, ambigue=False):
        Exception.__init__(self, message)
        self.ambigue = ambigue


# ---------------------------------------------------------------- utilitaires

def _en_date(valeur):
    if valeur is None:
        return None
    if isinstance(valeur, datetime.datetime):
        return valeur.date()
    if isinstance(valeur, datetime.date):
        return valeur
    texte = str(valeur)
    return datetime.date(int(texte[:4]), int(texte[5:7]), int(texte[8:10]))


def _liste_sql(liste_ids):
    return "(%s)" % ", ".join(str(int(x)) for x in liste_ids)


def _lire(req):
    DB = GestionDB.DB()
    try:
        DB.ExecuterReq(req)
        return DB.ResultatReq()
    finally:
        DB.Close()


def CalculerDateFin(date_debut, duree):
    """ Même calcul que DLG_Saisie_cotisation.OnChoixUnite : jours, puis mois,
    puis années ajoutés à date_debut. Aucun jour retiré. `duree` : "j0-m0-a1". """
    correspondance = re.match(r"^j(\d+)-m(\d+)-a(\d+)$", str(duree or "").strip())
    if correspondance is None:
        raise ConfigurationAdhesionInvalide(u"Durée d'unité de cotisation invalide : %r" % (duree,))
    jours, mois, annees = [int(x) for x in correspondance.groups()]
    date_fin = _en_date(date_debut)
    if jours != 0:
        date_fin = date_fin + relativedelta.relativedelta(days=+jours)
    if mois != 0:
        date_fin = date_fin + relativedelta.relativedelta(months=+mois)
    if annees != 0:
        date_fin = date_fin + relativedelta.relativedelta(years=+annees)
    return date_fin


# -------------------------------------------------------------- configuration

def ResoudreConfiguration(IDtype_cotisation=None, IDunite_cotisation=None):
    """ Résout le type et l'unité d'adhésion.

    - sans argument : le type "individu" marqué par défaut (exactement un),
      et son unité à durée marquée par défaut (ou l'unique unité à durée) ;
    - IDtype_cotisation / IDunite_cotisation permettent de forcer le choix.

    Lève ConfigurationAdhesionInvalide si le choix est absent ou ambigu, si
    le type n'est pas individuel, ou si l'unité n'a pas de durée glissante
    (une unité à dates fixes ne peut pas porter la règle des 12 mois). """
    types = _lire("SELECT IDtype_cotisation, nom, type, carte, defaut FROM types_cotisations;")
    if IDtype_cotisation is None:
        candidats = [t for t in types if t[2] == "individu" and t[4] == 1]
        if len(candidats) != 1:
            raise ConfigurationAdhesionInvalide(
                u"Impossible de résoudre le type d'adhésion : %d type(s) individuel(s) par défaut." % len(candidats),
                ambigue=len(candidats) > 1)
        type_retenu = candidats[0]
    else:
        candidats = [t for t in types if t[0] == IDtype_cotisation]
        if not candidats:
            raise ConfigurationAdhesionInvalide(u"Type de cotisation %s introuvable." % IDtype_cotisation)
        type_retenu = candidats[0]
    ID_type, nom_type, categorie_type, carte, _defaut = type_retenu
    if categorie_type != "individu":
        raise ConfigurationAdhesionInvalide(u"Le type de cotisation %s n'est pas individuel." % ID_type)

    unites = _lire("""SELECT IDunite_cotisation, nom, montant, label_prestation, defaut, duree
    FROM unites_cotisations WHERE IDtype_cotisation=%d ORDER BY IDunite_cotisation;""" % ID_type)
    if IDunite_cotisation is None:
        unites_duree = [u for u in unites if u[5]]
        candidats = [u for u in unites_duree if u[4] == 1]
        if len(candidats) != 1:
            candidats = unites_duree if len(unites_duree) == 1 else []
        if len(candidats) != 1:
            raise ConfigurationAdhesionInvalide(
                u"Impossible de résoudre l'unité d'adhésion du type %s (unité à durée par défaut absente ou ambiguë)." % ID_type,
                ambigue=True)
        unite = candidats[0]
    else:
        candidats = [u for u in unites if u[0] == IDunite_cotisation]
        if not candidats:
            raise ConfigurationAdhesionInvalide(u"Unité de cotisation %s introuvable pour le type %s." % (IDunite_cotisation, ID_type))
        unite = candidats[0]
    ID_unite, nom_unite, montant, label_prestation, _defaut_unite, duree = unite
    if not duree:
        raise ConfigurationAdhesionInvalide(u"L'unité %s n'a pas de durée glissante (dates fixes)." % ID_unite)
    CalculerDateFin(datetime.date(2000, 1, 1), duree)  # valide le format

    return {
        "IDtype_cotisation": ID_type,
        "nom_type": nom_type,
        "carte": carte,
        "IDunite_cotisation": ID_unite,
        "nom_unite": nom_unite,
        "montant": float(montant) if montant is not None else 0.0,
        "label_prestation": label_prestation,
        "duree": duree,
    }


def GetActivitesConcernees(IDtype_cotisation):
    """ Activités qui exigent ce type d'adhésion (`cotisations_activites`). """
    lignes = _lire("SELECT DISTINCT IDactivite FROM cotisations_activites WHERE IDtype_cotisation=%d;" % IDtype_cotisation)
    return sorted(ligne[0] for ligne in lignes if ligne[0] is not None)


# ------------------------------------------------------------------ adhésions

def GetAdhesions(IDindividu, IDtype_cotisation):
    """ Toutes les adhésions de ce type pour cet individu, triées par début. """
    lignes = _lire("""SELECT IDcotisation, date_debut, date_fin, IDprestation, observations, IDunite_cotisation
    FROM cotisations WHERE IDindividu=%d AND IDtype_cotisation=%d
    ORDER BY date_debut, IDcotisation;""" % (IDindividu, IDtype_cotisation))
    return [{
        "IDcotisation": IDcotisation,
        "date_debut": _en_date(date_debut),
        "date_fin": _en_date(date_fin),
        "IDprestation": IDprestation,
        "observations": observations,
        "IDunite_cotisation": IDunite,
    } for IDcotisation, date_debut, date_fin, IDprestation, observations, IDunite in lignes]


def _est_valide(adhesion, date_reference):
    return adhesion["date_debut"] <= date_reference <= adhesion["date_fin"]


def GetAdhesionValide(IDindividu, date_reference, IDtype_cotisation):
    """ Adhésion couvrant `date_reference` (bornes INCLUSIVES), sinon None.
    S'il y en a plusieurs (données historiques), celle qui finit le plus tard. """
    date_reference = _en_date(date_reference)
    valides = [a for a in GetAdhesions(IDindividu, IDtype_cotisation) if _est_valide(a, date_reference)]
    if not valides:
        return None
    return max(valides, key=lambda a: (a["date_fin"], a["IDcotisation"]))


def GetDerniereAdhesion(IDindividu, IDtype_cotisation):
    """ Adhésion qui finit le plus tard (ou None). """
    adhesions = GetAdhesions(IDindividu, IDtype_cotisation)
    if not adhesions:
        return None
    return max(adhesions, key=lambda a: (a["date_fin"], a["IDcotisation"]))


# -------------------------------------------------------------- participations

def GetParticipations(IDindividu, activites, depuis, jusqu_a=None):
    """ Participations réelles de l'individu à partir de `depuis`, triées par
    date puis consommations avant prestations.

    [{"date", "source" ("consommation"|"prestation"), "id", "IDcompte_payeur", "IDinscription"}] """
    if not activites:
        return []
    depuis = _en_date(depuis)
    condition_fin_c = " AND consommations.date<='%s'" % _en_date(jusqu_a) if jusqu_a else ""
    condition_fin_p = " AND prestations.date<='%s'" % _en_date(jusqu_a) if jusqu_a else ""
    liste = _liste_sql(activites)

    consommations = _lire("""SELECT date, IDconso, IDcompte_payeur, IDinscription
    FROM consommations
    WHERE IDindividu=%d AND etat IN ('reservation', 'present') AND IDactivite IN %s AND date>='%s'%s
    ORDER BY date, IDconso;""" % (IDindividu, liste, depuis, condition_fin_c))
    prestations = _lire("""SELECT date, IDprestation, IDcompte_payeur
    FROM prestations
    WHERE IDindividu=%d AND categorie='consommation' AND IDactivite IN %s AND date>='%s'%s
    AND NOT EXISTS (SELECT 1 FROM consommations
        WHERE consommations.IDindividu=prestations.IDindividu
        AND consommations.IDactivite=prestations.IDactivite
        AND consommations.date=prestations.date)
    ORDER BY date, IDprestation;""" % (IDindividu, liste, depuis, condition_fin_p))

    participations = [
        {"date": _en_date(date), "source": "consommation", "id": ID, "IDcompte_payeur": IDcompte_payeur, "IDinscription": IDinscription}
        for date, ID, IDcompte_payeur, IDinscription in consommations
    ] + [
        {"date": _en_date(date), "source": "prestation", "id": ID, "IDcompte_payeur": IDcompte_payeur, "IDinscription": None}
        for date, ID, IDcompte_payeur in prestations
    ]
    participations.sort(key=lambda p: (p["date"], 0 if p["source"] == "consommation" else 1, p["id"]))
    return participations


def GetProchaineDateDeclenchante(IDindividu, config, depuis=None, date_reference=None):
    """ Première participation (à partir de `depuis`, par défaut
    `date_reference`, par défaut aujourd'hui) qui n'est couverte par aucune
    adhésion (bornes inclusives) -- ou None. Le dict retourné est la
    participation (cf. GetParticipations). Ne crée rien. """
    date_reference = _en_date(date_reference) or datetime.date.today()
    depuis = _en_date(depuis) or date_reference
    activites = GetActivitesConcernees(config["IDtype_cotisation"])
    titulaires, adhesions = {}, {}
    for participation in GetParticipations(IDindividu, activites, depuis):
        cle = (participation.get("IDcompte_payeur"), participation.get("IDinscription"))
        if cle not in titulaires:
            titulaires[cle] = ResoudreTitulaire(IDindividu, participation)["IDtitulaire"]
        IDtitulaire = titulaires[cle]
        if IDtitulaire not in adhesions:
            adhesions[IDtitulaire] = GetAdhesions(IDtitulaire, config["IDtype_cotisation"])
        if not any(_est_valide(a, participation["date"]) for a in adhesions[IDtitulaire]):
            return participation
    return None


# ------------------------------------------------------------------- création

def _periode_verrouillee(DB, date):
    """ Reprend UTILS_Gestion.Gestion.Verification (sans wx) : période de
    gestion verrouillée pour les prestations ou les cotisations. """
    if not DB.ExecuterReq("SELECT date_debut, date_fin, verrou_prestations, verrou_cotisations FROM periodes_gestion;"):
        return False
    date = str(date)
    for date_debut, date_fin, verrou_prestations, verrou_cotisations in DB.ResultatReq():
        if str(date_debut)[:10] <= date <= str(date_fin)[:10] and (verrou_prestations == 1 or verrou_cotisations == 1):
            return True
    return False


def _resoudre_payeur(DB, IDindividu, participation):
    """ (IDcompte_payeur, IDfamille) : payeur de la participation déclenchante,
    sinon celui de son inscription, sinon l'unique famille de rattachement.
    (None, None) si indéterminable -- jamais de choix arbitraire. """
    candidats = [participation.get("IDcompte_payeur")]
    if participation.get("IDinscription"):
        DB.ExecuterReq("SELECT IDcompte_payeur FROM inscriptions WHERE IDinscription=%d;" % participation["IDinscription"])
        candidats += [ligne[0] for ligne in DB.ResultatReq()]
    for IDcompte_payeur in candidats:
        if IDcompte_payeur:
            DB.ExecuterReq("SELECT IDfamille FROM comptes_payeurs WHERE IDcompte_payeur=%d;" % IDcompte_payeur)
            lignes = DB.ResultatReq()
            if lignes:
                return IDcompte_payeur, lignes[0][0]
    DB.ExecuterReq("""SELECT comptes_payeurs.IDcompte_payeur, comptes_payeurs.IDfamille
    FROM rattachements
    LEFT JOIN comptes_payeurs ON comptes_payeurs.IDfamille = rattachements.IDfamille
    WHERE rattachements.IDindividu=%d;""" % IDindividu)
    lignes = [ligne for ligne in DB.ResultatReq() if ligne[0] is not None]
    if len(lignes) == 1:
        return lignes[0]
    return None, None


# Civilités de personnes morales (DATA_Civilites, rubrique « AUTRE ») :
# 6 Collectivité, 7 Association, 8 Organisme, 9 Entreprise.
CIVILITES_PERSONNE_MORALE = (6, 7, 8, 9)


class TitulaireAmbigu(Exception):
    pass


class _Lecteur(object):
    """ Interface ExecuterReq/ResultatReq pour des lectures ponctuelles. """

    def __init__(self):
        self._req = None

    def ExecuterReq(self, req):
        self._req = req
        return 1

    def ResultatReq(self):
        return _lire(self._req)


def _StructureDeFamille(acces, IDfamille):
    """ IDindividu de la personne morale titulaire de la famille (structure
    adhérente), ou None pour une famille de personnes physiques. Lève
    TitulaireAmbigu si la famille a plusieurs personnes morales titulaires. """
    acces.ExecuterReq("""SELECT DISTINCT rattachements.IDindividu
    FROM rattachements
    JOIN individus ON individus.IDindividu = rattachements.IDindividu
    WHERE rattachements.IDfamille=%d AND rattachements.titulaire=1
    AND individus.IDcivilite IN %s;""" % (IDfamille, _liste_sql(CIVILITES_PERSONNE_MORALE)))
    ids = sorted(ligne[0] for ligne in acces.ResultatReq())
    if len(ids) > 1:
        raise TitulaireAmbigu(ids)
    return ids[0] if ids else None


def ResoudreTitulaire(IDindividu, participation, acces=None):
    """ Titulaire de l'adhésion couvrant cette participation :
    {"IDtitulaire", "IDcompte_payeur", "IDfamille", "structure", "motif"}.
    La famille est celle du payeur de la participation (cf. _resoudre_payeur).
    Si elle est une structure adhérente, le titulaire est sa personne morale ;
    sinon c'est l'individu qui participe. `motif` signale un cas à vérifier
    (payeur indéterminable, plusieurs personnes morales titulaires). """
    acces = acces or _Lecteur()
    IDcompte_payeur, IDfamille = _resoudre_payeur(acces, IDindividu, participation)
    titulaire = {"IDtitulaire": IDindividu, "IDcompte_payeur": IDcompte_payeur, "IDfamille": IDfamille,
                 "structure": False, "motif": None}
    if IDcompte_payeur is None:
        titulaire["motif"] = "payeur_indeterminable"
        return titulaire
    try:
        structure = _StructureDeFamille(acces, IDfamille)
    except TitulaireAmbigu:
        titulaire["motif"] = "titulaire_ambigu"
        return titulaire
    if structure is not None:
        titulaire.update(IDtitulaire=structure, structure=True)
    return titulaire


def _ParticipantsDuTitulaire(IDtitulaire):
    """ Individus dont les participations relèvent de ce titulaire : tous les
    membres des familles dont il est la personne morale titulaire, sinon
    lui seul. """
    familles = [ligne[0] for ligne in _lire("""SELECT rattachements.IDfamille
    FROM rattachements
    JOIN individus ON individus.IDindividu = rattachements.IDindividu
    WHERE rattachements.IDindividu=%d AND rattachements.titulaire=1
    AND individus.IDcivilite IN %s;""" % (IDtitulaire, _liste_sql(CIVILITES_PERSONNE_MORALE)))]
    if not familles:
        return [IDtitulaire]
    membres = _lire("SELECT IDindividu FROM rattachements WHERE IDfamille IN %s;" % _liste_sql(familles))
    return sorted({IDtitulaire} | {ligne[0] for ligne in membres})


class VerrouIndisponible(Exception):
    pass


class TransactionsNonSupportees(Exception):
    pass


# Attente maximale du verrou d'une autre sauvegarde (secondes).
DELAI_VERROU = 10
TABLES_ECRITES = ("cotisations", "prestations", "historique")


class _AccesStrict(object):
    """ Accès à la connexion d'écriture sans erreur avalée : dans la section
    protégée, une lecture en échec ne doit jamais valoir « aucune adhésion ». """

    def __init__(self, DB):
        if getattr(DB, "echec", 0) == 1:
            raise RuntimeError(u"Base inaccessible : %s" % getattr(DB, "erreur", u""))
        self.DB = DB
        self.cursor = DB.cursor

    def ExecuterReq(self, req):
        self.cursor.execute(req)
        return 1

    def ResultatReq(self):
        return list(self.cursor.fetchall())

    def Inserer(self, table, donnees):
        marque = "%s" if self.DB.isNetwork else "?"
        req = "INSERT INTO %s (%s) VALUES (%s)" % (
            table, ", ".join(nom for nom, _valeur in donnees), ", ".join([marque] * len(donnees)))
        self.cursor.execute(req, tuple(valeur for _nom, valeur in donnees))
        ID = self.cursor.lastrowid
        if not ID:
            raise RuntimeError(u"Insertion dans %s sans identifiant." % table)
        return ID

    def Modifier(self, req, valeurs):
        if self.DB.isNetwork:
            req = req.replace("?", "%s")
        self.cursor.execute(req, valeurs)
        if self.cursor.rowcount != 1:
            raise RuntimeError(u"Mise à jour inattendue (%s ligne(s)) : %s" % (self.cursor.rowcount, req))


def _Verrouiller(DB, IDindividu, IDtype_cotisation):
    """ Sérialise, entre postes, le contrôle d'existant et la création pour un
    individu et un type d'adhésion. Retourne la fonction de libération.

    - SQLite : BEGIN IMMEDIATE prend le verrou d'écriture du fichier avant le
      contrôle ; une autre sauvegarde attend (délai de la connexion) puis
      relit l'état validé. Garantie limitée à un verrouillage de fichier
      fiable (disque local ; un partage réseau n'en offre pas toujours).
    - MySQL : verrou nommé GET_LOCK, partagé par toutes les connexions au
      serveur. Les trois tables doivent être transactionnelles (InnoDB) pour
      qu'un échec n'écrive rien ; sinon la création automatique est refusée. """
    if DB.isNetwork:
        DB.cursor.execute("""SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN ('cotisations', 'prestations', 'historique');""")
        moteurs = dict((str(nom).lower(), str(moteur or "").lower()) for nom, moteur in DB.cursor.fetchall())
        if sorted(moteurs) != sorted(TABLES_ECRITES) or any(moteur != "innodb" for moteur in moteurs.values()):
            raise TransactionsNonSupportees(moteurs)
        nom = "CONCAT('noethys_adhesion_', LEFT(MD5(DATABASE()), 12), '_%d_%d')" % (IDindividu, IDtype_cotisation)
        DB.cursor.execute("SELECT GET_LOCK(%s, %d);" % (nom, DELAI_VERROU))
        obtenu = DB.cursor.fetchall()
        if not obtenu or obtenu[0][0] != 1:
            raise VerrouIndisponible()
        # Nouveau cliché de lecture après l'attente : voir ce qu'une autre
        # sauvegarde a validé pendant que ce poste attendait le verrou.
        DB.connexion.commit()

        def liberer():
            try:
                DB.cursor.execute("SELECT RELEASE_LOCK(%s);" % nom)
                DB.cursor.fetchall()
            except Exception:
                pass  # libéré de toute façon à la fermeture de la connexion
        return liberer

    import sqlite3
    if DB.connexion.in_transaction:
        DB.connexion.commit()
    try:
        DB.connexion.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError as err:
        if "locked" in str(err).lower() or "busy" in str(err).lower():
            raise VerrouIndisponible()
        raise
    return lambda: None


def CreerAdhesion(IDindividu, participation, config, date_reference=None, IDutilisateur=None):
    """ Crée UNE adhésion (cotisation + prestation `cotisation` + historique)
    dans une seule transaction, avec exactement les champs écrits par
    DLG_Saisie_cotisation.CTRL_Parametres.Sauvegarde pour une cotisation
    individuelle facturée.

    Le contrôle d'existant (couverture, chevauchement, adhésion à venir) et la
    création sont protégés ensemble par _Verrouiller : deux postes qui
    sauvegardent en même temps ne créent jamais deux adhésions. Toute erreur
    d'écriture annule l'ensemble (aucune cotisation sans prestation, aucune
    prestation en double).

    Retourne {"statut": STATUT_CREE|STATUT_RIEN|STATUT_A_VERIFIER, ...}. """
    date_reference = _en_date(date_reference) or datetime.date.today()
    date_debut = _en_date(participation["date"])
    date_fin = CalculerDateFin(date_debut, config["duree"])
    periode = {"date_debut": date_debut, "date_fin": date_fin}

    DB = GestionDB.DB()
    liberer = None
    try:
        acces = _AccesStrict(DB)
        titulaire = ResoudreTitulaire(IDindividu, participation, acces)
        IDtitulaire = titulaire["IDtitulaire"]
        periode["IDtitulaire"] = IDtitulaire
        if titulaire["motif"]:
            return dict(periode, statut=STATUT_A_VERIFIER, motif=titulaire["motif"])
        try:
            liberer = _Verrouiller(DB, IDtitulaire, config["IDtype_cotisation"])
        except VerrouIndisponible:
            return dict(periode, statut=STATUT_A_VERIFIER, motif="verrou_indisponible")
        except TransactionsNonSupportees:
            return dict(periode, statut=STATUT_A_VERIFIER, motif="transactions_non_supportees")

        # Re-vérification sous verrou (idempotence)
        acces.ExecuterReq("""SELECT IDcotisation FROM cotisations
        WHERE IDindividu=%d AND IDtype_cotisation=%d AND date_debut<='%s' AND date_fin>='%s';"""
                          % (IDtitulaire, config["IDtype_cotisation"], date_debut, date_debut))
        if acces.ResultatReq():
            return {"statut": STATUT_RIEN, "motif": "adhesion_deja_valide"}

        # Aucune adhésion ne doit chevaucher la période à créer, y compris une
        # adhésion future déjà enregistrée : la situation est laissée à vérifier.
        acces.ExecuterReq("""SELECT IDcotisation, date_debut, date_fin FROM cotisations
        WHERE IDindividu=%d AND IDtype_cotisation=%d AND date_debut<='%s' AND date_fin>='%s'
        ORDER BY date_debut, IDcotisation;"""
                          % (IDtitulaire, config["IDtype_cotisation"], date_fin, date_debut))
        chevauchements = [(ID, _en_date(debut), _en_date(fin)) for ID, debut, fin in acces.ResultatReq()]
        if chevauchements:
            return dict(periode, statut=STATUT_A_VERIFIER, motif="chevauchement", chevauchements=chevauchements)

        # Au plus une adhésion à venir : une participation plus lointaine attend
        # qu'une prochaine réconciliation la trouve sans adhésion à venir.
        if date_debut > date_reference:
            acces.ExecuterReq("""SELECT IDcotisation FROM cotisations
            WHERE IDindividu=%d AND IDtype_cotisation=%d AND date_debut>'%s';"""
                              % (IDtitulaire, config["IDtype_cotisation"], date_reference))
            if acces.ResultatReq():
                return {"statut": STATUT_RIEN, "motif": "adhesion_a_venir_existante"}

        if _periode_verrouillee(acces, date_reference):
            return dict(periode, statut=STATUT_A_VERIFIER, motif="periode_verrouillee")

        IDcompte_payeur, IDfamille_payeur = titulaire["IDcompte_payeur"], titulaire["IDfamille"]

        label = config["label_prestation"] or u"%s - %s" % (config["nom_type"], config["nom_unite"])
        observations = u"%s Créée automatiquement le %s à partir de la participation du %s (%s %s, individu %d)." % (
            MARQUEUR_AUTO, date_reference, date_debut, participation["source"], participation["id"], IDindividu)

        try:
            IDcotisation = acces.Inserer("cotisations", [
                ("IDfamille", None),
                ("IDindividu", IDtitulaire),
                ("IDtype_cotisation", config["IDtype_cotisation"]),
                ("IDunite_cotisation", config["IDunite_cotisation"]),
                ("date_saisie", str(date_reference)),
                ("IDutilisateur", IDutilisateur),
                ("date_creation_carte", None),
                ("numero", None),
                ("date_debut", str(date_debut)),
                ("date_fin", str(date_fin)),
                ("observations", observations),
                ("activites", None),
            ])
            IDprestation = acces.Inserer("prestations", [
                ("IDcompte_payeur", IDcompte_payeur),
                ("date", str(date_reference)),
                ("categorie", "cotisation"),
                ("label", label),
                ("montant_initial", config["montant"]),
                ("montant", config["montant"]),
                ("IDfamille", IDfamille_payeur),
                ("IDindividu", IDtitulaire),
                ("date_valeur", str(date_reference)),
            ])
            acces.Modifier("UPDATE cotisations SET IDprestation=? WHERE IDcotisation=?", (IDprestation, IDcotisation))
            maintenant = datetime.datetime.now()
            acces.Inserer("historique", [
                ("date", str(date_reference)),
                ("heure", maintenant.strftime("%H:%M:%S")),
                ("IDutilisateur", IDutilisateur),
                ("IDfamille", IDfamille_payeur if titulaire["structure"] else None),
                ("IDindividu", IDtitulaire),
                ("IDcategorie", 21),
                ("action", u"Saisie de la cotisation ID%d '%s' pour la période du %s au %s (création automatique)" % (
                    IDcotisation, label, date_debut.strftime("%d/%m/%Y"), date_fin.strftime("%d/%m/%Y"))),
            ])
            DB.Commit()
        except Exception:
            traceback.print_exc()
            DB.connexion.rollback()
            return dict(periode, statut=STATUT_A_VERIFIER, motif="echec_ecriture")
        return {"statut": STATUT_CREE, "IDcotisation": IDcotisation, "IDprestation": IDprestation,
                "date_debut": date_debut, "date_fin": date_fin, "IDtitulaire": IDtitulaire}
    except Exception:
        try:
            DB.connexion.rollback()
        except Exception:
            pass
        raise
    finally:
        # Fin de transaction (rien d'écrit si on n'a pas validé) puis libération.
        try:
            if getattr(DB, "connexion", None) is not None and getattr(DB.connexion, "in_transaction", False):
                DB.connexion.rollback()
        except Exception:
            pass
        if liberer is not None:
            liberer()
        DB.Close()


# ------------------------------------------------------------ réconciliation

def ReconcilierIndividu(IDindividu, date_reference=None, depuis=None, config=None, IDutilisateur=None):
    """ Crée, si nécessaire, les adhésions manquantes de cet individu pour
    ses participations réelles à partir de `depuis` (défaut : date_reference,
    donc jamais rétroactif sur l'historique). Idempotent : une seconde
    exécution ne crée rien. Ne supprime jamais rien.

    Retourne {"IDindividu", "statut", "cotisations_creees": [IDcotisation],
    "motif" (si a_verifier/configuration_invalide), "a_verifier": [...]}. """
    date_reference = _en_date(date_reference) or datetime.date.today()
    depuis = _en_date(depuis) or date_reference
    resultat = {"IDindividu": IDindividu, "statut": STATUT_RIEN, "cotisations_creees": []}

    if config is None:
        try:
            config = ResoudreConfiguration()
        except ConfigurationAdhesionInvalide as err:
            resultat.update({"statut": STATUT_CONFIG_INVALIDE, "motif": str(err), "ambigue": err.ambigue})
            return resultat

    for _i in range(_MAX_CREATIONS_PAR_APPEL):
        participation = GetProchaineDateDeclenchante(IDindividu, config, depuis=depuis, date_reference=date_reference)
        if participation is None:
            break
        creation = CreerAdhesion(IDindividu, participation, config, date_reference=date_reference, IDutilisateur=IDutilisateur)
        if creation["statut"] == STATUT_CREE:
            resultat["cotisations_creees"].append(creation["IDcotisation"])
            resultat["statut"] = STATUT_CREE
            continue
        if creation["statut"] == STATUT_A_VERIFIER:
            resultat.update({"statut": STATUT_A_VERIFIER, "motif": creation["motif"],
                             "date_debut": creation.get("date_debut"), "date_fin": creation.get("date_fin"),
                             "chevauchements": creation.get("chevauchements", []),
                             "IDtitulaire": creation.get("IDtitulaire", IDindividu)})
        elif creation.get("motif"):
            resultat["motif"] = creation["motif"]
        break

    # Évaluation des adhésions automatiques de chaque titulaire concerné.
    activites = GetActivitesConcernees(config["IDtype_cotisation"])
    titulaires = {IDindividu}
    for participation in GetParticipations(IDindividu, activites, depuis):
        titulaires.add(ResoudreTitulaire(IDindividu, participation)["IDtitulaire"])
    resultat["a_verifier"] = []
    for IDtitulaire in sorted(titulaires):
        resultat["a_verifier"].extend(EvaluerAdhesionsAutomatiques(IDtitulaire, config))
    return resultat


def ReconcilierIndividus(liste_individus, date_reference=None, depuis=None, IDutilisateur=None):
    """ ReconcilierIndividu pour plusieurs individus (configuration résolue
    une seule fois, chaque individu dédoublonné). `depuis` peut être une date
    commune ou un dict {IDindividu: date}. Retourne {IDindividu: résultat}. """
    try:
        config = ResoudreConfiguration()
    except ConfigurationAdhesionInvalide as err:
        return {ID: {"IDindividu": ID, "statut": STATUT_CONFIG_INVALIDE, "motif": str(err), "ambigue": err.ambigue,
                     "cotisations_creees": []}
                for ID in set(liste_individus)}
    resultats = {}
    for IDindividu in sorted(set(liste_individus)):
        depuis_individu = depuis.get(IDindividu) if isinstance(depuis, dict) else depuis
        resultats[IDindividu] = ReconcilierIndividu(IDindividu, date_reference=date_reference, depuis=depuis_individu,
                                                    config=config, IDutilisateur=IDutilisateur)
    return resultats


def ReconcilierSansEchec(liste_individus, date_reference=None, depuis=None, IDutilisateur=None):
    """ Point d'entrée pour les hooks : n'interrompt jamais l'appelant.
    En cas d'exception, le résultat contient la clé CLE_ERREUR afin que
    l'appelant la signale (voir MessagesAVerifier). """
    try:
        return ReconcilierIndividus(liste_individus, date_reference=date_reference, depuis=depuis, IDutilisateur=IDutilisateur)
    except Exception as err:
        traceback.print_exc()
        return {CLE_ERREUR: {"IDindividu": None, "statut": STATUT_ERREUR, "motif": u"%s" % err,
                             "individus": sorted(set(liste_individus)), "cotisations_creees": []}}


# ----------------------------------------------------------------- annulation

def EvaluerAdhesionsAutomatiques(IDindividu, config=None):
    """ Évalue, sans rien modifier ni supprimer, les adhésions créées
    automatiquement (marque MARQUEUR_AUTO) pour cet individu.

    - une participation réelle reste dans [date_debut, date_fin] : l'adhésion
      est conservée (jamais rattachée à UNE réservation particulière) ;
    - plus aucune participation :
        - prestation facturée (IDfacture) ou ventilée sur un règlement :
          aucune suppression automatique ;
        - sinon, Noethys ne permet pas de démontrer sans ambiguïté que
          l'adhésion n'est plus justifiée (rien ne trace la réservation
          d'origine, une participation peut avoir été saisie ailleurs) :
          statut `a_verifier`, aucune suppression.

    Retourne la liste des adhésions NON justifiées, chacune :
    {"IDcotisation", "statut": "a_verifier", "motif": "facturee_ou_reglee"|"non_demontrable"}. """
    if config is None:
        try:
            config = ResoudreConfiguration()
        except ConfigurationAdhesionInvalide:
            return []
    activites = GetActivitesConcernees(config["IDtype_cotisation"])
    participants = _ParticipantsDuTitulaire(IDindividu)
    a_verifier = []
    for adhesion in GetAdhesions(IDindividu, config["IDtype_cotisation"]):
        if MARQUEUR_AUTO not in (adhesion["observations"] or ""):
            continue
        if any(GetParticipations(ID, activites, adhesion["date_debut"], adhesion["date_fin"]) for ID in participants):
            continue
        facturee_ou_reglee = False
        if adhesion["IDprestation"]:
            lignes = _lire("SELECT IDfacture FROM prestations WHERE IDprestation=%d;" % adhesion["IDprestation"])
            facturee_ou_reglee = any(ligne[0] for ligne in lignes)
            if not facturee_ou_reglee:
                lignes = _lire("SELECT SUM(montant) FROM ventilation WHERE IDprestation=%d;" % adhesion["IDprestation"])
                facturee_ou_reglee = any(ligne[0] for ligne in lignes)
        a_verifier.append({
            "IDcotisation": adhesion["IDcotisation"],
            "IDtitulaire": IDindividu,
            "date_debut": adhesion["date_debut"],
            "date_fin": adhesion["date_fin"],
            "statut": STATUT_A_VERIFIER,
            "motif": "facturee_ou_reglee" if facturee_ou_reglee else "non_demontrable",
        })
    return a_verifier


# ------------------------------------------------------------ signalement

_LIBELLES_MOTIFS = {
    "periode_verrouillee": u"la période de gestion est verrouillée",
    "payeur_indeterminable": u"le payeur ne peut pas être déterminé (aucune famille ou plusieurs familles possibles)",
    "echec_ecriture": u"l'écriture en base a échoué",
    "titulaire_ambigu": u"la famille compte plusieurs personnes morales titulaires : le titulaire de l'adhésion ne peut pas être choisi",
    "verrou_indisponible": u"une autre sauvegarde traitait la même personne au même moment ; relancez la sauvegarde",
    "transactions_non_supportees": u"la base MySQL n'utilise pas de tables transactionnelles (InnoDB) : création automatique désactivée",
    "facturee_ou_reglee": u"elle n'a plus de participation, mais sa prestation est facturée ou réglée : aucune suppression automatique",
    "non_demontrable": u"elle n'a plus de participation sur sa période : à confirmer avant toute suppression manuelle",
}


def _date_fr(valeur):
    valeur = _en_date(valeur)
    return valeur.strftime("%d/%m/%Y") if valeur else u"?"


def _noms_individus(liste_ids):
    ids = sorted({int(ID) for ID in liste_ids if ID is not None})
    if not ids:
        return {}
    lignes = _lire("SELECT IDindividu, nom, prenom FROM individus WHERE IDindividu IN %s;" % _liste_sql(ids))
    return {ID: u" ".join(x for x in (nom, prenom) if x) or u"Individu %d" % ID for ID, nom, prenom in lignes}


def ElementsAVerifier(resultats):
    """ Liste à plat des situations à signaler dans un résultat de
    ReconcilierIndividus/ReconcilierSansEchec :
    [{"IDindividu", "nom", "texte", "date_debut", "date_fin", "motif"}].
    Une configuration simplement absente n'est pas signalée ; une configuration
    ambiguë l'est une seule fois. Ne modifie rien. """
    resultats = resultats or {}
    elements = []
    erreur = resultats.get(CLE_ERREUR)
    if erreur:
        elements.append({"IDindividu": None, "nom": u"", "date_debut": None, "date_fin": None, "motif": STATUT_ERREUR,
                         "texte": u"La vérification automatique des adhésions a échoué : %s. "
                                  u"Les adhésions des personnes concernées doivent être contrôlées manuellement." % erreur["motif"]})
    individus = [r for cle, r in resultats.items() if cle != CLE_ERREUR]
    noms = _noms_individus([r["IDindividu"] for r in individus]
                           + [r.get("IDtitulaire") for r in individus]
                           + [e.get("IDtitulaire") for r in individus for e in r.get("a_verifier", [])])

    def titulaire_de(ID, IDtitulaire):
        """ Nom du titulaire, avec la personne qui participe s'il diffère. """
        if IDtitulaire in (None, ID):
            return noms.get(ID, u"Individu %s" % ID)
        return u"%s (participation de %s)" % (noms.get(IDtitulaire, u"Individu %s" % IDtitulaire), noms.get(ID, u"Individu %s" % ID))
    config_signalee = False
    for r in sorted(individus, key=lambda r: (noms.get(r["IDindividu"], u""), r["IDindividu"])):
        ID = r["IDindividu"]
        nom = noms.get(ID, u"Individu %s" % ID)
        if r.get("statut") == STATUT_CONFIG_INVALIDE:
            if r.get("ambigue") and not config_signalee:
                config_signalee = True
                elements.append({"IDindividu": None, "nom": u"", "date_debut": None, "date_fin": None, "motif": STATUT_CONFIG_INVALIDE,
                                 "texte": u"Adhésion automatique désactivée : paramétrage ambigu. %s" % r["motif"]})
            continue
        if r.get("statut") == STATUT_A_VERIFIER:
            periode = u"du %s au %s" % (_date_fr(r.get("date_debut")), _date_fr(r.get("date_fin")))
            if r["motif"] == "chevauchement":
                existantes = u", ".join(u"du %s au %s" % (_date_fr(debut), _date_fr(fin)) for _ID, debut, fin in r.get("chevauchements", []))
                raison = u"elle chevaucherait l'adhésion déjà enregistrée %s" % existantes
            else:
                raison = _LIBELLES_MOTIFS.get(r["motif"], r["motif"])
            elements.append({"IDindividu": r.get("IDtitulaire") or ID, "nom": nom, "date_debut": r.get("date_debut"),
                             "date_fin": r.get("date_fin"), "motif": r["motif"],
                             "texte": u"%s : adhésion %s non créée, %s." % (titulaire_de(ID, r.get("IDtitulaire")), periode, raison)})
        for evaluation in r.get("a_verifier", []):
            periode = u"du %s au %s" % (_date_fr(evaluation.get("date_debut")), _date_fr(evaluation.get("date_fin")))
            IDtitulaire = evaluation.get("IDtitulaire", ID)
            elements.append({"IDindividu": IDtitulaire, "nom": noms.get(IDtitulaire, nom), "date_debut": evaluation.get("date_debut"),
                             "date_fin": evaluation.get("date_fin"), "motif": evaluation["motif"],
                             "texte": u"%s : adhésion automatique %s à vérifier, %s." % (
                                 noms.get(IDtitulaire, nom), periode, _LIBELLES_MOTIFS.get(evaluation["motif"], evaluation["motif"]))})
    return elements


def MessagesAVerifier(resultats):
    """ Textes lisibles (personne, période, motif) des situations à vérifier. """
    return [element["texte"] for element in ElementsAVerifier(resultats)]


def JournaliserAVerifier(resultats, IDutilisateur=None):
    """ Trace les situations à vérifier dans l'historique de chaque personne,
    pour les sauvegardes sans opérateur (badgeage, synchronisation). Écrit
    uniquement dans `historique`. Retourne le nombre de lignes écrites. """
    elements = ElementsAVerifier(resultats)
    if not elements:
        return 0
    maintenant = datetime.datetime.now()
    DB = GestionDB.DB()
    try:
        for element in elements:
            action = u"Adhésion automatique à vérifier : %s" % element["texte"]
            DB.ReqInsert("historique", [
                ("date", str(maintenant.date())),
                ("heure", maintenant.strftime("%H:%M:%S")),
                ("IDutilisateur", IDutilisateur),
                ("IDfamille", None),
                ("IDindividu", element["IDindividu"]),
                ("IDcategorie", 21),
                ("action", action[:495]),
            ], commit=False)
        DB.Commit()
    finally:
        DB.Close()
    return len(elements)

