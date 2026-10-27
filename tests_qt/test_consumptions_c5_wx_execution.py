"""C5: exécution du corps original wx Sauvegarde sur une SQLite FICTIVE.

Aucun import wx/GestionDB; la méthode inchangée est extraite de la copie
source du dépôt et exécutée avec des substituts empêchant tout accès externe.
Le résultat est une preuve de comportement sous doubles de test, PAS
un portage de la facturation ni une permission d'enregistrer dans Qt.
"""
from __future__ import annotations

import ast
import copy
import datetime as dt
import re
import sqlite3
import tempfile
import textwrap
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

from noethys_qt.consumptions_core import Consumption
from noethys_qt.consumptions_preparation_core import (
    PreflightSnapshot, assess_transition,
)

METHOD_FNV32_AUDIT = "d4745a0b"
LAB_MARKER = "C5_WX_SAVE_REPLAY_FICTIF_ONLY"
ALLOW_TABLES = frozenset((
    "consommations", "prestations", "deductions", "ventilation",
    "historique", "memo_journee",
))


class SimulatedFailure(RuntimeError):
    pass


def _method_source() -> str:
    path = Path(__file__).resolve().parents[1] / "noethys" / "Ctrl" / "CTRL_Grille.py"
    source = path.read_text(encoding="utf-8")
    anchor = "    def Sauvegarde(self):"
    start = source.index(anchor)
    end = source.index("\n    def SignalerAdhesionsAVerifier(", start)
    return source[start:end]


def _fnv_utf16(text: str) -> str:
    value = 2166136261
    for character in text:
        for unit in character.encode("utf-16-le"):
            # Paired bytes are regrouped into UTF-16 code units below instead.
            pass
        code = ord(character)
        if code > 65535:
            raise AssertionError("Unexpected non-BMP character in wx source")
        value = ((value ^ code) * 16777619) & 0xFFFFFFFF
    return f"{value:08x}"


def _compile_save_method():
    text = _method_source()
    if _fnv_utf16(text) != METHOD_FNV32_AUDIT:
        raise AssertionError(
            "Le corps Sauvegarde wx/qt a changé : renouveler l'audit C5 "
            "avant d'exécuter le banc d'essai."
        )
    tree = ast.parse(textwrap.dedent(text), filename="CTRL_Grille.py:Sauvegarde")
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise AssertionError("Extraction métier wx invalide")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)):
            raise AssertionError("Instruction source non autorisée dans le banc wx")
    return compile(tree, "CTRL_Grille.py:Sauvegarde[C5]", "exec")


class GuardedFixtureDb:
    """Substitut minimal de GestionDB, exclusivement sur base locale jetable."""

    def __init__(self, filename: Path, root: Path, *, fail_on: str | None = None):
        expected = root / "C5_SYNTHETIC.sqlite"
        if (
            filename != expected or filename.is_symlink()
            or filename.resolve() != expected
            or not filename.is_file()
        ):
            raise AssertionError("Chemin externe interdit par la fixture C5")
        self.con = sqlite3.connect(filename)
        self.commits = 0
        self.closed = False
        self.statements: list[tuple[str, str]] = []
        self.fail_on = fail_on
        checked = self.con.execute("PRAGMA database_list").fetchall()
        assert len(checked) == 1 and Path(checked[0][2]).resolve() == expected
        assert self.con.execute("SELECT token FROM c5_marker").fetchone() == (LAB_MARKER,)

    @staticmethod
    def _allow_sql(query: str) -> str:
        match = re.match(r"^\s*(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+([a-z_]+)\b", query, re.I)
        if not match or match.group(2).lower() not in ALLOW_TABLES:
            raise AssertionError("SQL de fixture non autorisé : " + query[:80])
        return match.group(2).lower()

    def Executermany(self, query, values, commit=True):
        table = self._allow_sql(query)
        self.con.executemany(query, values)
        self.statements.append(("many", table))
        if self.fail_on == "after_consumption_update" and table == "consommations" and query.lstrip().upper().startswith("UPDATE"):
            raise SimulatedFailure("Échec simulé avant le premier commit")
        if commit:
            self.Commit()

    def ExecuterReq(self, query):
        table = self._allow_sql(query)
        self.con.execute(query)
        self.statements.append(("query", table))
        return 1  # Fidèle à GestionDB.ExecuterReq : pas de commit implicite.

    def GetProchainID(self, table):
        if table != "prestations":
            raise AssertionError("Table de séquence non autorisée")
        return self.con.execute("SELECT COALESCE(MAX(IDprestation),0)+1 FROM prestations").fetchone()[0]

    def ReqInsert(self, table, data, commit=True):
        if table != "memo_journee":
            raise AssertionError("ReqInsert non autorisé")
        keys = [name for name, _ in data]
        values = [value for _, value in data]
        sql = "INSERT INTO memo_journee (" + ",".join(keys) + ") VALUES (" + ",".join("?" for _ in keys) + ")"
        new_id = self.con.execute(sql, values).lastrowid
        self.statements.append(("insert", table))
        if commit:
            self.Commit()
        return new_id

    def ReqMAJ(self, table, data, key, ident, commit=True):
        if table != "memo_journee" or key != "IDmemo":
            raise AssertionError("ReqMAJ non autorisé")
        names = [name for name, _ in data]
        values = [value for _, value in data] + [ident]
        sql = "UPDATE memo_journee SET " + ",".join(name + "=?" for name in names) + " WHERE IDmemo=?"
        self.con.execute(sql, values)
        self.statements.append(("update", table))
        if commit:
            self.Commit()

    def ReqDEL(self, table, key, ident, commit=True):
        if table != "memo_journee" or key != "IDmemo":
            raise AssertionError("ReqDEL non autorisé")
        self.con.execute("DELETE FROM memo_journee WHERE IDmemo=?", (ident,))
        self.statements.append(("delete", table))
        if commit:
            self.Commit()

    def Commit(self):
        self.con.commit()
        self.commits += 1

    def Close(self):
        if not self.closed:
            self.con.close()
            self.closed = True


