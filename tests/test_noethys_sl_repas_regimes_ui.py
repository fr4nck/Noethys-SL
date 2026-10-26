# -*- coding: utf-8 -*-
"""Lot 2A #430 : raccordement des regimes a la commande wx (donnees fictives).

Aucune fenetre n'est affichee : grille et page de parametrage sont creees
dans un cadre jamais montre, base remplacee par SQLite en memoire ou par
des donnees construites ici.
"""
import sqlite3
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
from Utils import UTILS_Repas_regimes as R  # noqa: E402
from Utils import UTILS_Repas_source  # noqa: E402
from Utils import UTILS_Repas_validation as V  # noqa: E402

try:
    import wx  # seule absence toleree : wxPython lui-meme
except ImportError:
    wx = None

JOUR = date(2026, 11, 4)
CHOIX = {"standard": 11, "sans_porc": 12, "vegetarien": 13}


def colonne(ID, role, site="Site A", service="midi", unites=((1, 10),), categorie="numerique_avec_suggestion", **extra):
    parametres = {"unites": [list(u) for u in unites], "role_repas": role,
                  "site_directeur": site, "service_directeur": service}
    if R.EstRoleRegime(role):
        parametres.update(question_regime=5, choix_regimes=dict(CHOIX))
    parametres.update(extra)
    return {"IDcolonne": ID, "ordre": ID, "nom_colonne": "C%d" % ID, "largeur": 60,
            "categorie": categorie, "parametres": parametres}


REGIMES = [colonne(4, "regime_standard"), colonne(5, "regime_sans_porc"),
           colonne(6, "regime_vegetarien"), colonne(7, "regime_non_renseigne")]


class RaccordementPurTests(unittest.TestCase):
    def test_une_seule_lecture_pour_les_quatre_colonnes(self):
        groupes, erreurs = R.GroupesColonnesRegimes(
            [colonne(1, "six_plus")] + REGIMES + [colonne(8, "regime_standard", service="soir", unites=((1, 20),))])
        self.assertEqual(erreurs, {})
        self.assertEqual(len(groupes), 1)
        self.assertEqual(groupes[0]["colonnes"], [4, 5, 6, 7, 8])
        self.assertEqual(groupes[0]["services"], {(1, 10): ("Site A", "midi"), (1, 20): ("Site A", "soir")})

    def test_parametrage_invalide_ou_unite_ambigue(self):
        mauvais = colonne(9, "regime_standard")
        mauvais["parametres"]["choix_regimes"] = {"standard": 11, "sans_porc": 12}
        sans_site = colonne(10, "regime_vegetarien", site=" ")
        groupes, erreurs = R.GroupesColonnesRegimes([mauvais, sans_site])
        self.assertEqual((groupes, sorted(erreurs)), ([], [9, 10]))
        groupes, erreurs = R.GroupesColonnesRegimes([colonne(4, "regime_standard"),
                                                      colonne(5, "regime_sans_porc", service="soir")])
        self.assertEqual(groupes, [])
        self.assertIn("deux sites/services", erreurs[4])

    def test_suggestion_et_alertes(self):
        cle = (JOUR, "Site A", "midi")
        entree = {"standard": 3, "sans_porc": 1, "vegetarien": 0, "non_renseignes": 2, "total_repas": 6,
                  "adultes_avec_conso": 1, "ages_inconnus": 0, "multisites": 1, "complet": True}
        valeur, alertes = R.SuggestionColonne("regime_sans_porc", {cle: entree}, cle)
        self.assertEqual(valeur, 1)
        self.assertEqual(len(alertes), 3)  # adulte, multisite, non renseigne
        self.assertEqual(R.SuggestionColonne("regime_non_renseigne", {cle: entree}, cle)[0], 2)
        self.assertEqual(R.SuggestionColonne("regime_standard", {}, cle), (0, []))
        incomplet = dict(entree, ages_inconnus=2, complet=False)
        valeur, alertes = R.SuggestionColonne("regime_standard", {cle: incomplet}, cle)
        self.assertIsNone(valeur)
        self.assertIn(u"Répartition incomplète : 2 âge(s) manquant(s)", alertes)
        self.assertEqual(R.SuggestionColonne("regime_standard", {cle: entree}, cle, "inconnue")[0], None)


