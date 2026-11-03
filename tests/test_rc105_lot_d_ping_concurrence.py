# -*- coding: utf-8 -*-
"""Lot D : test deterministe de l'effacement concurrent d'un ping wx.

Ne demarre ni interface graphique, ni thread, ni reseau. Injecte la course
exacte qui donnait TypeError: float - NoneType dans Upload_data.
"""
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
from Utils import UTILS_Priorite_ui as P


class PingChangeant(P.PrioriteUI):
    """Simule _pong() au moment de la seconde lecture de _ping."""

    def __getattribute__(self, nom):
        if nom == "_ping":
            d = object.__getattribute__(self, "__dict__")
            if "_lectures" in d:
                compte = d["_lectures"]
                d["_lectures"] = compte + 1
                if compte >= 1:
                    return None
        return object.__getattribute__(self, nom)


class CoursePingTests(unittest.TestCase):
    def test_ping_efface_entre_test_et_soustraction_ne_plante_plus(self):
        p = PingChangeant(poster=lambda callback: None, horloge=lambda: 100.0,
                          dormir=lambda second: None)
        p._ping = 99.98
        p._dernier_ping = 99.98
        p._lectures = 0
        self.assertIsNone(p.ceder())
        self.assertEqual(p._lectures, 1,
                         "Une seconde lecture non atomique peut recevoir None")

    def test_ping_recu_met_fin_a_attente(self):
        rappels = []
        horloge = [100.0]
        p = P.PrioriteUI(poster=rappels.append, horloge=lambda: horloge[0],
                         dormir=lambda duree: None)
        self.assertIsNone(p.ceder())
        self.assertEqual(len(rappels), 1)
        rappels[0]()
        self.assertIsNone(p._ping)
        horloge[0] = 100.10
        self.assertIsNone(p.ceder())
        self.assertEqual(len(rappels), 2)

    def test_poster_indisponible_ne_plante_pas(self):
        p = P.PrioriteUI(poster=False, horloge=lambda: 1.0)
        self.assertFalse(p.actif)
        self.assertIsNone(p.ceder())


if __name__ == "__main__":
    unittest.main()
