# -*- coding: utf-8 -*-
import csv
import datetime
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_noethys_sl_afas_donnees import _BaseAFASDonneesTests
from Data import DATA_Tables as Tables
from Utils import UTILS_AFAS
from Utils import UTILS_AFAS_Actualisation as AFAS
from Utils import UTILS_AFAS_Donnees


_APP = None


class ActualisationTests(_BaseAFASDonneesTests):
    def setUp(self):
        super().setUp()
        for nom in ("profils", "profils_parametres"):
            self.base.db.CreationTable(nom, dicoDB=Tables.DB_DATA)
        self.base.inserer("groupes", ["IDgroupe", "IDactivite", "nom"], [(1, 10, "Premier groupe")])
        self._commit()

    def preparer(self, manuel=None, perimetres=None):
        return AFAS.PreparerActualisation(2026, perimetres or [(10, 1)],
            {51: self._unite_reel(51, 10)}, self._options(),
            methode=UTILS_AFAS.METHODE_MANUEL if manuel is not None else UTILS_AFAS.METHODE_N1_AJUSTE,
            valeurs_manuelles=manuel)

    def test_septembre_exclut_octobre_et_estime_le_meme_trimestre_n1(self):
        for i, date, fin in ((1, "2026-09-30", "10:00"), (2, "2026-10-01", "17:00"),
                             (3, "2025-10-01", "12:00"), (4, "2025-03-01", "18:00")):
            self._inserer_conso(i, 1, 1, date, "08:00", fin)
            self._inserer_ouverture(date)
        self._inserer_ouverture("2026-12-31")
        self._commit()
        rapport = self.preparer()
        self.assertEqual(rapport["jours_realises"], 1)
        self.assertEqual(rapport["jours_previsionnels"], 2)
        self.assertEqual(rapport["historique"]["heures_reelles"], 4)
        self.assertEqual(rapport["lignes"]["heures_reelles"],
                         {"realise": 2, "prevision_restant": 8, "total_actualise": 10})
        direct = UTILS_AFAS_Donnees.GetDonneesAFAS(10, 1, 2026,
            UTILS_AFAS.PHASE_ACTUALISATION_SEPTEMBRE,
            {51: self._unite_reel(51, 10)}, {51: self._unite_facture(51, 10)}, self._options())
        self.assertEqual(direct["heures_reelles"], 2)

    def test_manuel_sans_historique_et_sous_total_non_additif(self):
        self._inserer_conso(1, 1, 1, "2026-09-30", "08:00", "10:00")
        self._inserer_aeeh(1, 1, "2026-01-01", "2026-12-31")
        self._commit()
        manuel = dict(zip([c for c, l in AFAS.METRIQUES], [10, 3, 12, 2]))
        rapport = self.preparer(manuel)
        self.assertEqual(rapport["lignes"]["heures_reelles"]["total_actualise"], 12)
        self.assertEqual(rapport["lignes"]["heures_reelles_aeeh"]["total_actualise"], 5)
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "afas.csv"
            AFAS.ExporterCSV(chemin, rapport, "Équipement Test")
            with chemin.open(encoding="utf-8-sig", newline="") as fichier:
                lignes = list(csv.reader(fichier, delimiter=";"))
            self.assertIn(["Heures réalisées", "2,00", "10,00", "12,00"], lignes)
            self.assertIn(["Équipement", "Équipement Test"], lignes)

    def test_absence_calendrier_ne_produit_pas_un_faux_zero(self):
        self._commit()
        with self.assertRaisesRegex(ValueError, "Aucun jour"):
            self.preparer()
        self._inserer_ouverture("2026-10-01")
        self._commit()
        with self.assertRaisesRegex(ValueError, "Aucun calendrier exploitable"):
            self.preparer()

    def test_saisie_invalide_et_aeeh_superieur_au_total_refuses(self):
        self._commit()
        for valeur in ("nan", "inf", "-1", "", "bonjour"):
            with self.subTest(valeur=valeur), self.assertRaises(ValueError):
                self.preparer({c: valeur for c, l in AFAS.METRIQUES})
        with self.assertRaisesRegex(ValueError, "dépasse"):
            self.preparer(dict(zip([c for c, l in AFAS.METRIQUES], [1, 2, 1, 0])))
        self.assertEqual(AFAS.NombrePositif("2,5"), 2.5)

    def test_quatre_declarations_conservent_le_cycle_annuel(self):
        for i, date in enumerate(("2026-06-30", "2026-07-01", "2026-09-30", "2026-10-01", "2026-12-31"), 1):
            self._inserer_conso(i, 1, 1, date, "08:00", "09:00")
        self._commit()
        for phase, reel, prevision in ((UTILS_AFAS.PHASE_PREVISIONNEL, 0, 10),
                                      (UTILS_AFAS.PHASE_ACTUALISATION_JUIN, 1, 10),
                                      (UTILS_AFAS.PHASE_ACTUALISATION_SEPTEMBRE, 3, 10),
                                      (UTILS_AFAS.PHASE_REEL, 5, 0)):
            with self.subTest(phase=phase):
                rapport = AFAS.PreparerActualisation(2026, [(10, 1)], {51: self._unite_reel(51, 10)},
                    self._options(), methode=UTILS_AFAS.METHODE_MANUEL,
                    valeurs_manuelles=dict(zip([c for c, l in AFAS.METRIQUES], [10, 0, 0, 0])), phase=phase)
                self.assertEqual(rapport["lignes"]["heures_reelles"]["realise"], reel)
                self.assertEqual(rapport["lignes"]["heures_reelles"]["prevision_restant"], prevision)
                self.assertEqual(rapport["lignes"]["heures_reelles"]["total_actualise"], reel + prevision)

    def test_prestation_et_jour_ne_sont_pas_doubles_entre_groupes(self):
        self.base.inserer("groupes", ["IDgroupe", "IDactivite", "nom"], [(2, 10, "Second groupe")])
        self._inserer_prestation(501, "02:00")
        self._inserer_conso(1, 1, 1, "2026-09-30", "08:00", "09:00", IDprestation=501)
        self._inserer_conso(2, 1, 1, "2026-09-30", "09:00", "10:00", IDprestation=501)
        self.base.db.ExecuterReq("UPDATE consommations SET IDgroupe=2 WHERE IDconso=2;")
        self._inserer_ouverture("2026-09-30")
        self.base.inserer("ouvertures", ["IDactivite", "IDunite", "IDgroupe", "date"], [(10, 51, 2, "2026-09-30")])
        self._commit()
        rapport = self.preparer({c: 0 for c, l in AFAS.METRIQUES}, [(10, 1), (10, 2)])
        self.assertEqual(rapport["jours_realises"], 1)
        self.assertEqual(rapport["lignes"]["heures_facturees"]["realise"], 2)
        self.assertEqual(rapport["lignes"]["heures_reelles"]["realise"], 2)

    def test_dialogue_calcule_la_selection_reelle(self):
        import wx
        from Dlg import DLG_AFAS_Actualisation
        global _APP
        _APP = wx.GetApp() or wx.App(False)
        _APP.SetAssertMode(wx.APP_ASSERT_EXCEPTION)
        self._inserer_conso(1, 1, 1, "2026-09-30", "08:00", "10:00")
        self._commit()
        dialogue = DLG_AFAS_Actualisation.Dialog(None, [10], {51: self._unite_reel(51, 10)}, self._options())
        try:
            dialogue.annee.SetValue(2026)
            dialogue.groupes.Check(0)
            dialogue.methode.SetSelection(1)
            dialogue.OnMethode(None)
            for controle in dialogue.manuels.values():
                controle.SetValue("0")
            rapport = dialogue.Calculer()
            self.assertEqual(rapport["lignes"]["heures_reelles"]["realise"], 2)
            self.assertEqual(dialogue.resultats.GetItemCount(), 4)
            self.assertEqual(dialogue.resultats.GetItemText(0, 3), "2.00")
            dialogue.equipement.SetValue("Club ados")
            configuration = dialogue.GetConfiguration()
            from Ctrl import CTRL_Profil
            self.base.inserer("profils", ["IDprofil", "label", "categorie", "defaut"], [(99, "Club ados", "afas_equipement", 0)])
            CTRL_Profil.SetParametres(IDprofil=99, dictParametres=configuration)
            recharge = CTRL_Profil.GetParametres(IDprofil=99)
            dialogue.groupes.Check(0, False)
            dialogue.unites = {}
            dialogue.SetConfiguration(recharge)
            self.assertTrue(dialogue.groupes.IsChecked(0))
            self.assertEqual(dialogue.equipement.GetValue(), "Club ados")
            self.assertEqual(dialogue.Calculer()["lignes"]["heures_reelles"]["realise"], 2)
            dialogue.phase.SetSelection(1)
            dialogue.OnPhase(None)
            self.assertEqual(dialogue.manuels["heures_reelles"].GetValue(), "")
            dialogue.phase.SetSelection(2)
            dialogue.OnPhase(None)
            self.assertEqual(dialogue.manuels["heures_reelles"].GetValue(), "0")
            dialogue.annee.SetValue(2027)
            dialogue.OnPhase(None)
            self.assertEqual(dialogue.manuels["heures_reelles"].GetValue(), "")
        finally:
            dialogue.Destroy()
