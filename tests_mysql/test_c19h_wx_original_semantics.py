"""C19h : contre-examen du code wx d'origine, sans importer wx.

Les trois fonctions etudiees sont extraites par AST du depot courant.
Le seul SQL utilise par ce banc est sqlite3 :memory: ; les tables, noms
et personnes sont inventes. Aucune mutation du code metier.
"""
from __future__ import annotations

import ast
from contextlib import redirect_stdout
from decimal import Decimal
import io
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
WX = ROOT / "noethys/Dlg/DLG_Factures_generation_selection.py"
DB = ROOT / "noethys/GestionDB.py"
MONEY = ROOT / "noethys/Utils/UTILS_Decimal.py"
FACT = ROOT / "noethys/Utils/UTILS_Facturation.py"
TABLES = ROOT / "noethys/Data/DATA_Tables.py"


def method_from_source(path, class_name, method_name):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    classes = [x for x in tree.body
               if isinstance(x, ast.ClassDef) and x.name == class_name]
    if len(classes) != 1:
        raise AssertionError("Classe historique introuvable ou ambigue")
    matches = [x for x in classes[0].body
               if isinstance(x, ast.FunctionDef) and x.name == method_name]
    if len(matches) != 1:
        raise AssertionError("Methode historique introuvable ou ambigue")
    return matches[0]


