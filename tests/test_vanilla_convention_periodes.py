# -*- coding: utf-8 -*-
"""ConstruirePeriodes() / FormatePeriodes() : representation structuree
du planning scolaire, independante de wx et du rendu PDF. Cas cibles :
plusieurs groupes, plusieurs periodes, trous (vacances), changement
d'horaire en cours de periode, groupe sans activite renseignee.
"""
from __future__ import annotations

import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import sys
import unittest
from decimal import Decimal
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
NOETHYS_DIR = TESTS_DIR.parent / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

from Utils import UTILS_Convention_champs as CC  # noqa: E402


def _conso(heure_debut, heure_fin, montant, date, etat="reservation"):
    return {
        "heure_debut": heure_debut, "heure_fin": heure_fin, "etat": etat,
        "prestation": None if montant is None else {"montant": montant, "label": "x", "paye": None},
    }


def _ajoute_seances(dictDonnees, IDindividu, nom, prenom, IDactivite, nom_activite, seances):
    """ seances : liste de (date, heure_debut, heure_fin, montant). """
    if IDindividu not in dictDonnees:
        dictDonnees[IDindividu] = {"nom": nom, "prenom": prenom, "date_naiss": None, "sexe": None, "activites": {}}
    activites = dictDonnees[IDindividu]["activites"]
    if IDactivite not in activites:
        activites[IDactivite] = {"nom": nom_activite, "agrement": None, "dates": {}}
    dates = activites[IDactivite]["dates"]
    for date, heure_debut, heure_fin, montant in seances:
        dates.setdefault(date, {"unites": {1: []}})
        dates[date]["unites"][1].append(_conso(heure_debut, heure_fin, montant, date))


