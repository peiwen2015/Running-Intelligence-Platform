"""Rule-based Workout Sequence Intelligence for the first product vertical slice.

Rule changelog:
- rule-v1.0: Initial WSI rule engine for the Activity vertical slice.
- rule-v1.1: Exclude low-confidence WSI from period mission rollups; recognize
  Long Run / LSD / 長距離慢跑 as Build; allow tied dominant missions in product
  summaries.
"""

from __future__ import annotations

import json
from typing import Any, Mapping


WSI_ENGINE_VERSION = "rule-v1.1"

QUALITY_TOKENS = (
    "tempo",
    "threshold",
    "marathon",
    "interval",
    "vo2",
    "race",
    "progression",
    "fartlek",
    "repetition",
    "speed",
    "節奏",
    "閾值",
    "乳酸",
    "間歇",
    "馬拉松",
    "漸速",
)
LONG_RUN_TOKENS = ("long run", "lsd", "endurance", "長距離", "長跑", "耐力")
RECOVERY_TOKENS = ("recovery", "recover", "rest", "absorb", "恢復", "休息")
EASY_TOKENS = ("easy", "aerobic base", "base", "輕鬆", "有氧")
ACTIVATION_TOKENS = ("stride", "strides", "activate", "neuromuscular", "running economy", "啟動", "加速跑")
KEY_OBLIGATION_TOKENS = QUALITY_TOKENS + LONG_RUN_TOKENS


def _value(item: Mapping[str, Any] | None, key: str, default: Any = None) -> Any:
    if item is None:
        return default
    try:
        value = item[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def _text(item: Mapping[str, Any] | None, *keys: str) -> str:
    values = []
    for key in keys:
        value = _value(item, key)
        if value not in (None, ""):
            values.append(str(value).strip().lower())
    return " ".join(values)


def _contains(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dict_or_none(row) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _workout_structure_rows(connection, activity_id: int) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            """
            SELECT
                split_index,
                split_type,
                total_distance_m,
                total_timer_time_sec,
                avg_speed_mps
            FROM activity_workout_split
            WHERE activity_id = ?
            ORDER BY split_index
            """,
            (activity_id,),
        ).fetchall()
    ]


