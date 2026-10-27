# -*- coding: utf-8 -*-
"""Campagne bornee #432 : plantages 0xC0000005 a la sortie du scenario wx.

Execute plusieurs fois le scenario fictif ``--corrige`` de
tests/test_connecthys_ui432_etapes.py, sous ``-X faulthandler``, avec des
variantes qui isolent la destruction wx, la veille du diagnostic et la
finalisation Python. Aucune base reelle, aucun reseau (garde du scenario).
Reserve a un runner Windows isole : ouvre des fenetres wx.
"""
import argparse
import collections
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "tests" / "test_connecthys_ui432_etapes.py"
VARIANTES = ("base", "sans_veille", "veille_jointe", "os_exit")
MARQUEURS = ("UI432_RESULT", "UI432_FIN_SCENARIO", "UI432_GC", "UI432_ATEXIT")

ENFANT = r"""
import atexit, gc, os, runpy, sys
variante = os.environ["UI432_VARIANTE"]
test = os.environ["UI432_TEST"]
from Utils import UTILS_Diagnostic_ui as Diag
if variante == "sans_veille":
    Diag.Diagnostic._surveiller_blocages = lambda self, ident: None
elif variante == "veille_jointe":
    origine = Diag.Diagnostic._on_destruction
    def _on_destruction(self, event):
        origine(self, event)
        veille = getattr(self, "_veille_thread", None)
        if veille is not None and event.GetEventObject() is self.fenetre:
            veille.join(2.0)
            print("UI432_VEILLE_JOINTE vivante=%s" % veille.is_alive(), flush=True)
    Diag.Diagnostic._on_destruction = _on_destruction
atexit.register(lambda: print("UI432_ATEXIT", flush=True))
sys.argv = [test, "--corrige"]
runpy.run_path(test, run_name="__main__")
print("UI432_FIN_SCENARIO", flush=True)
gc.collect()
print("UI432_GC", flush=True)
if variante == "os_exit":
    sys.stdout.flush()
    os._exit(0)
"""


def executer(variante, timeout):
    env = dict(os.environ, UI432_VARIANTE=variante, UI432_TEST=str(TEST))
    env.pop("NOETHYS_SL_UI_DIAG", None)
    try:
        p = subprocess.run([sys.executable, "-X", "faulthandler", "-c", ENFANT],
                           cwd=ROOT / "noethys", env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return dict(code="timeout", phase="timeout", extrait="")
    sortie = p.stdout.splitlines()
    phase = "debut"
    for marqueur in MARQUEURS:
        if any(l.startswith(marqueur) for l in sortie):
            phase = marqueur
    extrait = ""
    if p.returncode != 0:
        lignes = p.stderr.splitlines()
        debut = next((i for i, l in enumerate(lignes) if "fatal exception" in l.lower()), max(0, len(lignes) - 40))
        extrait = "\n".join(lignes[debut:debut + 60])
    return dict(code=p.returncode, phase=phase, extrait=extrait)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=30)
    parser.add_argument("--variantes", default=",".join(VARIANTES))
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    if sys.platform != "win32":
        print("Campagne reservee a Windows")
        return 0
    bilan = {}
    for variante in args.variantes.split(","):
        codes = collections.Counter()
        phases = collections.Counter()
        extraits = []
        for i in range(args.repetitions):
            r = executer(variante, args.timeout)
            codes[str(r["code"])] += 1
            if r["code"] != 0:
                phases[r["phase"]] += 1
                if len(extraits) < 3:
                    extraits.append(r["extrait"])
            print("UI432_RUN variante=%s n=%d code=%s phase=%s" % (variante, i + 1, r["code"], r["phase"]), flush=True)
        bilan[variante] = dict(codes=dict(codes), phases_echec=dict(phases))
        for n, extrait in enumerate(extraits, 1):
            print("----- UI432_EXTRAIT %s #%d -----\n%s" % (variante, n, extrait), flush=True)
    texte = json.dumps(bilan, indent=1, sort_keys=True)
    print("UI432_BILAN " + texte, flush=True)
    resume = os.environ.get("GITHUB_STEP_SUMMARY")
    if resume:
        with open(resume, "a", encoding="utf-8") as f:
            f.write("### Campagne #432 sortie wx\n\n```json\n%s\n```\n" % texte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
