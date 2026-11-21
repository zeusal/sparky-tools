#!/usr/bin/env python3
"""Convert a Hevy workout export (CSV) into SparkyFitness's Workout History CSV.

Hevy (free or Pro) exports workouts from the app (Profile > Settings >
Export & Import Data > Export Data > Export Workouts -> workout_data.csv) or
from the website (hevy.com/settings?export -> workouts.csv). SparkyFitness's
Workout History importer cannot read that file directly: the dates include a
time of day and the column names differ. This script rewrites it into the
importer's own template columns.

Usage:
    python hevy_to_sparkyfitness.py workout_data.csv --weight kg --distance km

    --weight kg|lbs       The weight unit set in SparkyFitness (Settings >
                          Preferences). The importer reads weights in that unit.
    --distance km|miles   The distance unit set in SparkyFitness.
    -o OUTPUT.csv         Output file (default: <input>_sparkyfitness.csv).
    --exercise-map T.csv  Use exercises you already have (see below).
    --date-order dmy|mdy  Only for a file re-saved in Excel whose dates look
                          like 03/12/2023, when the file itself cannot tell.
    --assisted-positive   Keep the assistance of assisted exercises (e.g. Pull
                          Up (Assisted)) as a positive number. By default it is
                          written as a negative weight on a bodyweight exercise,
                          which is how SparkyFitness records assistance. Use
                          this only when SparkyFitness already has the exercise
                          as a weighted one and you want the number shown as
                          the weight.

Then in SparkyFitness: Settings > Data Import > Workout History (CSV) >
Import, choose the output file, press Process File, check the preview and
import. Leave the format options on Auto-detect.

Using exercises you already have in SparkyFitness (optional):
SparkyFitness reuses an exercise only when its name is exactly the same,
capitals included; any other name becomes a new exercise, and SparkyFitness
cannot merge exercises afterwards. To log Hevy's history under exercises you
already have:

    python hevy_to_sparkyfitness.py workout_data.csv --list-exercises

writes workout_data_exercises.csv with one row per Hevy exercise. Fill in the
sparkyfitness_name column with the exact SparkyFitness name (leave it empty to
keep the Hevy name; several Hevy names can share one SparkyFitness name), save
it as CSV UTF-8, then convert with the table:

    python hevy_to_sparkyfitness.py workout_data.csv --weight kg --distance km
        --exercise-map workout_data_exercises.csv

On a SparkyFitness server shared with other people, an exercise someone else
shared publicly under exactly the same name can be used instead of yours. If
history lands on the wrong exercise, give yours a name only you use.

Only the Python standard library is used (Python 3.8 or newer).
"""
import argparse
import csv
import functools
import io
import os
import re
import sys
import unicodedata
from datetime import date

VERSION = "1.2"

LB_PER_KG = 2.20462262185
KM_PER_MILE = 1.609344
# SparkyFitness converts a lbs or miles profile's numbers to kg and km with
# these factors; dividing by them makes the stored value match the file.
SERVER_KG_PER_LB = 0.453592
SERVER_KM_PER_MILE = 1.60934

# Hevy's set types -> the labels SparkyFitness's web app offers (the same
# mapping the Hevy API sync uses, except failure, which the web lists as
# 'Failure').
SET_TYPES = {
    "normal": "Working Set",
    "warmup": "Warm-up",
    "dropset": "Drop Set",
    "failure": "Failure",
}

