# -*- coding: utf-8 -*-
"""EMAIL-07 -- reçu de règlement envoyé par email depuis la saisie du
règlement : il n'est mémorisé comme envoyé que si le Mailer a accepté un
message pour ce destinataire (DLG_Mailer.listeSucces). Avant correction,
DLG_Saisie_reglement jugeait sur DLG_Mailer.listeAnomalies, jamais
alimentée : le reçu était mémorisé même après un échec (caractérisé par
tests/test_audit_reseau_emails.py, audit phase 1)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

try:
    import wx  # noqa: F401
    from Utils import UTILS_Envoi_email
    IMPORT_ERREUR = None
except Exception as err:  # pragma: no cover
    IMPORT_ERREUR = err


def setUpModule():
    if IMPORT_ERREUR is not None:
        raise unittest.SkipTest("Import Noethys impossible : %r" % (IMPORT_ERREUR,))


def message(adresse):
    return UTILS_Envoi_email.Message(destinataires=[adresse], sujet=u"Reçu", texte_html=u"<p>x</p>", fichiers=[], images=[])


class RecuReglementTests(unittest.TestCase):
    """EMAIL-07 : le reçu n'est mémorisé comme envoyé que si le Mailer a
    accepté un message pour ce destinataire."""

    def setUp(self):
        from Dlg import DLG_Saisie_reglement
        self.f = DLG_Saisie_reglement.RecuAccepte

    def test_succes(self):
        self.assertTrue(self.f([message("a@example.org")], "a@example.org"))

    def test_echec(self):
        self.assertFalse(self.f([], "a@example.org"))

    def test_succes_pour_un_autre_destinataire(self):
        self.assertFalse(self.f([message("b@example.org")], "a@example.org"))

    def test_source_utilise_liste_succes(self):
        source = (NOETHYS_DIR / "Dlg" / "DLG_Saisie_reglement.py").read_text(encoding="utf-8")
        self.assertIn("succes = RecuAccepte(dlg2.listeSucces, adresse)", source)
        self.assertNotIn("dlg2.listeAnomalies", source)
        self.assertIn("if succes == True :\n                            dlg1.Sauvegarder(demander=False)", source)


if __name__ == "__main__":
    unittest.main()
