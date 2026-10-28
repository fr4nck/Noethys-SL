# -*- coding: utf-8 -*-
"""#436 : tests evenementiels isoles du dialogue wx, sans wx.App ni base PMSL.

Le comportement des deux boutons est extrait par AST. Les services sont
remplaces par des doubles instrumentes, afin d'interdire tout appel SQL.
"""
import ast
from datetime import date
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
NOETHYS = str(ROOT / "noethys")
if NOETHYS not in sys.path:
    sys.path.insert(0, NOETHYS)
import Utils  # noqa: E402
from Utils import UTILS_Reception_fiches as reception  # noqa: E402
from Utils import UTILS_Suivi_fiches as vrai_suivi  # noqa: E402
from Utils import UTILS_AEEH_Periodes as vrai_periodes  # noqa: E402


def _extraire():
    source = (ROOT / "noethys/Dlg/DLG_Reception_fiche_enfant.py").read_text(
        encoding="utf-8")
    arbre = ast.parse(source)
    dial = next(n for n in arbre.body if isinstance(n, ast.ClassDef)
                and n.name == "Dialog")
    noms = ("OnEnregistrerPeriode", "OnHistoriserParent", "_Source",
            "_DateSaisie", "_RafraichirConfirmation")
    fonctions = []
    for name in noms:
        fonction = next(n for n in dial.body if isinstance(n, ast.FunctionDef)
                        and n.name == name)
        fonction.decorator_list = []
        fonctions.append(fonction)
    util = next(n for n in arbre.body if isinstance(n, ast.FunctionDef)
                and n.name == "_FormaterDatePeriode")
    champs = next(n for n in arbre.body if isinstance(n, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == "RUBRIQUES_SANTE" for t in n.targets))
    messages = []
    config = {"reponse": 19}
    def message(*args):
        messages.append(args)
        return config["reponse"]
    wx = types.SimpleNamespace(
        YES=19, YES_NO=8, OK=1, ICON_WARNING=2,
        ICON_QUESTION=4, ICON_ERROR=16, ICON_INFORMATION=32,
        MessageBox=message,
    )
    namespace = {
        "wx": wx, "reception": reception, "date_calendrier": date,
        "RUBRIQUES_SANTE": ast.literal_eval(champs.value),
    }
    exec(compile(ast.fix_missing_locations(
        ast.Module(body=[util] + fonctions, type_ignores=[])),
        "<dialogue-fictif-436>", "exec"), namespace)
    return namespace, messages, wx, config


class Valeur:
    def __init__(self, valeur):
        self.valeur = valeur
    def GetValue(self):
        return self.valeur
    def GetSelection(self):
        return self.valeur
    def Set(self, valeurs):
        self.valeur = valeurs
    def SetLabel(self, texte):
        self.valeur = texte
    def Enable(self, statut):
        self.valeur = statut


class DateSaisie:
    def __init__(self, contenu=None, texte="  /  /    "):
        self.contenu = contenu
        self.texte = texte
    def GetDate(self):
        return self.contenu
    def GetValue(self):
        return self.texte


class Rubriques:
    def __init__(self, indices=()):
        self.indices = set(indices)
    def IsChecked(self, i):
        return i in self.indices