# Month names and abbreviations in the languages Hevy exports dates in
# (lower case, without accents or dots). Hevy writes month names in the app's
# or website's language.
_MONTHS = {
    1: "jan january janv janvier ene enero gen gennaio januar janeiro januari jaen",
    2: "feb february fev fevr fevrier febrero febbraio februar fevereiro februari",
    3: "mar march mars marzo marz maerz marco maart mrt",
    4: "apr april avr avril abr abril aprile",
    5: "may mai mag maggio mayo maio mei",
    6: "jun june juin junio giu giugno juni junho",
    7: "jul july juil juillet julio lug luglio juli julho",
    8: "aug august aout ago agosto",
    9: "sep sept september septembre septiembre set settembre setembro",
    10: "oct october octobre octubre ott ottobre okt oktober out outubro",
    11: "nov november novembre noviembre novembro",
    12: "dec december decembre dic diciembre dicembre dez dezember dezembro",
}
MONTHS = {name: num for num, names in _MONTHS.items() for name in names.split()}
PM_WORDS = ("오후", "下午", "午後", "晚上")
AM_WORDS = ("오전", "上午", "午前", "凌晨", "早上")

# Word starts in exercise names (accents removed). Cardio words decide
# whether an exercise that records only a time is cardio or a timed hold such
# as Plank; loaded words mark an exercise as weighted even when no weight was
# logged; assisted words cover Hevy's translated '(Assisted)'.
CARDIO_WORDS = (
    "run", "jog", "walk", "hiking", "cycling", "bike", "spinning", "elliptical",
    "treadmill", "rowing", "stair", "swim", "ski", "jump rope", "skipping",
    "sprint", "cardio", "aerobic", "climb", "step", "boxing", "hiit",
    "battle rope", "dance", "kayak", "skating",
    "corsa", "camminata", "cyclette", "ciclismo", "tapis roulant", "correr",
    "carrera", "caminar", "bicicleta", "laufen", "gehen", "radfahren", "fahrrad",
    "course", "marche", "velo", "corrida", "caminhada", "hardlopen", "fietsen",
    "wandelen",
)
LOADED_WORDS = (
    "barbell", "dumbbell", "machine", "cable", "kettlebell", "smith", "plate",
    "band", "weighted", "ez bar", "trap bar", "sandbag", "landmine", "sled",
)
ASSISTED_RE = re.compile(r"\b(assist|asist|unterstutzt)|^pull up \(band\)$")
# Hevy's bodyweight exercises with added load ("Weighted" variants of other
# exercises, such as Russian Twist (Weighted), are ordinary weighted ones).
WEIGHTED_BODYWEIGHT = {
    "chest dip (weighted)", "chin up (weighted)", "crunch (weighted)",
    "decline crunch (weighted)", "pull up (weighted)", "push up (weighted)",
    "sit up (weighted)", "triceps dip (weighted)",
    "back extension (weighted hyperextension)",
}

OUT_COLUMNS = [
    "entry_date", "exercise_name",
    "exercise_force", "exercise_level", "exercise_mechanic",
    "exercise_category", "exercise_equipment", "entry_notes",
    "set_number", "set_type", "reps", "weight", "duration_min",
    "distance", "set_notes",
]


def fail(message):
    sys.exit("Error: " + message)


def plain(text):
    """Lower case without accents or dots: 'Déc.' -> 'dec'."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c)).replace(".", "")


@functools.lru_cache(maxsize=None)
def has_word(name, words):
    name = plain(name)
    return any(re.search(r"\b" + re.escape(w), name) for w in words)


def is_assisted(name):
    return ASSISTED_RE.search(plain(name)) is not None


def name_words(name):
    """The words of an exercise name, for comparing names: lower case, no
    accents, plurals made singular ('Pull-Ups' -> ['pull', 'up'])."""
    words = []
    for w in re.findall(r"[^\W_]+", plain(name)):
        if len(w) > 4 and re.search(r"(ch|sh|x|ss)es$", w):
            w = w[:-2]
        elif len(w) > 2 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        words.append(w)
    return words


def similar_names(names):
    """Groups of names that are probably one exercise written differently:
    other capitals, accents, hyphens or spaces, a plural, or the same words in
    another order ('Pull Up', 'Pull-ups', 'Pullup'; 'Bench Press (Barbell)',
    'Barbell Bench Press'). Each group is sorted; groups by their first name."""
    parent = {}

    def root(name):
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    first_with = {}
    for name in names:
        parent.setdefault(name, name)
        words = name_words(name)
        if not words:
            continue
        for key in (("same words",) + tuple(sorted(words)), ("written together", "".join(words))):
            if key in first_with:
                parent[root(name)] = root(first_with[key])
            else:
                first_with[key] = name
    groups = {}
    for name in parent:
        groups.setdefault(root(name), []).append(name)
    return sorted((sorted(g, key=str.lower) for g in groups.values() if len(g) > 1),
                  key=lambda g: g[0].lower())


def apart(groups, name_of):
    """The groups whose names don't all end up as one exercise."""
    return [g for g in groups if len({name_of(n) for n in g}) > 1]


