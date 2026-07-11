#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

try:
    from semantic_layer import ensure_semantic_layer
except ModuleNotFoundError:
    from analysis_platform.semantic_layer import ensure_semantic_layer

try:
    from attention_selection_shadow import evaluate_candidates, live_signals, rank_candidates
except ModuleNotFoundError:
    from analysis_platform.attention_selection_shadow import evaluate_candidates, live_signals, rank_candidates


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
DEFAULT_DB_PATH = ROOT / "running_analytics.sqlite"
ASSETS_DIR = PROJECT_ROOT / "assets"
CONFIG_PATH = PROJECT_ROOT / "config" / "dropdown_options.json"
RAC_APP_PATH = PROJECT_ROOT / "app.py"
RAC_HOST = "127.0.0.1"
RAC_PORT = 8765
RAC_LOG_PATH = PROJECT_ROOT / "tmp" / "rac_server.log"
HOST = "127.0.0.1"
PORT = 8766
DB_PATH = DEFAULT_DB_PATH

DEFAULT_DROPDOWN_OPTIONS = {
    "shoes": [],
    "workout_types": [
        "Recovery Run（恢復跑）",
        "Easy Run（輕鬆跑）",
        "LSD（長距離慢跑）",
        "Long Run（長跑）",
        "Tempo Run（節奏跑）",
        "Marathon Pace（馬拉松配速）",
        "Interval（間歇）",
        "Repetition（速度訓練）",
        "Progression Run（漸速跑）",
        "Fartlek（法特萊克）",
        "Race（比賽）",
        "Other（其他）",
    ],
    "training_focus": [
        "Recovery（恢復）",
        "Aerobic Base（有氧基礎）",
        "Endurance（耐力）",
        "Marathon Pace（馬拉松配速）",
        "Threshold（乳酸閾值）",
        "VO₂max",
        "Speed（速度）",
        "Neuromuscular（神經肌肉活化）",
        "Running Economy（跑步經濟性）",
        "Running Form（跑姿技術）",
        "Heat Adaptation（高溫適應）",
        "Race Simulation（比賽模擬）",
        "Taper（減量）",
        "Test（測驗）",
    ],
}

SHOE_DIMENSION_DEFAULTS = {}

WORKOUT_TYPE_DIMENSION_DEFAULTS = {
    "Recovery Run": ("recovery_run", "Recovery Run", "恢復跑", "Recovery", 0, 0, 1, 10, "#7CB7B8"),
    "Easy Run": ("easy_run", "Easy Run", "輕鬆跑", "Easy", 0, 0, 0, 20, "#6FA8DC"),
    "LSD": ("lsd", "LSD", "長距離慢跑", "Easy", 0, 1, 0, 30, "#93C47D"),
    "Long Run": ("long_run", "Long Run", "長跑", "Moderate", 0, 1, 0, 40, "#76A5AF"),
    "Tempo Run": ("tempo_run", "Tempo Run", "節奏跑", "Quality", 1, 0, 0, 50, "#E69138"),
    "Marathon Pace": ("marathon_pace", "Marathon Pace", "馬拉松配速", "Quality", 1, 0, 0, 60, "#F6B26B"),
    "Interval": ("interval", "Interval", "間歇", "Quality", 1, 0, 0, 70, "#CC0000"),
    "Repetition": ("repetition", "Repetition", "速度訓練", "Quality", 1, 0, 0, 80, "#990000"),
    "Progression Run": ("progression_run", "Progression Run", "漸速跑", "Moderate", 1, 0, 0, 90, "#B6D7A8"),
    "Fartlek": ("fartlek", "Fartlek", "法特萊克", "Quality", 1, 0, 0, 100, "#674EA7"),
    "Race": ("race", "Race", "比賽", "Race", 1, 0, 0, 110, "#000000"),
    "Other": ("other", "Other", "其他", "Moderate", 0, 0, 0, 120, "#999999"),
}

TRAINING_PURPOSE_DIMENSION_DEFAULTS = {
    "Recovery": ("recovery", "Recovery", "恢復", "Recovery", 0, 1, 0, 10, "#7CB7B8"),
    "Aerobic Base": ("aerobic_base", "Aerobic Base", "有氧基礎", "Aerobic", 1, 0, 1, 20, "#6FA8DC"),
    "Endurance": ("endurance", "Endurance", "耐力", "Endurance", 1, 0, 1, 30, "#93C47D"),
    "Marathon Pace": ("race_specific", "Marathon Pace", "馬拉松配速", "Race", 1, 0, 1, 40, "#F6B26B"),
    "Threshold": ("threshold", "Threshold", "乳酸閾值", "Threshold", 1, 0, 1, 50, "#E69138"),
    "VO2max": ("vo2max", "VO2max", "最大攝氧", "VO2max", 1, 0, 1, 60, "#CC0000"),
    "Speed": ("speed", "Speed", "速度", "Speed", 1, 0, 1, 70, "#990000"),
    "Neuromuscular": ("neuromuscular", "Neuromuscular", "神經肌肉活化", "Technique", 0, 0, 1, 80, "#674EA7"),
    "Running Economy": ("running_economy", "Running Economy", "跑步經濟性", "Technique", 1, 0, 1, 90, "#76A5AF"),
    "Running Form": ("running_form", "Running Form", "跑姿技術", "Technique", 0, 0, 1, 100, "#8E7CC3"),
    "Heat Adaptation": ("heat_adaptation", "Heat Adaptation", "高溫適應", "Environmental", 0, 0, 1, 110, "#F1C232"),
    "Race Simulation": ("race_simulation", "Race Simulation", "比賽模擬", "Race", 0, 0, 1, 120, "#000000"),
    "Taper": ("taper", "Taper", "減量", "Maintenance", 0, 1, 0, 130, "#999999"),
    "Test": ("test", "Test", "測驗", "Maintenance", 0, 0, 1, 140, "#666666"),
}


def value_is_blank(value):
    return value in ("", None)


def format_pace_seconds(value):
    if value_is_blank(value):
        return ""
    try:
        seconds = int(round(float(value)))
    except (TypeError, ValueError):
        return ""
    return f"{seconds // 60}:{seconds % 60:02d}/km"


def format_hours(seconds):
    if value_is_blank(seconds):
        return ""
    try:
        total = int(round(float(seconds)))
    except (TypeError, ValueError):
        return ""
    hours, remainder = divmod(total, 3600)
    minutes, _seconds = divmod(remainder, 60)
    return f"{hours}h {minutes:02d}m"


def format_activity_time(value):
    if value_is_blank(value):
        return ""
    text = str(value)
    if "T" not in text:
        return text
    date_part, time_part = text.split("T", 1)
    return f"{date_part}<br><span>{html.escape(time_part[:5])}</span>"


def format_short_datetime(value):
    if value_is_blank(value):
        return ""
    text = str(value).replace("T", " ")
    return text[:16]


def parse_date(value):
    if value_is_blank(value):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def format_number(value, digits=1):
    if value_is_blank(value):
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number.is_integer():
        return str(int(number))
    return f"{number:.{digits}f}"


def format_delta_pct(value):
    if value is None:
        return ""
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.0f}%"


def connect():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    ensure_semantic_layer(connection)
    return connection


def first_form_value(form, key, default=""):
    values = form.get(key)
    if not values:
        return default
    return values[0]


def load_metadata_dropdown_options():
    options = {
        key: list(value)
        for key, value in DEFAULT_DROPDOWN_OPTIONS.items()
    }
    if not CONFIG_PATH.exists():
        return options
    try:
        loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return options
    for key in ("shoes", "workout_types", "training_focus"):
        if isinstance(loaded.get(key), list):
            options[key] = [str(item).strip() for item in loaded[key] if str(item).strip()]
    return options


def save_metadata_dropdown_options(options):
    current = {}
    if CONFIG_PATH.exists():
        try:
            current = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current = {}

    merged = dict(current)
    merged.update(options)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def append_shoe_option(label):
    value = str(label or "").strip()
    if not value:
        raise ValueError("請先輸入鞋款名稱。")

    options = load_metadata_dropdown_options()
    existing = {canonical_label(item).lower() for item in options.get("shoes", [])}
    if canonical_label(value).lower() in existing:
        raise ValueError("這雙鞋已經在清單裡了。")

    updated_shoes = list(options.get("shoes", []))
    updated_shoes.append(value)
    options["shoes"] = updated_shoes
    save_metadata_dropdown_options(options)
    return value


def label_primary(value):
    value = str(value or "").strip()
    if not value:
        return ""
    return re.split(r"[（(]", value, maxsplit=1)[0].strip()


def canonical_label(value):
    return label_primary(value).replace("₂", "2")


def code_from_label(value, prefix):
    label = canonical_label(value).lower()
    code = re.sub(r"[^a-z0-9]+", "_", label).strip("_")
    if code:
        return code
    digest = hashlib.sha1(str(value or "").encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{digest}"


def exact_or_primary_lookup(mapping, label):
    if not label:
        return None
    if label in mapping:
        return mapping[label]
    return mapping.get(canonical_label(label))


def shoe_dimension_row(label):
    row = exact_or_primary_lookup(SHOE_DIMENSION_DEFAULTS, label)
    if row:
        return {**row, "is_active": 1}
    primary = label_primary(label) or str(label or "").strip()
    return {
        "shoe_code": code_from_label(primary, "shoe"),
        "brand": "",
        "model": primary or "",
        "nickname": None,
        "category": "",
        "is_active": 1,
    }


def workout_type_dimension_row(label):
    row = exact_or_primary_lookup(WORKOUT_TYPE_DIMENSION_DEFAULTS, label)
    if row:
        code, name_en, name_zh, intensity, quality, long_run, recovery, sort_order, color = row
    else:
        name_en = label_primary(label) or str(label or "").strip() or "Other"
        code, name_zh, intensity, quality, long_run, recovery, sort_order, color = (
            code_from_label(name_en, "workout"),
            name_en,
            "Moderate",
            0,
            0,
            0,
            999,
            "#999999",
        )
    return {
        "workout_type_code": code,
        "name_en": name_en,
        "name_zh": name_zh,
        "description": None,
        "intensity_category": intensity,
        "is_quality_session": quality,
        "is_long_run": long_run,
        "is_recovery_focused": recovery,
        "sort_order": sort_order,
        "display_color": color,
    }


def training_purpose_dimension_row(label):
    row = exact_or_primary_lookup(TRAINING_PURPOSE_DIMENSION_DEFAULTS, label)
    if row:
        code, name_en, name_zh, category, physiological, recovery, performance, sort_order, color = row
    else:
        name_en = label_primary(label) or str(label or "").strip() or "Maintenance"
        code, name_zh, category, physiological, recovery, performance, sort_order, color = (
            code_from_label(name_en, "purpose"),
            name_en,
            "Maintenance",
            0,
            0,
            0,
            999,
            "#999999",
        )
    return {
        "training_purpose_code": code,
        "name_en": name_en,
        "name_zh": name_zh,
        "description": None,
        "purpose_category": category,
        "is_primary_physiological": physiological,
        "is_recovery_related": recovery,
        "is_performance_related": performance,
        "sort_order": sort_order,
        "display_color": color,
    }


def ensure_reference_choice(connection, table, code_column, row):
    existing = connection.execute(
        f"SELECT id FROM {table} WHERE {code_column} = ?",
        (row[code_column],),
    ).fetchone()
    if existing:
        return existing[0]
    columns = list(row)
    placeholders = ", ".join("?" for _ in columns)
    connection.execute(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
        [row[column] for column in columns],
    )
    return connection.execute(
        f"SELECT id FROM {table} WHERE {code_column} = ?",
        (row[code_column],),
    ).fetchone()[0]


def reconcile_shoe_choice(connection, row):
    existing = connection.execute(
        """
        SELECT
            id,
            brand,
            model,
            nickname,
            category,
            is_active,
            retire_date,
            retire_target_distance_km,
            retire_actual_distance_km,
            notes
        FROM shoe
        WHERE shoe_code = ?
        """,
        (row["shoe_code"],),
    ).fetchone()
    if not existing:
        columns = list(row)
        placeholders = ", ".join("?" for _ in columns)
        connection.execute(
            f"INSERT INTO shoe ({', '.join(columns)}) VALUES ({placeholders})",
            [row[column] for column in columns],
        )
        return
    connection.execute(
        """
        UPDATE shoe
        SET
            brand = ?,
            model = ?,
            nickname = ?,
            category = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE shoe_code = ?
        """,
        (
            row["brand"],
            row["model"],
            row["nickname"],
            row["category"],
            row["shoe_code"],
        ),
    )


def reconcile_reference_choice(connection, table, code_column, row):
    existing = connection.execute(
        f"SELECT id FROM {table} WHERE {code_column} = ?",
        (row[code_column],),
    ).fetchone()
    if not existing:
        columns = list(row)
        placeholders = ", ".join("?" for _ in columns)
        connection.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
            [row[column] for column in columns],
        )
        return
    update_columns = [column for column in row if column != code_column]
    assignments = ", ".join(f"{column} = ?" for column in update_columns)
    values = [row[column] for column in update_columns]
    values.append(row[code_column])
    connection.execute(
        f"UPDATE {table} SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE {code_column} = ?",
        values,
    )


def ensure_metadata_dimensions(connection, dropdown_options):
    for label in dropdown_options.get("shoes", []):
        reconcile_shoe_choice(connection, shoe_dimension_row(label))
    for label in dropdown_options.get("workout_types", []):
        reconcile_reference_choice(
            connection,
            "workout_type",
            "workout_type_code",
            workout_type_dimension_row(label),
        )
    for label in dropdown_options.get("training_focus", []):
        reconcile_reference_choice(
            connection,
            "training_purpose",
            "training_purpose_code",
            training_purpose_dimension_row(label),
        )


def metadata_choice_sets(connection):
    dropdown_options = load_metadata_dropdown_options()
    ensure_metadata_dimensions(connection, dropdown_options)

    shoes = connection.execute(
        """
        SELECT
            shoe_code,
            brand,
            model,
            nickname,
            is_active
        FROM shoe
        ORDER BY is_active DESC, brand, model, nickname, shoe_code
        """
    ).fetchall()
    workouts = connection.execute(
        """
        SELECT
            workout_type_code,
            name_en,
            intensity_category
        FROM workout_type
        ORDER BY COALESCE(sort_order, 999), name_en, workout_type_code
        """
    ).fetchall()
    purposes = connection.execute(
        """
        SELECT
            training_purpose_code,
            name_en,
            purpose_category
        FROM training_purpose
        ORDER BY COALESCE(sort_order, 999), name_en, training_purpose_code
        """
    ).fetchall()
    return dropdown_options, shoes, workouts, purposes


def metadata_candidates(connection, scope="unassigned", limit=40):
    clause = ""
    if scope == "unassigned":
        clause = """
        WHERE shoe_id IS NULL
           OR workout_type_id IS NULL
           OR primary_training_purpose_id IS NULL
        """
    elif scope == "missing_shoe":
        clause = "WHERE shoe_id IS NULL"
    elif scope == "missing_workout":
        clause = "WHERE workout_type_id IS NULL"
    elif scope == "missing_purpose":
        clause = "WHERE primary_training_purpose_id IS NULL"
    elif scope == "complete":
        clause = """
        WHERE shoe_id IS NOT NULL
          AND workout_type_id IS NOT NULL
          AND primary_training_purpose_id IS NOT NULL
        """
    return connection.execute(
        f"""
        SELECT
            activity_id,
            activity_start_time,
            activity_name,
            activity_type,
            distance_km,
            training_load,
            shoe_id,
            shoe_code,
            shoe_display_name,
            workout_type_id,
            workout_type_code,
            workout_type_name_en,
            primary_training_purpose_id,
            primary_training_purpose_code,
            primary_training_purpose_name_en,
            secondary_training_purpose_codes,
            secondary_training_purpose_names_en
        FROM activity_review_view
        {clause}
        ORDER BY activity_start_time DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def metadata_scope_counts(connection):
    return connection.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN shoe_id IS NULL THEN 1 ELSE 0 END) AS missing_shoe,
            SUM(CASE WHEN workout_type_id IS NULL THEN 1 ELSE 0 END) AS missing_workout,
            SUM(CASE WHEN primary_training_purpose_id IS NULL THEN 1 ELSE 0 END) AS missing_purpose,
            SUM(
                CASE
                    WHEN shoe_id IS NULL
                      OR workout_type_id IS NULL
                      OR primary_training_purpose_id IS NULL
                    THEN 1 ELSE 0
                END
            ) AS unassigned,
            SUM(
                CASE
                    WHEN shoe_id IS NOT NULL
                      AND workout_type_id IS NOT NULL
                      AND primary_training_purpose_id IS NOT NULL
                    THEN 1 ELSE 0
                END
            ) AS complete
        FROM activity_review_view
        """
    ).fetchone()


def metadata_activity(connection, activity_id):
    return connection.execute(
        """
        SELECT
            activity_id,
            activity_start_time,
            activity_name,
            activity_type,
            distance_km,
            duration_sec,
            training_load,
            shoe_id,
            shoe_code,
            shoe_display_name,
            workout_type_id,
            workout_type_code,
            workout_type_name_en,
            primary_training_purpose_id,
            primary_training_purpose_code,
            primary_training_purpose_name_en,
            secondary_training_purpose_codes,
            secondary_training_purpose_names_en
        FROM activity_review_view
        WHERE activity_id = ?
        """,
        (activity_id,),
    ).fetchone()


def parse_secondary_codes(value):
    if value_is_blank(value):
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def dimension_id_by_code(connection, table, code_column, code):
    if value_is_blank(code):
        return None
    row = connection.execute(
        f"SELECT id FROM {table} WHERE {code_column} = ?",
        (code,),
    ).fetchone()
    return row["id"] if row else None


def update_single_activity_metadata(
    connection,
    activity_id,
    shoe_code,
    workout_type_code,
    primary_purpose_code,
    secondary_purpose_code,
):
    ensure_metadata_dimensions(connection, load_metadata_dropdown_options())
    shoe_id = dimension_id_by_code(connection, "shoe", "shoe_code", shoe_code)
    workout_type_id = dimension_id_by_code(connection, "workout_type", "workout_type_code", workout_type_code)
    connection.execute(
        """
        UPDATE activity
        SET
            shoe_id = ?,
            workout_type_id = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (shoe_id, workout_type_id, activity_id),
    )
    purpose_labels = []
    purpose_codes = []
    if primary_purpose_code:
        purpose_codes.append(primary_purpose_code)
    if secondary_purpose_code and secondary_purpose_code != primary_purpose_code:
        purpose_codes.append(secondary_purpose_code)
    replace_activity_training_purposes_by_code(connection, activity_id, purpose_codes)


def replace_activity_training_purposes_by_code(connection, activity_id, purpose_codes):
    connection.execute(
        "DELETE FROM activity_training_purpose WHERE activity_id = ?",
        (activity_id,),
    )
    seen_codes = set()
    for index, code in enumerate([str(item).strip() for item in purpose_codes if str(item).strip()]):
        if code in seen_codes:
            continue
        seen_codes.add(code)
        training_purpose_id = dimension_id_by_code(
            connection,
            "training_purpose",
            "training_purpose_code",
            code,
        )
        if training_purpose_id is None:
            continue
        connection.execute(
            """
            INSERT INTO activity_training_purpose (
                activity_id,
                training_purpose_id,
                purpose_role,
                updated_at
            ) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (activity_id, training_purpose_id, "PRIMARY" if index == 0 else "SECONDARY"),
        )


def apply_batch_metadata_update(
    connection,
    activity_ids,
    shoe_action,
    workout_action,
    primary_action,
    secondary_action,
):
    if not activity_ids:
        return 0
    ensure_metadata_dimensions(connection, load_metadata_dropdown_options())
    purpose_should_replace = any(
        action != "__KEEP__"
        for action in (primary_action, secondary_action)
    )
    for activity_id in activity_ids:
        assignments = []
        values = []
        if shoe_action != "__KEEP__":
            shoe_id = None if shoe_action == "__CLEAR__" else dimension_id_by_code(connection, "shoe", "shoe_code", shoe_action)
            assignments.append("shoe_id = ?")
            values.append(shoe_id)
        if workout_action != "__KEEP__":
            workout_type_id = (
                None
                if workout_action == "__CLEAR__"
                else dimension_id_by_code(connection, "workout_type", "workout_type_code", workout_action)
            )
            assignments.append("workout_type_id = ?")
            values.append(workout_type_id)
        if assignments:
            assignments.append("updated_at = CURRENT_TIMESTAMP")
            values.append(activity_id)
            connection.execute(
                f"UPDATE activity SET {', '.join(assignments)} WHERE id = ?",
                values,
            )

        if purpose_should_replace:
            labels = []
            primary_label = "" if primary_action in {"__KEEP__", "__CLEAR__"} else primary_action
            secondary_label = "" if secondary_action in {"__KEEP__", "__CLEAR__"} else secondary_action
            if not primary_label and secondary_label:
                primary_label, secondary_label = secondary_label, ""
            if primary_label:
                labels.append(primary_label)
            if secondary_label and secondary_label != primary_label:
                labels.append(secondary_label)
            replace_activity_training_purposes_by_code(connection, activity_id, labels)
    return len(activity_ids)


def metrics(connection):
    return connection.execute("SELECT * FROM platform_summary_view").fetchone()


def week_summary(connection):
    return connection.execute("SELECT * FROM current_week_summary_view").fetchone()


def available_weeks(connection):
    return connection.execute(
        """
        SELECT
            week_offset,
            start_date,
            end_date,
            activities,
            total_km,
            training_load
        FROM weekly_summary_view
        ORDER BY week_offset
        """
    ).fetchall()


def selected_week_summary(connection, week_offset=None):
    if week_offset in ("", None):
        return week_summary(connection)
    try:
        offset = int(week_offset)
    except (TypeError, ValueError):
        return week_summary(connection)
    return connection.execute(
        """
        SELECT *
        FROM weekly_summary_view
        WHERE week_offset = ?
        """,
        (offset,),
    ).fetchone()


def weekly_history(connection):
    return connection.execute(
        """
        SELECT
            week_offset,
            start_date,
            end_date,
            activities,
            total_km,
            total_time_sec,
            avg_pace_sec_per_km,
            avg_hr,
            training_load
        FROM weekly_summary_view
        ORDER BY week_offset
        """
    ).fetchall()


def weekly_intelligence(connection):
    row = connection.execute("SELECT * FROM current_week_intelligence_view").fetchone()
    if not row:
        return None
    return weekly_intelligence_payload(dict(row))


def weekly_intelligence_payload(current):
    load_delta = current["load_delta_pct"]
    km_delta = current["km_delta_pct"]
    load_per_km_delta = current["load_per_km_delta_pct"]

    if load_delta is None or km_delta is None:
        coach_summary = "資料正在建立基準，先觀察每週跑量與訓練負荷的穩定性。"
    elif load_delta > 15:
        coach_summary = (
            f"本週訓練負荷較前四週平均高 {format_delta_pct(load_delta)}，"
            "下一次訓練建議優先觀察心率與疲勞反應。"
        )
    elif load_delta < -15:
        coach_summary = (
            f"本週訓練負荷較前四週平均低 {abs(load_delta):.0f}%，"
            "比較像吸收訓練的一週，可以準備下一個品質刺激。"
        )
    else:
        coach_summary = (
            "本週訓練負荷接近前四週平均，整體節奏穩定，適合維持目前訓練結構。"
        )

    return {
        "current": current,
        "baseline_km": current["baseline_km"],
        "baseline_load": current["baseline_load"],
        "baseline_load_per_km": current["baseline_load_per_km"],
        "km_delta": km_delta,
        "load_delta": load_delta,
        "load_per_km_delta": load_per_km_delta,
        "current_load_per_km": current["current_load_per_km"],
        "recovery_status": current["recovery_status"],
        "coach_summary": coach_summary,
    }


def selected_week_intelligence(connection, week_offset=None):
    target_week = selected_week_summary(connection, week_offset)
    if not target_week:
        return None
    row = connection.execute(
        """
        WITH target_week AS (
            SELECT *
            FROM weekly_summary_view
            WHERE week_offset = ?
        ),
        baseline AS (
            SELECT
                AVG(total_km) AS baseline_km,
                AVG(training_load) AS baseline_load,
                AVG(
                    CASE
                        WHEN total_km > 0
                        THEN training_load * 1.0 / total_km
                        ELSE NULL
                    END
                ) AS baseline_load_per_km
            FROM weekly_summary_view
            WHERE week_offset BETWEEN
                (SELECT week_offset + 1 FROM target_week)
                AND
                (SELECT week_offset + 4 FROM target_week)
        )
        SELECT
            target_week.start_date,
            target_week.end_date,
            target_week.activities,
            target_week.total_km,
            target_week.total_time_sec,
            target_week.avg_pace_sec_per_km,
            target_week.avg_hr,
            target_week.training_load,
            CASE
                WHEN target_week.total_km > 0
                THEN ROUND(target_week.training_load * 1.0 / target_week.total_km, 1)
                ELSE NULL
            END AS current_load_per_km,
            ROUND(baseline.baseline_km, 2) AS baseline_km,
            ROUND(baseline.baseline_load, 1) AS baseline_load,
            ROUND(baseline.baseline_load_per_km, 1) AS baseline_load_per_km,
            CASE
                WHEN baseline.baseline_km > 0
                THEN ROUND(((target_week.total_km - baseline.baseline_km) / baseline.baseline_km) * 100, 1)
                ELSE NULL
            END AS km_delta_pct,
            CASE
                WHEN baseline.baseline_load > 0
                THEN ROUND(((target_week.training_load - baseline.baseline_load) / baseline.baseline_load) * 100, 1)
                ELSE NULL
            END AS load_delta_pct,
            CASE
                WHEN baseline.baseline_load_per_km > 0 AND target_week.total_km > 0
                THEN ROUND((((target_week.training_load * 1.0 / target_week.total_km) - baseline.baseline_load_per_km) / baseline.baseline_load_per_km) * 100, 1)
                ELSE NULL
            END AS load_per_km_delta_pct,
            CASE
                WHEN baseline.baseline_load IS NULL OR baseline.baseline_load = 0 THEN 'Building baseline'
                WHEN ((target_week.training_load - baseline.baseline_load) / baseline.baseline_load) * 100 > 15 THEN 'Watch Load'
                WHEN ((target_week.training_load - baseline.baseline_load) / baseline.baseline_load) * 100 < -15 THEN 'Absorb'
                ELSE 'Balanced'
            END AS recovery_status
        FROM target_week
        CROSS JOIN baseline
        """,
        (int(target_week["week_offset"]),),
    ).fetchone()
    if not row:
        return None
    return weekly_intelligence_payload(dict(row))


def weekly_review_payload(weekly, intelligence):
    load_delta = intelligence["load_delta"]
    km_delta = intelligence["km_delta"]
    recovery_status = str(intelligence["recovery_status"] or "")

    if load_delta is None or km_delta is None:
        verdict = "先穩住節奏"
        learning = "你練到的不是跑得更多。你練到的是：先把規律放在數字前面。"
        focus = "這週真正留下來的，是規律。"
    elif load_delta > 15:
        verdict = "刺激偏高"
        learning = "你練到的不是跑得更快。你練到的是：開始承受更大的訓練刺激。"
        focus = "這週真正留下來的，是承受刺激的能力。"
    elif load_delta < -15:
        verdict = "吸收週"
        learning = "你練到的不是增加訓練。你練到的是：讓前面的刺激真正留下來。"
        focus = "這週真正留下來的，是吸收。"
    elif recovery_status.lower() == "balanced":
        verdict = "節奏穩住了"
        learning = "你練到的不是多做一堂課。你練到的是：把整體節奏穩穩留住。"
        focus = "這週真正留下來的，是穩定。"
    else:
        verdict = "整體可控"
        learning = "你練到的不是把計畫硬做完。你練到的是：把訓練壓力留在自己能承接的範圍裡。"
        focus = "這週真正留下來的，是可控感。"

    why = intelligence["coach_summary"]

    if load_delta is not None and load_delta > 15:
        looking_forward = "下週，只記住一件事：先把恢復留出來。"
    elif load_delta is not None and load_delta < -15:
        looking_forward = "下週，只記住一件事：慢慢把刺激帶回來。"
    else:
        looking_forward = "下週，只記住一件事：把這種穩定感留下來。"

    evidence_intro = "我會這樣看，因為這週的節奏、刺激與跑量都指向同一個學習。"

    return {
        "verdict": verdict,
        "learning_question": "這週，我到底練到了什麼？",
        "learning": learning,
        "why": why,
        "focus": focus,
        "looking_forward": looking_forward,
        "cause_question": "什麼真正讓你學會了這件事？",
        "evidence_intro": evidence_intro,
        "reasoning_steps": [
            ("先看學習", "#weekly-learning"),
            ("再看形成原因", "#weekly-cause"),
            ("再看關鍵課", "#weekly-key-activities"),
        ],
    }


