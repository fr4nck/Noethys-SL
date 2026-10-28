#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sauvegarde réseau volontaire sans lancer Noethys ; aucune restauration."""
import argparse
import os
from pathlib import Path
import sys
import tempfile

from diagnostic_sauvegarde_mysql import connexion, valeur_option

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "noethys/Utils"))
import UTILS_MySQL_backup as moteur
import UTILS_SQL_Integrite as integrite


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--client", type=Path, required=True, help="Chemin de mysqldump.exe")
    p.add_argument("--profil", type=Path, required=True)
    p.add_argument("--hote", required=True)
    p.add_argument("--base", action="append", required=True)
    p.add_argument("--categorie", choices=("DATA", "PHOTOS", "DOCUMENTS"), action="append", required=True)
    p.add_argument("--sortie", type=Path, required=True)
    args = p.parse_args()
    parametres = connexion(args.profil, args.hote, args.base[0])
    if any(connexion(args.profil, args.hote, base) != parametres for base in args.base):
        p.error("Les bases utilisent des connexions différentes")
    fichiers = ["%s_%s" % (b.lower(), c.lower()) for b in args.base for c in args.categorie]
    with tempfile.TemporaryDirectory(prefix="noethys-login-") as rep:
        login = os.path.join(rep, "client.cnf")
        fd = os.open(login, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("[client]\n" + "".join("%s=%s\n" % (k, valeur_option(v))
                                          for k, v in parametres.items()))
        dernier = [None]
        def progression(base, etape, taille):
            # Une ligne par tranche de 16 Mio, plus les changements d'étape.
            cle = (base, etape, int(taille / 16777216))
            if cle != dernier[0]:
                print("%s : %s, %.1f Mio" % (base, etape, taille / 1048576), flush=True)
                dernier[0] = cle
        bilan = moteur.CreerArchive(args.client.resolve(), login, fichiers, args.sortie,
                                    integrite, progression, (parametres["user"], parametres["password"]))
    print("Sauvegarde complète créée." if bilan["succes"] else "Échec : " + bilan["erreur"], flush=True)
    return 0 if bilan["succes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
