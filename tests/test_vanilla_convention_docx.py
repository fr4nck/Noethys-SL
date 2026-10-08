# -*- coding: utf-8 -*-
"""Contrat du générateur de conventions Word modifiables."""
from __future__ import annotations

import datetime
import sys
import tempfile
import unittest
import unittest.mock
import zipfile
from pathlib import Path

from lxml import etree

TESTS_DIR = Path(__file__).resolve().parent
NOETHYS_DIR = TESTS_DIR.parent / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from _fixtures_noethys_db import (  # noqa: E402
    RedirectionGestionDB,
    creer_base_association_simple,
)
from Utils import UTILS_Convention_docx as DOCX  # noqa: E402


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _xml(racine, paragraphes):
    corps = u"".join(u"<w:p>%s</w:p>" % p for p in paragraphes)
    return (u'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            u'<w:%s xmlns:w="%s">%s</w:%s>' % (racine, W, corps, racine)).encode("utf-8")


def _creer_modele(chemin, sans_champ=False, champ_inconnu=False):
    paragraphes = [
        u"<w:r><w:t>Famille : {FAMILLE_</w:t></w:r><w:r><w:t>NOM}</w:t></w:r>",
        u"<w:r><w:t>Planning : {CONVENTION_PLANNING_DETAIL}</w:t></w:r>",
    ]
    if champ_inconnu:
        paragraphes.append(u"<w:r><w:t>Champ inconnu : {CHAMP_</w:t></w:r><w:r><w:t>LIBRE}</w:t></w:r>")
    document = _xml("document", paragraphes)
    entete, pied = u"{ORGANISATEUR_NOM}", u"{CONVENTION_DATE_SIGNATURE}"
    if sans_champ:
        document = _xml("document", [u"<w:r><w:t>Document sans fusion</w:t></w:r>"])
        entete, pied = u"En-tête fixe", u"Pied fixe"
    with zipfile.ZipFile(chemin, "w") as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("word/document.xml", document)
        archive.writestr("word/header1.xml", _xml("hdr", [
            u"<w:r><w:t>%s</w:t></w:r>" % entete
        ]))
        archive.writestr("word/footer1.xml", _xml("ftr", [
            u"<w:r><w:t>%s</w:t></w:r>" % pied
        ]))
        archive.writestr("word/media/logo.png", b"PNG-INCHANGE")


def _texte_xml(archive, nom):
    racine = etree.fromstring(archive.read(nom))
    return u"".join(racine.xpath(".//w:t/text()", namespaces={"w": W}))


class ConventionDocxTests(unittest.TestCase):
    def test_impression_complete_utilise_les_donnees_noethys(self):
        with tempfile.TemporaryDirectory() as dossier:
            modele = Path(dossier) / "modele.docx"
            sortie = Path(dossier) / "convention.docx"
            _creer_modele(modele)
            with creer_base_association_simple() as base:
                with RedirectionGestionDB(base.chemin):
                    resultat = DOCX.Impression(
                        IDfamille=1, modele=modele,
                        date_debut="2026-09-01", date_fin="2026-09-30",
                        saison="2026-2027", nomDoc=sortie, afficherDoc=False,
                    )
            self.assertTrue(resultat)
            with zipfile.ZipFile(sortie) as archive:
                self.assertIn("STRUCTURE SPORTIVE TEST", _texte_xml(archive, "word/document.xml"))

    def test_remplace_corps_runs_tableaux_entete_pied_et_conserve_ressources(self):
        with tempfile.TemporaryDirectory() as dossier:
            modele = Path(dossier) / "modele.docx"
            sortie = Path(dossier) / "convention.docx"
            _creer_modele(modele)
            resultat = DOCX.GenererDOCX(modele, {
                "{FAMILLE_NOM}": "ATOUT & SPORTS",
                "{CONVENTION_PLANNING_DETAIL}": "Lundi\nMardi",
                "{ORGANISATEUR_NOM}": "PMSL 35",
                "{CONVENTION_DATE_SIGNATURE}": datetime.date(2026, 10, 5),
            }, nomDoc=sortie, afficherDoc=False)

            self.assertEqual(Path(resultat), sortie)
            self.assertTrue(modele.exists())
            with zipfile.ZipFile(sortie) as archive:
                corps = _texte_xml(archive, "word/document.xml")
                self.assertIn("Famille : ATOUT & SPORTS", corps)
                self.assertIn("LundiMardi", corps)
                self.assertEqual(_texte_xml(archive, "word/header1.xml"), "PMSL 35")
                self.assertEqual(_texte_xml(archive, "word/footer1.xml"), "05/10/2026")
                self.assertEqual(archive.read("word/media/logo.png"), b"PNG-INCHANGE")
                racine = etree.fromstring(archive.read("word/document.xml"))
                self.assertEqual(len(racine.xpath(".//w:br", namespaces={"w": W})), 1)

    def test_refuse_un_faux_docx(self):
        with tempfile.TemporaryDirectory() as dossier:
            modele = Path(dossier) / "modele.docx"
            modele.write_text("pas un zip", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "docx valide"):
                DOCX.GenererDOCX(modele, {"{FAMILLE_NOM}": "X"}, afficherDoc=False)

    def test_refuse_un_modele_sans_champ_et_supprime_la_sortie(self):
        with tempfile.TemporaryDirectory() as dossier:
            modele = Path(dossier) / "modele.docx"
            sortie = Path(dossier) / "sortie.docx"
            _creer_modele(modele, sans_champ=True)
            with self.assertRaisesRegex(ValueError, "aucun champ Noethys"):
                DOCX.GenererDOCX(
                    modele, {"{FAMILLE_NOM}": "X"}, nomDoc=sortie, afficherDoc=False
                )
            self.assertFalse(sortie.exists())

    CHAMPS = {
        "{FAMILLE_NOM}": "ATOUT & SPORTS",
        "{CONVENTION_PLANNING_DETAIL}": "Lundi",
        "{ORGANISATEUR_NOM}": "PMSL 35",
        "{CONVENTION_DATE_SIGNATURE}": datetime.date(2026, 10, 5),
    }

    def test_refuse_un_mot_cle_inconnu_sans_toucher_la_destination(self):
        with tempfile.TemporaryDirectory() as dossier:
            modele = Path(dossier) / "modele.docx"
            sortie = Path(dossier) / "convention.docx"
            _creer_modele(modele, champ_inconnu=True)
            sortie.write_bytes(b"ancien document")
            with self.assertRaisesRegex(ValueError, r"mots-clés inconnus : \{CHAMP_LIBRE\}"):
                DOCX.GenererDOCX(modele, self.CHAMPS, nomDoc=sortie, afficherDoc=False)
            self.assertEqual(sortie.read_bytes(), b"ancien document")
            self.assertEqual(sorted(p.name for p in Path(dossier).iterdir()), ["convention.docx", "modele.docx"])

    def test_une_valeur_inseree_n_est_pas_prise_pour_un_mot_cle(self):
        with tempfile.TemporaryDirectory() as dossier:
            modele = Path(dossier) / "modele.docx"
            sortie = Path(dossier) / "convention.docx"
            _creer_modele(modele)
            champs = dict(self.CHAMPS, **{"{FAMILLE_NOM}": u"Club {PAS_UN_CHAMP}"})
            DOCX.GenererDOCX(modele, champs, nomDoc=sortie, afficherDoc=False)
            with zipfile.ZipFile(sortie) as archive:
                self.assertIn(u"Famille : Club {PAS_UN_CHAMP}", _texte_xml(archive, "word/document.xml"))

    def test_ecriture_atomique_remplace_la_destination_sans_fichier_temporaire(self):
        with tempfile.TemporaryDirectory() as dossier:
            modele = Path(dossier) / "modele.docx"
            sortie = Path(dossier) / "convention.docx"
            _creer_modele(modele)
            sortie.write_bytes(b"ancien document")
            DOCX.GenererDOCX(modele, self.CHAMPS, nomDoc=sortie, afficherDoc=False)
            self.assertTrue(zipfile.is_zipfile(sortie))
            self.assertEqual(sorted(p.name for p in Path(dossier).iterdir()), ["convention.docx", "modele.docx"])

    def test_echec_d_ecriture_conserve_l_ancien_document(self):
        with tempfile.TemporaryDirectory() as dossier:
            modele = Path(dossier) / "modele.docx"
            sortie = Path(dossier) / "convention.docx"
            _creer_modele(modele)
            sortie.write_bytes(b"ancien document")
            with unittest.mock.patch.object(DOCX.os, "replace", side_effect=PermissionError("document ouvert dans Word")):
                with self.assertRaisesRegex(ValueError, "n'a pas pu être enregistré"):
                    DOCX.GenererDOCX(modele, self.CHAMPS, nomDoc=sortie, afficherDoc=False)
            self.assertEqual(sortie.read_bytes(), b"ancien document")
            self.assertEqual(sorted(p.name for p in Path(dossier).iterdir()), ["convention.docx", "modele.docx"])

    def test_ne_peut_pas_ecraser_le_modele(self):
        with tempfile.TemporaryDirectory() as dossier:
            modele = Path(dossier) / "modele.docx"
            _creer_modele(modele)
            with self.assertRaisesRegex(ValueError, "écraser le modèle"):
                DOCX.GenererDOCX(
                    modele, {"{FAMILLE_NOM}": "X"}, nomDoc=modele, afficherDoc=False
                )


if __name__ == "__main__":
    unittest.main()
