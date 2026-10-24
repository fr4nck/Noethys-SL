# -*- coding: utf-8 -*-
"""Diagnostic de démarrage : inactif par défaut, et capable de situer un
blocage, une exception invisible (exécutable fenêtré) ou un problème de
profil. Chaque cas est exécuté dans un sous-processus Python réel."""
import ast
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
NOETHYS = RACINE / "noethys"


def lancer(code, journal=None, delai=None):
    env = dict(os.environ)
    env.pop("NOETHYS_DIAGNOSTIC_DEMARRAGE", None)
    if journal is not None:
        env["NOETHYS_DIAGNOSTIC_DEMARRAGE"] = journal
    if delai is not None:
        env["NOETHYS_DIAGNOSTIC_DELAI_PILES"] = str(delai)
    env["PYTHONPATH"] = str(NOETHYS)
    return subprocess.run([sys.executable, "-c", textwrap.dedent(code)], env=env, capture_output=True,
                          text=True, timeout=60)


PREAMBULE = """
from Utils import UTILS_Diagnostic_demarrage as D
D.ActiverDepuisEnvironnement()
"""


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory(prefix="diag-demarrage-")
        self.addCleanup(self.dossier.cleanup)
        self.journal = os.path.join(self.dossier.name, "demarrage.log")

    def lire(self):
        with open(self.journal, encoding="utf-8") as fichier:
            return fichier.read()

    def test_inactif_par_defaut_aucun_fichier_aucune_sonde(self):
        resultat = lancer(PREAMBULE + """
import sys
assert D.Actif() is False
D.Etape("x")
assert not any(type(f).__name__ == "_JournalImports" for f in sys.meta_path)
assert sys.excepthook is sys.__excepthook__
print("ok")
""")
        self.assertEqual((resultat.returncode, resultat.stdout.strip()), (0, "ok"), resultat.stderr)
        self.assertEqual(os.listdir(self.dossier.name), [])

    def test_etapes_imports_et_fin_de_processus(self):
        resultat = lancer(PREAMBULE + """
import json, decimal
D.Etape("main_debut", rep="X")
""", journal=self.journal)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        texte = self.lire()
        for attendu in (" DEBUT pid=", " IMPORT decimal", " ETAPE main_debut rep='X'", " FIN_PROCESSUS"):
            self.assertIn(attendu, texte)
        self.assertLess(texte.index("IMPORT decimal"), texte.index("ETAPE main_debut"))

    def test_exception_d_import_invisible_consignee_avec_le_module_fautif(self):
        resultat = lancer(PREAMBULE + """
import json
import module_absent_du_paquet
""", journal=self.journal)
        self.assertNotEqual(resultat.returncode, 0)
        texte = self.lire()
        self.assertIn(" EXCEPTION NON INTERCEPTEE", texte)
        self.assertIn("ModuleNotFoundError: No module named 'module_absent_du_paquet'", texte)
        self.assertIn(" IMPORT module_absent_du_paquet", texte)

    def test_origine_du_module_masque_consignee(self):
        resultat = lancer(PREAMBULE + """
import os, sys, tempfile
racine = tempfile.mkdtemp()
os.mkdir(os.path.join(racine, "zoneinfo"))
open(os.path.join(racine, "zoneinfo", "__init__.py"), "w").close()
sys.path.insert(0, racine)
import zoneinfo
zoneinfo.reset_tzpath
""", journal=self.journal)
        self.assertNotEqual(resultat.returncode, 0)
        texte = self.lire()
        self.assertIn("AttributeError: module 'zoneinfo' has no attribute 'reset_tzpath'", texte)
        self.assertRegex(texte, r"MODULE zoneinfo origine='[^']*zoneinfo[\\/]+__init__\.py'")

    def test_blocage_situe_par_la_pile_periodique(self):
        resultat = lancer(PREAMBULE + """
import time
def bloque_ici_pendant_le_demarrage():
    time.sleep(2.6)
bloque_ici_pendant_le_demarrage()
""", journal=self.journal, delai=1)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertIn("bloque_ici_pendant_le_demarrage", self.lire())

    def test_exception_de_thread_consignee(self):
        resultat = lancer(PREAMBULE + """
import threading
def tache():
    raise RuntimeError("erreur dans un thread de demarrage")
t = threading.Thread(target=tache, name="Demarrage-Test")
t.start(); t.join()
""", journal=self.journal)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        texte = self.lire()
        self.assertIn(" EXCEPTION THREAD Demarrage-Test", texte)
        self.assertIn("RuntimeError: erreur dans un thread de demarrage", texte)

    def test_profil_portable_et_profil_systeme_consignes(self):
        resultat = lancer(PREAMBULE + """
import os, tempfile, types
base = tempfile.mkdtemp()
os.mkdir(os.path.join(base, "Portable"))
chemins = types.SimpleNamespace(REP_COURANT=base, GetMainPath=lambda f="": os.path.join(base, f))
fichiers = types.SimpleNamespace(GetRepUtilisateur=lambda f="": os.path.join(base, "Portable", f))
D.Profil(chemins, fichiers)
""", journal=self.journal)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        texte = self.lire()
        self.assertIn(" ETAPE profil ", texte)
        self.assertIn("portable_present=True", texte)
        self.assertIn("appdirs_user_config=", texte)

    def test_journal_impossible_n_empeche_pas_le_demarrage(self):
        resultat = lancer(PREAMBULE + """
assert D.Actif() is False
print("demarrage poursuivi")
""", journal=os.path.join(self.dossier.name, "absent", "x", "demarrage.log"))
        self.assertEqual((resultat.returncode, resultat.stdout.strip()), (0, "demarrage poursuivi"), resultat.stderr)


class RaccordementNoethysTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (NOETHYS / "Noethys.py").read_text(encoding="utf-8")
        cls.arbre = ast.parse(cls.source)

    def test_active_avant_tout_module_noethys(self):
        corps = [n for n in self.arbre.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
        textes = [ast.unparse(n) for n in corps[:4]]
        self.assertEqual(textes, ["import os, sys", "from Utils import UTILS_Diagnostic_demarrage",
                                  "UTILS_Diagnostic_demarrage.ActiverDepuisEnvironnement()", "import Chemins"])
        self.assertNotIn("UTILS_Diagnostic_demarrage.Activer(", self.source)
        self.assertEqual(ast.unparse(corps[4]), "UTILS_Diagnostic_demarrage.Etape('chemins', sys_path=sys.path[:20])")

    def test_etapes_dans_l_ordre_du_demarrage(self):
        def ordre(fonction, etapes):
            noeud = next(n for n in ast.walk(self.arbre) if isinstance(n, ast.FunctionDef) and n.name == fonction)
            texte = ast.unparse(noeud)
            positions = [texte.index('Etape(%r' % etape) for etape in etapes]
            self.assertEqual(positions, sorted(positions), fonction)
            return texte
        main = ordre("main", ["main_debut", "repertoires_utilisateur", "app_creation", "mainloop", "mainloop_fin"])
        self.assertLess(main.index("Profil(Chemins, UTILS_Fichiers)"), main.index("os.makedirs"))
        self.assertLess(main.index("Etape('repertoires_utilisateur'"), main.index("Customize()"))
        ordre("OnInit", ["oninit_debut", "mainframe_creation", "mainframe_initialisee", "oninit_fin"])
        self.assertIn("Etape('imports_termines'", ast.unparse(self.arbre))


if __name__ == "__main__":
    unittest.main()
