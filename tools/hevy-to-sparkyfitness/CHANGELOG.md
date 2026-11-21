# Changelog

All notable changes to Hevy to SparkyFitness. Versions follow the `x.y` scheme described in [CONTRIBUTING.md](../../CONTRIBUTING.md).

## 1.1

- New: an easy version at https://zeusal.github.io/sparky-tools/hevy-to-sparkyfitness/ for people who don't use the command line. It walks through the whole migration in the browser, on a computer or a phone, with nothing to install. It runs this same script with Pyodide, so its files are identical to the command line's, and the export never leaves the device. The command-line guide moved to https://zeusal.github.io/sparky-tools/hevy-to-sparkyfitness/command-line/.
- New: a visual exercise table in the easy version. It suggests names from your own SparkyFitness exercises (pasted once) and from Free Exercise DB, checks spelling and capitals against your names, and saves and loads tables in the same format as `--list-exercises`.
- `--list-exercises` keeps the names you filled in for exercises that aren't in the export (written with 0 sets) instead of dropping them, so listing a newer or shorter export loses no work, and it says how many it kept. When converting, such names are reported as "kept from an older export, or misspelled".
- Large exports convert several times faster.

## 1.0

First release.

- Converts Hevy workout exports from the app (`workout_data.csv`) and the website (`workouts.csv`) into SparkyFitness's Workout History CSV.
- Reads Hevy dates in English, Spanish, Italian, German, French, Portuguese, Dutch, Chinese, Japanese and Korean, and files re-saved by Excel (semicolons, decimal commas, UTF-16, day/month dates).
- Converts weights and distances to the units set in SparkyFitness, and durations from seconds to minutes.
- Numbers sets 1..n per exercise and day, maps Hevy's set types, and keeps RPE and supersets in the set notes and titles and notes in the entry notes.
- Sets up new exercises as cardio, timed holds, bodyweight, assisted (negative weight) or weight and reps.
- Exercise table (`--list-exercises`, `--exercise-map`) to log Hevy history under exercises that already exist in SparkyFitness.
