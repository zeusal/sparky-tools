# Changelog

All notable changes to Hevy to SparkyFitness. Versions follow the `x.y` scheme described in [CONTRIBUTING.md](../../CONTRIBUTING.md).

## 1.0

First release.

- Converts Hevy workout exports from the app (`workout_data.csv`) and the website (`workouts.csv`) into SparkyFitness's Workout History CSV.
- Reads Hevy dates in English, Spanish, Italian, German, French, Portuguese, Dutch, Chinese, Japanese and Korean, and files re-saved by Excel (semicolons, decimal commas, UTF-16, day/month dates).
- Converts weights and distances to the units set in SparkyFitness, and durations from seconds to minutes.
- Numbers sets 1..n per exercise and day, maps Hevy's set types, and keeps RPE and supersets in the set notes and titles and notes in the entry notes.
- Sets up new exercises as cardio, timed holds, bodyweight, assisted (negative weight) or weight and reps.
- Exercise table (`--list-exercises`, `--exercise-map`) to log Hevy history under exercises that already exist in SparkyFitness.
