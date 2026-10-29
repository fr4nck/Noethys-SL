# -*- coding: utf-8 -*-
"""Attentes communes : parent natif, focus, rendu et destruction sans données."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import _garde_reseau  # noqa: E402,F401
from Utils import UTILS_Attente as module  # noqa: E402


class AttenteTests(unittest.TestCase):
    def test_auto_deconnexion_ne_reentre_pas_pendant_une_attente(self):
        source = ROOT / 'noethys/Noethys.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        classe = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MainFrame')
        methode = next(n for n in classe.body if isinstance(n, ast.FunctionDef) and n.name == 'Autodeconnect')
        ns = {'wx': SimpleNamespace(GetMousePosition=mock.Mock(side_effect=AssertionError('Attente en cours')))}
        exec(compile(ast.Module(body=[methode], type_ignores=[]), str(source), 'exec'), ns)
        self.assertIs(ns['Autodeconnect'](SimpleNamespace(IsEnabled=lambda: False)), False)

    def test_parent_masque_remonte_au_parent_visible(self):
        visible = SimpleNamespace(IsShownOnScreen=lambda: True)
        masque = SimpleNamespace(IsShownOnScreen=lambda: False, GetParent=lambda: visible)
        with mock.patch.object(module.wx, 'GetTopLevelParent', side_effect=lambda w: w):
            self.assertIs(module._ParentVisible(masque), visible)

    def test_sans_parent_choisit_fenetre_active(self):
        visible = SimpleNamespace(IsShownOnScreen=lambda: True)
        with mock.patch.object(module.wx, 'GetActiveWindow', return_value=visible), \
             mock.patch.object(module.wx, 'GetTopLevelParent', side_effect=lambda w: w):
            self.assertIs(module._ParentVisible(None), visible)

    def test_travailleur_ne_cree_pas_de_widget_et_attente_courte_annulee(self):
        rappels = []
        with mock.patch.object(module.wx, 'IsMainThread', return_value=False), \
             mock.patch.object(module.wx, 'CallAfter', side_effect=lambda f, *a: rappels.append((f, a))), \
             mock.patch.object(module.wx, 'Frame', side_effect=AssertionError('Widget dans un worker')):
            attente = module.BusyInfo('Texte fictif')
            attente.Destroy()
        for f, a in rappels:
            f(*a)
        self.assertIsNone(attente._fenetre)

    def test_tous_les_appels_runtime_passent_par_l_attente_commune(self):
        appels = []
        for p in (ROOT / 'noethys').rglob('*.py'):
            if 'Outils' in p.parts:
                continue
            tree = ast.parse(p.read_text(encoding='utf-8-sig'))
            for n in ast.walk(tree):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'BusyInfo':
                    self.assertFalse(isinstance(n.func.value, ast.Name) and n.func.value.id == 'wx', str(p))
                    appels.append(p)
        self.assertGreaterEqual(len(appels), 86)


def scenario():
    import base64
    import ctypes
    from ctypes import wintypes
    import io
    import wx
    app = wx.App(False)
    frame = wx.Frame(None, title='Attentes - FICTIF', size=(950, 740))
    frame.Show()
    frame.Maximize(True)
    app.SetTopWindow(frame)
    u32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    u32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    u32.GetWindow.restype = wintypes.HWND
    u32.GetActiveWindow.restype = wintypes.HWND
    u32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    u32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    u32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    observations = []
    erreurs = []
    alsh = {}

    def handles():
        valeurs = set()
        cb = callback_type(lambda hwnd, arg: valeurs.add(hwnd) or True)
        u32.EnumThreadWindows(ctypes.windll.kernel32.GetCurrentThreadId(), cb, 0)
        return valeurs

    def lancer():
        reference = (frame.IsMaximized(), frame.IsIconized(), tuple(frame.GetRect()))
        texte = 'Recherche des données... A & B'
        try:
            for ancien in (True, False):
                avant = handles()
                actif = u32.GetActiveWindow()
                info = wx.BusyInfo(texte, frame) if ancien else module.BusyInfo(texte, frame)
                nouveaux = handles() - avant
                assert len(nouveaux) == 1, nouveaux
                hwnd = nouveaux.pop()
                rect = wintypes.RECT()
                u32.GetClientRect(hwnd, ctypes.byref(rect))
                observations.append(dict(ancien=ancien, owner=u32.GetWindow(hwnd, 4) == frame.GetHandle(),
                    topmost=bool(u32.GetWindowLongW(hwnd, -20) & 8),
                    focus_inchange=u32.GetActiveWindow() == actif,
                    taille=[rect.right, rect.bottom], etat_inchange=reference ==
                        (frame.IsMaximized(), frame.IsIconized(), tuple(frame.GetRect()))))
                if not ancien:
                    assert info._texte.GetLabelText() == texte
                bitmap = wx.Bitmap(rect.right, rect.bottom)
                dc = wx.MemoryDC(bitmap)
                if u32.PrintWindow(hwnd, dc.GetHDC(), 1):
                    dc.SelectObject(wx.NullBitmap)
                    sortie = io.BytesIO()
                    capture = bitmap.ConvertToImage()
                    data = bytes(capture.GetData())
                    observations[-1]['pixels_texte'] = sum(max(r, g, b) < 120
                        for r, g, b in zip(data[0::3], data[1::3], data[2::3]))
                    if not ancien:
                        observations[-1]['rectangle_texte'] = list(info._texte.GetRect())
                    capture.SaveFile(sortie, wx.BITMAP_TYPE_PNG)
                    print('ATTENTE_IMAGE ' + ('avant ' if ancien else 'apres ') + base64.b64encode(sortie.getvalue()).decode('ascii'), flush=True)
                else:
                    dc.SelectObject(wx.NullBitmap)
                del dc, bitmap
                if ancien:
                    del info
                else:
                    info.Destroy()
                    del info
                app.ProcessPendingEvents()
            from Dlg import DLG_Frequentation_collectivites as ecran
            import GestionDB
            import threading
            import time
            connexions = []
            class DBFictive:
                @staticmethod
                def GetNomFichierDefaut(parent):
                    assert wx.IsMainThread()
                    return 'alsh-fictif'
                def __init__(self, **kw):
                    assert not wx.IsMainThread()
                    self.thread = threading.get_ident()
                    self.fermee = False
                    connexions.append(self)
                def Close(self):
                    assert threading.get_ident() == self.thread
                    self.fermee = True
            def lecture(annee, db=None):
                assert annee == 2026 and not wx.IsMainThread()
                assert db is connexions[-1]
                time.sleep(1.1)
                return []
            with mock.patch.object(ecran.Dialog, '_message') as message:
                dlg = ecran.Dialog(frame)
                dlg.dossier = ecran.modele('Bais', 2026, '2026-10-29')
                dlg.Rafraichir()
                ticks = []
                timer = wx.Timer()
                timer.Bind(wx.EVT_TIMER, lambda event: ticks.append(time.monotonic()))
                def importer():
                    message.reset_mock()
                    avant = (frame.IsMaximized(), frame.IsIconized(), tuple(frame.GetRect()))
                    try:
                        with mock.patch.object(GestionDB, 'DB', DBFictive), \
                             mock.patch.object(ecran, 'lister_unites', side_effect=lecture):
                            timer.Start(25)
                            dlg.OnImporterNoethys(None)
                        alsh.update(connexion_fermee=bool(connexions) and connexions[-1].fermee,
                            retard_ms=round(1000 * max((b-a for a,b in zip(ticks,ticks[1:])), default=0)),
                            battements=len(ticks), retour_attendu=message.call_args.args[0].startswith('Aucune consommation'),
                            etat_inchange=avant == (frame.IsMaximized(), frame.IsIconized(), tuple(frame.GetRect())))
                    except BaseException as erreur:
                        erreurs.append(type(erreur).__name__ + ': ' + str(erreur))
                    finally:
                        timer.Stop()
                        timer.Unbind(wx.EVT_TIMER)
                        dlg.EndModal(wx.ID_CANCEL)
                wx.CallLater(200, importer)
                dlg.ShowModal()
                dlg.Destroy()
        except BaseException as erreur:
            erreurs.append(type(erreur).__name__ + ': ' + str(erreur))
        print('ATTENTES_UI ' + json.dumps(dict(observations=observations, erreurs=erreurs, alsh=alsh)), flush=True)
        frame.Destroy()

    wx.CallLater(250, lancer)
    app.MainLoop()
    app.ProcessPendingEvents()
    import gc
    gc.collect()
    app.Destroy()


@unittest.skipUnless(sys.platform == 'win32' and os.environ.get('GITHUB_ACTIONS') == 'true',
                     'Recette réservée au runner Windows isolé')
class AttenteWindowsTests(unittest.TestCase):
    def test_owner_focus_rendu_et_etat_de_la_fenetre(self):
        p = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--scenario'],
                           cwd=ROOT / 'noethys', capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=20)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        for ligne in p.stdout.splitlines():
            if ligne.startswith(('ATTENTE_IMAGE ', 'ATTENTES_UI ')):
                print(ligne, flush=True)
        ligne = next(l for l in p.stdout.splitlines() if l.startswith('ATTENTES_UI '))
        d = json.loads(ligne.split(' ', 1)[1])
        self.assertEqual(d['erreurs'], [])
        avant, apres = d['observations']
        self.assertFalse(avant['owner'])
        self.assertTrue(avant['topmost'])
        self.assertTrue(apres['owner'] and apres['focus_inchange'] and apres['etat_inchange'])
        self.assertFalse(apres['topmost'])
        self.assertEqual(avant['taille'], apres['taille'])
        self.assertGreater(avant['pixels_texte'], 50)
        self.assertGreater(apres['pixels_texte'], 50, apres)
        alsh = d['alsh']
        self.assertTrue(alsh['connexion_fermee'] and alsh['retour_attendu'] and alsh['etat_inchange'], alsh)
        self.assertGreater(alsh['battements'], 10)
        self.assertLess(alsh['retard_ms'], 500)


if __name__ == '__main__':
    if '--scenario' in sys.argv:
        scenario()
    else:
        unittest.main()
