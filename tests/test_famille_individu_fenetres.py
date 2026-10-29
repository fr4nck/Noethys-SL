# -*- coding: utf-8 -*-
"""Navigation famille/individu : appels réels, widgets fictifs, pas de données."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'noethys/Ctrl/CTRL_Composition.py'
REFERENCE = json.loads((ROOT / 'tests/fixtures/composition_rc102.json').read_text(encoding='utf-8'))


def charger(classe, nom, wx, constructeur, ancien=False):
    if ancien:
        code = REFERENCE[classe + '.' + nom]
    else:
        texte = SOURCE.read_text(encoding='utf-8')
        c = next(n for n in ast.parse(texte).body if isinstance(n, ast.ClassDef) and n.name == classe)
        code = ast.get_source_segment(texte, next(n for n in c.body if isinstance(n, ast.FunctionDef) and n.name == nom))
    ns = dict(wx=wx, _=lambda s: s, DLG_Individu=SimpleNamespace(Dialog=constructeur),
              UTILS_Utilisateurs=SimpleNamespace(VerificationDroitsUtilisateurActuel=lambda *a: True))
    exec(code, ns)
    return ns[nom]


def faux_dlg(constructeur):
    m = ModuleType('Dlg')
    m.DLG_Individu = SimpleNamespace(Dialog=constructeur)
    m.DLG_Rattachement = SimpleNamespace(Dialog=constructeur)
    return m


class NavigationTests(unittest.TestCase):
    def test_deux_compositions_creation_et_modification_rattachees_a_famille(self):
        for classe in ('CTRL_Graphique', 'CTRL_Liste'):
            for nom in ('Ajouter', 'Modifier'):
                with self.subTest(classe=classe, nom=nom):
                    famille = object()
                    appels = []
                    def creer(parent, **kw):
                        appels.append((parent, kw))
                        return SimpleNamespace(ShowModal=lambda: 5100, Destroy=mock.Mock(), IDindividu=17,
                                               GetData=lambda: ('creation', 2, 0, None, 'Fictif', 'Test'))
                    wx = SimpleNamespace(ID_OK=5100, GetTopLevelParent=lambda w: famille)
                    vue = SimpleNamespace(IDfamille=7, MAJ=mock.Mock(), MAJnotebook=mock.Mock(),
                        GetSelection=lambda: object(), SupprimerFamille=mock.Mock(),
                        GetMainWindow=lambda: SimpleNamespace(GetItemPyData=lambda item: {'type':'individu', 'IDindividu':17}))
                    with mock.patch.dict(sys.modules, {'Dlg': faux_dlg(creer)}):
                        methode = charger(classe, nom, wx, creer)
                        methode(vue, 17) if classe == 'CTRL_Graphique' and nom == 'Modifier' else methode(vue)
                    self.assertEqual(len(appels), 2 if nom == 'Ajouter' else 1)
                    self.assertTrue(all(parent is famille for parent, kw in appels))
                    vue.MAJnotebook.assert_called_once()
                    vue.SupprimerFamille.assert_not_called()

    def test_aucune_fiche_runtime_ouverte_sans_parent_explicite(self):
        anomalies = []
        for dossier in ('Ctrl', 'Dlg', 'Ol'):
            for chemin in (ROOT / 'noethys' / dossier).glob('*.py'):
                tree = ast.parse(chemin.read_text(encoding='utf-8-sig'))
                for classe in (n for n in tree.body if isinstance(n, ast.ClassDef)):
                    for n in ast.walk(classe):
                        if (isinstance(n, ast.Call) and n.args and isinstance(n.args[0], ast.Constant)
                                and n.args[0].value is None and isinstance(n.func, ast.Attribute)
                                and n.func.attr == 'Dialog' and isinstance(n.func.value, ast.Name)
                                and n.func.value.id in ('DLG_Famille', 'DLG_Individu', 'DLG_Rattachement')):
                            anomalies.append((str(chemin.relative_to(ROOT)), n.lineno))
        self.assertEqual(anomalies, [])


def scenario(ancien=False):
    sys.path.insert(0, str(ROOT / 'tests'))
    import _garde_reseau
    import ctypes
    import wx
    app = wx.App(False)
    frame = wx.Frame(None, title='Principale - FICTIF', size=(950, 740))
    frame.Show()
    frame.Maximize(True)
    app.SetTopWindow(frame)
    observations, erreurs = [], []
    u32 = ctypes.windll.user32
    u32.GetWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    u32.GetWindow.restype = ctypes.c_void_p
    reference = None
    famille = None

    def etat(w):
        return (w.IsMaximized(), w.IsIconized(), tuple(w.GetRect()))

    def ouvrir_famille(maximisee=False):
        nonlocal famille, reference
        reference = etat(frame)
        famille = wx.Dialog(frame, title='Famille - FICTIF', size=(840, 700),
                            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX | wx.MINIMIZE_BOX)
        if maximisee:
            famille.Maximize(True)
        panneau = wx.Panel(famille)
        panneau.IDfamille = 7
        panneau.MAJ = mock.Mock()
        panneau.MAJnotebook = mock.Mock()
        panneau.SupprimerFamille = mock.Mock()
        panneau.GetSelection = lambda: object()
        panneau.GetMainWindow = lambda: SimpleNamespace(GetItemPyData=lambda item: {'type':'individu', 'IDindividu':17})

        def exercer():
            initial = etat(famille)

            class IndividuFictif(wx.Dialog):
                def __init__(self, parent, **kw):
                    super().__init__(parent, title='Individu - FICTIF', size=(710, 600),
                                     style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX | wx.MINIMIZE_BOX)
                    self.IDindividu = 17

                def GetData(self):
                    return ('creation', 2, 0, None, 'Fictif', 'Test')

                def ShowModal(self):
                    def verifier():
                        observations.append(dict(parent_correct=self.GetParent() is famille,
                            owner_correct=u32.GetWindow(self.GetHandle(), 4) == famille.GetHandle(),
                            principale=etat(frame) == reference, famille=etat(famille) == initial,
                            famille_desactivee=not famille.IsEnabled()))
                        self.EndModal(wx.ID_OK)
                    wx.CallLater(80, verifier)
                    return super().ShowModal()

            try:
                with mock.patch.dict(sys.modules, {'Dlg': faux_dlg(IndividuFictif)}):
                    for classe in ('CTRL_Graphique', 'CTRL_Liste'):
                        for nom in ('Modifier', 'Ajouter'):
                            methode = charger(classe, nom, wx, IndividuFictif, ancien)
                            methode(panneau, 17) if classe == 'CTRL_Graphique' and nom == 'Modifier' else methode(panneau)
                            assert famille.IsEnabled(), 'Famille restée désactivée'
                            assert etat(famille) == initial and etat(frame) == reference, 'Géométrie modifiée'
            except BaseException as erreur:
                erreurs.append(type(erreur).__name__ + ': ' + str(erreur))
            finally:
                famille.EndModal(wx.ID_CANCEL)
        wx.CallLater(200, exercer)
        famille.ShowModal()
        famille.Destroy()
        famille = None

    def lancer():
        ouvrir_famille(False)
        ouvrir_famille(True)
        print('FAMILLE_INDIVIDU_UI ' + json.dumps(dict(ancien=ancien, observations=observations,
              erreurs=erreurs, reseau=len(_garde_reseau.TENTATIVES))), flush=True)
        frame.Destroy()

    wx.CallLater(250, lancer)
    app.MainLoop()
    app.ProcessPendingEvents()
    import gc
    gc.collect()
    app.Destroy()


@unittest.skipUnless(sys.platform == 'win32' and os.environ.get('GITHUB_ACTIONS') == 'true',
                     'Recette graphique réservée au runner Windows isolé')
class NavigationWindowsTests(unittest.TestCase):
    def test_cycles_ajout_modification_retour_sans_changer_etat_fenetres(self):
        mesures = []
        for argument in ('--ancien', '--courant'):
            p = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--scenario', argument],
                               cwd=ROOT / 'noethys', capture_output=True, text=True, encoding='utf-8',
                               errors='replace', timeout=30)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            ligne = next(l for l in p.stdout.splitlines() if l.startswith('FAMILLE_INDIVIDU_UI '))
            m = json.loads(ligne.split(' ', 1)[1])
            self.assertEqual(m['erreurs'], [])
            self.assertEqual(m['reseau'], 0)
            self.assertEqual(len(m['observations']), 12)
            mesures.append(m)
        courant = mesures[1]
        self.assertTrue(all(all(o.values()) for o in courant['observations']), courant)
        print('FAMILLE_INDIVIDU_COMPARE ' + json.dumps(mesures), flush=True)


if __name__ == '__main__':
    if '--scenario' in sys.argv:
        scenario('--ancien' in sys.argv)
    else:
        unittest.main()
