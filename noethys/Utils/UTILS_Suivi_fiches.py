# -*- coding: utf-8 -*-
"""Suivi des fiches Pêle-Mêle reçues, sur tables Noethys existantes (#436).

Aucune information médicale détaillée n'est inscrite dans l'historique.
L'enregistrement d'une période AEEH demande un justificatif vérifié.
Aucune mutation du statut tri-état individus.aeeh ni des vaccins/PAI.
"""
from datetime import date, datetime

from Utils import UTILS_AEEH_Periodes, UTILS_Reception_fiches

CATEGORIE_PERIODE_AEEH = 40
CATEGORIE_CONFIRMATION_PARENT = 41
SOURCES = ("papier", "pieces")


class ControleFicheInvalide(ValueError):
    pass


def _identifiant(valeur, etiquette):
    if type(valeur) is not int or valeur <= 0:
        raise ControleFicheInvalide("%s invalide" % etiquette)
    return valeur


def _source(valeur):
    if type(valeur) is not str or valeur not in SOURCES:
        raise ControleFicheInvalide("Source de fiche non renseignée ou inconnue")
    return valeur


def _date(valeur, facultative=False):
    try:
        return UTILS_Reception_fiches._date(valeur, facultative=facultative)
    except UTILS_Reception_fiches.ReceptionFicheInvalide as err:
        raise ControleFicheInvalide(str(err)) from err


def _ouvrir(DB):
    if DB is not None:
        return DB, False
    import GestionDB
    db = GestionDB.DB()
    if getattr(db, "echec", 0):
        raise ControleFicheInvalide("Impossible d'ouvrir la base Noethys")
    return db, True


def _executer(db, requete, valeurs=()):
    if db.isNetwork:
        requete = requete.replace("?", "%s")
    db.cursor.execute(requete, valeurs)


def _verrouiller_enfant(db, IDindividu):
    # Verrou sur la ligne enfant avant le contrôle des périodes.
    # SQLite : blocage des écrivains concurrents ; MySQL : verrou ligne.
    if not db.isNetwork:
        db.cursor.execute("BEGIN IMMEDIATE")
        requete = "SELECT IDindividu FROM individus WHERE IDindividu=?"
    else:
        requete = "SELECT IDindividu FROM individus WHERE IDindividu=? FOR UPDATE"
    _executer(db, requete, (IDindividu,))
    if db.cursor.fetchone() is None:
        raise ControleFicheInvalide("Enfant introuvable dans Noethys")


