# -*- coding: utf-8 -*-
"""#436 : tests isoles du dialogue wx de relecture, sans wx.App ni base PMSL."""
import ast
from datetime import date
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "noethys") not in sys.path:
    sys.path.insert(0, str(ROOT / "noethys"))
from Utils import UTILS_Reception_fiches as reception  # noqa: E402

FICHIER_DIALOGUE = ROOT / "noethys/Dlg/DLG_Reception_fiche_enfant.py"
FICHIER_INDIVIDU = ROOT / "noethys/Dlg/DLG_Individu.py"


def _charger_methodes():
    """Extrait le comportement a tester sans importer wxPython, ni creer d'UI."""
    source = FICHIER_DIALOGUE.read_text(encoding="utf-8")
    arbre = ast.parse(source)
    fonctions = []
    dialog = next(n for n in arbre.body
                  if isinstance(n, ast.ClassDef) and n.name == "Dialog")
    for nom in ("OnReporter", "OnOuvrirMedical", "_DateSaisie"):
        fonction = next(n for n in dialog.body
                        if isinstance(n, ast.FunctionDef) and n.name == nom)
        fonction.decorator_list = []
        fonctions.append(fonction)
    utilitaire = next(n for n in arbre.body
                      if isinstance(n, ast.FunctionDef)
                      and n.name == "_FormaterDatePeriode")
    messages = []
    wx = types.SimpleNamespace(
        ID_OK=5100, ID_APPLY=5103, OK=1, ICON_WARNING=2,
        MessageBox=lambda *args: messages.append(args),
    )
    contexte = {"reception": reception, "date_calendrier": date, "wx": wx}
    exec(compile(ast.fix_missing_locations(
        ast.Module(body=[utilitaire] + fonctions, type_ignores=[])),
        str(FICHIER_DIALOGUE), "exec"), contexte)
    return contexte, wx, messages


class Choix(object):
    def __init__(self, value):
        self.value = value

    def GetSelection(self):
        return self.value


class Valeur(object):
    def __init__(self, value):
        self.value = value

    def GetValue(self):
        return self.value


class DateFormulaire(object):
    def __init__(self, valeur_date=None, texte="  /  /    "):
        self.valeur_date = valeur_date
        self.texte = texte

    def GetDate(self):
        return self.valeur_date

    def GetValue(self):
        return self.texte