def list_groups(groups):
    return "; ".join(" = ".join(g) for g in groups)


def file_date_order(rows, requested):
    """For dates like 03/12/2023 (a file re-saved in Excel), decide once for
    the whole file which number is the day, so no row is swapped silently."""
    pairs = []
    for row in rows:
        m = re.match(r"\s*(\d{1,2})[/-](\d{1,2})[/-]\d{4}", row.get("start_time") or "")
        if m:
            pairs.append((int(m.group(1)), int(m.group(2))))
    if not pairs:
        return requested
    dmy = any(a > 12 for a, _ in pairs)
    mdy = any(b > 12 for _, b in pairs)
    if dmy and mdy:
        fail("the dates mix day/month and month/day; use the original file from Hevy")
    found = "dmy" if dmy else ("mdy" if mdy else None)
    if found and requested and requested != found:
        fail(f"the dates in this file are {found}, not {requested}; use --date-order {found}")
    if not found and not requested:
        fail("the dates look like 03/12/2023 or 03-12-2023, which could be day/month or month/day. "
             "This happens when the export was opened and saved in Excel. Use the "
             "original file from Hevy, or add --date-order dmy (or mdy).")
    return found or requested


def parse_stamp(stamp, date_order):
    """Hevy timestamp -> (date, minutes after midnight, whether a time was read).

    Shapes seen in real exports: '5 Dec 2025, 11:37' (app), '14 ott 2026,
    20:39' (app in Italian), 'Dec 27, 2025, 12:04 PM' (website, English),
    '20.01.2025, 12:00' (website, German), '20 ene 2025, 12:00' (website,
    Spanish), '2025. 1. 20. 오후 12:00' (website, Korean), ISO dates, and
    '03/12/2023 11:25' after a re-save in Excel.
    """
    raw = stamp.strip()
    time_match = re.search(r"(\d{1,2}):(\d{2})", raw)
    minutes = 0
    if time_match:
        hour, minute = int(time_match.group(1)), int(time_match.group(2))
        low = raw.lower()
        pm = re.search(r"\bp\.?\s?m\b", low) or any(w in raw for w in PM_WORDS)
        am = re.search(r"\ba\.?\s?m\b", low) or any(w in raw for w in AM_WORDS)
        if pm and hour < 12:
            hour += 12
        elif am and hour == 12:
            hour = 0
        minutes = hour * 60 + minute
        date_part = raw[: time_match.start()]
    else:
        date_part = raw
    numbers = [int(n) for n in re.findall(r"\d+", date_part)]
    words = [plain(w) for w in re.findall(r"[^\W\d_]+", date_part)]
    month_words = {MONTHS[w] for w in words if w in MONTHS}
    try:
        if numbers and len(re.match(r"\D*(\d+)", date_part).group(1)) == 4:
            year, month, day = numbers[0], numbers[1], numbers[2]  # 2025-01-20, 2025. 1. 20.
        elif len(month_words) == 1:
            years = [n for n in numbers if n >= 1000]
            days = [n for n in numbers if n < 1000]
            year, month, day = years[0], month_words.pop(), days[0]
        elif not month_words and re.search(r"\d{1,2}\.\d{1,2}\.\d{4}", date_part):
            day, month, year = numbers[0], numbers[1], numbers[2]  # 20.01.2025
        elif not month_words and date_order and re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{4}", date_part):
            first, second, year = numbers[0], numbers[1], numbers[2]
            day, month = (first, second) if date_order == "dmy" else (second, first)
        else:
            raise ValueError
        return date(year, month, day), minutes
    except (ValueError, IndexError, AttributeError):
        fail(
            f"could not read the date '{raw}'. Export again from the Hevy app or "
            "website (in English if possible) without editing the file."
        )


