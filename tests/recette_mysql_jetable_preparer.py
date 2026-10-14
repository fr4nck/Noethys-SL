# -*- coding: utf-8 -*-
"""Prépare un serveur MySQL LOCAL et jetable pour la recette réelle (CI).

Attend que le serveur réponde en root sans mot de passe (initialize-insecure),
puis crée l'utilisateur de test déclaré par NOETHYS_TEST_MYSQL_USER /
NOETHYS_TEST_MYSQL_PASSWORD. Refuse tout hôte non local. Ne jamais l'utiliser
contre un serveur contenant des données réelles.
"""
import os
import sys
import time

import MySQLdb

HOTES_LOCAUX = ("127.0.0.1", "localhost")


def main():
    hote = os.environ["NOETHYS_TEST_MYSQL_HOST"].strip().lower()
    if hote not in HOTES_LOCAUX:
        raise SystemExit("Serveur MySQL de recette non local refusé : %s" % hote)
    port = int(os.environ["NOETHYS_TEST_MYSQL_PORT"])
    utilisateur = os.environ["NOETHYS_TEST_MYSQL_USER"]
    motdepasse = os.environ["NOETHYS_TEST_MYSQL_PASSWORD"]
    limite = time.time() + 90
    while True:
        try:
            cx = MySQLdb.connect(host=hote, port=port, user="root", passwd="", charset="utf8")
            break
        except MySQLdb.OperationalError:
            if time.time() > limite:
                raise
            time.sleep(2)
    cur = cx.cursor()
    cur.execute("SELECT VERSION()")
    print("Serveur de recette : MySQL %s" % cur.fetchone()[0])
    for h in HOTES_LOCAUX:
        cur.execute("CREATE USER %s@%s IDENTIFIED BY %s", (utilisateur, h, motdepasse))
        cur.execute("GRANT ALL ON *.* TO %s@%s", (utilisateur, h))
    cx.close()


if __name__ == "__main__":
    sys.exit(main())
