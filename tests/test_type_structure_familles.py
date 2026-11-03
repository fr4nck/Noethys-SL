# -*- coding: utf-8 -*-
"""Tests isoles du classement d'entites dans les dossiers familles Noethys."""
import importlib.util
from pathlib import Path
import sqlite3
import unittest

RACINE = Path(__file__).resolve().parents[1]
CHEMIN = RACINE / "noethys" / "Utils" / "UTILS_Type_structure.py"
SPEC = importlib.util.spec_from_file_location("types_entites_tests", CHEMIN)
TYPES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TYPES)


class TypesEntitesTests(unittest.TestCase):
    def test_01_tous_les_types_attendus(self):
        codes = [code for code, libelle in TYPES.TYPES_STRUCTURE]
        self.assertEqual(codes[0], None)
        self.assertEqual(len(codes), len(set(codes)))
        self.assertTrue({"ecole", "association", "association_sportive",
                         "collectivite", "institution", "entreprise", "autre"}
                        .issubset(set(codes)))
        self.assertTrue(all(libelle for code, libelle in TYPES.TYPES_STRUCTURE))

    def test_02_conversion_reversible(self):
        for i, (code, libelle) in enumerate(TYPES.TYPES_STRUCTURE):
            with self.subTest(code=code):
                self.assertEqual(TYPES.CodeDepuisIndex(i), code)
                self.assertEqual(TYPES.IndexDepuisCode(code), i)
                self.assertEqual(TYPES.LibelleDepuisCode(code), libelle)
        self.assertEqual(TYPES.IndexDepuisCode(""), 0)

    def test_03_codes_inconnus_non_ecrases(self):
        for code in ("school", "COMMUNE", "ecole_ancienne", 8, True):
            with self.subTest(code=code), self.assertRaises(ValueError):
                TYPES.IndexDepuisCode(code)
        for i in (-1, len(TYPES.TYPES_STRUCTURE), "1", True, None):
            with self.subTest(i=i), self.assertRaises(ValueError):
                TYPES.CodeDepuisIndex(i)

    def test_04_migration_sqlite_conserve_dossiers(self):
        con = sqlite3.connect(":memory:")
        self.addCleanup(con.close)
        con.execute("CREATE TABLE familles (IDfamille INTEGER PRIMARY KEY, nom TEXT)")
        con.executemany("INSERT INTO familles VALUES (?, ?)", [
            (1, "Famille fictive"), (2, "Ecole fictive"), (3, "Association fictive")])
        avant = con.execute("SELECT IDfamille, nom FROM familles ORDER BY IDfamille").fetchall()
        sql = (RACINE / "noethys" / "Data" / "Migrations"
               / "familles_type_structure_sqlite.sql").read_text(encoding="utf-8")
        con.executescript(sql)
        self.assertIn("type_structure", [c[1] for c in con.execute("PRAGMA table_info(familles)")])
        self.assertEqual(con.execute("SELECT IDfamille, nom FROM familles ORDER BY IDfamille").fetchall(), avant)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM familles WHERE type_structure IS NOT NULL")
                         .fetchone()[0], 0)
        con.execute("UPDATE familles SET type_structure = ? WHERE IDfamille = 2", ("ecole",))
        con.execute("UPDATE familles SET type_structure = ? WHERE IDfamille = 3", ("association",))
        self.assertEqual(con.execute("SELECT type_structure FROM familles WHERE IDfamille = 2").fetchone()[0],
                         "ecole")
        self.assertEqual(con.execute("SELECT type_structure FROM familles WHERE IDfamille = 1").fetchone()[0],
                         None)

    def test_05_aucun_changement_du_schema_factures(self):
        for filename in ("familles_type_structure_sqlite.sql", "familles_type_structure_mysql57.sql"):
            sql = (RACINE / "noethys" / "Data" / "Migrations" / filename).read_text(encoding="utf-8")
            ddl = [x.strip().upper() for x in sql.splitlines() if x.strip().upper().startswith("ALTER TABLE")]
            self.assertEqual(len(ddl), 1)
            self.assertTrue(ddl[0].startswith("ALTER TABLE FAMILLES ADD COLUMN TYPE_STRUCTURE"))
            self.assertNotIn("FACTURES", sql.upper())
            self.assertNotIn("PRESTATIONS", sql.upper())


    def test_06_interface_wx_raccordee_sans_creer_un_second_annuaire(self):
        contenu = (RACINE / "noethys" / "Dlg"
                   / "DLG_Famille_divers.py").read_text(encoding="utf-8")
        for marqueur in ('name="type_structure"', 'GetListeChamps2("familles")',
                         'EnableProperty("type_structure"',
                         'listeDonnees.append(("type_structure",'):
            with self.subTest(marqueur=marqueur):
                self.assertIn(marqueur, contenu)

    def test_07_schema_natif_contient_le_type(self):
        contenu = (RACINE / "noethys" / "Data"
                   / "DATA_Tables.py").read_text(encoding="utf-8")
        debut = contenu.index('    "familles":')
        self.assertIn('("type_structure", "VARCHAR(40)"', contenu[debut:debut + 350])


    def test_08_fiche_divers_est_valide_et_enregistre_le_choix(self):
        """Contrat syntaxique qui aurait detecte la regression d'indentation."""
        import ast
        chemin = RACINE / "noethys" / "Dlg" / "DLG_Famille_divers.py"
        source = chemin.read_text(encoding="utf-8")
        ast.parse(source, filename=str(chemin))
        self.assertIn('name="type_structure"', source)
        self.assertIn('infos[:12]', source)
        self.assertIn('if self.type_structure_modifiable:', source)
        self.assertIn('listeDonnees.append(("type_structure",', source)
        self.assertIn('DB.ReqMAJ("familles", listeDonnees, "IDfamille", self.IDfamille)', source)

    def test_09_requalification_en_association_ne_modifie_pas_la_fiche(self):
        """Un ancien dossier personne/groupe conserve ses identifiants."""
        con = sqlite3.connect(":memory:")
        self.addCleanup(con.close)
        con.execute(
            "CREATE TABLE familles (IDfamille INTEGER PRIMARY KEY, "
            "IDcompte_payeur INTEGER, nom TEXT)"
        )
        con.execute("INSERT INTO familles VALUES (23, 47, 'Groupe fictif')")
        avant = con.execute(
            "SELECT IDfamille, IDcompte_payeur, nom FROM familles WHERE IDfamille=23"
        ).fetchone()
        sql = (RACINE / "noethys" / "Data" / "Migrations"
               / "familles_type_structure_sqlite.sql").read_text(encoding="utf-8")
        con.executescript(sql)
        con.execute(
            "UPDATE familles SET type_structure=? WHERE IDfamille=?",
            ("association", 23),
        )
        apres = con.execute(
            "SELECT IDfamille, IDcompte_payeur, nom, type_structure "
            "FROM familles WHERE IDfamille=23"
        ).fetchone()
        self.assertEqual(apres[:3], avant)
        self.assertEqual(apres[3], "association")
        con.execute(
            "UPDATE familles SET type_structure=? WHERE IDfamille=?",
            ("association_sportive", 23),
        )
        self.assertEqual(
            con.execute("SELECT type_structure FROM familles WHERE IDfamille=23").fetchone()[0],
            "association_sportive",
        )


if __name__ == "__main__":
    unittest.main()