class ConstruirePeriodesTests(unittest.TestCase):
    def test_plusieurs_groupes_produisent_des_periodes_distinctes(self):
        dictDonnees = {}
        _ajoute_seances(dictDonnees, 1, "ECOLE TEST", "CYCLE 1", 20, "Encadrement scolaire", [
            ("2026-09-03", "09:00", "10:00", 20.0),
        ])
        _ajoute_seances(dictDonnees, 2, "ECOLE TEST", "CYCLE 2", 20, "Encadrement scolaire", [
            ("2026-09-04", "10:00", "12:00", 40.0),
        ])
        periodes = CC.ConstruirePeriodes(dictDonnees)
        self.assertEqual(len(periodes), 2)
        groupes = {p.groupe for p in periodes}
        self.assertEqual(groupes, {"ECOLE TEST CYCLE 1", "ECOLE TEST CYCLE 2"})

    def test_ordre_est_stable_et_deterministe(self):
        dictDonnees = {}
        _ajoute_seances(dictDonnees, 1, "ECOLE", "CYCLE B", 20, "x", [("2026-09-03", "09:00", "10:00", 20.0)])
        _ajoute_seances(dictDonnees, 2, "ECOLE", "CYCLE A", 20, "x", [("2026-09-03", "09:00", "10:00", 20.0)])

        premier = [(p.groupe, str(p.date_debut)) for p in CC.ConstruirePeriodes(dictDonnees)]
        second = [(p.groupe, str(p.date_debut)) for p in CC.ConstruirePeriodes(dictDonnees)]
        self.assertEqual(premier, second)
        # Tri alphabetique par groupe : CYCLE A avant CYCLE B.
        self.assertEqual(premier[0][0], "ECOLE CYCLE A")

    def test_nombre_de_seances_et_duree_totale(self):
        dictDonnees = {}
        _ajoute_seances(dictDonnees, 1, "ECOLE", "CYCLE 3", 20, "Encadrement scolaire", [
            ("2026-09-03", "09:00", "11:00", 40.0),
            ("2026-09-10", "09:00", "11:00", 40.0),
            ("2026-09-17", "09:00", "11:00", 40.0),
        ])
        periodes = CC.ConstruirePeriodes(dictDonnees)
        self.assertEqual(len(periodes), 1)
        periode = periodes[0]
        self.assertEqual(periode.nombre_seances, 3)
        self.assertEqual(periode.duree_minutes, 3 * 120)
        self.assertEqual(periode.montant_total, Decimal("120.0"))

    def test_periode_avec_vacances_est_coupee_en_deux(self):
        """ Meme groupe, meme jour de semaine (jeudi), meme horaire, mais
        une interruption de plusieurs mois (vacances) : ne doit jamais
        etre presente comme un seul bloc continu. """
        dictDonnees = {}
        _ajoute_seances(dictDonnees, 1, "ECOLE", "CYCLE 2", 20, "Encadrement scolaire", [
            ("2025-09-11", "09:00", "12:00", 60.0),  # jeudi
            ("2025-09-18", "09:00", "12:00", 60.0),  # jeudi
            ("2025-09-25", "09:00", "12:00", 60.0),  # jeudi
            # Interruption (vacances) : reprise 7 mois plus tard, même jour/horaire.
            ("2026-05-21", "09:00", "12:00", 60.0),  # jeudi
            ("2026-05-28", "09:00", "12:00", 60.0),  # jeudi
        ])
        periodes = CC.ConstruirePeriodes(dictDonnees)
        self.assertEqual(len(periodes), 2, "l'interruption doit produire deux périodes distinctes")
        periodes_triees = sorted(periodes, key=lambda p: str(p.date_debut))
        self.assertEqual(str(periodes_triees[0].date_debut), "2025-09-11")
        self.assertEqual(str(periodes_triees[0].date_fin), "2025-09-25")
        self.assertEqual(periodes_triees[0].nombre_seances, 3)
        self.assertEqual(str(periodes_triees[1].date_debut), "2026-05-21")
        self.assertEqual(str(periodes_triees[1].date_fin), "2026-05-28")
        self.assertEqual(periodes_triees[1].nombre_seances, 2)

    def test_seances_hebdomadaires_normales_ne_sont_pas_coupees(self):
        """ Un ecart hebdomadaire habituel (7 jours) ne doit jamais
        declencher une coupure de periode. """
        dictDonnees = {}
        _ajoute_seances(dictDonnees, 1, "ECOLE", "CYCLE 1", 20, "x", [
            ("2026-09-0%d" % j, "09:00", "10:00", 20.0) for j in (3,)
        ] + [
            ("2026-09-%d" % j, "09:00", "10:00", 20.0) for j in (10, 17, 24)
        ])
        periodes = CC.ConstruirePeriodes(dictDonnees)
        self.assertEqual(len(periodes), 1)
        self.assertEqual(periodes[0].nombre_seances, 4)

    def test_changement_horaire_en_cours_de_periode_cree_un_groupe_separe(self):
        """ Cas reel constate (La Providence) : une exception ponctuelle
        d'horaire (ex. l'apres-midi au lieu du matin) doit apparaitre
        comme un creneau distinct, jamais fusionnee ni ignoree. """
        dictDonnees = {}
        _ajoute_seances(dictDonnees, 1, "ECOLE", "CYCLE 2", 20, "Encadrement scolaire", [
            ("2025-10-02", "09:00", "12:00", 60.0),
            ("2025-10-09", "13:15", "16:15", 60.0),  # exception d'horaire
        ])
        periodes = CC.ConstruirePeriodes(dictDonnees)
        self.assertEqual(len(periodes), 2)
        horaires = sorted((p.heure_debut, p.heure_fin) for p in periodes)
        self.assertEqual(horaires, [("09:00", "12:00"), ("13:15", "16:15")])
        for p in periodes:
            self.assertEqual(p.nombre_seances, 1)

    def test_groupe_sans_activite_renseignee_ne_fabrique_rien(self):
        dictDonnees = {}
        _ajoute_seances(dictDonnees, 1, "ECOLE", "CYCLE 1", 20, "", [
            ("2026-09-03", "09:00", "10:00", 20.0),
        ])
        periodes = CC.ConstruirePeriodes(dictDonnees)
        self.assertEqual(len(periodes), 1)
        self.assertEqual(periodes[0].activite, "")
        texte = CC.FormatePeriode(periodes[0])
        self.assertNotIn(" : ", texte.split(u"(")[0].rstrip())  # pas de ": " suivi de rien

    def test_activite_renseignee_apparait_textuellement(self):
        dictDonnees = {}
        _ajoute_seances(dictDonnees, 1, "ECOLE", "CYCLE 1", 20, "Encadrement sportif scolaires", [
            ("2026-09-03", "09:00", "10:00", 20.0),
        ])
        periodes = CC.ConstruirePeriodes(dictDonnees)
        texte = CC.FormatePeriode(periodes[0])
        self.assertIn("Encadrement sportif scolaires", texte)

    def test_formate_periodes_regroupe_par_groupe_dans_lordre(self):
        dictDonnees = {}
        _ajoute_seances(dictDonnees, 1, "ECOLE", "CYCLE 1", 20, "x", [("2026-09-03", "09:00", "10:00", 20.0)])
        _ajoute_seances(dictDonnees, 2, "ECOLE", "CYCLE 2", 20, "x", [("2026-09-04", "09:00", "10:00", 20.0)])
        texte = CC.FormatePeriodes(CC.ConstruirePeriodes(dictDonnees))
        self.assertIn("ECOLE CYCLE 1", texte)
        self.assertIn("ECOLE CYCLE 2", texte)
        self.assertLess(texte.index("ECOLE CYCLE 1"), texte.index("ECOLE CYCLE 2"))

    def test_get_resume_planning_totaux_coherents_avec_les_periodes(self):
        dictDonnees = {}
        _ajoute_seances(dictDonnees, 1, "ECOLE", "CYCLE 1", 20, "x", [
            ("2025-09-11", "09:00", "12:00", 60.0),
            ("2026-05-21", "09:00", "12:00", 60.0),
        ])
        resume = CC.GetResumePlanning(dictDonnees)
        self.assertEqual(len(resume["periodes"]), 2)
        self.assertEqual(resume["nbre_seances"], 2)
        self.assertEqual(resume["total_heures_minutes"], 2 * 180)
        self.assertEqual(resume["total_montant"], Decimal("120.0"))


if __name__ == "__main__":
    unittest.main()
