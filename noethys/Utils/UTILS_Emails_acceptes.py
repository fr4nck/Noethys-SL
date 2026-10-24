# -*- coding: utf-8 -*-
"""Suivi local d'une confirmation Connecthys envoyée sans éditeur.

Quand une confirmation (réponse à une demande, reçu, facture) n'est acceptée
que pour une partie des adresses de la famille, la demande reste « attente »
(aucun changement du protocole Connecthys). Le suivi conserve :
- les adresses déjà acceptées par le serveur d'envoi (jamais renvoyées) ;
- les adresses dont l'acceptation est incertaine (réponse perdue après
  transmission) : aucune relance automatique, contrôle manuel requis ;
- l'empreinte du document envoyé : un document modifié depuis est un nouvel
  envoi légitime à toutes les adresses ;
- l'indicateur « complet » : toutes les adresses acceptées.

Le suivi est conservé jusqu'à l'enregistrement de la demande validée
(EffacerConfirmationsCompletes, dans la même transaction que
portail_actions) ; seul un suivi complet est alors effacé. Une interruption
entre l'envoi et cet enregistrement ne provoque aucun renvoi.

Stockage : table native `parametres`, catégorie dédiée, valeur JSON, une ligne
par clé, écrite en une seule transaction. Cette catégorie n'est jamais lue
par la synchronisation Connecthys (catégorie `portail` uniquement) ; aucune
migration de schéma. Il ne s'agit pas d'une garantie « exactement une fois » :
le serveur de messagerie reste hors de toute transaction locale.
"""
import contextlib
import hashlib
import json
import re
import threading

import GestionDB

CATEGORIE = "noethys_sl_emails_acceptes"
DOCUMENTS = ("reponse", "recu", "facture")
_CLE = re.compile(r"^[a-z0-9_]{1,80}$")
DELAI_RESERVATION = 0  # secondes : un traitement simultané est refusé, pas attendu


class SuiviIllisible(Exception):
    """ Suivi présent mais inexploitable : aucun envoi automatique. """


class EnvoiEnCours(Exception):
    """ La même confirmation est déjà en cours de traitement. """


class Suivi(object):
    def __init__(self, acceptees=(), incertaines=(), empreinte=None, complet=False):
        self.acceptees = set(Normaliser(a) for a in acceptees if Normaliser(a))
        self.incertaines = set(Normaliser(a) for a in incertaines if Normaliser(a))
        self.empreinte = empreinte
        self.complet = bool(complet)

    def EstVide(self):
        return not (self.acceptees or self.incertaines or self.complet)

    def VersJSON(self):
        return json.dumps({"version": 2, "empreinte": self.empreinte, "complet": self.complet,
                           "acceptees": sorted(self.acceptees), "incertaines": sorted(self.incertaines)},
                          sort_keys=True)


def CleDemande(IDaction, document):
    """Clé d'une confirmation Connecthys : demande + document envoyé."""
    cle = "portail_action_%d_%s" % (int(IDaction), document)
    if not _CLE.match(cle):
        raise ValueError("Clé de suivi invalide : %r" % cle)
    return cle


def _verifier(cle):
    if not isinstance(cle, str) or not _CLE.match(cle):
        raise ValueError("Clé de suivi invalide : %r" % (cle,))


def Normaliser(adresse):
    return (adresse or u"").strip().lower()


def EmpreinteDocument(*elements):
    """ Empreinte stable d'un document (identifiants et valeurs qui le
    définissent) ; None si rien n'est connu. """
    if not elements:
        return None
    return hashlib.sha1(repr(elements).encode("utf-8")).hexdigest()


def EmpreinteLigne(table, champID, ID, champs):
    """ Empreinte d'une ligne (reçu : règlement, facture) ; None si la
    lecture échoue (empreinte inconnue : le suivi existant est conservé). """
    DB = GestionDB.DB()
    try:
        _requete(DB, "SELECT %s FROM %s WHERE %s=?" % (", ".join(champs), table, champID), [ID])
        lignes = DB.cursor.fetchall()
        return EmpreinteDocument(table, ID, [tuple(str(v) for v in ligne) for ligne in lignes])
    except Exception:
        return None
    finally:
        DB.Close()


def _requete(DB, req, valeurs=()):
    if getattr(DB, "echec", 0) == 1:
        raise RuntimeError(u"Base inaccessible : %s" % getattr(DB, "erreur", u""))
    if DB.isNetwork:
        req = req.replace("?", "%s")
    DB.cursor.execute(req, tuple(valeurs))


