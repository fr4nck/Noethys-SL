# -*- coding: utf-8 -*-
"""Échéances locales des quotients, sans recalcul des prestations/factures."""
import datetime


def DateFinProposee(date_debut):
    """Fin inclusive précédant le prochain 10 janvier ou 10 septembre."""
    janvier = datetime.date(date_debut.year, 1, 10)
    septembre = datetime.date(date_debut.year, 9, 10)
    if date_debut < janvier:
        prochaine = janvier
    elif date_debut < septembre:
        prochaine = septembre
    else:
        prochaine = datetime.date(date_debut.year + 1, 1, 10)
    return prochaine - datetime.timedelta(days=1)


def _Date(valeur):
    if isinstance(valeur, datetime.datetime):
        return valeur.date()
    if isinstance(valeur, datetime.date):
        return valeur
    return datetime.datetime.strptime(str(valeur), "%Y-%m-%d").date()


def LireChevauchements(DB, IDfamille, IDtype_quotient, IDquotient, debut, fin, verrouiller=False):
    marque = "%s" if DB.isNetwork else "?"
    sql = """SELECT IDquotient, date_debut, date_fin, observations
        FROM quotients WHERE IDfamille=? AND IDquotient<>?
        AND (IDtype_quotient=? OR (IDtype_quotient IS NULL AND ? IS NULL))
        AND date_debut<=? AND date_fin>=? ORDER BY IDquotient"""
    if DB.isNetwork and verrouiller:
        sql += " FOR UPDATE"
    DB.cursor.execute(sql.replace("?", marque),
                      (IDfamille, IDquotient or 0, IDtype_quotient,
                       IDtype_quotient, str(fin), str(debut)))
    return [(ID, _Date(d), _Date(f), obs or "")
            for ID, d, f, obs in DB.cursor.fetchall()]


def PrecedentACloturer(chevauchements, date_debut):
    """Une seule période antérieure peut être raccourcie sans la supprimer."""
    if len(chevauchements) == 1 and chevauchements[0][1] < date_debut:
        return chevauchements[0]
    return None


def Enregistrer(DB, donnees, IDquotient=None, precedent=None):
    """Enregistre les dates en une transaction, avec contrôle du précédent.

    DB est une connexion GestionDB dédiée. Les écritures restent limitées à
    quotients ; aucune facture ou prestation n'est modifiée.
    """
    debut, fin = donnees["date_debut"], donnees["date_fin"]
    if debut > fin:
        raise ValueError("La fin de validité doit être postérieure ou égale au début.")
    marque = "%s" if DB.isNetwork else "?"
    try:
        if DB.isNetwork and precedent is not None:
            DB.cursor.execute("SHOW TABLE STATUS LIKE 'quotients'")
            statut = DB.cursor.fetchone()
            if statut is None or str(statut[1]).lower() != "innodb":
                raise ValueError("Cette base réseau ne permet pas l'ajustement atomique du précédent. Aucun changement effectué.")
        DB.cursor.execute("START TRANSACTION" if DB.isNetwork else "BEGIN IMMEDIATE")
        actuels = LireChevauchements(DB, donnees["IDfamille"],
                                    donnees["IDtype_quotient"], IDquotient, debut, fin, verrouiller=True)
        attendus = [] if precedent is None else [precedent]
        if actuels != attendus or (precedent is not None and
                                  (IDquotient is not None or
                                   PrecedentACloturer(actuels, debut) is None)):
            raise ValueError("Les périodes ont changé ou se chevauchent. Vérifiez les quotients avant de réessayer.")
        if precedent is not None:
            ID, ancien_debut, ancienne_fin, observations = precedent
            nouvelle_fin = debut - datetime.timedelta(days=1)
            trace = "Fin ajustée de %s à %s lors du renouvellement du %s (sans recalcul des factures)." % (
                ancienne_fin.strftime("%d/%m/%Y"), nouvelle_fin.strftime("%d/%m/%Y"),
                debut.strftime("%d/%m/%Y"))
            observations = (observations + "\n" + trace).strip()
            DB.cursor.execute(
                "UPDATE quotients SET date_fin=%s, observations=%s WHERE IDquotient=%s" %
                (marque, marque, marque), (str(nouvelle_fin), observations, ID))
            if DB.cursor.rowcount != 1:
                raise ValueError("Le quotient précédent n'a pas pu être ajusté.")

        champs = ("IDfamille", "date_debut", "date_fin", "quotient", "revenu",
                  "observations", "IDtype_quotient")
        valeurs = [str(donnees[c]) if c in ("date_debut", "date_fin") else donnees[c]
                   for c in champs]
        if IDquotient is None:
            DB.cursor.execute("INSERT INTO quotients (%s) VALUES (%s)" % (
                ", ".join(champs), ", ".join([marque] * len(champs))), tuple(valeurs))
            nouveau_ID = DB.cursor.lastrowid
        else:
            DB.cursor.execute("UPDATE quotients SET %s WHERE IDquotient=%s AND IDfamille=%s" % (
                ", ".join(c + "=" + marque for c in champs), marque, marque),
                tuple(valeurs + [IDquotient, donnees["IDfamille"]]))
            # MySQL peut retourner 0 lorsqu'aucune valeur n'a changé.
            DB.cursor.execute("SELECT IDquotient FROM quotients WHERE IDquotient=%s AND IDfamille=%s" %
                              (marque, marque), (IDquotient, donnees["IDfamille"]))
            if DB.cursor.fetchone() is None:
                raise ValueError("Le quotient à modifier n'existe plus.")
            nouveau_ID = IDquotient
        DB.Commit()
        return nouveau_ID
    except Exception:
        DB.connexion.rollback()
        raise
