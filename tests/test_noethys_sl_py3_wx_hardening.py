# -*- coding: utf-8 -*-
"""Contrats de portage Python 3 / wxPython de Noethys SL 0.1.0."""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def lire(path):
    return (ROOT / path).read_text(encoding="utf-8")


def source_methode(path, class_name, method_name):
    source = lire(path)
    tree = ast.parse(source)
    cls = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    method = next(
        node for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    )
    return ast.get_source_segment(source, method)


class MailerPython3Contracts(unittest.TestCase):
    def test_mailjet_ne_decode_plus_un_str_python3(self):
        source = lire("noethys/Utils/UTILS_Envoi_email.py")
        self.assertIn("def _TexteUtf8(valeur):", source)
        self.assertNotIn('err = str(err).decode("utf8")', source)

        methode = source_methode("noethys/Utils/UTILS_Envoi_email.py", "Mailjet", "Envoyer_lot")
        self.assertIn("_TexteUtf8(err)", methode, "Envoyer_lot() doit convertir l'erreur via _TexteUtf8()")

    def test_normalisation_bytes_utilise_un_repli_sur_caractere_invalide(self):
        source = lire("noethys/Utils/UTILS_Envoi_email.py")
        self.assertIn('decode("utf-8", errors="replace")', source)


class SmsPython3Contracts(unittest.TestCase):
    def test_pieces_jointes_sms_sont_ecrites_en_texte_utf8(self):
        source = lire("noethys/Dlg/DLG_Envoi_sms.py")
        self.assertEqual(
            source.count('open(cheminFichier, "w", encoding="utf-8")'),
            3,
        )
        self.assertNotIn('fichier.write(texte.encode("utf8"))', source)

    def test_erreur_email_sms_ne_decode_plus_un_str(self):
        source = lire("noethys/Dlg/DLG_Envoi_sms.py")
        self.assertNotIn('str(err).decode("utf8")', source)
        self.assertIn("UTILS_Envoi_email._TexteUtf8(err)", source)


class ExportHeliosPython3Contracts(unittest.TestCase):
    def test_export_helios_ecrit_du_texte_utf8(self):
        source = lire("noethys/Dlg/DLG_Export_helios.py")
        self.assertIn('open(cheminFichier, "w", encoding="utf-8")', source)
        self.assertIn("fichier.write(texte)", source)
        self.assertNotIn('f.write(texte.encode("utf8"))', source)

    def test_dialogue_ecrasement_est_detruit_avant_le_retour(self):
        source = lire("noethys/Dlg/DLG_Export_helios.py")
        self.assertIn("reponse = dlg.ShowModal()", source)
        self.assertIn("dlg.Destroy()", source)
        self.assertNotIn("return False\n                dlg.Destroy()", source)


class NomadhysWxThreadContracts(unittest.TestCase):
    def test_image_journal_et_gauge_sont_deportes_vers_la_boucle_wx(self):
        path = "noethys/Ctrl/CTRL_Serveur_nomade.py"
        set_image = source_methode(path, "Panel", "SetImage")
        ecrit_log = source_methode(path, "Panel", "EcritLog")
        set_gauge = source_methode(path, "Panel", "SetGauge")

        self.assertIn("wx.CallAfter(self._AppliqueImage", set_image)
        self.assertIn("wx.CallAfter(self._AjouteLog", ecrit_log)
        self.assertIn("wx.CallAfter(self._AppliqueGauge", set_gauge)

        self.assertNotIn("self.ctrl_image.SetBitmap", set_image)
        self.assertNotIn("self.log.GetValue()", ecrit_log)
        self.assertNotIn("self.gauge.IsShown()", set_gauge)


class SynchronisationPasswordContracts(unittest.TestCase):
    def test_ftp_decode_les_bytes_avant_textctrl(self):
        src = source_methode(
            "noethys/Dlg/DLG_Synchronisation.py",
            "Page_ftp",
            "SetParametres",
        )
        self.assertIn('mdp.decode("utf-8", errors="replace")', src)
        self.assertIn("self.ctrl_mdp.SetValue(mdp)", src)

    def test_cryptage_decode_les_bytes_avant_textctrl(self):
        src = source_methode(
            "noethys/Dlg/DLG_Synchronisation.py",
            "Page_cryptage",
            "SetParametres",
        )
        self.assertIn('mdp.decode("utf-8", errors="replace")', src)
        self.assertIn("self.ctrl_mdp.SetValue(mdp)", src)


class PortailConfigLogContracts(unittest.TestCase):
    def test_journal_connecthys_ne_contient_plus_de_decode_python2(self):
        src = source_methode(
            "noethys/Dlg/DLG_Portail_config.py",
            "Dialog",
            "EcritLog",
        )
        self.assertNotIn("str(message).decode", src)
        self.assertIn('message.decode("utf-8", errors="replace")', src)


if __name__ == "__main__":
    unittest.main()
