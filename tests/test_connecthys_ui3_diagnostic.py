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
        def __init__(self, owner):
            self.owner = owner
            self.started = []
            self.stopped = False
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
