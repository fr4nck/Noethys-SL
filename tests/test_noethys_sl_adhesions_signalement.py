# -*- coding: utf-8 -*-
"""Adhésions automatiques : signalement des situations « à vérifier » et
limite d'une adhésion à venir sur plusieurs sauvegardes successives.

Base SQLite temporaire uniquement (RedirectionGestionDB), sans donnée réelle.
"""

import datetime
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"
if str(NOETHYS) not in sys.path:
    sys.path.insert(0, str(NOETHYS))

from test_noethys_sl_adhesions import Env  # noqa: E402
from Utils import UTILS_Adhesions as A  # noqa: E402

D = datetime.date
JOUR = D(2026, 10, 1)


class MessagesTests(unittest.TestCase):

    def test_chevauchement_indique_personne_periodes_et_motif(self):
        with Env() as e:
            e.conso(100, D(2026, 10, 14))
            A.ReconcilierSansEchec([100], date_reference=JOUR, depuis=D(2026, 10, 14))
            e.conso(100, D(2026, 10, 7))
            resultats = A.ReconcilierSansEchec([100], date_reference=JOUR, depuis=D(2026, 10, 7))
            messages = A.MessagesAVerifier(resultats)
        self.assertEqual(len(messages), 1)
        self.assertIn(u"DUPUIS Jean", messages[0])
        self.assertIn(u"du 07/10/2026 au 07/10/2027 non créée", messages[0])
        self.assertIn(u"chevaucherait l'adhésion déjà enregistrée du 14/10/2026 au 14/10/2027", messages[0])

    def test_payeur_indeterminable_signale(self):
        with Env() as e:
            e.conso(300, D(2026, 10, 7), payeur=None)  # rattaché à deux familles
            messages = A.MessagesAVerifier(A.ReconcilierSansEchec([300], date_reference=JOUR, depuis=D(2026, 10, 7)))
        self.assertEqual(len(messages), 1)
        self.assertIn(u"MARTIN Alice", messages[0])
        self.assertIn(u"le payeur ne peut pas être déterminé", messages[0])

    def test_creation_normale_et_attente_ne_sont_pas_signalees(self):
        with Env() as e:
            e.conso(100, D(2026, 10, 7))
            e.conso(100, D(2027, 10, 20))  # bloquée par la limite d'une adhésion à venir
            resultats = A.ReconcilierSansEchec([100], date_reference=JOUR, depuis=D(2026, 10, 7))
            self.assertEqual(resultats[100]["motif"], "adhesion_a_venir_existante")
            self.assertEqual(A.MessagesAVerifier(resultats), [])

    def test_adhesion_automatique_sans_participation_signalee(self):
        with Env() as e:
            conso = e.conso(100, D(2026, 10, 7))
            A.ReconcilierSansEchec([100], date_reference=JOUR, depuis=D(2026, 10, 7))
            e.supprimer_conso(conso)
            messages = A.MessagesAVerifier(A.ReconcilierSansEchec([100], date_reference=JOUR, depuis=D(2026, 10, 7)))
        self.assertEqual(len(messages), 1)
        self.assertIn(u"adhésion automatique du 07/10/2026 au 07/10/2027 à vérifier", messages[0])

    def test_configuration_absente_silencieuse_ambigue_signalee_une_fois(self):
        with Env() as e:
            e.base.db.ExecuterReq("UPDATE types_cotisations SET defaut=0;")
            e.base.db.Commit()
            e.conso(100, D(2026, 10, 7))
            self.assertEqual(A.MessagesAVerifier(A.ReconcilierSansEchec([100, 200], date_reference=JOUR, depuis=JOUR)), [])
            e.base.inserer("types_cotisations", ["IDtype_cotisation", "nom", "type", "carte", "defaut"],
                           [(2, "Adhesion bis", "individu", 0, 1)])
            e.base.db.ExecuterReq("UPDATE types_cotisations SET defaut=1;")
            e.base.db.Commit()
            messages = A.MessagesAVerifier(A.ReconcilierSansEchec([100, 200], date_reference=JOUR, depuis=JOUR))
        self.assertEqual(len(messages), 1)
        self.assertIn(u"paramétrage ambigu", messages[0])

    def test_exception_n_est_plus_avalee(self):
        with mock.patch.object(A, "ReconcilierIndividus", side_effect=RuntimeError("base indisponible")):
            resultats = A.ReconcilierSansEchec([100], date_reference=JOUR)
        messages = A.MessagesAVerifier(resultats)
        self.assertEqual(len(messages), 1)
        self.assertIn(u"a échoué : base indisponible", messages[0])

    def test_journalisation_dans_l_historique_de_la_personne(self):
        with Env() as e:
            e.adhesion(100, D(2027, 1, 1), D(2028, 1, 1), observations="saisie manuelle")
            e.conso(100, D(2026, 10, 7))
            resultats = A.ReconcilierSansEchec([100], date_reference=JOUR, depuis=D(2026, 10, 7))
            self.assertEqual(A.JournaliserAVerifier(resultats, IDutilisateur=7), 1)
            lignes = e.lire("SELECT IDindividu, IDutilisateur, IDcategorie, action FROM historique;")
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0][:3], (100, 7, 21))
        self.assertIn(u"Adhésion automatique à vérifier : DUPUIS Jean", lignes[0][3])


