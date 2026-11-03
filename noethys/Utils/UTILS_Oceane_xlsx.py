# -*- coding: utf-8 -*-
"""Lecture et écriture ciblées d'XLSX fournisseurs, sans dépendance ni réseau.

La modification se limite au XML des feuilles concernées dans une nouvelle
copie ZIP. Ainsi le classeur de menus comportant des dessins Excel atypiques
reste lisible sans charger ni réécrire ces dessins.
"""
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED
import os
import posixpath
import re
import tempfile

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
N = lambda name: "{%s}%s" % (NS, name)
RCELL = re.compile(r"^([A-Z]+)([1-9][0-9]*)$")
ET.register_namespace("", NS)
ET.register_namespace("r", REL)


def _col(lettres):
    nombre = 0
    for lettre in lettres:
        nombre = nombre * 26 + ord(lettre) - ord("A") + 1
    return nombre


def _coord(coord):
    if not isinstance(coord, str):
        raise ValueError("Coordonnée de cellule invalide")
    m = RCELL.fullmatch(coord.upper())
    if not m:
        raise ValueError("Coordonnée de cellule invalide : %r" % coord)
    return _col(m.group(1)), int(m.group(2))


def _table_onglets(z):
    root = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    targets = {}
    for rel in rels.findall("{%s}Relationship" % PKG):
        target = rel.get("Target", "")
        if target.startswith("/"):
            path = target.lstrip("/")
        else:
            path = posixpath.normpath(posixpath.join("xl", target))
        targets[rel.get("Id")] = path
    result = {}
    for sh in root.findall(".//" + N("sheet")):
        name, relid = sh.get("name"), sh.get("{%s}id" % REL)
        path = targets.get(relid)
        if not path or path not in z.namelist():
            raise ValueError("Onglet Excel introuvable : %s" % name)
        result[name] = path
    if not result:
        raise ValueError("Classeur Excel sans onglets")
    prop = root.find(N("workbookPr"))
    is1904 = prop is not None and prop.get("date1904") in ("1", "true")
    return result, is1904


def _chaines(z):
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    racine = ET.fromstring(z.read("xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in si.iter(N("t")))
            for si in racine.findall(N("si"))]


def _valeur(cell, strings):
    if cell is None:
        return None
    typ = cell.get("t")
    if typ == "inlineStr":
        return "".join(t.text or "" for t in cell.iter(N("t")))
    v = cell.find(N("v"))
    if v is None or v.text is None:
        return None
    if typ == "s":
        index = int(v.text)
        if index < 0 or index >= len(strings):
            raise ValueError("Chaîne partagée Excel invalide")
        return strings[index]
    if typ in ("str", "e"):
        return v.text
    if typ == "b":
        return v.text == "1"
    try:
        return float(v.text) if "." in v.text or "E" in v.text.upper() else int(v.text)
    except ValueError:
        return v.text


def _date_excel(val, is1904):
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        base = datetime(1904, 1, 1) if is1904 else datetime(1899, 12, 30)
        return (base + timedelta(days=val)).date()
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val).date()
        except ValueError:
            return None
    return None


def LireClasseur(path, noms=None):
    """Renvoie (dict nom->{coord:valeur}, date1904), en lecture seule."""
    path = Path(path)
    if path.suffix.lower() != ".xlsx" or not path.is_file():
        raise ValueError("Classeur XLSX introuvable")
    if path.stat().st_size > 40 * 1024 * 1024:
        raise ValueError("Classeur Excel trop volumineux")
    with ZipFile(path, "r") as z:
        mapping, is1904 = _table_onglets(z)
        strings = _chaines(z)
        selection = set(mapping) if noms is None else set(noms)
        if selection - set(mapping):
            raise ValueError("Onglet(s) absent(s) : %s" % ", ".join(sorted(selection - set(mapping))))
        donnees = {}
        for name in selection:
            root = ET.fromstring(z.read(mapping[name]))
            donnees[name] = {
                cell.get("r"): _valeur(cell, strings)
                for cell in root.iter(N("c"))
                if cell.get("r") is not None and _valeur(cell, strings) is not None
            }
        return donnees, is1904


