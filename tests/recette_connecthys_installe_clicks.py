# -*- coding: utf-8 -*-
"""Recette CLI : clics dans Noethys.exe INSTALLE sur un fichier fictif.

PRECONDITIONS : GitHub Actions Windows, dossier RUNNER_TEMP, base Recette_DATA.dat
generee par recette_creer_fichier_fictif.py. Aucun appel HTTP, SMTP ou Connecthys
reel. La CI doit bloquer les sorties reseau de l'executable.
"""
import datetime
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import traceback
from pathlib import Path

if os.name != "nt" or os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("STOP : seulement sur runner Windows ephemere GitHub Actions")
if len(sys.argv) != 4:
    raise SystemExit("Usage: recette_connecthys_installe_clicks.py EXE DB SORTIE")

root = Path(os.environ["RUNNER_TEMP"]).resolve()
exe = Path(sys.argv[1]).resolve()
dbpath = Path(sys.argv[2]).resolve()
sortie = Path(sys.argv[3]).resolve()
for cible in (exe, dbpath, sortie):
    if cible != root and root not in cible.parents:
        raise SystemExit("STOP : chemin hors RUNNER_TEMP : %s" % cible)
if exe.name.lower() != "noethys.exe" or dbpath.name != "Recette_DATA.dat":
    raise SystemExit("STOP : executable/base non reconnus")
if not exe.is_file() or not dbpath.is_file():
    raise SystemExit("STOP : executable/base fictive absents")
sortie.mkdir(parents=True, exist_ok=True)

import pywinauto
from pywinauto import Desktop, mouse, keyboard

DATE = "2026-10-15"
INSCRIPTION = 1
IDUNITE = 1
PARENT = 1


def lire():
    con = sqlite3.connect(str(dbpath), timeout=10)
    try:
        return dict(
            demandes=con.execute(
                "SELECT IDaction,etat FROM portail_actions "
                "WHERE IDaction IN (1001,1002) ORDER BY IDaction").fetchall(),
            consommations=con.execute(
                "SELECT IDconso,IDindividu,IDunite,date,etat FROM consommations "
                "WHERE IDindividu=2 AND IDunite=? AND date=? ORDER BY IDconso",
                (IDUNITE, DATE)).fetchall(),
            marqueurs=con.execute(
                "SELECT categorie,nom FROM parametres "
                "WHERE categorie='noethys_sl_reservations_tentatives'").fetchall())
    finally:
        con.close()


def preparer():
    with sqlite3.connect(str(dbpath), timeout=15) as con:
        tables = {x[0] for x in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ("portail_actions", "portail_periodes", "portail_unites",
                  "portail_reservations", "consommations", "inscriptions", "ouvertures"):
            if t not in tables:
                raise AssertionError("Table requise absente : %s" % t)
        if con.execute("SELECT COUNT(*) FROM portail_actions WHERE IDaction>=1001").fetchone()[0]:
            raise AssertionError("Fixture deja appliquee : refus de reprendre un etat non vierge")
        # Eviter la proposition de ventilation au chargement du fichier de
        # test : ce reglement non ventile appartient a la fixture generique,
        # jamais a la demande portail de cette recette.
        con.execute("DELETE FROM reglements WHERE IDreglement=1")
        con.execute("INSERT INTO portail_periodes "
                    "(IDperiode,IDactivite,nom,date_debut,date_fin,affichage) "
                    "VALUES (101,1,'Periode fictive','2026-10-05','2026-10-30',1)")
        con.execute("INSERT INTO portail_unites "
                    "(IDunite,IDactivite,nom,unites_principales,unites_secondaires,ordre) "
                    "VALUES (101,1,'Journee fictive','1','',1)")
        params = "IDactivite=1#date_debut_periode=2026-10-05#date_fin_periode=2026-10-30"
        for action, etat, date_action, operation in (
            (1001, 1, "2026-10-13 09:05:00", "ajout"),
            (1002, 0, "2026-10-14 10:15:00", "suppression")):
            con.execute(
                "INSERT INTO portail_actions "
                "(IDaction,horodatage,IDfamille,IDindividu,categorie,action,"
                "description,commentaire,parametres,etat,IDperiode) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (action,date_action,PARENT,2,"reservations","saisie",
                 "Demande de %s fictive" % operation,"",
                 params,"attente",101))
            con.execute(
                "INSERT INTO portail_reservations "
                "(IDreservation,date,IDinscription,IDunite,IDaction,etat) "
                "VALUES (?,?,?,?,?,?)",
                (action,DATE,INSCRIPTION,101,action,etat))
    # Premier demarrage d'une application empaquetee : sans cette valeur
    # fictive, la modale Bienvenue bloque l'ouverture differee du fichier.
    profil=exe.parent/"Portable"/"Config.json"
    if not profil.is_file():
        raise AssertionError("Profil de recette attendu absent")
    with profil.open("r",encoding="utf-8") as entree:
        config=json.load(entree)
    if config.get("nomFichier")!="Recette":
        raise AssertionError("Profil utilisateur non fictif : STOP")
    config["annonce"]=[999,999,999,999]
    config["assistant_demarrage"]=True
    config["propose_maj"]=False
    with profil.open("w",encoding="utf-8") as sortie_config:
        json.dump(config,sortie_config,ensure_ascii=False)
    print("FICTIVE_FIXTURE",lire(),flush=True)


