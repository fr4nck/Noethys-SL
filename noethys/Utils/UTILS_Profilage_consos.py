# -*- coding: utf-8 -*-
"""Profilage facultatif, local et anonymise du clic OK sur les consommations.

Activation explicite par NOETHYS_SL_PROFILE_CONSOS=1 avant demarrage.
Par defaut, aucune collecte et aucun fichier. Le rapport est une ligne JSON
locale avec temps par phase et fonctions les plus couteuses. Ne conserve
JAMAIS requete SQL, arguments, ID, nom, adresse, resultat ou traceback.
Ne touche a aucune connexion ni transaction metier (#427).
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
import time

_ENV = "NOETHYS_SL_PROFILE_CONSOS"
_NOM_LOG = "performance-consommations.jsonl"
_MAX_LOG_BYTES = 1024 * 1024
_MAX_FONCTIONS = 25


def CheminJournal():
    """Chemin local explicite, independant de la base Noethys."""
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    return Path(base) / "Noethys-SL" / "Diagnostics" / _NOM_LOG


class SuiviValidation:
    """Contexte sans effet sur l'execution, journalise uniquement sur opt-in."""

    def __init__(self):
        self.actif = os.environ.get(_ENV) == "1"
        self.etapes = []
        self._profile = None
        self._debut = None

    def __enter__(self):
        if self.actif:
            import cProfile
            self._profile = cProfile.Profile()
            self._debut = time.perf_counter()
            self._profile.enable()
        return self

    @contextmanager
    def etape(self, nom):
        if not self.actif:
            yield
            return
        debut = time.perf_counter()
        try:
            yield
        finally:
            self.etapes.append({
                "phase": nom,
                "ms": round((time.perf_counter() - debut) * 1000.0, 2),
            })

    def __exit__(self, type_erreur, erreur, traceback):
        if not self.actif:
            return False
        self._profile.disable()
        try:
            fonctions = []
            for ligne in self._profile.getstats():
                # Inclure uniquement les noms de fonctions Python definies
                # dans les sources, jamais les valeurs ni chemins complets.
                code = ligne.code
                if not hasattr(code, "co_filename"):
                    continue
                fonctions.append({
                    "fichier": os.path.basename(code.co_filename),
                    "fonction": code.co_name,
                    "appels": ligne.callcount,
                    "temps_ms": round(ligne.totaltime * 1000.0, 2),
                    "temps_propre_ms": round(ligne.inlinetime * 1000.0, 2),
                })
            fonctions.sort(key=lambda valeur: valeur["temps_ms"], reverse=True)
            donnees = {
                "horodatage": datetime.now().isoformat(timespec="seconds"),
                "duree_ms": round((time.perf_counter() - self._debut) * 1000.0, 2),
                "termine_sans_exception": type_erreur is None,
                "etapes": self.etapes,
                "fonctions": fonctions[:_MAX_FONCTIONS],
            }
            path = CheminJournal()
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and path.stat().st_size > _MAX_LOG_BYTES:
                # Rotation bornee ; le journal ne doit pas grossir a l'infini.
                path.replace(path.with_suffix(".ancien.jsonl"))
            with path.open("a", encoding="utf-8") as fichier:
                fichier.write(json.dumps(donnees, ensure_ascii=False) + "\n")
        except Exception:
            # Une erreur de diagnostic ne doit JAMAIS invalider l'enregistrement.
            pass
        return False