class ActualWxSaveReplayTests(unittest.TestCase):
    """Corps de Sauvegarde wx exécuté, mais données et dépendances fictives."""

    @classmethod
    def setUpClass(cls):
        cls.compiled_method = _compile_save_method()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="c5-wx-sauvegarde-fictive-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.path = self.root / "C5_SYNTHETIC.sqlite"
        with closing(sqlite3.connect(self.path)) as con:
            con.executescript("""
                CREATE TABLE c5_marker (token TEXT PRIMARY KEY);
                CREATE TABLE individus (IDindividu INTEGER PRIMARY KEY);
                CREATE TABLE consommations (
                    IDconso INTEGER PRIMARY KEY, IDindividu INTEGER,
                    IDinscription INTEGER, IDactivite INTEGER, date TEXT,
                    IDunite INTEGER, IDgroupe INTEGER, heure_debut TEXT,
                    heure_fin TEXT, etat TEXT, verrouillage INTEGER,
                    date_saisie TEXT, IDutilisateur INTEGER,
                    IDcategorie_tarif INTEGER, IDcompte_payeur INTEGER,
                    IDprestation INTEGER, quantite TEXT, etiquettes TEXT,
                    IDevenement INTEGER, badgeage_debut TEXT, badgeage_fin TEXT
                );
                CREATE TABLE prestations (
                    IDprestation INTEGER PRIMARY KEY, IDcompte_payeur INTEGER,
                    date TEXT, categorie TEXT, label TEXT, montant_initial TEXT,
                    montant TEXT, IDactivite INTEGER, IDtarif INTEGER,
                    IDfacture INTEGER, IDfamille INTEGER, IDindividu INTEGER,
                    temps_facture TEXT, IDcategorie_tarif INTEGER,
                    forfait_date_debut TEXT, forfait_date_fin TEXT,
                    code_compta TEXT, code_produit_local TEXT, tva TEXT,
                    date_valeur TEXT
                );
                CREATE TABLE deductions (
                    IDdeduction INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDprestation INTEGER, IDcompte_payeur INTEGER, date TEXT,
                    montant TEXT, label TEXT, IDaide INTEGER
                );
                CREATE TABLE ventilation (
                    IDventilation INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDprestation INTEGER, montant TEXT
                );
                CREATE TABLE historique (
                    IDaction INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDfamille INTEGER, IDindividu INTEGER,
                    IDcategorie INTEGER, action TEXT
                );
                CREATE TABLE memo_journee (
                    IDmemo INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDindividu INTEGER, date TEXT, texte TEXT, couleur TEXT
                );
                INSERT INTO individus VALUES (10);
                INSERT INTO consommations
                  (IDconso, IDindividu, IDinscription, IDactivite, date,
                   IDunite, IDgroupe, etat, verrouillage, IDprestation)
                VALUES (1, 10, 20, 30, '2026-10-20', 11, 40, 'reservation', 0, 101);
                INSERT INTO prestations
                  (IDprestation, label, montant, montant_initial)
                VALUES (101, 'Séance fictive', '12.00', '12.00');
                INSERT INTO ventilation (IDprestation, montant)
                VALUES (101, '0.00');
            """)
            con.execute("INSERT INTO c5_marker VALUES (?)", (LAB_MARKER,))
            con.commit()
        self.case = self._make_case()
        self.grid = SimpleNamespace(
            dictPrestations={}, dictDeductions={},
            listePrestationsModifiees=[], listePrestationsSupprimees=[],
            dictConsoIndividus={10: {dt.date(2026, 10, 20): {11: [self.case]}}},
            listeConsoSupprimees=[], dictUnites={11: {"abrege": "SF"}},
            dictMemos={}, IDutilisateur=7,
        )
        self.database = None

    @staticmethod
    def _make_case(*, etat="present", statut="modification", ident=1, prestation=101):
        return SimpleNamespace(
            statut=statut, IDconso=ident, IDinscription=20,
            IDactivite=30, IDgroupe=40, heure_debut=None, heure_fin=None,
            etat=etat, date_saisie=dt.date(2026, 10, 27),
            IDutilisateur=7, IDcategorie_tarif=8,
            IDcompte_payeur=9, IDprestation=prestation,
            quantite=1, etiquettes=[], IDevenement=None,
            badgeage_debut=None, badgeage_fin=None, IDfamille=50,
        )

    def _snapshot(self):
        with closing(sqlite3.connect(self.path)) as con:
            return {
                table: con.execute("SELECT * FROM " + table + " ORDER BY rowid").fetchall()
                for table in (
                    "consommations", "prestations", "deductions",
                    "ventilation", "historique", "memo_journee"
                )
            }

    def _run_wx(self, *, fail_on=None):
        database = GuardedFixtureDb(self.path, self.root, fail_on=fail_on)
        self.database = database

        def insert_history(actions, DB):
            if fail_on == "history":
                raise SimulatedFailure("Service historique factice interrompu")
            if DB is not database:
                raise AssertionError("Connexion DB non autorisée")
            for action in actions:
                database.Executermany(
                    "INSERT INTO historique (IDfamille, IDindividu, IDcategorie, action) VALUES (?,?,?,?)",
                    [(action["IDfamille"], action["IDindividu"], action["IDcategorie"], action["action"])],
                    commit=False,
                )

        forbidden = lambda *_args, **_kw: (_ for _ in ()).throw(
            AssertionError("Adhésions automatiques interdites au C5")
        )
        globals_dict = {
            "__builtins__": {
                "len": len, "str": str, "list": list, "tuple": tuple,
                "dict": dict, "int": int, "Exception": Exception,
            },
            "GestionDB": SimpleNamespace(DB=lambda: database),
            "copy": copy,
            "datetime": dt,
            "ConvertListeToStr": lambda x: ";".join(str(v) for v in x),
            "UTILS_Historique": SimpleNamespace(InsertActions=insert_history),
            "UTILS_Adhesions": SimpleNamespace(
                AUTO_CREATION_SUSPENDUE=True,
                ReconcilierSansEchec=forbidden,
            ),
        }
        exec(self.compiled_method, globals_dict)
        try:
            globals_dict["Sauvegarde"](self.grid)
        finally:
            database.Close()
        return database

    def test_wx_source_method_pinned_and_no_implicit_financial_guards(self):
        text = _method_source()
        self.assertEqual(_fnv_utf16(text), METHOD_FNV32_AUDIT)
        self.assertEqual(text.count("DB.Commit()"), 2)
        self.assertIn("AUTO_CREATION_SUSPENDUE", text)
        self.assertIn("listePrestationsModifiees", text)
        self.assertIn("listeConsoSupprimees", text)
        self.assertNotIn("VerificationDroitsUtilisateurActuel", text)
        self.assertNotIn('gestion.Verification("consommations"', text)

    def test_unchanged_row_produces_no_write_or_history(self):
        self.case.etat = "reservation"
        self.case.statut = None
        before = self._snapshot()
        db = self._run_wx()
        self.assertEqual(before, self._snapshot())
        self.assertEqual(db.statements, [])
        self.assertEqual(db.commits, 2)

    def test_actual_save_modifies_existing_consumption_and_history(self):
        before = self._snapshot()
        db = self._run_wx()
        after = self._snapshot()
        self.assertNotEqual(before["consommations"], after["consommations"])
        self.assertEqual(after["consommations"][0][9], "present")
        self.assertEqual(after["consommations"][0][10], 0)
        self.assertEqual(after["consommations"][0][15], 101)
        self.assertEqual(after["prestations"], before["prestations"])
        self.assertEqual(after["ventilation"], before["ventilation"])
        self.assertEqual(len(after["historique"]), 1)
        self.assertEqual(after["historique"][0][3], 29)
        self.assertEqual(db.commits, 2)

    def test_real_legacy_save_inserts_consumption_in_fixture(self):
        self.case = self._make_case(etat="reservation", statut="ajout", ident=None)
        self.grid.dictConsoIndividus = {10: {dt.date(2026, 10, 21): {11: [self.case]}}}
        db = self._run_wx()
        after = self._snapshot()
        self.assertEqual(len(after["consommations"]), 2)
        self.assertEqual(len(after["historique"]), 1)
        self.assertEqual(after["historique"][0][3], 9)
        self.assertEqual(db.commits, 2)

    def test_real_legacy_save_deletes_consumption_in_fixture(self):
        self.case.statut = "suppression"
        self.case.etat = None
        self._run_wx()
        after = self._snapshot()
        self.assertEqual(len(after["consommations"]), 0)
        self.assertEqual(len(after["historique"]), 1)
        self.assertEqual(after["historique"][0][3], 10)

    def test_modified_prestation_removes_ventilation_in_same_first_phase(self):
        self.grid.listePrestationsModifiees = [101]
        self.grid.dictPrestations[101] = {
            "label": "Corrigée", "montant_initial": "13.00",
            "montant": "13.00", "forfait_date_debut": None,
            "forfait_date_fin": None, "code_compta": None,
            "code_produit_local": None, "tva": None,
        }
        self._run_wx()
        after = self._snapshot()
        self.assertEqual(after["prestations"][0][4], "Corrigée")
        self.assertEqual(after["ventilation"], [])
        self.assertEqual(len(after["historique"]), 1)

    def test_sql_failure_before_first_commit_has_no_persistent_effect(self):
        before = self._snapshot()
        with self.assertRaises(SimulatedFailure):
            self._run_wx(fail_on="after_consumption_update")
        self.assertEqual(before, self._snapshot())
        self.assertEqual(self.database.commits, 0)

    def test_history_failure_after_first_commit_leaves_partial_write(self):
        before = self._snapshot()
        with self.assertRaises(SimulatedFailure):
            self._run_wx(fail_on="history")
        after = self._snapshot()
        self.assertNotEqual(after["consommations"], before["consommations"])
        self.assertEqual(after["consommations"][0][9], "present")
        self.assertEqual(after["historique"], [])
        self.assertEqual(self.database.commits, 1)

    def test_qt_preflight_is_still_unexecutable_despite_wx_reference(self):
        shown = Consumption(
            consumption_id=1, date=dt.date(2026, 10, 20), state="reservation",
            activity="Fictive", unit="Séance", group="Jeunes",
            last_name="Enfant", first_name="Fictif",
            start_time=None, end_time=None, prestation_id=101, amount=None,
            individual_id=10, activity_id=30,
        )
        snapshot = PreflightSnapshot(
            consumption_id=1, date="2026-10-20", state="reservation",
            locked=0, forfait=None, prestation_id=101,
            individual_id=10, activity_id=30, inscription_id=20,
            event_id=None, prestation_exists=True, invoice_id=None,
            forfait_start=None, ventilation_rows=0,
        )
        preview = assess_transition(shown, "present", snapshot)
        self.assertFalse(preview.executable)
        codes = {issue.code for issue in preview.issues}
        self.assertIn("DROITS_NON_VERIFIES", codes)
        self.assertIn("PERIODE_NON_VERIFIEE", codes)
        self.assertIn("FACTURATION_NON_RACCORDEE", codes)

    def test_adapter_rejects_path_outside_own_temporary_directory(self):
        with tempfile.TemporaryDirectory() as foreign:
            external = Path(foreign) / "C5_SYNTHETIC.sqlite"
            with closing(sqlite3.connect(external)) as con:
                con.execute("CREATE TABLE sentinel (id INT)")
                con.commit()
            with self.assertRaises(AssertionError):
                GuardedFixtureDb(external, self.root)
            with closing(sqlite3.connect(external)) as con:
                self.assertEqual(
                    con.execute("SELECT name FROM sqlite_master WHERE name='sentinel'").fetchone(),
                    ("sentinel",),
                )


if __name__ == "__main__":
    unittest.main()