def number(text):
    """A Hevy number cell, or None when it is blank or zero (Hevy writes 0 for
    'not tracked' on some sets, e.g. duration_seconds on strength sets)."""
    text = (text or "").strip()
    if not text:
        return None
    if re.fullmatch(r"-?\d+,\d+", text):
        text = text.replace(",", ".")  # decimal comma after an Excel re-save
    try:
        value = float(text)
    except ValueError:
        fail(f"'{text}' is not a number")
    return value if value != 0 else None


def fmt(value, places=2):
    if value is None:
        return ""
    text = f"{value:.{places}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def one_line(text):
    return " ".join(text.replace("\\n", " ").split())


def read_table(path, what):
    """Rows of a CSV that may have been re-saved by Excel: UTF-8 (with or
    without BOM), UTF-16, or a Windows encoding, separated by commas,
    semicolons or tabs."""
    with open(path, "rb") as f:
        utf16 = f.read(2) in (b"\xff\xfe", b"\xfe\xff")
    for encoding in (("utf-16",) if utf16 else ("utf-8-sig", "cp1252")):
        try:
            with open(path, newline="", encoding=encoding) as f:
                text = f.read()
            break
        except UnicodeDecodeError:
            continue
    else:
        fail(f"could not read {what} as text")
    first_line = re.split(r"\r\n|\r|\n", text, maxsplit=1)[0]
    delimiter = max((",", ";", "\t"), key=first_line.count)
    return list(csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter)), encoding


def read_exercise_map(path, require_filled=True):
    """The two-column table written by --list-exercises, filled in by hand:
    hevy_name -> sparkyfitness_name."""
    if not os.path.isfile(path):
        fail(f"exercise table not found: {path}")
    rows, encoding = read_table(path, f"the exercise table {path}")
    columns = {(c or "").strip().lower(): c for c in (rows[0].keys() if rows else [])}
    if "hevy_name" not in columns or "sparkyfitness_name" not in columns:
        fail(f"the exercise table {path} needs the columns hevy_name and "
             "sparkyfitness_name (create it with --list-exercises)")
    mapping = {}
    for row in rows:
        hevy = (row.get(columns["hevy_name"]) or "").strip()
        sparky = (row.get(columns["sparkyfitness_name"]) or "").strip()
        if hevy and sparky:
            if mapping.get(hevy, sparky) != sparky:
                fail(f"the exercise table lists '{hevy}' twice, as '{mapping[hevy]}' "
                     f"and as '{sparky}'; keep one of them")
            mapping[hevy] = sparky
    if require_filled and rows and not mapping:
        fail(f"no sparkyfitness_name is filled in {path}. If Excel showed each row in "
             "a single column, open the file with Data > From Text/CSV (or use "
             "LibreOffice or Google Sheets), fill in the names and save it as CSV UTF-8.")
    return mapping, encoding


def exercise_kind(t, assisted_positive):
    """How SparkyFitness should show an exercise the import creates:
    - cardio: distance or time with no reps or weight (a timed hold such as
      Plank when the name is not a cardio activity);
    - bodyweight: assisted exercises (negative weight = assistance), Hevy's
      '(Weighted)' bodyweight moves (positive weight = added load), and reps
      with no weight unless the name says the exercise is loaded;
    - weights: anything else (weight x reps).
    SparkyFitness accepts a negative weight only on a bodyweight exercise."""
    if (t["distance"] or t["time"]) and not t["reps"] and not t["weight"]:
        return "cardio" if t["distance"] or t["cardio_word"] else "timed"
    if t["assisted"]:
        if assisted_positive:
            return "weights" if t["weight"] else "bodyweight"
        return "assisted"
    if t["weighted_bw"]:
        return "bodyweight"
    if t["negative"] or (t["reps"] and not t["weight"] and not t["loaded_word"]):
        return "bodyweight"
    return "weights"


