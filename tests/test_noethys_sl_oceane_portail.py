# -*- coding: utf-8 -*-
"""Import self-service des menus Océane dans Noethys et Connecthys.

Aucun réseau, aucune base réelle, aucune publication effective.
"""
from datetime import date, datetime
from pathlib import Path
import sqlite3
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))

from Utils import UTILS_Repas_oceane_publication as P
from Utils import UTILS_Repas_oceane_import_db as Imp


def exemple():
    return {
        date(2026,11,4): {
            "source": "Semaine 45", "entree": ["Salade des tropiques"],
            "plat": ["Sauté de porc BBC sauce forestière ℗"],
            "garniture": ["Semoule HVE"],
            "laitage": ["Petit suisse sucré x1"],
            "dessert": ["Purée de pommes pêches BIO"],
        },
        date(2026,11,18): {
            "source": "Semaine 47", "entree": ["Betteraves BIO vinaigrette"],
            "plat": ["Rôti de porc BBC sauce aux herbes"],
            "garniture": ["Boulgour BIO à la tomate"],
            "laitage": ["Yaourt sucré BIO"],
            "dessert": ["Fruit de saison"],
        },
    }


class MenuPureTests(unittest.TestCase):
    def test_selection_dates_non_vides_et_sans_affichage_blanc(self):
        menus = exemple()
        menus[date(2026,11,11)] = {"source":"Semaine 46"}
        resultat = P.PreparerMenus(menus, [date(2026,11,4), date(2026,11,18)])
        self.assertEqual(len(resultat),2)
        self.assertEqual(resultat[date(2026,11,4)]["plat"],
                         ["Sauté de porc BBC sauce forestière ℗"])
        self.assertNotIn(date(2026,11,11),resultat)
        with self.assertRaises(ValueError):
            P.PreparerMenus(menus,[date(2026,11,11)])
        with self.assertRaises(ValueError):
            P.PreparerMenus(menus,[])
        with self.assertRaises(ValueError):
            P.PreparerMenus(menus,[date(2026,11,5)])
        with self.assertRaises(ValueError):
            P.PreparerMenus({},None)

    def test_html_public_sans_donnees_de_commandes(self):
        menus = exemple()
        menus[date(2026,11,4)]["plat"] = [
            "<script>window.location='attaque'</script>", "Sauté de porc"]
        html = P.HTMLPortail(menus)
        self.assertNotIn("<script>",html)
        self.assertIn("&lt;script&gt;",html)
        self.assertIn("Menus des mercredis",html)
        self.assertIn("Fromage / laitage",html)
        for token in ("animateurs_repas","grammages","num_allocataire",
                      "sans_porc","adulte_dans_P","prix"):
            self.assertNotIn(token, html)
        self.assertEqual(html.count("<h3>Mercredi"),2)
        self.assertIn("MERCREDI 04/11/2026",P.TextePortail(menus))
        self.assertIn("18/11/2026",P.TitrePortail(menus))
        self.assertEqual(P.DateFinPublication(menus).date(),date(2026,11,25))

    def test_plan_categories_reutilise_les_existantes(self):
        cats = [(7,"Hors d'oeuvre"),(8,"Plats chauds"),(9,"Légumes"),
                (10,"Fromages"),(11,"Desserts")]
        plan = P.PlanifierImport(exemple(),cats,[])
        self.assertEqual(plan["creer_categories"], [])
        self.assertEqual(len(plan["ajouter"]),10)
        self.assertEqual(plan["categories_existantes"]["plat"],8)
        existants = [(101,7,date(2026,11,4),"Salade des tropiques")]
        plan = P.PlanifierImport(exemple(),cats,existants)
        self.assertEqual(len(plan["identiques"]),1)
        self.assertEqual(len(plan["ajouter"]),9)
        plan = P.PlanifierImport(exemple(),cats,[(101,7,"2026-11-04","Autre plat")])
        self.assertEqual(len(plan["conflits"]),1)

    def test_categories_ambiguës_refusees(self):
        cats=[(1,"Plat"),(2,"Plat chaud")]
        with self.assertRaises(ValueError):
            P.PlanifierImport(exemple(),cats,[])


