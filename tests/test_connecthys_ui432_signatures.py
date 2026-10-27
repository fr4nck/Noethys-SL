# -*- coding: utf-8 -*-
"""#432 : signatures du diagnostic UI pour quatre causes de gel injectees.

Chaque cas tourne dans un sous-processus avec une vraie boucle wx, une frame
jamais affichee et la veille reelle de UTILS_Diagnostic_ui :
- wx : le thread wx dort (le GIL reste disponible) ;
- gil : un thread de synchro execute un appel C qui conserve le GIL ;
- sql : le thread wx attend dans GestionDB.ExecuterReq un verrou tenu par la
  synchro (attente de serveur simulee, aucune base) ;
- suspension : le processus est suspendu par le systeme (retard de
  planification Windows simule), sans aucun thread de synchro.
Aucune base, aucun reseau, aucun email.
"""
import os
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DUREE_S = 3.0


def scenario(cas):
    sys.path.insert(0, str(ROOT / "noethys"))
    import ctypes
    import threading
    import wx
    from Utils import UTILS_Diagnostic_ui as Diag
    nom_synchro = Diag.THREADS_SYNCHRO[0]
    app = wx.App(False)
    frame = wx.Frame(None, title="UI432 signatures - fictif")  # jamais affichee
    frame._diag_ui = Diag.Diagnostic(frame, actif=True, role="principale")

    def bloquer():
        print("UI432_PRET", flush=True)
        if cas == "wx":
            time.sleep(DUREE_S)
        elif cas == "gil":
            # PyDLL ne relache pas le GIL : modele d'un appel C monopolisant.
            sommeil = ctypes.PyDLL("kernel32").Sleep

            def synchro():
                sommeil(int(DUREE_S * 1000))
                time.sleep(1.0)  # rester visible de la veille a son reveil

            threading.Thread(target=synchro, name=nom_synchro, daemon=True).start()
        elif cas == "sql":
            import GestionDB
            verrou = threading.Lock()
            verrou.acquire()

            def liberer():
                time.sleep(DUREE_S)
                verrou.release()

            class Curseur:
                def execute(self, req):
                    with verrou:
                        pass

            threading.Thread(target=liberer, name=nom_synchro, daemon=True).start()
            db = GestionDB.DB.__new__(GestionDB.DB)
            db.echec, db.isNetwork, db.cursor, db.IDconnexion = 0, False, Curseur(), "ui432"
            GestionDB.DICT_CONNEXIONS["ui432"] = []
            assert db.ExecuterReq("SELECT 1;") == 1
        # suspension : rien a faire, le processus parent suspend l'enfant.

    def finir():
        print("UI432_FIN", flush=True)
        frame.Destroy()

    wx.CallLater(1000, bloquer)
    wx.CallLater(int(DUREE_S * 1000) + 3500, finir)
    app.MainLoop()
    sys.stdout.flush()
    # La sortie de ce banc n'est pas l'objet de la mesure (voir la campagne
    # tools/ui432_campagne_sortie.py) : eviter la finalisation wx.
    os._exit(0)


def executer(cas):
    p = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--cas", cas],
                         cwd=ROOT / "noethys", stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace",
                         env={**os.environ, "NOETHYS_SL_UI_DIAG": "1"})
    lignes = []
    try:
        for ligne in p.stdout:
            lignes.append(ligne.rstrip())
            if cas == "suspension" and ligne.startswith("UI432_PRET"):
                import ctypes
                ntdll = ctypes.WinDLL("ntdll")
                ntdll.NtSuspendProcess(ctypes.c_void_p(int(p._handle)))
                try:
                    time.sleep(DUREE_S)
                finally:
                    ntdll.NtResumeProcess(ctypes.c_void_p(int(p._handle)))
        p.wait(timeout=30)
    finally:
        if p.poll() is None:
            p.kill()
    evenements = []
    for ligne in lignes:
        if ligne.startswith("NOETHYS_UI_DIAG "):
            evenements.append(dict(re.findall(r"(\w+)=(\S+)", ligne)))
    return p.returncode, lignes, evenements


@unittest.skipUnless(sys.platform == "win32", "Boucle native Windows requise")
class SignaturesTests(unittest.TestCase):
    def mesurer(self, cas):
        code, lignes, evenements = executer(cas)
        texte = "\n".join(lignes)
        self.assertEqual(code, 0, texte)
        self.assertIn("UI432_FIN", texte)
        self.assertNotIn("Users", " ".join(e.get("point", "") + e.get("point_synchro", "")
                                           for e in evenements))
        par_type = {}
        for e in evenements:
            par_type.setdefault(e["evenement"], []).append(e)
        retards = [int(e["retard_ms"]) for e in par_type.get("retard_boucle", [])]
        veilles = [int(e["veille_retard_ms"]) for e in par_type.get("veille_retardee", [])]
        blocages = par_type.get("blocage_thread", [])
        print("UI432_SIGNATURE %s retard_max=%s veille_max=%s blocages=%s" % (
            cas, max(retards, default=0), max(veilles, default=0),
            [(b.get("point"), b.get("point_synchro"), b.get("veille_retard_ms")) for b in blocages]),
            flush=True)
        self.assertGreater(max(retards, default=0), 2000, texte)
        return veilles, blocages

    def test_blocage_du_thread_wx(self):
        veilles, blocages = self.mesurer("wx")
        self.assertEqual(veilles, [])
        self.assertTrue(blocages)
        self.assertTrue(all(b["point_synchro"] == "aucune" and int(b["veille_retard_ms"]) < 1000
                            for b in blocages))

    def test_monopolisation_du_gil_par_la_synchro(self):
        veilles, blocages = self.mesurer("gil")
        self.assertTrue(veilles and max(veilles) > 2000)
        self.assertTrue(any(b["point_synchro"] != "aucune" for b in blocages))

    def test_attente_sql_du_thread_wx(self):
        veilles, blocages = self.mesurer("sql")
        self.assertEqual(veilles, [])
        self.assertTrue(any(b["point"].startswith("GestionDB.py:ExecuterReq:") for b in blocages))
        self.assertTrue(all(b["point_synchro"] != "aucune" for b in blocages))

    def test_suspension_du_processus(self):
        veilles, blocages = self.mesurer("suspension")
        self.assertTrue(veilles and max(veilles) > 2000)
        self.assertTrue(all(b["point_synchro"] == "aucune" for b in blocages))


if __name__ == "__main__":
    if "--cas" in sys.argv:
        scenario(sys.argv[sys.argv.index("--cas") + 1])
    else:
        unittest.main()
