# -*- coding: utf-8 -*-
"""Ajoute au paquet Windows les clients MySQL 5.7 utilisés par la sauvegarde réseau.

Seuls mysql.exe et mysqldump.exe sont extraits de l'archive officielle Oracle
(empreinte SHA-256 épinglée), avec leur licence, le runtime Visual C++ qu'ils
importent et une notice de provenance. Aucun serveur MySQL n'est livré.

Usage : python packaging/assembler_client_mysql.py ARCHIVE_ZIP DIST_NOETHYS
Échoue (code 1) si l'archive, une dépendance DLL ou la version diffère.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

import pefile

VERSION = "5.7.44"
RACINE_ARCHIVE = "mysql-%s-winx64/" % VERSION
SHA256_ARCHIVE = "aed661fe8120254a1dc30f5a4d5de346681922f4847cf025e2d4084eca78e70e"
URL_ARCHIVE = "https://cdn.mysql.com/archives/mysql-5.7/mysql-%s-winx64.zip" % VERSION
URL_SOURCES = "https://cdn.mysql.com/archives/mysql-5.7/mysql-%s.tar.gz" % VERSION
SHA256_SOURCES = "d03d8ff688862c40da3488451072a4b2178a86b53b4a7546ee5f864bb15cd919"
PROGRAMMES = ("mysql.exe", "mysqldump.exe")
RUNTIME_VC = ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll")
# DLL fournies par Windows 10/11 (UCRT incluse via api-ms-win-crt-*).
DLL_SYSTEME = {"kernel32.dll", "user32.dll", "advapi32.dll", "shell32.dll", "crypt32.dll",
               "secur32.dll", "bcrypt.dll", "ws2_32.dll", "ntdll.dll", "ole32.dll"}
REPERTOIRE = "mysql-client"

NOTICE = u"""Clients MySQL livrés avec Noethys SL
=====================================

Ce dossier contient uniquement les programmes clients mysql.exe et mysqldump.exe
de MySQL Community {version} pour Windows (x86-64), utilisés par Noethys SL pour
sauvegarder et restaurer les fichiers réseau (.nod/.noc) sans installer MySQL.
Aucun serveur MySQL n'est installé ni démarré.

Origine (binaires non modifiés) :
  {url_archive}
  SHA-256 de l'archive : {sha_archive}

Licence : GNU General Public License version 2 (voir LICENSE et README,
copiés sans modification depuis l'archive officielle). Copyright (c) 2000, 2023,
Oracle and/or its affiliates.

Code source correspondant (GPLv2) :
  {url_sources}
  SHA-256 : {sha_sources}

Runtime Microsoft Visual C++ 2015-2022 (msvcp140.dll, vcruntime140.dll,
vcruntime140_1.dll) : fichiers redistribuables Microsoft, copiés depuis le paquet
Noethys SL pour que ces clients démarrent sur un Windows sans runtime installé.
"""


def _sha256(chemin):
    empreinte = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1024 * 1024), b""):
            empreinte.update(bloc)
    return empreinte.hexdigest()


def _imports(chemin):
    pe = pefile.PE(chemin, fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
    return [e.dll.decode("ascii").lower() for e in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])]


def _trouver_runtime(dist):
    """ Les trois DLL du runtime VC++ prises dans un même dossier (versions cohérentes). """
    for racine, _, fichiers in os.walk(dist):
        if os.path.relpath(racine, dist).split(os.sep)[0] == REPERTOIRE:
            continue
        noms = {f.lower(): os.path.join(racine, f) for f in fichiers}
        # x86-64 uniquement (0x8664), comme les clients MySQL.
        if all(n in noms and pefile.PE(noms[n], fast_load=True).FILE_HEADER.Machine == 0x8664 for n in RUNTIME_VC):
            return [noms[n] for n in RUNTIME_VC]
    return None


def VerifierDependances(bin_):
    """ Toute DLL importée (récursivement) est système ou présente dans bin_. """
    livrees = {f.lower(): os.path.join(bin_, f) for f in os.listdir(bin_)}
    erreurs, a_voir, vus = [], [livrees[p] for p in PROGRAMMES], set()
    while a_voir:
        chemin = a_voir.pop()
        for dll in _imports(chemin):
            if dll in DLL_SYSTEME or dll.startswith("api-ms-win-") or dll in vus:
                continue
            vus.add(dll)
            if dll in livrees:
                a_voir.append(livrees[dll])
            else:
                erreurs.append("%s importe %s, absente de %s" % (os.path.basename(chemin), dll, bin_))
    return erreurs


def Assembler(archive, dist):
    if _sha256(archive) != SHA256_ARCHIVE:
        raise SystemExit("Empreinte inattendue pour %s" % archive)
    cible = os.path.join(dist, REPERTOIRE)
    if os.path.exists(cible):
        shutil.rmtree(cible)
    bin_ = os.path.join(cible, "bin")
    os.makedirs(bin_)
    with zipfile.ZipFile(archive) as z:
        for membre, destination in [("bin/" + p, os.path.join(bin_, p)) for p in PROGRAMMES] + \
                                   [(n, os.path.join(cible, n)) for n in ("LICENSE", "README")]:
            with z.open(RACINE_ARCHIVE + membre) as source, open(destination, "wb") as sortie:
                shutil.copyfileobj(source, sortie)
    sources = _trouver_runtime(dist)
    if sources is None:
        raise SystemExit("Aucun dossier de %s ne contient le runtime VC++ complet %s" % (dist, RUNTIME_VC))
    print("Runtime VC++ copié depuis %s" % os.path.dirname(sources[0]))
    for nom, source in zip(RUNTIME_VC, sources):
        shutil.copy2(source, os.path.join(bin_, nom))
    with open(os.path.join(cible, "LISEZMOI-NOETHYS.txt"), "w", encoding="utf-8") as f:
        f.write(NOTICE.format(version=VERSION, url_archive=URL_ARCHIVE, sha_archive=SHA256_ARCHIVE,
                              url_sources=URL_SOURCES, sha_sources=SHA256_SOURCES))

    erreurs = VerifierDependances(bin_)
    if erreurs:
        raise SystemExit("Dépendances non livrées :\n  " + "\n  ".join(erreurs))
    for programme in PROGRAMMES:
        sortie = subprocess.run([os.path.join(bin_, programme), "--no-defaults", "--version"],
                                capture_output=True, text=True, timeout=30)
        if sortie.returncode != 0 or ("Distrib %s," % VERSION) not in sortie.stdout:
            raise SystemExit("%s --version inattendu : %r" % (programme, sortie.stdout + sortie.stderr))
        print(sortie.stdout.strip())
    for fichier in sorted(os.listdir(bin_)):
        print("%s  mysql-client/bin/%s" % (_sha256(os.path.join(bin_, fichier)), fichier))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    Assembler(sys.argv[1], sys.argv[2])