class Case:
    def __init__(self, valeur):
        self.valeur = valeur

    def GetValeur(self):
        return self.valeur

    def SetValeur(self, valeur):
        self.valeur = valeur


def donnees(valeurs, colonnes):
    return {"liste_colonnes": colonnes, "liste_dates": [JOUR, "Total"],
            "cases": dict(((0, i), Case(v)) for i, v in enumerate(valeurs))}


class ControleEmissionTests(unittest.TestCase):
    COLONNES = [colonne(1, "moins_6"), colonne(2, "six_plus"), colonne(3, "animateurs")] + REGIMES

    def test_42_8_5_0_egal_55_accepte(self):
        lignes = V.ConstruireControle(donnees([18, 32, 5, 42, 8, 5, 0], self.COLONNES))
        self.assertEqual(lignes[0]["totaux"]["total_repas"], 55)
        self.assertEqual(lignes[0]["regimes"], {"standard": 42, "sans_porc": 8, "vegetarien": 5, "non_renseignes": 0})
        self.assertEqual(lignes[0]["colonnes_non_classees"], ())
        self.assertEqual(V.ErreursRegimes(lignes), [])
        self.assertEqual(V.ResumerControle(lignes)[0]["regimes"]["vegetarien"], 5)

    def test_repartition_ne_couvrant_pas_le_total_refusee(self):
        # Adultes non classes : 50 repartis pour 55 commandes.
        lignes = V.ConstruireControle(donnees([18, 32, 5, 40, 7, 3, 0], self.COLONNES))
        self.assertEqual(V.ErreursRegimes(lignes), ["04/11/2026 Site A midi : 50 repas repartis pour 55 repas commandes"])
        incomplet = V.ConstruireControle(donnees([18, 32, 5, 42, 8], self.COLONNES[:5]))
        self.assertIn("colonnes de regime manquantes (vegetarien, non_renseignes)", V.ErreursRegimes(incomplet)[0])

    def test_regimes_jamais_dans_les_totaux_ni_reecrits(self):
        cases_donnees = donnees([18, 32, 5, 42, 8, 5, 0], self.COLONNES)
        lignes = V.ConstruireControle(cases_donnees)
        self.assertEqual(lignes[0]["totaux"]["repas_6_et_plus"], 37)
        lignes[0]["valeurs"]["enfants_6_et_plus"] = 31
        V.AppliquerControle(lignes)
        cases = cases_donnees["cases"]
        self.assertEqual((cases[(0, 1)].valeur, cases[(0, 3)].valeur), (31, 42))
        self.assertTrue(V.ErreursRegimes(lignes))  # correction d'effectif sans reprise des regimes

    def test_erreur_de_parametrage_bloque_l_emission(self):
        d = donnees([18, 32, 5, 42, 8, 5, 0], self.COLONNES)
        d["erreurs_regimes"] = {4: "Reponses alimentaires a corriger : 1 inconnue(s), 0 contradictoire(s)"}
        with self.assertRaises(ValueError):
            V.ConstruireControle(d)

    def test_ancien_modele_sans_porc_inchange(self):
        colonnes = [colonne(1, "moins_6"), colonne(2, "six_plus"), colonne(3, "sans_porc")]
        lignes = V.ConstruireControle(donnees([18, 32, 7], colonnes))
        self.assertEqual(lignes[0]["regimes"], {})
        self.assertEqual(lignes[0]["totaux"]["sans_porc"], 7)
        self.assertEqual(V.ErreursRegimes(lignes), [])
        self.assertEqual(V.ROLES, ("moins_6", "six_plus", "animateurs", "direction", "autres_adultes", "sans_porc"))


