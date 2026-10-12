# -*- coding: utf-8 -*-
"""Frontieres texte/binaire et encodages explicites des exports.

Repris de origin/master :
- 299dbcc3 : exports protocolaires Corail, Magnus, UTILS_Corail/Jvs/Pes
  (octets de toprettyxml(encoding=...) ecrits dans un fichier texte ->
  TypeError) ;
- b2ce3aef : encodages UTF-8 explicites (lot JVS, traductions,
  prelevements) ;
- 910cc8f5 : encodages explicites (lot PES en ISO-8859-1, FonctionsPerso,
  UTILS_Envoi_email).

Fichiers temporaires uniquement ; aucune base, aucun reseau, aucune fenetre.
"""
import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import ast  # noqa: E402
import os  # noqa: E402
import tempfile  # noqa: E402
import unittest  # noqa: E402
from pathlib import Path  # noqa: E402
from xml.dom.minidom import Document  # noqa: E402

import wx  # noqa: E402

_APP = wx.App(False) if not wx.GetApp() else wx.GetApp()

NOETHYS = Path(__file__).resolve().parents[1] / "noethys"


def _arbre(relatif):
    return ast.parse((NOETHYS / relatif).read_text(encoding="utf-8"))


def _mot_cle(appel, nom):
    for kw in appel.keywords:
        if kw.arg == nom and isinstance(kw.value, ast.Constant):
            return kw.value.value
    return None


def _mode(appel):
    if len(appel.args) >= 2 and isinstance(appel.args[1], ast.Constant):
        return appel.args[1].value
    return _mot_cle(appel, "mode") or "r"


def _appels_open(arbre):
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Call):
            f = noeud.func
            nom = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
            if nom == "open" and not (isinstance(f, ast.Attribute) and getattr(f.value, "id", "") in ("wx", "webbrowser")):
                yield noeud


def _ouvertures_texte_sans_encodage(relatif):
    """Lignes des open() en mode texte sans encoding= explicite."""
    fautes = []
    for appel in _appels_open(_arbre(relatif)):
        mode = _mode(appel)
        if not isinstance(mode, str) or "b" in mode:
            continue
        if _mot_cle(appel, "encoding") is None and not any(kw.arg == "encoding" for kw in appel.keywords):
            fautes.append(appel.lineno)
    return fautes


def _ouvertures_texte_pour_toprettyxml_encode(relatif):
    """open() en mode texte dont l'objet recoit toprettyxml(encoding=...)
    (des octets) : TypeError en Python 3."""
    fautes = []
    arbre = _arbre(relatif)
    for fonction in ast.walk(arbre):
        if not isinstance(fonction, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        modes = {}
        for noeud in ast.walk(fonction):
            if isinstance(noeud, ast.Assign) and isinstance(noeud.value, ast.Call) \
                    and noeud.value in list(_appels_open(noeud.value)):
                for cible in noeud.targets:
                    if isinstance(cible, ast.Name):
                        modes[cible.id] = (_mode(noeud.value), noeud.lineno)
            if isinstance(noeud, ast.withitem) and isinstance(noeud.context_expr, ast.Call) \
                    and isinstance(noeud.optional_vars, ast.Name) \
                    and noeud.context_expr in list(_appels_open(noeud.context_expr)):
                modes[noeud.optional_vars.id] = (_mode(noeud.context_expr), noeud.context_expr.lineno)
        for noeud in ast.walk(fonction):
            if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute) \
                    and noeud.func.attr == "write" and isinstance(noeud.func.value, ast.Name) \
                    and noeud.func.value.id in modes and noeud.args:
                arg = noeud.args[0]
                if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute) \
                        and arg.func.attr in ("toprettyxml", "toxml") \
                        and any(kw.arg == "encoding" for kw in arg.keywords):
                    mode, ligne = modes[noeud.func.value.id]
                    if "b" not in mode:
                        fautes.append(ligne)
    return fautes


