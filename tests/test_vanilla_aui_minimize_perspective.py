# -*- coding: utf-8 -*-
"""Micro-repro (sans correctif) : doublon de pane '<nom>_min' après un
MinimizePane() suivi d'un LoadPerspective() vers une perspective antérieure
à la minimisation, puis d'un nouveau MinimizePane().

Mécanisme confirmé par lecture directe de wx.lib.agw.aui.framemanager
(wxPython 4.2.5) :

- AuiManager.MinimizePane() crée à chaque appel un nouvel AuiToolBar et
  l'ajoute via AddPane(AuiPaneInfo().Name(pane.name + "_min")...)
  (framemanager.py ~9902-9962).
- AuiManager.AddPane1() n'avertit ("A pane with the name '...' already
  exists in the manager!") et ne renomme que si un pane du MÊME NOM est
  déjà géré par un AUTRE objet fenêtre (framemanager.py ~4542-4550).
- AuiManager.LoadPerspective() ne touche que les panes présents dans la
  chaîne de perspective chargée (framemanager.py ~5255-5377) : un pane
  '<nom>_min' apparu APRÈS la sauvegarde de cette perspective n'y figure
  pas, n'est donc ni mis à jour ni détaché -- il reste géré, cabché.
- AuiManager.RestoreMinimizedPane() (chemin normal, hors
  AUI_MINIMIZE_POS_TOOLBAR), lui, appelle explicitement
  self.DetachPane(paneInfo.window) sur le pane '<nom>_min'
  (framemanager.py ~10096-10100) : il ne laisse donc aucune trace.

Ce fichier caractérise uniquement le défaut (aucun correctif Noethys SL
n'est testé ici) : contrat A (séquence problématique) et contrat B
(contrôle négatif, séquence normale).
"""
from __future__ import annotations

import sys
import unittest
import warnings
from pathlib import Path

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

import wx  # noqa: E402
import wx.lib.agw.aui as aui  # noqa: E402

_APP = wx.App(False)

from Utils import UTILS_AUI_Apparence  # noqa: E402


class MicroReproDoublonPaneMinTests(unittest.TestCase):
    """Reproduction mécanique avec un vrai aui.AuiManager, aucun code
    Noethys SL, aucun correctif : sert à classifier le défaut avant toute
    décision de correctif (contrat explicite de la mission)."""

    def setUp(self):
        self.frame = wx.Frame(None)
        self.addCleanup(self.frame.Destroy)
        self.mgr = aui.AuiManager()
        self.mgr.SetManagedWindow(self.frame)
        self.addCleanup(self.mgr.UnInit)

        self.panneau = wx.Panel(self.frame)
        self.mgr.AddPane(
            self.panneau,
            aui.AuiPaneInfo().Name("ephemeride").Caption("Ephéméride").Left(),
        )
        self.mgr.Update()

    def _capturer_avertissements(self):
        return warnings.catch_warnings(record=True)

    def test_A_minimiser_puis_loadperspective_par_defaut_puis_reminimiser_produit_l_avertissement(self):
        # Perspective par défaut : sauvegardée AVANT toute minimisation, ne
        # contient donc jamais de pane "ephemeride_min".
        perspective_defaut = self.mgr.SavePerspective()
        self.assertNotIn("ephemeride_min", perspective_defaut)

        # 1) minimiser
        self.mgr.MinimizePane(self.mgr.GetPane("ephemeride"))
        self.assertTrue(self.mgr.GetPane("ephemeride_min").IsOk(), "précondition : le pane '_min' auto-créé doit exister")
        ancien_toolbar = self.mgr.GetPane("ephemeride_min").window

        # 2) revenir à la disposition par défaut (le pane '_min' n'y figure
        # pas -> il n'est ni mis à jour ni détaché par LoadPerspective)
        self.mgr.LoadPerspective(perspective_defaut)
        self.assertTrue(
            self.mgr.GetPane("ephemeride_min").IsOk(),
            "le pane '_min' antérieur doit rester géré après LoadPerspective (c'est la cause du défaut)",
        )
        self.assertIs(self.mgr.GetPane("ephemeride_min").window, ancien_toolbar)

        # 3) minimiser à nouveau -> nouveau AuiToolBar, même nom "ephemeride_min"
        with self._capturer_avertissements() as capture:
            warnings.simplefilter("always")
            self.mgr.MinimizePane(self.mgr.GetPane("ephemeride"))

        messages = [str(item.message) for item in capture]
        self.assertTrue(
            any("ephemeride_min" in message and "already exists" in message for message in messages),
            "avertissement attendu absent ; messages capturés : %r" % (messages,),
        )

    def test_B_minimiser_puis_restaurer_normalement_puis_reminimiser_ne_produit_aucun_avertissement(self):
        """Contrôle négatif : le chemin normal (bouton restaurer, pas
        LoadPerspective) détache explicitement le pane '_min' -- aucun
        doublon ne doit se produire."""
        self.mgr.MinimizePane(self.mgr.GetPane("ephemeride"))
        self.assertTrue(self.mgr.GetPane("ephemeride_min").IsOk())

        self.mgr.RestoreMinimizedPane(self.mgr.GetPane("ephemeride"))
        self.assertFalse(
            self.mgr.GetPane("ephemeride_min").IsOk(),
            "la restauration normale doit détacher le pane '_min'",
        )

        with self._capturer_avertissements() as capture:
            warnings.simplefilter("always")
            self.mgr.MinimizePane(self.mgr.GetPane("ephemeride"))

        messages = [str(item.message) for item in capture]
        self.assertEqual(messages, [], "aucun avertissement attendu sur le chemin de restauration normal")


