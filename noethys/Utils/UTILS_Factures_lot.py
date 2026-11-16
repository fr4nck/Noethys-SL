# -*- coding: utf-8 -*-
"""Emission de factures atomique, compatible SQLite et MySQL 5.7.

Aucun acces a une base n'est effectue par import. L'appelant fournit une
connexion Noethys et une liste de factures deja acceptees par l'operateur.
"""
import hashlib
import re


class EmissionFacturesImpossible(RuntimeError):
    """Ecriture refusee, sans exposer de requete SQL ou de donnees personnelles."""


def _prefixe_sql(base, prefixe):
    if prefixe is None:
        return "IDprefixe IS NULL", ()
    return "IDprefixe=" + ("%s" if base.isNetwork else "?"), (int(prefixe),)


def _verifier_transactions_mysql(base):
    base.cursor.execute(
        "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() "
        "AND TABLE_NAME IN ('factures', 'prestations')")
    moteurs = {str(nom).lower(): str(moteur).upper()
               for nom, moteur in base.cursor.fetchall()}
    if moteurs != {"factures": "INNODB", "prestations": "INNODB"}:
        raise EmissionFacturesImpossible(
            "Emission refusee : les deux tables financieres doivent etre transactionnelles (InnoDB).")


def _preparer(factures, prefixe):
    if not factures:
        return []
    deja = set()
    result = []
    for ligne in factures:
        donnees = list(ligne["champs"])
        champs = [cle for cle, _ in donnees]
        if len(champs) != len(set(champs)) or any(
                not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", cle) for cle in champs):
            raise EmissionFacturesImpossible("Structure de facture incorrecte")
        valeurs = dict(donnees)
        payeur = int(ligne["IDcompte_payeur"])
        if payeur <= 0 or valeurs.get("IDcompte_payeur") != payeur or valeurs.get("IDprefixe") != prefixe:
            raise EmissionFacturesImpossible("Identification de facture incoherente")
        if "numero" not in valeurs:
            raise EmissionFacturesImpossible("Numero de facture absent")
        prestations = [int(idp) for idp in ligne["prestations"]]
        if any(idp <= 0 or idp in deja for idp in prestations):
            raise EmissionFacturesImpossible("Prestation double ou invalide dans le lot")
        deja.update(prestations)
        result.append((donnees, payeur, prestations))
    return result


def EnregistrerLot(base, factures, prefixe=None, premier_numero=None, attente_verrou=15):
    """Enregistre la totalite du lot, ou aucune facture.

    Pour MySQL, GET_LOCK serialise les clients de cette version sur la base et
    le prefixe. Cette garantie ne peut proteger les anciens clients qui
    n'utilisent pas le verrou nomme : mise a jour de tous les postes requise.
    """
    candidats = _preparer(factures, prefixe)
    if not candidats:
        return []
    if premier_numero is not None:
        try:
            premier_numero = int(premier_numero)
        except (TypeError, ValueError):
            raise EmissionFacturesImpossible("Numero initial de facture invalide")
        if premier_numero <= 0:
            raise EmissionFacturesImpossible("Numero initial de facture invalide")
    curseur = base.cursor
    verrou = None
    transaction = False
    commit_tente = False
    try:
        if getattr(base, "echec", 0):
            raise EmissionFacturesImpossible("Connexion de facturation indisponible")
        if base.isNetwork:
            _verifier_transactions_mysql(base)
            curseur.execute("SELECT DATABASE()")
            schema = curseur.fetchone()[0]
            if not schema:
                raise EmissionFacturesImpossible("Base de facturation indeterminee")
            cle = "%s:%s" % (schema, prefixe)
            verrou = "noethys_fact_" + hashlib.sha256(cle.encode("utf-8")).hexdigest()[:32]
            curseur.execute("SELECT GET_LOCK(%s, %s)", (verrou, int(attente_verrou)))
            if curseur.fetchone()[0] != 1:
                raise EmissionFacturesImpossible("Verrou de numerotation indisponible")
            transaction = True
            curseur.execute("START TRANSACTION")
        else:
            curseur.execute("BEGIN IMMEDIATE")
            transaction = True

        condition, args = _prefixe_sql(base, prefixe)
        curseur.execute("SELECT MAX(numero) FROM factures WHERE " + condition, args)
        maximum = curseur.fetchone()[0]
        debut = premier_numero if premier_numero is not None else int(maximum or 0) + 1
        if debut <= 0:
            raise EmissionFacturesImpossible("Numero de facture hors limites")
        marques = "%s" if base.isNetwork else "?"
        curseur.execute(
            "SELECT numero FROM factures WHERE " + condition +
            " AND numero >= " + marques + " AND numero < " + marques,
            args + (debut, debut + len(candidats)))
        if bool(curseur.fetchall()):
            raise EmissionFacturesImpossible("Numero de facture deja utilise dans ce prefixe")

        identifiants = []
        for index, (donnees, payeur, prestations) in enumerate(candidats):
            valeurs = dict(donnees)
            valeurs["numero"] = debut + index
            colonnes = list(valeurs)
            curseur.execute(
                "INSERT INTO factures (" + ", ".join(colonnes) + ") VALUES (" +
                ", ".join([marques] * len(colonnes)) + ")",
                tuple(valeurs[col] for col in colonnes))
            ident = curseur.lastrowid
            if not ident:
                raise EmissionFacturesImpossible("Facture non enregistree")
            for prestation in prestations:
                curseur.execute(
                    "UPDATE prestations SET IDfacture=" + marques +
                    " WHERE IDprestation=" + marques +
                    " AND IDcompte_payeur=" + marques + " AND IDfacture IS NULL",
                    (ident, prestation, payeur))
                if curseur.rowcount != 1:
                    raise EmissionFacturesImpossible(
                        "Une prestation a change ou est deja facturee")
            identifiants.append(int(ident))
        commit_tente = True
        base.connexion.commit()
        transaction = False
        return identifiants
    except Exception as err:
        if commit_tente:
            raise EmissionFacturesImpossible(
                "Resultat d emission incertain apres COMMIT : controler les factures avant toute relance") from None
        if transaction:
            try:
                base.connexion.rollback()
            except Exception:
                raise EmissionFacturesImpossible(
                    "Resultat d'emission incertain : verifier la base avant toute relance") from None
        if isinstance(err, EmissionFacturesImpossible):
            raise
        raise EmissionFacturesImpossible(
            "Ecriture de facture interrompue (%s). Aucune relance automatique." % type(err).__name__) from None
    finally:
        if verrou is not None:
            try:
                curseur.execute("SELECT RELEASE_LOCK(%s)", (verrou,))
                curseur.fetchone()
            except Exception:
                # Le client est ouvert sans pool : sa fermeture par l'appelant
                # garantit la liberation de la connexion et de ses verrous.
                pass