# -*- coding: utf-8 -*-
"""Recherche d'anomalies : même résultat, boucle wx disponible, aucune base réelle."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import _garde_reseau  # noqa: E402,F401
from Utils import UTILS_Depannage as module  # noqa: E402

REFERENCE = json.loads((ROOT / 'tests/fixtures/depannage_rc102.json').read_text(encoding='utf-8'))


class BaseFictive:
    instances = []
    delai = 0
    panne = False
    reseau = False

    def __init__(self, nomFichier='fictif', suffixe='DATA'):
        self.nomFichier = nomFichier
        self.isNetwork = self.reseau
        self.thread = threading.get_ident()
        self.fermee = False
        self.requetes = []
        type(self).instances.append(self)

    def GetNomFichierDefaut(self):
        # La résolution par défaut touche la fenêtre : elle doit précéder le worker.
        assert threading.current_thread() is threading.main_thread()
        return 'fictif'

    def ExecuterReq(self, requete):
        assert threading.get_ident() == self.thread
        assert requete.lstrip().upper().startswith(('SELECT ', 'SHOW ')), 'Écriture interdite'
        self.requetes.append(requete)
        if len(self.requetes) == 1:
            time.sleep(self.delai)
            if self.panne:
                raise RuntimeError('PANNE_FICTIVE')
        return 1

    def ResultatReq(self):
        assert threading.get_ident() == self.thread
        if len(self.requetes) == 1:
            return [(7, 2, 'Activité fictive', '2026-10-01', 99)]
        if self.requetes[-1].startswith('SHOW '):
            return [('version', '8.0.42')]
        return []

    def Close(self):
        assert threading.get_ident() == self.thread
        self.fermee = True


def resultats(recherche):
    return [(probleme, correction, [(type(a).__name__, a.kwds) for a in anomalies])
            for probleme, correction, anomalies in recherche.listeResultats]


class RechercheTests(unittest.TestCase):
    def setUp(self):
        BaseFictive.instances = []
        BaseFictive.delai = 0
        BaseFictive.panne = False
        BaseFictive.reseau = False
        self.patch = mock.patch.object(module.GestionDB, 'DB', BaseFictive)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_lectures_et_resultats_equivalents_a_rc102(self):
        ns = dict(module.__dict__)
        exec(REFERENCE['recherche'], ns)
        ancien = module.Depannage()
        courant = module.Depannage()
        with mock.patch.object(module.wx, 'BusyInfo'), mock.patch.object(module, 'EcritStatusbar'):
            ns['RechercheDonnees'](ancien)
        courant.listeResultats = []
        courant._RechercherDonnees('fictif')
        self.assertEqual(resultats(ancien), resultats(courant))
        self.assertEqual(ancien.GetNbreAnomalies(), 1)
        self.assertEqual(BaseFictive.instances[0].requetes, BaseFictive.instances[1].requetes)
        self.assertGreater(len(BaseFictive.instances[1].requetes), 18)
        self.assertTrue(all(db.fermee for db in BaseFictive.instances))

    def test_connexion_fermee_si_lecture_echoue(self):
        BaseFictive.panne = True
        recherche = module.Depannage()
        recherche.listeResultats = []
        with self.assertRaisesRegex(RuntimeError, 'PANNE_FICTIVE'):
            recherche._RechercherDonnees('fictif')
        self.assertTrue(BaseFictive.instances[0].fermee)

    def test_mysql8_ne_consulte_pas_wx_dans_la_recherche(self):
        BaseFictive.reseau = True
        recherche = module.Depannage()
        recherche.listeResultats = []
        with mock.patch.object(BaseFictive, 'GetNomFichierDefaut', side_effect=AssertionError('wx interdit')):
            recherche._RechercherDonnees('fictif')
        self.assertEqual(recherche.GetNbreAnomalies(), 2)

    def test_nettoyage_attente_et_statut_apres_exception(self):
        recherche = module.Depannage()
        with mock.patch.object(module.UTILS_Attente, 'BusyInfo'), \
             mock.patch.object(module.wx, 'GetApp', return_value=object()), \
             mock.patch.object(module.wx, 'IsMainThread', return_value=True), \
             mock.patch.object(module, 'EcritStatusbar') as statut, \
             mock.patch.object(module, '_ExecuterRechercheHorsUI', side_effect=RuntimeError('PANNE_FICTIVE')):
            with self.assertRaisesRegex(RuntimeError, 'PANNE_FICTIVE'):
                recherche.RechercheDonnees()
        self.assertEqual(statut.call_args.args, ('',))

    def test_aucun_texte_modifie_et_aucune_remaximisation(self):
        source = (ROOT / 'noethys/Utils/UTILS_Depannage.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        textes = [n.args[0].value for n in ast.walk(tree) if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Name) and n.func.id == '_' and n.args
                  and isinstance(n.args[0], ast.Constant)]
        self.assertEqual(textes, REFERENCE['traductions'])
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                self.assertNotIn(n.func.attr, ('Maximize', 'Restore', 'Iconize', 'SetSize', 'ShowFullScreen'))


def scenario(ancien=False, mode='maximise', panne=False):
    import ctypes
    import wx
    app = wx.App(False)
    frame = wx.Frame(None, title='Anomalies - FICTIF', size=(950, 740))
    frame.SetName('general')
    frame.userConfig = {'nomFichier': 'fictif'}
    app.SetTopWindow(frame)
    frame.Show()
    if mode == 'maximise':
        frame.Maximize(True)
    elif mode == 'plein_ecran':
        frame.ShowFullScreen(True)
    battements, etats, erreurs = [], [], []
    donnees = {}
    u32 = ctypes.windll.user32
    u32.GetWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    u32.GetWindow.restype = ctypes.c_void_p
    u32.GetParent.argtypes = [ctypes.c_void_p]
    u32.GetParent.restype = ctypes.c_void_p
    u32.IsZoomed.argtypes = [ctypes.c_void_p]
    u32.IsIconic.argtypes = [ctypes.c_void_p]
    timer = wx.Timer()

    def battement(event):
        battements.append(time.monotonic())
        etats.append((frame.IsMaximized(), frame.IsFullScreen(), bool(u32.IsZoomed(frame.GetHandle())),
                      bool(u32.IsIconic(frame.GetHandle())), tuple(frame.GetRect())))
    timer.Bind(wx.EVT_TIMER, battement)
    timer.Start(25)
    attente_module = module.wx if ancien else module.UTILS_Attente
    busy_initial = attente_module.BusyInfo
    attaches = []

    def fenetres_thread():
        handles = set()
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        callback = callback_type(lambda hwnd, arg: handles.add(hwnd) or True)
        u32.EnumThreadWindows(ctypes.windll.kernel32.GetCurrentThreadId(), callback, 0)
        return handles

    def attente(*args):
        assert wx.IsMainThread()
        avant = fenetres_thread()
        busy = busy_initial(*args)
        nouvelles = fenetres_thread() - avant
        attaches.extend(u32.GetParent(hwnd) == frame.GetHandle() or
                        u32.GetWindow(hwnd, 4) == frame.GetHandle() for hwnd in nouvelles)
        return busy

    def finir():
        timer.Stop()
        timer.Unbind(wx.EVT_TIMER)
        donnees.update(retard_max_ms=round(1000 * max((b-a for a, b in zip(battements, battements[1:])), default=0)),
                       battements=len(battements), geometrie_identique=all(e[-1] == initial[-1] for e in etats),
                       etat_identique=all(e[:-1] == initial[:-1] for e in etats), owner_ok=bool(attaches) and all(attaches),
                       worker=BaseFictive.instances[0].thread != threading.get_ident(),
                       connexion_fermee=BaseFictive.instances[0].fermee, erreurs=erreurs,
                       reactivation=frame.IsEnabled(), reseau=len(_garde_reseau.TENTATIVES))
        print('ANOMALIES_UI ' + json.dumps(donnees, ensure_ascii=True), flush=True)
        frame.Destroy()

    def lancer():
        nonlocal initial
        initial = (frame.IsMaximized(), frame.IsFullScreen(), bool(u32.IsZoomed(frame.GetHandle())),
                   bool(u32.IsIconic(frame.GetHandle())), tuple(frame.GetRect()))
        BaseFictive.instances = []
        BaseFictive.delai = 1.25
        BaseFictive.panne = panne
        recherche = module.Depannage(frame)
        try:
            with mock.patch.object(module.GestionDB, 'DB', BaseFictive), \
                 mock.patch.object(attente_module, 'BusyInfo', side_effect=attente):
                if ancien:
                    ns = dict(module.__dict__)
                    exec(REFERENCE['recherche'], ns)
                    ns['RechercheDonnees'](recherche)
                else:
                    recherche.RechercheDonnees()
        except RuntimeError as err:
            erreurs.append(str(err))
        donnees.update(resultats=resultats(recherche), requetes=BaseFictive.instances[0].requetes)
        wx.CallLater(125, finir)

    initial = None
    wx.CallLater(150, lancer)
    app.MainLoop()
    app.ProcessPendingEvents()
    import gc
    gc.collect()
    app.Destroy()


@unittest.skipUnless(sys.platform == 'win32' and os.environ.get('GITHUB_ACTIONS') == 'true',
                     'Fenêtres de recette réservées au runner Windows isolé')
class BoucleWindowsTests(unittest.TestCase):
    def mesurer(self, *arguments):
        p = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--scenario', *arguments],
                           cwd=ROOT / 'noethys', capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=20)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        ligne = next(l for l in p.stdout.splitlines() if l.startswith('ANOMALIES_UI '))
        m = json.loads(ligne.split(' ', 1)[1])
        self.assertTrue(m['geometrie_identique'] and m['etat_identique'], m)
        self.assertTrue(m['reactivation'], m)
        self.assertEqual(m['owner_ok'], '--ancien' not in arguments, m)
        self.assertEqual(m['reseau'], 0)
        print('ANOMALIES_MESURE ' + json.dumps({k: v for k, v in m.items() if k not in ('resultats', 'requetes')}), flush=True)
        return m

    def test_contre_epreuve_et_etats_fenetre(self):
        avant = self.mesurer('--ancien')
        self.assertGreater(avant['retard_max_ms'], 1000)
        self.assertFalse(avant['worker'])
        for mode in ('maximise', 'fenetre', 'plein_ecran'):
            apres = self.mesurer('--mode', mode)
            self.assertLess(apres['retard_max_ms'], 500, apres)
            self.assertTrue(apres['worker'] and apres['connexion_fermee'], apres)
            self.assertEqual(avant['resultats'], apres['resultats'])
            self.assertEqual(avant['requetes'], apres['requetes'])
            self.assertGreater(apres['battements'], avant['battements'])

    def test_erreur_worker_restituee_et_fenetre_reactivee(self):
        m = self.mesurer('--panne')
        self.assertEqual(m['erreurs'], ['PANNE_FICTIVE'])
        self.assertTrue(m['worker'] and m['connexion_fermee'])
        self.assertLess(m['retard_max_ms'], 500)


if __name__ == '__main__':
    if '--scenario' in sys.argv:
        mode = sys.argv[sys.argv.index('--mode') + 1] if '--mode' in sys.argv else 'maximise'
        scenario('--ancien' in sys.argv, mode, '--panne' in sys.argv)
    else:
        unittest.main()
