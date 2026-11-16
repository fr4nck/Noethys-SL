# -*- coding: utf-8 -*-
"""#435 : deux actions distinctes, vrais traitements et connexions isolees.

La grille est un double : lectures/ecritures MySQL reelles, planificateur,
SaisieConso, Traitement et finalisation de production. Aucun profil PMSL,
aucun email. Les deux postes sont deux processus Python independants.
"""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace as NS
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for chemin in (ROOT, ROOT / "noethys", ROOT / "tests"):
    sys.path.insert(0, str(chemin))

import _garde_reseau
import GestionDB
from _fixtures_noethys_db import RedirectionGestionDB
from tests import test_connecthys_ui3c1_reconciliation as recette
from tests import test_connecthys_reprises_mysql as mysql
from Utils import UTILS_Portail_reconciliation as Marqueurs

DAY = datetime.date(2026, 11, 4)


@unittest.skipIf(recette.Module is None, "wxPython requis")
class FamilleSQLiteTests(unittest.TestCase):
    setUp = recette.ReconciliationTests.setUp

    def test_actions_distinctes_meme_famille_ne_sont_pas_simultanees(self):
        with Marqueurs.ExecutionExclusive(7):
            with self.assertRaises(Marqueurs.ReconciliationRequise):
                with Marqueurs.ExecutionExclusive(8):
                    self.fail("Deux actions de la famille entrent dans la grille")
        with Marqueurs.ExecutionExclusive(8):
            pass

    def test_autre_famille_reste_accessible_et_exception_libere(self):
        self.base.inserer("portail_actions", ["IDaction", "IDfamille", "etat"],
                          [(9, 4, "attente")])
        with self.assertRaisesRegex(RuntimeError, "panne fictive"):
            with Marqueurs.ExecutionExclusive(7):
                with Marqueurs.ExecutionExclusive(9):
                    raise RuntimeError("panne fictive")
        with Marqueurs.ExecutionExclusive(8):
            pass

    def test_famille_inconnue_refuse_avant_la_grille(self):
        for identifiant in (999, 10):
            if identifiant == 10:
                self.base.inserer("portail_actions", ["IDaction", "etat"],
                                  [(10, "attente")])
            with self.assertRaises(Marqueurs.ReconciliationRequise):
                with Marqueurs.ExecutionExclusive(identifiant):
                    self.fail("Action sans famille acceptee")


class GrilleDurable(recette.GrilleQuantite):
    """Snapshot de lecture, puis insertion des seules cases modifiees."""
    def __init__(self, fixture, enfant, barriere=None):
        super().__init__(fixture)
        self.enfant = enfant
        self.barriere = barriere
        self.grille.dictUnites[103] = dict(self.grille.dictUnites[101])
        self.modifiees = set()
        self.etats = {}

    def InitGrille(self, **kwargs):
        db = self.fixture.base.db
        db.cursor.execute("SELECT IDunite, quantite, etat FROM consommations "
                          "WHERE IDindividu=%s AND date=%s", (self.enfant, DAY))
        self.quantites = {101: 0, 102: 0, 103: 0}
        self.etats = {}
        for unite, quantite, etat in db.cursor.fetchall():
            self.quantites[unite] = quantite
            self.etats[unite] = etat
        db.connexion.commit()  # pas de snapshot MySQL conserve entre les lectures

    def GetCase(self, IDunite, date):
        case = super().GetCase(IDunite, date)
        case.etat = self.etats.get(IDunite)
        case.IDfacture = None
        case.verrouillage = 0
        if case.etat is not None:
            conso = NS(etat=case.etat, IDinscription=77,
                       IDfacture=None, verrouillage=0)
            case.GetListeConso = lambda: [conso]
        clic = case.OnClick

        def enregistrer(**kwargs):
            clic(**kwargs)
            self.etats[IDunite] = "reservation"
            self.modifiees.add(IDunite)
        case.OnClick = enregistrer
        return case

    def Sauvegarde(self):
        self.saves += 1
        if self.barriere:
            (self.barriere / "A_avant_save").write_text("1")
            limite = time.monotonic() + 45
            while not (self.barriere / "A_continuer").exists():
                if time.monotonic() > limite:
                    raise RuntimeError("Barriere de test expiree")
                time.sleep(0.05)
        db = self.fixture.base.db
        for unite in sorted(self.modifiees):
            db.cursor.execute(
                "INSERT INTO consommations (IDindividu, IDactivite, "
                "IDinscription, date, IDunite, quantite, etat) "
                "VALUES (%s, 1, 77, %s, %s, %s, %s)",
                (self.enfant, DAY, unite, self.quantites[unite], self.etats[unite]))
        db.connexion.commit()