def liste_fenetres(pid):
    windows = Desktop(backend="win32").windows(process=pid,visible_only=True)
    return [(w.window_text(),w.class_name(),hex(w.handle),w) for w in windows]


def attendre(pid,texte,limite=25,exclure=None):
    stop=time.monotonic()+limite
    derniere=[]
    while time.monotonic()<stop:
        ws=liste_fenetres(pid)
        derniere=[(a,b,h) for a,b,h,_ in ws]
        for title,cls,handle,win in ws:
            if texte.lower() in title.lower() and (not exclure or exclure not in title):
                print("WINDOW_FOUND",title,cls,handle,flush=True)
                return win
        time.sleep(0.5)
    raise AssertionError("Fenetre absente '%s', visibles=%r"%(texte,derniere))


def capture(win,name):
    try:
        fichier=sortie/name
        win.capture_as_image().save(str(fichier))
        print("CAPTURE",fichier.name,fichier.stat().st_size,flush=True)
    except Exception as e:
        print("CAPTURE_NON_DISPONIBLE",type(e).__name__,str(e)[:300],flush=True)


def etiquettes(win):
    try:
        elements=win.descendants()
        infos=[(e.window_text(),e.class_name()) for e in elements
               if e.window_text()][:60]
        print("LABELS",repr(infos),flush=True)
    except Exception as e:
        print("LABELS_ERREUR",repr(e),flush=True)


def cliquer(win,libelle):
    # La recherche est bornee au dialogue de la base fictive.
    for backend in ("win32","uia"):
        try:
            w=Desktop(backend=backend).window(handle=win.handle)
            controls=w.descendants()
            matches=[c for c in controls if
                     c.window_text().strip().lower()==libelle.lower() and
                     c.is_visible() and c.is_enabled()]
            if not matches:
                matches=[c for c in controls if libelle.lower() in
                         c.window_text().strip().lower() and
                         c.is_visible() and c.is_enabled()]
            if matches:
                button=matches[0]
                print("CLICK",libelle,backend,button.class_name(),flush=True)
                button.click_input()
                return
        except Exception as e:
            print("CLICK_RETRY",backend,libelle,str(e)[:160],flush=True)
    raise AssertionError("Bouton non trouve : "+libelle)