class BaseFictive:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.results, self.closed = [], False
        self.db.executescript("""
            CREATE TABLE questionnaire_categories (IDcategorie INTEGER PRIMARY KEY, ordre INTEGER, type TEXT);
            CREATE TABLE questionnaire_questions (IDquestion INTEGER PRIMARY KEY, IDcategorie INTEGER,
                                                 ordre INTEGER, label TEXT, controle TEXT);
            CREATE TABLE questionnaire_choix (IDchoix INTEGER PRIMARY KEY, IDquestion INTEGER, ordre INTEGER, label TEXT);
            INSERT INTO questionnaire_categories VALUES (1, 1, 'individu'), (2, 2, 'famille');
            INSERT INTO questionnaire_questions VALUES (5, 1, 1, 'Régime repas', 'liste_deroulante'),
                (6, 1, 2, 'Allergies', 'liste_coches'), (7, 2, 1, 'Régime famille', 'liste_deroulante');
            INSERT INTO questionnaire_choix VALUES (13, 5, 3, 'Végétarien'), (11, 5, 1, 'Standard'),
                (12, 5, 2, 'Sans porc'), (21, 7, 1, 'Autre');
        """)

    def ExecuterReq(self, req):
        self.results = self.db.execute(req).fetchall()
        return True

    def ResultatReq(self):
        return self.results

    def Close(self):
        self.closed = True


class SourceParametrageTests(unittest.TestCase):
    def setUp(self):
        self.base = BaseFictive()
        self.addCleanup(self.base.db.close)
        patcher = patch.object(UTILS_Repas_source.GestionDB, "DB", return_value=self.base)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_questions_et_choix_lisibles(self):
        self.assertEqual(UTILS_Repas_source.ListerQuestionsRegime(), [(5, u"Régime repas")])
        self.assertEqual(UTILS_Repas_source.ListerChoixQuestion(5),
                         [(11, u"Standard"), (12, u"Sans porc"), (13, u"Végétarien")])
        self.assertTrue(self.base.closed)

    def test_verification_du_parametrage(self):
        self.assertEqual(UTILS_Repas_source.VerifierParametrageRegimes(5, CHOIX), (5, CHOIX))
        invalides = [(99, CHOIX), (6, CHOIX), (7, {"standard": 21, "sans_porc": 12, "vegetarien": 13}),
                     (5, dict(CHOIX, vegetarien=21)), (5, dict(CHOIX, vegetarien=None)), (None, CHOIX)]
        for question, choix in invalides:
            with self.subTest(question=question, choix=choix), self.assertRaises(ValueError):
                UTILS_Repas_source.VerifierParametrageRegimes(question, choix)


