# -*- coding: utf-8 -*-
"""UI-432K : rendu Noedoc par le vrai Noethys.exe PyInstaller installe.

Le parent est le Python du runner (fixture SQLite), mais le processus enfant
qui rend le PDF est obligatoirement Noethys.exe installe. Aucun profil reel,
aucun appel Connecthys, aucun email ni publication. Ce test ne demontre pas
encore que le parent GUI de l'application installee reste reactif.
"""
import faulthandler
import multiprocessing
from multiprocessing import spawn
import os
from pathlib import Path
import re
import sys
import tempfile
from unittest import mock


def verifier():
    if sys.platform != "win32" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("STOP : recette reservee au runner Windows GitHub Actions")
    if len(sys.argv) != 2:
        raise SystemExit("Usage : recette_ui432k_pdf_installe.py EXE")
    if not os.environ.get("RUNNER_TEMP"):
        raise SystemExit("STOP : RUNNER_TEMP absent")
    # Un unique diagnostic de pile en cas de gel (fixture anonyme uniquement).
    faulthandler.enable()
    faulthandler.dump_traceback_later(75, repeat=False, file=sys.stderr)
    print("UI432K_INSTALLE_PHASE preparation", flush=True)

    temporaire_runner = Path(os.environ["RUNNER_TEMP"]).resolve()
    executable = Path(sys.argv[1]).resolve()
    if (executable.name.lower() != "noethys.exe"
            or temporaire_runner not in executable.parents
            or not executable.is_file()):
        raise SystemExit("STOP : Noethys.exe installe hors du runner ou absent")

    depot = Path(__file__).resolve().parents[1]
    for chemin in (depot, depot / "tests", depot / "noethys"):
        sys.path.insert(0, str(chemin))
    # Charger popen_spawn_win32 AVANT d'usurper sys.executable : sinon
    # son indicateur WINENV est calcule pour un environnement virtuel
    # fictif et le moteur Windows substitue python.exe a Noethys.exe.
    from multiprocessing import popen_spawn_win32
    import _garde_reseau
    import wx
    print("UI432K_INSTALLE_ETAPE imports", flush=True)
    from _fixtures_noethys_db import RedirectionGestionDB, _DEFAUTS_OBJET
    from tests.test_vanilla_facture_prestation_sans_activite import (
        _creer_base_facture_avec_prestation_sans_activite, _dict_options_minimal)
    from Utils import (UTILS_Facturation, UTILS_Impression_facture,
                       UTILS_PDF_processus, UTILS_PDF_securise)

    os.chdir(str(depot / "noethys"))
    app = wx.GetApp() or wx.App(False)
    print("UI432K_INSTALLE_ETAPE fixture_debut", flush=True)
    base, modele = _creer_base_facture_avec_prestation_sans_activite()
    print("UI432K_INSTALLE_ETAPE fixture_ok", flush=True)
    print("UI432K_INSTALLE_PHASE base_fictive", flush=True)

    try:
        options = _dict_options_minimal(modele)
        with RedirectionGestionDB(base.chemin):
            facturation = UTILS_Facturation.Facturation()
            resultat = facturation.GetDonneesImpression(
                listeFactures=[1], dictOptions=options, parent=None)
        if resultat is False:
            raise AssertionError("Donnees de facture fictives indisponibles")
        comptes = resultat[0]
        comptes, options = UTILS_PDF_processus.Preparer(comptes, options)
        print("UI432K_INSTALLE_ETAPE comptes_prets", flush=True)

        # La preparation du spawn doit reproduire le cas d'un parent gele,
        # sans transmettre les chemins des sources/tests ni site-packages.
        # WINEXE est calcule A L'IMPORT dans multiprocessing.spawn.
        ancien_executable = spawn.get_executable()
        chemins_enfant = [str(executable.parent)]
        if any(str(depot).lower() in p.lower() for p in chemins_enfant):
            raise AssertionError("Source du depot transmise au processus gele")
        try:
            with tempfile.TemporaryDirectory(
                    dir=str(temporaire_runner),
                    prefix="ui432k-exe-fictif-") as dossier:
                for bloc_texte in (False, True):
                    if bloc_texte:
                        objet = dict(_DEFAUTS_OBJET)
                        objet.update({
                            "IDmodele": modele, "nom": "Texte fictif",
                            "categorie": "bloc_texte", "ordre": 1,
                            "x": 22, "y": 235, "largeur": 115,
                            "hauteur": 35,
                            "texte": "Facture de test\\nSans donnees utilisateur",
                            "largeurTexte": 100,
                        })
                        base.db.ReqInsert("documents_objets", list(objet.items()))
                        base.db.Commit()

                    suffixe = "avec-texte" if bloc_texte else "standard"
                    reference = str(Path(dossier) / ("reference-" + suffixe + ".pdf"))
                    fichier = str(Path(dossier) / ("installe-" + suffixe + ".pdf"))
                    print("UI432K_INSTALLE_PHASE reference_" + suffixe, flush=True)
                    print("UI432K_INSTALLE_ETAPE reference_" + suffixe, flush=True)
                    with RedirectionGestionDB(base.chemin):
                        UTILS_Impression_facture.Impression(
                            comptes, options, IDmodele=modele,
                            ouverture=False, nomFichier=reference)

                    # multiprocessing.spawn.get_command_line() utilise
                    # sys.executable (et non set_executable) en mode frozen.
                    # Sans cette substitution le test lancerait python.exe
                    # et produirait un faux PASS du binaire installe.
                    multiprocessing.set_executable(str(executable))
                    with mock.patch.object(sys, "frozen", True, create=True), \
                         mock.patch.object(sys, "executable", str(executable)), \
                         mock.patch.object(spawn, "WINEXE", True), \
                         mock.patch.object(popen_spawn_win32, "WINENV", False), \
                         mock.patch.object(sys, "path", chemins_enfant), \
                         mock.patch.dict(os.environ, {"PYTHONPATH": ""}):
                        commande = spawn.get_command_line(
                            parent_pid=os.getpid(), pipe_handle=100)
                        if (Path(commande[0]).resolve() != executable or
                                "--multiprocessing-fork" not in commande):
                            raise AssertionError(
                                "Le processus enfant ne lance pas Noethys.exe")
                        # L'enfant ne doit ni importer ni lire les sources
                        # et ressources du depot depuis le cwd du parent.
                        print("UI432K_INSTALLE_ETAPE spawn_" + suffixe, flush=True)
                        dossier_initial = Path.cwd()
                        try:
                            os.chdir(str(executable.parent))
                            print("UI432K_INSTALLE_PHASE spawn_" + suffixe, flush=True)
                            UTILS_PDF_securise.Generer(
                                fichier, lambda provisoire:
                                    UTILS_PDF_processus.Generer(
                                        comptes, options, modele, provisoire,
                                        base.chemin, delai=90, donnees_pretes=True))
                        finally:
                            os.chdir(str(dossier_initial))
                        print("UI432K_INSTALLE_ETAPE enfant_termine_" + suffixe, flush=True)

                    ancien = Path(reference).read_bytes()
                    nouveau = Path(fichier).read_bytes()
                    for pdf in (ancien, nouveau):
                        if not pdf.startswith(b"%PDF-") or b"%%EOF" not in pdf[-2048:]:
                            raise AssertionError("PDF reel non valide : " + suffixe)
                    pages = lambda contenu: len(
                        re.findall(rb"/Type\s*/Page\b", contenu))
                    if pages(ancien) == 0 or pages(ancien) != pages(nouveau):
                        raise AssertionError("Pages PDF divergentes : " + suffixe)
                    if abs(len(ancien) - len(nouveau)) >= max(
                            2000, int(len(ancien) * 0.10)):
                        raise AssertionError("Taille PDF divergente : " + suffixe)
                    print("UI432K_INSTALLE_PASS " + suffixe, flush=True)
        finally:
            multiprocessing.set_executable(ancien_executable)
        if _garde_reseau.TENTATIVES:
            raise AssertionError("Tentative reseau dans le processus de recette")
    finally:
        base.fermer()
        app.Destroy()


if __name__ == "__main__":
    verifier()
