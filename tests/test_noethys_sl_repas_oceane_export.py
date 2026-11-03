# -*- coding: utf-8 -*-
"""Régression Océane : ZIP XLSX sans dépendance, sans données personnelles."""
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
import hashlib
import os
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
from Utils import UTILS_Oceane_xlsx as X
from Utils import UTILS_Repas_oceane_menus as Menus
from Utils import UTILS_Repas_oceane_export as E
from Utils.UTILS_Repas_totaux import TotauxRepas

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
F = lambda x: "{%s}%s" % (NS, x)

SITE_CODES = (("LGB",7011),("MOUT",7012),("Bais",7077))
LIBELLES = E.LIGNES_LIBELLES


def _fichier(path, feuilles, sstrings=False):
    """Classeur OpenXML minimal avec styles vides, sans formule ni macros."""
    workbook = ET.Element(F("workbook"))
    shs = ET.SubElement(workbook, F("sheets"))
    relroot = ET.Element("{%s}Relationships" % PKG)
    payloads = {}
    for i, (name, cells) in enumerate(feuilles.items(), 1):
        ET.SubElement(shs, F("sheet"), {
            "name": name, "sheetId": str(i), "{%s}id" % REL: "rId%d" % i})
        ET.SubElement(relroot, "{%s}Relationship" % PKG, {
            "Id": "rId%d" % i, "Type": REL + "/worksheet",
            "Target": "worksheets/sheet%d.xml" % i})
        worksheet = ET.Element(F("worksheet"))
        data = ET.SubElement(worksheet, F("sheetData"))
        rows = {}
        for coord, valeur in cells.items():
            rownum = int("".join(c for c in coord if c.isdigit()))
            row = rows.get(rownum)
            if row is None:
                row = ET.SubElement(data, F("row"), {"r": str(rownum)})
                rows[rownum] = row
            el = ET.SubElement(row, F("c"), {"r": coord})
            if valeur is None:
                continue
            if isinstance(valeur, int):
                v = ET.SubElement(el, F("v"))
                v.text = str(valeur)
            elif isinstance(valeur, tuple) and valeur[0] == "shared":
                el.set("t", "s")
                ET.SubElement(el, F("v")).text = str(valeur[1])
            else:
                el.set("t", "inlineStr")
                ET.SubElement(ET.SubElement(el, F("is")), F("t")).text = str(valeur)
        payloads["xl/worksheets/sheet%d.xml" % i] = ET.tostring(worksheet)
    with ZipFile(path, "w", ZIP_DEFLATED) as z:
        z.writestr("xl/workbook.xml", ET.tostring(workbook))
        z.writestr("xl/_rels/workbook.xml.rels", ET.tostring(relroot))
        z.writestr("xl/metadata_test.bin", b"KEEP-UNRELATED-CONTENT")
        if sstrings:
            ss=ET.Element(F("sst"))
            ET.SubElement(ET.SubElement(ss,F("si")),F("t")).text="    "
            z.writestr("xl/sharedStrings.xml",ET.tostring(ss))
        for name, data in payloads.items():
            z.writestr(name, data)


def _modele(path):
    feuilles = {}
    for site, code in SITE_CODES:
        cells = {"B2": code, "B27": code, "C4": ("shared", 0),
                 "C29": ("shared",0)}
        for shift in (0,25):
            cells["I%d"%(6+shift)] = "MERCREDI"
            for lettre, nom in (("I","M"),("J","P"),("K","A")):
                cells["%s%d"%(lettre,7+shift)] = nom
            for row, nom in LIBELLES.items():
                cells["A%d"%(row+shift)] = nom
                for lettre in "IJK":
                    cells["%s%d"%(lettre,row+shift)] = None
            for adr in ("E%d"%(4+shift),"J%d"%(4+shift),
                        "J%d"%(21+shift)):
                cells[adr]=None
        feuilles[site] = cells
    _fichier(path, feuilles, sstrings=True)


def _cas(site, day=date(2026,11,4)):
    return {"date":day, "site":site, "service":"midi",
            "totaux":TotauxRepas(8,25,animateurs_repas=3,direction_repas=1),
            "variantes":{
                "sans_porc":{"M":1,"P":2},
                "sans_viande":{"M":0,"P":1},
                "vegetarien":{"M":1,"P":3},
                "sans_allergene":{"M":0,"P":0}}}


