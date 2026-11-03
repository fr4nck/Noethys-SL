# -*- coding: utf-8 -*-
"""Lot A RC10.5 : contrôle en LECTURE SEULE d'une archive Noethys non chiffrée.

Ne contacte jamais MySQL et n'extrait aucun fichier. Une archive structurellement
valide N'EST PAS une preuve de restauration ; seule une restauration isolée
permet de lever le STOP-GATE de l'incident #437.
"""
import hashlib
import os
import re
import stat
import zipfile

_FIN = b"-- NOETHYS-SQL-MANIFEST-END-V1 "
_ENTETE = b"-- NOETHYS-SQL-MANIFEST-V1 "
_RE_JETON = re.compile(br"[a-f0-9]{32}\Z")
_RE_FIN = re.compile(br"-- NOETHYS-SQL-MANIFEST-END-V1 ([a-f0-9]{32}) ([0-9]+) ([a-f0-9]{64})\n?\Z")
_RE_MYSQL = re.compile(br"-- Dump completed(?: on [^\r\n]*)?\Z")
_BLOC = 1024 * 1024
_QUEUE = 4096
_CATEGORIES = ("DATA", "PHOTOS", "DOCUMENTS")


class ArchiveNoethysInvalide(ValueError):
    pass


def _categorie(nom):
    basename = nom.rsplit("/", 1)[-1]
    base = basename[:-4].upper()
    if base == "PHOTOS" or base.endswith("_PHOTOS"):
        return "PHOTOS"
    if base == "DOCUMENTS" or base.endswith("_DOCUMENTS"):
        return "DOCUMENTS"
    return "DATA"


def _fin_mysqldump(queue):
    contenu = queue.rstrip()
    return _RE_MYSQL.fullmatch(contenu[contenu.rfind(b"\n") + 1:]) is not None


def _analyser_sql(flux):
    """Contrôler ZIP+CRC et manifeste V1 en flux, sans charger un gros BLOB."""
    debut = flux.readline(128)
    if not debut:
        raise ArchiveNoethysInvalide("dump SQL vide")
    manifeste = debut.startswith(_ENTETE)
    if debut.startswith(b"-- NOETHYS-SQL-MANIFEST-V1") and not manifeste:
        raise ArchiveNoethysInvalide("entete du manifeste SQL invalide")
    if manifeste:
        if not debut.endswith(b"\n"):
            raise ArchiveNoethysInvalide("entete du manifeste SQL tronquee")
        jeton = debut[len(_ENTETE):-1]
        if _RE_JETON.fullmatch(jeton) is None:
            raise ArchiveNoethysInvalide("jeton du manifeste SQL invalide")
    reste = debut if not manifeste else b""
    empreinte = hashlib.sha256()
    taille = 0
    while True:
        bloc = flux.read(_BLOC)
        if not bloc:
            break
        reste += bloc
        if len(reste) > _QUEUE:
            prefixe, reste = reste[:-_QUEUE], reste[-_QUEUE:]
            empreinte.update(prefixe)
            taille += len(prefixe)
    if not manifeste:
        if _FIN in reste:
            raise ArchiveNoethysInvalide("manifeste terminal sans entete")
        if taille + len(reste) == 0:
            raise ArchiveNoethysInvalide("dump SQL vide")
        if not _fin_mysqldump(reste):
            raise ArchiveNoethysInvalide("ancien dump sans ligne finale mysqldump")
        return "ANCIEN_FORMAT_NON_AUTHENTIFIE"
    marqueur = reste.rfind(b"\n" + _FIN)
    if marqueur < 0:
        raise ArchiveNoethysInvalide("manifest terminal absent ou tronque")
    ligne = reste[marqueur + 1:]
    correspondance = _RE_FIN.fullmatch(ligne)
    if correspondance is None:
        raise ArchiveNoethysInvalide("manifest terminal invalide")
    jeton_fin, taille_declaree, sha_declare = correspondance.groups()
    if jeton_fin != jeton:
        raise ArchiveNoethysInvalide("jetons du manifeste differents")
    contenu = reste[:marqueur]
    empreinte.update(contenu)
    taille += len(contenu)
    if taille == 0 or taille != int(taille_declaree):
        raise ArchiveNoethysInvalide("taille SQL differente du manifeste")
    if empreinte.hexdigest().encode("ascii") != sha_declare:
        raise ArchiveNoethysInvalide("empreinte SQL differente du manifeste")
    # Un SHA valide n'etablit pas qu'un export mysqldump est arrive au bout.
    # L'ajout manuel d'un manifeste a un SQL tronque ne doit jamais valoir PASS.
    if not _fin_mysqldump(contenu):
        raise ArchiveNoethysInvalide("ligne finale mysqldump absente du manifeste")
    return "MANIFESTE_V1_VERIFIE"