class EvenementsRelectureAEEH(unittest.TestCase):
    def setUp(self):
        self.api, self.wx, self.messages = _charger_methodes()
        class Boite(object):
            OnReporter = self.api["OnReporter"]
            OnOuvrirMedical = self.api["OnOuvrirMedical"]
            _DateSaisie = staticmethod(self.api["_DateSaisie"])

            def EndModal(self, code):
                self.fin = code
        self.boite = Boite()
        self.boite.IDindividu = 77
        self.boite.aeeh_actuelle = None
        self.boite.periodes = [
            {"date_debut": "2026-01-01", "date_fin": "2026-12-31"}
        ]
        self.boite.choix = Choix(1)
        self.boite.relecture = Valeur(True)
        self.boite.date_debut = DateFormulaire()
        self.boite.date_fin = DateFormulaire()
        self.boite._valeur_proposee = None
        self.boite._controle_periode = None
        self.boite.fin = None

    def test_date_existante_formatee_sans_ecriture(self):
        self.assertEqual(self.api["_FormaterDatePeriode"]("2026-10-28"), "28/10/2026")
        self.assertEqual(self.api["_FormaterDatePeriode"](date(2026, 10, 28)), "28/10/2026")
        self.assertEqual(self.api["_FormaterDatePeriode"](None), "date non indiquée")
        self.assertEqual(self.api["_FormaterDatePeriode"]("invalide"), "date à vérifier")

    def test_oui_relue_remonte_dans_le_controle_sans_creer_de_periode(self):
        self.boite.OnReporter(None)
        self.assertEqual(self.boite.fin, self.wx.ID_OK)
        self.assertEqual(self.boite._valeur_proposee, 1)
        self.assertEqual(self.boite._controle_periode["action"], "dates_non_communiquees")
        self.assertFalse(self.boite._controle_periode["ecriture_autorisee"])

    def test_relecture_non_confirmee_refuse_une_valeur(self):
        self.boite.relecture.value = False
        self.boite.OnReporter(None)
        self.assertIsNone(self.boite.fin)
        self.assertIsNone(self.boite._valeur_proposee)
        self.assertTrue(self.messages)

    def test_champs_date_partiels_refuses(self):
        self.boite.date_debut = DateFormulaire(None, "12/  /2026")
        self.boite.OnReporter(None)
        self.assertIsNone(self.boite.fin)
        self.assertIsNone(self.boite._valeur_proposee)
        self.assertTrue(self.messages)

    def test_fin_sans_debut_refusee(self):
        self.boite.date_fin = DateFormulaire(date(2027, 10, 28), "28/10/2027")
        self.boite.OnReporter(None)
        self.assertIsNone(self.boite.fin)
        self.assertTrue(self.messages)

    def test_periode_existante_detectee(self):
        self.boite.date_debut = DateFormulaire(date(2026, 1, 1), "01/01/2026")
        self.boite.date_fin = DateFormulaire(date(2026, 12, 31), "31/12/2026")
        self.boite.OnReporter(None)
        self.assertEqual(self.boite._controle_periode["action"], "periode_deja_connue")
        self.assertEqual(self.boite.fin, self.wx.ID_OK)

    def test_periode_qui_chevauche_est_a_arbitrer(self):
        self.boite.date_debut = DateFormulaire(date(2026, 7, 1), "01/07/2026")
        self.boite.date_fin = DateFormulaire(date(2027, 3, 1), "01/03/2027")
        self.boite.OnReporter(None)
        self.assertEqual(self.boite._controle_periode["action"], "periode_a_arbitrer")
        self.assertFalse(self.boite._controle_periode["ecriture_autorisee"])

    def test_nouvelle_periode_reste_a_verifier(self):
        self.boite.date_debut = DateFormulaire(date(2027, 1, 1), "01/01/2027")
        self.boite.OnReporter(None)
        self.assertEqual(self.boite._controle_periode["action"], "periode_a_verifier")

    def test_bouton_medical_ouvre_onglet_via_retour_modal(self):
        self.boite.OnOuvrirMedical(None)
        self.assertEqual(self.boite.fin, self.wx.ID_APPLY)

    def test_choix_inconnu_refuse(self):
        self.boite.choix.value = 99
        self.boite.OnReporter(None)
        self.assertIsNone(self.boite.fin)

    def test_dans_la_boite_aucune_reponse_medicale_n_est_validee(self):
        source = FICHIER_DIALOGUE.read_text(encoding="utf-8")
        self.assertIn("CTRL_Saisie_date.Date", source)
        self.assertIn("ComparerPeriodeAEEH(", source)
        self.assertIn("GetControlePeriode", source)
        for interdit in ("ReqInsert(", "ReqMAJ(", "UPDATE ", "INSERT INTO ",
                         "DLG_Saisie_pb_sante.Dialog", "DLG_Saisie_vaccin"):
            self.assertNotIn(interdit, source)

    def test_parent_ouvre_medical_sans_modifier_les_dates(self):
        src = FICHIER_INDIVIDU.read_text(encoding="utf-8")
        morceau = src.split("    def MenuControlerFicheEnfant(self, event):", 1)[1].split(
            "    def OnClose(self, event):", 1)[0]
        self.assertIn('if resultat_dialogue == wx.ID_APPLY:', morceau)
        self.assertIn('self.ctrl_notebook.AffichePage("medical")', morceau)
        self.assertIn('controle_periode = dlg.GetControlePeriode()', morceau)
        self.assertIn('action_periode == "periode_a_arbitrer"', morceau)
        self.assertIn('action_periode == "periode_a_verifier"', morceau)
        self.assertNotIn("ReqInsert(", morceau)
        self.assertNotIn("ReqMAJ(", morceau)
        self.assertNotIn('Sauvegarde(', morceau)


if __name__ == "__main__":
    unittest.main()