class ExcelOceaneTests(unittest.TestCase):
    def setUp(self):
        self.dossier=TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        self.modele=Path(self.dossier.name)/"modele.xlsx"
        self.output=Path(self.dossier.name)/"commande.xlsx"
        _modele(self.modele)

    def test_export_reel_trois_sites_et_mercredi(self):
        precedent=hashlib.sha256(self.modele.read_bytes()).hexdigest()
        lignes=[_cas(s) for s in ("LGB","MOUT","Bais")]
        result=E.ExporterBordereau(self.modele,self.output,lignes)
        self.assertEqual(result["total_M"],24)
        self.assertEqual(result["total_P"],87)
        self.assertEqual(result["adultes_inclus_P"],12)
        donnees,_=X.LireClasseur(self.output)
        self.assertEqual(set(donnees), {"LGB","MOUT","Bais"})
        for s in ("LGB","MOUT","Bais"):
            self.assertEqual(donnees[s]["I8"],8)
            self.assertEqual(donnees[s]["J9"],29)
            self.assertEqual(donnees[s]["I17"],1)
            self.assertEqual(donnees[s]["J19"],3)
            self.assertEqual(donnees[s]["C4"],45)
            self.assertEqual(donnees[s]["E4"],"02/11/2026")
            self.assertEqual(donnees[s]["J4"],"06/11/2026")
            self.assertNotIn("K8",donnees[s])
            self.assertNotIn("K9",donnees[s])
        self.assertEqual(hashlib.sha256(self.modele.read_bytes()).hexdigest(),precedent)
        with ZipFile(self.modele) as z1,ZipFile(self.output) as z2:
            self.assertEqual(z1.read("xl/metadata_test.bin"),
                             z2.read("xl/metadata_test.bin"))
            self.assertEqual(z1.read("xl/sharedStrings.xml"),
                             z2.read("xl/sharedStrings.xml"))

    def test_second_mercredi_memes_onglets_bloc2(self):
        items=[_cas("Bais"),_cas("Bais",date(2026,11,11))]
        E.ExporterBordereau(self.modele,self.output,items)
        cellules,_=X.LireClasseur(self.output,noms=["Bais"])
        s=cellules["Bais"]
        self.assertEqual((s["I8"],s["I33"],s["J34"]), (8,8,29))
        self.assertEqual(s["C29"],46)
        self.assertEqual(s["E29"],"09/11/2026")
        self.assertNotIn("K33",s)

    def test_saisie_grammages_dans_commentaire_sans_modifier_modele(self):
        e=_cas("Bais")
        e["grammages"]={"plat":{"M":90,"P":110}}
        E.ExporterBordereau(self.modele,self.output,[e])
        d,_=X.LireClasseur(self.output,noms=["Bais"])
        self.assertIn("90 g",d["Bais"]["J21"])
        self.assertIn("110 g",d["Bais"]["J21"])

    def test_refuse_plus_de_deux_semaines_et_site_double(self):
        with self.assertRaises(ValueError):
            E.ExporterBordereau(self.modele,self.output,[
                _cas("Bais",date(2026,11,4)),
                _cas("Bais",date(2026,11,11)),
                _cas("Bais",date(2026,11,18))])
        with self.assertRaises(ValueError):
            E.ExporterBordereau(self.modele,self.output,[
                _cas("Bais"),_cas("Bais")])
        self.assertFalse(self.output.exists())

    def test_refuse_variante_incomplete_et_modele_deja_renseigne(self):
        e=_cas("Bais")
        del e["variantes"]["sans_viande"]
        with self.assertRaises(ValueError):
            E.ExporterBordereau(self.modele,self.output,[e])
        self.assertFalse(self.output.exists())
        e=_cas("Bais")
        E.ExporterBordereau(self.modele,self.output,[e])
        with self.assertRaises(ValueError):
            E.ExporterBordereau(self.output,self.modele,[e])

    def test_refuse_ecraser_modele_source_et_dates_non_mercredi(self):
        with self.assertRaises(ValueError):
            E.ExporterBordereau(self.modele,self.modele,[_cas("Bais")])
        with self.assertRaises(ValueError):
            E.ExporterBordereau(self.modele,self.output,[
                _cas("Bais",date(2026,11,3))])

    def test_lecture_menus_detailles_et_affichages_dates(self):
        path=Path(self.dossier.name)/"menus.xlsx"
        def serial(date_):return (date_-date(1899,12,30)).days
        _fichier(path,{
            "Menus Mat & prim":{
                "E3":serial(date(2026,5,20)),
                "E4":"Salade coleslaw","E5":"Concombre à l'estragon",
                "E9":"Agneau","E10":"Tarte végétarienne",
                "E12":"Salade verte","E13":"Riz","E15":"Brie",
                "E18":"Fruit de saison"},
            "Semaine 45":{
                "G6":serial(date(2026,11,4)),
                "G7":"Salade tropicale","G8":"Carotte & ananas",
                "G9":"Sauté de porc","G11":"Semoule",
                "G13":"Petit suisse","G15":"Compote"}
        })
        menus=Menus.ChargerMenus(path)
        self.assertEqual(len(menus),2)
        self.assertEqual(menus[date(2026,5,20)]["plat"],
                         ["Agneau","Tarte végétarienne"])
        self.assertEqual(menus[date(2026,11,4)]["source"],"Semaine 45")
        self.assertEqual(menus[date(2026,11,4)]["entree"],
                         ["Salade tropicale — Carotte & ananas"])
        self.assertTrue(Menus.PresentationMenu(menus[date(2026,11,4)]))
        self.assertNotIn("2026-05-27",str(menus))


if __name__ == "__main__":
    unittest.main()
