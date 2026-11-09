# -*- coding: utf-8 -*-
"""Trace durable des tentatives de reservations Connecthys, sans blocage.
Le marqueur permet de reconnaitre une reprise apres interruption. Les
reservations deja enregistrees sont controlees avant toute nouvelle ecriture.
Seuls les traitements simultanes sont exclus temporairement.
La categorie reste distincte du suivi des emails acceptes.
"""

import contextlib
import re
import threading
import uuid

import GestionDB

CATEGORIE = "noethys_sl_reservations_tentatives"


class ReconciliationRequise(RuntimeError):
    pass


_ACTIFS = set()
_MUTEX = threading.Lock()


@contextlib.contextmanager
def ExecutionExclusive(IDaction):
    """Une seule execution simultanee ; aucune quarantaine apres interruption."""
    cle = _cle(IDaction)
    with _MUTEX:
        if cle in _ACTIFS:
            raise ReconciliationRequise("Traitement de cette demande deja en cours.")
        _ACTIFS.add(cle)
    DB = None
    verrou = None
    try:
        DB = GestionDB.DB()
        if getattr(DB, "echec", 0):
            raise ReconciliationRequise("Base inaccessible")
        if getattr(DB, "isNetwork", False):
            nom = ("CONCAT('noethys_resa_exec_', LEFT(MD5(DATABASE()), 12), '_%d')"
                   % int(IDaction))
            _executer(DB, "SELECT GET_LOCK(%s, 0)" % nom)
            reponse = DB.cursor.fetchall()
            if not reponse or reponse[0][0] != 1:
                raise ReconciliationRequise("Demande deja traitee par un autre poste.")
            verrou = nom
            DB.connexion.commit()
        yield
    finally:
        try:
            if DB is not None:
                try:
                    if verrou is not None:
                        try:
                            _executer(DB, "SELECT RELEASE_LOCK(%s)" % verrou)
                            DB.cursor.fetchall()
                        except Exception:
                            pass  # Close() libere aussi le verrou cote serveur.
                finally:
                    DB.Close()
        finally:
            with _MUTEX:
                _ACTIFS.discard(cle)


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


def Commencer(IDaction, avec_origine=False):
    """Reprendre librement une tentative sans effacer son historique.

    Avec avec_origine=True : (jeton, reprise). Sur un marqueur illisible,
    jeton=None et reprise=True ; l'ancienne trace reste conservee.
    """
    cle = _cle(IDaction)
    with _verrouiller(IDaction) as DB:
        valeurs = _lire(DB, IDaction)
        _executer(DB, "SELECT etat FROM portail_actions WHERE IDaction=?", (IDaction,))
        lignes = list(DB.cursor.fetchall())
        if len(lignes) != 1:
            raise ReconciliationRequise("Demande absente ou dupliquee en base")
        etat = lignes[0][0]
        if etat == "validation":
            # Une validation deja commitee n'est jamais reappliquee.
            if (len(valeurs) == 1 and len(valeurs[0]) == 1
                    and isinstance(valeurs[0][0], str)
                    and re.fullmatch(r"[0-9a-f]{32}", valeurs[0][0])):
                _executer(DB, "DELETE FROM parametres WHERE categorie=? AND nom=? AND parametre=?",
                          (CATEGORIE, cle, valeurs[0][0]))
                DB.connexion.commit()
            raise ReconciliationRequise("Demande deja validee, aucune reapplication.")
        if etat != "attente":
            raise ReconciliationRequise("Etat SQL incompatible avec un traitement")
        if valeurs:
            jeton = (valeurs[0][0] if len(valeurs) == 1 and
                     len(valeurs[0]) == 1 and
                     isinstance(valeurs[0][0], str) and
                     re.fullmatch(r"[0-9a-f]{32}", valeurs[0][0]) else None)
            DB.connexion.commit()
            return (jeton, True) if avec_origine else jeton
        jeton = uuid.uuid4().hex
        _executer(DB, "INSERT INTO parametres (categorie, nom, parametre) VALUES (?, ?, ?)",
                  (CATEGORIE, cle, jeton))
        DB.connexion.commit()
    return (jeton, False) if avec_origine else jeton


def NettoyerSiValidee(IDaction):
    """Purger uniquement une trace valide dont l'action est deja validee."""
    with _verrouiller(IDaction) as DB:
        valeurs = _lire(DB, IDaction)
        if (len(valeurs) != 1 or len(valeurs[0]) != 1 or
                not isinstance(valeurs[0][0], str) or
                re.fullmatch(r"[0-9a-f]{32}", valeurs[0][0]) is None):
            return False
        _executer(DB, "SELECT etat FROM portail_actions WHERE IDaction=?", (IDaction,))
        if list(DB.cursor.fetchall()) != [("validation",)]:
            return False
        _executer(DB, "DELETE FROM parametres WHERE categorie=? AND nom=? AND parametre=?",
                  (CATEGORIE, _cle(IDaction), valeurs[0][0]))
        DB.connexion.commit()
        return True


def Terminer(IDaction, jeton):
    if jeton is None:
        return False  # conserver un marqueur ancien/illisible sans bloquer
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
