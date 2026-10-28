#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vérification destructive UNIQUEMENT sur le MySQL jetable 127.0.0.1:3407.

Exige le datadir de recette et l'absence de TOUTES les bases à restaurer.
Aucun paramètre ne permet de choisir un autre hôte, port, compte ou profil.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "noethys/Utils"))
import UTILS_SQL_Integrite as integrite


def verifier(runtime, archive):
    runtime, archive = Path(runtime).resolve(), Path(archive).resolve()
    commande = [str(runtime / "mysql-5.7.44-winx64/bin/mysql.exe"), "--no-defaults",
                "--host=127.0.0.1", "--port=3407", "--user=root",
                "--max-allowed-packet=1G", "--binary-mode", "-N", "-B"]
    def sql(requete=None, fichier=None):
        if fichier:
            with open(fichier, "rb") as entree:
                resultat = subprocess.run(commande, stdin=entree, capture_output=True, timeout=300)
        else:
            resultat = subprocess.run(commande + ["-e", requete], capture_output=True, timeout=60)
        if resultat.returncode:
            # Jamais afficher une requête d'import ou son contenu en erreur.
            code = re.search(rb"ERROR\s+(\d+)", resultat.stderr)
            raise RuntimeError("MySQL local : code %s, erreur %s" % (
                resultat.returncode, code.group(1).decode() if code else "non fournie"))
        return resultat.stdout
    garde = sql("SELECT @@port,@@datadir,@@version;").decode().strip().split("\t")
    if garde[0] != "3407" or not garde[2].startswith("5.7."):
        raise RuntimeError("Serveur de recette non conforme")
    if Path(garde[1].replace("\\\\", "\\")).resolve() != (runtime / "mysql-data").resolve():
        raise RuntimeError("Datadir différent du serveur jetable désigné ; restauration interdite")
    rapport = {"serveur_cible": "127.0.0.1:3407", "mysql": garde[2], "bases": []}
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise RuntimeError("Archive corrompue")
        membres = z.namelist()
        if not membres or len(set(membres)) != len(membres) or any(
                not re.fullmatch(r"[A-Za-z0-9_$]+\.sql", n) for n in membres):
            raise RuntimeError("Membres SQL invalides")
        bases = [n[:-4] for n in membres]
        existantes = sql("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME IN (%s);"
                         % ",".join("'%s'" % b for b in bases)).strip()
        if existantes:
            raise RuntimeError("Au moins une base cible existe ; aucune restauration autorisée")
        try:
            with tempfile.TemporaryDirectory(prefix="noethys-verification-") as rep:
                for membre, base in zip(membres, bases):
                    chemin = Path(z.extract(membre, rep))
                    manifeste, erreur = integrite.VerifierIntegriteSQL(chemin)
                    if not manifeste or erreur:
                        raise RuntimeError("Manifeste SQL absent ou invalide : %s" % base)
                    sql(fichier=chemin)
                    entree = {"base": base, "tables": len(sql("SHOW TABLES FROM `%s`;" % base).splitlines())}
                    if base.lower().endswith("_documents"):
                        tailles = sql("SELECT COUNT(*),COALESCE(SUM(OCTET_LENGTH(document)),0),"
                                      "COALESCE(MAX(OCTET_LENGTH(document)),0) FROM `%s`.`documents`;" % base)
                        valeurs = tailles.decode().strip().split("\t")
                        entree["documents"] = dict(zip(("nombre", "octets_total", "octets_maximum"), map(int, valeurs)))
                        empreintes = sql("SELECT OCTET_LENGTH(document),SHA2(document,256) FROM `%s`.`documents` "
                                         "ORDER BY SHA2(document,256),OCTET_LENGTH(document);" % base)
                        entree["empreinte_documents"] = hashlib.sha256(empreintes.replace(b"\r\n", b"\n")).hexdigest()
                    rapport["bases"].append(entree)
                    chemin.unlink()
                    print("%s : restauration locale vérifiée" % base, flush=True)
        finally:
            # Ces noms sont validés et leur absence a été prouvée avant import.
            # La commande de suppression utilise exclusivement le client LOCAL.
            for base in bases:
                sql("DROP DATABASE IF EXISTS `%s`;" % base)
    digest = hashlib.sha256()
    with open(archive, "rb") as f:
        for bloc in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(bloc)
    rapport.update(succes=True, archive_sha256=digest.hexdigest(), crc="OK", bases_jetables_supprimees=True)
    return rapport


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runtime", type=Path, required=True)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--rapport", type=Path, required=True)
    args = p.parse_args()
    rapport = verifier(args.runtime, args.archive)
    args.rapport.write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rapport, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
