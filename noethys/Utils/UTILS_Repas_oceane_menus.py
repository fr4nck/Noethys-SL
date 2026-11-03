# -*- coding: utf-8 -*-
"""Import des menus Océane (fichier transmis) avec leur date et provenance.

Sont lus : "Menus Mat & prim" (choix 5 composantes) et les affichages
"Semaine NN" portant la date au mercredi G6. Les noms des plats sont
des informations, jamais des autorisations ou des régimes présumés.
"""
from datetime import date
from Utils.UTILS_Oceane_xlsx import LireClasseur, DateExcel

CATEGORIES = ("entree", "plat", "garniture", "laitage", "dessert")
OFFSETS = {
    "entree": (1, 2, 3, 4),
    "plat": (6, 7),
    "garniture": (9, 10, 11),
    "laitage": (12, 13),
    "dessert": (15, 16, 17, 18),
}


def _valeur(texte):
    if texte is None or isinstance(texte, (int, float, bool)):
        return ""
    val = " ".join(str(texte).split())
    if not val or val.upper() in ("FÉRIÉ", "FERIE", "****", "*****",
                                 "******", "AUCUN", "AUCUNE"):
        return ""
    if set(val) == {"*"}:
        return ""
    return val


def _unique(items):
    result = []
    for item in items:
        val = _valeur(item)
        if val and val not in result:
            result.append(val)
    return result


def _source_detaillee(cells, is1904):
    """Feuille de référence 5C : semaines espacées de 19 lignes."""
    menus = {}
    for ligne in range(3, 212, 19):
        jour = DateExcel(cells.get("E%d" % ligne), is1904)
        if jour is None or jour.weekday() != 2:
            continue
        comps = {nom: _unique(
            cells.get("E%d" % (ligne + off)) for off in offsets)
            for nom, offsets in OFFSETS.items()}
        if not any(comps.values()):
            continue
        menus[jour] = dict(comps, source="Menus Mat & prim")
    return menus


def _source_affichages(nom, cells, is1904):
    """Menus de l'affichage 5C ; G8 peut préciser l'entrée G7."""
    jour = DateExcel(cells.get("G6"), is1904)
    if jour is None or jour.weekday() != 2:
        return None
    entree = _unique((cells.get("G7"),))
    detail = _valeur(cells.get("G8"))
    if entree and detail:
        entree[0] += " — " + detail
    elif detail:
        entree = [detail]
    comps = {
        "entree": entree,
        "plat": _unique((cells.get("G9"), cells.get("G10"))),
        "garniture": _unique((cells.get("G11"), cells.get("G12"))),
        "laitage": _unique((cells.get("G13"), cells.get("G14"))),
        "dessert": _unique((cells.get("G15"), cells.get("G16"))),
    }
    if not any(comps.values()):
        return None
    return jour, dict(comps, source=nom)


def ChargerMenus(chemin):
    """Retourne {date: composantes et source} depuis un XLSX existant.

    Un affichage de semaine daté a priorité sur la feuille de travail pour
    la même date, mais toutes les périodes différentes sont conservées.
    """
    feuilles, is1904 = LireClasseur(chemin)
    if "Menus Mat & prim" not in feuilles and not any(
            name.startswith("Semaine ") for name in feuilles):
        raise ValueError("Le classeur ne contient pas les menus Océane attendus")
    sortie = {}
    if "Menus Mat & prim" in feuilles:
        sortie.update(_source_detaillee(feuilles["Menus Mat & prim"], is1904))
    for nom, cells in feuilles.items():
        if not nom.startswith("Semaine ") or not nom[8:].strip().isdigit():
            continue
        item = _source_affichages(nom, cells, is1904)
        if item:
            jour, valeur = item
            sortie[jour] = valeur
    if not sortie:
        raise ValueError("Aucun menu de mercredi utilisable")
    return sortie


def PresentationMenu(menu, largeur=100):
    if not menu:
        return u"Aucun menu Océane disponible pour ce mercredi"
    elements = []
    for nom, cle in (("Entrée", "entree"), ("Plat", "plat"),
                     ("Garniture", "garniture"), ("Laitage", "laitage"),
                     ("Dessert", "dessert")):
        vals = menu.get(cle) or []
        elements.append(u"%s : %s" % (nom, " / ".join(vals) if vals else "Non indiqué"))
    return ("\n".join(elements))[:2000]