def _historiser(db, IDindividu, IDutilisateur, categorie, action, IDdonnee=None):
    maintenant = datetime.now()
    _executer(db, """INSERT INTO historique
        (date, heure, IDutilisateur, IDfamille, IDindividu, IDcategorie, action, IDdonnee)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (
        maintenant.date().isoformat(), maintenant.strftime("%H:%M:%S"),
        IDutilisateur, None, IDindividu, categorie, action, IDdonnee,
    ))


def EnregistrerPeriodeVerifiee(IDindividu, IDutilisateur, date_debut, date_fin=None,
                                justificatif_verifie=False, source=None,
                                fin_non_precisee_confirmee=False, DB=None):
    """Enregistre uniquement une période réellement vérifiée, puis son audit.

    Fin absente refusée, sauf si l'opérateur confirme expressément que le
    document ne précise aucune échéance. Ne modifie jamais individus.aeeh.
    """
    _identifiant(IDindividu, "IDindividu")
    _identifiant(IDutilisateur, "IDutilisateur")
    _source(source)
    if justificatif_verifie is not True:
        raise ControleFicheInvalide("Justificatif AEEH non vérifié")
    if type(fin_non_precisee_confirmee) is not bool:
        raise ControleFicheInvalide("Confirmation de fin de droit invalide")
    debut = _date(date_debut)
    fin = _date(date_fin, facultative=True)
    if fin is None and not fin_non_precisee_confirmee:
        raise ControleFicheInvalide("Date de fin absente : vérification explicite requise")
    if fin is not None and fin_non_precisee_confirmee:
        raise ControleFicheInvalide("Fin datée et sans échéance : indications contradictoires")
    if fin is not None and fin < debut:
        raise ControleFicheInvalide("La fin précède le début du droit")

    db, proprietaire = _ouvrir(DB)
    try:
        _verrouiller_enfant(db, IDindividu)
        # Réutilise le contrôle d'intervalles Noethys avec la même transaction.
        UTILS_AEEH_Periodes.ValiderPeriode(
            IDindividu, debut.isoformat(), fin.isoformat() if fin else None, DB=db,
        )
        _executer(db, "INSERT INTO aeeh_periodes (IDindividu, date_debut, date_fin) VALUES (?, ?, ?)",
                  (IDindividu, debut.isoformat(), fin.isoformat() if fin else None))
        IDperiode = db.cursor.lastrowid
        if type(IDperiode) is not int or IDperiode <= 0:
            raise ControleFicheInvalide("L'insertion AEEH n'a pas fourni d'identifiant")
        action = "AEEH : période contrôlée sur justificatif (%s au %s), source %s" % (
            debut.isoformat(), fin.isoformat() if fin else "non précisée", source)
        _historiser(db, IDindividu, IDutilisateur, CATEGORIE_PERIODE_AEEH,
                    action, IDdonnee=IDperiode)
        db.Commit()
        return IDperiode
    except Exception:
        db.connexion.rollback()
        raise
    finally:
        if proprietaire:
            db.Close()


def EnregistrerConfirmationParentale(IDindividu, IDutilisateur, rubriques,
                                     source=None, fiche_signee=False,
                                     document_relu=False, date_parent=None,
                                     IDpiece=None, DB=None):
    """Trace la déclaration parentale reçue, pas une validation médicale.

    La date de réception est celle de l'événement historique. La date de
    signature parentale, si connue, reste distincte. Aucune donnée de santé
    détaillée n'est conservée ici.
    """
    _identifiant(IDindividu, "IDindividu")
    _identifiant(IDutilisateur, "IDutilisateur")
    _source(source)
    if fiche_signee is not True or document_relu is not True:
        raise ControleFicheInvalide("Fiche parentale signée et relue requise")
    if not isinstance(rubriques, (list, tuple)) or not rubriques:
        raise ControleFicheInvalide("Aucune rubrique parentale confirmée")
    if (any(type(r) is not str or r not in UTILS_Reception_fiches.RUBRIQUES_MEDICALES
            for r in rubriques) or len(set(rubriques)) != len(rubriques)):
        raise ControleFicheInvalide("Rubrique médicale absente, dupliquée ou inconnue")
    if IDpiece is not None:
        _identifiant(IDpiece, "IDpiece")
    if date_parent is not None:
        date_parent = _date(date_parent)
        if date_parent > date.today():
            raise ControleFicheInvalide("Date parentale dans le futur")
    action = ("Fiche enfant : déclaration parentale relue ; rubriques %s ; "
              "source %s ; signature %s ; justificatifs non validés") % (
                  ", ".join(rubriques), source,
                  date_parent.isoformat() if date_parent else "non datée")
    if len(action) >= 500:
        raise ControleFicheInvalide("Historique trop long")
    db, proprietaire = _ouvrir(DB)
    try:
        _verrouiller_enfant(db, IDindividu)
        _historiser(db, IDindividu, IDutilisateur, CATEGORIE_CONFIRMATION_PARENT,
                    action, IDdonnee=IDpiece)
        db.Commit()
        return True
    except Exception:
        db.connexion.rollback()
        raise
    finally:
        if proprietaire:
            db.Close()


def GetDerniereConfirmationParentale(IDindividu, DB=None):
    """Dernière réception contrôlée, sans présumer du statut vaccinal/PAI."""
    _identifiant(IDindividu, "IDindividu")
    db, proprietaire = _ouvrir(DB)
    try:
        _executer(db, """SELECT date, heure, IDutilisateur, action, IDdonnee
            FROM historique WHERE IDindividu=? AND IDcategorie=?
            ORDER BY date DESC, heure DESC, IDaction DESC LIMIT 1""",
            (IDindividu, CATEGORIE_CONFIRMATION_PARENT))
        resultat = db.cursor.fetchone()
        if resultat is None:
            return None
        return dict(zip(("date_reception", "heure", "IDutilisateur",
                         "description", "IDpiece"), resultat))
    finally:
        if proprietaire:
            db.Close()
