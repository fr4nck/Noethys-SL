# -*- coding: utf-8 -*-
"""Contrat C17 commun aux deux interfaces, testé sans wx/Qt et sans profil."""
import sqlite3
import unittest

from noethys.Utils import UTILS_Consumption_StateCounts as S


class SharedConsumptionStateTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE consommations(
                IDconso INTEGER PRIMARY KEY, date TEXT,
                IDactivite INTEGER, etat TEXT
            );
            INSERT INTO consommations VALUES
              (1,'2026-09-01',7,'reservation'),
              (2,'2026-09-02',7,'present'),
              (3,'2026-09-03',7,'present'),
              (4,'2026-09-04',7,'absentj'),
              (5,'2026-09-05',7,'absenti'),
              (6,'2026-09-06',7,'attente'),
              (7,'2026-09-07',7,'refus'),
              (8,'2026-09-08',7,NULL),
              (9,'2026-09-09',7,'legacy_unknown'),
              (10,'2026-09-10',8,'present'),
              (11,'2026-12-31',8,NULL),
              (12,'2027-01-01',7,'present');
        """)
        self.db.execute("PRAGMA query_only = ON")

    def sql_result(self, **kwargs):
        sql, params = S.build_state_summary_statement(**kwargs)
        if sql is None:
            return S.make_status_summary(
                year=kwargs["year"],
                activity_id=kwargs.get("activity_id"),
                states=kwargs.get("states", S.ALL_STATES),
            )
        rows = self.db.execute(sql, params).fetchall()
        return S.make_status_summary(
            year=kwargs["year"],
            activity_id=kwargs.get("activity_id"),
            states=kwargs.get("states", S.ALL_STATES),
            grouped_rows=rows,
        )

    def test_contract_codes_exact(self):
        self.assertEqual(S.CONTRACT, "stored-consumption-state-counts/1")
        self.assertEqual(len(S.STATES), 6)
        self.assertEqual(len(S.DISPLAY_STATES), 7)
        self.assertEqual(S.OTHER, "__autres__")
        self.assertEqual(
            S.ALL_STATES,
            {"reservation", "attente", "refus", "present",
             "absentj", "absenti", "__autres__"},
        )

    def test_all_states_count_raw_rows_not_people(self):
        result = self.sql_result(year=2026)
        self.assertEqual(result.total, 11)
        self.assertEqual(len(result.rows), 7)
        counts = {row.code: row.count for row in result.rows}
        self.assertEqual(counts["present"], 3)
        self.assertEqual(counts[S.OTHER], 3)
        self.assertEqual(counts["reservation"], 1)
        self.assertEqual(sum(counts.values()), 11)

    def test_other_includes_null_and_legacy_codes(self):
        result = self.sql_result(year=2026, states={S.OTHER})
        self.assertEqual(result.total, 3)
        self.assertEqual(result.rows[0].label, "Autres / non renseignés")

    def test_filter_is_exact_primary_activity_key(self):
        result = self.sql_result(year=2026, activity_id=7)
        self.assertEqual(result.total, 9)
        self.assertEqual({r.code: r.count for r in result.rows}["present"], 2)
        other = self.sql_result(year=2026, activity_id=8, states={"present"})
        self.assertEqual(other.total, 1)

    def test_start_of_next_year_excluded(self):
        self.assertEqual(self.sql_result(year=2027).total, 1)
        self.assertEqual(self.sql_result(year=2026).total, 11)

    def test_missing_known_category_is_explicit_zero(self):
        result = self.sql_result(year=2027, states={"refus", "present"})
        self.assertEqual({r.code: r.count for r in result.rows}, {
            "refus": 0, "present": 1,
        })

    def test_empty_selection_does_not_produce_sql(self):
        self.assertEqual(
            S.build_state_summary_statement(year=2026, states=[]),
            (None, ()),
        )
        self.assertEqual(
            self.sql_result(year=2026, states=[]).rows, (),
        )

    def test_two_supported_placeholders_same_binds(self):
        sql, bind = S.build_state_summary_statement(
            year=2026, activity_id=7, states={"present", S.OTHER},
        )
        mysql, args = S.build_state_summary_statement(
            year=2026, activity_id=7,
            states={"present", S.OTHER}, placeholder="%s",
        )
        self.assertEqual(sql.count("?"), len(bind))
        self.assertEqual(mysql.count("%s"), len(args))
        self.assertEqual(bind, args)
        self.assertIn("GROUP BY", sql)
        self.assertNotIn("UPDATE", sql.upper())
        self.assertNotIn("DELETE", sql.upper())

    def test_incorrect_filters_rejected_without_query(self):
        cases = [
            {"year": True},
            {"year": 2099},
            {"year": 2026, "activity_id": True},
            {"year": 2026, "activity_id": 0},
            {"year": 2026, "activity_id": -1},
            {"year": 2026, "states": None},
            {"year": 2026, "states": ["present", "' OR 1=1 --"]},
            {"year": 2026, "states": [["present"]]},
            {"year": 2026, "placeholder": ":named"},
        ]
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    S.build_state_summary_statement(**case)

    def test_bad_result_values_fail_closed(self):
        for grouped in (
            [("present", 2), ("present", 3)],
            [("unknown", 2)],
            [("present", -1)],
            [("present", 2.5)],
            [("present", True)],
            [(None, 1)],
        ):
            with self.subTest(grouped=grouped):
                with self.assertRaises(ValueError):
                    S.make_status_summary(
                        year=2026, states={"present"}, grouped_rows=grouped,
                    )

    def test_unselected_code_cannot_enter_result(self):
        with self.assertRaises(ValueError):
            S.make_status_summary(
                year=2026, states={"present"},
                grouped_rows=[("reservation", 1)],
            )

    def test_report_reading_does_not_modify_sqlite(self):
        before = "\n".join(self.db.iterdump())
        for year in (2026, 2027):
            for states in (S.ALL_STATES, {S.OTHER}, {"present"}, set()):
                self.sql_result(year=year, states=states)
        self.assertEqual(before, "\n".join(self.db.iterdump()))


if __name__ == "__main__":
    unittest.main()
