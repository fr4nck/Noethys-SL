# -*- coding: utf-8 -*-
"""Import SQL borne pour le client MySQL, sans wx ni connexion applicative.

L'import de DDL n'est pas atomique : apres un echec la cible peut etre
partiellement restauree. Cet utilitaire ne relance jamais une importation.
"""
import os
import re
import subprocess
import tempfile
import time


def _diagnostic(texte, secrets=()):
    """Garde seulement un diagnostic court et masque les secrets connus."""
    import base64
    if not isinstance(texte, str):
        texte = str(texte)
    valeurs = [str(s) for s in secrets if s]
    for valeur in tuple(valeurs):
        if valeur.startswith("#64#"):
            try:
                valeurs.append(base64.b64decode(valeur[4:]).decode("utf-8"))
            except (ValueError, UnicodeError):
                pass
    for secret in sorted(set(valeurs), key=len, reverse=True):
        texte = texte.replace(secret, "[masque]")
    texte = re.sub(r"(?is)(?:INSERT\s+INTO|REPLACE\s+INTO).*", "[SQL masque]", texte)
    return texte[-4096:]


def _arreter(proc):
    """Ne pas laisser de processus mysql enfant sur une erreur ou timeout."""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def ImporterSQL(programme, login, fichier, base, progression=None,
                secrets=(), duree_max=7200, intervalle=2):
    """Importe exactement un SQL en stdin binaire, sans shell ou pipe bloque.

    Le compte rendu est toujours un dictionnaire ; aucun contenu SQL, option
    d'authentification ou mot de passe n'est retourne dans le diagnostic.
    """
    debut = time.monotonic()
    code = None
    erreur = None
    diagnostic = ""
    proc = None
    try:
        if not re.fullmatch(r"[A-Za-z0-9_$]+", str(base)):
            raise ValueError("Nom de base SQL non pris en charge")
        if duree_max <= 0 or intervalle <= 0:
            raise ValueError("Delai d'import SQL non valide")
        args = [os.fspath(programme), "--defaults-extra-file=%s" % os.fspath(login),
                "--max-allowed-packet=1G", str(base)]
        creation = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
        with open(fichier, "rb") as source, tempfile.TemporaryFile(mode="w+b") as erreurs:
            proc = subprocess.Popen(args, shell=False, stdin=source,
                                    stdout=subprocess.DEVNULL, stderr=erreurs,
                                    creationflags=creation)
            try:
                while True:
                    reste = duree_max - (time.monotonic() - debut)
                    if reste <= 0:
                        erreur = "Import MySQL arrete : duree maximale depassee."
                        break
                    try:
                        proc.wait(timeout=min(intervalle, reste))
                        break
                    except subprocess.TimeoutExpired:
                        if progression:
                            progression()
            finally:
                _arreter(proc)
            code = proc.returncode
            erreurs.seek(0, os.SEEK_END)
            erreurs.seek(max(0, erreurs.tell() - 8192))
            diagnostic = _diagnostic(erreurs.read().decode("utf-8", "replace"), secrets)
            if erreur is None and code != 0:
                erreur = "Le client mysql a echoue (code %s). %s" % (code, diagnostic[-2048:])
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        erreur = "Import MySQL impossible : %s" % _diagnostic(str(exc), secrets)
    except Exception as exc:
        erreur = "Import MySQL interrompu : %s" % _diagnostic(str(exc), secrets)
    return {"code_retour": code,
            "erreur": _diagnostic(erreur, secrets) if erreur else None,
            "diagnostic": diagnostic,
            "secondes": round(time.monotonic() - debut, 1)}