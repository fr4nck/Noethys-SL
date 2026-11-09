# -*- coding: utf-8 -*-
"""Situation du jour dans Connecthys : SQLite fictif, aucune donnee reelle."""
import datetime
import unittest
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for rep in (ROOT / "noethys", ROOT / "tests"):
    if str(rep) not in sys.path:
        sys.path.insert(0, str(rep))

import _garde_reseau  # noqa: E402,F401 - interdit les connexions de prod
from _fixtures_noethys_db import BaseTest, RedirectionGestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402
from Utils import UTILS_Portail_situation as S  # noqa: E402

JOUR = datetime.date(2026, 11, 9)


class SituationConnecthysTests(unittest.TestCase):
    def setUp(self):
        self.base = BaseTest()
        self.addCleanup(self.base.fermer)
        for table in ("comptes_payeurs", "reglements", "factures",
                      "factures_prefixes", "ventilation", "types_cotisations",
                      "cotisations", "unites_cotisations"):
            if not self.base.db.IsTableExists(table):
                self.base.db.CreationTable(table, dicoDB=Tables.DB_DATA)
        self.base.db.Commit()
        self.base.inserer("familles", ["IDfamille"], [(3,), (4,)])
        self.base.inserer("comptes_payeurs", ["IDcompte_payeur", "IDfamille"],
                          [(30, 3), (40, 4)])
        self.base.inserer("individus", ["IDindividu", "nom", "prenom", "IDcivilite"],
                          [(77, "FICTIF", "Enfant", 1), (78, "AUTRE", "Enfant", 1),
                           (900, "STRUCTURE FICTIVE", "", 7),
                           (901, "STRUCTURE AMBIGUE", "", 7)])
        self.base.inserer("rattachements",
                          ["IDrattachement", "IDfamille", "IDindividu",
                           "IDcategorie", "titulaire"],
                          [(1, 3, 77, 2, 0), (2, 3, 78, 2, 0)])
        self.base.inserer(
            "types_cotisations",
            ["IDtype_cotisation", "nom", "type", "carte", "defaut"],
            [(1, "Adhésion annuelle", "individu", 0, 1),
             (2, "Adhésion familiale", "famille", 1, 0),
             (3, "Prêt de matériel", "individu", 0, 0)])
        self.base.inserer("unites_cotisations",
                           ["IDunite_cotisation", "IDtype_cotisation", "nom", "montant"],
                           [(11, 1, "Adhésion individuelle", 7.50)])
        self.redirection = RedirectionGestionDB(self.base.chemin)
        self.redirection.__enter__()
        self.addCleanup(self.redirection.__exit__, None, None, None)

    def lire(self, enfant=77, jour=JOUR, famille=3):
        return S.LireSituation(famille, enfant, jour)

    def test_solde_du_jour_ne_compte_pas_prestations_ni_reglements_futurs(self):
        self.base.inserer("prestations",
            ["IDprestation", "IDfamille", "date", "montant"],
            [(101, 3, "2026-11-01", 40.00),
             (102, 3, "2026-11-19", 20.00),
             (103, 4, "2026-11-01", 100.00)])
        self.base.inserer("reglements",
            ["IDreglement", "IDcompte_payeur", "date", "montant"],
            [(1, 30, "2026-11-01", 15.00),
             (2, 30, "2026-11-19", 25.00),
             (3, 40, "2026-11-01", 150.00)])
        self.assertEqual(self.lire()["solde_du_jour"], Decimal("-25.00"))

    def test_solde_crediteur_sans_prestation_et_inconnu_distinct_de_zero(self):
        self.base.inserer("reglements",
            ["IDreglement", "IDcompte_payeur", "date", "montant"],
            [(1, 30, "2026-11-09", 21.50)])
        self.assertEqual(self.lire()["solde_du_jour"], Decimal("21.50"))
        with self.assertRaises(S.SituationIndisponible):
            S.LireSituation(0, 77, JOUR)
        with self.assertRaises(S.SituationIndisponible):
            S.LireSituation("3 OR 1=1", 77, JOUR)

    def test_factures_non_soldees_recalculees_sur_ventilation(self):
        self.base.inserer("factures",
            ["IDfacture", "numero", "IDcompte_payeur", "date_edition",
             "date_echeance", "solde"],
            [(100, 100, 30, "2026-10-01", "2026-10-20", 0),
             (101, 101, 30, "2026-10-20", "2026-12-10", 0),
             (102, 102, 30, "2026-09-20", "2026-10-10", 99),
             (103, 103, 40, "2026-09-20", "2026-10-10", 0),
             (104, 104, 30, "2026-12-15", "2026-12-29", 90)])
        self.base.inserer("prestations",
            ["IDprestation", "IDfamille", "IDcompte_payeur",
             "IDfacture", "date", "montant"],
            [(201, 3, 30, 100, "2026-10-01", 100.00),
             (202, 3, 30, 101, "2026-10-20", 50.00),
             (203, 3, 30, 102, "2026-09-20", 30.00),
             (204, 4, 40, 103, "2026-09-20", 30.00),
             (205, 3, 30, 104, "2026-12-15", 90.00)])
        self.base.inserer("ventilation",
            ["IDventilation", "IDprestation", "IDcompte_payeur", "montant"],
            [(1, 201, 30, 25.00), (2, 203, 30, 30.00),
             (3, 205, 30, 20.00)])
        result = self.lire()
        self.assertEqual([f["IDfacture"] for f in result["factures_impayees"]], [101, 100])
        self.assertEqual([f["reste"] for f in result["factures_impayees"]],
                         [Decimal("50.00"), Decimal("75.00")])
        self.assertEqual(result["total_factures"], Decimal("125.00"))
        self.assertIn("n°100", S.FormaterSituationHtml(result))
        self.assertIn("échue", S.FormaterSituationHtml(result))
        self.assertNotIn("n°102", S.FormaterSituationHtml(result))

    def test_avoir_non_ventile_n_annule_pas_facture(self):
        self.base.inserer("factures",
            ["IDfacture", "numero", "IDcompte_payeur", "date_edition"],
            [(1, 900, 30, "2026-10-01")])
        self.base.inserer("prestations",
            ["IDprestation", "IDfamille", "IDfacture", "montant", "date"],
            [(2, 3, 1, 80, "2026-10-01")])
        self.base.inserer("reglements",
            ["IDreglement", "IDcompte_payeur", "montant", "date"],
            [(1, 30, 100, "2026-10-01")])
        result = self.lire()
        self.assertEqual(result["solde_du_jour"], Decimal("20.00"))
        self.assertEqual(result["total_factures"], Decimal("80.00"))

    def test_adhesion_individuelle_limites_inclusives_et_expiration(self):
        self.base.inserer("cotisations",
            ["IDcotisation", "IDindividu", "IDtype_cotisation",
             "IDunite_cotisation", "date_debut", "date_fin"],
            [(11, 77, 1, 11, "2025-11-09", "2026-11-09")])
        self.assertEqual(self.lire()["adhesion"]["statut"], "en_cours")
        self.assertEqual(self.lire()["adhesion"]["montant"], Decimal("7.50"))
        self.assertEqual(self.lire(jour=JOUR + datetime.timedelta(days=1))
                         ["adhesion"]["statut"], "expiree")
        self.assertEqual(self.lire(enfant=78)["adhesion"]["statut"], "absente")

    def test_adhesion_familiale_couvre_l_enfant(self):
        self.base.inserer("cotisations",
            ["IDcotisation", "IDfamille", "IDtype_cotisation",
             "date_debut", "date_fin"],
            [(21, 3, 2, "2026-01-01", "2027-01-01")])
        resultat = self.lire()
        self.assertEqual(resultat["adhesion"]["statut"], "en_cours")
        self.assertEqual(resultat["adhesion"]["portee"], "famille")

    def test_personne_morale_titulaire_et_ambiguite(self):
        self.base.inserer("rattachements",
                          ["IDrattachement", "IDfamille", "IDindividu",
                           "IDcategorie", "titulaire"],
                          [(3, 3, 900, 1, 1)])
        self.base.inserer("cotisations",
            ["IDcotisation", "IDindividu", "IDtype_cotisation",
             "date_debut", "date_fin"],
            [(22, 900, 1, "2026-01-01", "2027-01-01")])
        resultat = self.lire()
        self.assertEqual(resultat["adhesion"]["portee"], "structure")
        self.assertEqual(resultat["adhesion"]["statut"], "en_cours")
        self.base.inserer("rattachements",
                          ["IDrattachement", "IDfamille", "IDindividu",
                           "IDcategorie", "titulaire"],
                          [(4, 3, 901, 1, 1)])
        self.assertEqual(self.lire()["adhesion"]["statut"], "a_verifier")

    def test_cotisation_autre_ne_devient_pas_fausse_adhesion(self):
        self.base.inserer("cotisations",
            ["IDcotisation", "IDindividu", "IDtype_cotisation",
             "date_debut", "date_fin"],
            [(22, 77, 3, "2026-01-01", "2027-01-01")])
        self.assertEqual(self.lire()["adhesion"]["statut"], "a_verifier")
        self.assertIn("Prêt de matériel",
                      S.FormaterSituationHtml(self.lire()))

    def test_html_echappe_les_donnees_de_facture_et_d_adhesion(self):
        rendu = S.FormaterSituationHtml({
            "date": JOUR, "solde_du_jour": Decimal("-10.00"),
            "factures_impayees": [{
                "IDfacture": 5, "numero": "5", "prefixe": "<script>",
                "reste": Decimal("10.00"), "echeance": None}],
            "total_factures": Decimal("10.00"),
            "adhesion": {"statut": "en_cours", "nom": "<img src=x>",
                          "portee": "enfant", "fin": JOUR},
        })
        self.assertNotIn("<script>", rendu)
        self.assertNotIn("<img src=x>", rendu)
        self.assertIn("&lt;img src=x&gt;", rendu)

    def test_raccordement_lecture_seule_de_la_fenetre_connecthys(self):
        import ast
        source = (ROOT / "noethys" / "Dlg" /
                  "DLG_Saisie_portail_demande.py").read_text(encoding="utf-8")
        arbre = ast.parse(source)
        dialogue = next(x for x in arbre.body
                        if isinstance(x, ast.ClassDef) and x.name == "Dialog")
        methodes = {
            n.name: ast.get_source_segment(source, n)
            for n in dialogue.body if isinstance(n, ast.FunctionDef)
        }
        self.assertIn("self.MAJ_situation()", methodes["MAJ_informations"])
        self.assertIn("UTILS_Portail_situation.LireSituation(", methodes["MAJ_situation"])
        self.assertIn("self.situation_factures_table.InsertItem(", methodes["MAJ_situation"])
        self.assertIn("self.situation_adhesion_statut.SetLabel(", methodes["MAJ_situation"])
        self.assertIn("self.panel_situation.Show(True)", methodes["MAJ_situation"])
        self.assertIn("self.situation_solde_jour.SetLabel(", methodes["MAJ_situation"])
        # Non-redondance : le solde rouge historique ne figure plus sur la
        # ligne Famille. Le controle cache reste requis pour le mail.
        self.assertIn("self.ctrl_solde.Hide()", methodes["__init__"])
        self.assertNotIn("self.label_solde", methodes["__init__"])
        self.assertNotIn("self.label_solde", methodes["__do_layout"])
        self.assertNotIn("grid_sizer_famille.Add(self.ctrl_solde",
                         methodes["__do_layout"])
        self.assertIn("rows=1, cols=2", methodes["__do_layout"])
        self.assertIn("self.ctrl_solde.GetSolde()", methodes["MAJ_situation"])
        self.assertIn('dict_champs["{SOLDE_FAMILLE}"] = self.ctrl_solde.GetSolde()',
                      methodes["Envoyer"] if "Envoyer" in methodes else source)
        self.assertIn("self.situation_factures_carte", methodes["_ConstruireSituationFamille"])
        self.assertIn("self.situation_solde_carte", methodes["_ConstruireSituationFamille"])
        self.assertIn("self.situation_adhesion_carte", methodes["_ConstruireSituationFamille"])
        self.assertIn("grid_sizer_contenu.Add(self.panel_situation",
                      methodes["__do_layout"])
        self.assertIn("wx.BoxSizer(wx.HORIZONTAL)",
                      methodes["_ConstruireSituationFamille"])
        self.assertIn('_(u"N° facture")', methodes["_ConstruireSituationFamille"])
        self.assertIn('_(u"Restant dû")', methodes["_ConstruireSituationFamille"])
        self.assertIn("self.panel_situation.Show(False)", methodes["MAJ_situation"])
        self.assertIn("Situation du jour indisponible", methodes["MAJ_situation"])
        self.assertNotIn("INSERT", methodes["MAJ_situation"])
        self.assertNotIn("UPDATE", methodes["MAJ_situation"])

    def test_erreur_de_lecture_n_est_pas_interpretee_comme_absence(self):
        self.base.db.ExecuterReq("DROP TABLE factures_prefixes")
        self.base.db.Commit()
        with self.assertRaises(S.SituationIndisponible):
            self.lire()


if __name__ == "__main__":
    unittest.main()