CATEGORY = {
    "cardio": ("cardio", ""),
    "timed": ("isometric", ""),
    "assisted": ("strength", "body only"),
    "bodyweight": ("strength", "body only"),
    "weights": ("strength", ""),
}


def collect_traits(parsed, key):
    traits = {}
    for p in parsed:
        t = traits.setdefault(p[key], {"distance": False, "weight": False, "reps": False,
                                       "time": False, "negative": False, "assisted": False,
                                       "cardio_word": False, "loaded_word": False,
                                       "weighted_bw": False, "sets": 0, "last": p["day"]})
        # Words are read from the Hevy name and from the name it is written
        # as, so a renamed exercise keeps its kind.
        names = (p["hevy_name"], p[key])
        loaded = any(has_word(n, LOADED_WORDS) for n in names)
        t["cardio_word"] |= any(has_word(n, CARDIO_WORDS) for n in names)
        t["loaded_word"] |= loaded
        t["weighted_bw"] |= any(plain(n) in WEIGHTED_BODYWEIGHT for n in names)
        t["distance"] |= p["distance"] is not None
        t["weight"] |= p["weight"] is not None
        # A stray negative weight on a barbell or machine exercise must not
        # turn its whole history into bodyweight.
        t["negative"] |= p["weight"] is not None and p["weight"] < 0 and not loaded
        t["reps"] |= p["reps"] is not None
        t["time"] |= p["seconds"] is not None
        t["assisted"] |= p["assisted"]
        t["sets"] += 1
        t["last"] = max(t["last"], p["day"])
    return traits


def write_exercise_list(parsed, path, input_path, assisted_positive):
    """One row per Hevy exercise name with a sparkyfitness_name column to fill
    in. Written with a BOM so Excel opens emojis and accents right. Names
    already filled in an existing table are kept, and new Hevy names added."""
    traits = collect_traits(parsed, "hevy_name")
    filled = {}
    if os.path.exists(path):
        if os.path.samefile(path, input_path):
            fail("the exercise table would overwrite the Hevy export; give it another name")
        filled, _ = read_exercise_map(path, require_filled=False)
    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["hevy_name", "sparkyfitness_name", "sets", "last_done", "kind"])
            for name in sorted(traits, key=str.lower):
                t = traits[name]
                writer.writerow([name, filled.get(name, ""), t["sets"], t["last"].isoformat(),
                                 exercise_kind(t, assisted_positive)])
            # Names filled in for exercises this export doesn't have (for
            # example from an older export) stay, so no work is lost.
            others = sorted((n for n in filled if n not in traits and filled[n]), key=str.lower)
            for name in others:
                writer.writerow([name, filled[name], 0, "", ""])
    except OSError as error:
        fail(f"could not write {path} ({error.strerror}). Close it in Excel or "
             "choose another name.")
    kept = sum(1 for name in traits if filled.get(name))
    print(f"Wrote {len(traits)} Hevy exercise names to {path}"
          + (f" (kept {kept} names already filled in)" if kept else ""))
    if others:
        print(f"Also kept {len(others)} filled-in names for exercises that aren't in this "
              "export, with 0 sets.")
    shown = f'"{path}"' if " " in path else path
    print("Fill in the sparkyfitness_name column with the exact name of the "
          "SparkyFitness exercise to use (same spelling and capitals), or leave it "
          "empty to keep the Hevy name. Several Hevy names can share one "
          "SparkyFitness name: their sets become one exercise. In Excel, save it as "
          "'CSV UTF-8'. Then run the conversion again with --exercise-map " + shown)
    alike = apart(similar_names(traits), lambda n: filled.get(n) or n)
    if alike:
        print("These Hevy names look like the same exercise: " + list_groups(alike)
              + ". To make each group one exercise in SparkyFitness, give its names "
              "the same sparkyfitness_name.")


