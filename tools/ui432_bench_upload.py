# -*- coding: utf-8 -*-
"""Banc #432 : Upload_data reel sur une base Noethys SQLite fictive volumineuse.

Execute le vrai UTILS_Portail_synchro.Synchro.Upload_data dans un thread nomme
comme la synchro automatique, avec hebergement local (repertoire temporaire),
schema Connecthys de reference et un serveur HTTP local repondant a syncup.
Pendant ce temps, le thread principal mesure sa reactivite par des "ticks"
d'appels wx (sans aucune fenetre) et une sonde mesure la disponibilite du GIL.

Aucune donnee reelle, aucun reseau hors 127.0.0.1, aucun email.
Usage : python tools/ui432_bench_upload.py [--familles 1000] [--profil]
"""
import argparse
import contextlib
import copy
import cProfile
import datetime
import io
import json
import os
import pstats
import queue
import random
import shutil
import sqlite3
import statistics
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for chemin in (ROOT / "noethys", ROOT / "tests"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))
os.chdir(ROOT / "noethys")

import _garde_reseau  # noqa: E402,F401  interdit tout acces reseau non local
import wx  # noqa: E402
import GestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402
from Dlg import DLG_Portail_config  # noqa: E402
from Utils import UTILS_Portail_synchro  # noqa: E402
try:
    from Utils import UTILS_Priorite_ui  # noqa: E402
except ImportError:  # arbre anterieur au correctif (mesure de reference)
    UTILS_Priorite_ui = None
from _fixtures_noethys_db import RedirectionGestionDB  # noqa: E402
from test_audit_reseau_connecthys import ServeurHTTPLocal, params_synchro, repondre  # noqa: E402

MODELS = ROOT / "tests" / "fixtures" / "connecthys_models_reference.py"
NOM_THREAD = "Noethys-Connecthys-synchro"


