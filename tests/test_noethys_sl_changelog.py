# -*- coding: utf-8 -*-
"""Contrat des notes de versions affichees par Noethys SL.

La section la plus recente est en tete, chaque nouveaute sur sa propre
ligne "- ", et l'historique Noethys numerique reste intact pour les
migrations et Connecthys. Aucun import wx, aucune connexion de base.
"""
from __future__ import annotations

import ast
import hashlib
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"
ENTETE_INTERNE = "Version 1.3.4.4 (01/10/2026) :"
SHA_HISTORIQUE = "5b13501bdc51ad5c08aced106d4db0f66e809bf8"


def version_publique():
    tree = ast.parse((NOETHYS / "Identite.py").read_text(encoding="utf-8"))
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(
            isinstance(c, ast.Name) and c.id == "PRODUCT_VERSION_DISPLAY"
            for c in n.targets
        ):
            return ast.literal_eval(n.value)
    raise AssertionError("PRODUCT_VERSION_DISPLAY absent")


class NotesDeVersionsTests(unittest.TestCase):
    def setUp(self):
        self.contenu = (NOETHYS / "Versions.txt").read_text(encoding="utf-8")

    def test_historique_d_origine_est_conserve_integralement(self):
        debut = self.contenu.find(ENTETE_INTERNE)
        self.assertGreaterEqual(debut, 0)
        suffixe = self.contenu[debut:].encode("utf-8")
        signature = hashlib.sha1(
            ("blob %d\0" % len(suffixe)).encode("ascii") + suffixe
        ).hexdigest()
        self.assertEqual(signature, SHA_HISTORIQUE)

    def test_derniere_version_interne_numerique_reste_1344(self):
        trouvees = re.findall(
            r"^Version (\d+(?:\.\d+){3}) \(\d{2}/\d{2}/\d{4}\) :$",
            self.contenu, re.MULTILINE,
        )
        self.assertTrue(trouvees)
        self.assertEqual(trouvees[0], "1.3.4.4")

    def test_nouveautes_en_tete_une_puce_par_ligne(self):
        debut_legacy = self.contenu.index(ENTETE_INTERNE)
        nouveautes = self.contenu[:debut_legacy]
        if not nouveautes.strip():
            # main / Qt n'ont pas le numero public RC7.2 de la branche wx.
            self.assertTrue(self.contenu.startswith(ENTETE_INTERNE))
            return

        premiere = nouveautes.splitlines()[0]
        self.assertRegex(
            premiere,
            r"^Version Noethys SL " + re.escape(version_publique())
            + r" \(\d{2}/\d{2}/\d{4}\) :$",
        )
        nb_puces = 0
        for ligne in nouveautes.splitlines():
            if not ligne:
                continue
            if ligne.startswith("Version Noethys SL "):
                self.assertRegex(
                    ligne,
                    r"^Version Noethys SL .+ \(\d{2}/\d{2}/\d{4}\) :$",
                )
                continue
            self.assertTrue(ligne.startswith("- "), "Nouvelle entree sans tiret : %r" % ligne)
            self.assertGreater(len(ligne), 2)
            nb_puces += 1
        self.assertGreater(nb_puces, 0)


if __name__ == "__main__":
    unittest.main()