class NoethysSLAuiManagerLoadPerspectiveMinimizeTests(unittest.TestCase):
    """Correctif : NoethysSLAuiManager.LoadPerspective() détache tout
    pane-outil "_min" encore géré avant de déléguer à la version parente,
    générique (basé sur le suffixe "_min" de MinimizePane(), jamais sur un
    nom de pane particulier) -- vérifié ici sur plusieurs noms de panes
    métier distincts (ephemeride, messages, effectifs)."""

    NOMS_PANES = ["ephemeride", "messages", "effectifs"]

    def setUp(self):
        self.frame = wx.Frame(None)
        self.addCleanup(self.frame.Destroy)
        self.mgr = UTILS_AUI_Apparence.NoethysSLAuiManager()
        self.mgr.SetManagedWindow(self.frame)
        self.addCleanup(self.mgr.UnInit)

        self.panneaux = {}
        for nom in self.NOMS_PANES:
            panneau = wx.Panel(self.frame)
            self.panneaux[nom] = panneau
            self.mgr.AddPane(panneau, aui.AuiPaneInfo().Name(nom).Caption(nom).Left())
        self.mgr.Update()

    def _panes_min_geres(self):
        return [pane for pane in self.mgr._panes if pane.name.endswith("_min")]

    def test_1_minimiser_puis_perspective_par_defaut_puis_reminimiser_aucun_avertissement(self):
        for nom in self.NOMS_PANES:
            with self.subTest(pane=nom):
                perspective_defaut = self.mgr.SavePerspective()

                self.mgr.MinimizePane(self.mgr.GetPane(nom))
                self.assertTrue(self.mgr.GetPane(nom + "_min").IsOk())

                with warnings.catch_warnings(record=True) as capture:
                    warnings.simplefilter("always")
                    self.mgr.LoadPerspective(perspective_defaut)
                    self.mgr.MinimizePane(self.mgr.GetPane(nom))

                messages = [str(item.message) for item in capture]
                self.assertEqual(messages, [], "aucun avertissement attendu pour %r ; obtenu : %r" % (nom, messages))

    def test_2_un_seul_pane_min_reste_gere_par_nom(self):
        nom = "ephemeride"
        perspective_defaut = self.mgr.SavePerspective()

        self.mgr.MinimizePane(self.mgr.GetPane(nom))
        self.mgr.LoadPerspective(perspective_defaut)
        self.mgr.MinimizePane(self.mgr.GetPane(nom))

        panes_min = [pane for pane in self._panes_min_geres() if pane.name == nom + "_min"]
        self.assertEqual(len(panes_min), 1, "un seul pane '%s_min' doit rester géré, obtenu : %r" % (nom, panes_min))
        # Et aucun pane-outil fantôme renommé aléatoirement ne doit traîner.
        self.assertEqual(len(self._panes_min_geres()), 1, "aucun pane '_min' fantôme ne doit rester géré")

    def test_3_minimiser_puis_restaurer_puis_reminimiser_toujours_ok(self):
        nom = "messages"
        self.mgr.MinimizePane(self.mgr.GetPane(nom))
        self.mgr.RestoreMinimizedPane(self.mgr.GetPane(nom))

        with warnings.catch_warnings(record=True) as capture:
            warnings.simplefilter("always")
            self.mgr.MinimizePane(self.mgr.GetPane(nom))

        messages = [str(item.message) for item in capture]
        self.assertEqual(messages, [])
        self.assertEqual(len([p for p in self._panes_min_geres() if p.name == nom + "_min"]), 1)

    def test_4_perspective_sauvegardee_avec_pane_minimise_puis_rechargee_stable(self):
        nom = "effectifs"
        self.mgr.MinimizePane(self.mgr.GetPane(nom))
        perspective_minimisee = self.mgr.SavePerspective()
        self.assertIn(nom + "_min", perspective_minimisee)

        with warnings.catch_warnings(record=True) as capture:
            warnings.simplefilter("always")
            self.mgr.LoadPerspective(perspective_minimisee)

        messages = [str(item.message) for item in capture]
        self.assertEqual(messages, [], "rechargement d'une perspective déjà minimisée : aucun avertissement attendu")

        panes_min = [p for p in self._panes_min_geres() if p.name == nom + "_min"]
        self.assertEqual(len(panes_min), 1, "un seul pane '%s_min' doit rester géré après rechargement" % nom)
        self.assertTrue(self.mgr.GetPane(nom).IsMinimized())
        self.assertEqual(len(self._panes_min_geres()), 1, "aucun pane '_min' fantôme ne doit rester géré")

    def test_5_save_load_perspective_normal_sans_minimisation_aucune_regression(self):
        perspective = self.mgr.SavePerspective()

        with warnings.catch_warnings(record=True) as capture:
            warnings.simplefilter("always")
            resultat = self.mgr.LoadPerspective(perspective)

        self.assertTrue(resultat)
        messages = [str(item.message) for item in capture]
        self.assertEqual(messages, [])
        for nom in self.NOMS_PANES:
            pane = self.mgr.GetPane(nom)
            self.assertTrue(pane.IsOk())
            self.assertIs(pane.window, self.panneaux[nom])
            self.assertFalse(pane.IsMinimized())
        self.assertEqual(self._panes_min_geres(), [])