class EvenementsWx(unittest.TestCase):
    def setUp(self):
        api, self.messages, self.wx, self.config = _extraire()
        class Boite:
            OnEnregistrerPeriode = api["OnEnregistrerPeriode"]
            OnHistoriserParent = api["OnHistoriserParent"]
            _Source = api["_Source"]
            _DateSaisie = staticmethod(api["_DateSaisie"])
            _RafraichirConfirmation = api["_RafraichirConfirmation"]

        self.dlg = Boite()
        self.dlg.IDindividu = 77
        self.dlg.source = Valeur(2)
        self.dlg.relecture = Valeur(True)
        self.dlg.justificatif = Valeur(True)
        self.dlg.date_debut = DateSaisie(date(2026, 1, 1))
        self.dlg.date_fin = DateSaisie(date(2026, 12, 31))
        self.dlg.fin_non_precisee = Valeur(False)
        self.dlg.liste_periodes = Valeur([])
        self.dlg.bouton_periode = Valeur(True)
        self.dlg.periodes = []
        self.dlg.fiche_signee = Valeur(True)
        self.dlg.rubriques_sante = Rubriques((0, 3))
        self.dlg.date_signature = DateSaisie(date(2026, 10, 20))
        self.dlg.label_derniere = Valeur("")

        self.suivi = types.SimpleNamespace(
            ControleFicheInvalide=vrai_suivi.ControleFicheInvalide,
            EnregistrerPeriodeVerifiee=mock.Mock(return_value=123),
            EnregistrerConfirmationParentale=mock.Mock(return_value=True),
            GetDerniereConfirmationParentale=mock.Mock(return_value={
                "date_reception": "2026-10-28", "heure": "09:00:00",
            }),
        )
        self.periodes = types.SimpleNamespace(
            PeriodeAEEHInvalide=vrai_periodes.PeriodeAEEHInvalide,
            GetPeriodes=mock.Mock(return_value=[{
                "IDperiode": 123, "date_debut": "2026-01-01",
                "date_fin": "2026-12-31",
            }]),
        )
        self.ident = types.SimpleNamespace(GetIDutilisateur=mock.Mock(return_value=11))
        self.droits = types.SimpleNamespace(
            VerificationDroitsUtilisateurActuel=mock.Mock(return_value=True),
        )
        for attr, objet in (("UTILS_Suivi_fiches", self.suivi),
                            ("UTILS_AEEH_Periodes", self.periodes),
                            ("UTILS_Identification", self.ident),
                            ("UTILS_Utilisateurs", self.droits)):
            p = mock.patch.object(Utils, attr, objet, create=True)
            p.start()
            self.addCleanup(p.stop)

    def test_enregistrement_periode_exige_confirmation_et_justificatif(self):
        self.dlg.OnEnregistrerPeriode(None)
        self.suivi.EnregistrerPeriodeVerifiee.assert_called_once()
        args, kw = self.suivi.EnregistrerPeriodeVerifiee.call_args
        self.assertEqual(args[:2], (77, 11))
        self.assertEqual(kw["source"], "pieces")
        self.assertIs(kw["justificatif_verifie"], True)
        self.assertEqual(self.dlg.liste_periodes.valeur, [
            "Du 01/01/2026 au 31/12/2026",
        ])

    def test_pas_de_justificatif(self):
        self.dlg.justificatif.valeur = False
        self.dlg.OnEnregistrerPeriode(None)
        self.suivi.EnregistrerPeriodeVerifiee.assert_not_called()

    def test_pas_de_relecture(self):
        self.dlg.relecture.valeur = False
        self.dlg.OnEnregistrerPeriode(None)
        self.suivi.EnregistrerPeriodeVerifiee.assert_not_called()

    def test_source_absente(self):
        self.dlg.source.valeur = 0
        self.dlg.OnEnregistrerPeriode(None)
        self.suivi.EnregistrerPeriodeVerifiee.assert_not_called()

    def test_operateur_inconnu(self):
        self.ident.GetIDutilisateur.return_value = None
        self.dlg.OnEnregistrerPeriode(None)
        self.suivi.EnregistrerPeriodeVerifiee.assert_not_called()

    def test_periode_sans_debut(self):
        self.dlg.date_debut = DateSaisie()
        self.dlg.OnEnregistrerPeriode(None)
        self.suivi.EnregistrerPeriodeVerifiee.assert_not_called()

    def test_refus_confirmation(self):
        self.config["reponse"] = -1
        self.dlg.OnEnregistrerPeriode(None)
        self.suivi.EnregistrerPeriodeVerifiee.assert_not_called()

    def test_erreur_service_aucune_reussite_affichee(self):
        self.suivi.EnregistrerPeriodeVerifiee.side_effect = (
            vrai_suivi.ControleFicheInvalide("test : pas de justificatif"))
        self.dlg.OnEnregistrerPeriode(None)
        self.assertFalse(any("n°123 enregistré" in args[0]
                             for args in self.messages))

    def test_echec_rafraichissement_ne_rejoue_pas_une_ecriture(self):
        self.periodes.GetPeriodes.side_effect = RuntimeError("simulation")
        self.dlg.OnEnregistrerPeriode(None)
        self.suivi.EnregistrerPeriodeVerifiee.assert_called_once()
        self.assertIs(self.dlg.bouton_periode.valeur, False)

    def test_enregistrement_parental_signale_mais_ne_certifie_pas_medical(self):
        self.dlg.OnHistoriserParent(None)
        self.suivi.EnregistrerConfirmationParentale.assert_called_once()
        args, kw = self.suivi.EnregistrerConfirmationParentale.call_args
        self.assertEqual(args[:2], (77, 11))
        self.assertEqual(args[2], ["vaccinations", "pai"])
        self.assertEqual(kw["date_parent"], date(2026, 10, 20))
        self.assertIs(kw["fiche_signee"], True)
        self.assertIs(kw["document_relu"], True)
        self.suivi.GetDerniereConfirmationParentale.assert_called_once_with(77)
        self.assertIn("Dernière réception contrôlée", self.dlg.label_derniere.valeur)

    def test_parentale_non_signee_refusee(self):
        self.dlg.fiche_signee.valeur = False
        self.dlg.OnHistoriserParent(None)
        self.suivi.EnregistrerConfirmationParentale.assert_not_called()

    def test_parentale_aucune_rubrique_refusee(self):
        self.dlg.rubriques_sante = Rubriques()
        self.dlg.OnHistoriserParent(None)
        self.suivi.EnregistrerConfirmationParentale.assert_not_called()

    def test_parentale_confirmation_annulee(self):
        self.config["reponse"] = -1
        self.dlg.OnHistoriserParent(None)
        self.suivi.EnregistrerConfirmationParentale.assert_not_called()

    def test_parentale_erreur_service_ne_presume_pas_succes(self):
        self.suivi.EnregistrerConfirmationParentale.side_effect = RuntimeError("injection")
        self.dlg.OnHistoriserParent(None)
        self.assertFalse(any("Réception parentale historisée" in args[0]
                             for args in self.messages))
        self.suivi.GetDerniereConfirmationParentale.assert_not_called()

    def test_droit_parental_sans_reception(self):
        self.suivi.GetDerniereConfirmationParentale.return_value = None
        self.dlg._RafraichirConfirmation()
        self.assertIn("Aucune réception parentale", self.dlg.label_derniere.valeur)

    def test_historique_interdit_ne_consulte_rien(self):
        self.droits.VerificationDroitsUtilisateurActuel.return_value = False
        self.dlg._RafraichirConfirmation()
        self.droits.VerificationDroitsUtilisateurActuel.assert_called_once_with(
            "individus_historique", "consulter", afficheMessage=False)
        self.suivi.GetDerniereConfirmationParentale.assert_not_called()
        self.assertIn("non accessible", self.dlg.label_derniere.valeur)

    def test_historique_indisponible_signale(self):
        self.suivi.GetDerniereConfirmationParentale.side_effect = RuntimeError("injection")
        self.dlg._RafraichirConfirmation()
        self.assertIn("indisponible", self.dlg.label_derniere.valeur)


if __name__ == "__main__":
    unittest.main()
