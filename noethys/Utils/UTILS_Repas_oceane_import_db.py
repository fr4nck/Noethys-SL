# -*- coding: utf-8 -*-
"""Import transactionnel des menus Océane dans les tables natives de Noethys.

Aucune nouvelle table. Conflits refusés, relecture sans doublon, aucun
écrasement d'un menu déjà saisi par l'équipe.
"""
from Utils import UTILS_Repas_oceane_publication as P


def _valider_id(ident):
    if type(ident) is not int or ident <= 0:
        raise ValueError("Choisissez un restaurateur Noethys existant")
    return ident


def LireEtat(db, restaurateur, menus):
    _valider_id(restaurateur)
    menus = P.PreparerMenus(menus)
    if getattr(db, "echec", 0):
        raise RuntimeError("Base Noethys indisponible")
    p = "%s" if db.isNetwork else "?"
    db.cursor.execute("SELECT IDcategorie, nom FROM menus_categories")
    categories = db.cursor.fetchall()
    db.cursor.execute(
        "SELECT IDmenu, IDcategorie, date, texte FROM menus "
        "WHERE IDrestaurateur=" + p + " AND date>=" + p +
        " AND date<=" + p,
        (restaurateur, min(menus), max(menus)))
    existants = db.cursor.fetchall()
    return P.PlanifierImport(menus, categories, existants)


def Enregistrer(db, restaurateur, menus):
    """Enregistre uniquement après confirmation explicite par l'interface.

    Toutes les créations sont dans une seule transaction. En cas de conflit,
    rien n'est modifié. ReqInsert sans commit utilise le fonctionnement
    SQLite/MySQL natif de GestionDB.
    """
    _valider_id(restaurateur)
    menus = P.PreparerMenus(menus)
    plan = LireEtat(db, restaurateur, menus)
    if plan["conflits"]:
        raise ValueError(
            "%d menu(s) déjà saisi(s) diffèrent des menus importés : "
            "aucune modification. Corrigez-les manuellement." %
            len(plan["conflits"]))
    if not plan["ajouter"] and not plan["creer_categories"]:
        return {"ajoutes": 0, "identiques": len(plan["identiques"]),
                "categories_creees": 0}
    try:
        categories = dict(plan["categories_existantes"])
        for composante in plan["creer_categories"]:
            nouvel_id = db.ReqInsert("menus_categories", [
                ("nom", P.LIBELLES[composante]),
                ("ordre", P.COMPOSANTES.index(composante) + 1),
            ], commit=False)
            if type(nouvel_id) is not int or nouvel_id <= 0:
                raise RuntimeError("Échec de création de la catégorie de menu")
            categories[composante] = nouvel_id
        for composante, jour, texte in plan["ajouter"]:
            nouvel_id = db.ReqInsert("menus", [
                ("IDrestaurateur", restaurateur),
                ("IDcategorie", categories[composante]),
                ("date", jour.isoformat()),
                ("texte", texte),
            ], commit=False)
            if type(nouvel_id) is not int or nouvel_id <= 0:
                raise RuntimeError("Échec d'insertion du menu")
        db.Commit()
    except Exception:
        db.connexion.rollback()
        raise
    return {
        "ajoutes": len(plan["ajouter"]),
        "identiques": len(plan["identiques"]),
        "categories_creees": len(plan["creer_categories"]),
    }
