# -*- coding: utf-8 -*-
"""Barriere wx contre le rejeu d'une tentative de reservations incertaine.

Une ligne native parametres est commitee AVANT les effets metier. Elle reste
presente apres panne/crash et n'est retiree qu'apres finalisation SQL confirmee
ou annulation explicite avant Save_grille. Aucun effacement par expiration.
Categorie distincte des suivis emails RC9 et du protocole Connecthys.
"""
import contextlib
import uuid

import GestionDB

CATEGORIE = "noethys_sl_reservations_tentatives"


class ReconciliationRequise(RuntimeError):
    pass


def _executer(DB, sql, valeurs=()):
    if getattr(DB, "echec", 0):
        raise ReconciliationRequise("Base inaccessible")
    DB.cursor.execute(sql.replace("?", "%s") if DB.isNetwork else sql, tuple(valeurs))


def _cle(IDaction):
    if IDaction is None or int(IDaction) <= 0:
        raise ReconciliationRequise("Demande sans identifiant durable")
    return "action_%d" % int(IDaction)


def _lire(DB, IDaction):
    _executer(DB, "SELECT parametre FROM parametres WHERE categorie=? AND nom=?",
              (CATEGORIE, _cle(IDaction)))
    # Toute presence, y compris doublon ou valeur corrompue, bloque le rejeu.
    return list(DB.cursor.fetchall())


def EnAttente(IDaction):
    DB = GestionDB.DB()
    try:
        return bool(_lire(DB, IDaction))
    finally:
        DB.Close()


@contextlib.contextmanager
def _verrouiller(IDaction):
    DB = GestionDB.DB()
    verrou = None
    try:
        if getattr(DB, "isNetwork", False):
            # Verrou court, commun aux postes wx, independant du moteur SQL
            # des tables : aucun besoin de migration MyISAM -> InnoDB.
            nom = "CONCAT('noethys_resa_', LEFT(MD5(DATABASE()), 12), '_%d')" % int(IDaction)
            _executer(DB, "SELECT GET_LOCK(%s, 0)" % nom)
            obtenu = DB.cursor.fetchall()
            if not obtenu or obtenu[0][0] != 1:
                raise ReconciliationRequise("Autre tentative en cours")
            verrou = nom
            DB.connexion.commit()  # terminer une eventuelle lecture precedente
        else:
            _executer(DB, "BEGIN IMMEDIATE")
        yield DB
    except Exception:
        if getattr(DB, "connexion", None) is not None:
            DB.connexion.rollback()
        raise
    finally:
        try:
            if verrou is not None:
                _executer(DB, "SELECT RELEASE_LOCK(%s)" % verrou)
                DB.cursor.fetchall()
        finally:
            DB.Close()


def Commencer(IDaction):
    cle = _cle(IDaction)
    jeton = uuid.uuid4().hex
    with _verrouiller(IDaction) as DB:
        if _lire(DB, IDaction):
            raise ReconciliationRequise("Tentative precedente a reconcilier")
        _executer(DB, "SELECT etat FROM portail_actions WHERE IDaction=?", (IDaction,))
        lignes = DB.cursor.fetchall()
        if len(lignes) != 1 or lignes[0][0] != "attente":
            raise ReconciliationRequise("Etat durable incompatible avec un nouveau traitement")
        _executer(DB, "INSERT INTO parametres (categorie, nom, parametre) VALUES (?, ?, ?)",
                  (CATEGORIE, cle, jeton))
        DB.connexion.commit()
    return jeton


def Terminer(IDaction, jeton):
    with _verrouiller(IDaction) as DB:
        if _lire(DB, IDaction) != [(jeton,)]:
            raise ReconciliationRequise("Marqueur absent ou different : reconciliation requise")
        _executer(DB, "DELETE FROM parametres WHERE categorie=? AND nom=? AND parametre=?",
                  (CATEGORIE, _cle(IDaction), jeton))
        DB.connexion.commit()


def LireReprise(IDaction):
    """Lire le marqueur unique et l'état durable avant arbitrage opérateur.

    Ne modifie ni les consommations ni le marqueur. La prise de décision
    est séparée du contrôle du jeton, qui doit être re-vérifié avant écritures.
    """
    import re
    with _verrouiller(IDaction) as DB:
        valeurs = _lire(DB, IDaction)
        if (len(valeurs) != 1 or len(valeurs[0]) != 1 or
                not isinstance(valeurs[0][0], str) or
                re.fullmatch(r'[0-9a-f]{32}', valeurs[0][0]) is None):
            raise ReconciliationRequise(
                'Marqueur de reprise absent, dupliqué ou illisible')
        _executer(DB,
                  'SELECT etat FROM portail_actions WHERE IDaction=?',
                  (IDaction,))
        etats = list(DB.cursor.fetchall())
        if len(etats) != 1 or etats[0][0] not in ('attente', 'validation'):
            raise ReconciliationRequise(
                'État de demande non compatible avec une reprise')
        return valeurs[0][0], etats[0][0]
