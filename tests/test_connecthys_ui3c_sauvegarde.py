# -*- coding: utf-8 -*-
"""UI-3C : coherences wx/SQLite et absence de second traitement apres panne.

Tous les tests travaillent sur un fichier SQLite temporaire, et sur des
widgets doubles. Aucune sauvegarde PMSL, aucun reseau, aucun mail reel.
"""
from __future__ import annotations

import ast
import datetime
import re
import sqlite3
import sys
import unittest
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "noethys", ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import _garde_reseau  # noqa: E402,F401
import GestionDB  # noqa: E402
from _fixtures_noethys_db import BaseTest, RedirectionGestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402
from Utils import UTILS_Emails_acceptes as Suivis  # noqa: E402

SOURCE = ROOT / "noethys" / "Dlg" / "DLG_Saisie_portail_demande.py"

try:
    from Dlg import DLG_Saisie_portail_demande as Module  # noqa: E402
except (ImportError, RuntimeError):
    Module = None


class RadioEtat:
    def __init__(self):
        self.validation = False

    def attente(self):
        parent = self
        class Radio:
            def GetValue(self):
                return not parent.validation
            def SetValue(self, value):
                if value:
                    parent.validation = False
        return Radio()

    def valide(self):
        parent = self
        class Radio:
            def GetValue(self):
                return parent.validation
            def SetValue(self, value):
                if value:
                    parent.validation = True
        return Radio()


class Texte:
    def __init__(self, valeur=""):
        self.valeur = valeur
    def GetValue(self):
        return self.valeur
    def ChangeValue(self, valeur):
        self.valeur = valeur


class Date:
    def __init__(self, valeur=None):
        self.date = valeur or datetime.date(2026, 10, 26)
    def GetDate(self):
        return self.date
    def SetDate(self, date):
        self.date = date
    def Enable(self, enable):
        pass


class ErreurCurseur:
    def __init__(self, origine, fixture):
        self.origine = origine
        self.fixture = fixture
    def execute(self, sql, *params):
        if (self.fixture.echec_sql
                and re.search(r"^UPDATE portail_actions SET", sql, re.I)):
            raise sqlite3.OperationalError("UPDATE refuse (simulation)")
        return self.origine.execute(sql, *params)
    def __getattr__(self, nom):
        return getattr(self.origine, nom)


class DialogueFictif:
    """Attache les vraies methodes production, pas une copie de logique."""
    def __init__(self):
        self.track = SimpleNamespace(
            IDaction=7, IDfamille=3, email_date=None, categorie="reservations",
            etat="attente", reponse=None, traitement_date=None,
            Refresh=mock.Mock(),
        )
        self.tracks = [self.track, SimpleNamespace(IDaction=8)]
        self.radio = RadioEtat()
        self.radio_attente = self.radio.attente()
        self.radio_validation = self.radio.valide()
        self.ctrl_reponse = Texte()
        self.ctrl_date_validation = Date()
        self.panel_bandeau = mock.Mock()
        self.OnRadioEtat = mock.Mock()
        self._traitement_en_cours = False
        self._finalisation_en_attente = None
        self._finalisation_en_cours = False
        self.ctrl_solde = mock.Mock()
        self.MAJ_informations = mock.Mock()
        self.AfficherProgressionReservations = mock.Mock()
        self.MAJ = mock.Mock()
        self.EndModal = mock.Mock()
        self.SetEtat = MethodType(Module.Dialog.SetEtat, self)
        self.Sauvegarde = MethodType(Module.Dialog.Sauvegarde, self)
        self.EnregistrerDemande = MethodType(Module.Dialog.EnregistrerDemande, self)
        self._AfficherEtatEnregistre = MethodType(Module.Dialog._AfficherEtatEnregistre, self)
        self._RestaurerEtatDurable = MethodType(Module.Dialog._RestaurerEtatDurable, self)
        self._ConfirmerEtatDurable = MethodType(Module.Dialog._ConfirmerEtatDurable, self)
        self._ReservationsBloquees = MethodType(Module.Dialog._ReservationsBloquees, self)
        self._SignalerReconciliation = MethodType(Module.Dialog._SignalerReconciliation, self)
        self._FinaliserTraitementEnAttente = MethodType(Module.Dialog._FinaliserTraitementEnAttente, self)
        self.Traitement = MethodType(Module.Dialog.Traitement, self)
        self.OnClose = MethodType(Module.Dialog.OnClose, self)
        self.OnBoutonFermer = MethodType(Module.Dialog.OnBoutonFermer, self)
        self.OnNavigation = MethodType(Module.Dialog.OnNavigation, self)
        self._diag_ui = None


