"""Deux postes isoles completant la meme cotisation, donnees synthetiques."""
import datetime
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _garde_reseau
from _fixtures_noethys_db import RedirectionGestionDB
from _aide_concurrence_adhesions import nom_fichier_mysql
from Utils import UTILS_Adhesions as A


def executer(cible, role, barriere):
    if role == 'A':
        original = A._AccesStrict.Modifier

        def pause(acces, req, valeurs):
            if req.startswith('UPDATE cotisations SET activites='):
                (barriere / 'A_dans_section').write_text('1')
                limite = time.monotonic() + 30
                while not (barriere / 'continuer').exists():
                    if time.monotonic() > limite:
                        raise RuntimeError('Barriere non liberee')
                    time.sleep(0.02)
            return original(acces, req, valeurs)
        A._AccesStrict.Modifier = pause
    else:
        original = A._Verrouiller

        def annoncer(*args):
            (barriere / 'B_avant_verrou').write_text('1')
            return original(*args)
        A._Verrouiller = annoncer
    with RedirectionGestionDB(cible):
        ids = A.CompleterActivitesAutomatiques(201 if role == 'A' else 202,
                                              200, A.ResoudreConfiguration(), datetime.date(2026, 10, 15))
    (barriere / (role + '.json')).write_text(json.dumps(ids))


if __name__ == '__main__':
    mode, cible, role, barriere = sys.argv[1:]
    if mode == 'mysql':
        with _garde_reseau.ServeurMySQLDeTest() as params:
            executer(nom_fichier_mysql(params, cible), role, Path(barriere))
    else:
        executer(cible, role, Path(barriere))
