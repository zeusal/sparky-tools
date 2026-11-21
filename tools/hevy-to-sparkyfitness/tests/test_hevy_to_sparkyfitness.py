"""Tests for hevy_to_sparkyfitness.py. Standard library only; Python 3.8+.

Run from the repository root:
    python3 -m unittest discover -s tools/hevy-to-sparkyfitness/tests -t tools/hevy-to-sparkyfitness/tests
"""
import csv
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cases import CASES  # noqa: E402

SCRIPT = HERE.parent / "hevy_to_sparkyfitness.py"
FIXTURES = HERE / "fixtures"
EXPECTED = HERE / "expected"

_spec = importlib.util.spec_from_file_location("hevy_to_sparkyfitness", str(SCRIPT))
hevy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hevy)

KG_KM = ["--weight", "kg", "--distance", "km"]


def run(*args, cwd=None):
    """Run the converter as a user would; return (exit code, stdout, stderr)."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                            capture_output=True, text=True, encoding="utf-8",
                            cwd=cwd, env=env)
    return result.returncode, result.stdout, result.stderr


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class TempDirTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def copy_fixture(self, name, as_name=None):
        target = self.tmp / (as_name or name)
        shutil.copyfile(FIXTURES / name, target)
        return target


class GoldenOutputTests(TempDirTestCase):
    """Each synthetic export converts to exactly the expected file."""

    def test_cases(self):
        for name, fixture, options in CASES:
            with self.subTest(case=name):
                out = self.tmp / f"{name}.csv"
                args = [o.replace("{fixtures}", str(FIXTURES)) for o in options]
                code, _, err = run(FIXTURES / fixture, *args, "-o", out)
                self.assertEqual(code, 0, err)
                self.assertEqual(out.read_bytes(), (EXPECTED / f"{name}.csv").read_bytes(),
                                 f"output differs from expected/{name}.csv")

    def test_every_expected_file_has_a_case(self):
        names = {name for name, _, _ in CASES}
        self.assertEqual({p.stem for p in EXPECTED.glob("*.csv")}, names)


class OutputInvariantTests(unittest.TestCase):
    """Rules SparkyFitness's importer relies on, checked on every expected file."""

    def test_invariants(self):
        for path in sorted(EXPECTED.glob("*.csv")):
            with self.subTest(file=path.name):
                with open(path, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    self.assertEqual(reader.fieldnames, hevy.OUT_COLUMNS)
                    rows = list(reader)
                numbers = {}
                for row in rows:
                    self.assertRegex(row["entry_date"], r"^\d{4}-\d{2}-\d{2}$")
                    key = (row["entry_date"], row["exercise_name"])
                    numbers.setdefault(key, []).append(int(row["set_number"]))
                    if row["reps"]:
                        self.assertRegex(row["reps"], r"^\d+$")
                    for column in ("weight", "duration_min", "distance"):
                        self.assertNotIn(",", row[column])
                    if row["weight"].startswith("-"):
                        self.assertEqual(row["exercise_equipment"], "body only",
                                         "negative weights only on bodyweight exercises")
                for key, sets in numbers.items():
                    self.assertEqual(sets, list(range(1, len(sets) + 1)), key)


class DateTests(unittest.TestCase):
    def check(self, stamp, expected_date, expected_minutes, order=None):
        self.assertEqual(hevy.parse_stamp(stamp, order), (expected_date, expected_minutes))

    def test_app_english(self):
        self.check("5 Dec 2025, 11:37", date(2025, 12, 5), 11 * 60 + 37)

    def test_app_italian(self):
        self.check("14 ott 2026, 20:39", date(2026, 10, 14), 20 * 60 + 39)

    def test_app_german_full_month(self):
        self.check("23 Juni 2026, 20:01", date(2026, 6, 23), 20 * 60 + 1)

    def test_website_english_12_hour_clock(self):
        self.check("Dec 27, 2025, 12:04 PM", date(2025, 12, 27), 12 * 60 + 4)
        self.check("Dec 27, 2025, 12:30 AM", date(2025, 12, 27), 30)
        self.check("Jun 11, 2026, 1:05 PM", date(2026, 6, 11), 13 * 60 + 5)

    def test_website_german_and_spanish(self):
        self.check("20.01.2025, 12:00", date(2025, 1, 20), 720)
        self.check("20 ene 2025, 12:00", date(2025, 1, 20), 720)
        self.check("20 ene 2025, 1:00 p. m.", date(2025, 1, 20), 780)

    def test_french_with_accents(self):
        self.check("5 déc. 2025 à 11:37", date(2025, 12, 5), 697)

    def test_year_first(self):
        self.check("2025. 1. 20. 오후 12:00", date(2025, 1, 20), 720)
        self.check("2025年1月20日 下午1:30", date(2025, 1, 20), 13 * 60 + 30)
        self.check("2026-11-14 18:05:00", date(2026, 11, 14), 18 * 60 + 5)

    def test_slash_dates_need_an_order(self):
        self.check("03/12/2023 11:25", date(2023, 12, 3), 685, order="dmy")
        self.check("03/12/2023 11:25", date(2023, 3, 12), 685, order="mdy")
        with self.assertRaises(SystemExit):
            hevy.parse_stamp("03/12/2023 11:25", None)

    def test_two_month_words_are_refused(self):
        with self.assertRaises(SystemExit):
            hevy.parse_stamp("mar. 5 déc. 2025, 11:37", None)

    def test_unsupported_language_is_refused(self):
        with self.assertRaises(SystemExit):
            hevy.parse_stamp("1 янв. 2025 г., 12:00", None)

    def test_file_date_order(self):
        rows = [{"start_time": "05/12/2025 11:37"}, {"start_time": "25/12/2025 11:37"}]
        self.assertEqual(hevy.file_date_order(rows, None), "dmy")
        with self.assertRaises(SystemExit):
            hevy.file_date_order(rows, "mdy")
        with self.assertRaises(SystemExit):
            hevy.file_date_order([{"start_time": "05/12/2025 11:37"}], None)
        self.assertEqual(hevy.file_date_order([{"start_time": "05/12/2025 11:37"}], "mdy"), "mdy")
        self.assertIsNone(hevy.file_date_order([{"start_time": "5 Dec 2025, 11:37"}], None))


class ValueTests(unittest.TestCase):
    def test_number(self):
        self.assertEqual(hevy.number("82.5"), 82.5)
        self.assertEqual(hevy.number("62,5"), 62.5)
        self.assertIsNone(hevy.number(""))
        self.assertIsNone(hevy.number("0"), "Hevy writes 0 for 'not tracked'")
        with self.assertRaises(SystemExit):
            hevy.number("abc")

    def test_fmt(self):
        self.assertEqual(hevy.fmt(10, 0), "10")
        self.assertEqual(hevy.fmt(100.0), "100")
        self.assertEqual(hevy.fmt(82.5), "82.5")
        self.assertEqual(hevy.fmt(0.8333), "0.83")
        self.assertEqual(hevy.fmt(-0.0001), "0")
        self.assertEqual(hevy.fmt(None), "")

    def test_assisted_names(self):
        for name in ("Pull Up (Assisted)", "Trazioni (Assistite)", "Dominadas (Asistidas)",
                     "Klimmzug (Unterstützt)", "Nordic Curl (Band Assisted)", "Pull Up (Band)"):
            self.assertTrue(hevy.is_assisted(name), name)
        for name in ("Pull Up", "Pull Up (Unassisted, weighted belt)", "Bench Press (Barbell)"):
            self.assertFalse(hevy.is_assisted(name), name)


class CommandLineTests(TempDirTestCase):
    def test_default_output_name_and_summary(self):
        export = self.copy_fixture("app_en_lbs_miles.csv", "workout_data.csv")
        code, out, err = run(export, *KG_KM)
        self.assertEqual(code, 0, err)
        self.assertTrue((self.tmp / "workout_data_sparkyfitness.csv").is_file())
        self.assertIn("Wrote 11 sets from 2 workouts (2026-11-05 to 2026-11-14)", out)
        self.assertIn("Units: file in lbs/miles, written in kg/km.", out)
        self.assertIn("Assisted (assistance written as a negative weight): Pull Up (Assisted)", out)
        self.assertIn("Some entries failed to import.", out)

    def test_units_are_required_to_convert(self):
        code, _, err = run(FIXTURES / "app_en_kg_km.csv")
        self.assertNotEqual(code, 0)
        self.assertIn("--weight and --distance are required", err)

    def test_version(self):
        code, out, _ = run("--version")
        self.assertEqual(code, 0)
        self.assertIn(hevy.VERSION, out)

    def test_not_a_hevy_export(self):
        other = self.tmp / "other.csv"
        other.write_text("date,food,calories\n2025-01-01,Apple,95\n", encoding="utf-8")
        code, _, err = run(other, *KG_KM)
        self.assertNotEqual(code, 0)
        self.assertIn("does not look like a Hevy workout export", err)

    def test_empty_exercise_titles(self):
        code, _, err = run(FIXTURES / "empty_exercise_titles.csv", *KG_KM, "-o", self.tmp / "x.csv")
        self.assertNotEqual(code, 0)
        self.assertIn("no exercises", err)
        self.assertFalse((self.tmp / "x.csv").exists())

    def test_ambiguous_excel_dates_ask_for_an_order(self):
        code, _, err = run(FIXTURES / "excel_ambiguous_dates.csv", *KG_KM, "-o", self.tmp / "x.csv")
        self.assertNotEqual(code, 0)
        self.assertIn("--date-order", err)
        code, _, err = run(FIXTURES / "excel_ambiguous_dates.csv", *KG_KM,
                           "--date-order", "dmy", "-o", self.tmp / "x.csv")
        self.assertEqual(code, 0, err)
        self.assertEqual(read_rows(self.tmp / "x.csv")[0]["entry_date"], "2025-12-05")

    def test_never_overwrites_the_export(self):
        export = self.copy_fixture("app_en_kg_km.csv")
        before = export.read_bytes()
        code, _, err = run(export, *KG_KM, "-o", export)
        self.assertNotEqual(code, 0)
        self.assertIn("overwrite the Hevy export", err)
        self.assertEqual(export.read_bytes(), before)

    def test_negative_weight_on_a_loaded_exercise_is_blanked(self):
        code, out, err = run(FIXTURES / "negative_weight_on_barbell.csv", *KG_KM,
                             "-o", self.tmp / "x.csv")
        self.assertEqual(code, 0, err)
        self.assertIn("negative weights left blank", out)

    def test_cp1252_console_does_not_crash(self):
        env = dict(os.environ, PYTHONIOENCODING="cp1252")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(FIXTURES / "app_en_kg_km.csv"), *KG_KM,
             "-o", str(self.tmp / "x.csv")],
            capture_output=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)


