# -*- coding: utf-8 -*-
"""Lectures sans porc : simulations SQL uniquement, sans reelle DB."""
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "noethys"))
from Utils import UTILS_Repas_source


class DBFictive:
    def __init__(self, mauvaise_question=False, multi_reponses=False):
        self.requetes = []
        self.closed = False
        self.mauvaise_question = mauvaise_question
        self.multi_reponses = multi_reponses
        self.derniere = ""
    def ExecuterReq(self, req):
        self.requetes.append(req)
        self.derniere = req
        return True
    def ResultatReq(self):
        req = self.derniere
        if "FROM questionnaire_questions" in req:
            return [("liste_coches", "Famille" if self.mauvaise_question else "Individu")]
        if "FROM questionnaire_choix" in req:
            return [(12,)]
        if "FROM consommations" in req:
            return [("2026-10-19", 1, 10, 1, "reservation"),
                    ("2026-10-19", 1, 10, 1, "present"),
                    ("2026-10-19", 1, 10, 2, "present"),
                    ("2026-10-19", 9, 10, 3, "present"),
                    ("2026-10-19", 1, 10, 4, "absent")]
        if "FROM questionnaire_reponses" in req:
            r = [(1, "12;13"), (2, "13")]
            return r + [(1, "13")] if self.multi_reponses else r
        return []
    def Close(self):
        self.closed = True


class RepasSourceTests(unittest.TestCase):
    def setUp(self):
        self.debut = self.fin = date(2026, 10, 19)

    def test_question_explicite_groupe_et_doublons(self):
        db = DBFictive()
        with patch.object(UTILS_Repas_source.GestionDB, "DB", return_value=db):
            r = UTILS_Repas_source.ChargerRepartition(5, 12, [(1, 10)], self.debut, self.fin)
        self.assertEqual(r[self.debut], {"sans_porc": 1, "repas": 2, "non_renseignes": 0})
        self.assertTrue(db.closed)
        self.assertEqual(sum("FROM questionnaire_reponses" in q for q in db.requetes), 1)
        self.assertTrue(all(q.lstrip().startswith("SELECT") for q in db.requetes))
        self.assertNotIn("nom", " ".join(db.requetes).lower())

    def test_refuse_question_famille(self):
        db = DBFictive(mauvaise_question=True)
        with patch.object(UTILS_Repas_source.GestionDB, "DB", return_value=db):
            with self.assertRaises(ValueError):
                UTILS_Repas_source.ChargerRepartition(5, 12, [(1, 10)], self.debut, self.fin)
        self.assertTrue(db.closed)

    def test_refuse_reponses_multiple_pour_meme_enfant(self):
        db = DBFictive(multi_reponses=True)
        with patch.object(UTILS_Repas_source.GestionDB, "DB", return_value=db):
            with self.assertRaises(ValueError):
                UTILS_Repas_source.ChargerRepartition(5, 12, [(1, 10)], self.debut, self.fin)

    def test_unites_vides_ne_contactent_pas_DB(self):
        with patch.object(UTILS_Repas_source.GestionDB, "DB") as db:
            self.assertEqual(UTILS_Repas_source.ChargerRepartition(1, 1, [], self.debut, self.fin), {})
            db.assert_not_called()


if __name__ == "__main__":
    unittest.main()