def activity_split_summary(split_rows):
    if not split_rows:
        return {
            "pace_change_sec": None,
            "hr_change": None,
            "first_pace": None,
            "last_pace": None,
        }
    first = split_rows[0]
    last = split_rows[-1]
    first_pace = first["elapsed_pace_sec_per_km"]
    last_pace = last["elapsed_pace_sec_per_km"]
    first_hr = first["avg_hr"]
    last_hr = last["avg_hr"]
    pace_change = None
    hr_change = None
    if first_pace is not None and last_pace is not None:
        pace_change = float(last_pace) - float(first_pace)
    if first_hr is not None and last_hr is not None:
        hr_change = float(last_hr) - float(first_hr)
    return {
        "pace_change_sec": pace_change,
        "hr_change": hr_change,
        "first_pace": first_pace,
        "last_pace": last_pace,
    }


def activity_review_payload(activity, split_rows):
    workout = str(activity["workout_type_name_en"] or activity["activity_type"] or "").lower()
    distance = float(activity["distance_km"] or 0)
    training_load = float(activity["training_load"] or 0)
    temperature = activity["temperature_c"]
    stamina_start = activity["stamina_start_pct"]
    stamina_end = activity["stamina_end_pct"]
    stamina_drop = None
    if stamina_start is not None and stamina_end is not None:
        stamina_drop = float(stamina_start) - float(stamina_end)
    split_summary = activity_split_summary(split_rows)
    pace_change = split_summary["pace_change_sec"]
    hr_change = split_summary["hr_change"]
    is_hot = temperature is not None and float(temperature) >= 28
    quality_workout = any(token in workout for token in ("tempo", "interval", "repetition", "fartlek", "marathon pace"))
    long_run = any(token in workout for token in ("long run", "lsd")) or distance >= 18
    recovery_run = "recovery" in workout
    easy_run = "easy" in workout
    disrupted = quality_workout and ((pace_change is not None and pace_change >= 18) or (stamina_drop is not None and stamina_drop >= 25) or is_hot)

    if disrupted:
        learning = "你練到的不是完成原本的刺激。你練到的是：在狀態改變時，仍然把整體節奏留住。"
        focus = "這堂課真正留下來的，不是課表完成度，而是節奏。"
        reminder = "下一堂課，只記住一件事：先把節奏接回來，再決定要不要把刺激拉高。"
    elif recovery_run:
        learning = "你練到的不是增加刺激。你練到的是：讓前一段訓練真正被吸收。"
        focus = "這堂課真正留下來的，是吸收。"
        reminder = "下一堂課，只記住一件事：不要急著證明自己，先讓恢復站穩。"
    elif long_run:
        learning = "你練到的不是把距離撐完。你練到的是：在疲勞開始出現後，仍然守住耐力主線。"
        focus = "這堂課真正留下來的，是耐力主線。"
        reminder = "下一堂課，只記住一件事：先消化長跑留下來的壓力。"
    elif quality_workout:
        learning = "你練到的不是單純達標。你練到的是：在後半段仍然守住節奏。"
        focus = "這堂課真正留下來的，是品質節奏。"
        reminder = "下一堂課，只記住一件事：把今天的刺激留住，不要急著再堆下一層。"
    elif easy_run:
        learning = "你練到的不是跑得更快。你練到的是：把節奏穩穩接回來。"
        focus = "這堂課真正留下來的，是接回節奏。"
        reminder = "下一堂課，只記住一件事：延續這個穩定感。"
    else:
        learning = "你練到的不是把今天做完。你練到的是：把這堂課放回整體訓練節奏裡。"
        focus = "這堂課真正留下來的，是可延續性。"
        reminder = "下一堂課，只記住一件事：先延續今天能承接的東西。"

    if disrupted:
        why = "這堂課真正改變判讀的，不是原本的目標，而是你怎麼在狀態改變後保住節奏。"
    elif quality_workout:
        why = "這堂課真正有價值的地方，不只是刺激本身，而是你有沒有把刺激穩穩留到最後。"
    elif long_run:
        why = "這堂課真正重要的，不只是距離，而是耐力主線有沒有在後段繼續成立。"
    else:
        why = "這堂課真正重要的，不是數字漂不漂亮，而是它有沒有替整體節奏留下東西。"

    last_split_index = split_rows[-1]["split_index"] if split_rows else None
    middle_split_index = split_rows[len(split_rows) // 2]["split_index"] if len(split_rows) >= 3 else last_split_index

    cards = []
    if split_rows:
        if pace_change is not None:
            pace_label = "後段仍穩" if pace_change <= 8 else "後段回落"
            pace_note = (
                f"第一公里到最後一公里約慢了 {format_number(abs(pace_change), 0)} 秒。"
                if pace_change >= 0 else
                f"最後一公里仍比開頭快 {format_number(abs(pace_change), 0)} 秒。"
            )
        else:
            pace_label = "節奏待補"
            pace_note = "目前還沒有足夠 split 可以比較前後段。"
        cards.append({
            "title": "節奏反應",
            "value": pace_label,
            "note": pace_note,
            "fragment_anchor": "#fragment-finish",
            "evidence_anchor": f"#split-{last_split_index}" if last_split_index is not None else "#activity-evidence",
            "segment_label": "收尾狀態",
        })

    if training_load:
        load_label = f"負荷 {format_number(training_load, 0)}"
        if distance >= 16:
            load_note = "這堂課本身已經足夠形成耐力或品質壓力。"
        elif training_load >= 250:
            load_note = "這堂課本身的刺激不低，重點是之後怎麼承接。"
        else:
            load_note = "今天的刺激不算高，判讀更要看它放回整體節奏後的意義。"
        cards.append({
            "title": "刺激份量",
            "value": load_label,
            "note": load_note,
            "fragment_anchor": "#fragment-middle",
            "evidence_anchor": f"#split-{middle_split_index}" if middle_split_index is not None else "#activity-evidence",
            "segment_label": "中段反應",
        })

    if is_hot or stamina_drop is not None or hr_change is not None:
        body_parts = []
        if is_hot:
            body_parts.append(f"氣溫 {format_number(temperature, 0)}°C")
        if stamina_drop is not None:
            body_parts.append(f"Stamina -{format_number(stamina_drop, 0)}")
        if hr_change is not None:
            body_parts.append(f"HR {format_number(hr_change, 0)} bpm")
        body_label = " · ".join(body_parts) if body_parts else "身體有回應"
        body_note = "環境與身體回應一起決定了今天該怎麼理解，不只是看配速。"
        cards.append({
            "title": "身體訊號",
            "value": body_label,
            "note": body_note,
            "fragment_anchor": "#fragment-middle",
            "evidence_anchor": f"#split-{middle_split_index}" if middle_split_index is not None else "#activity-evidence",
            "segment_label": "中段反應",
        })

    evidence_intro = "我會這樣看，不是因為單一數字，而是因為這堂課的節奏、刺激與身體回應指向同一個學習。"

    return {
        "learning_question": "這堂課，我真正練到了什麼？",
        "cause_question": "什麼真正讓你學會了這件事？",
        "learning": learning,
        "focus": focus,
        "why": why,
        "looking_forward": reminder,
        "evidence_intro": evidence_intro,
        "cards": cards[:3],
        "reasoning_steps": [
            ("先看學習", "#activity-learning"),
            ("再看形成原因", "#activity-cause"),
            ("再看關鍵片段", "#activity-segments"),
            ("最後回到證據", "#activity-evidence"),
        ],
    }


def month_summary(connection):
    return connection.execute("SELECT * FROM current_month_summary_view").fetchone()


def available_months(connection):
    return connection.execute(
        """
        SELECT
            month_key,
            month_start,
            month_end
        FROM monthly_summary_view
        ORDER BY month_start DESC
        """
    ).fetchall()


def selected_month_summary(connection, month_key=None):
    if month_key:
        row = connection.execute(
            """
            WITH latest_activity AS (
                SELECT DATE(MAX(activity_start_time)) AS latest_date
                FROM activity
            )
            SELECT
                monthly_summary_view.*,
                latest_activity.latest_date,
                CASE
                    WHEN monthly_summary_view.month_start = DATE(latest_activity.latest_date, 'start of month')
                         AND latest_activity.latest_date < monthly_summary_view.month_end
                    THEN 1
                    ELSE 0
                END AS is_partial_month
            FROM monthly_summary_view
            CROSS JOIN latest_activity
            WHERE monthly_summary_view.month_key = ?
            """,
            (month_key,),
        ).fetchone()
        if row:
            return row
    return connection.execute("SELECT * FROM current_month_summary_view").fetchone()


def month_window(month_key):
    if not month_key:
        return None, None
    try:
        year, month = [int(part) for part in str(month_key).split("-", 1)]
        start = date(year, month, 1)
    except (TypeError, ValueError):
        return None, None
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    end = next_month - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def monthly_history(connection):
    return connection.execute(
        """
        SELECT
            month_start,
            month_end,
            month_key,
            activities,
            total_km,
            total_time_sec,
            avg_pace_sec_per_km,
            avg_hr,
            training_load
        FROM monthly_summary_view
        ORDER BY month_start DESC
        """
    ).fetchall()


def monthly_intelligence(connection):
    row = connection.execute("SELECT * FROM current_month_intelligence_view").fetchone()
    if not row:
        return None
    current = dict(row)
    load_delta = current["load_delta_pct"]
    km_delta = current["km_delta_pct"]
    activities_delta = current["activities_delta_pct"]
    partial = bool(current["is_partial_month"])

    if load_delta is None or km_delta is None:
        coach_summary = "月資料基準還在建立中，先累積 3 個完整月份後再看月度節奏。"
    elif partial:
        coach_summary = (
            f"目前是 {current['month_key']} 的月中進度，"
            "先把它當成進度表來看，完整月結束後再做更公平的月對月判讀。"
        )
    elif load_delta > 15:
        coach_summary = (
            f"本月訓練負荷較前 3 個月平均高 {format_delta_pct(load_delta)}，"
            "如果接近比賽或高峰週期，這是合理的；否則要留意恢復是否跟上。"
        )
    elif load_delta < -15:
        coach_summary = (
            f"本月訓練負荷較前 3 個月平均低 {abs(load_delta):.0f}%，"
            "這比較像吸收或調整月，可以觀察下個月是否重新把品質刺激拉回來。"
        )
    else:
        coach_summary = "本月負荷接近最近 3 個月平均，整體月節奏穩定，適合維持目前訓練結構。"

    return {
        "current": current,
        "baseline_km": current["baseline_km"],
        "baseline_load": current["baseline_load"],
        "baseline_activities": current["baseline_activities"],
        "baseline_load_per_km": current["baseline_load_per_km"],
        "km_delta": km_delta,
        "load_delta": load_delta,
        "activities_delta": activities_delta,
        "load_per_km_delta": current["load_per_km_delta_pct"],
        "current_load_per_km": current["current_load_per_km"],
        "is_partial_month": partial,
        "coach_summary": coach_summary,
    }


def selected_month_intelligence(connection, month_key=None):
    target_month = selected_month_summary(connection, month_key)
    if not target_month:
        return None

    row = connection.execute(
        """
        WITH latest_activity AS (
            SELECT DATE(MAX(activity_start_time)) AS latest_date
            FROM activity
        ),
        ranked_months AS (
            SELECT
                monthly_summary_view.*,
                ROW_NUMBER() OVER (ORDER BY month_start DESC) AS month_rank
            FROM monthly_summary_view
        ),
        target_month AS (
            SELECT
                ranked_months.*,
                latest_activity.latest_date,
                CASE
                    WHEN ranked_months.month_start = DATE(latest_activity.latest_date, 'start of month')
                         AND latest_activity.latest_date < ranked_months.month_end
                    THEN 1
                    ELSE 0
                END AS is_partial_month
            FROM ranked_months
            CROSS JOIN latest_activity
            WHERE ranked_months.month_key = ?
        ),
        baseline AS (
            SELECT
                AVG(total_km) AS baseline_km,
                AVG(training_load) AS baseline_load,
                AVG(activities) AS baseline_activities,
                AVG(
                    CASE
                        WHEN total_km > 0
                        THEN training_load * 1.0 / total_km
                        ELSE NULL
                    END
                ) AS baseline_load_per_km
            FROM ranked_months
            WHERE month_rank BETWEEN
                (SELECT month_rank + 1 FROM target_month)
                AND
                (SELECT month_rank + 3 FROM target_month)
        )
        SELECT
            target_month.month_start,
            target_month.month_end,
            target_month.month_key,
            target_month.activities,
            target_month.total_km,
            target_month.total_time_sec,
            target_month.avg_pace_sec_per_km,
            target_month.avg_hr,
            target_month.training_load,
            target_month.is_partial_month,
            CASE
                WHEN target_month.total_km > 0
                THEN ROUND(target_month.training_load * 1.0 / target_month.total_km, 1)
                ELSE NULL
            END AS current_load_per_km,
            ROUND(baseline.baseline_km, 2) AS baseline_km,
            ROUND(baseline.baseline_load, 1) AS baseline_load,
            ROUND(baseline.baseline_activities, 1) AS baseline_activities,
            ROUND(baseline.baseline_load_per_km, 1) AS baseline_load_per_km,
            CASE
                WHEN baseline.baseline_km > 0
                THEN ROUND(((target_month.total_km - baseline.baseline_km) / baseline.baseline_km) * 100, 1)
                ELSE NULL
            END AS km_delta_pct,
            CASE
                WHEN baseline.baseline_load > 0
                THEN ROUND(((target_month.training_load - baseline.baseline_load) / baseline.baseline_load) * 100, 1)
                ELSE NULL
            END AS load_delta_pct,
            CASE
                WHEN baseline.baseline_activities > 0
                THEN ROUND(((target_month.activities - baseline.baseline_activities) / baseline.baseline_activities) * 100, 1)
                ELSE NULL
            END AS activities_delta_pct,
            CASE
                WHEN baseline.baseline_load_per_km > 0 AND target_month.total_km > 0
                THEN ROUND((((target_month.training_load * 1.0 / target_month.total_km) - baseline.baseline_load_per_km) / baseline.baseline_load_per_km) * 100, 1)
                ELSE NULL
            END AS load_per_km_delta_pct
        FROM target_month
        CROSS JOIN baseline
        """,
        (target_month["month_key"],),
    ).fetchone()

    if not row:
        return None

    current = dict(row)
    load_delta = current["load_delta_pct"]
    km_delta = current["km_delta_pct"]
    activities_delta = current["activities_delta_pct"]
    partial = bool(current["is_partial_month"])

    if load_delta is None or km_delta is None:
        coach_summary = "月資料基準還在建立中，先累積 3 個完整月份後再看月度節奏。"
    elif partial:
        coach_summary = (
            f"目前是 {current['month_key']} 的月中進度，"
            "先把它當成進度表來看，完整月結束後再做更公平的月對月判讀。"
        )
    elif load_delta > 15:
        coach_summary = (
            f"本月訓練負荷較前 3 個月平均高 {format_delta_pct(load_delta)}，"
            "如果接近比賽或高峰週期，這是合理的；否則要留意恢復是否跟上。"
        )
    elif load_delta < -15:
        coach_summary = (
            f"本月訓練負荷較前 3 個月平均低 {abs(load_delta):.0f}%，"
            "這比較像吸收或調整月，可以觀察下個月是否重新把品質刺激拉回來。"
        )
    else:
        coach_summary = "本月負荷接近最近 3 個月平均，整體月節奏穩定，適合維持目前訓練結構。"

    return {
        "current": current,
        "baseline_km": current["baseline_km"],
        "baseline_load": current["baseline_load"],
        "baseline_activities": current["baseline_activities"],
        "baseline_load_per_km": current["baseline_load_per_km"],
        "km_delta": km_delta,
        "load_delta": load_delta,
        "activities_delta": activities_delta,
        "load_per_km_delta": current["load_per_km_delta_pct"],
        "current_load_per_km": current["current_load_per_km"],
        "is_partial_month": partial,
        "coach_summary": coach_summary,
    }


def selected_month_related_weeks(connection, month_key=None, limit=5):
    target_month = selected_month_summary(connection, month_key)
    if not target_month:
        return []
    start_date, end_date = month_window(target_month["month_key"])
    if not start_date or not end_date:
        return []

    rows = connection.execute(
        """
        SELECT
            week_offset,
            start_date,
            end_date,
            activities,
            total_km,
            training_load
        FROM weekly_summary_view
        WHERE start_date <= ?
          AND end_date >= ?
        ORDER BY start_date
        LIMIT ?
        """,
        (end_date, start_date, limit),
    ).fetchall()

    result = []
    for row in rows:
        intelligence = selected_week_intelligence(connection, row["week_offset"])
        load_delta = intelligence["load_delta"] if intelligence else None
        if load_delta is None:
            note = "這週還在建立自己的基準。"
        elif load_delta > 15:
            note = "這週把刺激往上推，是這個月的重要建構來源。"
        elif load_delta < -15:
            note = "這週把刺激收回來，幫這個月留下吸收空間。"
        else:
            note = "這週主要在把節奏穩穩接住。"
        verdict = weekly_review_payload(row, intelligence)["verdict"] if intelligence else "本週"
        result.append(
            {
                "week_offset": row["week_offset"],
                "start_date": row["start_date"],
                "end_date": row["end_date"],
                "activities": row["activities"],
                "total_km": row["total_km"],
                "training_load": row["training_load"],
                "verdict": verdict,
                "note": note,
            }
        )
    return result


def monthly_distribution(connection, limit=8):
    return connection.execute(
        """
        SELECT
            workout_type_name_en,
            primary_training_purpose_name_en,
            activity_count,
            total_km,
            avg_training_load
        FROM current_month_training_distribution_view
        ORDER BY total_km DESC, activity_count DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def selected_month_distribution(connection, month_key=None, limit=8):
    target_month = selected_month_summary(connection, month_key)
    if not target_month:
        return []
    return connection.execute(
        """
        SELECT
            COALESCE(activity_review_view.workout_type_name_en, 'Unassigned') AS workout_type_name_en,
            COALESCE(activity_review_view.primary_training_purpose_name_en, 'Unassigned') AS primary_training_purpose_name_en,
            COUNT(*) AS activity_count,
            ROUND(SUM(activity_review_view.distance_km), 2) AS total_km,
            ROUND(AVG(activity_review_view.training_load), 1) AS avg_training_load
        FROM activity_review_view
        WHERE activity_review_view.activity_date BETWEEN ? AND ?
        GROUP BY
            COALESCE(activity_review_view.workout_type_name_en, 'Unassigned'),
            COALESCE(activity_review_view.primary_training_purpose_name_en, 'Unassigned')
        ORDER BY total_km DESC, activity_count DESC
        LIMIT ?
        """,
        (target_month["month_start"], target_month["month_end"], limit),
    ).fetchall()


def selected_week_distribution(connection, week_offset=None, limit=6):
    target_week = selected_week_summary(connection, week_offset)
    if not target_week:
        return []
    return connection.execute(
        """
        SELECT
            COALESCE(activity_review_view.workout_type_name_en, 'Unassigned') AS workout_type_name_en,
            COALESCE(activity_review_view.primary_training_purpose_name_en, 'Unassigned') AS primary_training_purpose_name_en,
            COUNT(*) AS activity_count,
            ROUND(SUM(activity_review_view.distance_km), 2) AS total_km,
            ROUND(AVG(activity_review_view.training_load), 1) AS avg_training_load
        FROM activity_review_view
        WHERE activity_review_view.activity_date BETWEEN ? AND ?
        GROUP BY
            COALESCE(activity_review_view.workout_type_name_en, 'Unassigned'),
            COALESCE(activity_review_view.primary_training_purpose_name_en, 'Unassigned')
        ORDER BY total_km DESC, activity_count DESC
        LIMIT ?
        """,
        (target_week["start_date"], target_week["end_date"], limit),
    ).fetchall()


def monthly_progress(connection):
    return connection.execute("SELECT * FROM current_month_progress_view").fetchone()


def selected_month_progress(connection, month_key=None):
    target_month = selected_month_summary(connection, month_key)
    if not target_month:
        return None

    return connection.execute(
        """
        WITH latest_activity AS (
            SELECT DATE(MAX(activity_start_time)) AS latest_date
            FROM activity
        ),
        ranked_months AS (
            SELECT
                month_start,
                month_end,
                month_key,
                activities,
                total_km,
                training_load,
                ROW_NUMBER() OVER (ORDER BY month_start DESC) AS month_rank
            FROM monthly_summary_view
        ),
        target_month AS (
            SELECT
                ranked_months.*,
                latest_activity.latest_date,
                CASE
                    WHEN ranked_months.month_start = DATE(latest_activity.latest_date, 'start of month')
                         AND latest_activity.latest_date < ranked_months.month_end
                    THEN 1
                    ELSE 0
                END AS is_partial_month
            FROM ranked_months
            CROSS JOIN latest_activity
            WHERE ranked_months.month_key = ?
        ),
        progress AS (
            SELECT
                CASE
                    WHEN is_partial_month = 1
                    THEN CAST(STRFTIME('%d', latest_date) AS INTEGER)
                    ELSE CAST(STRFTIME('%d', month_end) AS INTEGER)
                END AS day_of_month,
                CAST(STRFTIME('%d', month_end) AS INTEGER) AS days_in_month,
                CASE
                    WHEN is_partial_month = 1
                    THEN CAST(STRFTIME('%d', latest_date) AS REAL) / CAST(STRFTIME('%d', month_end) AS REAL)
                    ELSE 1.0
                END AS progress_ratio
            FROM target_month
        ),
        month_session_counts AS (
            SELECT
                DATE(activity_date, 'start of month') AS month_start,
                SUM(CASE WHEN is_quality_session = 1 THEN 1 ELSE 0 END) AS quality_sessions,
                SUM(CASE WHEN is_long_run = 1 THEN 1 ELSE 0 END) AS long_runs
            FROM activity_review_view
            GROUP BY DATE(activity_date, 'start of month')
        ),
        current_session_counts AS (
            SELECT
                COALESCE(quality_sessions, 0) AS quality_sessions,
                COALESCE(long_runs, 0) AS long_runs
            FROM month_session_counts
            WHERE month_start = (SELECT month_start FROM target_month)
        ),
        baseline_months AS (
            SELECT month_start
            FROM ranked_months
            WHERE month_rank BETWEEN
                (SELECT month_rank + 1 FROM target_month)
                AND
                (SELECT month_rank + 3 FROM target_month)
        ),
        baseline_summary AS (
            SELECT
                AVG(activities) AS baseline_activities,
                AVG(total_km) AS baseline_km,
                AVG(training_load) AS baseline_load
            FROM monthly_summary_view
            WHERE month_start IN (SELECT month_start FROM baseline_months)
        ),
        baseline_session_counts AS (
            SELECT
                AVG(quality_sessions) AS baseline_quality_sessions,
                AVG(long_runs) AS baseline_long_runs
            FROM month_session_counts
            WHERE month_start IN (SELECT month_start FROM baseline_months)
        )
        SELECT
            target_month.month_key,
            progress.day_of_month,
            progress.days_in_month,
            ROUND(progress.progress_ratio * 100, 1) AS progress_pct,
            target_month.activities AS current_activities,
            target_month.total_km AS current_km,
            target_month.training_load AS current_load,
            COALESCE(current_session_counts.quality_sessions, 0) AS current_quality_sessions,
            COALESCE(current_session_counts.long_runs, 0) AS current_long_runs,
            ROUND(baseline_summary.baseline_activities, 1) AS baseline_activities,
            ROUND(baseline_summary.baseline_km, 2) AS baseline_km,
            ROUND(baseline_summary.baseline_load, 1) AS baseline_load,
            ROUND(baseline_session_counts.baseline_quality_sessions, 1) AS baseline_quality_sessions,
            ROUND(baseline_session_counts.baseline_long_runs, 1) AS baseline_long_runs,
            ROUND(baseline_summary.baseline_activities * progress.progress_ratio, 1) AS target_activities_to_date,
            ROUND(baseline_summary.baseline_km * progress.progress_ratio, 1) AS target_km_to_date,
            ROUND(baseline_summary.baseline_load * progress.progress_ratio, 1) AS target_load_to_date,
            ROUND(baseline_session_counts.baseline_quality_sessions * progress.progress_ratio, 1) AS target_quality_to_date,
            ROUND(baseline_session_counts.baseline_long_runs * progress.progress_ratio, 1) AS target_long_runs_to_date
        FROM target_month
        LEFT JOIN current_session_counts ON 1 = 1
        LEFT JOIN baseline_summary ON 1 = 1
        LEFT JOIN baseline_session_counts ON 1 = 1
        CROSS JOIN progress
        """,
        (target_month["month_key"],),
    ).fetchone()


def monthly_key_sessions(connection):
    return connection.execute(
        """
        SELECT
            key_session_type,
            activity_id,
            activity_start_time,
            activity_name,
            activity_type,
            distance_km,
            avg_pace_sec_per_km,
            avg_hr,
            training_load,
            shoe_display_name,
            workout_type_name_en
        FROM current_month_key_sessions_view
        """
    ).fetchall()


def selected_month_key_sessions(connection, month_key=None):
    target_month = selected_month_summary(connection, month_key)
    if not target_month:
        return []
    return connection.execute(
        """
        WITH current_rows AS (
            SELECT *
            FROM activity_review_view
            WHERE activity_date BETWEEN ? AND ?
        ),
        longest AS (
            SELECT 'Longest Run' AS key_session_type, *
            FROM current_rows
            ORDER BY distance_km DESC, duration_sec DESC, activity_start_time DESC
            LIMIT 1
        ),
        highest_load AS (
            SELECT 'Highest Load' AS key_session_type, *
            FROM current_rows
            WHERE training_load IS NOT NULL
            ORDER BY training_load DESC, distance_km DESC, activity_start_time DESC
            LIMIT 1
        ),
        fastest_quality AS (
            SELECT 'Fastest Quality' AS key_session_type, *
            FROM current_rows
            WHERE is_quality_session = 1
              AND avg_pace_sec_per_km IS NOT NULL
            ORDER BY avg_pace_sec_per_km ASC, distance_km DESC, activity_start_time DESC
            LIMIT 1
        ),
        lowest_hr_easy AS (
            SELECT 'Lowest HR Easy' AS key_session_type, *
            FROM current_rows
            WHERE intensity_category IN ('Recovery', 'Easy')
              AND avg_hr IS NOT NULL
            ORDER BY avg_hr ASC, distance_km DESC, activity_start_time DESC
            LIMIT 1
        ),
        combined AS (
            SELECT * FROM longest
            UNION ALL
            SELECT * FROM highest_load
            UNION ALL
            SELECT * FROM fastest_quality
            UNION ALL
            SELECT * FROM lowest_hr_easy
        )
        SELECT
            key_session_type,
            activity_id,
            activity_start_time,
            activity_name,
            activity_type,
            distance_km,
            avg_pace_sec_per_km,
            avg_hr,
            training_load,
            shoe_display_name,
            workout_type_name_en
        FROM combined
        """,
        (target_month["month_start"], target_month["month_end"]),
    ).fetchall()


def selected_week_key_sessions(connection, week_offset=None):
    target_week = selected_week_summary(connection, week_offset)
    if not target_week:
        return []
    return connection.execute(
        """
        WITH current_rows AS (
            SELECT *
            FROM activity_review_view
            WHERE activity_date BETWEEN ? AND ?
        ),
        longest AS (
            SELECT 'Longest Run' AS key_session_type, *
            FROM current_rows
            ORDER BY distance_km DESC, duration_sec DESC, activity_start_time DESC
            LIMIT 1
        ),
        highest_load AS (
            SELECT 'Highest Load' AS key_session_type, *
            FROM current_rows
            WHERE training_load IS NOT NULL
            ORDER BY training_load DESC, distance_km DESC, activity_start_time DESC
            LIMIT 1
        ),
        fastest_quality AS (
            SELECT 'Fastest Quality' AS key_session_type, *
            FROM current_rows
            WHERE is_quality_session = 1
              AND avg_pace_sec_per_km IS NOT NULL
            ORDER BY avg_pace_sec_per_km ASC, distance_km DESC, activity_start_time DESC
            LIMIT 1
        ),
        lowest_hr_easy AS (
            SELECT 'Lowest HR Easy' AS key_session_type, *
            FROM current_rows
            WHERE intensity_category IN ('Recovery', 'Easy')
              AND avg_hr IS NOT NULL
            ORDER BY avg_hr ASC, distance_km DESC, activity_start_time DESC
            LIMIT 1
        ),
        combined AS (
            SELECT * FROM longest
            UNION ALL
            SELECT * FROM highest_load
            UNION ALL
            SELECT * FROM fastest_quality
            UNION ALL
            SELECT * FROM lowest_hr_easy
        )
        SELECT
            key_session_type,
            activity_id,
            activity_start_time,
            activity_name,
            activity_type,
            distance_km,
            avg_pace_sec_per_km,
            avg_hr,
            training_load,
            shoe_display_name,
            workout_type_name_en
        FROM combined
        """,
        (target_week["start_date"], target_week["end_date"]),
    ).fetchall()


def monthly_assignment_quality(connection):
    return connection.execute("SELECT * FROM current_month_assignment_quality_view").fetchone()


def selected_month_assignment_quality(connection, month_key=None):
    target_month = selected_month_summary(connection, month_key)
    if not target_month:
        return None
    return connection.execute(
        """
        SELECT
            COUNT(*) AS total_activities,
            SUM(CASE WHEN workout_type_id IS NOT NULL THEN 1 ELSE 0 END) AS workout_tagged_activities,
            SUM(CASE WHEN primary_training_purpose_id IS NOT NULL THEN 1 ELSE 0 END) AS purpose_tagged_activities,
            SUM(CASE WHEN workout_type_id IS NOT NULL AND primary_training_purpose_id IS NOT NULL THEN 1 ELSE 0 END) AS fully_tagged_activities,
            ROUND(
                SUM(CASE WHEN workout_type_id IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
                1
            ) AS workout_tagged_pct,
            ROUND(
                SUM(CASE WHEN primary_training_purpose_id IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
                1
            ) AS purpose_tagged_pct,
            ROUND(
                SUM(CASE WHEN workout_type_id IS NOT NULL AND primary_training_purpose_id IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
                1
            ) AS fully_tagged_pct
        FROM activity_review_view
        WHERE activity_date BETWEEN ? AND ?
        """,
        (target_month["month_start"], target_month["month_end"]),
    ).fetchone()


def training_distribution(connection, limit=6):
    return connection.execute(
        """
        SELECT
            workout_type_name_en,
            primary_training_purpose_name_en,
            activity_count,
            total_km,
            avg_training_load
        FROM training_distribution_view
        ORDER BY total_km DESC, activity_count DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def training_balance(connection):
    return connection.execute(
        """
        SELECT
            intensity_category,
            activity_count,
            total_km,
            total_time_sec,
            avg_training_load,
            total_training_load
        FROM training_balance_view
        ORDER BY total_km DESC, activity_count DESC
        """
    ).fetchall()


def training_assignment_quality(connection):
    return connection.execute("SELECT * FROM training_assignment_quality_view").fetchone()


def recent_training_intent(connection, limit=8):
    return connection.execute(
        """
        SELECT
            activity_id,
            activity_start_time,
            activity_name,
            activity_type,
            distance_km,
            training_load,
            workout_type_name_en,
            primary_training_purpose_name_en,
            secondary_training_purpose_names_en,
            intensity_category,
            shoe_display_name
        FROM recent_training_intent_view
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def shoes_overview(connection):
    return connection.execute(
        """
        SELECT
            shoe_id,
            shoe_code,
            brand,
            model,
            nickname,
            category,
            is_active,
            run_count,
            total_distance_km,
            observed_first_run_time,
            observed_last_run_time,
            avg_hr,
            avg_pace_sec_per_km,
            avg_training_load,
            avg_cadence_spm
        FROM shoe_comparison_view
        ORDER BY total_distance_km DESC, run_count DESC, shoe_id
        """
    ).fetchall()


def shoe_status_rows(connection):
    return connection.execute(
        """
        SELECT
            id,
            shoe_code,
            brand,
            model,
            nickname,
            category,
            is_active,
            retire_date,
            notes
        FROM shoe
        ORDER BY is_active DESC, brand, model, nickname, shoe_code
        """
    ).fetchall()


def shoe_intelligence(connection):
    return connection.execute(
        """
        SELECT
            shoe_id,
            shoe_code,
            shoe_display_name,
            category,
            is_active,
            run_count,
            total_distance_km,
            avg_pace_sec_per_km,
            avg_hr,
            avg_training_load,
            avg_cadence_spm,
            tagged_activity_count,
            tagged_total_km,
            tagged_avg_hr,
            tagged_avg_pace_sec_per_km,
            tagged_avg_training_load,
            tagged_avg_cadence_spm,
            tagged_avg_gct_ms,
            tagged_avg_stride_length_mm
        FROM shoe_intelligence_view
        ORDER BY total_distance_km DESC, run_count DESC, shoe_id
        """
    ).fetchall()


def shoe_workout_comparison(connection, limit=12):
    return connection.execute(
        """
        SELECT
            shoe_display_name,
            workout_type_name_en,
            activity_count,
            total_km,
            avg_pace_sec_per_km,
            avg_hr,
            avg_training_load,
            avg_cadence_spm,
            avg_gct_ms,
            avg_stride_length_mm
        FROM shoe_workout_comparison_view
        ORDER BY total_km DESC, activity_count DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def coach_today(intelligence, latest_activity):
    if not intelligence or not latest_activity:
        return None
    load_delta = intelligence["load_delta"]
    latest_date = parse_date(latest_activity["activity_start_time"])
    current_date = parse_date(intelligence["current"]["end_date"])
    days_since_activity = None
    if latest_date and current_date:
        days_since_activity = (current_date - latest_date).days

    stamina_drop = None
    if latest_activity["stamina_start_pct"] is not None and latest_activity["stamina_end_pct"] is not None:
        stamina_drop = latest_activity["stamina_start_pct"] - latest_activity["stamina_end_pct"]

    latest_load = latest_activity["training_load"] or 0
    if load_delta is not None and load_delta < -15 and latest_load < 180 and (stamina_drop is None or stamina_drop <= 25):
        status = "可刺激"
        suggestion = "安排品質刺激"
        reason = "本週負荷低於前四週平均，最近一次活動負荷不高，適合安排一次品質刺激。"
    elif latest_load >= 250 or (load_delta is not None and load_delta > 15):
        status = "先恢復"
        suggestion = "恢復跑"
        reason = "最近訓練負荷偏高，今天優先保留恢復空間會比較穩。"
    elif days_since_activity is not None and days_since_activity >= 2:
        status = "重啟節奏"
        suggestion = "輕鬆跑"
        reason = "距離上次活動已有一段時間，建議用輕鬆跑重新接回節奏。"
    else:
        status = "平衡"
        suggestion = "輕鬆有氧"
        reason = "目前週負荷接近可控區間，今天適合維持有氧節奏。"

    return {
        "status": status,
        "suggestion": suggestion,
        "reason": reason,
        "latest_activity": latest_activity,
    }


def first_sentence(text):
    if value_is_blank(text):
        return ""
    content = str(text).strip()
    for marker in ("。", "！", "？"):
        if marker in content:
            return content.split(marker, 1)[0] + marker
    return content


def monthly_overview_payload(monthly, intelligence, progress_row):
    if not monthly or not intelligence:
        return None
    progress_pct = progress_row["progress_pct"] if progress_row else None
    quality_sessions = int(progress_row["current_quality_sessions"] or 0) if progress_row else 0
    long_runs = int(progress_row["current_long_runs"] or 0) if progress_row else 0

    if quality_sessions >= 3:
        phase = "品質建構"
    elif long_runs >= 2:
        phase = "耐力累積"
    elif quality_sessions >= 1:
        phase = "平衡建構"
    else:
        phase = "基礎累積"

    if intelligence["is_partial_month"]:
        verdict = "正常"
        verdict_reason = (
            f"目前仍屬於正常累積。因為本月只完成 {format_number(progress_pct, 0)}%，"
            "目前負荷與里程都還在可接受區間。"
        )
    elif intelligence["load_delta"] is not None and intelligence["load_delta"] < -15:
        verdict = "吸收月"
        verdict_reason = "本月整體偏向吸收與調整，負荷低於近期平均，但方向仍然合理。"
    elif intelligence["load_delta"] is not None and intelligence["load_delta"] > 15:
        verdict = "負荷建構"
        verdict_reason = "本月負荷高於近期平均，代表正處於明顯的建構期，恢復品質會變得更重要。"
    else:
        verdict = "平衡建構"
        verdict_reason = "本月方向整體平衡，里程、品質課與長跑配置都還在合理範圍內。"

    return {
        "phase": phase,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "progress_pct": progress_pct,
    }


def overview_attention_payload(connection):
    ranked = rank_candidates(evaluate_candidates(live_signals(connection)))
    if not ranked:
        return {
            "has_focus": False,
            "title": "今天沒有需要特別處理的訊號",
            "why": "目前各項節奏穩定，照原本計畫走就好。",
            "evidence": (),
            "cta": "回顧本週學到了什麼",
            "href": "/?" + urlencode({"page": "weekly"}),
            "secondary_note": None,
        }

    primary = ranked[0]
    secondary = ranked[1] if len(ranked) > 1 else None

    def tighten_evidence_line(text):
        return str(text).strip().rstrip("。")

    def surface_link(target_surface):
        if target_surface == "weekly":
            return "查看本週反思", "/?" + urlencode({"page": "weekly"})
        if target_surface == "monthly":
            return "查看本月定位", "/?" + urlencode({"page": "monthly"})
        if target_surface == "shoes":
            return "查看鞋款狀態", "/?" + urlencode({"page": "shoes"})
        return "查看更多", "/?" + urlencode({"page": "home"})

    cta, href = surface_link(primary.target_surface)
    why = "，".join(tighten_evidence_line(item) for item in primary.evidence[:2]) + "。" if primary.evidence else "今天這個焦點，比其他訊號更值得先看。"

    secondary_note = None
    if secondary and secondary.attention_label:
        secondary_note = secondary.attention_label.removeprefix("今天最該關心的是")
        secondary_note = secondary_note.strip() + "。"

    return {
        "has_focus": True,
        "title": primary.attention_label or "今天先看這件事",
        "why": why,
        "evidence": primary.evidence[:3],
        "cta": cta,
        "href": href,
        "secondary_note": secondary_note,
    }


def coach_desk_focus_route(today, weekly_review, monthly_overview, story, latest_activity):
    if monthly_overview and monthly_overview["progress_pct"] is not None and float(monthly_overview["progress_pct"]) >= 75:
        return {
            "page": "monthly",
            "label": "月回顧",
            "title": str(monthly_overview["verdict"]),
            "reason": "如果今天只能花五分鐘，我會希望你先回頭看這個月，確認整體方向有沒有對齊。",
            "cta": f"先讀這封{monthly_overview['verdict']}的月信",
            "href": "/?" + urlencode({"page": "monthly"}),
        }
    if latest_activity:
        return {
            "page": "weekly",
            "label": "週回顧",
            "title": str(weekly_review["verdict"]) if weekly_review else "本週檢討",
            "reason": "如果今天只能先看一頁，我會希望你先回頭看看這一週，整理這週到底學到了什麼。",
            "cta": f"先看這週為什麼{weekly_review['verdict']}" if weekly_review else "先看這週檢討",
            "href": "/?" + urlencode({"page": "weekly"}),
        }
    return {
        "page": "home",
        "label": "總覽",
        "title": "今天",
        "reason": "今天先把節奏站穩，比急著往下翻更重要。",
        "cta": "先從今天開始",
        "href": "/?" + urlencode({"page": "home"}),
    }


def coach_desk_panel(attention, weekly_review, monthly_overview, monthly_review, story, latest_activity):
    if not attention:
        return ""

    latest_line = ""
    if latest_activity:
        latest_href = "/?" + urlencode({"page": "activity", "activity": latest_activity["activity_id"]})
        latest_summary = (
            f"{format_short_datetime(latest_activity['activity_start_time'])} · "
            f"{format_number(latest_activity['distance_km'], 2)} km · "
            f"{format_pace_seconds(latest_activity['avg_pace_sec_per_km'])}"
        )
        latest_line = (
            f'<p class="note">最近一次：<a href="{html.escape(latest_href, quote=True)}">'
            f"{html.escape(latest_summary)}</a></p>"
        )

    weekly_href = "/?" + urlencode({"page": "weekly"})
    monthly_href = "/?" + urlencode({"page": "monthly"})

    weekly_line = weekly_review["focus"] if weekly_review else "先讓這週的節奏說話。"
    monthly_line = first_sentence(monthly_review["coach_summary"]) if monthly_review else "先把這個月的方向看清楚。"
    evidence_html = ""
    if attention["evidence"]:
        evidence_html = "<ul class=\"coach-attention-evidence\">" + "".join(
            f"<li>{html.escape(item)}</li>" for item in attention["evidence"]
        ) + "</ul>"

    return f"""
      <section class="panel-section">
        <h2>今天先看什麼</h2>
        <div class="coach-attention-card{' no-focus' if not attention['has_focus'] else ''}">
          <span>今天最該先放注意力的地方</span>
          <strong>{html.escape(attention["title"])}</strong>
          <p>{html.escape(attention["why"])}</p>
          {evidence_html}
          <div class="coach-attention-footer">
            <a class="desk-link" href="{html.escape(attention['href'], quote=True)}">{html.escape(attention['cta'])}</a>
            {f'<small>另外留意：{html.escape(attention["secondary_note"])}</small>' if attention["secondary_note"] else ""}
          </div>
          {latest_line}
        </div>
      </section>
      <section class="panel-section">
        <h2>今天可以從這裡往下看</h2>
        <div class="coach-desk-route-grid">
          <a class="coach-route-card" href="{html.escape(weekly_href, quote=True)}">
            <span>週回顧</span>
            <strong>本週學到了什麼</strong>
            <p>{html.escape(weekly_line)}</p>
          </a>
          <a class="coach-route-card" href="{html.escape(monthly_href, quote=True)}">
            <span>月回顧</span>
            <strong>教練這個月怎麼看你</strong>
            <p>{html.escape(monthly_line)}</p>
          </a>
        </div>
      </section>
    """    


def rac_is_running(host=RAC_HOST, port=RAC_PORT, timeout=0.25):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def ensure_rac_running():
    if rac_is_running():
        return True
    if not RAC_APP_PATH.exists():
        return False

    rac_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    python_cmd = str(rac_python) if rac_python.exists() else (sys.executable or "python3")

    RAC_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RAC_LOG_PATH.open("ab") as log_file:
        subprocess.Popen(
            [python_cmd, str(RAC_APP_PATH)],
            cwd=str(PROJECT_ROOT),
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
        )

    for _ in range(12):
        if rac_is_running():
            return True
        time.sleep(0.25)
    return False


def rac_entry_panel():
    href = "/open-rac"
    status = "資料匯入工具已就緒" if rac_is_running() else "從這裡進入 FIT 匯入與資料整理"
    note = (
        "把 FIT 轉成 Excel、補活動資訊、寫回 SQLite，然後再回到 Running Intelligence Platform 繼續看 Activity、Weekly、Monthly。"
    )
    return f"""
      <section class="panel-section">
        <h2>資料入口</h2>
        <div class="coach-attention-card">
          <span>資料匯入工具</span>
          <strong>先進入 FIT 匯入與資料整理</strong>
          <p>{html.escape(note)}</p>
          <div class="coach-attention-footer">
            <a class="desk-link" href="{html.escape(href, quote=True)}">進入資料匯入工具</a>
            <small>{html.escape(status)}</small>
          </div>
        </div>
      </section>
    """


def no_data_yet_panel():
    return f"""
      <section class="panel-section">
        <h2>先開始第一批資料</h2>
        <div class="coach-attention-card no-focus">
          <span>第一次使用</span>
          <strong>目前還沒有跑步資料</strong>
          <p>這不是錯誤。先進入資料匯入工具匯入第一批 FIT，平台就會開始長出 Activity、Weekly、Monthly 與 Overview。</p>
          <ul class="coach-attention-evidence">
            <li>先選一個或幾個 FIT 檔</li>
            <li>轉成 Excel 並寫回 SQLite</li>
            <li>回到平台重新整理，就能開始看教練式回顧</li>
          </ul>
          <div class="coach-attention-footer">
            <a class="desk-link" href="/open-rac">先進入資料匯入工具</a>
            <small>第一批資料匯入後，首頁會自動變成真正的 Overview。</small>
          </div>
        </div>
      </section>
    """


def monthly_recommendation_plan(intelligence):
    if intelligence["is_partial_month"]:
        return (
            "maintain",
            "這個月先別急著追更多公里。把現在的節奏穩住、留住一次長跑，月底再決定要不要把品質課再往上推。",
        )
    if intelligence["load_delta"] is not None and intelligence["load_delta"] < -15:
        return (
            "bring_back_quality",
            "下個月不用一下子加滿。先把節奏慢慢拉回來，找回一到兩次 Threshold 或 Tempo 課就夠了。",
        )
    if intelligence["load_delta"] is not None and intelligence["load_delta"] > 15:
        return (
            "protect_recovery",
            "下個月先把恢復擺前面。保留一次長跑就夠，不需要再硬塞額外負荷。",
        )
    return (
        "maintain_threshold",
        "下個月不用大改。把現在這個節奏延續下去，維持 Threshold 方向，再留一次長跑讓耐力站穩。",
    )


def monthly_coach_memory(connection, selected_month):
    months = [str(row["month_key"]) for row in available_months(connection)]
    if selected_month not in months:
        return None
    index = months.index(selected_month)
    if index + 1 >= len(months):
        return None

    previous_month_key = months[index + 1]
    previous_intelligence = selected_month_intelligence(connection, previous_month_key)
    current_progress = selected_month_progress(connection, selected_month)
    if not previous_intelligence or not current_progress:
        return None

    previous_plan_key, previous_recommendation = monthly_recommendation_plan(previous_intelligence)
    current_quality = int(current_progress["current_quality_sessions"] or 0)
    current_long_runs = int(current_progress["current_long_runs"] or 0)

    if previous_plan_key == "bring_back_quality":
        follow_up = (
            f"本月目前已完成 {current_quality} 次品質課，已開始把刺激拉回來。"
            if current_quality >= 1
            else "本月目前還沒看到品質課，是否延續上月建議仍待觀察。"
        )
    elif previous_plan_key == "protect_recovery":
        follow_up = (
            "本月目前仍以吸收與穩定累積為主，和上月的恢復建議一致。"
            if current_quality <= 1
            else "本月已重新加入較多刺激，之後要留意是否回得太快。"
        )
    elif previous_plan_key == "maintain_threshold":
        follow_up = (
            f"本月目前已完成 {current_quality} 次品質課、{current_long_runs} 次長跑，延續方向算是成立。"
            if current_quality >= 1
            else "本月目前仍偏累積，Threshold 方向是否延續，還要再看後半月。"
        )
    else:
        follow_up = (
            "本月目前維持原有節奏，和上月的穩定建議一致。"
            if current_long_runs >= 1
            else "本月目前仍在建立節奏，月底再看是否確實維持住。"
        )

    return {
        "previous_month_key": previous_month_key,
        "previous_recommendation": previous_recommendation,
        "follow_up": follow_up,
    }


def journey_story(connection, month_key=None):
    target_month = selected_month_summary(connection, month_key)
    if not target_month:
        return None
    return connection.execute(
        """
        SELECT *
        FROM journey_month_story_view
        WHERE month_key = ?
        """,
        (target_month["month_key"],),
    ).fetchone()


def journey_timeline(connection):
    return connection.execute(
        """
        SELECT
            month_key,
            month_start,
            month_end,
            total_km,
            training_load,
            activities,
            chapter_code,
            chapter_label,
            coach_verdict
        FROM journey_month_story_view
        ORDER BY month_start
        """
    ).fetchall()


def journey_turning_points(connection, month_key=None, limit=6):
    target_month = selected_month_summary(connection, month_key)
    if not target_month:
        return []
    return connection.execute(
        """
        SELECT
            month_key,
            month_start,
            milestone_code,
            milestone_title,
            milestone_note
        FROM journey_turning_point_view
        WHERE month_start <= (
            SELECT month_start
            FROM journey_month_story_view
            WHERE month_key = ?
        )
        ORDER BY month_start DESC, milestone_code
        LIMIT ?
        """,
        (target_month["month_key"], limit),
    ).fetchall()


def recent_activities(connection, limit=10):
    return connection.execute(
        """
        SELECT
            activity_id,
            activity_start_time,
            activity_type,
            activity_name,
            distance_km,
            avg_pace_sec_per_km,
            avg_hr,
            training_load,
            workout_type_name_en,
            shoe_display_name,
            primary_training_purpose_name_en
        FROM recent_activity_view
        ORDER BY activity_start_time DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def available_activities(connection, limit=500):
    return connection.execute(
        """
        SELECT
            activity_id,
            activity_start_time,
            activity_type,
            activity_name,
            distance_km,
            workout_type_name_en,
            primary_training_purpose_name_en
        FROM recent_activity_view
        ORDER BY activity_start_time DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def selected_activity(connection, activity_id):
    if activity_id:
        row = connection.execute(
            """
            SELECT
                activity_id,
                activity_start_time,
                activity_type,
                activity_name,
                distance_km,
                duration_sec,
                workout_type_id,
                shoe_id,
                workout_type_name_en,
                shoe_display_name,
                primary_training_purpose_name_en,
                secondary_training_purpose_names_en,
                avg_pace_sec_per_km,
                avg_hr,
                training_load,
                stamina_start_pct,
                stamina_end_pct,
                temperature_c,
                humidity_pct,
                weather_description,
                garmin_feeling,
                garmin_perceived_effort
            FROM activity_review_view
            WHERE activity_id = ?
            """,
            (activity_id,),
        ).fetchone()
        if row:
            return row
    return connection.execute(
        """
        SELECT
            activity_id,
            activity_start_time,
            activity_type,
            activity_name,
            distance_km,
            duration_sec,
            workout_type_id,
            shoe_id,
            workout_type_name_en,
            shoe_display_name,
            primary_training_purpose_name_en,
            secondary_training_purpose_names_en,
            avg_pace_sec_per_km,
            avg_hr,
            training_load,
            stamina_start_pct,
            stamina_end_pct,
            temperature_c,
            humidity_pct,
            weather_description,
            garmin_feeling,
            garmin_perceived_effort
        FROM activity_review_view
        ORDER BY activity_start_time DESC
        LIMIT 1
        """
    ).fetchone()


def splits(connection, activity_id):
    if not activity_id:
        return []
    return connection.execute(
        """
        SELECT
            split_index,
            split_distance_m,
            elapsed_pace_sec_per_km,
            avg_hr,
            avg_power_w,
            avg_cadence_spm
        FROM kilometer_split_view
        WHERE activity_id = ?
        ORDER BY split_index
        """,
        (activity_id,),
    ).fetchall()


def chart_points(values, width, height, padding, lower_is_better=False):
    numeric = [float(value) if isinstance(value, (int, float)) else None for value in values]
    actual = [value for value in numeric if value is not None]
    if len(actual) < 2:
        return []
    low = min(actual)
    high = max(actual)
    spread = high - low or 1
    step = (width - padding * 2) / (len(numeric) - 1)
    points = []
    for index, value in enumerate(numeric):
        if value is None:
            continue
        x = padding + index * step
        normalized = (value - low) / spread
        if lower_is_better:
            y = padding + normalized * (height - padding * 2)
        else:
            y = height - padding - normalized * (height - padding * 2)
        points.append((index, value, x, y))
    return points


def polyline_points(points):
    return " ".join(f"{x:.1f},{y:.1f}" for _index, _value, x, y in points)


def point_markers(points, css_class, split_rows):
    markers = []
    for index, _value, x, y in points:
        row = split_rows[index]
        title = (
            f"KM {row['split_index']} | "
            f"配速 {format_pace_seconds(row['elapsed_pace_sec_per_km']) or '-'} | "
            f"HR {row['avg_hr'] if row['avg_hr'] is not None else '-'} | "
            f"功率 {str(row['avg_power_w']) + 'W' if row['avg_power_w'] is not None else '-'}"
        )
        markers.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" class="marker {css_class}">'
            f"<title>{html.escape(title)}</title></circle>"
        )
    return "".join(markers)


def range_label(label, values, formatter):
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    if not numeric:
        return ""
    low = min(numeric)
    high = max(numeric)
    return f"""
      <span>
        <b>{html.escape(label)}</b>
        {html.escape(formatter(low))} – {html.escape(formatter(high))}
      </span>
    """


def trend_svg(split_rows):
    if not split_rows:
        return '<p class="note">目前沒有 split 可畫趨勢。</p>'
    width = 860
    height = 260
    padding = 28
    pace_values = [row["elapsed_pace_sec_per_km"] for row in split_rows]
    hr_values = [row["avg_hr"] for row in split_rows]
    power_values = [row["avg_power_w"] for row in split_rows]
    pace = chart_points(pace_values, width, height, padding, lower_is_better=True)
    hr = chart_points(hr_values, width, height, padding)
    power = chart_points(power_values, width, height, padding)
    pace_range = range_label("配速", pace_values, format_pace_seconds)
    hr_range = range_label("HR", hr_values, lambda value: f"{int(round(value))} bpm")
    power_range = range_label("功率", power_values, lambda value: f"{int(round(value))} W")
    return f"""
      <div class="chart-panel">
        <svg viewBox="0 0 {width} {height}" role="img" aria-label="配速 心率 功率 趨勢">
          <line x1="{padding}" y1="{height - padding}" x2="{width - padding}" y2="{height - padding}" class="axis" />
          <line x1="{padding}" y1="{padding}" x2="{padding}" y2="{height - padding}" class="axis" />
          <polyline points="{polyline_points(pace)}" class="trend pace-line" />
          <polyline points="{polyline_points(hr)}" class="trend hr-line" />
          <polyline points="{polyline_points(power)}" class="trend power-line" />
          {point_markers(pace, "pace-marker", split_rows)}
          {point_markers(hr, "hr-marker", split_rows)}
          {point_markers(power, "power-marker", split_rows)}
        </svg>
        <div class="axis-ranges">{pace_range}{hr_range}{power_range}</div>
        <div class="legend">
          <span><i class="pace-dot"></i>配速</span>
          <span><i class="hr-dot"></i>HR</span>
          <span><i class="power-dot"></i>功率</span>
        </div>
      </div>
    """


def activity_selector_bar(rows, selected_activity_id):
    if not rows:
        return ""
    active_row = None
    options = []
    for row in rows:
        activity_key = str(row["activity_id"])
        label = (
            f"{str(row['activity_start_time']).replace('T', ' ')[:16]} · "
            f"{str(row['activity_name'] or row['activity_type'] or '活動')} · "
            f"{format_number(row['distance_km'], 2)} km"
        )
        selected = " selected" if activity_key == str(selected_activity_id) else ""
        options.append(
            f'<option value="{html.escape(activity_key, quote=True)}"{selected}>{html.escape(label)}</option>'
        )
        if activity_key == str(selected_activity_id):
            active_row = row
    if active_row is None:
        active_row = rows[0]
    return f"""
      <section class="panel-section">
        <div class="month-selector-bar">
          <div>
            <span class="eyebrow">單堂課回顧</span>
            <strong>{html.escape(str(active_row["activity_name"] or active_row["activity_type"] or "活動"))}</strong>
            <p class="note">{html.escape(str(active_row["activity_start_time"]).replace("T", " ")[:16])} · {html.escape(format_number(active_row["distance_km"], 2))} km</p>
          </div>
          <form method="get" class="month-selector-form">
            <input type="hidden" name="page" value="activity">
            <label>
            <span>活動</span>
              <select name="activity" onchange="this.form.submit()">
                {"".join(options)}
              </select>
            </label>
          </form>
        </div>
      </section>
    """


def metric_card(label, value):
    return f"""
      <div class="metric-card">
        <span>{html.escape(label)}</span>
        <strong>{html.escape(str(value))}</strong>
      </div>
    """


def detail_chip(label, value):
    if value_is_blank(value):
        value = "未設定"
    return f"""
      <span class="detail-chip">
        <b>{html.escape(label)}</b>
        {html.escape(str(value))}
      </span>
    """


def intelligence_metric(label, value, delta_value=None):
    delta_html = ""
    if delta_value is not None:
        delta_class = "up" if delta_value > 0 else "down" if delta_value < 0 else "flat"
        delta_html = f'<small class="{delta_class}">{html.escape(format_delta_pct(delta_value))} vs 4W avg</small>'
    return f"""
      <div class="intelligence-metric">
        <span>{html.escape(label)}</span>
        <strong>{html.escape(str(value))}</strong>
        {delta_html}
      </div>
    """


def today_panel(today):
    if not today:
        return ""
    latest = today["latest_activity"]
    latest_summary = (
        f"{format_short_datetime(latest['activity_start_time'])} · "
        f"{format_number(latest['distance_km'], 2)} km · "
        f"負荷 {latest['training_load'] if latest['training_load'] is not None else '-'}"
    )
    return f"""
      <section class="panel-section">
        <h2>今天</h2>
        <div class="today-panel">
          <div class="today-status">
            <span>恢復狀態</span>
            <strong>{html.escape(today["status"])}</strong>
          </div>
          <div class="today-suggestion">
            <span>今日建議</span>
            <strong>{html.escape(today["suggestion"])}</strong>
            <p>{html.escape(today["reason"])}</p>
          </div>
          <div class="today-latest">
            <span>最近一次活動</span>
            <strong>{html.escape(latest_summary)}</strong>
          </div>
        </div>
      </section>
    """


def weekly_intelligence_panel(intelligence):
    if not intelligence:
        return ""
    current = intelligence["current"]
    load_per_km = (
        format_number(intelligence["current_load_per_km"], 1)
        if intelligence["current_load_per_km"] is not None
        else ""
    )
    metrics_html = [
        intelligence_metric(
            "公里",
            f"{format_number(current['total_km'], 2)} km",
            intelligence["km_delta"],
        ),
        intelligence_metric(
            "訓練負荷",
            int(current["training_load"] or 0),
            intelligence["load_delta"],
        ),
        intelligence_metric(
            "每公里負荷",
            load_per_km,
            intelligence["load_per_km_delta"],
        ),
        intelligence_metric(
            "恢復狀態",
            intelligence["recovery_status"],
        ),
    ]
    return f"""
      <section class="panel-section">
        <h2>本週判讀</h2>
        <div class="intelligence-panel">
          <div class="intelligence-grid">
            {"".join(metrics_html)}
          </div>
          <div class="coach-summary">
            <span>教練摘要</span>
            <p>{html.escape(intelligence["coach_summary"])}</p>
          </div>
        </div>
      </section>
    """


def archive_metric_strip(summary):
    return f"""
      <section class="panel-section archive-strip">
        <h2>歷史累積</h2>
        <div class="metric-grid compact-metrics">
          {metric_card("活動數", summary["activities"] or 0)}
          {metric_card("總公里", summary["total_km"] or 0)}
          {metric_card("總時間", format_hours(summary["total_time_sec"]))}
          {metric_card("平均配速", format_pace_seconds(summary["avg_pace_sec_per_km"]))}
          {metric_card("平均心率", summary["avg_hr"] or "")}
        </div>
      </section>
    """


def page_nav(page):
    items = [
        ("activity", "單堂課"),
        ("home", "總覽"),
        ("weekly", "週回顧"),
        ("monthly", "月回顧"),
        ("shoes", "鞋款"),
        ("training", "訓練"),
        ("metadata", "標註"),
    ]
    links = []
    for slug, label in items:
        css_class = "nav-link active" if slug == page else "nav-link"
        href = "/?" + urlencode({"page": slug})
        links.append(f'<a class="{css_class}" href="{html.escape(href, quote=True)}">{html.escape(label)}</a>')
    return f'<nav class="page-nav">{"".join(links)}</nav>'


def monthly_selector_bar(months, selected_month, page_slug="monthly"):
    if not months:
        return ""
    options = []
    for row in months:
        month_key = str(row["month_key"])
        selected = " selected" if month_key == selected_month else ""
        options.append(
            f'<option value="{html.escape(month_key, quote=True)}"{selected}>{html.escape(month_key)}</option>'
        )
    return f"""
      <section class="panel-section">
        <div class="month-selector-bar">
          <div>
            <span class="eyebrow">回顧月份</span>
            <strong>{html.escape(selected_month)}</strong>
          </div>
          <form method="get" class="month-selector-form">
            <input type="hidden" name="page" value="{html.escape(page_slug, quote=True)}">
            <label>
            <span>月份</span>
              <select name="month" onchange="this.form.submit()">
                {"".join(options)}
              </select>
            </label>
          </form>
        </div>
      </section>
    """


def week_label_from_offset(week_offset):
    try:
        offset = int(week_offset)
    except (TypeError, ValueError):
        return "本週"
    if offset == 0:
        return "本週"
    if offset == 1:
        return "上一週"
    if offset == 2:
        return "兩週前"
    if offset == 3:
        return "三週前"
    if offset == 4:
        return "四週前"
    return f"{offset} 週前"


def weekly_selector_bar(weeks, selected_week, page_slug="weekly"):
    if not weeks:
        return ""
    active_row = None
    options = []
    for row in weeks:
        week_key = str(row["week_offset"])
        label = f"{week_label_from_offset(row['week_offset'])}（{row['start_date']} – {row['end_date']}）"
        selected = " selected" if week_key == selected_week else ""
        options.append(
            f'<option value="{html.escape(week_key, quote=True)}"{selected}>{html.escape(label)}</option>'
        )
        if week_key == selected_week:
            active_row = row
    if active_row is None:
        active_row = weeks[0]
    return f"""
      <section class="panel-section">
        <div class="month-selector-bar">
          <div>
            <span class="eyebrow">目前學習視窗（最近 5 週）</span>
            <strong>{html.escape(week_label_from_offset(active_row["week_offset"]))}</strong>
            <p class="note">{html.escape(str(active_row["start_date"]))} – {html.escape(str(active_row["end_date"]))}</p>
          </div>
          <form method="get" class="month-selector-form">
            <input type="hidden" name="page" value="{html.escape(page_slug, quote=True)}">
            <label>
            <span>週次</span>
              <select name="week" onchange="this.form.submit()">
                {"".join(options)}
              </select>
            </label>
          </form>
        </div>
        <p class="note">Weekly 只保留最近 5 週，讓這一頁專注在短期學習。更早以前的資料先留在背景裡，不打斷這一週真正留下來的東西。</p>
      </section>
    """


def recovery_badge(status):
    raw_status = status or ""
    status_class = {
        "Balanced": "balanced",
        "Absorb": "absorb",
        "Watch Load": "watch",
        "Building baseline": "baseline",
    }.get(raw_status, "baseline")
    display_status = {
        "Balanced": "平衡",
        "Absorb": "吸收",
        "Watch Load": "留意負荷",
        "Building baseline": "建立基準中",
    }.get(raw_status, "未知")
    return f'<span class="status-badge {status_class}">{html.escape(display_status)}</span>'


def weekly_history_table(rows, selected_week="0"):
    if not rows:
        return '<p class="note">目前還沒有足夠的週資料。</p>'
    body = []
    for row in rows:
        label = week_label_from_offset(row["week_offset"])
        row_class = "selected-row" if str(row["week_offset"]) == str(selected_week) else ""
        body.append(
            f"""
            <tr class="{row_class}">
              <td>{html.escape(label)}</td>
              <td>{html.escape(str(row["start_date"]))} – {html.escape(str(row["end_date"]))}</td>
              <td>{row["activities"]}</td>
              <td>{format_number(row["total_km"], 2)}</td>
              <td>{html.escape(format_hours(row["total_time_sec"]))}</td>
              <td>{html.escape(format_pace_seconds(row["avg_pace_sec_per_km"]))}</td>
              <td>{'' if row["avg_hr"] is None else row["avg_hr"]}</td>
              <td>{'' if row["training_load"] is None else row["training_load"]}</td>
            </tr>
            """
        )
    return f"""
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>週別</th>
              <th>期間</th>
              <th>活動數</th>
              <th>KM</th>
              <th>時間</th>
              <th>配速</th>
              <th>平均心率</th>
              <th>負荷</th>
            </tr>
          </thead>
          <tbody>{"".join(body)}</tbody>
        </table>
      </div>
    """


def monthly_history_table(rows):
    if not rows:
        return '<p class="note">目前還沒有足夠的月資料。</p>'
    body = []
    for index, row in enumerate(rows):
        label = f"{row['month_key']}（月中）" if index == 0 else row["month_key"]
        load_per_km = None
        if row["total_km"]:
            try:
                load_per_km = float(row["training_load"]) / float(row["total_km"])
            except (TypeError, ValueError, ZeroDivisionError):
                load_per_km = None
        body.append(
            f"""
            <tr>
              <td>{html.escape(label)}</td>
              <td>{html.escape(str(row["month_start"]))} – {html.escape(str(row["month_end"]))}</td>
              <td>{row["activities"]}</td>
              <td>{format_number(row["total_km"], 2)}</td>
              <td>{html.escape(format_hours(row["total_time_sec"]))}</td>
              <td>{html.escape(format_pace_seconds(row["avg_pace_sec_per_km"]))}</td>
              <td>{'' if row["training_load"] is None else format_number(row["training_load"], 1)}</td>
              <td>{'' if load_per_km is None else format_number(load_per_km, 1)}</td>
            </tr>
            """
        )
    return f"""
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>月份</th>
              <th>期間</th>
              <th>活動數</th>
              <th>KM</th>
              <th>時間</th>
              <th>配速</th>
              <th>負荷</th>
              <th>每公里負荷</th>
            </tr>
          </thead>
          <tbody>{"".join(body)}</tbody>
        </table>
      </div>
    """


def training_distribution_panel(rows):
    if not rows:
        return '<p class="note">這週還沒有可用的訓練分布資料。</p>'
    body = []
    for row in rows:
        body.append(
            f"""
            <tr>
              <td>{html.escape(str(row["workout_type_name_en"] or "未標註"))}</td>
              <td>{html.escape(str(row["primary_training_purpose_name_en"] or "未標註"))}</td>
              <td>{row["activity_count"]}</td>
              <td>{format_number(row["total_km"], 2)}</td>
              <td>{'' if row["avg_training_load"] is None else format_number(row["avg_training_load"], 1)}</td>
            </tr>
            """
        )
    return f"""
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>課表類型</th>
              <th>訓練目的</th>
              <th>活動數</th>
              <th>KM</th>
              <th>平均負荷</th>
            </tr>
          </thead>
          <tbody>{"".join(body)}</tbody>
        </table>
      </div>
    """


def progress_bar_row(label, current_value, target_value, suffix="", digits=1):
    current_number = 0.0 if value_is_blank(current_value) else float(current_value)
    target_number = 0.0 if value_is_blank(target_value) else float(target_value)
    ratio = 0 if target_number <= 0 else max(0, min(current_number / target_number, 1.2))
    width_pct = max(4, min(int(round(ratio * 100)), 100)) if current_number > 0 else 0
    current_text = format_number(current_number, digits) if digits else format_number(current_number, 0)
    target_text = format_number(target_number, digits) if digits else format_number(target_number, 0)
    return f"""
      <div class="progress-row">
        <div class="progress-meta">
          <span>{html.escape(label)}</span>
          <strong>{html.escape(f"{current_text} / {target_text} {suffix}".strip())}</strong>
        </div>
        <div class="progress-track">
          <div class="progress-fill" style="width:{width_pct}%"></div>
        </div>
      </div>
    """


def verdict_star_string(level):
    level = max(1, min(int(level), 5))
    return "★" * level + "☆" * (5 - level)


def month_signal_assessment(current_value, target_value):
    if value_is_blank(target_value) or float(target_value) <= 0:
        return ("基準建立中", "baseline", "參考基準仍在建立中。")
    current = 0.0 if value_is_blank(current_value) else float(current_value)
    target = float(target_value)
    ratio = current / target if target else 0
    if ratio >= 1.05:
        return ("超前進度", "balanced", "目前進度比這個時間點的參考節奏更快一些。")
    if ratio >= 0.9:
        return ("穩定累積", "balanced", "目前節奏還在合理範圍內，不需要刻意追趕。")
    if ratio >= 0.75:
        return ("可追回", "watch", "現在稍微慢一點沒關係，只要節奏穩住，這個月還追得回來。")
    return ("值得留意", "watch", "目前進度明顯慢於參考節奏，之後需要更有意識地安排。")


def signal_card(label, status, reason, badge_class):
    return f"""
      <div class="review-card signal-card">
        <span>{html.escape(label)}</span>
        <strong>{html.escape(status)}</strong>
        <p>{html.escape(reason)}</p>
        <div><span class="status-badge {badge_class}">{html.escape(status)}</span></div>
      </div>
    """


def monthly_coach_timeline_panel(monthly, verdict, verdict_reason, coach_memory, recommendation):
    steps = []
    if coach_memory:
        steps.append(
            f"""
            <div class="coach-timeline-step">
              <span>上月 · {html.escape(coach_memory["previous_month_key"])}</span>
              <strong>當時的建議</strong>
              <p>{html.escape(coach_memory["previous_recommendation"])}</p>
              <p class="note">{html.escape(coach_memory["follow_up"])}</p>
            </div>
            """
        )
    steps.append(
        f"""
        <div class="coach-timeline-step active">
          <span>本月 · {html.escape(str(monthly["month_key"]))}</span>
          <strong>{html.escape(verdict)}</strong>
          <p>{html.escape(verdict_reason)}</p>
        </div>
        """
    )
    steps.append(
        f"""
        <div class="coach-timeline-step">
          <span>下月 · 準備</span>
          <strong>接下來怎麼接</strong>
          <p>{html.escape(recommendation)}</p>
        </div>
        """
    )
    return f'<div class="coach-timeline">{"".join(steps)}</div>'


def monthly_letter_payload(monthly, intelligence, verdict, phase, progress_pct):
    month_key = str(monthly["month_key"])
    if intelligence["is_partial_month"]:
        opening = (
            f"{month_key} 目前還在進行中，但整體方向沒有偏掉。"
            " 這不是一個需要焦慮追趕的月份，而是一個先把節奏穩住的月份。"
        )
    elif verdict == "吸收月":
        opening = (
            f"{month_key} 不是一個追求突破的月份，但它很可能是下一次突破真正開始的地方。"
        )
    elif verdict == "負荷建構":
        opening = (
            f"{month_key} 是一個明顯往前推進的月份。你不是只是做更多，而是在學會承受更高的訓練刺激。"
        )
    else:
        opening = (
            f"{month_key} 更像一個穩穩站住腳步的月份。"
            " 沒有耀眼突破，但很多重要的東西都正在慢慢對齊。"
        )

    why = intelligence["coach_summary"]

    if intelligence["is_partial_month"]:
        looking_forward = "下個月，我希望你先把這個月的節奏走完整，再決定要不要把刺激往上拉。"
    elif verdict == "吸收月":
        looking_forward = "下個月，我希望你把吸收下來的能量，慢慢轉回更清楚的品質刺激。"
    elif verdict == "負荷建構":
        looking_forward = "下個月，我希望你不要急著再加，而是先把這個月承受下來的東西真正消化掉。"
    elif phase == "耐力累積":
        looking_forward = "下個月，我希望你在保留長跑的同時，慢慢把速度刺激帶回來。"
    else:
        looking_forward = "下個月，我希望你延續現在這個節奏，讓穩定先站住，再決定下一步要推哪一塊。"

    evidence_intro = (
        f"我會這樣看，不是因為單一一次表現，而是因為這個月累積起來的節奏、負荷與課表選擇都指向同一個方向。"
    )

    return {
        "opening": opening,
        "why": why,
        "looking_forward": looking_forward,
        "evidence_intro": evidence_intro,
        "progress_note": (
            f"目前月份完成度約 {format_number(progress_pct, 0)}%。"
            if progress_pct is not None
            else "目前月份完成度仍在計算中。"
        ),
    }


def distribution_bar_groups(rows):
    if not rows:
        return '<p class="note">本月還沒有可用的訓練分布資料。</p>'
    workouts = {}
    purposes = {}
    for row in rows:
        workout = str(row["workout_type_name_en"] or "未標註")
        purpose = str(row["primary_training_purpose_name_en"] or "未標註")
        workouts[workout] = workouts.get(workout, 0.0) + float(row["total_km"] or 0)
        purposes[purpose] = purposes.get(purpose, 0.0) + float(row["total_km"] or 0)

    def render_group(title, values):
        if not values:
            return ""
        top = sorted(values.items(), key=lambda item: item[1], reverse=True)
        max_value = top[0][1] or 1
        items = []
        for label, value in top[:6]:
            width = int(round((value / max_value) * 100)) if max_value else 0
            items.append(
                f"""
                <div class="bar-item">
                  <div class="bar-label-line">
                    <span>{html.escape(label)}</span>
                    <strong>{html.escape(format_number(value, 2))} km</strong>
                  </div>
                  <div class="bar-track"><div class="bar-fill" style="width:{width}%"></div></div>
                </div>
                """
            )
        return f"""
          <div class="review-card bar-group-card">
            <span>{html.escape(title)}</span>
            <div class="bar-group">
              {"".join(items)}
            </div>
          </div>
        """

    return f"""
      <div class="metric-grid training-kpi-grid">
        {render_group("課表分布", workouts)}
        {render_group("目的分布", purposes)}
      </div>
    """


def monthly_briefing_why_points(monthly, intelligence, progress_row, coach_memory=None):
    points = []
    load_delta = intelligence["load_delta"]
    km_delta = intelligence["km_delta"]

    if intelligence["is_partial_month"]:
        completion = format_number(progress_row["progress_pct"], 0) if progress_row and progress_row["progress_pct"] is not None else "—"
        points.append(f"本月目前完成約 {completion}%，先把這次判讀視為進度檢查，不急著下完整月結論。")
    elif load_delta is not None:
        if load_delta > 15:
            points.append(f"訓練負荷較前 3 個月平均增加 {format_delta_pct(load_delta)}，目前屬於明顯往前推進的建構。")
        elif load_delta < -15:
            points.append(f"訓練負荷較前 3 個月平均下降 {abs(load_delta):.0f}%，更像有意識地吸收與調整。")
        else:
            points.append("訓練負荷大致貼近前 3 個月基準，整體節奏仍維持在可延續範圍內。")

    if km_delta is not None:
        if km_delta > 10:
            points.append(f"里程較基準增加 {format_delta_pct(km_delta)}，目前的增加不只來自單次刺激，而是整體累積。")
        elif km_delta < -10:
            points.append(f"里程較基準下降 {abs(km_delta):.0f}%，但目前判讀更重視這是否屬於刻意收整。")
        else:
            points.append("里程變化不大，代表本月方向主要不是靠單純多跑來改變。")

    quality_sessions = int(progress_row["current_quality_sessions"] or 0) if progress_row else 0
    long_runs = int(progress_row["current_long_runs"] or 0) if progress_row else 0
    if quality_sessions >= 3:
        points.append(f"本月已有 {quality_sessions} 次品質刺激，代表速度工作已經回到訓練結構裡。")
    elif quality_sessions >= 1:
        points.append(f"本月已有 {quality_sessions} 次品質刺激，刺激正在回來，但還沒有壓過整體節奏。")
    elif long_runs >= 2:
        points.append(f"本月保留了 {long_runs} 次長跑，耐力主線仍然連續。")
    elif long_runs == 1:
        points.append("本月至少保留一次長跑，代表耐力主線沒有完全中斷。")

    if coach_memory and coach_memory.get("follow_up"):
        points.append(f"從上月延續來看：{coach_memory['follow_up']}")

    return points[:4]


def _monthly_trend_card(title, question, rows, selected_month, value_key, unit, insight):
    if not rows:
        return ""
    latest = list(rows)
    latest.reverse()
    values = [float(row[value_key] or 0) for row in latest]
    max_value = max(values) if values else 0
    items = []
    for row, value in zip(latest, values):
        width = int(round((value / max_value) * 100)) if max_value else 0
        active_class = " active" if str(row["month_key"]) == selected_month else ""
        if unit == "km":
            value_label = f"{format_number(value, 1)} km"
        else:
            value_label = format_number(value, 0)
        items.append(
            f"""
            <div class="bar-item trend-bar-item{active_class}">
              <div class="bar-label-line">
                <span>{html.escape(str(row["month_key"]))}</span>
                <strong>{html.escape(value_label)}</strong>
              </div>
              <div class="bar-track"><div class="bar-fill" style="width:{width}%"></div></div>
            </div>
            """
        )
    return f"""
      <div class="review-card bar-group-card briefing-chart-card">
        <span>{html.escape(title)}</span>
        <strong>{html.escape(question)}</strong>
        <div class="bar-group">
          {"".join(items)}
        </div>
        <p>{html.escape(insight)}</p>
      </div>
    """


def monthly_driver_card(intelligence, progress_row):
    if not intelligence:
        return ""

    km_delta = intelligence["km_delta"]
    load_delta = intelligence["load_delta"]
    quality_sessions = int(progress_row["current_quality_sessions"] or 0) if progress_row else 0
    long_runs = int(progress_row["current_long_runs"] or 0) if progress_row else 0
    target_quality = float(progress_row["target_quality_to_date"] or 0) if progress_row else 0
    target_long_runs = float(progress_row["target_long_runs_to_date"] or 0) if progress_row else 0

    def level_from_delta(delta, positive_threshold=10, negative_threshold=-10):
        if delta is None:
            return ("neutral", "基準建立中")
        if delta >= positive_threshold:
            return ("up", f"較基準 {format_delta_pct(delta)}")
        if delta <= negative_threshold:
            return ("down", f"較基準 {abs(delta):.0f}%")
        return ("steady", "大致貼近基準")

    def level_from_sessions(current, target):
        if current >= max(3, round(target + 0.5)):
            return ("up", f"{current} 次，刺激已經回來")
        if current >= max(1, round(target)):
            return ("steady", f"{current} 次，維持在節奏裡")
        if current == 0:
            return ("down", "本月還沒有明顯刺激")
        return ("steady", f"{current} 次，正在慢慢回來")

    def level_from_long_runs(current, target):
        if current >= max(2, round(target + 0.5)):
            return ("up", f"{current} 次，耐力主線很清楚")
        if current >= 1:
            return ("steady", f"{current} 次，耐力主線仍在")
        return ("down", "本月長跑主線較弱")

    km_level, km_note = level_from_delta(km_delta)
    quality_level, quality_note = level_from_sessions(quality_sessions, target_quality)
    long_level, long_note = level_from_long_runs(long_runs, target_long_runs)

    def driver_row(label, level, note):
        level_map = {
            "up": ("主要推力", "driver-up"),
            "steady": ("維持節奏", "driver-steady"),
            "down": ("明顯回收", "driver-down"),
            "neutral": ("基準建立中", "driver-neutral"),
        }
        badge_text, badge_class = level_map[level]
        return f"""
        <div class="driver-row">
          <div class="driver-row-top">
            <strong>{html.escape(label)}</strong>
            <span class="driver-badge {badge_class}">{html.escape(badge_text)}</span>
          </div>
          <p>{html.escape(note)}</p>
        </div>
        """

    summary = "這個位置主要是多個節奏一起堆出來的，而不是單一一堂課。"
    if load_delta is not None and load_delta > 15:
        if km_delta is not None and km_delta > 10:
            summary = "這次建構主要來自整體跑量累積，而不是單次品質課暴增。"
        elif quality_sessions >= max(3, round(target_quality + 0.5)):
            summary = "這次建構主要來自品質刺激回來，而不是單純多跑。"
        else:
            summary = "這次建構主要來自整體節奏往前推進，而不是單一指標跳高。"
    elif load_delta is not None and load_delta < -15:
        if long_runs >= 1:
            summary = "這次吸收主要來自整體刺激回收，但長跑主線還在。"
        else:
            summary = "這次回收主要來自整體刺激下降，而不是單一課表失手。"
    elif km_delta is not None and abs(km_delta) <= 10:
        summary = "這個位置不是靠單純多跑形成的，而是靠整體結構慢慢站穩。"

    return f"""
      <div class="review-card driver-card briefing-chart-card">
        <span>這個位置是怎麼形成的？</span>
        <strong>這個位置主要是怎麼形成的？</strong>
        <div class="driver-list">
          {driver_row("跑量累積", km_level, km_note)}
          {driver_row("品質刺激", quality_level, quality_note)}
          {driver_row("長跑主線", long_level, long_note)}
        </div>
        <p>{html.escape(summary)}</p>
        <div class="reasoning-jump-row">
          <a class="inline-jump-link" href="#monthly-weeks">去看關鍵週</a>
        </div>
      </div>
    """


def monthly_load_state_card(rows, selected_month, verdict):
    if not rows:
        return ""

    latest = list(rows)
    latest.reverse()
    states = []
    previous_load = None
    for row in latest:
        month_key = str(row["month_key"])
        load = float(row["training_load"] or 0)
        if previous_load is None or previous_load <= 0:
            state = "起步"
            badge_class = "baseline"
        else:
            delta_pct = ((load - previous_load) / previous_load) * 100
            if delta_pct >= 12:
                state = "建構"
                badge_class = "balanced"
            elif delta_pct <= -12:
                state = "吸收" if month_key == selected_month and verdict == "吸收月" else "回落"
                badge_class = "absorb" if state == "吸收" else "watch"
            else:
                state = "延續"
                badge_class = "baseline"
        previous_load = load
        states.append(
            {
                "month_key": month_key,
                "state": state,
                "badge_class": badge_class,
                "active": month_key == selected_month,
            }
        )

    selected_index = next((index for index, item in enumerate(states) if item["active"]), len(states) - 1)
    has_observed_next = (selected_index + 1) < (len(states) - 1)
    visible_states = states[max(0, selected_index - 3) : selected_index + 1]

    current = next((item for item in visible_states if item["active"]), None)
    current_state = current["state"] if current else "目前"
    insight = "不要先看數字，先看它屬於哪一段。"
    if current_state == "吸收":
        insight = "先確認：這不是失去節奏，而是建構後的吸收。"
    elif current_state == "建構":
        insight = "先確認：這不是硬撐，而是可吸收的建構。"
    elif current_state == "延續":
        insight = "先確認：重點不是拉高，而是把節奏穩穩接住。"
    elif current_state == "回落":
        insight = "先確認：這比較像掉出主線，而不是計畫中的回收。"

    future_label = "下一步"
    future_state = "延續"
    future_class = "baseline"
    if current_state == "吸收":
        future_state = "下一次建構"
        future_class = "balanced"
    elif current_state == "建構":
        future_state = "守住後再加"
        future_class = "baseline"
    elif current_state == "延續":
        future_state = "穩定推進"
        future_class = "balanced"
    elif current_state == "回落":
        future_state = "先找回節奏"
        future_class = "watch"

    items = []
    for index, item in enumerate(visible_states):
        active_class = " active" if item["active"] else ""
        month_label = str(int(str(item["month_key"]).split("-")[1])) + "月"
        connector = '<div class="state-connector"></div>' if index < len(visible_states) - 1 else ""
        items.append(
            f"""
            <div class="state-node-wrap">
              <div class="state-step {item['badge_class']}{active_class}">
                <span class="state-month">{html.escape(month_label)}</span>
                <strong>{html.escape(item["state"])}</strong>
                <div class="state-marker"><span class="state-dot"></span></div>
                <p>{"現在" if item["active"] else "&nbsp;"}</p>
              </div>
              {connector}
            </div>
            """
        )
    if has_observed_next:
        observed_next = states[selected_index + 1]
        next_month_label = str(int(str(observed_next["month_key"]).split("-")[1])) + "月"
        items.append(
            f"""
            <div class="state-node-wrap future-slot">
              <div class="state-connector"></div>
              <div class="state-step {observed_next['badge_class']} future-observed">
                <span class="state-month">{next_month_label}</span>
                <strong>{html.escape(observed_next['state'])}</strong>
                <div class="state-marker"><span class="state-dot"></span></div>
                <p>下一段</p>
              </div>
            </div>
            """
        )
    else:
        items.append(
            f"""
            <div class="state-node-wrap future-slot">
              <div class="state-connector future-connector"></div>
              <div class="state-step {future_class} future">
                <span class="state-month">{future_label}</span>
                <strong>{future_state}</strong>
                <div class="state-marker"><span class="state-dot"></span></div>
                <p>方向已定</p>
              </div>
            </div>
            """
        )

    return f"""
      <div class="review-card briefing-chart-card state-briefing-card">
        <span>先回答一件事</span>
        <strong>這個月是在建構，還是失去節奏？</strong>
        <div class="state-sequence">
          {"".join(items)}
        </div>
        <p>{html.escape(insight)}</p>
        <div class="reasoning-jump-row">
          <a class="inline-jump-link" href="#monthly-weeks">再看這個月是由哪幾週撐起來的</a>
        </div>
      </div>
    """


def monthly_structure_card(distribution_rows):
    if not distribution_rows:
        return """
          <div class="review-card bar-group-card briefing-chart-card">
            <span>本月訓練結構</span>
            <strong>本月是由哪些訓練組成的？</strong>
            <p>目前還沒有足夠的訓練分布資料可以建立這張圖。</p>
          </div>
        """

    purposes = {}
    for row in distribution_rows:
        purpose = str(row["primary_training_purpose_name_en"] or "Unassigned")
        purposes[purpose] = purposes.get(purpose, 0.0) + float(row["total_km"] or 0)

    top = sorted(purposes.items(), key=lambda item: item[1], reverse=True)[:5]
    max_value = top[0][1] if top else 0
    purpose_label_map = {
        "Aerobic Base": "有氧基礎",
        "Endurance": "耐力",
        "Recovery": "恢復",
        "Race Specific": "比賽專項",
        "Threshold": "門檻",
        "Unassigned": "未標註",
    }
    items = []
    for label, value in top:
        width = int(round((value / max_value) * 100)) if max_value else 0
        items.append(
            f"""
            <div class="bar-item">
              <div class="bar-label-line">
                <span>{html.escape(purpose_label_map.get(label, label))}</span>
                <strong>{html.escape(format_number(value, 1))} km</strong>
              </div>
              <div class="bar-track"><div class="bar-fill" style="width:{width}%"></div></div>
            </div>
            """
        )

    top_label = purpose_label_map.get(top[0][0], top[0][0]) if top else "訓練"
    insight = f"本月仍以{top_label}為主體，這張圖用來確認品質刺激、長跑與恢復是否壓過了整體節奏。"
    return f"""
      <div class="review-card bar-group-card briefing-chart-card">
        <span>本月訓練結構</span>
        <strong>本月是由哪些訓練組成的？</strong>
        <div class="bar-group">
          {"".join(items)}
        </div>
        <p>{html.escape(insight)}</p>
        <div class="reasoning-jump-row">
          <a class="inline-jump-link" href="#monthly-key-activities">再看關鍵課</a>
        </div>
      </div>
    """


def monthly_related_weeks_table(rows):
    if not rows:
        return '<p class="note">這個月目前還沒有足夠的週資料可以串起來。</p>'
    body = []
    for row in rows:
        href = "/?" + urlencode({"page": "weekly", "week": row["week_offset"]})
        body.append(
            f"""
            <tr>
              <td>{html.escape(week_label_from_offset(row["week_offset"]))}</td>
              <td>{html.escape(str(row["start_date"]))} – {html.escape(str(row["end_date"]))}</td>
              <td>{html.escape(str(row["verdict"]))}</td>
              <td>{format_number(row["total_km"], 1)}</td>
              <td>{format_number(row["training_load"], 0)}</td>
              <td>{html.escape(str(row["note"]))}</td>
              <td><a class="inline-jump-link" href="{html.escape(href, quote=True)}">看這一週</a></td>
            </tr>
            """
        )
    return f"""
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>週次</th>
              <th>日期</th>
              <th>本週判讀</th>
              <th>KM</th>
              <th>負荷</th>
              <th>這週留下了什麼</th>
              <th>往下看</th>
            </tr>
          </thead>
          <tbody>{"".join(body)}</tbody>
        </table>
      </div>
    """


def weekly_distribution_snapshot(distribution_rows):
    purpose_totals = {}
    quality_sessions = 0
    long_run_sessions = 0
    for row in distribution_rows or []:
        purpose = str(row["primary_training_purpose_name_en"] or "Unassigned")
        workout = str(row["workout_type_name_en"] or "Unassigned")
        purpose_totals[purpose] = purpose_totals.get(purpose, 0.0) + float(row["total_km"] or 0)
        if workout.lower() in {"tempo run", "interval", "progression run"} or purpose in {"Threshold", "Race Specific"}:
            quality_sessions += int(row["activity_count"] or 0)
        if workout.lower() in {"lsd", "long run"} or purpose == "Endurance":
            long_run_sessions += int(row["activity_count"] or 0)
    top_purpose = None
    if purpose_totals:
        top_purpose = max(purpose_totals.items(), key=lambda item: item[1])[0]
    return {
        "purpose_totals": purpose_totals,
        "quality_sessions": quality_sessions,
        "long_run_sessions": long_run_sessions,
        "top_purpose": top_purpose,
    }


def weekly_learning_driver_card(intelligence, distribution_rows):
    if not intelligence:
        return ""

    load_delta = intelligence["load_delta"]
    km_delta = intelligence["km_delta"]
    snapshot = weekly_distribution_snapshot(distribution_rows)
    quality_sessions = snapshot["quality_sessions"]
    long_run_sessions = snapshot["long_run_sessions"]

    def delta_level(delta, positive_threshold=12, negative_threshold=-12):
        if delta is None:
            return ("neutral", "基準建立中")
        if delta >= positive_threshold:
            return ("up", f"較基準 {format_delta_pct(delta)}")
        if delta <= negative_threshold:
            return ("down", f"較基準 {abs(delta):.0f}%")
        return ("steady", "大致貼近基準")

    def stimulus_level(quality_count, long_run_count):
        if quality_count >= 2:
            return ("up", f"{quality_count} 次品質刺激，刺激真的有回來")
        if quality_count == 1 and long_run_count >= 1:
            return ("steady", "品質刺激與耐力主線都有留下")
        if quality_count == 1:
            return ("steady", "有 1 次清楚刺激，但沒有壓過整體節奏")
        if long_run_count >= 1:
            return ("steady", "刺激不高，但耐力主線仍然有留下")
        return ("down", "這週沒有明顯刺激，重點更像在守住節奏")

    load_level, load_note = delta_level(load_delta)
    km_level, km_note = delta_level(km_delta, positive_threshold=10, negative_threshold=-10)
    stimulus_level_value, stimulus_note = stimulus_level(quality_sessions, long_run_sessions)

    def driver_row(label, level, note):
        level_map = {
            "up": ("主要推力", "driver-up"),
            "steady": ("維持節奏", "driver-steady"),
            "down": ("明顯回收", "driver-down"),
            "neutral": ("基準建立中", "driver-neutral"),
        }
        badge_text, badge_class = level_map[level]
        return f"""
        <div class="driver-row">
          <div class="driver-row-top">
            <strong>{html.escape(label)}</strong>
            <span class="driver-badge {badge_class}">{html.escape(badge_text)}</span>
          </div>
          <p>{html.escape(note)}</p>
        </div>
        """

    if load_delta is not None and load_delta > 15:
        summary = "真正推動這個學習的，是整週刺激一起往上。"
    elif load_delta is not None and load_delta < -15:
        summary = "真正推動這個學習的，是你把刺激收回來。"
    else:
        summary = "真正推動這個學習的，是整週節奏。"

    return f"""
      <div class="review-card driver-card briefing-chart-card">
        <span>先追問一件事</span>
        <strong>什麼真正讓你學會了這件事？</strong>
        <div class="driver-list">
          {driver_row("負荷節奏", load_level, load_note)}
          {driver_row("跑量節奏", km_level, km_note)}
          {driver_row("刺激安排", stimulus_level_value, stimulus_note)}
        </div>
        <p>{html.escape(summary)}</p>
        <div class="reasoning-jump-row">
          <a class="inline-jump-link" href="#weekly-key-activities">去看關鍵課</a>
        </div>
      </div>
    """


def weekly_structure_card(distribution_rows):
    if not distribution_rows:
        return """
          <div class="review-card bar-group-card briefing-chart-card">
            <span>這週訓練結構</span>
            <strong>這週主要把時間花在哪裡？</strong>
            <p>目前還沒有足夠的訓練分布資料可以建立這張圖。</p>
          </div>
        """

    purpose_totals = {}
    label_map = {
        "Aerobic Base": "有氧基礎",
        "Endurance": "耐力",
        "Recovery": "恢復",
        "Race Specific": "比賽專項",
        "Threshold": "門檻",
        "Unassigned": "未標註",
    }
    for row in distribution_rows:
        purpose = str(row["primary_training_purpose_name_en"] or "Unassigned")
        purpose_totals[purpose] = purpose_totals.get(purpose, 0.0) + float(row["total_km"] or 0)

    top = sorted(purpose_totals.items(), key=lambda item: item[1], reverse=True)[:5]
    max_value = top[0][1] if top else 0
    items = []
    for label, value in top:
        width = int(round((value / max_value) * 100)) if max_value else 0
        items.append(
            f"""
            <div class="bar-item">
              <div class="bar-label-line">
                <span>{html.escape(label_map.get(label, label))}</span>
                <strong>{html.escape(format_number(value, 1))} km</strong>
              </div>
              <div class="bar-track"><div class="bar-fill" style="width:{width}%"></div></div>
            </div>
            """
        )

    top_label = label_map.get(top[0][0], top[0][0]) if top else "訓練"
    insight = f"這週仍以{top_label}為主，學習主要也是從這裡長出來的。"

    return f"""
      <div class="review-card bar-group-card briefing-chart-card">
        <span>這週訓練結構</span>
        <strong>這週主要把時間花在哪裡？</strong>
        <div class="bar-group">
          {"".join(items)}
        </div>
        <p>{html.escape(insight)}</p>
        <div class="reasoning-jump-row">
          <a class="inline-jump-link" href="#weekly-key-activities">再看是哪幾堂課留下來的</a>
        </div>
      </div>
    """


def monthly_key_sessions_table(rows):
    if not rows:
        return '<p class="note">本月還沒有代表課資料。</p>'
    body = []
    session_label_map = {
        "Longest Run": "最長一課",
        "Highest Load": "最高負荷",
        "Fastest Quality": "最快品質課",
        "Lowest HR Easy": "最低心率輕鬆跑",
    }
    seen = set()
    for row in rows:
        key = row["key_session_type"]
        if key in seen:
            continue
        seen.add(key)
        activity_name = row["activity_name"] or row["activity_type"] or "活動"
        body.append(
            f"""
            <tr>
              <td>{html.escape(session_label_map.get(str(row["key_session_type"]), str(row["key_session_type"])))}</td>
              <td>{html.escape(str(activity_name))}</td>
              <td>{html.escape(format_short_datetime(row["activity_start_time"]))}</td>
              <td>{html.escape(str(row["workout_type_name_en"] or ""))}</td>
              <td>{format_number(row["distance_km"], 2)}</td>
              <td>{html.escape(format_pace_seconds(row["avg_pace_sec_per_km"]))}</td>
              <td>{'' if row["avg_hr"] is None else int(round(row["avg_hr"]))}</td>
              <td>{'' if row["training_load"] is None else format_number(row["training_load"], 1)}</td>
              <td>{html.escape(str(row["shoe_display_name"] or ""))}</td>
              <td>{f'<a class="inline-jump-link" href="/?page=activity&activity_id={int(row["activity_id"])}">看這堂課</a>' if row["activity_id"] else ''}</td>
            </tr>
            """
        )
    return f"""
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>判斷依據</th>
              <th>活動</th>
              <th>開始時間</th>
              <th>課表</th>
              <th>KM</th>
              <th>配速</th>
              <th>HR</th>
              <th>負荷</th>
              <th>鞋款</th>
              <th>往下看</th>
            </tr>
          </thead>
          <tbody>{"".join(body)}</tbody>
        </table>
      </div>
    """


def activity_key_segments(split_rows):
    if not split_rows:
        return []
    rows = []
    first = split_rows[0]
    last = split_rows[-1]
    rows.append({
        "anchor": "fragment-start",
        "label": "起跑節奏",
        "section": f"KM {first['split_index']}",
        "metric": f"配速 {format_pace_seconds(first['elapsed_pace_sec_per_km']) or '—'} · HR {'' if first['avg_hr'] is None else int(round(first['avg_hr']))}",
        "note": "先看這堂課一開始是怎麼進入今天的節奏。",
        "split_anchor": f"split-{first['split_index']}",
    })
    if len(split_rows) >= 3:
        middle = split_rows[len(split_rows) // 2]
        rows.append({
            "anchor": "fragment-middle",
            "label": "中段反應",
            "section": f"KM {middle['split_index']}",
            "metric": f"配速 {format_pace_seconds(middle['elapsed_pace_sec_per_km']) or '—'} · HR {'' if middle['avg_hr'] is None else int(round(middle['avg_hr']))}",
            "note": "中段通常最能看出刺激有沒有真正成立。",
            "split_anchor": f"split-{middle['split_index']}",
        })
    rows.append({
        "anchor": "fragment-finish",
        "label": "收尾狀態",
        "section": f"KM {last['split_index']}",
        "metric": f"配速 {format_pace_seconds(last['elapsed_pace_sec_per_km']) or '—'} · HR {'' if last['avg_hr'] is None else int(round(last['avg_hr']))}",
        "note": "最後一段最能看出今天留下來的是節奏、耐力，還是單純把課表做完。",
        "split_anchor": f"split-{last['split_index']}",
    })
    return rows


def activity_fragment_table(activity, split_rows):
    rows = activity_key_segments(split_rows)
    if not rows:
        return '<p class="note">目前還沒有足夠的 split 可以建立關鍵片段。</p>'

    body = []
    for row in rows:
        body.append(
            f"""
            <tr id="{html.escape(row['anchor'], quote=True)}">
              <td>{html.escape(row['label'])}</td>
              <td>{html.escape(row['section'])}</td>
              <td>{html.escape(row['metric'])}</td>
              <td>{html.escape(row['note'])}</td>
              <td><a class="inline-jump-link" href="#{html.escape(row['split_anchor'], quote=True)}">看這段證據</a></td>
            </tr>
            """
        )
    return f"""
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>教練看了什麼</th>
              <th>片段</th>
              <th>數據</th>
              <th>為什麼重要</th>
              <th>往下看</th>
            </tr>
          </thead>
          <tbody>{"".join(body)}</tbody>
        </table>
      </div>
    """


def activity_driver_card(title, value, note, fragment_anchor=None, evidence_anchor=None, segment_label=None):
    footer = ""
    if fragment_anchor or evidence_anchor:
        links = []
        if fragment_anchor:
            links.append(f'<a class="inline-jump-link" href="{html.escape(fragment_anchor, quote=True)}">先看{html.escape(segment_label or "關鍵片段")}</a>')
        if evidence_anchor:
            links.append(f'<a class="inline-jump-link" href="{html.escape(evidence_anchor, quote=True)}">再看證據</a>')
        footer = f'<div class="reasoning-jump-row">{"".join(links)}</div>'
    return f"""
      <div class="review-card briefing-chart-card">
        <span>{html.escape(title)}</span>
        <strong>{html.escape(value)}</strong>
        <p>{html.escape(note)}</p>
        {footer}
      </div>
    """


def activity_facts_panel(activity):
    if not activity:
        return ""
    chips = [
        detail_chip("開始時間", str(activity["activity_start_time"]).replace("T", " ")[:16]),
        detail_chip("距離", f"{format_number(activity['distance_km'], 2)} km"),
        detail_chip("時間", format_hours(activity["duration_sec"])),
        detail_chip("平均配速", format_pace_seconds(activity["avg_pace_sec_per_km"])),
        detail_chip("平均 HR", "" if activity["avg_hr"] is None else int(round(activity["avg_hr"]))),
        detail_chip("負荷", "" if activity["training_load"] is None else format_number(activity["training_load"], 0)),
        detail_chip("課表", activity["workout_type_name_en"] or activity["activity_type"] or "未標註"),
        detail_chip("鞋款", activity["shoe_display_name"] or "未標註"),
    ]
    if activity["primary_training_purpose_name_en"]:
        chips.append(detail_chip("主要目的", activity["primary_training_purpose_name_en"]))
    if activity["temperature_c"] is not None:
        chips.append(detail_chip("氣溫", f"{format_number(activity['temperature_c'], 0)}°C"))
    if activity["humidity_pct"] is not None:
        chips.append(detail_chip("濕度", f"{format_number(activity['humidity_pct'], 0)}%"))
    if activity["weather_description"]:
        chips.append(detail_chip("天氣", activity["weather_description"]))
    if activity["garmin_feeling"]:
        chips.append(detail_chip("Garmin Feeling", activity["garmin_feeling"]))
    if activity["garmin_perceived_effort"]:
        chips.append(detail_chip("Garmin RPE", activity["garmin_perceived_effort"]))

    return f"""
      <section class="panel-section">
        <h2>活動資訊</h2>
        <p class="note">如果你想自己往下核對，這堂課的基本事實都在這裡。</p>
        <div class="review-card metric-collection">
          <div class="detail-chips">
            {"".join(chips)}
          </div>
        </div>
      </section>
    """


def activity_split_table(split_rows):
    if not split_rows:
        return '<p class="note">目前還沒有每公里 split 可以往下看。</p>'
    body = []
    for row in split_rows:
        cadence = "" if row["avg_cadence_spm"] is None else format_number(row["avg_cadence_spm"], 1)
        body.append(
            f"""
            <tr id="split-{row["split_index"]}">
              <td>{row["split_index"]}</td>
              <td>{format_number((row["split_distance_m"] or 0) / 1000, 2)}</td>
              <td>{html.escape(format_pace_seconds(row["elapsed_pace_sec_per_km"]))}</td>
              <td>{'' if row["avg_hr"] is None else int(round(row["avg_hr"]))}</td>
              <td>{'' if row["avg_power_w"] is None else int(round(row["avg_power_w"]))}</td>
              <td>{html.escape(cadence)}</td>
            </tr>
            """
        )
    return f"""
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>KM</th>
              <th>距離</th>
              <th>配速</th>
              <th>HR</th>
              <th>功率</th>
              <th>步頻</th>
            </tr>
          </thead>
          <tbody>{"".join(body)}</tbody>
        </table>
      </div>
    """


def activity_review_panel(activity, split_rows, activity_rows, selected_activity_id, weekly_review=None, monthly_overview=None):
    if not activity:
        return """
        <section class="panel-section">
          <h2>單堂課回顧</h2>
          <p class="note">目前還沒有活動可以建立回顧。</p>
        </section>
        """

    review = activity_review_payload(activity, split_rows)
    workout_name = str(activity["workout_type_name_en"] or activity["activity_type"] or "活動")
    start_time = str(activity["activity_start_time"]).replace("T", " ")[:16]
    side_cards = []
    if weekly_review:
        side_cards.append(
            f"""
            <div class="review-card">
              <span>接到這週</span>
              <strong>本週學到了什麼</strong>
              <p>{html.escape(weekly_review["focus"])}</p>
              <a class="desk-link" href="/?page=weekly">看看這週因此學到了什麼</a>
            </div>
            """
        )
    if monthly_overview:
        side_cards.append(
            f"""
            <div class="review-card">
              <span>接到這個月</span>
              <strong>{html.escape(monthly_overview["verdict"])}</strong>
              <p>{html.escape(monthly_overview["verdict_reason"])}</p>
              <a class="desk-link" href="/?page=monthly">看看這個月因此走到哪裡</a>
            </div>
            """
        )

    return f"""
      {activity_selector_bar(activity_rows, selected_activity_id)}
      <section class="panel-section">
        <h2>單堂課教練回顧</h2>
        <div class="weekly-review-grid">
          <div class="weekly-review-main">
            <div class="review-header">
              <div>
                <span class="eyebrow">{html.escape(start_time)}</span>
                <strong>{html.escape(str(activity["activity_name"] or activity["activity_type"] or "活動"))}</strong>
                <p class="note">{html.escape(workout_name)} · {html.escape(format_number(activity["distance_km"], 2))} km · 負荷 {html.escape(format_number(activity["training_load"], 0))}</p>
              </div>
              <span class="status-badge balanced">{html.escape(workout_name)}</span>
            </div>
            <div class="coach-summary review-summary" id="activity-learning">
              <span>先回答一件事</span>
              <strong>{html.escape(review["learning_question"])}</strong>
              <p>{html.escape(review["learning"])}</p>
              <div class="reasoning-jump-row">
                {"".join(f'<a class="inline-jump-link" href="{html.escape(href, quote=True)}">{html.escape(label)}</a>' for label, href in review["reasoning_steps"])}
              </div>
            </div>
            <div class="coach-summary review-summary">
              <span>這堂課真正留下來的</span>
              <p>{html.escape(review["focus"])}</p>
            </div>
            <div class="coach-summary review-summary">
              <span>教練判讀</span>
              <p>{html.escape(review["why"])}</p>
            </div>
            <div class="coach-summary review-summary">
              <span>下一堂課，只記住一件事</span>
              <p>{html.escape(review["looking_forward"])}</p>
            </div>
          </div>
          <div class="weekly-review-side">
            <div class="review-card">
              <span>本堂摘要</span>
              <strong>{html.escape(format_number(activity["distance_km"], 1))} km</strong>
              <p>平均配速 {html.escape(format_pace_seconds(activity["avg_pace_sec_per_km"]))} · 平均 HR {html.escape("" if activity["avg_hr"] is None else str(int(round(activity["avg_hr"]))))}</p>
              <p class="note">這裡只保留最短摘要；真正的理解放在下方教練推理裡。</p>
            </div>
            {"".join(side_cards)}
          </div>
        </div>
      </section>
      <section class="panel-section" id="activity-cause">
        <h2>什麼真正讓你學會了這件事？</h2>
        <p class="note">{html.escape(review["evidence_intro"])}</p>
        <div class="metric-grid training-kpi-grid briefing-evidence-grid">
          {"".join(activity_driver_card(card["title"], card["value"], card["note"], card.get("fragment_anchor"), card.get("evidence_anchor"), card.get("segment_label")) for card in review["cards"])}
        </div>
      </section>
      <section class="panel-section" id="activity-segments">
        <h2>教練看了哪些關鍵片段</h2>
        <p class="note">先看教練停在哪幾段，再一路往下核對那一段的實際 split。</p>
        {activity_fragment_table(activity, split_rows)}
      </section>
      {activity_facts_panel(activity)}
      <section class="panel-section" id="activity-evidence">
        <h2>完整 split</h2>
        <p class="note">如果你想自己驗證教練剛剛為什麼這樣看，完整每公里資料放在這裡。</p>
        {activity_split_table(split_rows)}
      </section>
    """


def journey_timeline_panel(rows, selected_month):
    if not rows:
        return '<p class="note">目前還沒有足夠的月份資料可以建立旅程。</p>'
    cards = []
    for row in rows:
        active_class = " active" if str(row["month_key"]) == selected_month else ""
        cards.append(
            f"""
            <div class="journey-step{active_class}">
              <span>{html.escape(str(row["month_key"]))}</span>
              <strong>{html.escape(str(row["chapter_label"] or "旅程中"))}</strong>
              <p>{format_number(row["total_km"], 1)} km · 負荷 {format_number(row["training_load"], 0)}</p>
            </div>
            """
        )
    return f'<div class="journey-timeline">{"".join(cards)}</div>'


def journey_turning_points_panel(rows):
    if not rows:
        return '<p class="note">目前還沒有足夠的轉折點資料。</p>'
    items = []
    for row in rows:
        items.append(
            f"""
            <div class="journey-turning-point">
              <span>{html.escape(str(row["month_key"]))}</span>
              <strong>{html.escape(str(row["milestone_title"]))}</strong>
              <p>{html.escape(str(row["milestone_note"]))}</p>
            </div>
            """
        )
    return f'<div class="journey-turning-points">{"".join(items)}</div>'


def journey_reflection_payload(story):
    chapter_code = str(story["chapter_code"] or "")
    is_partial = bool(story["is_partial_month"])

    if is_partial and chapter_code == "balanced_build":
        return {
            "emotion": "這一章不像衝刺，更像開始學會拿捏訓練與恢復之間的距離。",
            "reflection": "這一章最大的價值，不是衝得更快，而是開始知道什麼時候該快、什麼時候該慢。",
            "quote": "平衡不是放慢，而是知道何時加速、何時保留。",
            "memory": "如果一年後回頭看，這一章值得記住的，會是你開始學會用更成熟的節奏安排自己。",
            "abilities": ["節奏感", "恢復意識", "長跑穩定度"],
        }
    if chapter_code == "absorb":
        return {
            "emotion": "這一章看起來比較安靜，但真正沉澱下來的，往往正是之後能不能再往前推的關鍵。",
            "reflection": "這一章最大的收穫，不是跑得更多，而是開始理解恢復也是訓練的一部分。",
            "quote": "恢復不是停下來，而是為了走得更遠。",
            "memory": "如果一年後回頭看，這一章值得記住的，會是你第一次真正把恢復當成訓練的一部分。",
            "abilities": ["恢復意識", "耐心", "訓練吸收能力"],
        }
    if chapter_code == "load_build":
        return {
            "emotion": "這一章會讓人感覺壓力變重，但同時也代表你已經開始有能力承受更大的刺激。",
            "reflection": "這一章代表你正在學會承受更大的刺激，同時也更需要保護恢復品質。",
            "quote": "真正的建構，不只是加量，而是學會承擔更高的訓練壓力。",
            "memory": "如果一年後回頭看，這一章值得記住的，會是你開始相信自己可以承受更大的訓練量。",
            "abilities": ["訓練承載力", "壓力管理", "自我節奏"],
        }
    if chapter_code == "endurance_build":
        return {
            "emotion": "這一章不像突破，更像把耐心一點一點磨出來，直到長距離開始變成你的能力。",
            "reflection": "這一章的改變，在於長距離不再只是完成，而開始變成一種穩定能力。",
            "quote": "長距離的成長，常常先發生在心裡，再發生在腿上。",
            "memory": "如果一年後回頭看，這一章值得記住的，會是你第一次覺得長距離不再只是硬撐。",
            "abilities": ["長距離耐心", "耐力穩定度", "補給節奏"],
        }
    if chapter_code == "steady_build":
        return {
            "emotion": "這一章沒有特別戲劇化，但很多真正可靠的改變，往往都從這種平凡的累積開始。",
            "reflection": "這一章比較像靜靜地把地基鋪厚，讓之後的刺激真正有地方落下來。",
            "quote": "穩定累積看起來平凡，卻常常是成長最可靠的來源。",
            "memory": "如果一年後回頭看，這一章值得記住的，會是你願意一再回到那些看似普通、卻最重要的日常。",
            "abilities": ["一致性", "基礎有氧", "日常紀律"],
        }
    return {
        "emotion": "這一章比較像起點，很多東西還不明顯，但改變其實已經悄悄開始。",
        "reflection": "這一章代表基礎正在形成。你不一定已經變快，但你已經開始變得更像一位跑者。",
        "quote": "每一次願意出門跑步，都是在替未來的自己打底。",
        "memory": "如果一年後回頭看，這一章值得記住的，會是你從這裡開始，把跑步變成生活的一部分。",
        "abilities": ["習慣建立", "信心", "基礎體能"],
    }


def journey_key_session_cards(rows):
    if not rows:
        return '<p class="note">本章目前還沒有足夠的代表課資料。</p>'
    session_label_map = {
        "Longest Run": ("最長一課", "這不是單純的距離最長，而是你願意把耐心帶進訓練的一次證明。"),
        "Highest Load": ("最高負荷", "這堂課像是本章最重的一筆，提醒你曾經承受過比以前更多的刺激。"),
        "Fastest Quality": ("最快品質課", "這堂課代表速度不再只是衝出來，而開始被你穩穩地掌握。"),
        "Lowest HR Easy": ("最低心率輕鬆跑", "這堂課常常是最安靜的進步，代表恢復效率與有氧穩定度正在變好。"),
    }
    cards = []
    seen = set()
    for row in rows:
        key = str(row["key_session_type"])
        if key in seen:
            continue
        seen.add(key)
        title, meaning = session_label_map.get(key, (key, "這堂課是本章的重要片段。"))
        activity_name = row["activity_name"] or row["activity_type"] or "活動"
        meta_bits = [
            format_short_datetime(row["activity_start_time"]),
            f"{format_number(row['distance_km'], 2)} km",
        ]
        if row["workout_type_name_en"]:
            meta_bits.append(str(row["workout_type_name_en"]))
        cards.append(
            f"""
            <div class="journey-session-card">
              <span>{html.escape(title)}</span>
              <strong>{html.escape(str(activity_name))}</strong>
              <p>{html.escape(" · ".join(bit for bit in meta_bits if bit))}</p>
              <div class="detail-chips journey-session-chips">
                {detail_chip("配速", format_pace_seconds(row["avg_pace_sec_per_km"]))}
                {detail_chip("心率", "" if row["avg_hr"] is None else f"{int(round(row['avg_hr']))} bpm")}
                {detail_chip("負荷", "" if row["training_load"] is None else format_number(row["training_load"], 1))}
              </div>
              <p class="journey-session-meaning">{html.escape(meaning)}</p>
            </div>
            """
        )
    return f'<div class="journey-session-grid">{"".join(cards)}</div>'


def journey_page_panel(story, timeline_rows, turning_point_rows, available_month_rows, selected_month, coach_memory=None, key_session_rows=None):
    if not story:
        return """
        <section class="panel-section">
          <h2>旅程</h2>
          <p class="note">目前還沒有足夠的月份資料可以建立旅程。</p>
        </section>
        """

    position_note = (
        "這個月仍在進行中，先把它當成目前章節的進度點。"
        if story["is_partial_month"]
        else "這個月已完整收束，可以把它視為旅程中一個已完成的章節。"
    )
    tagged_text = (
        f"{format_number(story['fully_tagged_pct'], 0)}%"
        if story["fully_tagged_pct"] is not None
        else "—"
    )
    latest_turning_point = turning_point_rows[0] if turning_point_rows else None
    reflection = journey_reflection_payload(story)
    chapter_title = f"{story['month_key']} · {story['chapter_label']}"

    return f"""
      {monthly_selector_bar(available_month_rows, selected_month, page_slug="journey")}
      <section class="panel-section">
        <h2>旅程</h2>
        <div class="weekly-review-grid">
          <div class="weekly-review-main">
            <div class="review-header">
              <div>
                <span class="eyebrow">{html.escape(str(story["month_key"]))}</span>
                <strong>{html.escape(str(chapter_title))}</strong>
                <p class="note">{html.escape(str(story["coach_verdict"]))} · {html.escape(position_note)}</p>
              </div>
              <span class="status-badge {"baseline" if story["is_partial_month"] else "balanced"}">{html.escape(str(story["chapter_label"]))}</span>
            </div>
            <div class="review-card">
              <span>你現在在哪一章</span>
              <strong>{html.escape(str(story["chapter_label"]))}</strong>
              <p>{html.escape(str(story["coach_note"]))}</p>
            </div>
            {"<div class=\"coach-summary review-summary\"><span>教練延續</span><p>上個月（" + html.escape(coach_memory["previous_month_key"]) + "）建議：" + html.escape(coach_memory["previous_recommendation"]) + "</p><p class=\"note\">" + html.escape(coach_memory["follow_up"]) + "</p></div>" if coach_memory else ""}
            <div class="coach-summary review-summary">
              <span>這一章的感受</span>
              <p>{html.escape(reflection["emotion"])}</p>
            </div>
            <div class="coach-summary review-summary">
              <span>章節反思</span>
              <p>{html.escape(reflection["reflection"])}</p>
              <p class="note">{html.escape(reflection["quote"])}</p>
            </div>
            <div class="coach-summary review-summary">
              <span>留給未來的自己</span>
              <p>{html.escape(reflection["memory"])}</p>
            </div>
            <div class="coach-summary review-summary">
              <span>下一章</span>
              <p>{html.escape(str(story["next_chapter_note"]))}</p>
            </div>
          </div>
          <div class="weekly-review-side">
            <div class="metric-grid training-kpi-grid">
              {training_metric_card("本月章節", story["chapter_label"], "這個月在旅程中的位置")}
              {training_metric_card("下一章", story["next_chapter_label"], "下一步的方向")}
              {training_metric_card("月里程", f"{format_number(story['total_km'], 1)} km", "本章累積")}
              {training_metric_card("標註完整度", tagged_text, "旅程可解讀程度")}
            </div>
            <div class="review-card">
              <span>成長轉折</span>
              <strong>{html.escape(str(latest_turning_point["milestone_title"])) if latest_turning_point else "旅程持續中"}</strong>
              <p>{html.escape(str(latest_turning_point["milestone_note"])) if latest_turning_point else "還在累積更多里程碑。"}</p>
            </div>
            <div class="review-card">
              <span>這一章正在建立</span>
              <div class="detail-chips journey-ability-chips">
                {"".join(detail_chip("能力", ability) for ability in reflection["abilities"])}
              </div>
              <p>Journey 記住的不是單一數字，而是你正在長出來的能力。</p>
            </div>
          </div>
        </div>
      </section>
      <section class="panel-section">
        <h2>旅程章節</h2>
        {journey_timeline_panel(timeline_rows, selected_month)}
      </section>
      <section class="panel-section">
        <h2>旅程轉折</h2>
        {journey_turning_points_panel(turning_point_rows)}
      </section>
      <section class="panel-section">
        <h2>本章故事片段</h2>
        {journey_key_session_cards(key_session_rows or [])}
      </section>
    """


def monthly_review_panel(monthly, intelligence, progress_row, assignment_quality_row, history_rows, distribution_rows, key_session_rows, related_week_rows, available_month_rows, selected_month, coach_memory=None):
    if not monthly or not intelligence:
        return """
        <section class="panel-section">
          <h2>月回顧</h2>
          <p class="note">目前還沒有足夠的月資料可以建立回顧。</p>
        </section>
        """

    progress_pct = progress_row["progress_pct"] if progress_row else None

    quality_sessions = int(progress_row["current_quality_sessions"] or 0) if progress_row else 0
    long_runs = int(progress_row["current_long_runs"] or 0) if progress_row else 0

    if quality_sessions >= 3:
        phase = "品質建構"
    elif long_runs >= 2:
        phase = "耐力累積"
    elif quality_sessions >= 1:
        phase = "平衡建構"
    else:
        phase = "基礎累積"

    tagged_pct = assignment_quality_row["fully_tagged_pct"] if assignment_quality_row else None
    baseline_available = intelligence["baseline_km"] is not None and intelligence["baseline_load"] is not None

    if intelligence["is_partial_month"] and (tagged_pct is None or tagged_pct < 70):
        confidence = "中"
    elif intelligence["is_partial_month"]:
        confidence = "中"
    elif not baseline_available or tagged_pct is None or tagged_pct < 70:
        confidence = "中"
    else:
        confidence = "高"

    confidence_reason = (
        f"月份完成度 {format_number(progress_pct, 0) if progress_pct is not None else '—'}% · "
        f"已標註活動 {format_number(tagged_pct, 0) if tagged_pct is not None else '—'}% · "
        f"基準 {'可用' if baseline_available else '建立中'}"
    )

    _, recommendation = monthly_recommendation_plan(intelligence)

    if intelligence["is_partial_month"]:
        verdict = "正常"
        verdict_reason = (
            f"目前仍屬於正常累積。因為本月只完成 {format_number(progress_pct, 0)}%，"
            "目前負荷與里程都還在可接受區間，月底再做完整評估即可。"
        )
    elif intelligence["load_delta"] is not None and intelligence["load_delta"] < -15:
        verdict = "吸收月"
        verdict_reason = "本月整體偏向吸收與調整，負荷低於近期平均，但方向仍然合理。"
    elif intelligence["load_delta"] is not None and intelligence["load_delta"] > 15:
        verdict = "負荷建構"
        verdict_reason = "本月負荷高於近期平均，代表正處於明顯的建構期，恢復品質會變得更重要。"
    else:
        verdict = "平衡建構"
        verdict_reason = "本月方向整體平衡，里程、品質課與長跑配置都還在合理範圍內。"

    letter = monthly_letter_payload(monthly, intelligence, verdict, phase, progress_pct)
    why_points = monthly_briefing_why_points(monthly, intelligence, progress_row, coach_memory)

    if intelligence["is_partial_month"]:
        month_state = "進行中"
    else:
        month_state = "完整"

    evidence_cards = [
        monthly_load_state_card(history_rows, selected_month, verdict),
        monthly_driver_card(intelligence, progress_row),
        monthly_structure_card(distribution_rows),
    ]
    reasoning_steps = [
        ("先看位置", "#monthly-position"),
        ("再看形成原因", "#monthly-understanding"),
        ("再看關鍵週", "#monthly-weeks"),
        ("最後回到關鍵課", "#monthly-key-activities"),
    ]

    return f"""
      {monthly_selector_bar(available_month_rows, selected_month)}
      <section class="panel-section">
        <h2>月度教練簡報</h2>
        <div class="weekly-review-grid">
          <div class="weekly-review-main">
            <div class="review-header">
              <div>
                <span class="eyebrow">{html.escape(str(monthly["month_key"]))}</span>
                <strong>{html.escape(verdict)}</strong>
                <p class="note">{html.escape(month_state)} · {html.escape(phase)}</p>
              </div>
              <span class="status-badge {"baseline" if intelligence["is_partial_month"] else "balanced"}">{html.escape(confidence)}</span>
            </div>
            <div class="review-card" id="monthly-position">
              <span>本月判讀</span>
              <strong>{html.escape(verdict)}</strong>
              <p>{html.escape(letter["opening"])}</p>
              <p class="note">月份狀態：{html.escape(month_state)} · 信心：{html.escape(confidence)} · {html.escape(confidence_reason)}</p>
              <div class="reasoning-jump-row">
                {"".join(f'<a class="inline-jump-link" href="{html.escape(href, quote=True)}">{html.escape(label)}</a>' for label, href in reasoning_steps)}
              </div>
            </div>
            <div class="coach-summary review-summary">
              <span>判讀依據</span>
              <p>這個月的判讀不是單看一次表現，而是看負荷、里程、連續性與前一階段是否接得起來。</p>
            </div>
            {monthly_coach_timeline_panel(monthly, verdict, verdict_reason, coach_memory, recommendation)}
            <div class="coach-summary review-summary">
              <span>為什麼這樣判斷</span>
              <ul class="briefing-point-list">
                {"".join(f"<li>{html.escape(point)}</li>" for point in why_points)}
              </ul>
            </div>
            <div class="coach-summary review-summary">
              <span>下一步</span>
              <p>{html.escape(letter["looking_forward"])}</p>
            </div>
          </div>
          <div class="weekly-review-side">
            <div class="review-card">
              <span>本月摘要</span>
              <strong>{html.escape(format_number(monthly["total_km"], 1))} km</strong>
              <p>負荷 {html.escape(format_number(monthly["training_load"], 0))} · 平均配速 {html.escape(format_pace_seconds(monthly["avg_pace_sec_per_km"]))}</p>
              <p class="note">這裡只保留最短摘要；詳細證據放在下方關鍵圖表裡。</p>
            </div>
          </div>
        </div>
      </section>
      <section class="panel-section" id="monthly-understanding">
        <h2>教練怎麼理解這個月</h2>
        <p class="note">{html.escape(letter["evidence_intro"])}</p>
        <div class="metric-grid training-kpi-grid briefing-evidence-grid">
          {"".join(evidence_cards)}
        </div>
      </section>
      <section class="panel-section" id="monthly-weeks">
        <h2>教練沿著哪些週確認這個月</h2>
        <p class="note">月份判讀不是直接跳到單堂課，而是先看哪幾週一起把這個月推到現在的位置。</p>
        {monthly_related_weeks_table(related_week_rows)}
      </section>
      <section class="panel-section" id="monthly-key-activities">
        <h2>教練看了哪些關鍵課</h2>
        {monthly_key_sessions_table(key_session_rows)}
      </section>
    """


def weekly_review_panel(weekly, intelligence, history_rows, distribution_rows, key_session_rows, selected_week="0"):
    if not weekly or not intelligence:
        return """
        <section class="panel-section">
          <h2>週回顧</h2>
          <p class="note">目前還沒有足夠的週資料可以建立回顧。</p>
        </section>
        """
    baseline_km = intelligence["baseline_km"]
    baseline_load = intelligence["baseline_load"]
    baseline_load_per_km = intelligence["baseline_load_per_km"]
    baseline_text = "前四週平均尚在建立中。"
    if baseline_km is not None and baseline_load is not None:
        baseline_text = (
            f"前四週平均 {format_number(baseline_km, 2)} km / "
            f"負荷 {format_number(baseline_load, 1)} / "
            f"每公里負荷 {format_number(baseline_load_per_km, 1)}"
        )
    review = weekly_review_payload(weekly, intelligence)
    evidence_cards = [
        weekly_learning_driver_card(intelligence, distribution_rows),
        weekly_structure_card(distribution_rows),
    ]
    return f"""
      <section class="panel-section">
        <h2>週教練簡報</h2>
        <div class="weekly-review-grid">
          <div class="weekly-review-main">
            <div class="review-header">
              <div>
                <span class="eyebrow">{html.escape(week_label_from_offset(weekly["week_offset"])) if weekly["week_offset"] is not None else "週次"}</span>
                <strong>{html.escape(str(weekly["start_date"]))} – {html.escape(str(weekly["end_date"]))}</strong>
              </div>
              {recovery_badge(intelligence["recovery_status"])}
            </div>
            <div class="coach-summary review-summary" id="weekly-learning">
              <span>先回答一件事</span>
              <strong>{html.escape(review["learning_question"])}</strong>
              <p>{html.escape(review["learning"])}</p>
              <div class="reasoning-jump-row">
                {"".join(f'<a class="inline-jump-link" href="{html.escape(href, quote=True)}">{html.escape(label)}</a>' for label, href in review["reasoning_steps"])}
              </div>
            </div>
            <div class="coach-summary review-summary">
              <span>這週最大的收穫</span>
              <p>{html.escape(review["focus"])}</p>
            </div>
            <div class="coach-summary review-summary">
              <span>教練判讀</span>
              <strong>{html.escape(review["verdict"])}</strong>
              <p>{html.escape(review["why"])}</p>
              <p class="note">{html.escape(baseline_text)}</p>
            </div>
            <div class="coach-summary review-summary">
              <span>下週，只做一件事</span>
              <p>{html.escape(review["looking_forward"])}</p>
            </div>
          </div>
          <div class="weekly-review-side">
            <div class="review-card">
              <span>本週摘要</span>
              <strong>{html.escape(format_number(weekly['total_km'], 1))} km</strong>
              <p>負荷 {html.escape(format_number(weekly["training_load"], 0))} · 活動 {html.escape(str(weekly["activities"] or 0))} 次</p>
              <p class="note">這裡只保留最短摘要；真正的理解放在下方教練推理裡。</p>
            </div>
            <div class="review-card">
              <span>本週相對基準</span>
              <strong>{html.escape(format_delta_pct(intelligence["load_delta"]) if intelligence["load_delta"] is not None else "基準建立中")}</strong>
              <p>里程 {html.escape(format_delta_pct(intelligence["km_delta"]) if intelligence["km_delta"] is not None else "—")} · 每公里負荷 {html.escape(format_number(intelligence["current_load_per_km"], 1) if intelligence["current_load_per_km"] is not None else "—")}</p>
            </div>
          </div>
        </div>
      </section>
      <section class="panel-section" id="weekly-cause">
        <h2>教練怎麼理解這週</h2>
        <p class="note">{html.escape(review["evidence_intro"])}</p>
        <div class="metric-grid training-kpi-grid briefing-evidence-grid">
          {"".join(evidence_cards)}
        </div>
      </section>
      <section class="panel-section" id="weekly-key-activities">
        <h2>教練看了哪些關鍵課</h2>
        <p class="note">這裡不是列出全部活動，而是列出最能解釋這週學習是怎麼長出來的那幾堂課。</p>
        {monthly_key_sessions_table(key_session_rows)}
      </section>
      <section class="panel-section">
        <h2>最近 5 週節奏</h2>
        {weekly_history_table(history_rows, selected_week)}
      </section>
    """


def shoe_display_name(row):
    if "shoe_display_name" in row.keys() and row["shoe_display_name"]:
        return str(row["shoe_display_name"])
    brand = row["brand"]
    if str(brand or "").strip().lower() == "unknown":
        brand = None
    parts = [brand, row["model"], row["nickname"]]
    return " ".join(str(part) for part in parts if part)


def shoe_kpi_card(label, value, subtext=""):
    sub_html = f"<p>{html.escape(subtext)}</p>" if subtext else ""
    return f"""
      <div class="review-card shoe-kpi-card">
        <span>{html.escape(label)}</span>
        <strong>{html.escape(str(value))}</strong>
        {sub_html}
      </div>
    """


def shoes_page_panel(rows, intelligence_rows, workout_rows, status_rows, message=""):
    used_rows = [row for row in rows if (row["run_count"] or 0) > 0]
    active_rows = [row for row in rows if row["is_active"]]
    tagged_rows = [row for row in intelligence_rows if (row["tagged_activity_count"] or 0) > 0]

    most_used = max(used_rows, key=lambda row: (row["total_distance_km"] or 0, row["run_count"] or 0), default=None)
    fastest = min(
        [row for row in used_rows if row["avg_pace_sec_per_km"] is not None],
        key=lambda row: row["avg_pace_sec_per_km"],
        default=None,
    )
    highest_load = max(
        [row for row in used_rows if row["avg_training_load"] is not None],
        key=lambda row: row["avg_training_load"],
        default=None,
    )

    kpis = [
        shoe_kpi_card("服役鞋款", len(active_rows), "目前仍在輪替中"),
        shoe_kpi_card(
            "最常使用",
            shoe_display_name(most_used) if most_used else "—",
            f"{format_number(most_used['total_distance_km'], 2)} km"
            if most_used
            else "",
        ),
        shoe_kpi_card(
            "最快平均配速",
            format_pace_seconds(fastest["avg_pace_sec_per_km"]) if fastest else "—",
            shoe_display_name(fastest) if fastest else "",
        ),
        shoe_kpi_card(
            "最高平均負荷",
            format_number(highest_load["avg_training_load"], 1) if highest_load else "—",
            shoe_display_name(highest_load) if highest_load else "",
        ),
    ]

    lowest_hr_tagged = min(
        [row for row in tagged_rows if row["tagged_avg_hr"] is not None],
        key=lambda row: row["tagged_avg_hr"],
        default=None,
    )
    fastest_tagged = min(
        [row for row in tagged_rows if row["tagged_avg_pace_sec_per_km"] is not None],
        key=lambda row: row["tagged_avg_pace_sec_per_km"],
        default=None,
    )
    lowest_gct_tagged = min(
        [row for row in tagged_rows if row["tagged_avg_gct_ms"] is not None],
        key=lambda row: row["tagged_avg_gct_ms"],
        default=None,
    )

    tagged_activity_total = sum((row["tagged_activity_count"] or 0) for row in intelligence_rows)
    tagged_km_total = sum((row["tagged_total_km"] or 0) for row in intelligence_rows)

    easy_rows = [row for row in workout_rows if classify_shoe_workout_bucket(row["workout_type_name_en"]) == "easy" and row["avg_hr"] is not None]
    quality_rows = [row for row in workout_rows if classify_shoe_workout_bucket(row["workout_type_name_en"]) == "quality" and row["avg_pace_sec_per_km"] is not None]
    long_run_rows = [row for row in workout_rows if classify_shoe_workout_bucket(row["workout_type_name_en"]) == "long_run"]

    easiest_shoe = min(easy_rows, key=lambda row: (row["avg_hr"], row["avg_pace_sec_per_km"] or 10**9), default=None)
    quality_shoe = min(quality_rows, key=lambda row: row["avg_pace_sec_per_km"], default=None)
    long_run_shoe = max(long_run_rows, key=lambda row: (row["total_km"] or 0, row["activity_count"] or 0), default=None)

    insight_cards = []
    if tagged_rows:
        if lowest_hr_tagged:
            insight_cards.append(
                shoe_kpi_card(
                    "最低標註心率",
                    f"{int(round(lowest_hr_tagged['tagged_avg_hr']))} bpm",
                    shoe_display_name(lowest_hr_tagged),
                )
            )
        if fastest_tagged:
            insight_cards.append(
                shoe_kpi_card(
                    "最快標註配速",
                    format_pace_seconds(fastest_tagged["tagged_avg_pace_sec_per_km"]),
                    shoe_display_name(fastest_tagged),
                )
            )
        if lowest_gct_tagged:
            insight_cards.append(
                shoe_kpi_card(
                    "最低標註 GCT",
                    f"{format_number(lowest_gct_tagged['tagged_avg_gct_ms'], 1)} ms",
                    shoe_display_name(lowest_gct_tagged),
                )
            )
    else:
        insight_cards.append(
            shoe_kpi_card(
                "標註比較",
                "資料不足",
                "補齊鞋款與課表標註後，鞋款判讀會更乾淨",
            )
        )

    comparison_cards = []
    if easiest_shoe:
        comparison_cards.append(
            shoe_kpi_card(
                "最適合輕鬆 / 恢復",
                str(easiest_shoe["shoe_display_name"] or "—"),
                f"{int(round(easiest_shoe['avg_hr']))} bpm · {easiest_shoe['workout_type_name_en']}",
            )
        )
    if quality_shoe:
        comparison_cards.append(
            shoe_kpi_card(
                "最適合品質課",
                str(quality_shoe["shoe_display_name"] or "—"),
                f"{format_pace_seconds(quality_shoe['avg_pace_sec_per_km'])} · {quality_shoe['workout_type_name_en']}",
            )
        )
    if long_run_shoe:
        comparison_cards.append(
            shoe_kpi_card(
                "最適合長跑累積",
                str(long_run_shoe["shoe_display_name"] or "—"),
                f"{format_number(long_run_shoe['total_km'], 1)} km · {long_run_shoe['workout_type_name_en']}",
            )
        )
    if not comparison_cards:
        comparison_cards.append(
            shoe_kpi_card(
                "鞋款比較",
                "還不夠乾淨",
                "先補鞋款與課表標註，再回來看哪雙鞋更適合什麼。",
            )
        )

    table_rows = []
    for row in rows:
        name = shoe_display_name(row) or row["shoe_code"]
        status = "服役中" if row["is_active"] else "已退役"
        last_run = format_short_datetime(row["observed_last_run_time"]) if row["observed_last_run_time"] else "尚無跑步紀錄"
        pace = format_pace_seconds(row["avg_pace_sec_per_km"]) or "—"
        avg_hr = "" if row["avg_hr"] is None else str(int(round(row["avg_hr"])))
        avg_load = "" if row["avg_training_load"] is None else format_number(row["avg_training_load"], 1)
        cadence = "" if row["avg_cadence_spm"] is None else format_number(row["avg_cadence_spm"], 1)
        table_rows.append(
            f"""
            <tr>
              <td>{html.escape(name)}</td>
              <td>{html.escape(str(row["category"] or ""))}</td>
              <td>{html.escape(status)}</td>
              <td>{row["run_count"]}</td>
              <td>{format_number(row["total_distance_km"], 2)}</td>
              <td>{html.escape(pace)}</td>
              <td>{html.escape(avg_hr)}</td>
              <td>{html.escape(avg_load)}</td>
              <td>{html.escape(cadence)}</td>
              <td>{html.escape(last_run)}</td>
            </tr>
            """
        )

    workout_rows_html = []
    for row in workout_rows:
        workout_rows_html.append(
            f"""
            <tr>
              <td>{html.escape(str(row["shoe_display_name"] or ""))}</td>
              <td>{html.escape(str(row["workout_type_name_en"] or ""))}</td>
              <td>{row["activity_count"]}</td>
              <td>{format_number(row["total_km"], 2)}</td>
              <td>{html.escape(format_pace_seconds(row["avg_pace_sec_per_km"]))}</td>
              <td>{'' if row["avg_hr"] is None else int(round(row["avg_hr"]))}</td>
              <td>{'' if row["avg_training_load"] is None else format_number(row["avg_training_load"], 1)}</td>
              <td>{'' if row["avg_cadence_spm"] is None else format_number(row["avg_cadence_spm"], 1)}</td>
              <td>{'' if row["avg_gct_ms"] is None else format_number(row["avg_gct_ms"], 1)}</td>
              <td>{'' if row["avg_stride_length_mm"] is None else format_number(row["avg_stride_length_mm"], 1)}</td>
            </tr>
            """
        )

    status_editor_rows = []
    for row in status_rows:
        display_name = shoe_display_name(row) or row["shoe_code"]
        active_selected = " selected" if row["is_active"] else ""
        retired_selected = " selected" if not row["is_active"] else ""
        status_editor_rows.append(
            f"""
            <tr>
              <td>{html.escape(display_name)}</td>
              <td>{html.escape(str(row["category"] or ""))}</td>
              <td>
                <form method="post" action="/shoes/save-status" class="inline-status-form">
                  <input type="hidden" name="shoe_id" value="{row["id"]}">
                  <label class="inline-field">
                    <span>狀態</span>
                    <select name="is_active">
                      <option value="1"{active_selected}>服役中</option>
                      <option value="0"{retired_selected}>已退役</option>
                    </select>
                  </label>
              </td>
              <td>
                  <label class="inline-field">
                    <span>退役日期</span>
                    <input type="date" name="retire_date" value="{html.escape(str(row["retire_date"] or ""), quote=True)}">
                  </label>
              </td>
              <td>
                  <button type="submit">儲存</button>
                </form>
              </td>
            </tr>
            """
        )

    message_html = f'<section class="status">{html.escape(message)}</section>' if message else ""
    has_tracked_shoes = bool(status_rows)
    add_shoe_help = (
        "先把目前在用的鞋款加進來，之後補活動標註時就不用再回頭改設定檔。"
        if not has_tracked_shoes
        else "新增目前在用的鞋款後，歷史活動就能開始補標，鞋款判讀也會一起變乾淨。"
    )
    empty_note_html = ""
    if not rows:
        empty_note_html = '<p class="note">目前還沒有鞋款資料，先從新增你現在在用的鞋開始。</p>'

    return f"""
      {message_html}
      <section class="panel-section">
        <h2>先補鞋款</h2>
        <div class="weekly-review-grid">
          <div class="weekly-review-main">
            <div class="review-header">
              <div>
                <span class="eyebrow">第一個有感的標註</span>
                <strong>先把目前在用的鞋款加進來</strong>
              </div>
              <span class="status-badge balanced">{len(status_rows)} tracked</span>
            </div>
            <div class="coach-summary review-summary">
              <span>為什麼先補鞋款</span>
              <p>{html.escape(add_shoe_help)}</p>
            </div>
            {empty_note_html}
            <form method="post" action="/shoes/add" class="metadata-form">
              <label>
                <span>鞋款名稱</span>
                <input type="text" name="shoe_name" placeholder="例如：Adidas Boston 13" required>
              </label>
              <div class="form-actions">
                <button type="submit">新增鞋款</button>
              </div>
            </form>
          </div>
          <div class="weekly-review-side">
            <div class="review-card">
              <span>新增後會影響</span>
              <strong>Activity / Weekly / Monthly</strong>
              <p>鞋款補齊後，單堂課、週回顧與鞋款頁的判讀都會更完整。</p>
            </div>
          </div>
        </div>
      </section>
      <section class="panel-section">
        <h2>鞋款</h2>
        <div class="weekly-review-grid">
          <div class="weekly-review-main">
            <div class="review-header">
              <div>
                <span class="eyebrow">裝備回顧</span>
                <strong>用語意層做鞋款比較</strong>
              </div>
              <span class="status-badge balanced">{len(rows)} tracked</span>
            </div>
            <div class="metric-grid shoe-kpi-grid">
              {"".join(kpis)}
            </div>
            <div class="coach-summary review-summary">
              <span>鞋款洞察</span>
              <p>鞋款頁面現在回答的是「哪雙鞋跑最多、哪雙鞋最快、哪雙鞋承受最高平均負荷」。之後這裡很自然就能接上跑姿效率、心率漂移與鞋款適配分析。</p>
              <p class="note">目前鞋款 intelligence 只對已標註鞋款與課表的活動做比較，不對未標註資料做假設。</p>
            </div>
          </div>
          <div class="weekly-review-side">
            <div class="review-card">
              <span>累積公里</span>
              <strong>{html.escape(format_number(sum((row["total_distance_km"] or 0) for row in rows), 2))}</strong>
              <p>所有已追蹤鞋款合計</p>
            </div>
            <div class="review-card">
              <span>有跑步紀錄的鞋</span>
              <strong>{len(used_rows)}</strong>
              <p>已在活動歷史中出現</p>
            </div>
            <div class="review-card">
              <span>已標註活動</span>
              <strong>{tagged_activity_total}</strong>
              <p>{format_number(tagged_km_total, 2)} km 含鞋款與課表語境</p>
            </div>
            <div class="review-card">
              <span>尚未出現的鞋</span>
              <strong>{len([row for row in rows if (row['run_count'] or 0) == 0])}</strong>
              <p>已建立，但匯入活動中尚未出現</p>
            </div>
          </div>
        </div>
      </section>
      <section class="panel-section">
        <h2>鞋款判讀</h2>
        <div class="coach-summary review-summary">
          <span>先看哪雙鞋更適合什麼</span>
          <p>鞋款頁現在不只是在算公里，而是先回答三件事：哪雙鞋最適合輕鬆恢復、哪雙鞋最適合品質課、哪雙鞋最適合長距離累積。</p>
          <p class="note">若標註還不夠，先到標註助手補鞋款與課表，這裡的判讀就會自然變清楚。</p>
        </div>
        <div class="metric-grid shoe-kpi-grid">
          {"".join(comparison_cards)}
        </div>
      </section>
      <section class="panel-section">
        <h2>鞋款比較證據</h2>
        <div class="metric-grid shoe-kpi-grid">
          {"".join(insight_cards)}
        </div>
      </section>
      <section class="panel-section">
        <h2>鞋款狀態</h2>
        <p class="note">先把鞋況整理乾淨，之後補歷史活動標註時，標註助手就能區分服役中與已退役鞋款。</p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>鞋款</th>
                <th>分類</th>
                <th>狀態</th>
                <th>退役日期</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>{"".join(status_editor_rows)}</tbody>
          </table>
        </div>
      </section>
      <section class="panel-section">
        <h2>已標註課表比較</h2>
        <p class="note">只納入同時有鞋款與課表類型標註的活動。</p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>鞋款</th>
                <th>課表</th>
                <th>活動數</th>
                <th>KM</th>
                <th>平均配速</th>
                <th>平均心率</th>
                <th>平均負荷</th>
                <th>步頻</th>
                <th>GCT</th>
                <th>步幅</th>
              </tr>
            </thead>
            <tbody>{"".join(workout_rows_html) if workout_rows_html else '<tr><td colspan=\"10\">目前已標註資料還不夠。</td></tr>'}</tbody>
          </table>
        </div>
      </section>
      <section class="panel-section">
        <h2>鞋款總覽</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>鞋款</th>
                <th>分類</th>
                <th>狀態</th>
                <th>次數</th>
                <th>總公里</th>
                <th>平均配速</th>
                <th>平均心率</th>
                <th>平均負荷</th>
                <th>步頻</th>
                <th>最近一次</th>
              </tr>
            </thead>
            <tbody>{"".join(table_rows)}</tbody>
          </table>
        </div>
      </section>
    """


def training_metric_card(label, value, subtext=""):
    sub_html = f"<p>{html.escape(subtext)}</p>" if subtext else ""
    return f"""
      <div class="review-card training-kpi-card">
        <span>{html.escape(label)}</span>
        <strong>{html.escape(str(value))}</strong>
        {sub_html}
      </div>
    """


def training_metric_card_with_link(label, value, subtext="", href="", link_label=""):
    sub_html = f"<p>{html.escape(subtext)}</p>" if subtext else ""
    link_html = ""
    if href and link_label:
        link_html = f'<p><a href="{html.escape(href, quote=True)}">{html.escape(link_label)}</a></p>'
    return f"""
      <div class="review-card training-kpi-card">
        <span>{html.escape(label)}</span>
        <strong>{html.escape(str(value))}</strong>
        {sub_html}
        {link_html}
      </div>
    """


def metadata_scope_link(scope, current_scope, count, label, note):
    active = " active" if scope == current_scope else ""
    href = "/?" + urlencode({"page": "metadata", "scope": scope})
    return f"""
      <a class="scope-link{active}" href="{html.escape(href, quote=True)}">
        <span>{html.escape(label)}</span>
        <strong>{html.escape(str(count))}</strong>
        <p>{html.escape(note)}</p>
      </a>
    """


def classify_shoe_workout_bucket(workout_name):
    value = str(workout_name or "").strip().lower()
    if value in {"recovery run", "easy run"}:
        return "easy"
    if value in {"tempo run", "interval", "progression run"}:
        return "quality"
    if value in {"lsd", "long run"}:
        return "long_run"
    return ""


def training_balance_table(rows):
    if not rows:
        return '<p class="note">目前還沒有可用的訓練平衡資料。</p>'
    body = []
    for row in rows:
        body.append(
            f"""
            <tr>
              <td>{html.escape(str(row["intensity_category"] or "未標註"))}</td>
              <td>{row["activity_count"]}</td>
              <td>{format_number(row["total_km"], 2)}</td>
              <td>{html.escape(format_hours(row["total_time_sec"]))}</td>
              <td>{'' if row["avg_training_load"] is None else format_number(row["avg_training_load"], 1)}</td>
              <td>{'' if row["total_training_load"] is None else format_number(row["total_training_load"], 1)}</td>
            </tr>
            """
        )
    return f"""
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>強度</th>
              <th>活動數</th>
              <th>KM</th>
              <th>時間</th>
              <th>平均負荷</th>
              <th>總負荷</th>
            </tr>
          </thead>
          <tbody>{"".join(body)}</tbody>
        </table>
      </div>
    """


def recent_training_intent_table(rows):
    if not rows:
        return '<p class="note">目前還沒有最近訓練意圖資料。</p>'
    body = []
    for row in rows:
        purpose = row["primary_training_purpose_name_en"] or "未標註"
        if row["secondary_training_purpose_names_en"]:
            purpose = f"{purpose} + {row['secondary_training_purpose_names_en']}" if purpose != "未標註" else row["secondary_training_purpose_names_en"]
        body.append(
            f"""
            <tr>
              <td>{format_activity_time(row["activity_start_time"])}</td>
              <td>{html.escape(str(row["activity_name"] or row["activity_type"] or ""))}</td>
              <td>{html.escape(str(row["workout_type_name_en"] or "未標註"))}</td>
              <td>{html.escape(str(purpose or "未標註"))}</td>
              <td>{html.escape(str(row["intensity_category"] or "未標註"))}</td>
              <td>{format_number(row["distance_km"], 2)}</td>
              <td>{'' if row["training_load"] is None else row["training_load"]}</td>
              <td>{html.escape(str(row["shoe_display_name"] or "未標註"))}</td>
            </tr>
            """
        )
    return f"""
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>開始時間</th>
              <th>活動</th>
              <th>課表</th>
              <th>目的</th>
              <th>強度</th>
              <th>KM</th>
              <th>負荷</th>
              <th>鞋款</th>
            </tr>
          </thead>
          <tbody>{"".join(body)}</tbody>
        </table>
      </div>
    """


def training_page_panel(distribution_rows, balance_rows, quality_row, recent_rows):
    if quality_row is None:
        return """
        <section class="panel-section">
          <h2>訓練</h2>
          <p class="note">目前還沒有可用的訓練資料。</p>
        </section>
        """

    total = quality_row["total_activities"] or 0
    workout_tagged = quality_row["workout_tagged_activities"] or 0
    purpose_tagged = quality_row["purpose_tagged_activities"] or 0
    fully_tagged = quality_row["fully_tagged_activities"] or 0
    unassigned = quality_row["unassigned_activities"] or 0

    balance_map = {str(row["intensity_category"] or "未標註"): row for row in balance_rows}

    def balance_count(label):
        row = balance_map.get(label)
        if row is None:
            return 0
        return int(row["activity_count"] or 0)

    quality_count = balance_count("Quality")
    easy_count = balance_count("Easy")
    recovery_count = balance_count("Recovery")
    long_run_count = sum(1 for row in recent_rows if (row["workout_type_name_en"] or "").lower() in {"long run", "lsd"})

    top_distribution = distribution_rows[0] if distribution_rows else None
    top_mix_text = "目前還沒有可比較的標註組合。"
    if top_distribution:
        top_mix_text = (
            f"{top_distribution['workout_type_name_en'] or '未標註'} / "
            f"{top_distribution['primary_training_purpose_name_en'] or '未標註'} · "
            f"{format_number(top_distribution['total_km'], 2)} km"
        )

    kpis = [
        training_metric_card("已標註課表", f"{workout_tagged}/{total}", f"{format_number(quality_row['workout_tagged_pct'], 1)}% 覆蓋"),
        training_metric_card("已標註目的", f"{purpose_tagged}/{total}", f"{format_number(quality_row['purpose_tagged_pct'], 1)}% 覆蓋"),
        training_metric_card("完整標註", f"{fully_tagged}/{total}", f"{format_number(quality_row['fully_tagged_pct'], 1)}% 可直接進深度分析"),
        training_metric_card_with_link(
            "未標註",
            unassigned,
            "仍缺課表或訓練目的標籤",
            "/?page=metadata&scope=unassigned",
            "前往標註助手",
        ),
    ]

    insight_cards = [
        training_metric_card("品質 / 輕鬆", f"{quality_count} / {easy_count}", "觀察強度是否平衡"),
        training_metric_card("恢復課次數", recovery_count, "明確以恢復為主的活動"),
        training_metric_card("長跑標記", long_run_count, "最近資料中的長跑型活動"),
        training_metric_card("最常見標註組合", top_distribution["activity_count"] if top_distribution else "—", top_mix_text),
    ]

    next_step_text = "先補最近那批未標註活動，鞋款、週回顧與 AI 判讀都會一起變乾淨。"
    if unassigned == 0:
        next_step_text = "目前標註已經夠穩，可以回頭看週回顧、月回顧與鞋款頁的判讀差異。"

    return f"""
      <section class="panel-section">
        <h2>訓練</h2>
        <div class="weekly-review-grid">
          <div class="weekly-review-main">
            <div class="review-header">
              <div>
                <span class="eyebrow">訓練回顧</span>
                <strong>看訓練怎麼被標註、平衡與理解</strong>
              </div>
              <span class="status-badge balanced">{total} activities</span>
            </div>
            <div class="metric-grid training-kpi-grid">
              {"".join(kpis)}
            </div>
            <div class="coach-summary review-summary">
              <span>訓練洞察</span>
              <p>訓練頁面先回答三件事：課表與訓練目的目前標得多完整、最近訓練在強度上是否平衡，以及哪些已標註活動已經可以支援更深的週分析、鞋款分析與 AI Coach。</p>
              <p class="note"><a href="/?page=metadata&scope=unassigned">有缺標註的活動時，直接到標註助手補鞋款、課表與訓練目的。</a></p>
            </div>
          </div>
          <div class="weekly-review-side">
            <div class="review-card">
              <span>完整標註比例</span>
              <strong>{html.escape(format_number(quality_row['fully_tagged_pct'], 1))}%</strong>
              <p>同時有課表與目的標籤的活動</p>
            </div>
            <div class="review-card">
              <span>可直接用於判讀</span>
              <strong>{fully_tagged}</strong>
              <p>可直接支援鞋款與週回顧分析</p>
            </div>
            <div class="review-card">
              <span>需要補標註</span>
              <strong>{unassigned}</strong>
              <p>最適合優先補資料的一批活動</p>
            </div>
            <div class="review-card">
              <span>下一步最省力</span>
              <strong>{"先補標註" if unassigned else "回看判讀"}</strong>
              <p>{html.escape(next_step_text)}</p>
            </div>
          </div>
        </div>
      </section>
      <section class="panel-section">
        <h2>訓練平衡</h2>
        <div class="metric-grid training-kpi-grid">
          {"".join(insight_cards)}
        </div>
        {training_balance_table(balance_rows)}
      </section>
      <section class="panel-section">
        <h2>課表 / 目的分布</h2>
        {training_distribution_panel(distribution_rows)}
      </section>
      <section class="panel-section">
        <h2>最近訓練意圖</h2>
        <p class="note">最近活動目前對應的課表與訓練目的，包含仍待補標註的資料列。</p>
        {recent_training_intent_table(recent_rows)}
      </section>
    """


def metadata_metric_card(label, value, subtext=""):
    sub_html = f"<p>{html.escape(subtext)}</p>" if subtext else ""
    return f"""
      <div class="review-card training-kpi-card">
        <span>{html.escape(label)}</span>
        <strong>{html.escape(str(value))}</strong>
        {sub_html}
      </div>
    """


def metadata_status_label(row):
    missing = []
    if row["shoe_id"] is None:
        missing.append("shoe")
    if row["workout_type_id"] is None:
        missing.append("workout")
    if row["primary_training_purpose_id"] is None:
        missing.append("purpose")
    if not missing:
        return "完整"
    return "缺少：" + ", ".join(missing)


def metadata_select(name, options, selected_code="", allow_blank=False, include_keep=False):
    tags = []
    if include_keep:
        tags.append('<option value="__KEEP__">（保留原值）</option>')
        tags.append('<option value="__CLEAR__">（清空）</option>')
    elif allow_blank:
        tags.append('<option value="">（無）</option>')
    for option in options:
        code = option["code"]
        label = option["label"]
        extra = option.get("extra", "")
        text = label if not extra else f"{label} · {extra}"
        selected = " selected" if selected_code == code else ""
        tags.append(
            f'<option value="{html.escape(code, quote=True)}"{selected}>{html.escape(text)}</option>'
        )
    return f'<select name="{html.escape(name, quote=True)}">{"".join(tags)}</select>'


def metadata_page_panel(
    candidates,
    selected_row,
    shoes,
    workouts,
    purposes,
    quality_row,
    scope_counts,
    scope,
    message,
):
    total = quality_row["total_activities"] if quality_row else 0
    fully_tagged = quality_row["fully_tagged_activities"] if quality_row else 0
    unassigned = quality_row["unassigned_activities"] if quality_row else 0
    coverage = format_number(quality_row["fully_tagged_pct"], 1) if quality_row else "0"
    message_html = ""
    if message:
        message_html = f'<section class="status">{html.escape(message)}</section>'

    shoe_options = [
        {
            "code": row["shoe_code"],
            "label": shoe_display_name(row) or row["shoe_code"],
            "extra": "active" if row["is_active"] else "retired",
        }
        for row in shoes
    ]
    workout_options = [
        {
            "code": row["workout_type_code"],
            "label": row["name_en"],
            "extra": row["intensity_category"],
        }
        for row in workouts
    ]
    purpose_options = [
        {
            "code": row["training_purpose_code"],
            "label": row["name_en"],
            "extra": row["purpose_category"],
        }
        for row in purposes
    ]

    scope_cards = [
        metadata_scope_link("unassigned", scope, scope_counts["unassigned"] or 0, "只看未標註", "最適合優先補資料"),
        metadata_scope_link("missing_shoe", scope, scope_counts["missing_shoe"] or 0, "先補鞋款", "最快改善鞋款分析"),
        metadata_scope_link("missing_workout", scope, scope_counts["missing_workout"] or 0, "先補課表", "讓週 / 月回顧更準"),
        metadata_scope_link("missing_purpose", scope, scope_counts["missing_purpose"] or 0, "先補目的", "讓教練判讀更有語境"),
        metadata_scope_link("all", scope, scope_counts["total"] or 0, "看最近全部", "需要回頭校正時再看"),
    ]

    scope_names = {
        "unassigned": "僅未標註",
        "missing_shoe": "缺鞋款",
        "missing_workout": "缺課表",
        "missing_purpose": "缺目的",
        "all": "最近全部",
        "complete": "完整標註",
    }
    current_scope_name = scope_names.get(scope, "僅未標註")

    helper_text = "先從『缺鞋款』開始補，鞋款分析會最有感。"
    if scope == "missing_workout":
        helper_text = "這一批先補課表類型，週回顧與月信的語氣會立刻更準。"
    elif scope == "missing_purpose":
        helper_text = "這一批先補訓練目的，平台才知道這堂課為什麼而跑。"
    elif scope == "all":
        helper_text = "這裡適合回頭校正最近活動；如果想省力，先切回上面的缺項範圍。"
    elif scope == "complete":
        helper_text = "這一批已經可直接支援更深的週 / 月 / Journey 判讀。"

    table_rows = []
    for row in candidates:
        edit_link = "/?" + urlencode({"page": "metadata", "edit": row["activity_id"], "scope": scope})
        selected_class = " selected-row" if selected_row and row["activity_id"] == selected_row["activity_id"] else ""
        table_rows.append(
            f"""
            <tr class="clickable-row{selected_class}" onclick="window.location.href='{html.escape(edit_link, quote=True)}'">
              <td><input type="checkbox" name="activity_id" value="{row['activity_id']}" onclick="event.stopPropagation();"></td>
              <td class="time-cell"><a href="{html.escape(edit_link, quote=True)}">{format_activity_time(row["activity_start_time"])}</a></td>
              <td>{html.escape(str(row["activity_name"] or row["activity_type"] or ""))}</td>
              <td>{format_number(row["distance_km"], 2)}</td>
              <td>{html.escape(str(row["shoe_display_name"] or "未標註"))}</td>
              <td>{html.escape(str(row["workout_type_name_en"] or "未標註"))}</td>
              <td>{html.escape(str(row["primary_training_purpose_name_en"] or "未標註"))}</td>
              <td>{html.escape(metadata_status_label(row))}</td>
            </tr>
            """
        )

    selected_html = ""
    if selected_row:
        selected_secondary_codes = parse_secondary_codes(selected_row["secondary_training_purpose_codes"])
        secondary_selected = selected_secondary_codes[0] if selected_secondary_codes else ""
        selected_html = f"""
          <section class="panel-section">
            <h2>活動編輯</h2>
            <div class="weekly-review-grid">
              <div class="weekly-review-main">
                <div class="review-header">
                  <div>
                    <span class="eyebrow">已選活動</span>
                    <strong>{html.escape(str(selected_row["activity_name"] or selected_row["activity_type"] or ""))}</strong>
                  </div>
                  <span class="status-badge balanced">{html.escape(metadata_status_label(selected_row))}</span>
                </div>
                <div class="detail-chips">
                  {detail_chip("開始時間", str(selected_row["activity_start_time"]).replace("T", " ")[:16])}
                  {detail_chip("距離", f"{format_number(selected_row['distance_km'], 2)} km")}
                  {detail_chip("負荷", "" if selected_row["training_load"] is None else selected_row["training_load"])}
                </div>
                <form method="post" action="/metadata/save" class="metadata-form">
                  <input type="hidden" name="activity_id" value="{selected_row["activity_id"]}">
                  <input type="hidden" name="scope" value="{html.escape(scope, quote=True)}">
                  <label>
                    <span>鞋款</span>
                    {metadata_select("shoe_code", shoe_options, selected_row["shoe_code"] or "", allow_blank=True)}
                  </label>
                  <label>
                    <span>課表類型</span>
                    {metadata_select("workout_type_code", workout_options, selected_row["workout_type_code"] or "", allow_blank=True)}
                  </label>
                  <label>
                    <span>主要目的</span>
                    {metadata_select("primary_purpose_code", purpose_options, selected_row["primary_training_purpose_code"] or "", allow_blank=True)}
                  </label>
                  <label>
                    <span>次要目的</span>
                    {metadata_select("secondary_purpose_code", purpose_options, secondary_selected, allow_blank=True)}
                  </label>
                  <div class="form-actions">
                    <button type="submit">儲存標註</button>
                  </div>
                </form>
              </div>
              <div class="weekly-review-side">
                <div class="review-card">
                  <span>目前鞋款</span>
                  <strong>{html.escape(str(selected_row["shoe_display_name"] or "未標註"))}</strong>
                  <p>歷史活動可以標到已退役鞋款</p>
                </div>
                <div class="review-card">
                  <span>目前課表</span>
                  <strong>{html.escape(str(selected_row["workout_type_name_en"] or "未標註"))}</strong>
                  <p>描述這堂課怎麼跑</p>
                </div>
                <div class="review-card">
                  <span>目前目的</span>
                  <strong>{html.escape(str(selected_row["primary_training_purpose_name_en"] or "未標註"))}</strong>
                  <p>{html.escape(str(selected_row["secondary_training_purpose_names_en"] or "目前沒有次要目的"))}</p>
                </div>
              </div>
            </div>
          </section>
        """

    return f"""
      {message_html}
      <section class="panel-section">
        <h2>標註助手</h2>
        <div class="weekly-review-grid">
          <div class="weekly-review-main">
            <div class="review-header">
              <div>
                <span class="eyebrow">標註補齊工作台</span>
                <strong>補齊缺少的鞋款、課表與訓練目的</strong>
              </div>
              <span class="status-badge balanced">目前 {len(candidates)} 筆活動</span>
            </div>
            <div class="metric-grid training-kpi-grid">
              {metadata_metric_card("總活動數", total, "所有已匯入活動")}
              {metadata_metric_card("完整標註", f"{fully_tagged}/{total}", f"{coverage}% 已可進入判讀")}
              {metadata_metric_card("未標註", unassigned, "仍缺課表或目的語境")}
              {metadata_metric_card("目前範圍", current_scope_name, "可先依缺項縮小範圍")}
            </div>
            <div class="coach-summary review-summary">
              <span>助手原則</span>
              <p>標註助手只補你真的知道的資料。看不到答案的活動，就先保留未標註，讓平台誠實反映目前的 Source of Truth。</p>
            </div>
          </div>
          <div class="weekly-review-side">
            <div class="review-card">
              <span>範圍</span>
              <strong>{html.escape(current_scope_name)}</strong>
              <p>{html.escape(helper_text)}</p>
            </div>
            <div class="review-card">
              <span>退役鞋款</span>
              <strong>可補標</strong>
              <p>只要資料匯入工具下拉選單有的鞋，都能用來補歷史資料</p>
            </div>
          </div>
        </div>
      </section>

      <section class="panel-section">
        <h2>先補哪一批會最省力</h2>
        <div class="scope-link-grid">
          {"".join(scope_cards)}
        </div>
      </section>

      {selected_html}

      <section class="panel-section">
        <h2>批次補標</h2>
        <p class="note">先選幾筆活動，再把相同標註一次套用。若只想更新其中一項，就把其他欄位留在保留原值。</p>
        <form method="post" action="/metadata/batch">
          <input type="hidden" name="scope" value="{html.escape(scope, quote=True)}">
          <div class="metadata-batch-bar">
            <label>
              <span>鞋款</span>
              {metadata_select("batch_shoe_code", shoe_options, include_keep=True)}
            </label>
            <label>
              <span>課表類型</span>
              {metadata_select("batch_workout_type_code", workout_options, include_keep=True)}
            </label>
            <label>
              <span>主要目的</span>
              {metadata_select("batch_primary_purpose_code", purpose_options, include_keep=True)}
            </label>
            <label>
              <span>次要目的</span>
              {metadata_select("batch_secondary_purpose_code", purpose_options, include_keep=True)}
            </label>
            <div class="form-actions compact">
              <button type="submit">套用到所選活動</button>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>選取</th>
                  <th>開始時間</th>
                  <th>活動</th>
                  <th>KM</th>
                  <th>鞋款</th>
                  <th>課表</th>
                  <th>主要目的</th>
                  <th>狀態</th>
                </tr>
              </thead>
              <tbody>{"".join(table_rows) if table_rows else '<tr><td colspan=\"8\">這個範圍目前沒有活動。</td></tr>'}</tbody>
            </table>
          </div>
        </form>
      </section>
    """


def base_styles():
    return """
    :root {
      color-scheme: light;
      --ink: #18222f;
      --muted: #657386;
      --line: #d9e3ee;
      --accent: #0f766e;
      --page: #f3f7fa;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans TC", sans-serif;
      background: linear-gradient(180deg, #edf5f7 0, var(--page) 260px), var(--page);
      color: var(--ink);
    }
    main {
      width: min(1120px, calc(100vw - 32px));
      margin: 28px auto 40px;
    }
    .hero {
      margin: 0 0 18px;
      padding: 28px 32px;
      border-radius: 18px;
      color: #fff;
      background:
        linear-gradient(90deg, rgba(3, 33, 48, 0.78) 0%, rgba(5, 55, 65, 0.46) 52%, rgba(5, 87, 88, 0.2) 100%),
        url("/assets/rac_banner.png") center / cover no-repeat;
      box-shadow: 0 18px 48px rgba(11, 79, 95, 0.22);
      min-height: 220px;
    }
    .hero h1 {
      margin: 0;
      font-size: 42px;
      line-height: 1.15;
      letter-spacing: 0;
      text-shadow: 0 2px 12px rgba(0, 0, 0, 0.24);
    }
    .hero p {
      max-width: 720px;
      margin: 16px 0 0;
      color: rgba(255, 255, 255, 0.86);
      line-height: 1.6;
    }
    .page-nav {
      display: flex;
      gap: 10px;
      margin: 0 0 18px;
      flex-wrap: wrap;
    }
    .nav-link {
      min-height: 38px;
      display: inline-flex;
      align-items: center;
      padding: 0 14px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.82);
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0;
    }
    .nav-link.active {
      background: var(--ink);
      border-color: var(--ink);
      color: #fff;
    }
    .metric-grid {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
      margin: 0 0 18px;
    }
    .metric-card {
      min-height: 82px;
      display: grid;
      align-content: space-between;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 8px 22px rgba(31, 41, 51, 0.05);
    }
    .metric-card span {
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
      text-transform: uppercase;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }
    .metric-card strong {
      color: var(--ink);
      font-size: 24px;
      line-height: 1.1;
      overflow-wrap: anywhere;
    }
    .compact-metrics {
      grid-template-columns: repeat(5, minmax(0, 1fr));
      margin-bottom: 0;
    }
    .compact-metrics .metric-card {
      min-height: 66px;
      padding: 12px;
      box-shadow: none;
      background: rgba(255, 255, 255, 0.72);
    }
    .compact-metrics .metric-card strong {
      font-size: 18px;
    }
    .archive-strip {
      opacity: 0.9;
    }
    .panel-section {
      margin: 0 0 22px;
    }
    .panel-section h2 {
      margin: 0 0 10px;
      font-size: 18px;
      letter-spacing: 0;
    }
    .note {
      color: var(--muted);
      font-size: 13px;
      margin: 8px 0 0;
    }
    .table-wrap {
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 8px 22px rgba(31, 41, 51, 0.05);
    }
    .table-wrap tr:target {
      background: #fff8ef;
      outline: 2px solid #f3c7ae;
      outline-offset: -2px;
    }
    table {
      width: 100%;
      min-width: 560px;
      border-collapse: collapse;
      color: var(--ink);
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 9px 10px;
      text-align: left;
      vertical-align: middle;
    }
    th {
      background: #f7fafb;
      font-weight: 800;
    }
    tr:last-child td {
      border-bottom: 0;
    }
    .selected-row td {
      background: #eef6fb;
      font-weight: 700;
    }
    .clickable-row {
      cursor: pointer;
    }
    .clickable-row:hover td {
      background: #f3f8fb;
    }
    a {
      color: #0b5cad;
      text-decoration: none;
      font-weight: 800;
    }
    .time-cell span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    .chart-panel {
      overflow-x: auto;
      margin: 12px 0;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 8px 22px rgba(31, 41, 51, 0.05);
    }
    .chart-panel svg {
      width: 100%;
      min-width: 560px;
      height: auto;
      display: block;
    }
    .axis {
      stroke: #cdd7df;
      stroke-width: 1;
    }
    .trend {
      fill: none;
      stroke-width: 3;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .pace-line { stroke: #2454a6; }
    .hr-line { stroke: #c2413c; }
    .power-line { stroke: #2f8f5b; }
    .marker {
      stroke: #fff;
      stroke-width: 1.5;
    }
    .pace-marker { fill: #2454a6; }
    .hr-marker { fill: #c2413c; }
    .power-marker { fill: #2f8f5b; }
    .axis-ranges {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    .axis-ranges span {
      padding: 5px 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #f7fafb;
    }
    .axis-ranges b {
      color: var(--ink);
      margin-right: 5px;
    }
    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }
    .legend i {
      width: 10px;
      height: 10px;
      display: inline-block;
      margin-right: 6px;
      border-radius: 50%;
    }
    .pace-dot { background: #2454a6; }
    .hr-dot { background: #c2413c; }
    .power-dot { background: #2f8f5b; }
    .status {
      border-radius: 8px;
      padding: 14px 16px;
      margin: 0 0 18px;
      border: 1px solid var(--line);
      background: #fff;
      line-height: 1.55;
    }
    .detail-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 10px 0 12px;
    }
    .detail-chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 34px;
      padding: 6px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }
    .detail-chip b {
      color: var(--ink);
    }
    .today-panel {
      display: grid;
      grid-template-columns: 0.7fr 1.4fr 1fr;
      gap: 12px;
      margin-bottom: 18px;
    }
    .today-status,
    .today-suggestion,
    .today-latest {
      min-height: 132px;
      display: grid;
      align-content: space-between;
      gap: 10px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 8px 22px rgba(31, 41, 51, 0.05);
    }
    .today-status {
      background: #0f766e;
      color: #fff;
      border-color: #0f766e;
    }
    .today-status span,
    .today-suggestion span,
    .today-latest span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .today-status span {
      color: rgba(255, 255, 255, 0.75);
    }
    .today-status strong {
      font-size: 30px;
      line-height: 1;
    }
    .today-suggestion strong,
    .today-latest strong {
      font-size: 24px;
      line-height: 1.15;
    }
    .today-suggestion p {
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
      font-weight: 700;
    }
    .coach-desk-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr) minmax(280px, 0.9fr);
      gap: 12px;
      margin-bottom: 18px;
    }
    .coach-desk-card {
      min-height: 190px;
      display: grid;
      align-content: start;
      gap: 12px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 8px 22px rgba(31, 41, 51, 0.05);
    }
    .coach-desk-card span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .coach-desk-card strong {
      font-size: 28px;
      line-height: 1.15;
      color: var(--ink);
    }
    .coach-desk-card p {
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
      font-weight: 700;
    }
    .coach-desk-primary {
      background: #0f766e;
      border-color: #0f766e;
    }
    .coach-desk-primary span,
    .coach-desk-primary strong,
    .coach-desk-primary p,
    .coach-desk-primary .note,
    .coach-desk-primary .note a {
      color: #fff;
    }
    .coach-desk-primary .status-badge {
      background: rgba(255, 255, 255, 0.18);
      color: #fff;
      border-color: rgba(255, 255, 255, 0.22);
    }
    .coach-desk-focus {
      background: #eef6fb;
      border-color: #cfe1ed;
    }
    .coach-attention-card {
      display: grid;
      align-content: start;
      gap: 12px;
      padding: 18px;
      border: 1px solid #cfe1ed;
      border-radius: 8px;
      background: #eef6fb;
      box-shadow: 0 8px 22px rgba(31, 41, 51, 0.05);
      margin-bottom: 18px;
    }
    .coach-attention-card.no-focus {
      background: #f8fbfd;
      border-color: var(--line);
    }
    .coach-attention-card > span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .coach-attention-card strong {
      font-size: 30px;
      line-height: 1.15;
      color: var(--ink);
    }
    .coach-attention-card p {
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
      font-weight: 700;
    }
    .coach-attention-evidence {
      margin: 0;
      padding-left: 20px;
      display: grid;
      gap: 6px;
      color: var(--ink);
      font-weight: 700;
    }
    .coach-attention-footer {
      display: grid;
      gap: 8px;
      justify-items: start;
    }
    .coach-attention-footer small {
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }
    .coach-desk-route-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .coach-route-card {
      min-height: 160px;
      display: grid;
      align-content: start;
      gap: 10px;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 8px 22px rgba(31, 41, 51, 0.05);
      color: inherit;
    }
    .coach-route-card span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .coach-route-card strong {
      color: var(--ink);
      font-size: 22px;
      line-height: 1.2;
    }
    .coach-route-card p {
      margin: 0;
      color: var(--muted);
      line-height: 1.55;
      font-weight: 700;
    }
    .coach-route-card:hover {
      border-color: #b6cfe0;
      background: #f7fafc;
    }
    .desk-link {
      align-self: end;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 40px;
      padding: 0 14px;
      border-radius: 999px;
      background: var(--ink);
      color: #fff;
      font-size: 14px;
      font-weight: 800;
      width: fit-content;
    }
    .desk-link:hover {
      opacity: 0.92;
    }
    .intelligence-panel {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(280px, 0.72fr);
      gap: 12px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 8px 22px rgba(31, 41, 51, 0.05);
    }
    .intelligence-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }
    .intelligence-metric {
      min-height: 86px;
      display: grid;
      align-content: space-between;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #f7fafb;
    }
    .intelligence-metric span,
    .coach-summary span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .intelligence-metric strong {
      font-size: 20px;
      line-height: 1.15;
    }
    .intelligence-metric small {
      font-size: 12px;
      font-weight: 800;
    }
    .intelligence-metric small.up { color: #a74712; }
    .intelligence-metric small.down { color: #0f766e; }
    .intelligence-metric small.flat { color: var(--muted); }
    .coach-summary {
      min-height: 100%;
      display: grid;
      align-content: start;
      gap: 10px;
      padding: 14px;
      border-radius: 8px;
      background: #eef6fb;
      border: 1px solid #cfe1ed;
    }
    .coach-summary p {
      margin: 0;
      line-height: 1.65;
      font-weight: 700;
    }
    .weekly-review-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.8fr);
      gap: 12px;
    }
    .weekly-review-main,
    .weekly-review-side {
      display: grid;
      gap: 12px;
    }
    .review-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 8px 22px rgba(31, 41, 51, 0.05);
    }
    .review-header strong {
      display: block;
      margin-top: 4px;
      font-size: 22px;
      line-height: 1.15;
    }
    .eyebrow {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .status-badge {
      min-height: 34px;
      display: inline-flex;
      align-items: center;
      padding: 0 12px;
      border-radius: 999px;
      font-size: 13px;
      font-weight: 800;
      border: 1px solid transparent;
      white-space: nowrap;
    }
    .status-badge.balanced {
      color: #0f766e;
      background: #e6f6f2;
      border-color: #bce5db;
    }
    .status-badge.absorb {
      color: #0f766e;
      background: #e8f5ec;
      border-color: #c5e2cf;
    }
    .status-badge.watch {
      color: #a74712;
      background: #fff1e8;
      border-color: #f3c7ae;
    }
    .status-badge.baseline {
      color: var(--muted);
      background: #f5f7fa;
      border-color: var(--line);
    }
    .weekly-metrics {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin: 0;
    }
    .weekly-metrics .metric-card {
      min-height: 98px;
      padding: 14px;
      box-shadow: none;
      background: #f7fafb;
    }
    .weekly-metrics .metric-card strong {
      font-size: clamp(18px, 1.9vw, 24px);
    }
    .review-summary {
      min-height: 0;
    }
    .reasoning-jump-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      margin-top: 2px;
    }
    .inline-jump-link {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 32px;
      padding: 0 10px;
      border-radius: 999px;
      border: 1px solid #cfe1ed;
      background: #f8fbfd;
      color: #0f766e;
      font-size: 13px;
      font-weight: 800;
      white-space: nowrap;
    }
    .inline-jump-link:hover {
      background: #eef6fb;
      border-color: #b6d2e2;
    }
    .weekly-review-side {
      align-content: start;
    }
    .review-card {
      min-height: 120px;
      display: grid;
      align-content: space-between;
      gap: 10px;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 8px 22px rgba(31, 41, 51, 0.05);
    }
    .review-card span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .review-card strong {
      font-size: 28px;
      line-height: 1;
    }
    .review-card p {
      margin: 0;
      color: var(--muted);
      line-height: 1.5;
      font-weight: 700;
    }
    .metric-collection {
      min-height: 0;
      align-content: start;
      gap: 12px;
      background: #f9fbfd;
    }
    .progress-row {
      display: grid;
      gap: 8px;
      margin: 0 0 12px;
    }
    .progress-row:last-child {
      margin-bottom: 0;
    }
    .progress-meta {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
    }
    .progress-meta span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .progress-meta strong {
      font-size: 14px;
      line-height: 1.2;
    }
    .progress-track,
    .bar-track {
      width: 100%;
      height: 10px;
      background: #e8eef4;
      border-radius: 999px;
      overflow: hidden;
    }
    .progress-fill,
    .bar-fill {
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, #0f766e 0%, #38b2ac 100%);
    }
    .bar-group {
      display: grid;
      gap: 12px;
    }
    .bar-item {
      display: grid;
      gap: 6px;
    }
    .bar-label-line {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
    }
    .bar-label-line span {
      color: var(--ink);
      font-size: 13px;
      font-weight: 700;
      text-transform: none;
    }
    .bar-label-line strong {
      font-size: 13px;
      line-height: 1.2;
    }
    .bar-group-card {
      min-height: 0;
      gap: 14px;
    }
    .shoe-kpi-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      margin-bottom: 0;
    }
    .training-kpi-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      margin-bottom: 0;
    }
    .briefing-point-list {
      margin: 0;
      padding-left: 18px;
      display: grid;
      gap: 8px;
      color: var(--muted);
      line-height: 1.6;
      font-weight: 700;
    }
    .briefing-point-list li {
      margin: 0;
    }
    .briefing-evidence-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      align-items: start;
    }
    .briefing-evidence-grid .state-briefing-card {
      grid-column: 1 / -1;
    }
    .briefing-chart-card {
      min-height: 0;
      align-content: start;
      gap: 12px;
    }
    .briefing-chart-card strong {
      font-size: 20px;
      line-height: 1.35;
    }
    .state-briefing-card {
      gap: 14px;
    }
    .state-sequence {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 92px));
      justify-content: start;
      column-gap: 8px;
      row-gap: 0;
      align-items: start;
      max-width: 100%;
    }
    .state-node-wrap {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 12px;
      align-items: start;
      gap: 6px;
      min-width: 0;
    }
    .state-step {
      display: grid;
      align-content: start;
      justify-items: start;
      gap: 6px;
      padding: 2px 6px 0;
      border: none;
      background: transparent;
      text-align: left;
    }
    .state-step.active {
      transform: translateY(-2px);
    }
    .state-step .state-month {
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0;
      line-height: 1;
    }
    .state-marker {
      width: 100%;
      display: flex;
      justify-content: flex-start;
      align-items: center;
      min-height: 18px;
    }
    .state-dot {
      width: 12px;
      height: 12px;
      border-radius: 999px;
      background: #b8c5d1;
      box-shadow: 0 0 0 5px #edf2f7;
    }
    .state-step strong {
      justify-self: start;
      font-size: 15px;
      line-height: 1.2;
      padding: 6px 8px;
      border-radius: 999px;
      background: #f5f7fa;
      color: #243444;
      white-space: nowrap;
      word-break: keep-all;
      overflow-wrap: normal;
    }
    .state-step p {
      justify-self: start;
      margin: 0;
      color: var(--muted);
      line-height: 1.3;
      font-weight: 700;
      font-size: 11px;
    }
    .state-connector {
      height: 2px;
      width: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, #d5dee7 0%, #c1d5e5 100%);
      align-self: center;
      margin-top: 29px;
    }
    .future-connector {
      position: relative;
      background: repeating-linear-gradient(
        90deg,
        #c7d3de 0 10px,
        transparent 10px 16px
      );
    }
    .future-connector::after {
      content: "";
      position: absolute;
      right: -1px;
      top: 50%;
      transform: translateY(-50%);
      border-left: 8px solid #c7d3de;
      border-top: 5px solid transparent;
      border-bottom: 5px solid transparent;
    }
    .state-step.balanced .state-dot {
      background: #1f9d77;
      box-shadow: 0 0 0 5px #e9f7f1;
    }
    .state-step.balanced strong {
      background: #eef8f6;
      color: #0f766e;
    }
    .state-step.absorb .state-dot {
      background: #d38242;
      box-shadow: 0 0 0 5px #fff1e6;
    }
    .state-step.absorb strong {
      background: #fff3ea;
      color: #b45309;
    }
    .state-step.watch .state-dot {
      background: #c66b4a;
      box-shadow: 0 0 0 5px #fff2ec;
    }
    .state-step.watch strong {
      background: #fff4ee;
      color: #9a3412;
    }
    .state-step.baseline .state-dot {
      background: #7b8ea1;
      box-shadow: 0 0 0 5px #edf2f7;
    }
    .state-step.baseline strong {
      background: #f4f7fa;
      color: #3f5568;
    }
    .state-step.active .state-dot {
      width: 16px;
      height: 16px;
    }
    .state-step.active strong {
      box-shadow: 0 10px 22px rgba(15, 118, 110, 0.12);
    }
    .state-step.active.absorb strong {
      box-shadow: 0 10px 22px rgba(180, 83, 9, 0.12);
    }
    .state-step.future {
      opacity: 0.82;
    }
    .state-step.future strong {
      border: 1px dashed currentColor;
    }
    .state-node-wrap.future-slot .state-connector {
      margin-top: 30px;
    }
    .driver-card {
      gap: 14px;
    }
    .driver-list {
      display: grid;
      gap: 10px;
    }
    .driver-row {
      display: grid;
      gap: 6px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #f8fafc;
    }
    .driver-row-top {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
    }
    .driver-row-top strong {
      font-size: 15px;
      line-height: 1.3;
    }
    .driver-row p {
      margin: 0;
      color: var(--muted);
      line-height: 1.45;
      font-weight: 700;
      font-size: 14px;
    }
    .driver-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 5px 9px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 800;
      white-space: nowrap;
    }
    .driver-badge.driver-up {
      background: #e9f7f1;
      color: #0f766e;
    }
    .driver-badge.driver-steady {
      background: #eef2f7;
      color: #475569;
    }
    .driver-badge.driver-down {
      background: #fff1e8;
      color: #b45309;
    }
    .driver-badge.driver-neutral {
      background: #f3f4f6;
      color: #6b7280;
    }
    .trend-bar-item.active .bar-track {
      background: #d9eeea;
    }
    .trend-bar-item.active .bar-fill {
      background: linear-gradient(90deg, #0f766e 0%, #14b8a6 100%);
    }
    .trend-bar-item.active .bar-label-line span,
    .trend-bar-item.active .bar-label-line strong {
      color: #0f766e;
    }
    .journey-timeline {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 12px;
    }
    .journey-step,
    .journey-turning-point {
      min-height: 110px;
      display: grid;
      align-content: start;
      gap: 8px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 8px 22px rgba(31, 41, 51, 0.05);
    }
    .journey-step.active {
      border-color: #0f766e;
      background: #eef8f6;
      box-shadow: 0 10px 28px rgba(15, 118, 110, 0.12);
    }
    .journey-step span,
    .journey-turning-point span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .journey-step strong,
    .journey-turning-point strong {
      font-size: 18px;
      line-height: 1.25;
    }
    .journey-step p,
    .journey-turning-point p {
      margin: 0;
      color: var(--muted);
      line-height: 1.5;
      font-weight: 700;
    }
    .journey-turning-points {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .journey-session-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .journey-session-card {
      min-height: 160px;
      display: grid;
      align-content: start;
      gap: 10px;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 8px 22px rgba(31, 41, 51, 0.05);
    }
    .journey-session-card span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .journey-session-card strong {
      font-size: 20px;
      line-height: 1.25;
    }
    .journey-session-card p {
      margin: 0;
      color: var(--muted);
      line-height: 1.5;
      font-weight: 700;
    }
    .journey-session-meaning {
      color: var(--ink) !important;
    }
    .coach-timeline {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 12px;
      margin-top: 8px;
    }
    .coach-timeline-step {
      min-height: 140px;
      display: grid;
      align-content: start;
      gap: 8px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 8px 22px rgba(31, 41, 51, 0.05);
    }
    .coach-timeline-step.active {
      border-color: #0f766e;
      background: #eef8f6;
      box-shadow: 0 10px 28px rgba(15, 118, 110, 0.12);
    }
    .coach-timeline-step span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .coach-timeline-step strong {
      font-size: 18px;
      line-height: 1.25;
    }
    .coach-timeline-step p {
      margin: 0;
      color: var(--muted);
      line-height: 1.5;
      font-weight: 700;
    }
    .journey-session-chips,
    .journey-ability-chips {
      margin: 0;
    }
    .shoe-kpi-card strong {
      font-size: 22px;
      line-height: 1.15;
    }
    .training-kpi-card strong {
      font-size: 22px;
      line-height: 1.15;
    }
    .metadata-form,
    .metadata-batch-bar {
      display: grid;
      gap: 12px;
    }
    .scope-link-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
    }
    .scope-link {
      min-height: 120px;
      display: grid;
      align-content: start;
      gap: 8px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: inherit;
      text-decoration: none;
      box-shadow: 0 8px 22px rgba(31, 41, 51, 0.05);
    }
    .scope-link.active {
      border-color: #0f766e;
      background: #eef8f6;
      box-shadow: 0 10px 28px rgba(15, 118, 110, 0.12);
    }
    .scope-link span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .scope-link strong {
      font-size: 22px;
      line-height: 1.15;
    }
    .scope-link p {
      margin: 0;
      color: var(--muted);
      line-height: 1.5;
      font-weight: 700;
    }
    .month-selector-bar {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 16px;
      padding: 16px 18px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 8px 22px rgba(31, 41, 51, 0.05);
    }
    .month-selector-form {
      display: flex;
      align-items: end;
      gap: 12px;
    }
    .month-selector-form label {
      display: grid;
      gap: 6px;
    }
    .month-selector-form label span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .month-selector-form select {
      min-width: 160px;
      min-height: 38px;
      padding: 0 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      font: inherit;
    }
    .metadata-form {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 8px 22px rgba(31, 41, 51, 0.05);
    }
    .metadata-batch-bar {
      grid-template-columns: repeat(5, minmax(0, 1fr));
      margin: 0 0 12px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 8px 22px rgba(31, 41, 51, 0.05);
    }
    .metadata-form label,
    .metadata-batch-bar label {
      display: grid;
      gap: 6px;
    }
    .metadata-form label span,
    .metadata-batch-bar label span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .metadata-form select,
    .metadata-batch-bar select {
      width: 100%;
      min-height: 38px;
      padding: 0 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      font: inherit;
    }
    .form-actions {
      display: flex;
      align-items: end;
      gap: 10px;
    }
    .form-actions.compact {
      min-height: 100%;
    }
    .form-actions button {
      min-height: 40px;
      padding: 0 14px;
      border: 0;
      border-radius: 8px;
      background: var(--ink);
      color: #fff;
      font: inherit;
      font-weight: 800;
      cursor: pointer;
    }
    .form-actions button:hover {
      opacity: 0.94;
    }
    .inline-status-form {
      display: contents;
    }
    .inline-field {
      display: grid;
      gap: 6px;
    }
    .inline-field span {
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .inline-field select,
    .inline-field input {
      width: 100%;
      min-height: 36px;
      padding: 0 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      font: inherit;
    }
    code {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 13px;
      color: var(--ink);
    }
    @media (max-width: 760px) {
      main { width: min(100vw - 20px, 1040px); margin: 18px auto; }
      .hero { padding: 22px; border-radius: 14px; min-height: 0; }
      .hero h1 { font-size: 30px; }
      .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .metric-card strong { font-size: 20px; }
      .weekly-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .detail-chip { width: 100%; justify-content: space-between; border-radius: 8px; }
      .today-panel { grid-template-columns: 1fr; }
      .coach-desk-grid { grid-template-columns: 1fr; }
      .coach-desk-route-grid { grid-template-columns: 1fr; }
      .intelligence-panel { grid-template-columns: 1fr; }
      .intelligence-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .compact-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .weekly-review-grid { grid-template-columns: 1fr; }
      .shoe-kpi-grid { grid-template-columns: 1fr; }
      .training-kpi-grid { grid-template-columns: 1fr; }
      .briefing-evidence-grid { grid-template-columns: 1fr; }
      .state-sequence { grid-template-columns: 1fr; row-gap: 12px; column-gap: 0; }
      .state-node-wrap { min-width: 0; display: grid; grid-template-columns: 1fr; gap: 8px; }
      .state-connector { width: 2px; height: 16px; justify-self: center; margin: 0 auto; }
      .state-node-wrap.future-slot .state-connector { margin: 0 auto; }
      .journey-turning-points { grid-template-columns: 1fr; }
      .journey-session-grid { grid-template-columns: 1fr; }
      .metadata-form { grid-template-columns: 1fr; }
      .metadata-batch-bar { grid-template-columns: 1fr; }
      .scope-link-grid { grid-template-columns: 1fr; }
      .month-selector-bar { flex-direction: column; align-items: stretch; }
      .month-selector-form { width: 100%; }
    }
    """


def render_dashboard(activity_id="", page="home", edit_activity_id="", scope="unassigned", message="", month="", week=""):
    if not DB_PATH.exists():
        return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Running Intelligence Platform</title>
  <style>{base_styles()}</style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>Running Intelligence Platform</h1>
      <p>先匯入第一批跑步資料，平台才會開始整理出 Activity、Weekly、Monthly 與 Overview。</p>
    </section>
    {page_nav(page)}
    {message and f'<section class="status">{html.escape(message)}</section>' or ""}
    {no_data_yet_panel()}
    {rac_entry_panel()}
  </main>
</body>
</html>"""

    summary = None
    weekly = None
    intelligence = None
    weekly_rows = []
    week_rows = []
    selected_week = ""
    distribution_rows = []
    weekly_key_session_rows = []
    month_rows = []
    monthly = None
    selected_month = ""
    monthly_review = None
    monthly_memory = None
    monthly_rows = []
    monthly_distribution_rows = []
    monthly_progress_row = None
    monthly_key_session_rows = []
    monthly_related_week_rows = []
    monthly_assignment_quality_row = None
    journey_selected_story = None
    journey_timeline_rows = []
    journey_turning_rows = []
    training_balance_rows = []
    training_quality_row = None
    recent_training_rows = []
    shoe_rows = []
    shoe_status_data = []
    shoe_intelligence_rows = []
    shoe_workout_rows = []
    metadata_shoes = []
    metadata_workouts = []
    metadata_purposes = []
    metadata_rows = []
    metadata_selected = None
    metadata_scope_data = None
    recent = []
    activity_rows = []
    latest_activity = None
    selected = None
    split_rows = []
    today = None
    overview_attention = None

    with connect() as connection:
        summary = metrics(connection)

        if page == "weekly":
            all_week_rows = available_weeks(connection)
            week_rows = all_week_rows[:5]
            allowed_week_offsets = {str(row["week_offset"]) for row in week_rows}
            selected_week_request = str(week) if week not in ("", None) else None
            if selected_week_request and selected_week_request not in allowed_week_offsets:
                selected_week_request = None
            weekly = selected_week_summary(connection, selected_week_request or None)
            selected_week = str(weekly["week_offset"]) if weekly else (str(week_rows[0]["week_offset"]) if week_rows else "0")
            intelligence = selected_week_intelligence(connection, selected_week or None)
            weekly_rows = weekly_history(connection)[:5]
            distribution_rows = selected_week_distribution(connection, selected_week or None, limit=6)
            weekly_key_session_rows = selected_week_key_sessions(connection, selected_week or None)

        elif page == "activity":
            activity_rows = available_activities(connection)
            selected = selected_activity(connection, int(activity_id) if str(activity_id).isdigit() else None)
            split_rows = splits(connection, selected["activity_id"] if selected else None)
            weekly = week_summary(connection)
            intelligence = weekly_intelligence(connection)
            monthly = selected_month_summary(connection, None)
            monthly_review = selected_month_intelligence(connection, None)
            monthly_progress_row = selected_month_progress(connection, None)

        elif page == "journey":
            month_rows = available_months(connection)
            journey_selected_story = journey_story(connection, month or None)
            selected_month = str(journey_selected_story["month_key"]) if journey_selected_story else (str(month_rows[0]["month_key"]) if month_rows else "")
            monthly_memory = monthly_coach_memory(connection, selected_month or None)
            monthly_key_session_rows = selected_month_key_sessions(connection, selected_month or None)
            journey_timeline_rows = journey_timeline(connection)
            journey_turning_rows = journey_turning_points(connection, selected_month or None, limit=6)

        elif page == "monthly":
            month_rows = available_months(connection)
            monthly = selected_month_summary(connection, month or None)
            selected_month = str(monthly["month_key"]) if monthly else (str(month_rows[0]["month_key"]) if month_rows else "")
            monthly_review = selected_month_intelligence(connection, selected_month or None)
            monthly_memory = monthly_coach_memory(connection, selected_month or None)
            monthly_rows = monthly_history(connection)
            monthly_distribution_rows = selected_month_distribution(connection, selected_month or None, limit=8)
            monthly_progress_row = selected_month_progress(connection, selected_month or None)
            monthly_key_session_rows = selected_month_key_sessions(connection, selected_month or None)
            monthly_related_week_rows = selected_month_related_weeks(connection, selected_month or None, limit=5)
            monthly_assignment_quality_row = selected_month_assignment_quality(connection, selected_month or None)

        elif page == "shoes":
            shoe_rows = shoes_overview(connection)
            shoe_status_data = shoe_status_rows(connection)
            shoe_intelligence_rows = shoe_intelligence(connection)
            shoe_workout_rows = shoe_workout_comparison(connection, limit=12)

        elif page == "training":
            distribution_rows = training_distribution(connection, limit=6)
            training_balance_rows = training_balance(connection)
            training_quality_row = training_assignment_quality(connection)
            recent_training_rows = recent_training_intent(connection, limit=8)

        elif page == "metadata":
            _dropdown_options, metadata_shoes, metadata_workouts, metadata_purposes = metadata_choice_sets(connection)
            metadata_rows = metadata_candidates(connection, scope=scope, limit=60)
            training_quality_row = training_assignment_quality(connection)
            metadata_scope_data = metadata_scope_counts(connection)
            metadata_selected = metadata_activity(
                connection,
                int(edit_activity_id) if str(edit_activity_id).isdigit() else (metadata_rows[0]["activity_id"] if metadata_rows else 0),
            ) if (edit_activity_id or metadata_rows) else None

        else:
            weekly = week_summary(connection)
            intelligence = weekly_intelligence(connection)
            latest_activity = selected_activity(connection, None)
            monthly = selected_month_summary(connection, None)
            monthly_review = selected_month_intelligence(connection, None)
            monthly_progress_row = selected_month_progress(connection, None)
            journey_selected_story = journey_story(connection, None)
            today = coach_today(intelligence, latest_activity)
            overview_attention = overview_attention_payload(connection)

    weekly_review = weekly_review_payload(weekly, intelligence) if weekly and intelligence else None
    monthly_overview = monthly_overview_payload(monthly, monthly_review, monthly_progress_row) if monthly and monthly_review else None

    html_start = f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Running Intelligence Platform</title>
  <style>{base_styles()}</style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>Running Intelligence Platform</h1>
      <p>把治理後的跑步資料，整理成以教練視角出發的訓練回顧與判讀。</p>
    </section>

    {page_nav(page)}
"""
    message_html = f'<section class="status">{html.escape(message)}</section>' if message else ""

    if page == "weekly":
        return f"""{html_start}
    {weekly_selector_bar(week_rows, selected_week, "weekly")}
    {weekly_review_panel(weekly, intelligence, weekly_rows, distribution_rows, weekly_key_session_rows, selected_week)}
    {archive_metric_strip(summary)}
  </main>
</body>
</html>"""

    if page == "activity":
        return f"""{html_start}
    {activity_review_panel(selected, split_rows, activity_rows, selected["activity_id"] if selected else "", weekly_review, monthly_overview)}
    {archive_metric_strip(summary)}
  </main>
</body>
</html>"""

    if page == "journey":
        return f"""{html_start}
    {journey_page_panel(journey_selected_story, journey_timeline_rows, journey_turning_rows, month_rows, selected_month, monthly_memory, monthly_key_session_rows)}
    {archive_metric_strip(summary)}
  </main>
</body>
</html>"""

    if page == "monthly":
        return f"""{html_start}
    {monthly_review_panel(monthly, monthly_review, monthly_progress_row, monthly_assignment_quality_row, monthly_rows, monthly_distribution_rows, monthly_key_session_rows, monthly_related_week_rows, month_rows, selected_month, monthly_memory)}
  </main>
</body>
</html>"""

    if page == "shoes":
        return f"""{html_start}
    {shoes_page_panel(shoe_rows, shoe_intelligence_rows, shoe_workout_rows, shoe_status_data, message)}
    {archive_metric_strip(summary)}
  </main>
</body>
</html>"""

    if page == "training":
        return f"""{html_start}
    {training_page_panel(distribution_rows, training_balance_rows, training_quality_row, recent_training_rows)}
    {archive_metric_strip(summary)}
  </main>
</body>
</html>"""

    if page == "metadata":
        return f"""{html_start}
    {metadata_page_panel(
        metadata_rows,
        metadata_selected,
        metadata_shoes,
        metadata_workouts,
        metadata_purposes,
        training_quality_row,
        metadata_scope_data,
        scope,
        message,
    )}
    {archive_metric_strip(summary)}
  </main>
</body>
</html>"""

    return f"""{html_start}
    {message_html}
    {rac_entry_panel()}
    {coach_desk_panel(overview_attention, weekly_review, monthly_overview, monthly_review, journey_selected_story, latest_activity)}
    {archive_metric_strip(summary)}
  </main>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def send_html(self, content, status=200):
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_asset(self, path):
        try:
            resolved = path.resolve()
            asset_root = ASSETS_DIR.resolve()
            if not resolved.is_file() or not resolved.is_relative_to(asset_root):
                raise FileNotFoundError
            data = resolved.read_bytes()
        except (OSError, FileNotFoundError):
            self.send_html(render_dashboard(), status=404)
            return
        content_type = "image/png" if resolved.suffix.lower() == ".png" else "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/assets/"):
            self.send_asset(ASSETS_DIR / parsed.path.removeprefix("/assets/"))
            return
        if parsed.path == "/open-rac":
            if ensure_rac_running():
                self.redirect(f"http://{RAC_HOST}:{RAC_PORT}")
                return
            self.send_html(
                render_dashboard(
                    page="home",
                    message="資料匯入工具目前沒有成功啟動，請稍後再試一次。",
                ),
                status=503,
            )
            return
        query = parse_qs(parsed.query)
        page = (query.get("page") or ["home"])[0]
        if page not in {"home", "activity", "journey", "weekly", "monthly", "shoes", "training", "metadata"}:
            page = "home"
        self.send_html(
            render_dashboard(
                (query.get("activity") or [""])[0],
                page,
                (query.get("edit") or [""])[0],
                (query.get("scope") or ["unassigned"])[0],
                (query.get("message") or [""])[0],
                (query.get("month") or [""])[0],
                (query.get("week") or [""])[0],
            )
        )

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        form = parse_qs(self.rfile.read(length).decode("utf-8"))

        if parsed.path == "/shoes/add":
            try:
                shoe_name = append_shoe_option(first_form_value(form, "shoe_name"))
                with connect() as connection:
                    ensure_metadata_dimensions(connection, load_metadata_dropdown_options())
                    connection.commit()
                message = f"已新增鞋款：{shoe_name}"
            except ValueError as exc:
                message = str(exc)
            except Exception:
                message = "新增鞋款時出了點問題，請再試一次。"
            location = "/?" + urlencode(
                {
                    "page": "shoes",
                    "message": message,
                }
            )
            self.redirect(location)
            return

        if parsed.path == "/shoes/save-status":
            shoe_id = int(first_form_value(form, "shoe_id", "0") or "0")
            is_active = 1 if first_form_value(form, "is_active", "1") == "1" else 0
            retire_date = first_form_value(form, "retire_date", "").strip() or None

            with connect() as connection:
                connection.execute(
                    """
                    UPDATE shoe
                    SET
                        is_active = ?,
                        retire_date = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (is_active, retire_date, shoe_id),
                )
                connection.commit()

            location = "/?" + urlencode(
                {
                    "page": "shoes",
                    "message": "鞋款狀態已儲存",
                }
            )
            self.redirect(location)
            return

        if parsed.path == "/metadata/save":
            activity_id = int(first_form_value(form, "activity_id", "0") or "0")
            scope = first_form_value(form, "scope", "unassigned")
            shoe_code = first_form_value(form, "shoe_code")
            workout_code = first_form_value(form, "workout_type_code")
            primary_code = first_form_value(form, "primary_purpose_code")
            secondary_code = first_form_value(form, "secondary_purpose_code")

            with connect() as connection:
                update_single_activity_metadata(
                    connection,
                    activity_id,
                    shoe_code,
                    workout_code,
                    primary_code,
                    secondary_code,
                )
                connection.commit()

            location = "/?" + urlencode(
                {
                    "page": "metadata",
                    "edit": activity_id,
                    "scope": scope,
                    "message": "標註已儲存",
                }
            )
            self.redirect(location)
            return

        if parsed.path == "/metadata/batch":
            scope = first_form_value(form, "scope", "unassigned")
            activity_ids = [int(value) for value in form.get("activity_id", []) if str(value).isdigit()]
            shoe_code = first_form_value(form, "batch_shoe_code", "__KEEP__")
            workout_code = first_form_value(form, "batch_workout_type_code", "__KEEP__")
            primary_code = first_form_value(form, "batch_primary_purpose_code", "__KEEP__")
            secondary_code = first_form_value(form, "batch_secondary_purpose_code", "__KEEP__")

            with connect() as connection:
                updated = apply_batch_metadata_update(
                    connection,
                    activity_ids,
                    shoe_code,
                    workout_code,
                    primary_code,
                    secondary_code,
                )
                connection.commit()

            message = "尚未選取活動" if updated == 0 else f"已更新 {updated} 筆活動"
            location = "/?" + urlencode(
                {
                    "page": "metadata",
                    "scope": scope,
                    "message": message,
                }
            )
            self.redirect(location)
            return

        self.send_html(render_dashboard(page="metadata", message="Unsupported action"), status=400)

    def log_message(self, format, *args):
        return


def open_browser_later(url):
    timer = threading.Timer(0.6, lambda: webbrowser.open(url))
    timer.daemon = True
    timer.start()


def main():
    global DB_PATH
    parser = argparse.ArgumentParser(description="Run the Running Analytics dashboard.")
    parser.add_argument("db", nargs="?", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    DB_PATH = args.db
    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        open_browser_later(url)
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Running Intelligence Dashboard: {url}")
    print(f"SQLite database: {DB_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()
