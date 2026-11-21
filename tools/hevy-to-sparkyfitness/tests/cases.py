"""Golden cases: a synthetic Hevy export, the options, and the file the
converter must write (tests/expected/<name>.csv). Shared by the tests and by
regenerate_expected.py. "{fixtures}" in an option is the fixtures folder."""

KG_KM = ["--weight", "kg", "--distance", "km"]
LBS_MILES = ["--weight", "lbs", "--distance", "miles"]

CASES = [
    # name, fixture, options
    ("app_en_kg_km__kg_km", "app_en_kg_km.csv", KG_KM),
    ("app_en_kg_km__lbs_miles", "app_en_kg_km.csv", LBS_MILES),
    ("app_en_lbs_miles__kg_km", "app_en_lbs_miles.csv", KG_KM),
    ("web_en_us__kg_km", "web_en_us.csv", KG_KM),
    ("excel_semicolon_decimal_comma__kg_km", "excel_semicolon_decimal_comma.csv", KG_KM),
    ("excel_day_first__kg_km", "excel_day_first.csv", KG_KM),
    ("utf16_tab__kg_km", "utf16_tab.csv", KG_KM),
    ("bom_crlf_multiline_notes__kg_km", "bom_crlf_multiline_notes.csv", KG_KM),
    ("same_day_12h_clock__kg_km", "same_day_12h_clock.csv", KG_KM),
    ("same_day_notes__kg_km", "same_day_notes.csv", KG_KM),
    ("chinese_am_pm__kg_km", "chinese_am_pm.csv", KG_KM),
    ("localized_assisted__kg_km", "localized_assisted.csv", KG_KM),
    ("localized_assisted__assisted_positive", "localized_assisted.csv", KG_KM + ["--assisted-positive"]),
    ("unassisted_name__kg_km", "unassisted_name.csv", KG_KM),
    ("weighted_bodyweight__kg_km", "weighted_bodyweight.csv", KG_KM),
    ("negative_weight_on_barbell__kg_km", "negative_weight_on_barbell.csv", KG_KM),
    ("short_distances__kg_km", "short_distances.csv", KG_KM),
    ("short_distances__lbs_miles", "short_distances.csv", LBS_MILES),
    ("timed_cardio__kg_km", "timed_cardio.csv", KG_KM),
    ("exercise_table__kg_km", "exercise_table_export.csv",
     KG_KM + ["--exercise-map", "{fixtures}/exercise_table_filled.csv"]),
    ("exercise_table_excel__kg_km", "exercise_table_export.csv",
     KG_KM + ["--exercise-map", "{fixtures}/exercise_table_excel_semicolon.csv"]),
]