def travailleur(base, action, sortie, pause):
    """Executer la vraie methode Dialog.Traitement dans un second processus."""
    with _garde_reseau.ServeurMySQLDeTest() as p:
        nom = "%d;%s;%s;%s[RESEAU]%s" % (
            p["port"], p["hote"], p["utilisateur"],
            GestionDB.EncodeMdpReseau(p["motdepasse"]), base)
        with RedirectionGestionDB(nom):
            db = GestionDB.DB()
            try:
                ui = recette.precedent.DialogueFictif()
                fixture = NS(base=NS(db=db))
                recette.ReconciliationTests.configurer_ui(fixture, ui)
                ui.track.IDaction = action
                ui.track.IDfamille = 2 if action == 9 else 1
                ui.track.IDindividu = 200 if action == 9 else 100
                ui.dictUnites[3] = dict(ui.dictUnites[2],
                                       unites_principales=[103])
                for numero, role in ((1, "journee"), (2, "matin"), (3, "apres_midi")):
                    ui.dictUnites[numero]["role_portail"] = role
                ui.ctrl_grille = GrilleDurable(
                    fixture, ui.track.IDindividu, Path(sortie) if pause else None)
                with mock.patch.object(recette.Module.Traitement, "Verifier_ventilation"), \
                        mock.patch.object(recette.Module.wx, "MessageDialog"), \
                        mock.patch.object(recette.Module.UTILS_Envoi_email, "EnvoiEmailFamille",
                                          side_effect=AssertionError("Email interdit")):
                    ui.Traitement()
                db.cursor.execute("SELECT etat FROM portail_actions WHERE IDaction=%s", (action,))
                etat = db.cursor.fetchone()[0]
                resultat = dict(etat=etat, saves=ui.ctrl_grille.saves,
                                saisies=ui.ctrl_grille.saisies)
                (Path(sortie) / ("%s.json" % action)).write_text(json.dumps(resultat))
            finally:
                db.Close()


@unittest.skipUnless(os.environ.get("NOETHYS_TEST_MYSQL_HOST"), "MySQL local jetable requis")
class ActionsMySQLTests(unittest.TestCase):
    _nom = mysql.SuiviConnecthysMySQLTests._nom
    connexion = mysql.SuiviConnecthysMySQLTests.connexion
    lignes = mysql.SuiviConnecthysMySQLTests.lignes

    def setUp(self):
        mysql.SuiviConnecthysMySQLTests.setUp(self)
        db = self.connexion()
        try:
            for table in ("portail_reservations", "portail_unites"):
                db.CreationTable(table, dicoDB=mysql.Tables.DB_DATA)
            for sql in (
                "DELETE FROM consommations",
                "INSERT INTO portail_actions (IDaction,IDfamille,etat) VALUES (8,1,'attente'),(9,2,'attente')",
                "INSERT INTO portail_unites (IDunite,nom) VALUES (1,'Journee'),(2,'Matin'),(3,'Apres-midi')",
                "INSERT INTO portail_reservations (IDreservation,IDaction,date,IDinscription,IDunite,etat) VALUES "
                "(71,7,'2026-11-04',77,1,1),(81,8,'2026-11-04',77,2,1),"
                "(82,8,'2026-11-04',77,3,1),(91,9,'2026-11-04',77,2,1)",
            ):
                db.cursor.execute(sql)
            db.Commit()
        finally:
            db.Close()
        dossier = tempfile.TemporaryDirectory(prefix="connecthys-deux-postes-")
        self.addCleanup(dossier.cleanup)
        self.sortie = Path(dossier.name)

    def lancer(self, action, pause=False):
        processus = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--worker", self.base,
             str(action), str(self.sortie), "1" if pause else "0"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        def arreter():
            if processus.poll() is None:
                processus.kill()
            processus.communicate(timeout=10)
        self.addCleanup(arreter)
        return processus

    def terminer(self, processus, action):
        journal, _ = processus.communicate(timeout=60)
        self.assertEqual(processus.returncode, 0, journal.decode(errors="replace")[-6000:])
        return json.loads((self.sortie / ("%s.json" % action)).read_text())

    def scenario(self, autre_action):
        poste_a = self.lancer(7, pause=True)
        limite = time.monotonic() + 40
        while not (self.sortie / "A_avant_save").exists():
            self.assertIsNone(poste_a.poll(), "A termine avant la sauvegarde")
            self.assertLess(time.monotonic(), limite, "A n'atteint pas la grille")
            time.sleep(0.05)
        try:
            resultat_b = self.terminer(self.lancer(autre_action), autre_action)
        finally:
            (self.sortie / "A_continuer").write_text("1")
        resultat_a = self.terminer(poste_a, 7)
        self.assertEqual(resultat_a["etat"], "validation")
        return resultat_b

    def test_journee_contre_demis_deux_postes_puis_reprise_sans_doublon(self):
        b = self.scenario(8)
        # Sans le verrou famille : B valide et persiste les deux demis.
        self.assertEqual(b, dict(etat="attente", saves=0, saisies=0))
        self.assertEqual(self.lignes("SELECT IDunite,quantite FROM consommations ORDER BY IDunite"), [(101, 1)])
        b = self.terminer(self.lancer(8), 8)
        self.assertEqual(b["etat"], "validation")
        self.assertEqual(b["saisies"], 0)
        self.assertEqual(self.lignes("SELECT IDunite,quantite FROM consommations ORDER BY IDunite"), [(101, 1)])
        self.assertEqual(self.lignes("SELECT nom FROM parametres WHERE categorie='%s'" % Marqueurs.CATEGORIE), [])

    def test_famille_distincte_progresse_pendant_la_grille_du_poste_a(self):
        b = self.scenario(9)
        self.assertEqual((b["etat"], b["saisies"]), ("validation", 1))
        self.assertEqual(self.lignes("SELECT IDindividu,IDunite,quantite FROM consommations ORDER BY IDindividu"),
                         [(100, 101, 1), (200, 102, 1)])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        travailleur(sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5] == "1")
    else:
        unittest.main()
