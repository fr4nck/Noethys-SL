# -*- coding: utf-8 -*-
"""Comportement réel de l'État global des consommations restauré.

La page est celle d'origine (noethys/Dlg/DLG_Etat_global.py de
https://github.com/Noethys/Noethys). Ces tests exécutent son vrai
Dialog.Apercu() sur une base SQLite fictive et lisent les tableaux du PDF
produit par reportlab : aucune base réelle, aucune fenêtre affichée.

Les valeurs attendues découlent des règles de calcul d'origine (heures
seuil/plafond, durées seuil/plafond, arrondi, coefficient, temps facturé,
formule, plafond journalier, états, jours, périodes, régimes). Aucun forfait
méridien n'est ajouté.
"""
from __future__ import annotations

import datetime
import sys
import unittest
from pathlib import Path
from unittest import mock

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
TESTS_DIR = Path(__file__).resolve().parent
for chemin in (NOETHYS_DIR, TESTS_DIR):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))

from _fixtures_noethys_db import BaseTest, RedirectionGestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402

try:
    import wx  # noqa: E402
    from Dlg import DLG_Etat_global  # noqa: E402
except (ImportError, RuntimeError) as erreur:  # pragma: no cover
    raise unittest.SkipTest("wxPython indisponible : %s" % erreur)


TABLES_SUPPLEMENTAIRES = ("vacances", "evenements", "etiquettes", "comptes_payeurs",
                          "categories_tarifs", "quotients", "tarifs_lignes")

DEBUT = datetime.date(2026, 1, 1)
FIN = datetime.date(2026, 12, 31)
MERCREDI_SCOLAIRE = "2026-03-04"
MERCREDI_FEVRIER = "2026-02-18"
MERCREDI_ETE = "2026-07-08"


class _Date:
    def __init__(self, date):
        self.date = date

    def GetDate(self):
        return self.date

    def FonctionValiderDate(self):
        return True


class _Panel:
    def __init__(self, activites):
        self.ctrl_date_debut = _Date(DEBUT)
        self.ctrl_date_fin = _Date(FIN)
        self.activites = activites

    def GetActivites(self):
        return self.activites

    def GetLabelParametres(self):
        return u"Période fictive | Activités : Accueil fictif"


class _Retour:
    def __init__(self, valeur, valide=True):
        self.valeur = valeur
        self.valide = valide

    def GetDonnees(self):
        return self.valeur

    def GetParametres(self):
        return dict(self.valeur)

    def Validation(self):
        return self.valide


class _FauxDialog:
    """ Les attributs que Dialog.Apercu() lit sur la fenêtre, sans fenêtre. """
    Apercu = DLG_Etat_global.Dialog.Apercu
    Calcule_formule = DLG_Etat_global.Dialog.Calcule_formule

    def __init__(self, unites, options):
        self.panel_parametres = _Panel([10])
        self.ctrl_parametres = _Retour(unites)
        self.ctrl_options = _Retour(options)
        # Même cache que l'original : les informations individuelles déjà
        # chargées pour cette date de début ne sont pas relues.
        self.date_debut = DEBUT
        self.date_fin = FIN
        self.dictInfosIndividus = {1: {"INDIVIDU_VILLE": "Ville A"}, 2: {"INDIVIDU_VILLE": None}}
        self.dictInfosFamilles = {}


def unite(IDunite, nom, typeCalcul=1, coeff=None, arrondi=None, duree_seuil=None,
          duree_plafond=None, heure_seuil=None, heure_plafond=None, formule=None):
    return {
        "IDunite": IDunite, "IDactivite": 10, "nomUnite": nom, "nomActivite": "Accueil fictif",
        "typeCalcul": typeCalcul, "coeff": coeff, "arrondi": arrondi,
        "duree_plafond": duree_plafond, "duree_seuil": duree_seuil,
        "heure_plafond": heure_plafond, "heure_seuil": heure_seuil, "formule": formule,
    }


def options(**valeurs):
    resultat = {
        "regroupement_principal": "aucun",
        "regroupement_age": [],
        "tranches_qf_perso": [],
        "periodes_detaillees": False,
        "format_donnees": "horaire",
        "afficher_regime_inconnu": False,
        "associer_regime_inconnu": "non",
        "plafond_journalier_individu": 0,
        "jours_hors_vacances": [0, 1, 2, 3, 4, 5, 6],
        "jours_vacances": [0, 1, 2, 3, 4, 5, 6],
        "etat_consommations": ["reservation", "present", "absentj", "absenti"],
        "orientation": "portrait",
        "couleur_ligne_age": wx.Colour(192, 192, 192),
        "couleur_ligne_total": wx.Colour(234, 234, 234),
        "couleur_case_regroupement": wx.Colour(0, 0, 0),
        "couleur_texte_regroupement": wx.Colour(255, 255, 255),
    }
    resultat.update(valeurs)
    return resultat