class AdhesionsAVenirTests(unittest.TestCase):

    def test_adhesion_future_manuelle_compte_dans_la_limite(self):
        with Env() as e:
            e.adhesion(100, D(2026, 12, 1), D(2027, 12, 1), observations="saisie manuelle")
            e.conso(100, D(2028, 1, 10))
            res = A.ReconcilierIndividu(100, date_reference=JOUR, depuis=JOUR)
            self.assertEqual((res["statut"], res["motif"]), (A.STATUT_RIEN, "adhesion_a_venir_existante"))
            self.assertEqual(e.compte("cotisations"), 1)

    def test_sauvegardes_successives(self):
        with Env() as e:
            e.adhesion(100, D(2026, 12, 1), D(2027, 12, 1), observations="saisie manuelle")
            e.conso(100, D(2028, 1, 10))
            e.conso(100, D(2029, 3, 1))
            # Plusieurs sauvegardes avant le début de l'adhésion enregistrée : rien.
            for jour in (D(2026, 10, 1), D(2026, 10, 1), D(2026, 11, 15), D(2026, 11, 30)):
                A.ReconcilierIndividu(100, date_reference=jour, depuis=jour)
                self.assertEqual(e.compte("cotisations"), 1, jour)
            # L'adhésion enregistrée a commencé : une seule adhésion à venir est créée.
            for jour in (D(2026, 12, 5), D(2026, 12, 5), D(2027, 6, 1)):
                A.ReconcilierIndividu(100, date_reference=jour, depuis=jour)
                self.assertEqual(e.compte("cotisations"), 2, jour)
            self.assertEqual(e.lire("SELECT date_debut FROM cotisations ORDER BY date_debut;")[-1][0], "2028-01-10")
            self.assertEqual(e.compte("prestations", "categorie='cotisation'"), 1)
            # La suivante n'est créée qu'une fois l'adhésion de 2028 commencée.
            A.ReconcilierIndividu(100, date_reference=D(2028, 2, 1), depuis=D(2028, 2, 1))
            self.assertEqual(e.compte("cotisations"), 3)

    def test_autre_type_n_entre_pas_dans_la_limite(self):
        with Env() as e:
            e.base.inserer("types_cotisations", ["IDtype_cotisation", "nom", "type", "carte", "defaut"],
                           [(2, "Cotisation famille", "famille", 0, 0)])
            e.base.inserer("cotisations", ["IDcotisation", "IDfamille", "IDindividu", "IDtype_cotisation", "date_debut", "date_fin"],
                           [(9, 1, 100, 2, "2026-12-01", "2027-12-01")])
            e.conso(100, D(2026, 10, 7))
            self.assertEqual(A.ReconcilierIndividu(100, date_reference=JOUR, depuis=JOUR)["statut"], A.STATUT_CREE)


class GrilleTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import wx
        cls.app = wx.GetApp() or wx.App(False)
        from Ctrl import CTRL_Grille
        cls.CTRL_Grille = CTRL_Grille

    def _signaler(self, interactif):
        faux = mock.Mock(IDutilisateur=3)
        faux.signaler_adhesions_interactif = interactif
        resultats = {100: {"IDindividu": 100, "statut": A.STATUT_A_VERIFIER, "motif": "chevauchement",
                           "date_debut": D(2026, 10, 7), "date_fin": D(2027, 10, 7),
                           "chevauchements": [(1, D(2026, 10, 14), D(2027, 10, 14))], "a_verifier": []}}
        with mock.patch.object(A, "_noms_individus", return_value={100: u"DUPUIS Jean"}), \
             mock.patch.object(A, "JournaliserAVerifier", return_value=1) as journal, \
             mock.patch.object(self.CTRL_Grille.wx, "MessageDialog") as dialogue:
            self.CTRL_Grille.CTRL.SignalerAdhesionsAVerifier(faux, resultats)
        return dialogue, journal

    def test_operateur_present_fenetre_avec_le_detail(self):
        dialogue, journal = self._signaler(True)
        self.assertTrue(dialogue.return_value.ShowModal.called)
        texte = dialogue.call_args[0][1]
        self.assertIn(u"DUPUIS Jean : adhésion du 07/10/2026 au 07/10/2027 non créée", texte)
        journal.assert_not_called()

    def test_sans_operateur_trace_dans_l_historique(self):
        dialogue, journal = self._signaler(False)
        dialogue.assert_not_called()
        journal.assert_called_once()

    def test_resultat_de_la_reconciliation_transmis_au_signalement(self):
        source = (NOETHYS / "Ctrl" / "CTRL_Grille.py").read_text(encoding="utf-8")
        self.assertIn("resultats = UTILS_Adhesions.ReconcilierSansEchec(", source)
        self.assertIn("self.SignalerAdhesionsAVerifier(resultats)", source)
        badgeage = (NOETHYS / "Dlg" / "DLG_Badgeage_grille.py").read_text(encoding="utf-8")
        self.assertIn('signaler_adhesions_interactif = usage not in ("badgeage", "nomadhys")', badgeage)


if __name__ == "__main__":
    unittest.main()
