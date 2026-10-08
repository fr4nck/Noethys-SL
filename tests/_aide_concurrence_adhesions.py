# -*- coding: utf-8 -*-
"""Processus « poste » pour les tests de sauvegardes concurrentes des adhésions.

Lancé deux fois par test_noethys_sl_adhesions_concurrence, chaque processus
ouvre ses propres connexions, comme deux postes Noethys distincts.

Usage : _aide_concurrence_adhesions.py <sqlite|mysql> <cible> <A|B> <dossier_barriere> [IDindividu]
  cible : chemin du fichier SQLite, ou nom de la base MySQL de test (les
          identifiants du serveur local de test viennent de l'environnement).
Le poste A s'arrête DANS la section protégée (après le contrôle d'existant,
avant l'écriture) jusqu'à ce que le test crée le fichier « A_continuer ».
"""
import datetime
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402
from _fixtures_noethys_db import RedirectionGestionDB  # noqa: E402
import GestionDB  # noqa: E402
from Utils import UTILS_Adhesions as A  # noqa: E402

JOUR = datetime.date(2026, 10, 1)


def nom_fichier_mysql(parametres, base):
    return u"%d;%s;%s;%s[RESEAU]%s" % (parametres["port"], parametres["hote"], parametres["utilisateur"],
                                      GestionDB.EncodeMdpReseau(parametres["motdepasse"]), base)


def executer(cible, role, barriere, IDindividu=100):
    if role == "A":
        original = A._periode_verrouillee  # appelée sous verrou, après le contrôle d'existant

        def en_pause(*args, **kwargs):
            (barriere / "A_dans_section").write_text("1")
            limite = time.time() + 30
            while not (barriere / "A_continuer").exists() and time.time() < limite:
                time.sleep(0.05)
            return original(*args, **kwargs)
        A._periode_verrouillee = en_pause
    with RedirectionGestionDB(cible):
        resultat = A.ReconcilierIndividu(IDindividu, date_reference=JOUR, depuis=datetime.date(2026, 10, 7))
    (barriere / ("%s.json" % role)).write_text(json.dumps(
        {"statut": resultat["statut"], "motif": resultat.get("motif"), "creees": resultat["cotisations_creees"]}))


def main():
    mode, cible, role, barriere = sys.argv[1], sys.argv[2], sys.argv[3], Path(sys.argv[4])
    IDindividu = int(sys.argv[5]) if len(sys.argv) > 5 else 100
    if mode == "mysql":
        with _garde_reseau.ServeurMySQLDeTest() as parametres:
            executer(nom_fichier_mysql(parametres, cible), role, barriere, IDindividu)
    else:
        executer(cible, role, barriere, IDindividu)


if __name__ == "__main__":
    main()