class DBFictive:
    isNetwork = False
    echec = 0
    def __init__(self):
        self.connexion=sqlite3.connect(":memory:")
        self.cursor=self.connexion.cursor()
        self.connexion.executescript("""
            CREATE TABLE menus_categories(
                IDcategorie INTEGER PRIMARY KEY, nom TEXT, ordre INTEGER);
            CREATE TABLE menus(
                IDmenu INTEGER PRIMARY KEY, IDrestaurateur INTEGER,
                IDcategorie INTEGER, date TEXT, texte TEXT);
            INSERT INTO menus_categories(IDcategorie, nom, ordre)
                VALUES (7,'Entrée',1);
        """)
    def ReqInsert(self, table, data, commit=True):
        # L'interface historique Noethys retourne None en cas d'échec.
        colonnes = [k for k,_ in data]
        values=[v for _,v in data]
        try:
            self.cursor.execute(
                "INSERT INTO %s (%s) VALUES (%s)" %
                (table,",".join(colonnes),",".join("?" for _ in data)),
                values)
            if commit:
                self.connexion.commit()
            return self.cursor.lastrowid
        except sqlite3.DatabaseError:
            return None
    def Commit(self):
        self.connexion.commit()


class ImportSQLiteTests(unittest.TestCase):
    def setUp(self):
        self.db=DBFictive()
        self.addCleanup(self.db.connexion.close)

    def test_insert_transactionnel_et_second_import_idempotent(self):
        result=Imp.Enregistrer(self.db,21,exemple())
        self.assertEqual(result["ajoutes"],10)
        self.assertEqual(result["categories_creees"],4)
        self.assertEqual(self.db.cursor.execute(
            "SELECT COUNT(*) FROM menus").fetchone()[0],10)
        self.assertEqual(self.db.cursor.execute(
            "SELECT COUNT(*) FROM menus_categories").fetchone()[0],5)
        again=Imp.Enregistrer(self.db,21,exemple())
        self.assertEqual(again["ajoutes"],0)
        self.assertEqual(again["identiques"],10)
        self.assertEqual(self.db.cursor.execute(
            "SELECT COUNT(*) FROM menus").fetchone()[0],10)

    def test_id_restaurateur_etranger_non_touche(self):
        Imp.Enregistrer(self.db,21,exemple())
        Imp.Enregistrer(self.db,22,exemple())
        self.assertEqual(self.db.cursor.execute(
            "SELECT COUNT(*) FROM menus WHERE IDrestaurateur=21").fetchone()[0],10)
        self.assertEqual(self.db.cursor.execute(
            "SELECT COUNT(*) FROM menus WHERE IDrestaurateur=22").fetchone()[0],10)

    def test_conflit_refuse_toutes_les_modifications(self):
        Imp.Enregistrer(self.db,21,exemple())
        self.db.cursor.execute(
            "UPDATE menus SET texte='Corrigé par opérateur' "
            "WHERE IDrestaurateur=21 AND date='2026-11-04' AND IDcategorie=7")
        self.db.connexion.commit()
        debut=self.db.connexion.total_changes
        with self.assertRaises(ValueError):
            Imp.Enregistrer(self.db,21,exemple())
        self.assertEqual(self.db.connexion.total_changes,debut)
        self.assertEqual(self.db.cursor.execute(
            "SELECT texte FROM menus WHERE IDcategorie=7 AND "
            "IDrestaurateur=21 AND date='2026-11-04'").fetchone()[0],
            "Corrigé par opérateur")

    def test_rollback_en_cas_d_echec_en_milieu_d_import(self):
        # Une contrainte artificielle interdit l'un des inserts :
        # aucune catégorie ni aucun menu ne doit être conservé.
        self.db.connexion.execute("""
          CREATE TRIGGER refus_plat BEFORE INSERT ON menus
          WHEN NEW.texte LIKE '%Sauté%' BEGIN
            SELECT RAISE(FAIL,'test');
          END
        """)
        self.db.connexion.commit()
        with self.assertRaises(RuntimeError):
            Imp.Enregistrer(self.db,21,exemple())
        self.assertEqual(self.db.cursor.execute(
            "SELECT COUNT(*) FROM menus").fetchone()[0],0)
        self.assertEqual(self.db.cursor.execute(
            "SELECT COUNT(*) FROM menus_categories").fetchone()[0],1)

    def test_identifiant_restaurateur_invalide(self):
        for bad in (-1,0,None,True,"21"):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                Imp.Enregistrer(self.db,bad,exemple())


class IntegrationsSourceTests(unittest.TestCase):
    def test_ui_menus_ouvre_dialogue_natif_blog_sans_synchro_auto(self):
        source=(ROOT/"noethys/Dlg/DLG_Menus.py").read_text(encoding="utf-8")
        self.assertIn("Importer menus Océane (ou déposer XLSX)",source)
        self.assertIn("CibleFichierOceane(wx.FileDropTarget)",source)
        self.assertIn("DLG_Saisie_portail_bloc.Dialog(self",source)
        self.assertIn('SetPageByCode("bloc_blog")',source)
        self.assertIn("portail",source)
        self.assertNotIn(".Synchroniser(",source)


if __name__=="__main__":
    unittest.main()