@unittest.skipIf(wx is None, "wxPython absent")
class GrilleWxTests(unittest.TestCase):
    """Vraie grille CTRL_Commande_repas, jamais affichee."""

    @classmethod
    def setUpClass(cls):
        cls.app = wx.GetApp() or wx.App(False)
        from Ctrl import CTRL_Commande_repas
        cls.module = CTRL_Commande_repas

    def setUp(self):
        self.frame = wx.Frame(None)
        self.addCleanup(self.frame.Destroy)

    def construire(self, consos, reponses, naissances, valeurs=None, colonnes=None):
        colonnes = colonnes or ([colonne(1, "moins_6"), colonne(2, "six_plus"), colonne(3, "animateurs", categorie="numerique_sans_suggestion")]
                                + REGIMES + [colonne(8, "aucun", categorie="numerique_total")])
        groupes, erreurs = R.GroupesColonnesRegimes(colonnes)
        regimes, erreurs = {}, dict(erreurs)
        for groupe in groupes:
            try:
                repartition = R.RepartitionRegimes(consos, reponses, groupe["choix"], groupe["services"], naissances)
            except ValueError as exc:
                erreurs.update((ID, str(exc)) for ID in groupe["colonnes"])
                continue
            regimes.update((ID, repartition) for ID in groupe["colonnes"])
        individus = {}
        for c in consos:
            individus.setdefault((c["date"], c["IDgroupe"], c["IDunite"]), set()).add(c["IDindividu"])
        d = {"liste_colonnes": colonnes, "dict_colonnes": dict(enumerate(colonnes)),
             "liste_dates": [JOUR, "Total"], "valeurs": valeurs or {}, "dict_conso": {},
             "dict_conso_individus": individus, "dict_naissances": naissances, "dict_ouvertures": {},
             "dict_dates": {}, "dict_menus": {}, "sans_porc": {}, "erreurs_sans_porc": {},
             "regimes": regimes, "erreurs_regimes": erreurs, "infos_medicales": {}, "messages": {}}
        grille = self.module.CTRL(self.frame)
        with patch.object(self.module.CTRL, "Importation", return_value=d):
            grille.MAJ(JOUR, JOUR)
        return grille

    @staticmethod
    def scenario_55():
        consos, reponses, naissances = [], {}, {}
        for i in range(50):
            consos.append({"date": JOUR, "IDindividu": i, "IDgroupe": 1, "IDunite": 10, "etat": "reservation"})
            reponses[i] = "11" if i < 40 else ("12" if i < 47 else "13")
            naissances[i] = date(2022, 1, 1) if i % 50 < 18 else date(2017, 1, 1)
        return consos, reponses, naissances

    def case(self, grille, col):
        return grille.dictCases[(0, col)]

    def test_suggestions_correction_manuelle_et_total_55(self):
        grille = self.construire(*self.scenario_55())
        self.assertEqual([self.case(grille, c).suggestion for c in range(7)], [18, 32, None, 40, 7, 3, 0])
        self.assertEqual([self.case(grille, c).GetValeur() for c in range(8)], [0] * 8)  # rien d'impose
        grille.Importer_suggestions()
        self.case(grille, 2).SetValeur(5)  # adultes saisis
        for col, valeur in ((3, 42), (4, 8), (5, 5), (6, 0)):  # adultes classes explicitement
            self.case(grille, col).SetValeur(valeur)
        grille.CalcTotaux()
        self.assertEqual(self.case(grille, 7).GetValeur(), 55)  # regimes exclus du total additif
        lignes = V.ConstruireControle(grille.GetDonnees())
        self.assertEqual(V.ErreursRegimes(lignes), [])
        self.assertEqual(lignes[0]["regimes"], {"standard": 42, "sans_porc": 8, "vegetarien": 5, "non_renseignes": 0})

    def test_reponse_manquante_jamais_standard(self):
        consos, reponses, naissances = self.scenario_55()
        del reponses[0], reponses[1]
        grille = self.construire(consos, reponses, naissances)
        self.assertEqual((self.case(grille, 3).suggestion, self.case(grille, 6).suggestion), (38, 2))
        self.assertIn(u"2 préférence(s) non renseignée(s)", self.case(grille, 3).GetTexteToolTip())

    def test_valeur_enregistree_jamais_remplacee_par_recalcul(self):
        enregistrees = {JOUR: {4: {"IDvaleur": 1, "valeur": "39"}, 5: {"IDvaleur": 2, "valeur": "9"}}}
        grille = self.construire(*self.scenario_55(), valeurs=enregistrees)
        self.assertEqual((self.case(grille, 3).GetValeur(), self.case(grille, 3).suggestion), (39, 40))
        self.assertEqual((self.case(grille, 4).GetValeur(), self.case(grille, 4).suggestion), (9, 7))

    def test_anomalies_sans_suggestion(self):
        consos, reponses, naissances = self.scenario_55()
        naissances[0] = None
        naissances[1] = date(1990, 1, 1)
        grille = self.construire(consos, reponses, naissances)
        self.assertIsNone(self.case(grille, 3).suggestion)
        texte = self.case(grille, 3).GetTexteToolTip()
        self.assertIn(u"âge(s) manquant(s)", texte)
        self.assertIn(u"18 ans et plus", texte)
        reponses[2] = "11;12"
        grille = self.construire(consos, reponses, {**naissances, 0: date(2017, 1, 1)})
        self.assertIsNone(self.case(grille, 3).suggestion)
        self.assertIn(u"contradictoire", self.case(grille, 3).GetTexteToolTip())
        with self.assertRaises(ValueError):
            V.ConstruireControle(grille.GetDonnees())

    def test_deux_services_distincts(self):
        colonnes = [colonne(4, "regime_standard"), colonne(5, "regime_vegetarien"),
                    colonne(6, "regime_standard", service="soir", unites=((1, 20),)),
                    colonne(7, "regime_vegetarien", service="soir", unites=((1, 20),))]
        consos = [{"date": JOUR, "IDindividu": i, "IDgroupe": 1, "IDunite": u, "etat": "present"}
                  for i, u in ((1, 10), (2, 10), (1, 20))]
        grille = self.construire(consos, {1: "13", 2: "11"}, {1: date(2017, 1, 1), 2: date(2017, 1, 1)}, colonnes=colonnes)
        self.assertEqual([self.case(grille, c).suggestion for c in range(4)], [1, 1, 0, 1])