class ExerciseTableTests(TempDirTestCase):
    def test_list_writes_a_table_to_fill_in(self):
        export = self.copy_fixture("app_en_kg_km.csv", "workout_data.csv")
        code, out, err = run(export, "--list-exercises")
        self.assertEqual(code, 0, err)
        table = self.tmp / "workout_data_exercises.csv"
        self.assertTrue(table.read_bytes().startswith(b"\xef\xbb\xbf"), "BOM for Excel")
        with open(table, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        kinds = {r["hevy_name"]: r["kind"] for r in rows}
        self.assertEqual(kinds, {
            "Bench Press (Barbell)": "weights",
            "Lateral Raise (Dumbbell)": "weights",
            "Plank": "timed",
            "Pull Up": "bodyweight",
            "Pull Up (Assisted)": "assisted",
            "Running": "cardio",
            "Triceps Rope Pushdown": "weights",
        })
        self.assertTrue(all(r["sparkyfitness_name"] == "" for r in rows))
        self.assertIn("--exercise-map", out)

    def test_listing_again_keeps_filled_names(self):
        export = self.copy_fixture("exercise_table_export.csv", "export.csv")
        table = self.copy_fixture("exercise_table_filled.csv", "export_exercises.csv")
        code, out, err = run(export, "--list-exercises")
        self.assertEqual(code, 0, err)
        self.assertIn("kept 4 names already filled in", out)
        with open(table, newline="", encoding="utf-8-sig") as f:
            filled = {r["hevy_name"]: r["sparkyfitness_name"] for r in csv.DictReader(f)}
        self.assertEqual(filled["Pull Up (Assisted)"], "Pull-up")
        self.assertEqual(filled["Press Banca (Barra)"], "Barbell Bench Press")

    def test_list_never_overwrites_the_export(self):
        export = self.copy_fixture("app_en_kg_km.csv")
        code, _, err = run(export, "--list-exercises", export)
        self.assertNotEqual(code, 0)
        self.assertIn("overwrite the Hevy export", err)

    def test_output_never_overwrites_the_table(self):
        table = self.copy_fixture("exercise_table_filled.csv")
        code, _, err = run(FIXTURES / "exercise_table_export.csv", *KG_KM,
                           "--exercise-map", table, "-o", table)
        self.assertNotEqual(code, 0)
        self.assertIn("overwrite the exercise table", err)

    def test_summary_warns_about_unknown_names(self):
        code, out, err = run(FIXTURES / "exercise_table_export.csv", *KG_KM, "--exercise-map",
                             FIXTURES / "exercise_table_filled.csv", "-o", self.tmp / "x.csv")
        self.assertEqual(code, 0, err)
        self.assertIn("4 Hevy names renamed to 2 SparkyFitness names", out)
        self.assertIn("not in this export (check the spelling): Typo Name", out)

    def write_table(self, rows):
        table = self.tmp / "table.csv"
        with open(table, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["hevy_name", "sparkyfitness_name"])
            writer.writerows(rows)
        return table

    def test_duplicate_names_with_different_targets_are_refused(self):
        table = self.write_table([["Pull Up", "Pull-up"], ["Pull Up", "Chin-up"]])
        code, _, err = run(FIXTURES / "exercise_table_export.csv", *KG_KM,
                           "--exercise-map", table, "-o", self.tmp / "x.csv")
        self.assertNotEqual(code, 0)
        self.assertIn("lists 'Pull Up' twice", err)

    def test_empty_table_is_refused(self):
        table = self.write_table([["Pull Up", ""]])
        code, _, err = run(FIXTURES / "exercise_table_export.csv", *KG_KM,
                           "--exercise-map", table, "-o", self.tmp / "x.csv")
        self.assertNotEqual(code, 0)
        self.assertIn("no sparkyfitness_name is filled in", err)

    def test_chained_names_are_reported(self):
        table = self.write_table([["Press Banca (Barra)", "Bench Press (Barbell)"],
                                  ["Bench Press (Barbell)", "Barbell Bench Press"]])
        code, out, err = run(FIXTURES / "exercise_table_export.csv", *KG_KM,
                             "--exercise-map", table, "-o", self.tmp / "x.csv")
        self.assertEqual(code, 0, err)
        self.assertIn("renames again", out)

    def test_assisted_positive_refuses_mixed_targets(self):
        table = self.write_table([["Pull Up (Assisted)", "Pull-up"],
                                  ["Bench Press (Barbell)", "Pull-up"]])
        code, _, err = run(FIXTURES / "exercise_table_export.csv", *KG_KM, "--assisted-positive",
                           "--exercise-map", table, "-o", self.tmp / "x.csv")
        self.assertNotEqual(code, 0)
        self.assertIn("would both be positive", err)

    def test_kind_follows_the_hevy_name_after_renaming(self):
        export = self.tmp / "export.csv"
        export.write_text(
            '"title","start_time","end_time","description","exercise_title","superset_id",'
            '"exercise_notes","set_index","set_type","weight_kg","reps","distance_km",'
            '"duration_seconds","rpe"\n'
            '"W","5 Dec 2025, 11:37","","","Cycling",,"",0,"normal",,,,1200,\n'
            '"W","5 Dec 2025, 11:37","","","Lat Pulldown (Cable)",,"",0,"normal",,10,,,\n',
            encoding="utf-8")
        table = self.write_table([["Cycling", "Bici estatica"],
                                  ["Lat Pulldown (Cable)", "Jalon al pecho"]])
        code, _, err = run(export, *KG_KM, "--exercise-map", table, "-o", self.tmp / "x.csv")
        self.assertEqual(code, 0, err)
        rows = {r["exercise_name"]: r for r in read_rows(self.tmp / "x.csv")}
        self.assertEqual(rows["Bici estatica"]["exercise_category"], "cardio")
        self.assertEqual(rows["Jalon al pecho"]["exercise_equipment"], "",
                         "a cable exercise with no weight logged is not bodyweight")


class ReadTableTests(unittest.TestCase):
    def test_excel_table_reads_like_the_original(self):
        # Semicolons, CRLF and capitalised headers, as Excel saves in many locales.
        original, _ = hevy.read_exercise_map(str(FIXTURES / "exercise_table_filled.csv"))
        excel, _ = hevy.read_exercise_map(str(FIXTURES / "exercise_table_excel_semicolon.csv"))
        del original["Typo Name"]
        self.assertEqual(excel, original)

    def test_utf16_tab_separated(self):
        rows, encoding = hevy.read_table(str(FIXTURES / "utf16_tab.csv"), "t")
        self.assertEqual(encoding, "utf-16")
        self.assertEqual(rows[0]["exercise_title"], "Squat (Barbell)")


HEADER = ('"title","start_time","end_time","description","exercise_title","superset_id",'
          '"exercise_notes","set_index","set_type","weight_kg","reps","distance_km",'
          '"duration_seconds","rpe"\n')


class OrderAndTotalsTests(TempDirTestCase):
    """Same-day workouts: clock order, ties and distance totals."""

    def convert(self, *rows, extra=()):
        export = self.tmp / "export.csv"
        export.write_text(HEADER + "".join(r + "\n" for r in rows), encoding="utf-8")
        code, out, err = run(export, *KG_KM, *extra, "-o", self.tmp / "out.csv")
        self.assertEqual(code, 0, err)
        return read_rows(self.tmp / "out.csv"), out

    def test_same_day_order_follows_the_clock_not_the_file(self):
        rows, _ = self.convert(
            '"Morning","Dec 5, 2025, 9:00 AM","","","Squat (Barbell)",,"",0,"normal",90,3,,,',
            '"Noon","Dec 5, 2025, 12:15 PM","","","Squat (Barbell)",,"",0,"normal",100,3,,,')
        self.assertEqual([(r["set_number"], r["weight"]) for r in rows], [("1", "90"), ("2", "100")])

    def test_same_minute_workouts_keep_oldest_first(self):
        rows, _ = self.convert(
            '"Second","2026-11-14 18:05:40","","","Squat (Barbell)",,"",0,"normal",100,3,,,',
            '"First","2026-11-14 18:05:00","","","Squat (Barbell)",,"",0,"normal",90,3,,,')
        self.assertEqual([(r["set_number"], r["weight"]) for r in rows], [("1", "90"), ("2", "100")])

    def test_day_distance_is_the_total(self):
        rows, _ = self.convert(
            '"Evening","5 Dec 2025, 18:00","","","Running",,"",0,"normal",,,2,600,',
            '"Morning","5 Dec 2025, 07:00","","","Running",,"",0,"normal",,,3,900,')
        self.assertEqual([r["distance"] for r in rows], ["5", "5"])

    def test_negative_weight_on_unloaded_exercise_is_bodyweight(self):
        rows, _ = self.convert(
            '"W","5 Dec 2025, 11:37","","","Dip",,"",0,"normal",-10,8,,,',
            '"W","5 Dec 2025, 11:37","","","Dip",,"",1,"normal",5,8,,,')
        self.assertEqual([(r["exercise_equipment"], r["weight"]) for r in rows],
                         [("body only", "-10"), ("body only", "5")])

    def write_table(self, rows):
        table = self.tmp / "table.csv"
        table.write_text("hevy_name,sparkyfitness_name\n" + "".join(r + "\n" for r in rows),
                         encoding="utf-8")
        return table

    def test_mapping_to_an_assisted_name_flips_the_sign(self):
        table = self.write_table(["Pull Up Machine,Assisted Pull-up"])
        rows, _ = self.convert(
            '"W","5 Dec 2025, 11:37","","","Pull Up Machine",,"",0,"normal",30,8,,,',
            extra=("--exercise-map", table))
        self.assertEqual(rows[0]["weight"], "-30")

    def test_weighted_bodyweight_kind_survives_renaming(self):
        table = self.write_table(["Pull Up (Weighted),Lastre dominadas"])
        rows, _ = self.convert(
            '"W","5 Dec 2025, 11:37","","","Pull Up (Weighted)",,"",0,"normal",20,5,,,',
            extra=("--exercise-map", table))
        self.assertEqual(rows[0]["exercise_equipment"], "body only")

    def test_non_cp1252_names_print_on_a_cp1252_console(self):
        export = self.tmp / "export.csv"
        export.write_text(HEADER + '"W","5 Dec 2025, 11:37","","","Plank 🧘",,"",0,"normal",,,,60,\n',
                          encoding="utf-8")
        env = dict(os.environ, PYTHONIOENCODING="cp1252")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(export), *KG_KM, "-o", str(self.tmp / "x.csv")],
            capture_output=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"Timed holds: Plank ?", result.stdout)