def free_function(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    matches = [x for x in tree.body
               if isinstance(x, ast.FunctionDef) and x.name == name]
    if len(matches) != 1:
        raise AssertionError("Fonction historique absente ou ambigue")
    return matches[0]


def compile_function(node, globals_dict):
    # Evaluer uniquement la fonction selectionnee, jamais les imports
    # de l'application ou son code de demarrage.
    single = ast.fix_missing_locations(
        ast.Module(body=[node], type_ignores=[])
    )
    exec(compile(single, "<c19h-extrait-historique>", "exec"), globals_dict)
    return globals_dict[node.name]


def legacy_adapter():
    req_insert = method_from_source(DB, "DB", "ReqInsert")
    req_maj = method_from_source(DB, "DB", "ReqMAJ")
    space = {"_": lambda text: text}
    insert = compile_function(req_insert, space)
    maj = compile_function(req_maj, space)

    class Adapter:
        isNetwork = False
        ReqInsert = insert
        ReqMAJ = maj

        def __init__(self, conn):
            self.connexion = conn
            self.cursor = conn.cursor()

        def Commit(self):
            self.connexion.commit()

        def ExecuterReq(self, sql):
            self.cursor.execute(sql)

        def ResultatReq(self):
            return self.cursor.fetchall()

        def Close(self):
            # Connexion partagee avec le laboratoire en memoire :
            # ce faux Close ne touche ni fichier ni connexion externe.
            self.cursor.close()
    return Adapter


class Progress:
    def Update(self, *args):
        return True

    def Destroy(self):
        pass


def wx_generator(db_factory):
    wx = SimpleNamespace(
        ProgressDialog=lambda *args, **kwargs: Progress(),
        PD_SMOOTH=0, PD_AUTO_HIDE=0, PD_APP_MODAL=0,
    )
    space = {
        "GestionDB": SimpleNamespace(DB=db_factory),
        "UTILS_Identification": SimpleNamespace(GetIDutilisateur=lambda: 7),
        "wx": wx,
        "_": lambda s: s,
    }
    return compile_function(
        method_from_source(WX, "Panel", "SauvegardeFactures"), space
    )


def fake_panel(payer_id=201, prestation_ids=(301, 302),
               total=Decimal("12.01"), paid=Decimal("3.50")):
    infos = {
        "listePrestations": [(10, p) for p in prestation_ids],
        "individus": {10: {"select": True}},
        "liste_activites": [1],
        "total": total,
        "ventilation": paid,
        "date_edition": "2026-11-03",
        "date_echeance": "2026-11-30",
        "date_debut": "2026-10-01",
        "date_fin": "2026-10-31",
    }
    params = {
        "prochain_numero": None, "IDprefixe": None, "IDlot": None,
        "prestations": ["consommation"], "IDregie": None,
        "mention1": "", "mention2": "", "mention3": "",
    }
    tracks = [SimpleNamespace(nomSansCivilite="Famille fictive",
                              IDcompte_payeur=payer_id)]
    ctrl = SimpleNamespace(
        GetTracksCoches=lambda: tracks,
        dictComptes={payer_id: infos},
    )
    return SimpleNamespace(
        parent=SimpleNamespace(dictParametres=params),
        ctrl_factures=ctrl,
        EcritStatusbar=lambda *args: None,
    )


def setup_synthetic_sqlite():
    db = sqlite3.connect(":memory:")
    db.executescript("""
        CREATE TABLE factures (
            IDfacture INTEGER PRIMARY KEY AUTOINCREMENT,
            IDprefixe INTEGER, numero INTEGER, IDcompte_payeur INTEGER,
            date_edition TEXT, date_echeance TEXT, activites TEXT,
            individus TEXT, IDutilisateur INTEGER, date_debut TEXT,
            date_fin TEXT, total REAL, regle REAL, solde REAL,
            IDlot INTEGER, prestations TEXT, IDregie INTEGER,
            mention1 TEXT, mention2 TEXT, mention3 TEXT
        );
        CREATE TABLE prestations (
            IDprestation INTEGER PRIMARY KEY, IDfacture INTEGER NULL
        );
        INSERT INTO prestations VALUES (301,NULL),(302,NULL);
    """)
    return db


def money_func():
    return compile_function(
        free_function(MONEY, "FloatToDecimal"),
        {"decimal": __import__("decimal")},
    )


class C19hWxOriginalSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.conn = setup_synthetic_sqlite()
        self.addCleanup(self.conn.close)

    def run_generator(self, prestations=(301, 302)):
        adapter = legacy_adapter()
        panel = fake_panel(prestation_ids=prestations)
        result = wx_generator(lambda: adapter(self.conn))(panel)
        return result

    def test_original_numbering_is_max_plus_one_before_new_connection(self):
        method = method_from_source(WX, "Panel", "SauvegardeFactures")
        src = ast.unparse(method)
        self.assertIn("SELECT MAX(numero)", src)
        self.assertIn("numero = listeDonnees[0][0] + 1", src)
        self.assertIn("DB.Close()", src)
        self.assertIn("DB = GestionDB.DB()", src)
        self.assertNotIn("FOR UPDATE", src)
        self.assertNotIn("START TRANSACTION", src)

    def test_original_insert_and_update_default_to_individual_commit(self):
        for name in ("ReqInsert", "ReqMAJ"):
            fn = method_from_source(DB, "DB", name)
            self.assertIsInstance(fn.args.defaults[-1], ast.Constant)
            self.assertIs(fn.args.defaults[-1].value, True)
            self.assertIn("self.Commit()", ast.unparse(fn))

    def test_original_update_catches_sql_errors_without_raising(self):
        fn = method_from_source(DB, "DB", "ReqMAJ")
        self.assertTrue(any(isinstance(x, ast.ExceptHandler)
                            for x in ast.walk(fn)))
        self.assertNotIn("raise", ast.unparse(fn))

    def test_actual_wx_method_normal_path_runs_in_memory(self):
        result = self.run_generator()
        self.assertEqual(result, [1])
        self.assertEqual(
            self.conn.execute("SELECT numero FROM factures").fetchall(),
            [(1,)],
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT IDfacture FROM prestations ORDER BY IDprestation"
            ).fetchall(), [(1,), (1,)],
        )

    def test_actual_wx_method_reports_success_despite_partial_sql_error(self):
        self.conn.executescript("""
            CREATE TRIGGER fail_second_link
            BEFORE UPDATE OF IDfacture ON prestations
            WHEN NEW.IDprestation=302
            BEGIN SELECT RAISE(ABORT, 'simulated second link failure'); END;
        """)
        output = io.StringIO()
        with redirect_stdout(output):
            result = self.run_generator()
        self.assertEqual(result, [1])
        self.assertIn("simulated second link failure", output.getvalue())
        self.assertEqual(
            self.conn.execute(
                "SELECT IDprestation,IDfacture FROM prestations "
                "ORDER BY IDprestation"
            ).fetchall(), [(301, 1), (302, None)],
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM factures").fetchone()[0],
            1,
        )

    def test_actual_wx_method_does_not_notice_missing_prestation(self):
        result = self.run_generator(prestations=(301, 99999))
        self.assertEqual(result, [1])
        self.assertEqual(
            self.conn.execute(
                "SELECT IDprestation,IDfacture FROM prestations "
                "ORDER BY IDprestation"
            ).fetchall(), [(301, 1), (302, None)],
        )

    def test_two_max_plus_one_readers_can_reserve_same_number(self):
        # Entrelacement deterministe de DEUX lectures et DEUX inserts ;
        # pas une preuve de course multi-processus sur MySQL reel.
        self.conn.execute(
            "INSERT INTO factures (numero,IDcompte_payeur) VALUES(7,201)"
        )
        self.conn.commit()
        # Deux operateurs effectuent la lecture avant toute insertion.
        next_a = self.conn.execute(
            "SELECT MAX(numero) FROM factures WHERE IDprefixe IS NULL"
        ).fetchone()[0] + 1
        next_b = self.conn.execute(
            "SELECT MAX(numero) FROM factures WHERE IDprefixe IS NULL"
        ).fetchone()[0] + 1
        self.assertEqual(next_a, next_b)
        self.conn.execute(
            "INSERT INTO factures (numero,IDcompte_payeur) VALUES(?,201)",
            (next_a,),
        )
        self.conn.execute(
            "INSERT INTO factures (numero,IDcompte_payeur) VALUES(?,202)",
            (next_b,),
        )
        self.conn.commit()
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM factures WHERE numero=8"
            ).fetchone()[0], 2,
        )

    def test_source_declares_no_unique_invoice_number_index(self):
        source = TABLES.read_text(encoding="utf-8")
        self.assertIn('"numero", "BIGINT"', source)
        self.assertIn('"IDprefixe", "INTEGER"', source)
        tree = ast.parse(source)
        mapping = next(node.value for node in tree.body
                       if isinstance(node, ast.Assign) and
                       any(isinstance(n, ast.Name) and n.id == "DB_INDEX"
                           for n in node.targets))
        indexes = ast.literal_eval(mapping)
        self.assertFalse(any(
            value["table"] == "factures" and
            value["champ"] in ("numero", "IDprefixe")
            for value in indexes.values()
        ))

    def test_source_float_to_decimal_is_evaluated_not_reimplemented(self):
        func = money_func()
        self.assertEqual(str(func(12.005)), "12.01")
        self.assertEqual(str(func(2.675)), "2.67")
        self.assertEqual(str(func(-1.005)), "-1.00")
        self.assertEqual(str(func(None)), "0.00")

    def test_plus_proche_flag_does_not_change_returned_value(self):
        func = money_func()
        self.assertEqual(func(2.675, plusProche=True), func(2.675))
        self.assertEqual(func(12.005, plusProche=True), func(12.005))

    def test_invoice_total_reconverts_decimal_back_to_float(self):
        src = ast.unparse(method_from_source(WX, "Panel", "SauvegardeFactures"))
        self.assertIn("('total', float(total))", src)
        self.assertIn("('regle', float(regle))", src)
        self.assertIn("('solde', float(solde))", src)
        self.assertNotEqual(
            Decimal.from_float(float(Decimal("12.01"))),
            Decimal("12.01"),
        )

    def test_source_recognises_cotisation_condition(self):
        fn = method_from_source(FACT, "Facturation", "GetDonnees")
        predicates = [
            node.test for node in ast.walk(fn)
            if isinstance(node, ast.If)
            and "inclure_cotisations_si_conso" in ast.unparse(node.test)
            and "IDcompte_payeur" in ast.unparse(node.test)
        ]
        self.assertEqual(len(predicates), 1)
        expr = compile(ast.Expression(body=predicates[0]), "<wx-cotisation>", "eval")
        def should_skip(option, category, payer, has):
            return bool(eval(expr, {}, {
                "inclure_cotisations_si_conso": option,
                "categorie": category,
                "IDcompte_payeur": payer,
                "famille_has_prestations_activite": has,
            }))
        self.assertTrue(should_skip(True, "cotisation", 201, {}))
        self.assertFalse(should_skip(True, "cotisation", 201, {201: True}))
        self.assertFalse(should_skip(False, "cotisation", 201, {}))
        self.assertFalse(should_skip(True, "consommation", 201, {}))

    def test_forfait_dates_and_shared_service_remain_out_of_write_scope(self):
        schema = TABLES.read_text(encoding="utf-8")
        self.assertIn('"forfait_date_debut", "DATE"', schema)
        self.assertIn('"forfait_date_fin", "DATE"', schema)
        grid = (ROOT / "noethys/Ctrl/CTRL_Grille_cases.py").read_text(
            encoding="utf-8",
        )
        self.assertIn('if prestation["IDfacture"] and not prestation["forfait_date_debut"]:', grid)
        self.assertIn("forfait_date_debut", FACT.read_text(encoding="utf-8"))

    def test_no_real_database_or_gui_is_opened(self):
        self.assertEqual(
            self.conn.execute("PRAGMA database_list").fetchone()[2], "",
        )
        self.assertNotIn("wx", __import__("sys").modules)
        self.assertFalse(hasattr(self.conn, "connect_production"))


if __name__ == "__main__":
    unittest.main()
