# -*- coding: utf-8 -*-
"""UI-3A : les diagnostics ne capturent aucun contenu prive."""
from __future__ import annotations

import ast
import importlib.util
import os
from pathlib import Path
from unittest import TestCase, main, mock

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "noethys" / "Utils" / "UTILS_Diagnostic_ui.py"
CONNECT = ROOT / "noethys" / "Dlg" / "DLG_Saisie_portail_demande.py"
spec = importlib.util.spec_from_file_location("ui_diagnostic_synthetique", MODULE)
diag_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag_module)


class TempsFictif:
    def __init__(self):
        self.valeur = 0.0
    def __call__(self):
        return self.valeur


class Evenement:
    def __init__(self, actif=True, source=None):
        self.actif = actif
        self.source = source
        self.skipped = False
    def GetActive(self):
        return self.actif
    def GetEventObject(self):
        return self.source
    def Skip(self):
        self.skipped = True


class FenetreFictive:
    def __init__(self):
        self.bindings = {}
    def Bind(self, kind, func, *args):
        self.bindings[kind] = func
    def IsMaximized(self):
        return True
    def GetSize(self):
        return (800, 600)
    def IsIconized(self):
        return False


class WxFictif:
    EVT_TIMER = "timer"
    EVT_ACTIVATE = "activate"
    EVT_MAXIMIZE = "maximize"
    EVT_SIZE = "size"
    EVT_ICONIZE = "iconize"
    EVT_WINDOW_DESTROY = "destroy"

    class Timer:
        def __init__(self, owner=None):
            self.owner = owner
            self.started = []
            self.stopped = False
            self.bindings = {}
        def Bind(self, kind, func, *args):
            self.bindings[kind] = func
        def Start(self, interval):
            self.started.append(interval)
        def Stop(self):
            self.stopped = True


