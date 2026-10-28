#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnostic SELECT uniquement ; n'importe jamais Noethys ni son profil actif.

Lecture volontaire d'un Config.json désigné pour retrouver une connexion exacte.
Ne lit que les tailles des documents, jamais leur contenu, leur nom ou leurs IDs.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def valeur_option(valeur):
    valeur = str(valeur)
    for avant, apres in (("\\", "\\\\"), ('"', '\\"'), ("\n", "\\n"),
                         ("\r", "\\r"), ("\t", "\\t")):
        valeur = valeur.replace(avant, apres)
    return '"%s"' % valeur


def connexion(profil, hote, base):
    config = json.loads(Path(profil).read_text(encoding="utf-8-sig"))
    for chaine in [config.get("nomFichier", "")] + config.get("derniersFichiers", []):
        if not isinstance(chaine, str) or "[RESEAU]" not in chaine:
            continue
        parametres, nom = chaine.split("[RESEAU]", 1)
        champs = parametres.split(";")
        if len(champs) == 4 and champs[1].lower() == hote.lower() and nom.lower() == base.lower():
            port, host, user, password = champs
            if password.startswith("#64#"):
                password = base64.b64decode(password[4:]).decode("utf-8")
            return dict(host=host, port=port, user=user, password=password)
    raise ValueError("Connexion exacte hôte/base absente du profil désigné")


def requetes(base):
    if not re.fullmatch(r"[A-Za-z0-9_$]+", base):
        raise ValueError("Nom de base non pris en charge")
    return (
        "SELECT @@version, @@global.max_allowed_packet, @@session.max_allowed_packet, "
        "@@session.net_read_timeout, @@session.net_write_timeout, @@session.wait_timeout;",
        "SELECT COUNT(*), COALESCE(SUM(OCTET_LENGTH(document)),0), "
        "COALESCE(MAX(OCTET_LENGTH(document)),0) FROM `%s_documents`.`documents`;" % base,
        "SELECT OCTET_LENGTH(document),SHA2(document,256) FROM `%s_documents`.`documents` "
        "ORDER BY SHA2(document,256),OCTET_LENGTH(document);" % base,
        "SELECT nom,sauvegarde_repertoire,sauvegarde_fichiers_reseau FROM `%s_data`.`sauvegardes_auto` "
        "WHERE nom='Ma sauvegarde';" % base,
    )


def diagnostiquer(client, parametres, bases):
    rapport = {"lecture_seule": True, "bases": []}
    with tempfile.TemporaryDirectory(prefix="noethys-diagnostic-") as rep:
        login = os.path.join(rep, "client.cnf")
        fd = os.open(login, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("[client]\n" + "".join("%s=%s\n" % (k, valeur_option(v))
                                          for k, v in parametres.items()))
        for base in bases:
            entree = {"base": base}
            for index, sql in enumerate(requetes(base)):
                try:
                    resultat = subprocess.run(
                        [str(client), "--defaults-file=" + login, "--connect-timeout=5",
                         "--max-allowed-packet=1G", "--batch", "--skip-column-names", "-e", sql],
                        stdin=subprocess.DEVNULL, capture_output=True, timeout=45, check=False)
                    if resultat.returncode:
                        # Ne pas conserver stderr (peut citer un compte ou du SQL).
                        entree["erreur"] = "client MySQL : code %s" % resultat.returncode
                        match = re.search(rb"ERROR\s+(\d+)", resultat.stderr)
                        if match:
                            entree["code_mysql"] = int(match.group(1))
                        break
                    valeurs = resultat.stdout.decode("utf-8", "replace").strip().split("\t")
                    if index == 0:
                        entree["serveur"] = dict(zip(
                            ("version", "max_allowed_packet_global", "max_allowed_packet_session",
                             "net_read_timeout", "net_write_timeout", "wait_timeout"), valeurs))
                    elif index == 1:
                        entree["documents"] = dict(zip(
                            ("nombre", "octets_total", "octets_maximum"), map(int, valeurs)))
                    elif index == 2:
                        entree["empreinte_documents"] = hashlib.sha256(
                            resultat.stdout.replace(b"\r\n", b"\n")).hexdigest()
                    else:
                        entree["procedures"] = []
                        for ligne in resultat.stdout.decode("utf-8", "replace").strip().splitlines():
                            nom, repertoire, fichiers = ligne.split("\t")
                            entree["procedures"].append(dict(nom=nom, repertoire=repertoire,
                                repertoire_existe_sur_ce_poste=os.path.isdir(repertoire.replace("\\\\", "\\")),
                                fichiers_reseau=fichiers))
                except subprocess.TimeoutExpired:
                    entree["erreur"] = "délai du diagnostic dépassé (45 secondes)"
                    break
            rapport["bases"].append(entree)
    return rapport


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--client", required=True, type=Path)
    p.add_argument("--profil", required=True, type=Path)
    p.add_argument("--hote", required=True)
    p.add_argument("--base", required=True, action="append")
    p.add_argument("--sortie", required=True, type=Path)
    args = p.parse_args()
    parametres = connexion(args.profil, args.hote, args.base[0])
    # Vérifier que chaque base choisie utilise bien la même connexion.
    for base in args.base:
        if connexion(args.profil, args.hote, base) != parametres:
            p.error("Les bases choisies utilisent des connexions différentes")
    rapport = diagnostiquer(args.client.resolve(), parametres, args.base)
    args.sortie.write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rapport, ensure_ascii=False, indent=2))
    return int(any("erreur" in base for base in rapport["bases"]))


if __name__ == "__main__":
    raise SystemExit(main())