def _doc_accentue():
    doc = Document()
    racine = doc.createElement("Racine")
    racine.setAttribute("Libelle", u"Cantine éte – Noël")
    doc.appendChild(racine)
    return doc


class FrontieresTexteBinaireTests(unittest.TestCase):
    """299dbcc3"""

    def _enregistrer(self, module):
        with tempfile.TemporaryDirectory(prefix="noethys-export-") as rep:
            chemin = os.path.join(rep, "export.xml")
            module.EnregistrerXML(_doc_accentue(), chemin)
            return Path(chemin).read_bytes()

    def test_utils_corail_jvs_pes_ecrivent_des_octets_utf8(self):
        from Utils import UTILS_Corail, UTILS_Jvs, UTILS_Pes
        for module in (UTILS_Corail, UTILS_Jvs, UTILS_Pes):
            with self.subTest(module=module.__name__):
                contenu = self._enregistrer(module)
                self.assertTrue(contenu.startswith(b'<?xml version="1.0" encoding="UTF-8"?>'))
                self.assertIn(u"Cantine éte – Noël".encode("utf-8"), contenu)

    def test_dialogue_corail_ouvre_le_xml_en_binaire(self):
        for relatif in ("Dlg/DLG_Saisie_lot_tresor_public_corail.py",
                        "Utils/UTILS_Corail.py", "Utils/UTILS_Jvs.py", "Utils/UTILS_Pes.py"):
            with self.subTest(fichier=relatif):
                self.assertEqual(_ouvertures_texte_pour_toprettyxml_encode(relatif), [])

    def test_magnus_ecrit_ses_fichiers_texte_en_utf8_explicite(self):
        self.assertEqual(_ouvertures_texte_sans_encodage("Dlg/DLG_Saisie_lot_tresor_public_magnus.py"), [])


def _mimetext_sans_charset(relatif):
    """Lignes des MIMEText(fp.read(), ...) construits sans _charset."""
    fautes = []
    for noeud in ast.walk(_arbre(relatif)):
        if isinstance(noeud, ast.Call) and getattr(noeud.func, "id", None) == "MIMEText" \
                and noeud.args and isinstance(noeud.args[0], ast.Call) \
                and getattr(noeud.args[0].func, "attr", None) == "read" \
                and not any(kw.arg == "_charset" for kw in noeud.keywords):
            fautes.append(noeud.lineno)
    return fautes


def _encodages_xml_ecrits(relatif):
    """Encodages passes a toxml/toprettyxml dans un f.write(...)."""
    encodages = []
    for noeud in ast.walk(_arbre(relatif)):
        if isinstance(noeud, ast.Call) and getattr(noeud.func, "attr", None) == "write" and noeud.args:
            arg = noeud.args[0]
            if isinstance(arg, ast.Call) and getattr(arg.func, "attr", None) in ("toxml", "toprettyxml"):
                encodages.append(_mot_cle(arg, "encoding"))
    return encodages


TEXTE_HORS_CP1252 = u"Crèche – Zoë ŝ"


class EncodagesUtf8ExplicitesTests(unittest.TestCase):
    """b2ce3aef"""

    def test_prelevements_enregistre_un_xml_sepa_utf8(self):
        from Utils import UTILS_Prelevements
        doc = Document()
        racine = doc.createElement("Document")
        racine.appendChild(doc.createTextNode(TEXTE_HORS_CP1252))
        doc.appendChild(racine)
        with tempfile.TemporaryDirectory(prefix="noethys-sepa-") as rep:
            chemin = os.path.join(rep, "sepa.xml")
            UTILS_Prelevements.EnregistrerXML(doc, chemin)
            contenu = Path(chemin).read_bytes()
        self.assertTrue(contenu.startswith(b'<?xml version="1.0" encoding="UTF-8"?>'))
        self.assertIn(TEXTE_HORS_CP1252.encode("utf-8"), contenu)

    def test_lot_jvs_ecrit_un_xml_utf8_binaire(self):
        relatif = "Dlg/DLG_Saisie_lot_tresor_public_jvs.py"
        self.assertEqual(_ouvertures_texte_pour_toprettyxml_encode(relatif), [])
        self.assertEqual(_ouvertures_texte_sans_encodage(relatif), [])
        self.assertEqual(_encodages_xml_ecrits(relatif), ["UTF-8"])

    def test_traductions_piece_jointe_texte_utf8(self):
        relatif = "Dlg/DLG_Traductions.py"
        self.assertEqual(_ouvertures_texte_sans_encodage(relatif), [])
        self.assertEqual(_mimetext_sans_charset(relatif), [])


