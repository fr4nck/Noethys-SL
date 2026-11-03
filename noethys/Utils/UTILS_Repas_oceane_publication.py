# -*- coding: utf-8 -*-
"""Préparation des menus Océane : édition native Noethys et portail Connecthys.

Module pur : il ne lit aucune famille, n'écrit pas en base et n'appelle
pas le réseau. Les menus sont communs au restaurateur, jamais nominatifs.
"""
from datetime import date, datetime, timedelta
from html import escape
import re
import unicodedata

COMPOSANTES = ("entree", "plat", "garniture", "laitage", "dessert")
LIBELLES = {
    "entree": "Entrée",
    "plat": "Plat principal",
    "garniture": "Garniture",
    "laitage": "Fromage / laitage",
    "dessert": "Dessert",
}
ALIASES = {
    "entree": ("entree", "entrees", "hors d oeuvre", "hors d oeuvres"),
    "plat": ("plat", "plats", "plat principal", "plats chauds", "plat chaud"),
    "garniture": ("garniture", "garnitures", "legume", "legumes", "accompagnement", "accompagnements"),
    "laitage": ("laitage", "laitages", "produit laitier", "produits laitiers", "fromage", "fromages", "fromage laitage"),
    "dessert": ("dessert", "desserts"),
}


def _cle(texte):
    t = unicodedata.normalize("NFKD", str(texte or "").casefold())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def _jour(value):
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            raise ValueError("Date de menu invalide")
    if type(value) is not date or value.weekday() != 2:
        raise ValueError("Seuls les menus du mercredi sont pris en charge")
    return value


def PreparerMenus(menus, dates=None):
    """Renvoie les menus du mercredi non vides, vérifiés et triés.

    dates explicites : jamais de publication de l'ensemble d'un classeur
    historique par simple glisser-déposer.
    """
    if not isinstance(menus, dict) or not menus:
        raise ValueError("Classeur Océane sans menus")
    selection = set(menus) if dates is None else set(dates)
    if not selection or len(selection) > 24:
        raise ValueError("Sélectionnez entre 1 et 24 mercredis")
    if selection - set(menus):
        raise ValueError("Une date sélectionnée n'existe pas dans le classeur")
    resultat = {}
    for brut in selection:
        jour = _jour(brut)
        if jour in resultat:
            raise ValueError("Mercredi présent deux fois")
        source = menus[brut]
        if not isinstance(source, dict):
            raise ValueError("Menu fournisseur invalide")
        items = {}
        for composante in COMPOSANTES:
            valeurs = source.get(composante) or []
            if not isinstance(valeurs, (list, tuple)):
                raise ValueError("Composante de menu invalide : %s" % composante)
            textes = []
            for valeur in valeurs:
                if not isinstance(valeur, str):
                    raise ValueError("Libellé de plat invalide")
                texte = " ".join(valeur.split())
                if len(texte) > 300:
                    raise ValueError("Intitulé de plat excessif")
                if texte and texte not in textes:
                    textes.append(texte)
            items[composante] = textes
        if not any(items.values()):
            raise ValueError("Mercredi %s : aucune composante de menu" % jour)
        resultat[jour] = dict(items, source=str(source.get("source") or "Océane"))
    return dict(sorted(resultat.items()))


def TextePortail(menus):
    menus = PreparerMenus(menus)
    lignes = ["MENUS OCÉANE DE RESTAURATION", ""]
    for jour, entrees in menus.items():
        lignes.extend([u"MERCREDI %s" % jour.strftime("%d/%m/%Y"), ""])
        for nom in COMPOSANTES:
            textes = entrees[nom]
            lignes.append(u"%s : %s" % (
                LIBELLES[nom], " / ".join(textes) if textes else "Non communiqué"))
        lignes.extend(("", ""))
    lignes.append("Menus susceptibles de modifications par le restaurateur.")
    return "\n".join(lignes)


def HTMLPortail(menus):
    """HTML sûr destiné à un bloc Blog / texte existant, sans scripts ni liens."""
    menus = PreparerMenus(menus)
    morceaux = [
        '<div class="pmsl-menus-oceane">',
        '<h2>Menus des mercredis</h2>',
        '<p>Menus fournis par Océane de Restauration.</p>',
    ]
    for jour, entree in menus.items():
        morceaux.append('<h3>Mercredi %s</h3>' % jour.strftime("%d/%m/%Y"))
        morceaux.append("<ul>")
        for nom in COMPOSANTES:
            valeurs = entree[nom]
            texte = " / ".join(valeurs) if valeurs else "Non communiqué"
            morceaux.append("<li><strong>%s :</strong> %s</li>" %
                            (escape(LIBELLES[nom]), escape(texte)))
        morceaux.append("</ul>")
    morceaux.append("<p><em>Menus susceptibles de modifications.</em></p>")
    morceaux.append("</div>")
    html = "\n".join(morceaux)
    if len(html.encode("utf-8")) > 24000:
        raise ValueError("Publication trop longue : sélectionnez moins de mercredis")
    return html


def TitrePortail(menus):
    menus = PreparerMenus(menus)
    premier, dernier = min(menus), max(menus)
    if premier == dernier:
        return "Menus Océane - mercredi %s" % premier.strftime("%d/%m/%Y")
    return "Menus Océane - du %s au %s" % (
        premier.strftime("%d/%m/%Y"), dernier.strftime("%d/%m/%Y"))


def DateFinPublication(menus):
    menus = PreparerMenus(menus)
    jour = max(menus) + timedelta(days=7)
    return datetime.combine(jour, datetime.min.time()).replace(hour=23, minute=59)


def _date_enregistree(valeur):
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur)[:10])
    except ValueError:
        raise ValueError("Date de menu Noethys invalide")


def PlanifierImport(menus, categories, existants):
    """Prévol idempotent sur les tables natives menus_categories / menus.

    categories : [(IDcategorie, nom)]
    existants : [(IDmenu, IDcategorie, date, texte)] du SEUL restaurateur choisi.
    Retourne nouvelles catégories, inserts et conflits. Aucun écrasement.
    """
    menus = PreparerMenus(menus)
    cate = {}
    for ident, libelle in categories:
        if type(ident) is not int or ident <= 0:
            raise ValueError("Catégorie Noethys invalide")
        for composante, aliases in ALIASES.items():
            if _cle(libelle) in aliases:
                if composante in cate:
                    raise ValueError("Plusieurs catégories Noethys pour %s" % LIBELLES[composante])
                cate[composante] = ident
    creations = [c for c in COMPOSANTES if c not in cate]
    deja = {}
    for ident, id_categorie, jour, texte in existants:
        key = (int(id_categorie), _date_enregistree(jour))
        if key in deja:
            raise ValueError("Doublons dans les menus Noethys existants")
        deja[key] = (ident, str(texte or ""))
    ajouts, identiques, conflits = [], [], []
    for jour, menu in menus.items():
        for composante in COMPOSANTES:
            texte = " / ".join(menu[composante])
            if not texte:
                continue
            ident = cate.get(composante)
            if ident is None:
                ajouts.append((composante, jour, texte))
                continue
            actuel = deja.get((ident, jour))
            if actuel is None:
                ajouts.append((composante, jour, texte))
            elif actuel[1] == texte:
                identiques.append((composante, jour))
            else:
                conflits.append((composante, jour, actuel[1], texte))
    return {
        "categories_existantes": cate,
        "creer_categories": creations,
        "ajouter": ajouts,
        "identiques": identiques,
        "conflits": conflits,
        "jours": tuple(menus),
    }