def InspecterArchive(chemin):
    """Retourne un bilan anonymise : PASS / LEGACY / FAIL, sans mutation."""
    resultat = {"verdict": "FAIL", "bases": {}, "restauration_prouvee": False,
                "detail": ""}
    try:
        with zipfile.ZipFile(os.fspath(chemin), "r") as archive:
            categorise = {}
            annexes = []
            noms = set()
            for item in archive.infolist():
                nom = item.filename.replace("\\", "/")
                parts = nom.split("/")
                if (nom.startswith("/") or re.match(r"^[a-zA-Z]:", nom)
                        or any(p in ("", "..") for p in parts if p != parts[-1])
                        or ".." in parts or "\x00" in nom):
                    raise ArchiveNoethysInvalide("nom d'entree ZIP dangereux")
                if stat.S_IFMT(item.external_attr >> 16) == stat.S_IFLNK:
                    raise ArchiveNoethysInvalide("lien symbolique dans le ZIP")
                if item.is_dir():
                    continue
                if nom.lower() in noms:
                    raise ArchiveNoethysInvalide("nom d'entree ZIP duplique")
                noms.add(nom.lower())
                if item.flag_bits & 1:
                    raise ArchiveNoethysInvalide("entree ZIP chiffree, inspection impossible")
                if not nom.lower().endswith(".sql"):
                    annexes.append(item)
                    continue
                if "/" in nom:
                    raise ArchiveNoethysInvalide("SQL hors racine du ZIP")
                cat = _categorie(nom)
                if cat in categorise:
                    raise ArchiveNoethysInvalide("plusieurs dumps SQL pour " + cat)
                categorise[cat] = item
            if set(categorise) != set(_CATEGORIES):
                manque = sorted(set(_CATEGORIES) - set(categorise))
                raise ArchiveNoethysInvalide("bases manquantes : " + ", ".join(manque))
            # Verifier aussi le CRC des pieces non-SQL. Une ZIP peut avoir
            # trois dumps integres tout en contenant une annexe corrompue.
            # Lecture en flux : aucune extraction, aucun stockage en RAM.
            for item in annexes:
                with archive.open(item, "r") as flux:
                    while flux.read(_BLOC):
                        pass
            for cat in _CATEGORIES:
                item = categorise[cat]
                with archive.open(item, "r") as flux:
                    statut = _analyser_sql(flux)
                resultat["bases"][cat] = {"fichier": item.filename,
                                          "taille_sql": item.file_size,
                                          "controle": statut}
            resultat["verdict"] = ("PASS" if all(
                b["controle"] == "MANIFESTE_V1_VERIFIE"
                for b in resultat["bases"].values()) else "LEGACY")
            resultat["detail"] = (
                "Integrite ZIP/SQL controlee ; restaurer sur MySQL isole pour conclure"
                if resultat["verdict"] == "PASS" else
                "Ancien dump non authentifie ; restauration isolee et verification requises")
    except (ArchiveNoethysInvalide, zipfile.BadZipFile, OSError, RuntimeError,
            EOFError, ValueError) as erreur:
        resultat["detail"] = str(erreur)
    return resultat