@unittest.skipIf(wx is None, "wxPython absent")
class PageParametrageWxTests(unittest.TestCase):
    """Page de colonne : questions et choix par libelle, IDs stockes."""

    @classmethod
    def setUpClass(cls):
        cls.app = wx.GetApp() or wx.App(False)
        from Dlg import DLG_Saisie_commandes_colonne
        cls.module = DLG_Saisie_commandes_colonne

    def setUp(self):
        self.frame = wx.Frame(None)
        self.addCleanup(self.frame.Destroy)
        # Arbre des unites hors sujet : sans base, il n'est pas construit.
        for valeur, retour in (("MAJ", None), ("SetCoches", None), ("GetCoches", [])):
            p = patch.object(self.module.CTRL_Unites, valeur, return_value=retour)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(self.module.UTILS_Repas_source, "ListerQuestionsRegime",
                         return_value=[(5, u"Régime repas"), (8, u"Autre question")])
        p.start()
        self.addCleanup(p.stop)
        p = patch.object(self.module.UTILS_Repas_source, "ListerChoixQuestion",
                         side_effect=lambda q: [(11, u"Standard"), (12, u"Sans porc"), (13, u"Végétarien")] if q == 5 else [])
        p.start()
        self.addCleanup(p.stop)
        self.page = self.module.PAGE_Unites(self.frame)

    def role(self, code):
        return [c for c, _l in self.page.roles_repas].index(code)

    def test_selection_par_libelle_et_stockage_des_ids(self):
        self.page.ctrl_role_repas.SetSelection(self.role("regime_vegetarien"))
        self.page.OnChoixRole()
        self.assertTrue(self.page.ctrl_question_regime.IsEnabled())
        self.assertEqual(self.page.ctrl_question_regime.GetString(1), u"Régime repas")
        self.page.ctrl_question_regime.SetSelection(1)
        self.page.OnChoixQuestionRegime()
        self.assertEqual(self.page.ctrls_choix_regime["vegetarien"].GetString(3), u"Végétarien")
        for regime, index in (("standard", 1), ("sans_porc", 2), ("vegetarien", 3)):
            self.page.ctrls_choix_regime[regime].SetSelection(index)
        parametres = self.page.GetParametres()
        self.assertEqual((parametres["question_regime"], parametres["choix_regimes"]), (5, CHOIX))
        relue = self.module.PAGE_Unites(self.frame)
        relue.SetParametres(repr(parametres))
        self.assertEqual(relue.GetParametres()["choix_regimes"], CHOIX)

    def test_correspondance_incomplete_refusee(self):
        self.page.ctrl_unites.GetCoches = lambda: [(1, 10)]
        self.page.ctrl_site_directeur.SetValue("Site A")
        self.page.ctrl_role_repas.SetSelection(self.role("regime_standard"))
        self.page.ctrl_question_regime.SetSelection(1)
        self.page.OnChoixQuestionRegime()
        self.page.ctrls_choix_regime["standard"].SetSelection(1)
        with patch.object(self.module.wx, "MessageBox") as message:
            self.assertFalse(self.page.Validation())
        message.assert_called_once()

    def test_ancien_modele_relu_sans_nouvelle_cle(self):
        ancien = {"unites": [], "repas_directeur_detache": False, "site_directeur": "Site A",
                  "service_directeur": "midi", "direction_multisite": False, "groupe_direction": "",
                  "direction_renfort": "aucun", "repas_renfort_direction": False,
                  "role_repas": "sans_porc", "question_sans_porc": 5, "choix_sans_porc": 12}
        self.page.ctrl_unites.GetCoches = lambda: []
        self.page.SetParametres(repr(ancien))
        self.assertEqual(self.page.GetParametres(), ancien)
        self.assertFalse(self.page.ctrl_question_regime.IsEnabled())

    def test_question_ancienne_introuvable_conservee_et_signalee(self):
        self.page.SetParametres({"role_repas": "regime_standard", "question_regime": 77,
                                 "choix_regimes": {"standard": 1, "sans_porc": 2, "vegetarien": 3}})
        self.assertIn(u"introuvable", self.page.ctrl_question_regime.GetStringSelection())
        self.assertEqual(self.page.GetParametres()["question_regime"], 77)
        self.assertEqual(self.page.GetParametres()["choix_regimes"], {"standard": 1, "sans_porc": 2, "vegetarien": 3})


if __name__ == "__main__":
    unittest.main()