def _Decoder(texte):
    try:
        valeur = json.loads(texte or "")
    except ValueError:
        raise SuiviIllisible(u"Suivi illisible : %r" % ((texte or u"")[:200],))
    if isinstance(valeur, list):  # format initial : liste des adresses acceptées
        if not all(isinstance(v, str) for v in valeur):
            raise SuiviIllisible(u"Suivi illisible : adresses invalides.")
        return Suivi(acceptees=valeur)
    if (not isinstance(valeur, dict) or valeur.get("version") != 2
            or not isinstance(valeur.get("acceptees"), list) or not isinstance(valeur.get("incertaines"), list)
            or not all(isinstance(v, str) for v in valeur["acceptees"] + valeur["incertaines"])):
        raise SuiviIllisible(u"Suivi illisible : format inattendu.")
    return Suivi(valeur["acceptees"], valeur["incertaines"], valeur.get("empreinte"), valeur.get("complet"))


def LireSuivi(cle):
    """ Suivi enregistré pour cette clé (vide si aucun). Lève SuiviIllisible
    si la valeur est corrompue ou en double, et toute erreur de lecture :
    jamais « rien d'accepté » par défaut. """
    _verifier(cle)
    DB = GestionDB.DB()
    try:
        _requete(DB, "SELECT parametre FROM parametres WHERE categorie=? AND nom=?;", [CATEGORIE, cle])
        lignes = DB.cursor.fetchall()
    finally:
        DB.Close()
    if not lignes:
        return Suivi()
    if len(lignes) > 1:
        raise SuiviIllisible(u"Suivi enregistré plusieurs fois.")
    return _Decoder(lignes[0][0])


def Lire(cle):
    """Ensemble des adresses (normalisées) déjà acceptées pour cette clé."""
    return LireSuivi(cle).acceptees


def Enregistrer(cle, suivi):
    """ Remplace le suivi de cette clé en une seule transaction (une seule
    ligne). `suivi` : Suivi, ou ensemble d'adresses acceptées. """
    _verifier(cle)
    if not isinstance(suivi, Suivi):
        suivi = Suivi(acceptees=suivi)
    DB = GestionDB.DB()
    try:
        try:
            _requete(DB, "DELETE FROM parametres WHERE categorie=? AND nom=?;", [CATEGORIE, cle])
            _requete(DB, "INSERT INTO parametres (categorie, nom, parametre) VALUES (?, ?, ?);",
                     [CATEGORIE, cle, suivi.VersJSON()])
            DB.connexion.commit()
        except Exception:
            if getattr(DB, "connexion", None) is not None:
                try:
                    DB.connexion.rollback()
                except Exception:
                    pass
            raise
    finally:
        DB.Close()


def Effacer(cle):
    _verifier(cle)
    DB = GestionDB.DB()
    try:
        _requete(DB, "DELETE FROM parametres WHERE categorie=? AND nom=?;", [CATEGORIE, cle])
        DB.connexion.commit()
    finally:
        DB.Close()


def EffacerConfirmationsCompletes(DB, IDaction):
    """ Dans la transaction en cours de DB (enregistrement de la demande
    validée) : supprime le suivi des seules confirmations complètes de cette
    demande. Un suivi partiel, incertain ou illisible est conservé. """
    cles = [CleDemande(IDaction, document) for document in DOCUMENTS]
    _requete(DB, "SELECT IDparametre, parametre FROM parametres WHERE categorie=? AND nom IN (?, ?, ?);",
             [CATEGORIE] + cles)
    for IDparametre, texte in list(DB.cursor.fetchall()):
        try:
            complet = _Decoder(texte).complet
        except SuiviIllisible:
            complet = False
        if complet:
            _requete(DB, "DELETE FROM parametres WHERE IDparametre=?;", [IDparametre])


_RESERVEES = set()
_VERROU_LOCAL = threading.Lock()


@contextlib.contextmanager
def Reserver(cle):
    """ Empêche le traitement simultané d'une même confirmation : dans ce
    processus (double clic, réentrance) et, en base MySQL, entre postes
    (verrou nommé tenu pendant l'envoi). Lève EnvoiEnCours. """
    _verifier(cle)
    with _VERROU_LOCAL:
        if cle in _RESERVEES:
            raise EnvoiEnCours(cle)
        _RESERVEES.add(cle)
    DB = None
    nom = None
    try:
        DB = GestionDB.DB()
        if getattr(DB, "isNetwork", False) and getattr(DB, "echec", 0) != 1:
            nom = "CONCAT('noethys_suivi_email_', LEFT(MD5(DATABASE()), 12), '_%s')" % cle
            DB.cursor.execute("SELECT GET_LOCK(%s, %d);" % (nom, DELAI_RESERVATION))
            obtenu = DB.cursor.fetchall()
            if not obtenu or obtenu[0][0] != 1:
                nom = None
                raise EnvoiEnCours(cle)
        yield
    finally:
        try:
            if nom is not None:
                DB.cursor.execute("SELECT RELEASE_LOCK(%s);" % nom)
                DB.cursor.fetchall()
        except Exception:
            pass  # libéré de toute façon à la fermeture de la connexion
        finally:
            if DB is not None:
                DB.Close()
            with _VERROU_LOCAL:
                _RESERVEES.discard(cle)