def main():
    # A Windows console or redirect may not take emojis in exercise names.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    parser = argparse.ArgumentParser(
        description="Convert a Hevy workout CSV export into SparkyFitness's Workout History CSV."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("input", help="Hevy export (workout_data.csv or workouts.csv)")
    parser.add_argument("-o", "--output", help="output file (default: <input>_sparkyfitness.csv)")
    parser.add_argument("--weight", choices=["kg", "lbs"],
                        help="weight unit set in SparkyFitness (required to convert)")
    parser.add_argument("--distance", choices=["km", "miles"],
                        help="distance unit set in SparkyFitness (required to convert)")
    parser.add_argument("--list-exercises", nargs="?", const="", metavar="TABLE.csv",
                        help="only write the table of Hevy exercise names to fill in "
                             "(default: <input>_exercises.csv)")
    parser.add_argument("--exercise-map", metavar="TABLE.csv",
                        help="the filled-in table: use these SparkyFitness names")
    parser.add_argument("--date-order", choices=["dmy", "mdy"],
                        help="only for files re-saved in Excel with dates like 03/12/2023")
    parser.add_argument("--assisted-positive", action="store_true",
                        help="keep the assistance of assisted exercises positive, for "
                             "exercises SparkyFitness already has as weighted ones")
    args = parser.parse_args()
    listing = args.list_exercises is not None
    if not listing and (not args.weight or not args.distance):
        parser.error("--weight and --distance are required to convert "
                     "(use the units set in SparkyFitness)")

    if not os.path.isfile(args.input):
        fail(f"file not found: {args.input}")
    rows, encoding = read_table(args.input, "the file")
    if not rows:
        fail("the file has no workouts")
    header = set(rows[0].keys())
    needed = {"title", "start_time", "exercise_title", "set_index", "set_type", "reps"}
    if not needed <= header:
        fail("this does not look like a Hevy workout export (missing columns: "
             + ", ".join(sorted(needed - header)) + ")")
    weight_col = next((c for c in ("weight_kg", "weight_lbs") if c in header), None)
    distance_col = next((c for c in ("distance_km", "distance_miles") if c in header), None)
    file_weight = "lbs" if weight_col == "weight_lbs" else "kg"
    file_distance = "miles" if distance_col == "distance_miles" else "km"
    date_order = file_date_order(rows, args.date_order)

    def cell(row, column):
        return (row.get(column) or "") if column else ""

    mapping, map_encoding = ({}, None)
    if args.exercise_map and not listing:
        mapping, map_encoding = read_exercise_map(args.exercise_map)

    # Parse every row once and keep the file order inside each workout.
    parsed = []
    for index, row in enumerate(rows):
        hevy_name = (row.get("exercise_title") or "").strip()
        if not hevy_name:
            continue
        name = mapping.get(hevy_name, hevy_name)
        day, minutes = parse_stamp(row.get("start_time") or "", date_order)
        parsed.append({
            "row": row, "hevy_name": hevy_name, "name": name,
            "day": day, "minutes": minutes, "index": index,
            "assisted": is_assisted(hevy_name) or is_assisted(name),
            "reps": number(row.get("reps")),
            "weight": number(cell(row, weight_col)),
            "distance": number(cell(row, distance_col)),
            "seconds": number(row.get("duration_seconds")),
        })
    if not parsed:
        fail("the file has no exercises (every exercise_title is empty)")

    if listing:
        write_exercise_list(parsed, args.list_exercises
                            or os.path.splitext(args.input)[0] + "_exercises.csv",
                            args.input, args.assisted_positive)
        return

    output = args.output or os.path.splitext(args.input)[0] + "_sparkyfitness.csv"
    if os.path.exists(output) and os.path.samefile(output, args.input):
        fail("the output would overwrite the Hevy export; choose another name with -o")
    if (args.exercise_map and os.path.exists(output)
            and os.path.samefile(output, args.exercise_map)):
        fail("the output would overwrite the exercise table; choose another name with -o")

    def weight_in_profile(value):
        if value is None or file_weight == args.weight:
            return value
        return value / LB_PER_KG if file_weight == "lbs" else value / SERVER_KG_PER_LB

    def distance_in_profile(value):
        if value is None or file_distance == args.distance:
            return value
        return value * KM_PER_MILE if file_distance == "miles" else value / SERVER_KM_PER_MILE

    # Hevy lists the newest workout first; import oldest first so the sets of
    # two workouts on the same day keep their order, also when their start
    # times cannot be read or are equal.
    workout_first_row = {}
    for p in parsed:
        workout_first_row.setdefault(p["row"].get("start_time"), p["index"])
    parsed.sort(key=lambda p: (p["day"], p["minutes"],
                               -workout_first_row[p["row"].get("start_time")], p["index"]))

    # Classified by the name written to SparkyFitness, so Hevy names mapped to
    # one exercise share its kind. It only matters when the import creates the
    # exercise: an existing one keeps its own settings.
    traits = collect_traits(parsed, "name")
    kinds = {name: exercise_kind(t, args.assisted_positive) for name, t in traits.items()}
    if args.assisted_positive:
        mixed = sorted({p["name"] for p in parsed if p["assisted"] and p["weight"]}
                       & {p["name"] for p in parsed if not p["assisted"] and p["weight"]})
        if mixed:
            fail("with --assisted-positive, assistance and added weight would both be "
                 "positive in " + ", ".join(mixed) + ". Map assisted and weighted Hevy "
                 "exercises to different names, or leave out --assisted-positive.")

    # SparkyFitness merges all rows of one day and exercise into one entry and
    # keeps the entry's distance and notes from its first row, so every row
    # carries the day's total distance and all of the day's notes, and the
    # sets are numbered 1..n across that day.
    day_distance = {}
    day_notes = {}
    for p in parsed:
        key = (p["day"], p["name"])
        if p["distance"] is not None:
            day_distance[key] = day_distance.get(key, 0.0) + p["distance"]
        text = " - ".join(n for n in (one_line(p["row"].get(c) or "")
                                      for c in ("title", "description", "exercise_notes")) if n)
        seen = day_notes.setdefault(key, [])
        if text and text not in seen:
            seen.append(text)

    set_counter = {}
    dropped = set()
    out_rows = []
    for p in parsed:
        row, name = p["row"], p["name"]
        key = (p["day"], name)
        set_counter[key] = set_counter.get(key, 0) + 1
        category, equipment = CATEGORY[kinds[name]]
        weight = weight_in_profile(p["weight"])
        if p["assisted"] and weight is not None and weight > 0 and not args.assisted_positive:
            weight = -weight  # Hevy writes the assistance as a positive number
        if weight is not None and weight < 0 and equipment != "body only":
            dropped.add(name)  # SparkyFitness refuses a negative weight here
            weight = None
        set_notes = []
        rpe = (row.get("rpe") or "").strip()
        if rpe:
            set_notes.append(f"RPE {rpe}")
        superset = (row.get("superset_id") or "").strip()
        if superset.isdigit():
            set_notes.append(f"Superset {int(superset) + 1}")
        out_rows.append({
            "entry_date": p["day"].isoformat(),
            "exercise_name": name,
            "exercise_force": "", "exercise_level": "", "exercise_mechanic": "",
            "exercise_category": category,
            "exercise_equipment": equipment,
            "entry_notes": " | ".join(day_notes[key]),
            "set_number": set_counter[key],
            "set_type": SET_TYPES.get((row.get("set_type") or "").strip().lower(), "Working Set"),
            "reps": fmt(p["reps"], 0),
            "weight": fmt(weight),
            "duration_min": fmt(p["seconds"] / 60 if p["seconds"] is not None else None),
            "distance": fmt(distance_in_profile(day_distance.get(key)),
                            3 if args.distance == "km" else 4),
            "set_notes": "; ".join(set_notes),
        })

    try:
        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=OUT_COLUMNS)
            writer.writeheader()
            writer.writerows(out_rows)
    except OSError as error:
        fail(f"could not write {output} ({error.strerror}). Close it in Excel or "
             "choose another name with -o.")

    days = sorted({p["day"] for p in parsed})
    workouts = {(p["row"].get("title"), p["row"].get("start_time")) for p in parsed}
    print(f"Wrote {len(out_rows)} sets from {len(workouts)} workouts "
          f"({days[0]} to {days[-1]}) to {output}")
    print(f"Units: file in {file_weight}/{file_distance}, written in {args.weight}/{args.distance}.")
    if encoding != "utf-8-sig":
        print("Warning: the file was not saved as UTF-8 (was it re-saved in Excel?); "
              "check accented names and emojis in the preview.")
    if args.exercise_map:
        hevy_names = {p["hevy_name"] for p in parsed}
        used = sorted(h for h in mapping if h in hevy_names)
        unknown = sorted(h for h in mapping if h not in hevy_names)
        print(f"Exercise table: {len(used)} Hevy names renamed to "
              f"{len({mapping[h] for h in used})} SparkyFitness names. Names must match "
              "your SparkyFitness exercises exactly (spelling and capitals), or the "
              "import creates a new exercise with that name.")
        if map_encoding not in ("utf-8-sig", "utf-16"):
            print("Warning: the exercise table was not saved as UTF-8; names with "
                  "accents or emojis may not match. Save it as 'CSV UTF-8'.")
        if unknown:
            print("Warning: these names in the table are not in this export (kept "
                  "from an older export, or misspelled): " + ", ".join(unknown))
        chained = sorted(h for h in used if mapping[h] in hevy_names
                         and mapping.get(mapping[h], mapping[h]) != mapping[h])
        if chained:
            print("Warning: these are renamed to a Hevy name that the table renames "
                  "again, so their sets stay apart: " + "; ".join(
                      f"{h} -> {mapping[h]} (but {mapping[h]} -> {mapping[mapping[h]]})"
                      for h in chained))
    hevy_to_name = {p["hevy_name"]: p["name"] for p in parsed}
    alike = apart(similar_names(hevy_to_name), hevy_to_name.get)
    if alike:
        print("Warning: these Hevy names look like the same exercise but stay separate "
              "exercises: " + list_groups(alike) + ". To join them, give each group the "
              "same sparkyfitness_name in the exercise table (create it with "
              "--list-exercises) and convert again.")
    labels = {
        "cardio": "Cardio", "timed": "Timed holds", "bodyweight": "Bodyweight",
        "assisted": "Assisted (assistance written as a negative weight)",
    }
    for kind, label in labels.items():
        names = sorted(n for n, k in kinds.items() if k == kind)
        if names:
            print(f"{label}: " + ", ".join(names))
    if args.assisted_positive:
        names = sorted({p["name"] for p in parsed if p["assisted"]})
        if names:
            print("Assisted, assistance kept positive (SparkyFitness shows it as the "
                  "weight): " + ", ".join(names))
    if dropped:
        print("Warning: negative weights left blank on these weighted exercises "
              "(SparkyFitness accepts a negative weight only on a bodyweight "
              "exercise): " + ", ".join(sorted(dropped)))
    negative_names = sorted({r["exercise_name"] for r in out_rows if r["weight"].startswith("-")})
    if negative_names:
        print("Written with a negative weight (assistance): " + ", ".join(negative_names)
              + ". If SparkyFitness then says 'Some entries failed to import.', the rest "
              "was imported and one of these already exists in SparkyFitness as a "
              "weighted exercise: in Exercises, edit it, set Tracking type to "
              "'Bodyweight (+/- weight)' and import the same file again (nothing is "
              "duplicated), or convert again with --assisted-positive.")


if __name__ == "__main__":
    main()
