# -*- coding: utf-8 -*-
"""Complétude, confidentialité et conservation des sauvegardes précédentes."""
import base64
import ast
import datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile
import sys
import types
import unittest
from unittest import mock

from tests._mysql_backup_test_support import moteur
from tests.test_noethys_sl_backup_missing_file import _load_module
from tests.test_noethys_sl_backup_dump_watchdog import isoler, essai
from tests.test_noethys_sl_mysql_returncode import _charger_manifeste


class BackupCompletTests(unittest.TestCase):
    def test_verification_longue_rafraichit_la_progression(self):
        import threading
        with tempfile.TemporaryDirectory() as rep:
            fn = isoler(Path(rep), lambda *a, **k: self.fail("export simulé"), iter((0.0,)))
            env = fn.__globals__
            env["UTILS_MySQL_backup"].ExporterSQL = lambda *a, **k: {"erreur": None}
            terminee = threading.Event()
            progression = mock.Mock()
            def analyser(*args, **kwargs):
                progression.reset_mock()
                if not terminee.wait(2):
                    raise AssertionError("aucun rafraîchissement pendant l'analyse")
                return {}, None
            def update(*args):
                progression(*args)
                if progression.call_count >= 2:
                    terminee.set()
            env["UTILS_SQL_Integrite"].AnalyserDumpSQL = analyser
            env["wx"].ProgressDialog = lambda *a, **k: types.SimpleNamespace(
                Update=update, Destroy=lambda: None)
            self.assertFalse(essai(fn))  # Aucun fichier fictif à insérer ensuite.
            self.assertTrue(terminee.is_set())

    def test_echec_ou_annulation_ne_purge_pas_les_sauvegardes_precedentes(self):
        source = Path(__file__).resolve().parents[1] / "noethys/Utils/UTILS_Sauvegarde_auto.py"
        arbre = ast.parse(source.read_text(encoding="utf-8"))
        classe = next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == "Sauvegarde_auto")
        fonction = next(n for n in classe.body if isinstance(n, ast.FunctionDef) and n.name == "Start")
        env = dict(datetime=datetime, os=os, glob=types.SimpleNamespace(glob=mock.Mock()),
                   wx=types.SimpleNamespace(ID_CANCEL=5101),
                   ChoisirRepertoirePoste=lambda parent, procedure: (procedure["sauvegarde_repertoire"], None))
        exec(compile(ast.Module(body=[fonction], type_ignores=[]), str(source), "exec"), env)
        dialogue = types.SimpleNamespace(ShowModal=lambda: None, GetResultat=lambda: False, Destroy=lambda: None)
        package = types.ModuleType("Dlg")
        package.DLG_Sauvegarde = types.SimpleNamespace(Dialog=lambda *a, **k: dialogue)
        with tempfile.TemporaryDirectory() as rep, mock.patch.dict(sys.modules, {"Dlg": package}):
            for valide in (False, True):
                procedure = dict(sauvegarde_nom="Noethys", option_demander="0", option_afficher_interface="1",
                                 option_suppression="0", sauvegarde_repertoire=rep)
                objet = types.SimpleNamespace(listeSauvegardes=[procedure],
                                               VerificationConditions=lambda _: valide, parent=None)
                env["Start"](objet)
            env["glob"].glob.assert_not_called()

    def test_repertoire_absent_refuse_avant_creation_du_zip(self):
        with tempfile.TemporaryDirectory() as rep:
            rep = Path(rep)
            module = _load_module(rep, rep)
            self.assertFalse(module.Sauvegarde(listeFichiersLocaux=["fictif.dat"],
                             nom="essai", repertoire=str(rep / "autre-poste")))
            self.assertFalse((rep / "essai.nod").exists())

    def test_code_zero_sans_fin_dump_refuse_avant_manifeste(self):
        with tempfile.TemporaryDirectory() as rep:
            rep = Path(rep)
            class Processus:
                returncode = 0
                def poll(self):
                    return 0
                def wait(self, timeout=None):
                    return 0
            def lancer(args, **kwargs):
                kwargs["stdout"].write(b"CREATE TABLE t (id INT);\n")
                return Processus()
            fn = isoler(rep, lancer, iter((0.0,)))
            vrai = _charger_manifeste()
            fn.__globals__["UTILS_SQL_Integrite"] = vrai
            with mock.patch.object(vrai, "AjouterManifesteIntegriteSQL", side_effect=AssertionError("interdit")):
                self.assertFalse(essai(fn))
            self.assertFalse((rep / "testdump.nod").exists())
            self.assertFalse(any(rep.glob("savetemp*")))

    def test_client_introuvable_nettoie_zip_et_dossier_temporaire(self):
        with tempfile.TemporaryDirectory() as rep:
            rep = Path(rep)
            fn = isoler(rep, lambda *a, **k: self.fail("ne doit pas lancer"), iter((0.0,)))
            fn.__globals__["GetRepertoireMySQL"] = lambda _: None
            self.assertFalse(essai(fn))
            self.assertFalse((rep / "testdump.nod").exists())
            self.assertFalse(any(rep.glob("savetemp*")))

    def test_options_ne_peuvent_plus_produire_un_faux_succes_partiel(self):
        module = moteur()
        for option in ("--force", "--no-data", "--ignore-table=x.y", "--where=1=0",
                       "--result-file=ailleurs.sql", "--skip-comments", "--skip-opt",
                       "--lock-all-tables", "--password=SECRET", "--host=ailleurs", "--triggers=0"):
            with self.subTest(option=option), self.assertRaises(ValueError) as erreur:
                module.OptionsDump(option)
            self.assertNotIn("SECRET", str(erreur.exception))
        options = module.OptionsDump('--set-gtid-purged=OFF --ssl-ca="C:/un dossier/ca.pem"')
        self.assertIn("--ssl-ca=C:/un dossier/ca.pem", options)
        for option in ("--quick", "--hex-blob", "--max-allowed-packet=1G",
                       "--single-transaction", "--skip-lock-tables", "--dump-date"):
            self.assertIn(option, options)

    def test_secret_encode_et_sql_masques(self):
        secret = "p#asse XYZ"
        encode = "#64#" + base64.b64encode(secret.encode()).decode()
        resultat = moteur().NettoyerDiagnostic(
            "erreur %s %s INSERT INTO documents VALUES ('confidentiel')" % (secret, encode),
            (encode,))
        self.assertNotIn(secret, resultat)
        self.assertNotIn(encode, resultat)
        self.assertNotIn("confidentiel", resultat)

    def test_client_absent_et_option_invalide_rendent_un_diagnostic(self):
        with tempfile.TemporaryDirectory() as rep:
            chemin = Path(rep) / "dump.sql"
            module = moteur()
            resultat = module.ExporterSQL("client-absent-437", "absent.cnf", chemin, "fictif")
            self.assertIn("Impossible", resultat["erreur"])
            with mock.patch.object(module.subprocess, "Popen", side_effect=AssertionError("interdit")):
                resultat = module.ExporterSQL("absent", "absent", chemin, "fictif", options="--force")
            self.assertIn("Option", resultat["erreur"])

    def test_erreur_finale_stderr_et_code_conserves_sans_sql(self):
        module = moteur()
        class Processus:
            returncode = 3
            def wait(self, timeout=None):
                return 3
            def poll(self):
                return 3
        def lancer(args, **kwargs):
            kwargs["stderr"].write(b"x" * 9000 + b"\nERROR 2013 documents\n")
            return Processus()
        with tempfile.TemporaryDirectory() as rep, mock.patch.object(module.subprocess, "Popen", lancer):
            resultat = module.ExporterSQL("fictif", "fictif", Path(rep) / "dump.sql", "fictif")
        self.assertEqual(resultat["code_retour"], 3)
        self.assertIn("ERROR 2013 documents", resultat["diagnostic"])
        json.dumps(resultat)

    def test_copie_interrompue_conserve_ancienne_sauvegarde(self):
        with tempfile.TemporaryDirectory() as rep:
            rep = Path(rep)
            data, temp, sortie = (rep / nom for nom in ("data", "temp", "sortie"))
            for chemin in (data, temp, sortie):
                chemin.mkdir()
            (data / "fictif_DATA.dat").write_bytes(b"fictif")
            destination = sortie / "save.nod"
            destination.write_bytes(b"ANCIENNE SAUVEGARDE")
            module = _load_module(data, temp)
            wx = module.Sauvegarde.__globals__["wx"]
            wx.YES_NO = wx.NO_DEFAULT = wx.ICON_EXCLAMATION = 0
            def interrompre(source, cible):
                Path(cible).write_bytes(b"COPIE PARTIELLE")
                raise OSError("disque plein fictif")
            with mock.patch.object(module.shutil, "copy2", interrompre):
                self.assertFalse(module.Sauvegarde(
                    listeFichiersLocaux=["fictif_DATA.dat"], nom="save", repertoire=str(sortie)))
            self.assertEqual(destination.read_bytes(), b"ANCIENNE SAUVEGARDE")
            self.assertEqual(list(sortie.iterdir()), [destination])

    def test_vrai_enfant_bloque_est_arrete_et_attendu(self):
        # Vrai processus Python local, sans MySQL ni réseau.
        import sys
        module = moteur()
        popen = subprocess.Popen
        enfants = []
        def lancer(args, **kwargs):
            enfant = popen([sys.executable, "-c", "import time; time.sleep(90)"], **kwargs)
            enfants.append(enfant)
            return enfant
        with tempfile.TemporaryDirectory() as rep, mock.patch.object(module.subprocess, "Popen", lancer):
            resultat = module.ExporterSQL("fictif", "fictif", Path(rep) / "dump.sql", "fictif", inactivite=0.01)
        self.assertTrue(resultat["erreur"])
        self.assertIsNotNone(enfants[0].poll())


if __name__ == "__main__":
    unittest.main()
