# Hevy to SparkyFitness

Moves your workout history from [Hevy](https://www.hevyapp.com/) to [SparkyFitness](https://github.com/CodeWithCJ/SparkyFitness).

Hevy lets every account, free or Pro, export its workouts as a CSV file. SparkyFitness can import workout history from CSV, but not Hevy's file as it comes: the dates carry a time of day, the columns have other names, set numbers start at 0, and durations are in seconds. This script rewrites the file into the columns of SparkyFitness's Workout History importer, on your own computer.

**Prefer a guided walkthrough?** Follow the [step-by-step guide](https://zeusal.github.io/sparky-tools/hevy-to-sparkyfitness/). It builds the commands for your system and units.

## Contents

- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Options](#options)
- [Using exercises you already have](#using-exercises-you-already-have)
- [What comes across](#what-comes-across)
- [How exercises are set up](#how-exercises-are-set-up)
- [Troubleshooting](#troubleshooting)
- [Privacy](#privacy)
- [Development](#development)

## Requirements

- Python 3.8 or newer. Nothing else to install.
- A Hevy workout export:
  - **App:** Profile → Settings → Export & Import Data → Export Data → Export Workouts. You get `workout_data.csv`.
  - **Website:** sign in and open [hevy.com/settings?export](https://hevy.com/settings?export), then press *Export Workout Data*. You get `workouts.csv`.
  - The app writes exercise names in its own language, while the website always uses English. Don't save the file in Excel or Numbers before converting it.
- SparkyFitness on the web: the import screen is in the web app.

## Quick start

1. Check your units in SparkyFitness: *Settings → Preferences → Weight Unit* and *Distance Unit*.
2. Download [`hevy_to_sparkyfitness.py`](hevy_to_sparkyfitness.py) and put it in the same folder as your export.
3. Open a terminal in that folder and run it with your SparkyFitness units:

   ```bash
   # Windows
   py hevy_to_sparkyfitness.py workout_data.csv --weight kg --distance km
   # macOS and Linux
   python3 hevy_to_sparkyfitness.py workout_data.csv --weight kg --distance km
   ```

   It writes `workout_data_sparkyfitness.csv` next to your export and prints a summary.
4. In SparkyFitness, open *Settings → Data Import*, press *Import* next to *Workout History (CSV)*, choose the converted file and press *Process File*. Leave the format options on *Auto-detect*, check the preview and press *Confirm and Import*.

Example summary:

```text
Wrote 2184 sets from 96 workouts (2024-03-02 to 2025-12-05) to workout_data_sparkyfitness.csv
Units: file in lbs/miles, written in kg/km.
Cardio: Running, Treadmill
Timed holds: Plank
Bodyweight: Chin Up, Hanging Leg Raise, Pull Up
Assisted (assistance written as a negative weight): Pull Up (Assisted)
```

## Options

| Option | Meaning |
| --- | --- |
| `--weight kg\|lbs` | The weight unit set in SparkyFitness. Required to convert. |
| `--distance km\|miles` | The distance unit set in SparkyFitness. Required to convert. |
| `-o FILE`, `--output FILE` | Where to write the converted file. Default: `<export>_sparkyfitness.csv`. The script refuses to overwrite your export or your exercise table. |
| `--list-exercises [FILE]` | Only write the exercise table (see below). Default: `<export>_exercises.csv`. |
| `--exercise-map FILE` | Use a filled-in exercise table. |
| `--date-order dmy\|mdy` | Only for an export re-saved by Excel whose dates look like `03/12/2023`, when the file can't tell which number is the day. |
| `--assisted-positive` | Keep the assistance of assisted exercises as a positive number, for exercises SparkyFitness already has as weighted ones (see [How exercises are set up](#how-exercises-are-set-up)). |
| `--version` | Print the script's version. |

## Using exercises you already have

SparkyFitness reuses one of your exercises only when its name matches exactly, capitals included. Any other name becomes a new exercise in your library, named as in Hevy (for example *Bench Press (Barbell)*). SparkyFitness can't merge two exercises afterwards, and its progress charts follow one exercise.

- **New to SparkyFitness?** Keep the Hevy names and keep logging under them after the import.
- **Already logging under other names?** Use an exercise table, so your old and new history end up under the same exercise:

1. Write the table:

   ```bash
   python3 hevy_to_sparkyfitness.py workout_data.csv --list-exercises
   ```

   This writes `workout_data_exercises.csv` with these columns:

   | Column | Content |
   | --- | --- |
   | `hevy_name` | The exercise name in your export. Don't change it. |
   | `sparkyfitness_name` | Fill in the exact name of the SparkyFitness exercise to use. Leave it empty to keep the Hevy name. |
   | `sets`, `last_done` | How often and how recently you did it, to help you decide. |
   | `kind` | How the script will set the exercise up: `weights`, `bodyweight`, `assisted`, `cardio` or `timed`. |

2. Fill in `sparkyfitness_name` in Excel, LibreOffice, Numbers or a text editor. Copy names from SparkyFitness to get the spelling right. Several Hevy names can point to the same exercise. Save as **CSV UTF-8**. If Excel shows each row in a single column, open the file with *Data → From Text/CSV*, or use LibreOffice or Google Sheets.
3. Convert with the table:

   ```bash
   python3 hevy_to_sparkyfitness.py workout_data.csv --weight kg --distance km --exercise-map workout_data_exercises.csv
   ```

Running `--list-exercises` again later, for example with a newer export, keeps the names you filled in and adds any new exercises. The script stops if the table lists the same Hevy name twice with different targets, and warns about names that aren't in the export and about targets that the table renames again.

If you already imported under the Hevy names and want other names, importing again would duplicate your history. First delete the imported exercises in SparkyFitness with *Delete including history*, then convert with a table and import.

## What comes across

| In Hevy | In SparkyFitness |
| --- | --- |
| Workout date | Diary date (the day the workout started) |
| Sets, reps, weight, duration, distance | The same values, in your SparkyFitness units |
| Set types (warm-up, normal, drop set, failure) | Warm-up, Working Set, Drop Set, Failure |
| RPE and supersets | Set notes, for example `RPE 8; Superset 1` |
| Workout title, description, exercise notes | Notes on each exercise entry |

Not carried over:

- **The grouping into workouts.** SparkyFitness's importer makes one diary entry per exercise and day. Two workouts with the same exercise on one day are merged into one entry, with the sets in time order and the notes of both.
- **The time of day.**
- **Calories.** Hevy doesn't export them, so imported entries show 0 kcal.
- **Muscle groups and equipment.** Hevy's export doesn't include them. You can add them to the new exercises in SparkyFitness.

## How exercises are set up

When the import creates an exercise, its category and equipment decide how SparkyFitness tracks it. An exercise that already exists keeps its own settings. The script decides from what your history records and from the exercise name:

| Kind | When | Written as |
| --- | --- | --- |
| `cardio` | Distance or time, and no reps or weight (Running, Cycling, Rowing Machine…) | Category `cardio`: duration and distance |
| `timed` | Time only, and the name isn't a cardio activity (Plank, Dead Hang…) | Category `isometric`: duration |
| `assisted` | Hevy's assisted exercises: names with *Assisted* (also *Assistite*, *Asistidas*, *Unterstützt*…) and *Pull Up (Band)* | Bodyweight, with the assistance as a **negative** weight |
| `bodyweight` | Reps with no weight, unless the name says it's loaded (*Barbell*, *Machine*, *Cable*…), and Hevy's weighted bodyweight moves such as *Pull Up (Weighted)* | Bodyweight, with any added load as a positive weight |
| `weights` | Everything else | Weight and reps |

Hevy writes the assistance of an assisted exercise as a positive number. SparkyFitness records assistance as a negative weight on a bodyweight exercise, so the script flips the sign. SparkyFitness only accepts a negative weight on a bodyweight exercise. If you already have an assisted exercise saved as a weighted one, those entries fail (see [Troubleshooting](#troubleshooting)). A stray negative weight on a loaded exercise is left blank, and the summary says so.

## Troubleshooting

**`python` is not recognized, or `command not found`**
On Windows, use `py`, or reinstall Python with *Add python.exe to PATH* ticked. On macOS, use `python3`.

**`could not read the date …`**
Export again from Hevy and don't edit the file. The script reads Hevy's dates in English, Spanish, Italian, German, French, Portuguese, Dutch, Chinese, Japanese and Korean. For other languages, switch Hevy to English and export again.

**`the dates look like 03/12/2023 …`**
The file was saved by Excel, which rewrote the dates. Use the original export. If you can't, add `--date-order dmy` (day first) or `--date-order mdy` (month first).

**SparkyFitness says *Some entries failed to import.***
Everything else was imported. Usually an exercise the script wrote with a negative weight (it lists them at the end of its summary) already exists in SparkyFitness as a weighted exercise. Edit that exercise, set *Tracking type* to *Bodyweight (+/− weight)*, and import the same file again: nothing is duplicated. Or convert again with `--assisted-positive`, and the assistance shows as the weight.

**A "Map CSV Headers" window appears in SparkyFitness**
You chose the original Hevy file. Choose the converted `_sparkyfitness.csv` file.

**I imported the same file twice**
That's fine. With the same file and the same exercise names, SparkyFitness updates the entries it imported before.

**The history went to an exercise I don't own**
On a SparkyFitness server shared with other people, an exercise someone else shared publicly under exactly the same name can be used instead of yours. Give your exercise a name only you use, in SparkyFitness and in the exercise table.

## Privacy

The script reads your export and writes new files next to it. It makes no network requests and uploads nothing. Don't attach your real export to issues: share a few rows with the values changed.

## Development

The tests use only the standard library. From the repository root:

```bash
python scripts/run_tests.py
```

Or only this tool's tests:

```bash
python -m unittest discover -s tools/hevy-to-sparkyfitness/tests -t tools/hevy-to-sparkyfitness/tests
```

`tests/fixtures/` holds synthetic Hevy exports (app and website formats, several languages, Excel re-saves) and `tests/expected/` the converted files they must produce. When you change the output on purpose, regenerate the expected files with `python tools/hevy-to-sparkyfitness/tests/regenerate_expected.py` and review the difference before committing it.