def valider_saisie(auto=True):
    print("ASSERT_AVANT",lire(),flush=True)
    main=attendre(proc.pid,"Noethys",limite=70)
    print("FENETRES_DEMARRAGE",[(a,b,h) for a,b,h,_ in liste_fenetres(proc.pid)],flush=True)
    capture(main,"00_main_fictif.png")
    # L'ouverture du dernier fichier passe par une authentification
    # GUI reelle. Mot de passe uniquement du compte de recette fictif.
    authentifie=False
    fichier_ouvert=False
    stop=time.monotonic()+55
    while time.monotonic()<stop:
        noms=liste_fenetres(proc.pid)
        if "[Recette]" in main.window_text():
            fichier_ouvert=True
            break
        for titre,cls,handle,fenetre in noms:
            if titre.startswith("Ouverture du fichier Recette"):
                if not authentifie:
                    print("IDENTIFICATION_FICTIVE",titre,flush=True)
                    capture(fenetre,"00_identification_fictive.png")
                    fenetre.set_focus()
                    keyboard.send_keys("recette2026",pause=0.06)
                    authentifie=True
                    time.sleep(1)
            elif titre=="Bienvenue":
                raise AssertionError("La modale de bienvenue ne devait pas etre visible dans le profil fictif")
        time.sleep(0.5)
    print("FICHIER_FICTIF_OUVERT",fichier_ouvert, "AUTH",authentifie,
          "TITLE",main.window_text(),flush=True)
    if not fichier_ouvert:
        raise AssertionError("Base fictive non ouverte : "+
                             repr([(t,c) for t,c,h,w in liste_fenetres(proc.pid)]))
    etiquettes(main)
    try:
        menus=[i.text() for i in main.menu().items()]
        print("MENUS",repr(menus),flush=True)
    except Exception as exc:
        print("MENUS_DIAGNOSTIC",repr(exc),flush=True)
    # Ne JAMAIS cliquer sur une autre rubrique par defaut : STOP franc.
    print("NAVIGATE_Outils",flush=True)
    main.menu_select("Outils->Traiter les demandes du portail")
    liste=attendre(proc.pid,"Traitement des demandes",limite=20,exclure="[")
    capture(liste,"01_liste_portail_fictive.png")
    etiquettes(liste)
    for element in liste.descendants():
        try:
            if element.class_name() in ("SysListView32","wxWindowNR"):
                if hasattr(element,"item_count"):
                    print("LISTE_COMPTE",element.class_name(),element.window_text(),
                          element.item_count(),flush=True)
        except Exception:
            pass
    cliquer(liste,"Commencer")
    time.sleep(2)
    print("FENETRES_APRES_COMMENCER",
          [(a,b,h) for a,b,h,_ in liste_fenetres(proc.pid)],flush=True)
    etiquettes(liste)
    demande=attendre(proc.pid,"Traitement des demandes [",limite=12)
    capture(demande,"02_demande_fictive_avant.png")
    etiquettes(demande)
    cliquer(demande,"Automatique" if auto else "Manuel")
    time.sleep(3)
    print("FENETRES_APRES_CLIC",[(a,b,h) for a,b,h,_ in liste_fenetres(proc.pid)],flush=True)
    capture(demande,"03_demande_fictive_apres.png")
    print("SQL_APRES_CLIC",lire(),flush=True)
    etats=dict(lire()["demandes"])
    if etats.get(1001)!="validation":
        raise AssertionError("Demande ajout 1001 non validee : "+str(etats))
    if not lire()["consommations"]:
        raise AssertionError("Aucune consommation enregistree apres clic automatique")
    print("E2E_CLIC_AUTOMATIQUE_PASS",flush=True)


preparer()
proc=None
try:
    diagnostic=sortie/"diagnostic-installe.log"
    env=os.environ.copy()
    env["NOETHYS_DIAGNOSTIC_DEMARRAGE"]=str(diagnostic)
    env["NOETHYS_DIAGNOSTIC_DELAI_PILES"]="15"
    env["NOETHYS_SL_RECETTE_CONNECTHYS_DIAGNOSTIC"]="1"
    proc=subprocess.Popen([str(exe)],cwd=str(exe.parent),env=env)
    valider_saisie()
finally:
    if proc is not None:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
    print("SQL_FINAL",lire(),flush=True)
    # Journal redirige par le vrai Noethys.exe dans le Portable FICTIF.
    # Ne jamais extraire de journal depuis un profil utilisateur reel.
    journal=exe.parent/"Portable"/"journal.log"
    if journal.is_file() and (exe.parent/"Portable"/"Data"/"Recette_DATA.dat").is_file():
        texte=journal.read_text(encoding="utf-8",errors="replace")
        print("JOURNAL_FICTIF_FIN",texte[-12000:],flush=True)
        (sortie/"journal-fictif.log").write_text(texte[-12000:],encoding="utf-8")