def creer_base(chemin, familles, graine=432):
    """Volumes proportionnels au nombre de familles ; valeurs fictives."""
    rnd = random.Random(graine)
    db = GestionDB.DB(nomFichier=chemin, suffixe=None, modeCreation=True)
    for nom in Tables.DB_DATA:
        db.CreationTable(nom, dicoDB=Tables.DB_DATA)
    db.CreationTable("documents", dicoDB=Tables.DB_DOCUMENTS)
    db.Commit()
    db.Close()
    cnx = sqlite3.connect(chemin)
    c = cnx.cursor()
    today = datetime.date.today()
    j = lambda n: str(today + datetime.timedelta(days=n))
    c.execute("INSERT INTO organisateur (IDorganisateur, nom) VALUES (1, 'Organisateur fictif')")
    nb_act, jours = 20, list(range(-30, 181))
    c.executemany("INSERT INTO activites (IDactivite, nom, date_debut, date_fin, portail_inscriptions_affichage, "
                  "portail_reservations_affichage, portail_unites_multiples, portail_reservations_limite, "
                  "portail_reservations_absenti, nbre_inscrits_max) VALUES (?,?,?,?,1,1,0,NULL,NULL,0)",
                  [(a, "Activite %d" % a, j(-365), j(365)) for a in range(1, nb_act + 1)])
    groupes, unites, periodes, ouvertures = [], [], [], []
    for a in range(1, nb_act + 1):
        for g in (1, 2):
            groupes.append((a * 10 + g, a, "Groupe %d" % g, g, 0))
        for u in (1, 2, 3):
            unites.append((a * 10 + u, a, "Unite %d" % u, str(a * 10 + u), "", u))
        periodes.append((a, a, "Periode", j(-30), j(180), 1, None, None, "", 1))
        for d in jours:
            for u in (1, 2, 3):
                for g in (1, 2):
                    ouvertures.append((a, a * 10 + u, a * 10 + g, j(d)))
    c.executemany("INSERT INTO groupes (IDgroupe, IDactivite, nom, ordre, nbre_inscrits_max) VALUES (?,?,?,?,?)", groupes)
    c.executemany("INSERT INTO portail_unites (IDunite, IDactivite, nom, unites_principales, unites_secondaires, ordre) VALUES (?,?,?,?,?,?)", unites)
    c.executemany("INSERT INTO portail_periodes (IDperiode, IDactivite, nom, date_debut, date_fin, affichage, "
                  "affichage_date_debut, affichage_date_fin, introduction, prefacturation) VALUES (?,?,?,?,?,?,?,?,?,?)", periodes)
    c.executemany("INSERT INTO ouvertures (IDactivite, IDunite, IDgroupe, date) VALUES (?,?,?,?)", ouvertures)
    ind = insc = 0
    fam_rows, cp_rows, ind_rows, rat_rows, insc_rows, conso_rows = [], [], [], [], [], []
    presta_rows, fact_rows, regl_rows, vent_rows = [], [], [], []
    for f in range(1, familles + 1):
        fam_rows.append((f, j(-800), f, 1, "fam%05d" % f, "mdp%05d" % f))
        cp_rows.append((f, f))
        for k in range(rnd.choice((2, 3, 4))):
            ind += 1
            cat = 1 if k < 2 else 2
            ind_rows.append((ind, 1, "NOM%05d" % f, "Prenom%d" % k, j(-365 * (35 if cat == 1 else 8)),
                             "35000", "Ville", "1 rue fictive", "35000", "Ville", "0200000000", "0600000000",
                             "fictif%d@example.invalid" % ind, 0))
            rat_rows.append((ind, f, cat, 1 if k == 0 else 0))
            if cat == 2:
                for a in rnd.sample(range(1, nb_act + 1), 2):
                    insc += 1
                    insc_rows.append((insc, ind, f, a, a * 10 + 1, f, "ok"))
                    for d in jours[::3]:
                        conso_rows.append((ind, insc, a, j(d), a * 10 + 1, a * 10 + 1, "reservation", f))
        for m in range(12):
            presta_rows.append((f, j(-30 * m), "consommation", "Prestation", 12.5, 12.5, 1, f, None))
        for m in range(1, 13):
            fact_rows.append((m + f * 100, m, f, j(-30 * m), j(-30 * m + 15), j(-30 * m - 30), j(-30 * m), 150.0, 150.0, 0.0))
            regl_rows.append((f, j(-30 * m), 1, 150.0))
    c.executemany("INSERT INTO familles (IDfamille, date_creation, IDcompte_payeur, internet_actif, internet_identifiant, internet_mdp) VALUES (?,?,?,?,?,?)", fam_rows)
    c.executemany("INSERT INTO comptes_payeurs (IDcompte_payeur, IDfamille) VALUES (?,?)", cp_rows)
    c.executemany("INSERT INTO individus (IDindividu, IDcivilite, nom, prenom, date_naiss, cp_naiss, ville_naiss, rue_resid, cp_resid, "
                  "ville_resid, tel_domicile, tel_mobile, mail, deces) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ind_rows)
    c.executemany("INSERT INTO rattachements (IDindividu, IDfamille, IDcategorie, titulaire) VALUES (?,?,?,?)", rat_rows)
    c.executemany("INSERT INTO inscriptions (IDinscription, IDindividu, IDfamille, IDactivite, IDgroupe, IDcompte_payeur, statut) VALUES (?,?,?,?,?,?,?)", insc_rows)
    c.executemany("INSERT INTO consommations (IDindividu, IDinscription, IDactivite, date, IDunite, IDgroupe, etat, IDcompte_payeur) VALUES (?,?,?,?,?,?,?,?)", conso_rows)
    c.executemany("INSERT INTO prestations (IDcompte_payeur, date, categorie, label, montant_initial, montant, IDactivite, IDfamille, IDfacture) VALUES (?,?,?,?,?,?,?,?,?)", presta_rows)
    c.executemany("INSERT INTO factures (IDfacture, numero, IDcompte_payeur, date_edition, date_echeance, date_debut, date_fin, total, regle, solde) VALUES (?,?,?,?,?,?,?,?,?,?)", fact_rows)
    c.executemany("INSERT INTO reglements (IDcompte_payeur, date, IDmode, montant) VALUES (?,?,?,?)", regl_rows)
    cnx.commit()
    volumes = {t: c.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in (
        "familles", "individus", "inscriptions", "ouvertures", "consommations", "prestations", "factures", "reglements")}
    cnx.close()
    return volumes


class TempsSansPause:
    """Module time du seul UTILS_Portail_synchro, sans les pauses cosmetiques
    de 0,5 s ; le time.sleep global (sonde, boucle de mesure) reste intact."""

    def __getattr__(self, nom):
        return getattr(time, nom)

    @staticmethod
    def sleep(_secondes):
        pass


class Journal:
    def __init__(self):
        self.lignes = []

    def EcritLog(self, message=""):
        self.lignes.append((time.perf_counter(), message if isinstance(message, str) else repr(message)))

    def SetGauge(self, valeur=0):
        pass


def empreinte_export(temp):
    """Lignes par table de la base d'export ; contenu exact (identifiants
    compris) des tables non chiffrees ouvertures et consommations."""
    import hashlib
    bases = [f for f in os.listdir(temp) if f.startswith("import_") and f.endswith(".db")]
    if len(bases) != 1:
        return {"erreur": "bases d'export : %d" % len(bases)}
    cnx = sqlite3.connect(os.path.join(temp, bases[0]))
    try:
        tables = [r[0] for r in cnx.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        resultat = {"lignes": {t: cnx.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0] for t in tables}}
        for t in tables:
            if True:
                lignes = cnx.execute('SELECT * FROM "%s" ORDER BY 1' % t).fetchall()
                resultat["sha256_" + t] = hashlib.sha256(repr(lignes).encode("utf-8")).hexdigest()
        return resultat
    finally:
        cnx.close()


def conformite_export(chemin_source, temp):
    """Les tables exportees reprennent ligne a ligne, dans l'ordre et avec des
    identifiants 1..N, les ouvertures et consommations sources."""
    base = [f for f in os.listdir(temp) if f.startswith("import_") and f.endswith(".db")]
    if len(base) != 1:
        return False
    src, exp = sqlite3.connect(chemin_source), sqlite3.connect(os.path.join(temp, base[0]))
    try:
        ouv = src.execute("SELECT date, IDunite, IDgroupe FROM ouvertures ORDER BY IDouverture").fetchall()
        con = src.execute("SELECT date, etat, IDunite, IDinscription, IDevenement FROM consommations ORDER BY IDconso").fetchall()
        attendu_ouv = [(i + 1,) + tuple(r) for i, r in enumerate(ouv)]
        attendu_con = [(i + 1,) + tuple(r) for i, r in enumerate(con)]
        obtenu_ouv = exp.execute("SELECT IDouverture, date, IDunite, IDgroupe FROM portail_ouvertures ORDER BY 1").fetchall()
        obtenu_con = exp.execute("SELECT IDconsommation, date, etat, IDunite, IDinscription, IDevenement "
                                 "FROM portail_consommations ORDER BY 1").fetchall()
        return obtenu_ouv == attendu_ouv and obtenu_con == attendu_con
    finally:
        src.close()
        exp.close()


def sonde_gil(arret, mesures):
    """Retard d'un sommeil de 5 ms : temps d'attente du GIL par un thread Python."""
    while not arret.is_set():
        t = time.perf_counter()
        time.sleep(0.005)
        mesures.append(time.perf_counter() - t - 0.005)


def tick_wx(appels):
    for _ in range(appels):
        wx.Point(1, 2) + wx.Point(3, 4)


def executer(familles, profil, appels_par_tick, switch=None, priorite=True, boucle="simulee"):
    if switch:
        sys.setswitchinterval(switch)
    app = wx.App(False)  # aucune fenetre : seul le module wx est sollicite
    tmp = tempfile.mkdtemp(prefix="ui432-bench-")
    try:
        chemin = os.path.join(tmp, "fictif.dat")
        t = time.perf_counter()
        volumes = creer_base(chemin, familles)
        creation = time.perf_counter() - t
        portail = os.path.join(tmp, "portail")
        os.makedirs(os.path.join(portail, "application", "data"))
        shutil.copy(MODELS, os.path.join(portail, "application", "models.py"))
        temp = os.path.join(tmp, "temp")
        os.makedirs(temp)
        journal, resultat, profileur = Journal(), {}, cProfile.Profile() if profil else None
        # Boucle d'evenements simulee : les rappels postes (wx.CallAfter) ne
        # sont executes qu'entre deux traitements du thread principal.
        file_ui = queue.Queue()
        instances = []

        class PrioriteObservee(UTILS_Priorite_ui.PrioriteUI if UTILS_Priorite_ui else object):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                instances.append(self)

        with RedirectionGestionDB(chemin), \
                ServeurHTTPLocal(lambda h: repondre(h, 200, b"True")) as srv, \
                mock.patch.object(UTILS_Portail_synchro.UTILS_Fichiers, "GetRepTemp",
                                  side_effect=lambda fichier="": os.path.join(temp, fichier)), \
                mock.patch.object(UTILS_Portail_synchro, "time", TempsSansPause()),                 (mock.patch.object(UTILS_Priorite_ui, "_poster_wx",
                                   lambda: ((file_ui.put if boucle == "simulee" else wx.CallAfter)
                                            if priorite else None))
                 if UTILS_Priorite_ui else contextlib.nullcontext()),                 (mock.patch.object(UTILS_Priorite_ui, "PrioriteUI", PrioriteObservee)
                 if UTILS_Priorite_ui else contextlib.nullcontext()), \
                contextlib.redirect_stdout(io.StringIO()):
            p = copy.deepcopy(DLG_Portail_config.VALEURS_DEFAUT)
            p.update(params_synchro(srv.url, hebergement_type=0, hebergement_local_repertoire=portail))
            p["image_identification"] = ""
            synchro = UTILS_Portail_synchro.Synchro(dict_parametres=p, log=journal)

            def worker():
                debut = time.perf_counter()
                if profileur:
                    profileur.enable()
                try:
                    resultat["retour"] = synchro.Upload_data()
                except Exception as err:
                    resultat["erreur"] = repr(err)
                finally:
                    if profileur:
                        profileur.disable()
                    resultat["duree_s"] = time.perf_counter() - debut

            arret, gil = threading.Event(), []
            sonde = threading.Thread(target=sonde_gil, args=(arret, gil), daemon=True)
            sonde.start()
            # Reference sans worker
            reference = []
            for _ in range(20):
                t = time.perf_counter(); tick_wx(appels_par_tick); reference.append(time.perf_counter() - t)
                time.sleep(0.02)
            th = threading.Thread(target=worker, name=NOM_THREAD)
            ticks, retards = [], []
            if boucle == "wx":
                # Vraie boucle wx (frame jamais affichee) : les pongs passent
                # par wx.CallAfter comme dans Noethys. Runner isole uniquement.
                frame = wx.Frame(None)

                def traitement():
                    t = time.perf_counter()
                    tick_wx(appels_par_tick)
                    ticks.append(time.perf_counter() - t)
                    if th.is_alive():
                        wx.CallLater(20, traitement)
                    else:
                        frame.Destroy()

                th.start()
                wx.CallLater(20, traitement)
                app.MainLoop()
            else:
                th.start()
            prochain = time.perf_counter()
            def traiter_file(jusqua):
                while True:
                    reste = jusqua - time.perf_counter()
                    try:
                        rappel = file_ui.get(timeout=max(0.0, reste)) if reste > 0 else file_ui.get_nowait()
                    except queue.Empty:
                        return
                    rappel()

            while boucle != "wx" and th.is_alive():
                maintenant = time.perf_counter()
                retards.append(max(0.0, maintenant - prochain))
                t = maintenant
                tick_wx(appels_par_tick)
                ticks.append(time.perf_counter() - t)
                prochain = time.perf_counter() + 0.02
                traiter_file(prochain)
            th.join()
            arret.set()
        export = empreinte_export(temp)
        export["conforme_source"] = conformite_export(chemin, temp)
        phases = []
        for (t0, msg), (t1, _) in zip(journal.lignes, journal.lignes[1:] + [(journal.lignes[-1][0], "")]):
            phases.append((msg[:60], round(t1 - t0, 3)))
        ms = lambda v: round(v * 1000, 2)
        bilan = dict(
            familles=familles, volumes=volumes, creation_base_s=round(creation, 2),
            upload=dict(retour=resultat.get("retour"), erreur=resultat.get("erreur"),
                        duree_s=round(resultat.get("duree_s", 0), 2)),
            switch_interval_s=sys.getswitchinterval(), appels_wx_par_tick=appels_par_tick,
            boucle=boucle,
            priorite_ui=dict(active=priorite, pauses=sum(i.pauses for i in instances),
                             duree_pauses_s=round(sum(i.duree_pauses for i in instances), 2)),
            tick_reference_ms=dict(median=ms(statistics.median(reference)), max=ms(max(reference))),
            tick_pendant_ms=dict(n=len(ticks), median=ms(statistics.median(ticks)) if ticks else None,
                                 p95=ms(sorted(ticks)[int(len(ticks) * 0.95)]) if ticks else None,
                                 max=ms(max(ticks)) if ticks else None,
                                 total_s=round(sum(ticks), 2)),
            gil_sonde_ms=dict(n=len(gil), median=ms(statistics.median(gil)) if gil else None,
                              max=ms(max(gil)) if gil else None),
            phases_s=[ph for ph in phases if ph[1] >= 0.2],
            export=export,
        )
        if profileur:
            flux = io.StringIO()
            pstats.Stats(profileur, stream=flux).sort_stats("cumulative").print_stats(30)
            bilan["profil"] = flux.getvalue()
        return bilan
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        app.Destroy() if hasattr(app, "Destroy") else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--familles", type=int, default=1000)
    parser.add_argument("--appels", type=int, default=500, help="appels wx par tick")
    parser.add_argument("--switch", type=float, default=None)
    parser.add_argument("--profil", action="store_true")
    parser.add_argument("--sans-priorite", action="store_true")
    parser.add_argument("--boucle", choices=("simulee", "wx"), default="simulee")
    args = parser.parse_args()
    bilan = executer(args.familles, args.profil, args.appels, args.switch, not args.sans_priorite, args.boucle)
    profil = bilan.pop("profil", None)
    print("UI432_BENCH " + json.dumps(bilan, ensure_ascii=False, indent=1), flush=True)
    if profil:
        print(profil)
    return 0


if __name__ == "__main__":
    sys.exit(main())
