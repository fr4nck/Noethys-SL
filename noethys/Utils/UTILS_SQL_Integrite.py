# -*- coding: utf-8 -*-
"""Validation independante des manifestes SQL Noethys V1 (sans wx ni base)."""

import hashlib
import os
import re
import tempfile
import uuid

_ENTETE = b"-- NOETHYS-SQL-MANIFEST-V1 "
_FIN = b"-- NOETHYS-SQL-MANIFEST-END-V1 "
_JETON_RE = re.compile(br"[0-9a-f]{32}\Z")
_FIN_RE = re.compile(br"-- NOETHYS-SQL-MANIFEST-END-V1 ([0-9a-f]{32}) ([0-9]+) ([0-9a-f]{64})\n?\Z")
_BLOC = 1024 * 1024


def AjouterManifesteIntegriteSQL(fichier):
    """Ajoute le manifeste V1 de master sans supprimer la source avant remplacement."""
    chemin = os.fspath(fichier)
    jeton = uuid.uuid4().hex.encode("ascii")
    repertoire = os.path.dirname(os.path.abspath(chemin))
    nom = os.path.basename(chemin)
    temporaire = None
    try:
        with open(chemin, "rb") as source:
            if source.read(len(_ENTETE)) == _ENTETE:
                raise ValueError("dump deja dote d'un manifeste SQL")
            source.seek(0)
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=repertoire, prefix=nom + ".manifest-", delete=False
            ) as destination:
                temporaire = destination.name
                destination.write(_ENTETE + jeton + b"\n")
                empreinte = hashlib.sha256()
                taille = 0
                while True:
                    bloc = source.read(_BLOC)
                    if not bloc:
                        break
                    empreinte.update(bloc)
                    taille += len(bloc)
                    destination.write(bloc)
                destination.write(b"\n" + _FIN + jeton + b" " + str(taille).encode("ascii")
                                  + b" " + empreinte.hexdigest().encode("ascii") + b"\n")
        os.replace(temporaire, chemin)
        temporaire = None
    finally:
        if temporaire is not None:
            try:
                os.unlink(temporaire)
            except OSError:
                pass


def VerifierIntegriteSQL(fichier):
    """Retourne (avec_manifeste, erreur). Ancien dump autorise, manifeste V1 strict.

    La taille et le SHA-256 sont controles en flux, sans charger le dump en RAM.
    """
    chemin = os.fspath(fichier)
    try:
        with open(chemin, "rb") as source:
            taille_fichier = os.fstat(source.fileno()).st_size
            if taille_fichier == 0:
                return False, "dump SQL vide"
            premiere = source.readline(128)
            if not premiere.startswith(_ENTETE):
                if premiere.startswith(b"-- NOETHYS-SQL-MANIFEST-V1"):
                    return False, "en-tete du manifeste SQL invalide"
                source.seek(max(0, taille_fichier - 1024))
                if _FIN in source.read():
                    return False, "manifeste terminal sans en-tete"
                return False, None
            if not premiere.endswith(b"\n"):
                return True, "en-tete du manifeste SQL tronque"
            jeton = premiere[len(_ENTETE):-1]
            if _JETON_RE.fullmatch(jeton) is None:
                return True, "identifiant du manifeste SQL invalide"
            depart_charge = source.tell()
            debut_queue = max(depart_charge, taille_fichier - 1024)
            source.seek(debut_queue)
            queue = source.read()
            marqueur = queue.rfind(b"\n" + _FIN)
            if marqueur < 0:
                return True, "manifeste terminal absent ou tronque"
            ligne_fin = queue[marqueur + 1:]
            correspondance = _FIN_RE.fullmatch(ligne_fin)
            if correspondance is None:
                return True, "manifeste terminal invalide"
            jeton_fin, taille_declaree, empreinte_declaree = correspondance.groups()
            if jeton_fin != jeton:
                return True, "identifiants du manifeste SQL differents"
            fin_charge = debut_queue + marqueur
            taille_reelle = fin_charge - depart_charge
            if taille_reelle != int(taille_declaree):
                return True, "taille du dump SQL differente du manifeste"
            source.seek(depart_charge)
            empreinte = hashlib.sha256()
            reste = taille_reelle
            while reste > 0:
                bloc = source.read(min(_BLOC, reste))
                if not bloc:
                    return True, "charge SQL tronquee"
                empreinte.update(bloc)
                reste -= len(bloc)
            if empreinte.hexdigest().encode("ascii") != empreinte_declaree:
                return True, "empreinte SHA-256 du dump SQL invalide"
            return True, None
    except OSError as erreur:
        return False, "lecture du dump SQL impossible : %s" % erreur