class SourceTests(unittest.TestCase):
    def test_track_modifie_uniquement_apres_retour_succes_sql(self):
        source = SOURCE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        dialog = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Dialog")
        methodes = {n.name: ast.get_source_segment(source, n)
                    for n in dialog.body if isinstance(n, ast.FunctionDef)}
        sauvegarde = methodes["Sauvegarde"]
        self.assertIn("if not succes:", sauvegarde)
        self.assertLess(sauvegarde.index("self.EnregistrerDemande"),
                        sauvegarde.index("self._ConfirmerEtatDurable"))
        self.assertIn("self._RestaurerEtatDurable()", sauvegarde)
        traitement = methodes["Traitement"]
        self.assertIn("self._finalisation_en_attente", traitement)
        self.assertIn("self._FinaliserTraitementEnAttente()", traitement)
        self.assertLess(traitement.index("self._FinaliserTraitementEnAttente()"),
                        traitement.index("traitement.Traiter()"))


@unittest.skipIf(Module is None, "wxPython requis pour charger le vrai module de dialogue")
class SauvegardeEchecTests(unittest.TestCase):
    def setUp(self):
        self.base = BaseTest()
        self.addCleanup(self.base.fermer)
        self.base.db.CreationTable("portail_actions", dicoDB=Tables.DB_DATA)
        self.base.inserer("portail_actions",
                          ["IDaction", "IDfamille", "etat", "reponse"],
                          [(7, 3, "attente", None), (8, 3, "attente", None)])
        self.redirection = RedirectionGestionDB(self.base.chemin)
        self.redirection.__enter__()
        self.addCleanup(self.redirection.__exit__, None, None, None)
        self.echec_sql = False
        vraie_classe = GestionDB.DB
        fixture = self
        def db_interceptee(*args, **kwargs):
            db = vraie_classe(*args, **kwargs)
            db.cursor = ErreurCurseur(db.cursor, fixture)
            return db
        patch = mock.patch.object(GestionDB, "DB", side_effect=db_interceptee)
        patch.start()
        self.addCleanup(patch.stop)
        self.ui = DialogueFictif()
        patch_dlg = mock.patch.object(Module.wx, "MessageDialog")
        self.dlg = patch_dlg.start()
        self.addCleanup(patch_dlg.stop)
        self.dlg.return_value.ShowModal.return_value = None
        patch_persistance = mock.patch.object(Module.UTILS_Dialogs, "SaveSizePerso")
        patch_persistance.start()
        self.addCleanup(patch_persistance.stop)

    def etat_sql(self, id_action=7):
        self.base.db.ExecuterReq(
            "SELECT etat, reponse, traitement_date FROM portail_actions WHERE IDaction=%d"
            % id_action)
        return self.base.db.ResultatReq()[0]

    def test_contre_epreuve_sql_refuse_garde_etat_memoire_et_widgets(self):
        self.ui.radio_validation.SetValue(True)
        self.ui.ctrl_reponse.ChangeValue("Confirmation provisoire")
        self.ui.ctrl_date_validation.SetDate(datetime.date(2026, 10, 26))
        self.echec_sql = True
        self.assertFalse(self.ui.Sauvegarde())
        self.assertEqual(self.etat_sql(), ("attente", None, None))
        self.assertEqual(self.ui.track.etat, self.etat_sql()[0])
        self.assertEqual(self.ui.track.reponse, self.etat_sql()[1])
        self.assertEqual(self.ui.track.traitement_date, self.etat_sql()[2])
        self.assertFalse(self.ui.radio_validation.GetValue())
        self.assertTrue(self.ui.radio_attente.GetValue())
        self.assertEqual(self.ui.ctrl_reponse.GetValue(), "")
        self.ui.track.Refresh.assert_not_called()
        self.dlg.return_value.ShowModal.assert_called_once()

    def test_sauvegarde_normale_commite_avant_refresh_track(self):
        self.ui.radio_validation.SetValue(True)
        self.ui.ctrl_reponse.ChangeValue("Reponse fictive")
        etats_vus = []
        origine = self.ui.track.Refresh
        def notifier():
            etats_vus.append(self.etat_sql()[0])
        self.ui.track.Refresh.side_effect = notifier
        self.assertTrue(self.ui.Sauvegarde())
        self.assertEqual(self.etat_sql()[:2], ("validation", "Reponse fictive"))
        self.assertEqual(etats_vus, ["validation"])
        self.assertTrue(self.ui.radio_validation.GetValue())
        self.assertEqual(self.ui.track.etat, "validation")

    def test_apres_reservation_enregistree_seule_la_finalisation_est_reessayee(self):
        self.echec_sql = True
        compteur = []
        def simulation_traitement(**kw):
            class Metier:
                def Traiter(self):
                    compteur.append("sauvegarde_grille_fictive")
                    return {"etat": True, "reponse": "Confirmation fixe"}
            return Metier()
        with mock.patch.object(Module, "Traitement", side_effect=simulation_traitement):
            self.assertFalse(self.ui.Traitement(mode="automatique"))
            self.assertEqual(compteur, ["sauvegarde_grille_fictive"])
            self.assertEqual(self.etat_sql(), ("attente", None, None))
            self.assertEqual(self.ui.track.etat, "attente")
            self.assertEqual(self.ui.ctrl_reponse.GetValue(), "")
            self.assertEqual(self.ui._finalisation_en_attente["IDaction"], 7)
            # La saisie est alteree apres l'echec, mais la reponse du traitement
            # est figee : elle ne doit pas etre remplacee par le texte modifie.
            self.ui.radio_validation.SetValue(True)
            self.ui.ctrl_reponse.ChangeValue("Texte non fiable")
            self.echec_sql = False
            self.assertTrue(self.ui.Traitement(mode="manuel"))
        self.assertEqual(compteur, ["sauvegarde_grille_fictive"])
        self.assertEqual(self.etat_sql()[:2], ("validation", "Confirmation fixe"))
        self.assertEqual(self.ui.track.etat, "validation")
        self.assertEqual(self.ui.track.reponse, "Confirmation fixe")
        self.assertEqual(self.ui.ctrl_reponse.GetValue(), "Confirmation fixe")
        self.assertIsNone(self.ui._finalisation_en_attente)
        self.assertFalse(self.ui._traitement_en_cours)
        self.assertEqual(self.ui.track.Refresh.call_count, 1)

    def test_fermeture_et_navigation_interdites_pendant_echec_sql(self):
        self.echec_sql = True
        compteur = []
        def simulation(**kw):
            class Metier:
                def Traiter(self):
                    compteur.append(1)
                    return {"etat": True, "reponse": "Reserve"}
            return Metier()
        with mock.patch.object(Module, "Traitement", side_effect=simulation):
            self.assertFalse(self.ui.Traitement())
            event = mock.Mock()
            event.CanVeto.return_value = True
            self.ui.OnClose(event)
            event.Veto.assert_called_once()
            event.Skip.assert_not_called()
            self.ui.OnBoutonFermer(None)
            self.ui.EndModal.assert_not_called()
            nav = mock.Mock()
            nav.GetId.return_value = 30
            self.assertFalse(self.ui.OnNavigation(nav))
            self.assertEqual(self.ui.track.IDaction, 7)
            self.assertEqual(compteur, [1])
            self.assertEqual(self.etat_sql(), ("attente", None, None))

    def test_suivi_emails_rc9_conserve_apres_rollback_et_finalisation(self):
        Suivis.Enregistrer("portail_action_7_reponse", ["a@example.test"])
        self.ui.radio_validation.SetValue(True)
        self.ui.ctrl_reponse.ChangeValue("Reponse en attente")
        self.echec_sql = True
        self.assertFalse(self.ui.Sauvegarde())
        self.assertEqual(Suivis.Lire("portail_action_7_reponse"), {"a@example.test"})
        self.echec_sql = False
        self.assertTrue(self.ui.Sauvegarde())
        # La finalisation complete est effectuee dans la meme transaction
        # que la validation, sans interrompre ni rejouer les emails.
        self.assertEqual(self.etat_sql()[0], "attente")
        self.assertEqual(Suivis.Lire("portail_action_7_reponse"), {"a@example.test"})

    def test_reprise_si_sql_reste_indisponible_puis_revient(self):
        self.echec_sql = True
        traitement_calls = []
        def scenario(**kwargs):
            class Metier:
                def Traiter(self):
                    traitement_calls.append("consommations_appliquees")
                    return {"etat": True, "reponse": "Accord sous reserve"}
            return Metier()
        with mock.patch.object(Module, "Traitement", side_effect=scenario):
            self.assertFalse(self.ui.Traitement())
            self.assertFalse(self.ui.Traitement())  # SQL toujours indisponible
            self.assertEqual(traitement_calls, ["consommations_appliquees"])
            self.assertFalse(self.ui._finalisation_en_cours)
            self.assertEqual(self.etat_sql()[0], "attente")
            self.echec_sql = False
            self.assertTrue(self.ui.Traitement())
        self.assertEqual(traitement_calls, ["consommations_appliquees"])
        self.assertEqual(self.etat_sql()[:2], ("validation", "Accord sous reserve"))
        self.assertEqual(self.ui.track.etat, "validation")
        self.assertIsNone(self.ui._finalisation_en_attente)

    def test_finalisation_refusee_preserve_confirmations_complete_et_partielle(self):
        complete = "portail_action_7_reponse"
        partielle = "portail_action_7_recu"
        Suivis.Enregistrer(complete, Suivis.Suivi(["a@example.test"], [], None, True))
        Suivis.Enregistrer(partielle, Suivis.Suivi(["b@example.test"], [], None, False))
        self.echec_sql = True
        def scenario(**kwargs):
            class Metier:
                def Traiter(self):
                    return {"etat": True, "reponse": "Reservations appliquees"}
            return Metier()
        with mock.patch.object(Module, "Traitement", side_effect=scenario):
            self.assertFalse(self.ui.Traitement())
            self.assertEqual(self.etat_sql()[0], "attente")
            self.assertTrue(Suivis.LireSuivi(complete).complet)
            self.assertFalse(Suivis.LireSuivi(partielle).complet)
            self.echec_sql = False
            self.assertTrue(self.ui.Traitement())
        self.assertEqual(self.etat_sql()[0], "validation")
        self.assertEqual(Suivis.Lire(complete), set())
        self.assertEqual(Suivis.Lire(partielle), {"b@example.test"})

    def test_editions_simples_peuvent_etre_abandonnees_apres_rollback(self):
        self.ui.radio_validation.SetValue(True)
        self.ui.ctrl_reponse.ChangeValue("Texte non persiste")
        self.echec_sql = True
        event = mock.Mock()
        event.CanVeto.return_value = True
        self.ui.OnClose(event)
        event.Skip.assert_called_once()
        event.Veto.assert_not_called()
        self.assertEqual(self.etat_sql(), ("attente", None, None))
        self.assertEqual(self.ui.ctrl_reponse.GetValue(), "")
        self.assertIsNone(self.ui._finalisation_en_attente)

    def test_actions_reentrantes_refusees_durant_traitement_en_cours(self):
        self.ui._traitement_en_cours = True
        event = mock.Mock()
        event.CanVeto.return_value = True
        self.ui.OnClose(event)
        event.Veto.assert_called_once()
        self.ui.OnBoutonFermer(None)
        self.ui.EndModal.assert_not_called()
        nav = mock.Mock()
        self.assertFalse(self.ui.OnNavigation(nav))
        self.assertFalse(self.ui.Sauvegarde())
        self.assertEqual(self.etat_sql(), ("attente", None, None))
        self.dlg.assert_not_called()

    def test_succes_de_fermeture_et_navigation(self):
        evenement = mock.Mock()
        evenement.GetId.return_value = 30
        self.ui.OnNavigation(evenement)
        self.assertEqual(self.ui.track.IDaction, 8)
        self.ui.track = self.ui.tracks[0]
        self.ui.OnBoutonFermer(None)
        self.ui.EndModal.assert_called_once_with(Module.wx.ID_CANCEL)
        close = mock.Mock()
        self.ui.OnClose(close)
        close.Skip.assert_called_once()


if __name__ == "__main__":
    unittest.main()