class EncodagesExplicitesTests(unittest.TestCase):
    """910cc8f5 (adapte : pas de dependance obligatoire a chardet, absent
    des requirements de main ; moteur e-mail recent de main conserve)."""

    def test_lot_pes_ecrit_un_xml_iso_8859_1_binaire(self):
        relatif = "Dlg/DLG_Saisie_lot_tresor_public_pes.py"
        self.assertEqual(_ouvertures_texte_pour_toprettyxml_encode(relatif), [])
        self.assertEqual(_ouvertures_texte_sans_encodage(relatif), [])
        self.assertEqual(_encodages_xml_ecrits(relatif), ["ISO-8859-1"])

    def test_piece_jointe_texte_utf8_decodee_sans_mojibake(self):
        from email.mime.multipart import MIMEMultipart
        from Utils import UTILS_Envoi_email
        with tempfile.TemporaryDirectory(prefix="noethys-pj-") as rep:
            chemin = os.path.join(rep, "liste.txt")
            Path(chemin).write_bytes(TEXTE_HORS_CP1252.encode("utf-8"))
            message = UTILS_Envoi_email.Message.__new__(UTILS_Envoi_email.Message)
            message.fichiers = [chemin]
            email = MIMEMultipart()
            message.AttacheFichiersJoints(email)
        part = email.get_payload()[0]
        self.assertEqual(part.get_content_type(), "text/plain")
        texte = part.get_payload(decode=True).decode(part.get_content_charset())
        self.assertEqual(texte, TEXTE_HORS_CP1252)

    def test_piece_jointe_texte_cp1252_decodee(self):
        from email.mime.multipart import MIMEMultipart
        from Utils import UTILS_Envoi_email
        with tempfile.TemporaryDirectory(prefix="noethys-pj-") as rep:
            chemin = os.path.join(rep, "ancien.txt")
            Path(chemin).write_bytes(u"Crèche Zoë".encode("cp1252"))
            message = UTILS_Envoi_email.Message.__new__(UTILS_Envoi_email.Message)
            message.fichiers = [chemin]
            email = MIMEMultipart()
            message.AttacheFichiersJoints(email)
        part = email.get_payload()[0]
        texte = part.get_payload(decode=True).decode(part.get_content_charset())
        self.assertEqual(texte, u"Crèche Zoë")

    def test_prepare_fichier_bic_lit_cp1252_et_ecrit_utf8(self):
        import FonctionsPerso
        from unittest import mock
        source = u"1\tCrédit Agricole\tSaint-Étienne\tx\tAGRIFRPP\r\n2\tBanque Zoë\tSète\ty\tBQZOFRPP"
        with tempfile.TemporaryDirectory(prefix="noethys-bic-") as rep:
            Path(rep, "liste_bic_france.txt").write_bytes(source.encode("cp1252"))
            sortie = os.path.join(rep, "liste_bic_france_new.txt")
            cwd = os.getcwd()
            os.chdir(rep)
            try:
                with mock.patch.object(FonctionsPerso.UTILS_Fichiers, "GetRepTemp", return_value=sortie):
                    FonctionsPerso.PrepareFichierBIC()
            finally:
                os.chdir(cwd)
            resultat = Path(sortie).read_bytes().decode("utf-8")
        self.assertEqual(resultat,
                         u'("Crédit Agricole", "Saint-Étienne", "AGRIFRPP")\n'
                         u'("Banque Zoë", "Sète", "BQZOFRPP")\n')


if __name__ == "__main__":
    unittest.main()