def DateExcel(val, is1904=False):
    return _date_excel(val, is1904)


def _poser_cellule(root, coord, valeur):
    col, numero = _coord(coord)
    data = root.find(N("sheetData"))
    if data is None:
        raise ValueError("Onglet Excel sans cellules")
    ligne = next((r for r in data.findall(N("row"))
                  if int(r.get("r", "0")) == numero), None)
    if ligne is None:
        raise ValueError("Ligne %d absente du bordereau" % numero)
    cellule = next((c for c in ligne.findall(N("c"))
                    if c.get("r") == coord), None)
    if cellule is None:
        raise ValueError("Cellule %s absente du bordereau" % coord)
    if cellule.find(N("f")) is not None:
        raise ValueError("Cellule %s protégée par une formule" % coord)
    if cellule.find(N("v")) is not None or cellule.find(N("is")) is not None:
        raise ValueError("La cellule %s du modèle n'est pas vide" % coord)
    if valeur is None:
        return
    if isinstance(valeur, bool):
        raise ValueError("Valeur Excel booléenne refusée")
    if isinstance(valeur, int) and valeur >= 0:
        cellule.set("t", "n")
        v = ET.SubElement(cellule, N("v"))
        v.text = str(valeur)
    elif isinstance(valeur, str) and valeur.strip():
        cellule.set("t", "inlineStr")
        inline = ET.SubElement(cellule, N("is"))
        texte = ET.SubElement(inline, N("t"))
        texte.text = valeur
    else:
        raise ValueError("Valeur Excel non valide pour %s" % coord)


def EcrireCopie(source, destination, ecritures):
    """Ecrit des valeurs ponctuelles dans une nouvelle copie atomique.

    ecritures: {nom_onglet: {coord: entier >=0 ou chaîne non vide}}.
    Impossible d'écraser un fichier source ou un contenu déjà renseigné.
    """
    source, destination = Path(source), Path(destination)
    if source.suffix.lower() != ".xlsx" or destination.suffix.lower() != ".xlsx":
        raise ValueError("Fichiers source et destination attendus au format .xlsx")
    if not source.is_file():
        raise ValueError("Modèle de commande introuvable")
    if source.resolve() == destination.resolve():
        raise ValueError("Le modèle original ne doit jamais être écrasé")
    if not isinstance(ecritures, dict) or not ecritures:
        raise ValueError("Aucune donnée à exporter")
    contenu = {}
    with ZipFile(source, "r") as z:
        mapping, _ = _table_onglets(z)
        if set(ecritures) - set(mapping):
            raise ValueError("Onglets manquants dans le modèle")
        for feuille, cellules in ecritures.items():
            if not isinstance(cellules, dict):
                raise ValueError("Données de cellules invalides")
            root = ET.fromstring(z.read(mapping[feuille]))
            for coord, val in cellules.items():
                _poser_cellule(root, coord, val)
            contenu[mapping[feuille]] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        destination.parent.mkdir(parents=True, exist_ok=True)
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(
                    dir=str(destination.parent), suffix=".xlsx",
                    prefix=".oceane-", delete=False) as fichier:
                tmp = Path(fichier.name)
            with ZipFile(tmp, "w") as sortie:
                for item in z.infolist():
                    donnees = contenu.get(item.filename)
                    if donnees is None:
                        donnees = z.read(item.filename)
                    sortie.writestr(item, donnees)
            with ZipFile(tmp, "r") as controle:
                if controle.testzip() is not None:
                    raise ValueError("Export Excel incomplet")
            os.replace(tmp, destination)
        finally:
            if tmp is not None and tmp.exists():
                tmp.unlink()
    return str(destination)
