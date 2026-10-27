# -*- coding: utf-8 -*-
"""#432 : signatures du diagnostic UI pour quatre causes de gel injectees.

Chaque cas tourne dans un sous-processus avec une vraie boucle wx, une frame
jamais affichee et la veille reelle de UTILS_Diagnostic_ui :
- wx : le thread wx dort (le GIL reste disponible) ;
- gil : un thread de synchro execute un appel C qui conserve le GIL ;
- sql : le thread wx attend dans GestionDB.ExecuterReq un verrou tenu par la
  synchro (attente de serveur simulee, aucune base) ;
- suspension : le processus est suspendu par le systeme (retard de
  planification Windows simule), sans aucun thread de synchro ;
- fantome : frame visible gelee plus de 5 s ; le processus parent reduit la
  fenetre fantome Windows (ou, a defaut, la fenetre elle-meme) pendant le gel,
  comme un clic sur la barre des taches, pour observer l'etat apres le gel.
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
DUREE_FANTOME_S = 9.0


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
    duree = DUREE_FANTOME_S if cas == "fantome" else DUREE_S
    if cas == "fantome":
        frame.Show()

    def bloquer():
        print("UI432_PRET hwnd=%d" % frame.GetHandle(), flush=True)
        if cas in ("wx", "fantome"):
            time.sleep(duree)
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
    wx.CallLater(int(duree * 1000) + 3500, finir)
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
            if cas == "fantome" and ligne.startswith("UI432_PRET"):
                lignes.append(reduire_pendant_le_gel(int(ligne.split("hwnd=")[1])))
        p.wait(timeout=30)
    finally:
        if p.poll() is None:
            p.kill()
        p.stdout.close()
    evenements = []
    for ligne in lignes:
        if ligne.startswith("NOETHYS_UI_DIAG "):
            evenements.append(dict(re.findall(r"(\w+)=(\S+)", ligne)))
    return p.returncode, lignes, evenements


def fenetres_fantomes():
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    trouvees = []
    rappel_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def rappel(hwnd, _):
        classe = ctypes.create_unicode_buffer(32)
        user32.GetClassNameW(hwnd, classe, 32)
        if classe.value == "Ghost" and user32.IsWindowVisible(hwnd):
            trouvees.append(hwnd)
        return True

    user32.EnumWindows(rappel_type(rappel), 0)
    return trouvees


def reduire_pendant_le_gel(hwnd):
    """Agit comme Windows ou l'utilisateur sur une fenetre qui ne repond pas."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    user32.IsHungAppWindow.argtypes = [wintypes.HWND]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
    fin = time.monotonic() + DUREE_FANTOME_S - 1.5
    bloquee = fantomes = []
    while time.monotonic() < fin:
        time.sleep(0.25)
        bloquee = bool(user32.IsHungAppWindow(hwnd))
        fantomes = fenetres_fantomes()
        if bloquee and (fantomes or time.monotonic() > fin - 1.0):
            break
    if fantomes:
        action = "fantome"
        user32.PostMessageW(fantomes[0], 0x0112, 0xF020, 0)  # WM_SYSCOMMAND, SC_MINIMIZE
    else:
        action = "directe"
        user32.ShowWindowAsync(hwnd, 6)  # SW_MINIMIZE
    return "UI432_FANTOME action=%s ne_repond_pas=%s fantomes=%d" % (action, bloquee, len(fantomes))


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

    def test_reduction_pendant_un_gel_iconise_la_vraie_fenetre(self):
        code, lignes, evenements = executer("fantome")
        texte = "\n".join(lignes)
        self.assertEqual(code, 0, texte)
        action = next(l for l in lignes if l.startswith("UI432_FANTOME"))
        print(action, flush=True)
        blocages = [e for e in evenements if e["evenement"] == "blocage_thread"]
        print("UI432_SIGNATURE fantome blocages=%s" % [
            (b.get("duree_ms"), b.get("ne_repond_pas"), b.get("fantome")) for b in blocages], flush=True)
        self.assertIn("ne_repond_pas=True", action, texte)
        self.assertTrue(any(b.get("ne_repond_pas") == "True" for b in blocages), texte)
        etats = [e for e in evenements if e["evenement"] == "etat"]
        self.assertTrue(any(e.get("win32_iconise") == "True" for e in etats), texte)


if __name__ == "__main__":
    if "--cas" in sys.argv:
        scenario(sys.argv[sys.argv.index("--cas") + 1])
    else:
        unittest.main()