class EtatGlobalApercuTests(unittest.TestCase):

    def setUp(self):
        self.base = BaseTest()
        self.addCleanup(self.base.fermer)
        for nom_table in TABLES_SUPPLEMENTAIRES:
            self.base.db.CreationTable(nom_table, dicoDB=Tables.DB_DATA)
        self.base.inserer("organisateur", ["IDorganisateur", "nom"], [(1, "Organisateur fictif")])
        self.base.inserer("regimes", ["IDregime", "nom"], [(1, u"Régime général")])
        self.base.inserer("caisses", ["IDcaisse", "nom", "IDregime"], [(1, "Caisse fictive", 1)])
        self.base.inserer("familles", ["IDfamille", "IDcaisse"], [(1, 1), (2, None)])
        self.base.inserer("comptes_payeurs", ["IDcompte_payeur", "IDfamille"], [(1, 1), (2, 2)])
        self.base.inserer("individus", ["IDindividu", "nom", "prenom", "IDcivilite", "date_naiss"],
                          [(1, "FICTIF", "Un", 1, "2018-03-01"), (2, "FICTIF", "Deux", 1, "2018-03-01")])
        self.base.inserer("activites", ["IDactivite", "nom"], [(10, "Accueil fictif")])
        self.base.inserer("groupes", ["IDgroupe", "IDactivite", "nom"], [(1, 10, "Groupe fictif")])
        self.base.inserer("vacances", ["IDvacance", "nom", "annee", "date_debut", "date_fin"], [
            (1, u"Février", 2026, "2026-02-14", "2026-03-01"),
            (2, u"Eté", 2026, "2026-07-04", "2026-08-31"),
        ])
        self.base.inserer("evenements", ["IDevenement", "IDactivite", "nom", "date"],
                          [(5, 10, u"Sortie fictive", MERCREDI_SCOLAIRE)])
        self.IDconso = 0

        redirection = RedirectionGestionDB(self.base.chemin)
        redirection.__enter__()
        self.addCleanup(redirection.__exit__)

        dossier = Path(self.base.chemin).parent
        self.nom_pdf = str(dossier / "etat_global.pdf")
        self.recits = []
        patches = [
            mock.patch.object(DLG_Etat_global.FonctionsPerso, "GenerationNomDoc", return_value=self.nom_pdf),
            mock.patch.object(DLG_Etat_global.FonctionsPerso, "LanceFichierExterne"),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def conso(self, date, IDunite, debut=None, fin=None, etat="present", IDindividu=1,
              quantite=None, IDprestation=None, IDevenement=None):
        self.IDconso += 1
        self.base.inserer("consommations", [
            "IDconso", "IDindividu", "IDactivite", "IDgroupe", "IDcompte_payeur", "date", "IDunite",
            "heure_debut", "heure_fin", "etat", "quantite", "IDprestation", "IDevenement",
        ], [(self.IDconso, IDindividu, 10, 1, IDindividu, date, IDunite, debut, fin, etat,
             quantite, IDprestation, IDevenement)])

    def apercu(self, unites, opts=None):
        """ Lance le vrai Apercu() et renvoie les lignes des tableaux du PDF. """
        dialogue = _FauxDialog({u["IDunite"]: u for u in unites}, opts or options())
        from reportlab.platypus import SimpleDocTemplate, Table
        recit = []

        def construire(document, story, *args, **kwargs):
            recit.extend(story)

        with mock.patch.object(SimpleDocTemplate, "build", construire):
            retour = dialogue.Apercu(None)
        self.assertIsNone(retour)
        DLG_Etat_global.FonctionsPerso.LanceFichierExterne.assert_called_with(self.nom_pdf)
        lignes = []
        for element in recit:
            if isinstance(element, Table):
                lignes.extend([list(ligne) for ligne in element._cellvalues])
        return lignes[1:]  # sans l'entête "Etat global des consommations"

    def ligne(self, lignes, libelle):
        trouvees = [l for l in lignes if l and l[0] == libelle]
        self.assertEqual(len(trouvees), 1, (libelle, lignes))
        return trouvees[0][1:]

    # ---------------------------------------------------------------- temps réel

    def test_heure_seuil_et_heure_plafond(self):
        self.conso(MERCREDI_SCOLAIRE, 100, "07:30", "18:30")
        lignes = self.apercu([unite(100, u"Journée", heure_seuil="08:00", heure_plafond="18:00")])
        self.assertEqual(lignes[0], ["", u"Régime général", "Total"])
        self.assertEqual(self.ligne(lignes, "Hors vacances"), ["10h00", "10h00"])

    def test_duree_seuil_et_duree_plafond(self):
        self.conso(MERCREDI_SCOLAIRE, 100, "09:00", "09:20")
        self.conso(MERCREDI_FEVRIER, 100, "08:00", "19:00")
        lignes = self.apercu([unite(100, u"Journée", duree_seuil="01:00", duree_plafond="10:00")])
        self.assertEqual(self.ligne(lignes, "Hors vacances"), ["1h00", "1h00"])
        self.assertEqual(self.ligne(lignes, "Petites vacances"), ["10h00", "10h00"])

    def test_arrondi_duree_et_tranche_horaire(self):
        self.conso(MERCREDI_SCOLAIRE, 100, "09:00", "10:05")
        self.conso(MERCREDI_SCOLAIRE, 101, "09:10", "10:05")
        lignes = self.apercu([
            unite(100, u"Journée", arrondi=("duree", 15)),
            unite(101, u"Matin", arrondi=("tranche_horaire", 30)),
        ])
        # 1h05 arrondie à 1h15 + tranche 09:00-10:30 = 1h30.
        self.assertEqual(self.ligne(lignes, "Hors vacances"), ["2h45", "2h45"])

    def test_temps_du_midi_sans_forfait_ajoute(self):
        self.conso(MERCREDI_SCOLAIRE, 100, "11:30", "13:30")
        self.conso(MERCREDI_SCOLAIRE, 100, "12:00", "12:45", IDindividu=2)
        lignes = self.apercu([unite(100, u"Midi")])
        # Seules les durées pointées comptent : 0h45 (sans régime, ID 0 trié
        # en premier) + 2h00.
        self.assertEqual(lignes[0], ["", u"Sans régime", u"Régime général", "Total"])
        self.assertEqual(self.ligne(lignes, "Hors vacances"), ["0h45", "2h00", "2h45"])

    # ------------------------------------------------------- autres calculs

    def test_coefficient_multiplie_par_la_quantite(self):
        self.conso(MERCREDI_SCOLAIRE, 101, quantite=3)
        lignes = self.apercu([unite(101, "Repas", typeCalcul=0, coeff=2)])
        self.assertEqual(self.ligne(lignes, "Hors vacances"), ["6h00", "6h00"])

    def test_temps_facture_compte_une_seule_fois_par_prestation(self):
        self.base.inserer("prestations", ["IDprestation", "label", "montant", "temps_facture"],
                          [(1, "Forfait fictif", 10.0, "03:30")])
        self.conso(MERCREDI_SCOLAIRE, 102, "09:00", "10:00", IDprestation=1)
        self.conso("2026-03-11", 102, "09:00", "10:00", IDprestation=1)
        lignes = self.apercu([unite(102, "Forfait", typeCalcul=2)])
        self.assertEqual(self.ligne(lignes, "Hors vacances"), ["3h30", "3h30"])

    def test_formule(self):
        self.conso(MERCREDI_SCOLAIRE, 100, "08:00", "12:00")
        self.conso(MERCREDI_SCOLAIRE, 103, "13:00", "17:00")
        formule = "SI(unite100 != None, duree - HEURE('01:00'), duree)"
        lignes = self.apercu([unite(100, u"Matin"), unite(103, u"Après-midi", typeCalcul=3, formule=formule)])
        self.assertEqual(self.ligne(lignes, "Hors vacances"), ["7h00", "7h00"])

    def test_plafond_journalier_par_individu(self):
        self.conso(MERCREDI_SCOLAIRE, 100, "07:00", "13:00")
        self.conso(MERCREDI_SCOLAIRE, 101, "13:00", "18:00")
        lignes = self.apercu([unite(100, u"Matin"), unite(101, u"Après-midi")],
                             options(plafond_journalier_individu=480))
        self.assertEqual(self.ligne(lignes, "Hors vacances"), ["8h00", "8h00"])

    # ---------------------------------------------------------------- filtres

    def test_etats_jours_et_periodes(self):
        self.conso(MERCREDI_SCOLAIRE, 100, "09:00", "10:00", etat="present")
        self.conso(MERCREDI_SCOLAIRE, 100, "10:00", "12:00", etat="reservation", IDindividu=2)
        self.conso(MERCREDI_FEVRIER, 100, "09:00", "11:00")
        self.conso(MERCREDI_ETE, 100, "09:00", "12:00")
        self.conso("2026-03-05", 100, "09:00", "13:00")  # jeudi scolaire exclu
        self.conso(MERCREDI_SCOLAIRE, 100, "14:00", "15:00", etat="attente")
        self.conso(MERCREDI_SCOLAIRE, 100, "15:00", "16:00", etat="refus")
        lignes = self.apercu([unite(100, u"Journée")], options(
            etat_consommations=["present"], jours_hors_vacances=[2]))
        self.assertEqual(self.ligne(lignes, "Petites vacances"), ["2h00", "2h00"])
        self.assertEqual(self.ligne(lignes, u"Vacances d'été"), ["3h00", "3h00"])
        self.assertEqual(self.ligne(lignes, "Hors vacances"), ["1h00", "1h00"])
        self.assertEqual(self.ligne(lignes, "Total"), ["6h00", "6h00"])

    def test_regime_inconnu_associe_a_un_regime(self):
        self.conso(MERCREDI_SCOLAIRE, 100, "09:00", "10:00")
        self.conso(MERCREDI_SCOLAIRE, 100, "09:00", "11:00", IDindividu=2)
        lignes = self.apercu([unite(100, u"Journée")], options(associer_regime_inconnu=1))
        self.assertEqual(self.ligne(lignes, "Hors vacances"), ["3h00", "3h00"])

    def test_format_decimal(self):
        self.conso(MERCREDI_SCOLAIRE, 100, "09:00", "10:30")
        lignes = self.apercu([unite(100, u"Journée")], options(format_donnees="decimal"))
        self.assertEqual(self.ligne(lignes, "Hors vacances"), [1.5, 1.5])

    def test_regroupement_avec_valeur_vide_trie_comme_python2(self):
        self.conso(MERCREDI_SCOLAIRE, 100, "09:00", "10:00", IDevenement=5)
        self.conso(MERCREDI_SCOLAIRE, 100, "10:00", "12:00", IDindividu=2)
        lignes = self.apercu([unite(100, u"Journée")], options(regroupement_principal="evenement"))
        entetes = [l[0] for l in lignes if l and l[-1] == "Total"]
        self.assertEqual(entetes, [u"- Non renseigné -", u"Sortie fictive"])

    def test_tranches_age(self):
        self.conso(MERCREDI_SCOLAIRE, 100, "09:00", "10:00")
        lignes = self.apercu([unite(100, u"Journée")], options(regroupement_age=[6]))
        self.assertIn([u"Âge >= 6 ans", "", ""], lignes)

    def test_pdf_verrouille_affiche_le_message_d_origine(self):
        self.conso(MERCREDI_SCOLAIRE, 100, "09:00", "10:00")
        dialogue = _FauxDialog({100: unite(100, u"Journée")}, options())
        from reportlab.platypus import SimpleDocTemplate

        def refuser(*args, **kwargs):
            raise PermissionError(13, "Permission denied", self.nom_pdf)

        with mock.patch.object(SimpleDocTemplate, "build", refuser), \
                mock.patch.object(DLG_Etat_global.wx, "MessageDialog") as message:
            self.assertFalse(dialogue.Apercu(None))
        self.assertIn(u"ne peut pas créer le PDF", message.call_args.args[1])


class FormateValeurTests(unittest.TestCase):
    """ Mêmes résultats que la division entière de Python 2 d'origine. """

    def test_horaire(self):
        for minutes, attendu in ((0, "0h00"), (65, "1h05"), (1500, "25h00")):
            self.assertEqual(DLG_Etat_global.FormateValeur(datetime.timedelta(minutes=minutes), "horaire"), attendu)

    def test_decimal_comme_python2(self):
        # 1h05 donne 1.8 : écriture d'origine "heures.(minutes*100//60)".
        for minutes, attendu in ((0, 0.0), (60, 1.0), (90, 1.5), (65, 1.8), (75, 1.25), (1500, 25.0)):
            self.assertEqual(DLG_Etat_global.FormateValeur(datetime.timedelta(minutes=minutes), "decimal"), attendu)

    def test_tri_python2(self):
        valeurs = ["b", None, 3, "a", 1]
        self.assertEqual(sorted(valeurs, key=DLG_Etat_global.CleTriPython2), [None, 1, 3, "a", "b"])


if __name__ == "__main__":
    unittest.main()