class NoethysSLAuiManagerAucuneAccumulationDeToolbarTests(unittest.TestCase):
    """AuiManager.DetachPane() (wx.lib.agw.aui, wxPython 4.2.5) ne détruit
    jamais la fenêtre détachée : elle reste enfant de la fenêtre gérée,
    cachée mais vivante. Sans destruction explicite, répéter
    minimize -> LoadPerspective(...) accumule indéfiniment des AuiToolBar
    orphelines (jamais gérées, jamais détruites) -- vérifié mécaniquement
    avant tout correctif : 20 cycles -> 20 AuiToolBar orphelines.

    Le correctif honore IsDestroyOnClose() (posé systématiquement par
    MinimizePane() sur le pane-outil "_min" qu'elle crée) après
    DetachPane(), exactement comme le fait déjà AuiManager.ClosePane()
    pour tout pane ainsi marqué -- pas une destruction inventée."""

    NB_CYCLES = 20

    def setUp(self):
        self.frame = wx.Frame(None)
        self.addCleanup(self.frame.Destroy)
        self.mgr = UTILS_AUI_Apparence.NoethysSLAuiManager()
        self.mgr.SetManagedWindow(self.frame)
        self.addCleanup(self.mgr.UnInit)

        self.panneau = wx.Panel(self.frame)
        self.mgr.AddPane(self.panneau, aui.AuiPaneInfo().Name("ephemeride").Caption("Ephéméride").Left())
        self.mgr.Update()

    def _toolbars_enfants_de_la_fenetre_geree(self):
        return [fenetre for fenetre in self.frame.GetChildren() if isinstance(fenetre, aui.AuiToolBar)]

    def test_pas_daccumulation_de_toolbar_apres_cycles_repetes(self):
        perspective_defaut = self.mgr.SavePerspective()

        for _ in range(self.NB_CYCLES):
            self.mgr.MinimizePane(self.mgr.GetPane("ephemeride"))
            self.mgr.LoadPerspective(perspective_defaut)

        # Un seul pane géré au total (le pane métier lui-même) : aucun
        # pane-outil "_min" ne doit rester géré entre deux cycles.
        self.assertEqual(len(self.mgr._panes), 1)
        self.assertEqual(self.mgr._panes[0].name, "ephemeride")

        # Aucune AuiToolBar fantôme ne doit rester enfant de la fenêtre
        # gérée : DetachPane() seul les aurait laissées vivantes, cachées.
        self.assertEqual(
            self._toolbars_enfants_de_la_fenetre_geree(), [],
            "des AuiToolBar orphelines se sont accumulées après %d cycles" % self.NB_CYCLES,
        )

    def test_ne_detruit_pas_le_pane_metier_encore_utilise(self):
        """Le correctif ne doit détruire que les pane-outils "_min"
        auto-créés (DestroyOnClose() posé par MinimizePane() lui-même),
        jamais un pane métier -- même minimisé, même après rechargement."""
        perspective_defaut = self.mgr.SavePerspective()

        self.mgr.MinimizePane(self.mgr.GetPane("ephemeride"))
        self.mgr.LoadPerspective(perspective_defaut)

        self.assertFalse(self.mgr.GetPane("ephemeride").IsDestroyOnClose())
        self.assertTrue(self.panneau)  # objet C++ vivant : bool() ne lève pas
        self.assertIs(self.mgr.GetPane("ephemeride").window, self.panneau)


if __name__ == "__main__":
    unittest.main()
