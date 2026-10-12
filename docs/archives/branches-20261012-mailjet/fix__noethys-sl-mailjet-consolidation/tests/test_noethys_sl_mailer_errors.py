# -*- coding: utf-8 -*-
"""Régression : les erreurs SMTP restent visibles sous Python 3."""
from __future__ import annotations

import smtplib
import sys
import unittest
from pathlib import Path

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

from Dlg.DLG_Mailer import _FormateErreurMessagerie  # noqa: E402


class FormateErreurMessagerieTests(unittest.TestCase):
    def test_exception_standard(self):
        self.assertEqual(
            _FormateErreurMessagerie(RuntimeError("connexion refusée")),
            "connexion refusée",
        )

    def test_smtp_error_bytes(self):
        err = smtplib.SMTPResponseException(535, b"Authentification refusee")
        self.assertEqual(
            _FormateErreurMessagerie(err),
            "Authentification refusee",
        )

    def test_smtp_error_bytes_invalides_ne_font_pas_crasher(self):
        err = smtplib.SMTPResponseException(500, b"Erreur \xff")
        self.assertIn("\ufffd", _FormateErreurMessagerie(err))


if __name__ == "__main__":
    unittest.main()