class MoreDateTests(unittest.TestCase):
    def test_other_languages(self):
        self.assertEqual(hevy.parse_stamp("14 out 2026, 20:39", None)[0], date(2026, 10, 14))
        self.assertEqual(hevy.parse_stamp("5 mrt 2026, 20:39", None)[0], date(2026, 3, 5))
        self.assertEqual(hevy.parse_stamp("5 mei 2026, 20:39", None)[0], date(2026, 5, 5))
        self.assertEqual(hevy.parse_stamp("5 janv. 2026 à 11:37", None)[0], date(2026, 1, 5))
        self.assertEqual(hevy.parse_stamp("2025年1月20日 午後1:30", None), (date(2025, 1, 20), 810))
        self.assertEqual(hevy.parse_stamp("2025年1月20日 上午12:30", None), (date(2025, 1, 20), 30))

    def test_file_date_order_guards(self):
        with self.assertRaises(SystemExit):
            hevy.file_date_order([{"start_time": "12/05/2025 11:37"}], None)
        with self.assertRaises(SystemExit):
            hevy.file_date_order([{"start_time": "25/12/2025 11:37"},
                                  {"start_time": "12/25/2025 11:37"}], None)


class MoreCommandLineTests(TempDirTestCase):
    def test_two_month_words_in_a_file_are_refused(self):
        code, _, err = run(FIXTURES / "two_month_words.csv", *KG_KM, "-o", self.tmp / "x.csv")
        self.assertNotEqual(code, 0)
        self.assertIn("could not read the date", err)
        self.assertFalse((self.tmp / "x.csv").exists())

    def test_list_sets_and_last_done(self):
        export = self.tmp / "export.csv"
        export.write_text(HEADER
                          + '"B","14 Nov 2026, 18:05","","","Squat (Barbell)",,"",0,"normal",100,3,,,\n'
                          + '"B","14 Nov 2026, 18:05","","","Squat (Barbell)",,"",1,"normal",100,3,,,\n'
                          + '"A","5 Nov 2026, 07:30","","","Squat (Barbell)",,"",0,"normal",90,3,,,\n',
                          encoding="utf-8")
        code, _, err = run(export, "--list-exercises", self.tmp / "t.csv")
        self.assertEqual(code, 0, err)
        with open(self.tmp / "t.csv", newline="", encoding="utf-8-sig") as f:
            row = next(csv.DictReader(f))
        self.assertEqual((row["sets"], row["last_done"]), ("3", "2026-11-14"))

    def test_encoding_warnings(self):
        export = self.tmp / "export.csv"
        export.write_bytes((HEADER + '"W","5 Dec 2025, 11:37","","","Café Squat",,"",0,"normal",90,3,,,\n')
                           .encode("cp1252"))
        table = self.tmp / "table.csv"
        table.write_bytes("hevy_name,sparkyfitness_name\nCafé Squat,Squat\n".encode("cp1252"))
        code, out, err = run(export, *KG_KM, "--exercise-map", table, "-o", self.tmp / "x.csv")
        self.assertEqual(code, 0, err)
        self.assertIn("the file was not saved as UTF-8", out)
        self.assertIn("the exercise table was not saved as UTF-8", out)

    def test_listing_again_keeps_names_for_exercises_not_in_the_export(self):
        export = self.copy_fixture("exercise_table_export.csv", "export.csv")
        self.copy_fixture("exercise_table_filled.csv", "export_exercises.csv")
        code, out, err = run(export, "--list-exercises")
        self.assertEqual(code, 0, err)
        self.assertIn("Also kept 1 filled-in names", out)
        with open(self.tmp / "export_exercises.csv", newline="", encoding="utf-8-sig") as f:
            rows = {r["hevy_name"]: r for r in csv.DictReader(f)}
        self.assertEqual(rows["Typo Name"]["sparkyfitness_name"], "Something")
        self.assertEqual(rows["Typo Name"]["sets"], "0")


class FixtureUseTests(unittest.TestCase):
    def test_every_fixture_is_used(self):
        source = Path(__file__).read_text(encoding="utf-8")
        used = {fixture for _, fixture, _ in CASES}
        used |= {p.name for p in FIXTURES.iterdir() if p.name in source}
        self.assertEqual(sorted(p.name for p in FIXTURES.iterdir() if p.name not in used), [])


if __name__ == "__main__":
    unittest.main()