def _normalized_workout(item: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not item:
        return None
    text = _text(
        item,
        "workout_type_code",
        "workout_type_name_en",
        "workout_type_name_zh",
        "activity_type",
        "activity_name",
        "primary_training_purpose_code",
        "primary_training_purpose_name_en",
        "primary_training_purpose_name_zh",
    )
    label = (
        _value(item, "workout_type_name_zh")
        or _value(item, "workout_type_name_en")
        or _value(item, "activity_name")
        or _value(item, "activity_type")
        or "未標註活動"
    )
    has_training_label = any(
        _value(item, key)
        for key in (
            "workout_type_name_en",
            "workout_type_name_zh",
            "primary_training_purpose_name_en",
            "primary_training_purpose_name_zh",
            "activity_name",
        )
    )
    structure = _value(item, "workout_structure") or []
    structure_text = " ".join(str(row.get("split_type", "")) for row in structure if isinstance(row, Mapping)).lower()
    has_stride_segments = any(
        isinstance(row, Mapping)
        and "active" in str(row.get("split_type", "")).lower()
        and float(row.get("total_distance_m") or 0) < 300
        and float(row.get("total_timer_time_sec") or 0) <= 30
        for row in structure
    )
    return {
        "raw": item,
        "label": str(label),
        "text": f"{text} {structure_text}".strip(),
        "distance_km": _value(item, "distance_km"),
        "training_load": _value(item, "training_load"),
        "has_training_label": bool(has_training_label),
        "is_quality": bool(_value(item, "is_quality_session")) or _contains(text, QUALITY_TOKENS),
        "is_long_run": bool(_value(item, "is_long_run")) or _contains(text, LONG_RUN_TOKENS),
        "is_recovery": bool(_value(item, "is_recovery_focused")) or _contains(text, RECOVERY_TOKENS),
        "is_easy": _contains(text, EASY_TOKENS),
        "has_activation": has_stride_segments or _contains(f"{text} {structure_text}", ACTIVATION_TOKENS),
    }


def build_sequence_context(
    connection,
    activity_id: int,
    workout_structure: list[Mapping[str, Any]] | None = None,
    include_future: bool = False,
) -> dict[str, Any] | None:
    """Return the minimal context WSI needs, without exposing the database to the engine."""
    rows = connection.execute(
        """
        SELECT *
        FROM activity_review_view
        ORDER BY activity_start_time
        """
    ).fetchall()
    index = next((index for index, row in enumerate(rows) if int(row["activity_id"]) == int(activity_id)), None)
    if index is None:
        return None

    current = _dict_or_none(rows[index])
    if workout_structure is None:
        workout_structure = _workout_structure_rows(connection, activity_id)
    if workout_structure:
        current["workout_structure"] = [dict(row) for row in workout_structure]
    next_workout = _dict_or_none(rows[index + 1]) if include_future and index + 1 < len(rows) else None
    forward_context = [_dict_or_none(row) for row in rows[index + 2 : index + 4]] if include_future else []
    return {
        "previousWorkout": _dict_or_none(rows[index - 1]) if index > 0 else None,
        "currentWorkout": current,
        "nextWorkout": next_workout,
        "forwardContext": forward_context,
    }


def _quality_label(workout: dict[str, Any] | None, fallback: str = "下一堂關鍵課") -> str:
    return workout["label"] if workout else fallback


def _date_label(workout: dict[str, Any]) -> str:
    value = workout.get("raw", {}).get("activity_date") or workout.get("raw", {}).get("activity_start_time")
    if not value:
        return ""
    text = str(value)
    return text[:10]


def _workout_label(workout: dict[str, Any] | None) -> str:
    if not workout:
        return "未知活動"
    date_label = _date_label(workout)
    label = workout["label"]
    distance = _float_or_none(workout.get("distance_km"))
    distance_label = f"{distance:g} km" if distance is not None else ""
    prefix = f"{date_label} " if date_label else ""
    if workout.get("has_training_label"):
        suffix = f"（{distance_label}）" if distance_label else ""
        return f"{prefix}{label}{suffix}"
    load = _float_or_none(workout.get("training_load"))
    details = []
    if distance_label:
        details.append(distance_label)
    if load is not None:
        details.append(f"負荷 {load:g}")
    if details:
        return f"{prefix}{label}（{'，'.join(details)}）"
    if prefix:
        return f"{prefix}{label}"
    return label


def _has_key_obligation(workout: dict[str, Any] | None) -> bool:
    return bool(workout and (workout["is_quality"] or workout["is_long_run"] or _contains(workout["text"], KEY_OBLIGATION_TOKENS)))


def _is_unlabeled_primary_stimulus(workout: dict[str, Any]) -> bool:
    if workout.get("has_training_label"):
        return False
    load = _float_or_none(workout.get("training_load"))
    distance = _float_or_none(workout.get("distance_km"))
    return bool((load is not None and load >= 220) or (distance is not None and distance >= 14))


def _has_distinctive_evidence(workout: dict[str, Any]) -> bool:
    return bool(
        workout.get("has_training_label")
        or workout.get("is_quality")
        or workout.get("is_recovery")
        or workout.get("has_activation")
        or _is_unlabeled_primary_stimulus(workout)
    )


def _evidence_quality(current: dict[str, Any]) -> tuple[str, str]:
    if _has_distinctive_evidence(current):
        return "usable", "目前資料足以產生序列判讀。"
    return "needs_annotation", "這筆活動缺少課表類型或訓練目的，且距離、負荷或課表結構不夠有辨識度；建議先補標註再看 WSI。"


def _mission(context: dict[str, Any], previous, current, next_workout) -> tuple[str, str]:
    current_text = current["text"]
    next_has_key_obligation = _has_key_obligation(next_workout)
    previous_is_quality = bool(previous and previous["is_quality"])

    if current["is_quality"] and not current["is_recovery"]:
        return "Build", f"建立{current['label']}所需的能力刺激，同時保留後續連續性"

    if current["is_long_run"] and not current["is_recovery"]:
        return "Build", f"建立{current['label']}所需的耐力刺激，同時保留後續連續性"

    if _is_unlabeled_primary_stimulus(current):
        return "Build", "這堂雖然缺少課表標註，但距離或負荷已經像主刺激，應先視為建立能力的一天"

    if current["is_easy"] and current["has_activation"] and previous_is_quality:
        if next_workout and next_workout["is_recovery"]:
            return "Activate", "重新喚醒腿部轉換，讓品質課後的訓練節奏重新接上"

    if current["is_recovery"] or (
        current["is_easy"] and previous_is_quality and next_workout and next_workout["is_recovery"]
    ):
        return "Recover", "先吸收前一堂訓練刺激，讓恢復義務完成後再銜接下一步"

    if current["is_easy"] and next_has_key_obligation:
        if previous and (previous["is_recovery"] or "rest" in previous["text"]) and current["has_activation"]:
            return "Activate", f"重新喚醒腿部轉換，並為{_quality_label(next_workout)}保留可用入口"
        mechanism = "並保留必要的腿部轉換" if current["has_activation"] else ""
        return "Prepare", f"為{_quality_label(next_workout)}建立可用入口{mechanism}"

    if current["has_activation"]:
        return "Activate", "重新喚醒腿部轉換，讓訓練節奏重新接上"

    if _contains(current_text, RECOVERY_TOKENS):
        return "Recover", "整理目前訓練留下的負荷，讓後續序列保持可用"
    return "Prepare", "在目前序列中保留下一步訓練的可用入口"


def _mission_status(mission: str, current: dict[str, Any]) -> str:
    load = _float_or_none(current.get("training_load"))
    if load is None:
        return "Completed"
    if mission == "Prepare" and load >= 250:
        return "Partial"
    if mission == "Recover" and load >= 190:
        return "Partial"
    if mission == "Build" and load < 180:
        return "Partial"
    return "Completed"


def _continuity_state(mission: str, status: str, current, next_workout) -> str:
    if not next_workout:
        return "Maintained"
    next_has_key_obligation = _has_key_obligation(next_workout)
    load = _float_or_none(current.get("training_load"))
    if status == "Partial" and mission in {"Prepare", "Recover"}:
        return "Maintained"
    if mission == "Build":
        return "Maintained"
    if next_has_key_obligation and load is not None and load >= 260:
        return "Overloaded"
    if next_has_key_obligation and status == "Completed":
        return "Ready"
    return "Maintained"


MISSION_REASON_LABELS = {
    "Build": "建立能力",
    "Prepare": "準備下一堂",
    "Recover": "吸收恢復",
    "Activate": "重新啟動",
}

STATUS_REASON_LABELS = {
    "Completed": "已完成",
    "Partial": "部分完成",
}

CONTINUITY_REASON_LABELS = {
    "Ready": "已準備好",
    "Maintained": "維持住",
    "Overloaded": "負荷偏高",
}


def evaluate_wsi(sequence_context: Mapping[str, Any] | None) -> dict[str, str] | None:
    """Evaluate a context using the current validated WSI reasoning contract."""
    if not sequence_context or not sequence_context.get("currentWorkout"):
        return None
    previous = _normalized_workout(sequence_context.get("previousWorkout"))
    current = _normalized_workout(sequence_context.get("currentWorkout"))
    next_workout = _normalized_workout(sequence_context.get("nextWorkout"))
    mission, phrase = _mission(sequence_context, previous, current, next_workout)
    status = _mission_status(mission, current)
    continuity = _continuity_state(mission, status, current, next_workout)
    evidence_quality, evidence_note = _evidence_quality(current)

    mission_label = MISSION_REASON_LABELS.get(mission, mission)
    continuity_label = CONTINUITY_REASON_LABELS.get(continuity, continuity)
    reason_parts = [f"目前這堂課在序列中的主要角色是「{mission_label}」。"]
    if previous:
        reason_parts.append(f"前一堂是 {_workout_label(previous)}。")
    if next_workout:
        reason_parts.append(f"下一堂是 {_workout_label(next_workout)}，因此序列狀態目前判為「{continuity_label}」。")
    else:
        reason_parts.append("目前沒有足夠的後續課程資料，因此不過度宣告下一步狀態。")
    if status == "Partial":
        reason_parts.append("執行成本較高，先保留在「部分完成」，而不把這堂課的角色改寫成另一種任務。")

    return {
        "missionCategory": mission,
        "missionPhrase": phrase,
        "missionStatus": status,
        "continuityState": continuity,
        "sequenceReasoning": "".join(reason_parts),
        "evidenceQuality": evidence_quality,
        "evidenceNote": evidence_note,
    }


def ensure_activity_wsi_table(connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_wsi (
            activity_id INTEGER PRIMARY KEY,
            engine_version TEXT NOT NULL,
            mission_category TEXT NOT NULL,
            mission_phrase TEXT NOT NULL,
            mission_status TEXT NOT NULL,
            continuity_state TEXT NOT NULL,
            sequence_reasoning TEXT NOT NULL,
            evidence_quality TEXT NOT NULL DEFAULT 'usable',
            evidence_note TEXT NOT NULL DEFAULT '',
            context_json TEXT,
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(activity_id) REFERENCES activity(id) ON DELETE CASCADE
        )
        """
    )
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(activity_wsi)").fetchall()}
    if "evidence_quality" not in columns:
        connection.execute("ALTER TABLE activity_wsi ADD COLUMN evidence_quality TEXT NOT NULL DEFAULT 'usable'")
    if "evidence_note" not in columns:
        connection.execute("ALTER TABLE activity_wsi ADD COLUMN evidence_note TEXT NOT NULL DEFAULT ''")


def get_activity_wsi(connection, activity_id: int) -> dict[str, str] | None:
    ensure_activity_wsi_table(connection)
    row = connection.execute(
        """
        SELECT
            mission_category,
            mission_phrase,
            mission_status,
            continuity_state,
            sequence_reasoning,
            evidence_quality,
            evidence_note,
            context_json
        FROM activity_wsi
        WHERE activity_id = ?
        """,
        (activity_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "missionCategory": row["mission_category"],
        "missionPhrase": row["mission_phrase"],
        "missionStatus": row["mission_status"],
        "continuityState": row["continuity_state"],
        "sequenceReasoning": row["sequence_reasoning"],
        "evidenceQuality": row["evidence_quality"],
        "evidenceNote": row["evidence_note"],
        "context": json.loads(row["context_json"]) if row["context_json"] else None,
    }


def save_activity_wsi(connection, activity_id: int, wsi: Mapping[str, str], context: Mapping[str, Any] | None = None) -> None:
    ensure_activity_wsi_table(connection)
    context_json = json.dumps(context, ensure_ascii=False, default=str) if context else None
    connection.execute(
        """
        INSERT INTO activity_wsi (
            activity_id,
            engine_version,
            mission_category,
            mission_phrase,
            mission_status,
            continuity_state,
            sequence_reasoning,
            evidence_quality,
            evidence_note,
            context_json,
            generated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(activity_id) DO UPDATE SET
            engine_version = excluded.engine_version,
            mission_category = excluded.mission_category,
            mission_phrase = excluded.mission_phrase,
            mission_status = excluded.mission_status,
            continuity_state = excluded.continuity_state,
            sequence_reasoning = excluded.sequence_reasoning,
            evidence_quality = excluded.evidence_quality,
            evidence_note = excluded.evidence_note,
            context_json = excluded.context_json,
            generated_at = CURRENT_TIMESTAMP
        """,
        (
            activity_id,
            WSI_ENGINE_VERSION,
            wsi["missionCategory"],
            wsi["missionPhrase"],
            wsi["missionStatus"],
            wsi["continuityState"],
            wsi["sequenceReasoning"],
            wsi.get("evidenceQuality", "usable"),
            wsi.get("evidenceNote", ""),
            context_json,
        ),
    )


def recompute_activity_wsi(connection, activity_id: int, include_future: bool = True) -> dict[str, str] | None:
    context = build_sequence_context(connection, activity_id, include_future=include_future)
    wsi = evaluate_wsi(context)
    if not wsi:
        return None
    save_activity_wsi(connection, activity_id, wsi, context)
    return wsi


def recompute_all_activity_wsi(connection, month: str | None = None) -> dict[str, Any]:
    ensure_activity_wsi_table(connection)
    params: tuple[Any, ...] = ()
    where_sql = ""
    if month:
        where_sql = "WHERE activity_date LIKE ?"
        params = (f"{month}-%",)
    rows = connection.execute(
        f"""
        SELECT activity_id
        FROM activity_review_view
        {where_sql}
        ORDER BY activity_start_time
        """,
        params,
    ).fetchall()
    counts = {"total": len(rows), "updated": 0, "missing": 0, "missions": {}}
    mission_counts: dict[str, int] = {}
    for row in rows:
        wsi = recompute_activity_wsi(connection, int(row["activity_id"]))
        if not wsi:
            counts["missing"] += 1
            continue
        counts["updated"] += 1
        mission = wsi["missionCategory"]
        mission_counts[mission] = mission_counts.get(mission, 0) + 1
    counts["missions"] = mission_counts
    return counts