class DiagnosticTests(TestCase):
    def setUp(self):
        self.fenetre = FenetreFictive()
        self.temps = TempsFictif()
        self.logs = []

    def nouveau(self):
        return diag_module.Diagnostic(
            self.fenetre, actif=True, clock=self.temps,
            sortie=self.logs.append, wx_module=WxFictif,
        )

    def test_inactif_par_defaut_ne_cree_aucun_timer(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            d = diag_module.Diagnostic(self.fenetre, wx_module=WxFictif,
                                       sortie=self.logs.append)
        self.assertFalse(d.actif)
        self.assertEqual(self.fenetre.bindings, {})
        with d.mesurer("demande.traitement"):
            self.temps.valeur += 3
        self.assertEqual(self.logs, [])

    def test_operations_et_battement_enregistrent_uniquement_des_durees(self):
        d = self.nouveau()
        self.assertEqual(d._timer.started, [250])
        self.temps.valeur = 3.75
        ev = Evenement()
        d._on_battement(ev)
        self.assertTrue(ev.skipped)
        self.assertEqual(self.logs[0]["evenement"], "retard_boucle")
        self.assertEqual(self.logs[0]["retard_ms"], 3500)
        with d.mesurer("reservations.sauvegarde"):
            self.temps.valeur += 1.5
        self.assertEqual(self.logs[1]["operation"], "reservations.sauvegarde")
        self.assertEqual(self.logs[1]["duree_ms"], 1500)
        self.assertGreater(self.logs[1]["sans_evenements_ms"], 0)
        self.assertTrue(self.logs[1]["maximise"])

    def test_aucune_chaine_personnelle_dans_le_journal(self):
        d = self.nouveau()
        with self.assertRaisesRegex(ValueError, "NOM_FICTIF_NON_PUBLIC"):
            with d.mesurer("contact@example.test"):
                self.temps.valeur += 1
                raise ValueError("NOM_FICTIF_NON_PUBLIC")
        compte = self.logs[-1]
        self.assertEqual(compte["operation"], "inconnue")
        self.assertEqual(compte["erreur_type"], "ValueError")
        self.assertNotIn("NOM_FICTIF_NON_PUBLIC", repr(compte))
        self.assertNotIn("contact@example.test", repr(compte))
        self.assertFalse({"famille", "adresse", "email", "montant"} & set(compte))

    def test_etapes_individuelles_inertes_et_anonymisees(self):
        logs = []
        with mock.patch.dict(os.environ, {}, clear=True):
            diag_module.tracer_etape_grille("grille.activites", 3465, sortie=logs.append)
        self.assertEqual(logs, [])
        with mock.patch.dict(os.environ, {diag_module.ENVIRONNEMENT: "1"}):
            diag_module.tracer_etape_grille("grille.activites", 3465.8, sortie=logs.append)
            diag_module.tracer_etape_grille("contact@example.test", 11, sortie=logs.append)
        self.assertEqual(logs[0], {"evenement": "etape", "etape": "grille.activites",
                                   "duree_ms": 3465})
        self.assertEqual(logs[1]["etape"], "grille.inconnue")
        self.assertNotIn("contact@example.test", repr(logs))

    def test_focus_et_maximisation_ne_loggent_que_des_booleens(self):
        d = self.nouveau()
        ev = Evenement(actif=False, source=self.fenetre)
        d._on_activation(ev)
        self.assertEqual(self.logs[-1], {"evenement": "activation", "actif": False})
        d._on_maximisation(ev)
        self.assertEqual(self.logs[-1], {"evenement": "maximisation", "maximise": True})
        d._on_taille(ev)
        self.assertEqual(self.logs[-1], {"evenement": "taille", "largeur": 800,
                                         "hauteur": 600, "maximise": True})
        d._on_iconisation(ev)
        self.assertEqual(self.logs[-1], {"evenement": "iconisation", "iconise": False})
        self.assertTrue(ev.skipped)

    def test_evenements_enfants_ne_sont_pas_attribues_a_la_frame(self):
        d = self.nouveau()
        for methode in (d._on_activation, d._on_maximisation, d._on_taille,
                        d._on_iconisation):
            ev = Evenement(source=object())
            methode(ev)
            self.assertTrue(ev.skipped)
        self.assertEqual(self.logs, [])

    def test_role_ferme_distingue_frame_et_dialogue_sans_titre(self):
        d = diag_module.Diagnostic(self.fenetre, actif=True, role="principale",
                                   sortie=self.logs.append, wx_module=WxFictif)
        d._on_taille(Evenement(source=self.fenetre))
        self.assertEqual(self.logs[-1]["fenetre"], "principale")
        self.assertNotIn("titre", self.logs[-1])

    def test_veille_thread_inactive_pour_fenetre_fictive(self):
        d = diag_module.Diagnostic(
            self.fenetre, actif=True, role="principale",
            wx_module=WxFictif, sortie=self.logs.append)
        self.assertIsNone(d._veille_stop)
        self.assertNotIn("point", d._etat_precedent or {})

    def test_point_blocage_ne_devoile_ni_les_variables_ni_le_chemin(self):
        from types import SimpleNamespace as NS
        d = self.nouveau()
        point_code = NS(co_filename=diag_module.__file__, co_name="lecture_bloquante")
        cadre = NS(f_code=point_code, f_lineno=321, f_back=None,
                   f_locals={"mot_de_passe": "SECRET_JAMAIS_DANS_LE_LOG"})
        with mock.patch.object(diag_module.sys, "_current_frames",
                               return_value={987: cadre}):
            point = d._point_thread(987)
        self.assertEqual(point, "UTILS_Diagnostic_ui.py:lecture_bloquante:321")
        self.assertNotIn("SECRET", point)
        self.assertNotIn(str(diag_module.MODULE) if hasattr(diag_module, "MODULE")
                         else str(MODULE.parent), point)
        autre_fichier = os.path.abspath(
            os.path.join(os.path.dirname(diag_module.__file__), "..", "..", "privé.py"))
        cadre.f_code = NS(co_filename=autre_fichier, co_name="secret")
        with mock.patch.object(diag_module.sys, "_current_frames",
                               return_value={987: cadre}):
            self.assertEqual(d._point_thread(987), "hors_noethys")

    def test_veille_retardee_distingue_famine_gil_et_localise_la_synchro(self):
        from types import SimpleNamespace as NS
        d = self.nouveau()
        d._dernier_battement = 100.0
        point_code = NS(co_filename=diag_module.__file__, co_name="Upload_data")
        cadre = NS(f_code=point_code, f_lineno=77, f_back=None,
                   f_locals={"mdp": "SECRET_JAMAIS_DANS_LE_LOG"})
        synchro = NS(name="Noethys-Connecthys-synchro", ident=555,
                     is_alive=lambda: True)
        with mock.patch.object(diag_module.sys, "_current_frames",
                               return_value={555: cadre}), \
                mock.patch.object(diag_module.threading, "enumerate",
                                  return_value=[synchro]):
            prochaine = d._cycle_veille(987, maintenant=123.0, attendu=100.5,
                                        prochaine=0.0)
        self.assertEqual(prochaine, 128.0)
        veille, blocage = self.logs[-2], self.logs[-1]
        self.assertEqual(veille["evenement"], "veille_retardee")
        self.assertEqual(veille["veille_retard_ms"], 22500)
        self.assertEqual(veille["point_synchro"], "UTILS_Diagnostic_ui.py:Upload_data:77")
        self.assertEqual(blocage["evenement"], "blocage_thread")
        self.assertEqual(blocage["duree_ms"], 23000)
        self.assertEqual(blocage["point"], "hors_noethys")
        self.assertNotIn("SECRET", repr(self.logs))

    def test_veille_ponctuelle_sans_synchro_ne_signale_rien(self):
        d = self.nouveau()
        d._dernier_battement = 100.0
        avant = len(self.logs)
        with mock.patch.object(diag_module.threading, "enumerate", return_value=[]):
            self.assertEqual(d._cycle_veille(987, 100.6, 100.5, 0.0), 0.0)
            self.assertEqual(d._point_synchro(), "aucune")
        self.assertEqual(len(self.logs), avant)

    def test_threads_synchro_nommes_pour_le_diagnostic(self):
        racine = ROOT / "noethys"
        serveur = (racine / "Ctrl" / "CTRL_Portail_serveur.py").read_text(encoding="utf-8")
        manuel = (racine / "Dlg" / "DLG_Portail_config.py").read_text(encoding="utf-8")
        self.assertIn('Thread.__init__(self, name="%s")' % diag_module.THREADS_SYNCHRO[0], serveur)
        self.assertIn('name="%s"' % diag_module.THREADS_SYNCHRO[1], manuel)

    def test_timer_sans_proprietaire_et_arret_si_fenetre_detruite(self):
        d = self.nouveau()
        self.assertIsNone(d._timer.owner)
        self.assertIn(WxFictif.EVT_TIMER, d._timer.bindings)
        self.assertNotIn(WxFictif.EVT_TIMER, self.fenetre.bindings)
        timer = d._timer
        d._veille_stop = __import__("threading").Event()
        with mock.patch.object(FenetreFictive, "__bool__", lambda self: False, create=True):
            d._on_battement(Evenement(source=timer))
        self.assertTrue(timer.stopped)
        self.assertIsNone(d._timer)
        self.assertTrue(d._veille_stop.is_set())
        self.assertNotIn("retard_boucle", [e["evenement"] for e in self.logs])

    def test_timer_arrete_uniquement_a_la_destruction_de_la_fenetre(self):
        d = self.nouveau()
        d._on_destruction(Evenement(source=object()))
        self.assertFalse(d._timer.stopped)
        timer = d._timer
        d._on_destruction(Evenement(source=self.fenetre))
        self.assertTrue(timer.stopped)
        self.assertIsNone(d._timer)

    def test_mesurer_sur_fausse_fenetre_ne_change_pas_le_resultat(self):
        objet = object()
        with diag_module.mesurer(objet, "reservations.calcul"):
            valeur = 42
        self.assertEqual(valeur, 42)


def source_methode(classe, nom):
    s = CONNECT.read_text(encoding="utf-8")
    tree = ast.parse(s)
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == classe)
    method = next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == nom)
    return ast.get_source_segment(s, method)


class SourceContracts(TestCase):
    def test_collecte_connecthys_autour_des_phases_existantes(self):
        top = source_methode("Dialog", "Traitement")
        res = source_methode("Traitement", "Traitement_reservations")
        self.assertIn('"demande.traitement"', top)
        self.assertIn('"demande.enregistrement"', top)
        self.assertIn('"demande.actualisation"', top)
        for code in ("reservations.initialisation_grille", "reservations.calcul",
                     "reservations.sauvegarde"):
            self.assertIn(code, res)
        self.assertIn("self.Save_grille(ctrl_grille)", res)
        self.assertNotIn("wx.Yield", res)
        self.assertNotIn("threading.Thread", res)


if __name__ == "__main__":
    main()
