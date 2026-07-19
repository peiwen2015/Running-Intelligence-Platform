#!/usr/bin/env python3
from __future__ import annotations

import io
import argparse
import hashlib
import html
import mimetypes
import json
import re
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import webbrowser
from collections import Counter
from functools import lru_cache
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

try:
    from semantic_layer import ensure_semantic_layer
except ModuleNotFoundError:
    from analysis_platform.semantic_layer import ensure_semantic_layer

try:
    from attention_selection_shadow import evaluate_candidates, live_signals, rank_candidates
except ModuleNotFoundError:
    from analysis_platform.attention_selection_shadow import evaluate_candidates, live_signals, rank_candidates

try:
    from wsi_engine import ensure_activity_wsi_table, get_activity_wsi, recompute_activity_wsi
except ModuleNotFoundError:
    from analysis_platform.wsi_engine import ensure_activity_wsi_table, get_activity_wsi, recompute_activity_wsi


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
DEFAULT_DB_PATH = ROOT / "running_analytics.sqlite"
ASSETS_DIR = PROJECT_ROOT / "assets"
COACHOS_LOGO_DARK = "coachos_logo_dark.png"
COACHOS_WORDMARK = "coachos_wordmark.png"
COACHOS_TRANSPARENT_LOGO = "coachos_logo_transparent.png"
COACHOS_BANNER = "coachos_banner.png"
COACHOS_LOGO = "coachos_logo.png"
COACHOS_JOURNEY = "journey.png"
CONFIG_PATH = PROJECT_ROOT / "config" / "dropdown_options.json"
AI_REPLY_STORE_PATH = PROJECT_ROOT / "config" / "local_ai_replies.json"
AI_REPLIES_DIR = PROJECT_ROOT / "AI_REPLIES"
RAC_APP_PATH = PROJECT_ROOT / "app.py"
RAC_HOST = "127.0.0.1"
RAC_PORT = 8765
RAC_LOG_PATH = PROJECT_ROOT / "tmp" / "rac_server.log"
HOST = "127.0.0.1"
PORT = 8766
DB_PATH = DEFAULT_DB_PATH
DROPDOWN_SOURCE_TABLE = "dropdown_source"
FEEDBACK_DICTIONARY_TABLE = "feedback_dictionary_option"

ACTIVITY_METADATA_PROVENANCE_TABLE = "activity_metadata_provenance"
LEGACY_SHOE_FILL_CUTOFF = "2026-07-10T00:00:00"

ACTIVITY_METADATA_PROVENANCE_LABELS = {
    "manual": "你手動標的",
    "coach_knowledge": "CoachOS 學會的",
    "coach_memory_auto_fill": "CoachOS 先前補的",
    "legacy_unknown": "來源待確認",
}

FEEDBACK_DICTIONARY_LABELS = {
    "garmin_rpe": "感受難度",
    "garmin_feel": "感覺如何",
}

FEEDBACK_DICTIONARY_PLACEHOLDERS = {
    "garmin_rpe": "例如 1 - 非常輕鬆",
    "garmin_feel": "例如 普通",
}

FEEDBACK_DICTIONARY_FALLBACKS = {
    "garmin_rpe": [
        "1 - 非常輕鬆",
        "2 - 輕鬆",
        "3 - 中等",
        "4 - 有點難",
        "5 - 困難",
        "6 - 困難",
        "7 - 非常困難",
        "8 - 非常困難",
        "9 - 超級難",
        "10 - 極限",
    ],
    "garmin_feel": [
        "非常弱",
        "弱",
        "普通",
        "強",
        "非常強",
    ],
}

FEEDBACK_DICTIONARY_SEED_PATH = ROOT / "feedback_dictionary_seed.json"


def _load_feedback_dictionary_seed():
    defaults = {key: list(value) for key, value in FEEDBACK_DICTIONARY_FALLBACKS.items()}
    if not FEEDBACK_DICTIONARY_SEED_PATH.exists():
        return defaults
    try:
        loaded = json.loads(FEEDBACK_DICTIONARY_SEED_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    if isinstance(loaded, dict):
        for key in defaults:
            values = loaded.get(key)
            if isinstance(values, list):
                cleaned = [str(item).strip() for item in values if str(item).strip()]
                if cleaned:
                    defaults[key] = cleaned
    return defaults


FEEDBACK_DICTIONARY_DEFAULTS = _load_feedback_dictionary_seed()

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
    "workout_focus_map": {},
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

WORKOUT_PURPOSE_DEFAULTS = {
    "recovery_run": ("recovery", "maintenance"),
    "easy_run": ("aerobic_base", "maintenance"),
    "easy_run_strides": ("aerobic_base", "neuromuscular"),
    "lsd": ("endurance", "aerobic_base"),
    "progressive_lsd": ("endurance", "race_specific"),
    "long_run": ("endurance", "aerobic_base"),
    "marathon_pace": ("race_specific", "threshold"),
    "tempo_run": ("threshold", "race_specific"),
    "cruise_interval": ("threshold", "race_specific"),
    "interval": ("vo2max", "speed"),
    "repetition": ("speed", "neuromuscular"),
    "fartlek": ("speed", "running_economy"),
    "race": ("race", "race_specific"),
    "progression_run": ("endurance", "race_specific"),
    "other": ("maintenance", None),
}

WORKOUT_INTENSITY_LABELS_ZH = {
    "Quality": "高強度",
    "Easy": "輕鬆",
    "Recovery": "恢復",
    "Moderate": "中等",
    "Race": "比賽",
    "Endurance": "耐力",
    "Threshold": "閾值",
    "VO2max": "VO2max",
    "Speed": "速度",
    "Technique": "技術",
    "Environmental": "環境",
    "Maintenance": "維持",
}

PURPOSE_CATEGORY_LABELS_ZH = {
    "Recovery": "恢復",
    "Aerobic": "有氧",
    "Endurance": "耐力",
    "Race": "比賽",
    "Threshold": "閾值",
    "VO2max": "VO2max",
    "Speed": "速度",
    "Technique": "技術",
    "Environmental": "環境",
    "Maintenance": "維持",
}

WORKOUT_INTENSITY_OPTIONS = [
    ("Recovery", "恢復"),
    ("Easy", "輕鬆"),
    ("Moderate", "中等"),
    ("Endurance", "耐力"),
    ("Race", "比賽"),
    ("Threshold", "閾值"),
    ("VO2max", "VO2max"),
    ("Speed", "速度"),
    ("Technique", "技術"),
    ("Environmental", "環境"),
    ("Maintenance", "維持"),
    ("Quality", "高強度"),
]

PURPOSE_CATEGORY_OPTIONS = [
    ("Recovery", "恢復"),
    ("Aerobic", "有氧"),
    ("Endurance", "耐力"),
    ("Race", "比賽"),
    ("Threshold", "閾值"),
    ("VO2max", "VO2max"),
    ("Speed", "速度"),
    ("Technique", "技術"),
    ("Environmental", "環境"),
    ("Maintenance", "維持"),
]

SHOE_CATEGORY_OPTIONS = [
    ("Daily Trainer", "Daily Trainer"),
    ("Recovery", "Recovery"),
    ("Long Run", "Long Run"),
    ("Tempo", "Tempo"),
    ("Speed", "Speed / Interval"),
    ("Race", "Race"),
    ("Trail", "Trail"),
    ("Treadmill", "Treadmill"),
    ("Other", "Other"),
]

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


def format_duration_hms(seconds):
    if value_is_blank(seconds):
        return ""
    try:
        total = int(round(float(seconds)))
    except (TypeError, ValueError):
        return ""
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


def load_ai_reply_store():
    try:
        return json.loads(AI_REPLY_STORE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_ai_reply_store(payload):
    AI_REPLY_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    AI_REPLY_STORE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def extract_ai_reply_markdown(text):
    raw = (text or "").strip()
    if not raw:
        return ""

    tagged_patterns = [
        r"```running-intelligence-reply\s*\n(.*?)```",
        r"```markdown\s*\n(.*?)```",
        r"```md\s*\n(.*?)```",
    ]
    for pattern in tagged_patterns:
        matches = re.findall(pattern, raw, flags=re.IGNORECASE | re.DOTALL)
        if matches:
            return matches[-1].strip()

    generic_blocks = re.findall(r"```[a-zA-Z0-9_-]*\s*\n(.*?)```", raw, flags=re.DOTALL)
    if generic_blocks:
        return generic_blocks[-1].strip()
    return raw


def detect_ai_reply_parse_mode(text):
    raw = (text or "").strip()
    if not raw:
        return "empty"
    tagged_patterns = [
        r"```running-intelligence-reply\s*\n(.*?)```",
        r"```markdown\s*\n(.*?)```",
        r"```md\s*\n(.*?)```",
    ]
    for index, pattern in enumerate(tagged_patterns):
        matches = re.findall(pattern, raw, flags=re.IGNORECASE | re.DOTALL)
        if matches:
            return "tagged" if index == 0 else "markdown"
    generic_blocks = re.findall(r"```[a-zA-Z0-9_-]*\s*\n(.*?)```", raw, flags=re.DOTALL)
    if generic_blocks:
        return "generic"
    return "raw"


def markdown_inline(text):
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
    return escaped


def render_simple_markdown(markdown_text):
    text = (markdown_text or "").strip()
    if not text:
        return ""

    blocks = []
    list_items = []

    def flush_list():
        nonlocal list_items
        if list_items:
            blocks.append("<ul>" + "".join(f"<li>{item}</li>" for item in list_items) + "</ul>")
            list_items = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            flush_list()
            continue
        if stripped.startswith("### "):
            flush_list()
            blocks.append(f"<h5>{markdown_inline(stripped[4:])}</h5>")
        elif stripped.startswith("## "):
            flush_list()
            blocks.append(f"<h4>{markdown_inline(stripped[3:])}</h4>")
        elif stripped.startswith("# "):
            flush_list()
            blocks.append(f"<h3>{markdown_inline(stripped[2:])}</h3>")
        elif stripped.startswith("- "):
            list_items.append(markdown_inline(stripped[2:]))
        else:
            flush_list()
            blocks.append(f"<p>{markdown_inline(stripped)}</p>")
    flush_list()
    return "".join(blocks)


def build_ai_reply_key(surface, identifier):
    return f"{surface}:{identifier}"


def slugify_ai_reply_part(value):
    text = str(value or "").strip()
    if not text:
        return "unknown"
    text = text.replace(":", "__")
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_.")
    return text or "unknown"


def ai_reply_scope_dir(surface):
    return AI_REPLIES_DIR / slugify_ai_reply_part(surface)


def ai_reply_file_stem(surface, identifier):
    return f"{slugify_ai_reply_part(surface)}__{slugify_ai_reply_part(identifier)}"


def ai_reply_paths(surface, identifier):
    folder = ai_reply_scope_dir(surface)
    stem = ai_reply_file_stem(surface, identifier)
    return folder / f"{stem}.json", folder / f"{stem}.md"


def ai_reply_attachment_dir(surface, identifier):
    return ai_reply_scope_dir(surface) / slugify_ai_reply_part(identifier) / "attachments"


def ai_reply_attachment_url(surface, identifier, filename):
    return "/ai-replies-file?" + urlencode(
        {
            "surface": surface,
            "identifier": identifier,
            "filename": filename,
        }
    )


def sanitize_uploaded_filename(filename):
    name = Path(str(filename or "").strip()).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("._")
    return name or "image"


def list_ai_reply_attachments(surface, identifier):
    folder = ai_reply_attachment_dir(surface, identifier)
    if not folder.exists():
        return []
    items = []
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}:
            continue
        stat = path.stat()
        items.append(
            {
                "filename": path.name,
                "url": ai_reply_attachment_url(surface, identifier, path.name),
                "size": stat.st_size,
                "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            }
        )
    return items


def save_ai_reply_attachment(surface, identifier, uploaded_file):
    original_name = getattr(uploaded_file, "filename", "") or "image"
    file_data = uploaded_file.file.read() if getattr(uploaded_file, "file", None) else b""
    if not file_data:
        raise ValueError("上傳的圖檔是空的。")

    folder = ai_reply_attachment_dir(surface, identifier)
    folder.mkdir(parents=True, exist_ok=True)

    stem = sanitize_uploaded_filename(Path(original_name).stem)
    suffix = sanitize_uploaded_filename(Path(original_name).suffix).lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}:
        suffix = ".png"
    digest = hashlib.sha1(file_data).hexdigest()[:10]
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_{digest}_{stem}{suffix}"
    target = folder / filename
    target.write_bytes(file_data)
    return filename


def delete_ai_reply_attachment(surface, identifier, filename):
    target = ai_reply_attachment_dir(surface, identifier) / Path(str(filename or "")).name
    resolved = target.resolve()
    root = AI_REPLIES_DIR.resolve()
    if not resolved.is_file() or not resolved.is_relative_to(root):
        raise FileNotFoundError
    resolved.unlink()
    return resolved.name


def render_ai_reply_attachments(surface, identifier, page="", activity_id="", week="", month=""):
    attachments = list_ai_reply_attachments(surface, identifier)
    if not attachments:
        return '<p class="note">目前還沒有附加圖檔。</p>'

    cards = []
    for item in attachments:
        hidden_fields = [
            ("surface", surface),
            ("identifier", identifier),
            ("filename", item["filename"]),
            ("page", page),
            ("activity_id", activity_id),
            ("week", week),
            ("month", month),
        ]
        cards.append(
            f"""
            <figure class="ai-attachment-card">
              <a href="{html.escape(item['url'], quote=True)}" target="_blank" rel="noreferrer">
                <img src="{html.escape(item['url'], quote=True)}" alt="{html.escape(item['filename'])}">
              </a>
              <figcaption>
                <span>{html.escape(item['updated_at'].replace('T', ' '))}</span>
                <form method="post" action="/ai-replies/delete-image" class="ai-attachment-delete-form remember-scroll-form">
                  {"".join(f'<input type="hidden" name="{html.escape(name, quote=True)}" value="{html.escape(value, quote=True)}">' for name, value in hidden_fields if value)}
                  <input type="hidden" name="scroll_y" value="">
                  <button class="secondary-action ai-attachment-delete-button" type="submit">刪除這張</button>
                </form>
              </figcaption>
            </figure>
            """
        )
    return f'<div class="ai-attachment-gallery">{"".join(cards)}</div>'


def normalize_ai_reply_record(record):
    if not isinstance(record, dict):
        return None
    markdown = record.get("responseMarkdown")
    if markdown is None:
        markdown = record.get("markdown", "")
    created_at = record.get("createdAt") or record.get("saved_at") or ""
    updated_at = record.get("updatedAt") or record.get("saved_at") or created_at
    return {
        "analysisNodeId": record.get("analysisNodeId") or record.get("identifier") or "",
        "scope": record.get("scope") or record.get("surface") or "",
        "provider": record.get("provider") or "external-ai",
        "model": record.get("model"),
        "promptVersion": record.get("promptVersion") or "handoff-v1.1",
        "responseMarkdown": markdown or "",
        "markdown": markdown or "",
        "createdAt": created_at,
        "updatedAt": updated_at,
        "title": record.get("title") or "AI 回覆",
    }


def load_ai_reply_from_files(surface, identifier):
    meta_path, markdown_path = ai_reply_paths(surface, identifier)
    if not meta_path.exists():
        return None
    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    markdown = ""
    if markdown_path.exists():
        try:
            markdown = markdown_path.read_text(encoding="utf-8")
        except OSError:
            markdown = ""
    if markdown:
        metadata["responseMarkdown"] = markdown
        metadata["markdown"] = markdown
    return normalize_ai_reply_record(metadata)


def get_ai_reply(surface, identifier):
    file_record = load_ai_reply_from_files(surface, identifier)
    if file_record:
        return file_record
    store = load_ai_reply_store()
    return normalize_ai_reply_record(store.get(build_ai_reply_key(surface, identifier)))


def save_ai_reply(surface, identifier, title, raw_text):
    markdown = extract_ai_reply_markdown(raw_text)
    existing = get_ai_reply(surface, identifier) or {}
    now = datetime.now().isoformat(timespec="seconds")
    record = {
        "analysisNodeId": identifier,
        "scope": surface,
        "provider": "external-ai",
        "model": None,
        "promptVersion": "handoff-v1.1",
        "createdAt": existing.get("createdAt") or now,
        "updatedAt": now,
        "title": title,
    }
    meta_path, markdown_path = ai_reply_paths(surface, identifier)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(markdown.strip() + "\n", encoding="utf-8")
    record["markdownFile"] = markdown_path.name
    meta_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return markdown


class UploadedFormFile:
    def __init__(self, filename, content, content_type="application/octet-stream"):
        self.filename = filename
        self.file = io.BytesIO(content)
        self.content_type = content_type


def parse_multipart_form_data(body, content_type):
    if not content_type or "multipart/form-data" not in content_type:
        return {}

    boundary_match = re.search(r'boundary=("?)([^";]+)\1', content_type)
    if not boundary_match:
        return {}

    boundary = boundary_match.group(2).encode("utf-8")
    delimiter = b"--" + boundary
    form = {}

    for chunk in body.split(delimiter):
        chunk = chunk.strip()
        if not chunk or chunk == b"--":
            continue
        if chunk.endswith(b"--"):
            chunk = chunk[:-2].strip()
        header_blob, separator, data = chunk.partition(b"\r\n\r\n")
        if not separator:
            continue

        headers = {}
        for line in header_blob.split(b"\r\n"):
            if b":" not in line:
                continue
            name, value = line.split(b":", 1)
            headers[name.strip().lower()] = value.strip()

        disposition = headers.get(b"content-disposition", b"").decode("utf-8", errors="replace")
        field_match = re.search(r'name="([^"]+)"', disposition)
        if not field_match:
            continue
        field_name = field_match.group(1)
        filename_match = re.search(r'filename="([^"]*)"', disposition)
        value = data.rstrip(b"\r\n")

        if filename_match:
            uploaded = UploadedFormFile(
                filename_match.group(1),
                value,
                headers.get(b"content-type", b"application/octet-stream").decode("utf-8", errors="replace"),
            )
            form.setdefault(field_name, []).append(uploaded)
        else:
            form.setdefault(field_name, []).append(value.decode("utf-8", errors="replace"))

    return form


def ai_handoff_response_format_instructions():
    return [
        "## 回覆格式",
        "- 你的回覆必須包含兩個連續部分。",
        "- 第一部分：直接用一般 markdown 正常回答，不要加入「第一部分」、「閱讀版」或其他格式說明。",
        "- 第二部分：在閱讀內容結束後，再輸出一份完全相同、可貼回平台保存的 markdown。",
        "- 第二部分必須放進單一 fenced code block，並優先使用 ```running-intelligence-reply；若不方便，至少使用 ```markdown。",
        "- code block 內只能包含最終回答內容，不得加入前言、操作說明、JSON、HTML、資料來源說明或額外註解，也不得在框內再次建立 fenced code block。",
        "- 請固定使用以下結構：",
        "- `# 整體判讀`",
        "- `## 平台判讀依據`",
        "- `## AI 額外觀察`",
        "- `## 判讀衝突`",
        "- `## 下一步提醒`",
        "- 若沒有額外觀察，請寫「沒有需要額外補充的明顯訊號」。",
        "- 若沒有衝突，請寫「未發現原始資料與平台判讀之間有明顯衝突」。",
        "- 下一步提醒只能提供一個。",
    ]


def append_previous_ai_response(prompt_lines, existing_reply):
    if not existing_reply or not existing_reply.get("responseMarkdown"):
        return
    prompt_lines.extend(
        [
            "",
            "## 先前的 AI 回覆",
            "以下內容是使用者先前保存的 AI 延伸分析。",
            "它只能作為討論脈絡，不是平台治理事實，也不能用來覆蓋活動事實、教練理解、推理、關鍵片段、上下文或證據。",
            "如果舊回覆中的內容無法由本次平台資料支持，請把它視為先前推測，不要延續為既定事實。",
            existing_reply["responseMarkdown"],
        ]
    )


def coach_prompt_reference_lines(surface_label, primary_output, analysis_outline, standard_inputs, rules, extra_notes=None):
    lines = [
        "## Prompt Reference",
        f"- 系統定位：{surface_label} 不是一次性分析 Prompt，而是可長期維護的個人跑步資料分析規格。",
        f"- 主要輸出：{primary_output}",
        "- 分析層次：單次訓練＋週期狀態＋長期趨勢",
        "- 語言：繁體中文",
        "- 風格：專業、清楚、教練式、避免過度碎片化短句",
    ]
    if standard_inputs:
        lines.extend(["", "### 標準輸入"])
        lines.extend([f"- {item}" for item in standard_inputs if item])
    if analysis_outline:
        lines.extend(["", "### 建議架構"])
        lines.extend([f"{index}. {item}" for index, item in enumerate(analysis_outline, 1) if item])
    if rules:
        lines.extend(["", "### 判讀原則"])
        lines.extend([f"- {item}" for item in rules if item])
    if extra_notes:
        lines.extend(["", "### 補充提醒"])
        lines.extend([f"- {item}" for item in extra_notes if item])
    return lines


def activity_daily_training_card_prompt(
    activity,
    review,
    split_rows=None,
    workout_split_rows=None,
    weekly_review=None,
    monthly_overview=None,
    saved_reply=None,
):
    if not activity or not review:
        return ""

    def raw_text(value, fallback="—"):
        if value is None:
            return fallback
        text = str(value).strip()
        return text if text else fallback

    def activity_value(key, fallback=None):
        try:
            value = activity[key]
        except (KeyError, IndexError, TypeError):
            return fallback
        return fallback if value is None else value

    activity_date = str(activity["activity_start_time"]).replace("T", " ")[:10].replace("-", "/")
    activity_name = str(activity["activity_name"] or activity["activity_type"] or "活動")
    workout_text = str(activity["workout_type_name_en"] or activity["activity_type"] or "未標註")
    purpose_text = str(activity["primary_training_purpose_name_en"] or "未標註")
    shoe_text = str(activity["shoe_display_name"] or "未標註")
    location_text = raw_text(
        activity_value("location")
        or activity_value("activity_location")
        or activity_value("place")
    )
    if location_text == "—":
        location_text = ""
    if not location_text and activity_value("start_latitude") is not None and activity_value("start_longitude") is not None:
        location_text = reverse_geocode_location_label_concise(activity_value("start_latitude"), activity_value("start_longitude"))
    if not location_text and activity_value("end_latitude") is not None and activity_value("end_longitude") is not None:
        location_text = reverse_geocode_location_label_concise(activity_value("end_latitude"), activity_value("end_longitude"))
    if not location_text and activity_value("start_latitude") is not None and activity_value("start_longitude") is not None:
        location_text = f"{format_number(activity_value('start_latitude'), 5)}, {format_number(activity_value('start_longitude'), 5)}"
    if not location_text:
        location_text = "未提供"
    activity_distance_text = f"{format_number(activity['distance_km'], 2)} km"
    duration_text = format_duration_hms(activity["duration_sec"]) or "—"
    pace_text = format_pace_seconds(activity["avg_pace_sec_per_km"]) or "—"
    hr_text = "" if activity["avg_hr"] is None else str(int(round(activity["avg_hr"])))
    power_value = activity_value("avg_power_w")
    power_text = "" if power_value is None else format_number(power_value, 0)
    load_text = format_number(activity["training_load"], 0) or "—"
    recovery_text = raw_text(activity["recovery_time_hr"])
    cause_lines = [f"- {card['title']}：{card['value']}；{card['note']}" for card in review.get("cards", [])]
    segment_lines = []
    for row in activity_key_segments(activity, split_rows or [], workout_split_rows or []):
        segment_lines.append(
            f"- {row['label']}（{row['section']}）：{row['metric']}；{row['note']}"
        )
    workout_structure_lines = []
    for row in display_workout_splits(workout_split_rows or []):
        segment_type = workout_display_label(row, workout_split_rows or [])
        workout_distance_text = (
            f"{format_number((row['total_distance_m'] or 0) / 1000, 2)} km"
            if (row["total_distance_m"] or 0) >= 1000
            else f"{format_number(row['total_distance_m'], 0)} m"
        )
        time_text = format_duration_hms(row["total_timer_time_sec"]) or "—"
        pace_value = None if row["avg_speed_mps"] in (None, 0) else 1000.0 / float(row["avg_speed_mps"])
        pace_label = format_pace_seconds(pace_value) or "—"
        workout_structure_lines.append(
            f"- 片段 {row['split_index']}：{segment_type}，{workout_distance_text}，{time_text}，配速 {pace_label}"
        )
    has_previous_ai_reply = bool(saved_reply and saved_reply.get("responseMarkdown"))

    prompt_lines = [
        "請把以下跑步分析資料整理成一張可直接發布的每日訓練圖卡內容。",
        "輸出目標：16:9 橫式 Facebook 圖卡，深藍／藍灰科技感背景，專業、清楚、乾淨，接近 Garmin Connect + Runalyze 的資訊設計感。",
        "請不要畫成可愛風、漫畫風，也不要加入未提供的跑者故事、心情、身體狀態或訓練背景。",
        "若資料不足，請明確寫「未提供」或保守處理，不要自行猜測。",
        "請把內容整理成真正適合放進圖卡的文案與區塊，不要只是把欄位逐條重貼。",
        "請固定使用以下圖卡架構：1. 今日摘要 2. 課表完成度 3. 配速策略 4. 心肺負荷 5. 功率與跑步經濟性 6. 體力 7. Garmin 指標 8. 教練判斷 9. 下一步建議。",
        "",
        "## 產出要求",
        "- 每個區塊請用可上卡的短文案呈現，不要寫成長篇報告。",
        "- 整體語氣要像專業跑步教練，不要像資料庫或系統說明。",
        "- 若課表片段表存在，請先用它理解主體課程，再用原始分段補證據。",
        "- 不要把 warm-up、recovery、stride、cool-down 誤寫成今天的主體刺激。",
        "- 最後請補一行適合放在卡片底部的收尾句。",
        "",
        "## 今日摘要",
        f"- 標題：今日跑步分析",
        f"- 日期：{activity_date}",
        f"- 地點：{location_text}",
        f"- 鞋款：{shoe_text}",
        f"- 課表類型 / 訓練目的：{workout_text} / {purpose_text}",
        f"- 核心數據：距離 {activity_distance_text}，時間 {duration_text}，平均配速 {pace_text}，平均心率 {hr_text or '—'}，平均功率 {power_text or '—'}，訓練負荷 {load_text}，恢復時間 {recovery_text}",
        "",
        "## 平台已整理的教練判讀",
        f"- 這堂課先回答的問題：{review.get('learning_question', '—')}",
        f"- 學習：{review.get('learning', '請根據資料分析前後段配速與是否符合目的。')}",
        f"- 焦點：{review.get('focus', '請整理這堂課真正留下來的是什麼。')}",
        f"- 原因：{review.get('why', '請根據資料分析心率變化、漂移與環境影響。')}",
        f"- 下一步：{review.get('looking_forward', '請根據資料分析步頻、步幅、接地時間與垂直振幅。')}",
        "",
        "## 圖卡要強調的三件事",
        f"- 配速策略：{review.get('learning', '請根據資料分析前後段配速與是否符合目的。')}",
        f"- 身體反應：{review.get('why', '請根據資料分析心率變化、漂移與環境影響。')}",
        f"- 下一步方向：{review.get('looking_forward', '請根據資料分析步頻、步幅、接地時間與垂直振幅。')}",
        "",
        "## 課表結構與證據使用規則",
        "- 若有課表片段表，請優先把 WU / Main / Recovery / CD 當成主結構來理解今天這堂課。",
        "- 原始分段只能拿來補充證據，不要把 recovery、stride 或 cool-down 誤當成主體刺激。",
        "- 如果平台判讀與你從資料看到的內容有落差，請保守處理，避免寫成過度確定的句子。",
        "",
        "## 卡片中的教練建議",
        f"- 恢復或下一堂課建議：{weekly_review.get('looking_forward') if weekly_review and weekly_review.get('looking_forward') else (monthly_overview.get('looking_forward') if monthly_overview and monthly_overview.get('looking_forward') else '請依今天的訓練刺激給出恢復或下一堂課建議。')}",
        "",
        "## 收尾句",
        "- 請用一句短而有教練感的結論文字收尾，像是今天真正留下來的是什麼，或明天會因此更懂什麼。",
        "",
        "## 風格要求",
        "- 繁體中文",
        "- 精簡、專業",
        "- 不要塞太多小字",
        "- 若資料不足，明確標示未提供，不要捏造",
    ]

    if workout_structure_lines:
        prompt_lines.extend([
            "",
            "## 課表片段表",
            *workout_structure_lines,
        ])
    if review.get("structure_note"):
        prompt_lines.extend([
            "",
            "## 課表判讀口徑",
            f"- {review['structure_note']}",
        ])

    if cause_lines:
        prompt_lines.extend([
            "",
            "## 平台判讀依據",
            *cause_lines,
        ])

    if segment_lines:
        prompt_lines.extend([
            "",
            "## 關鍵片段",
            *segment_lines,
        ])

    if weekly_review:
        prompt_lines.extend([
            "",
            "## 教練脈絡",
            f"- 週回顧脈絡：{weekly_review.get('focus') or '—'}",
            f"- 週回顧學習：{weekly_review.get('learning') or '—'}",
        ])
    if monthly_overview:
        prompt_lines.extend([
            f"- 月回顧脈絡：{monthly_overview.get('verdict') or '—'}",
            f"- 月回顧摘要：{monthly_overview.get('verdict_reason') or '—'}",
        ])

    if has_previous_ai_reply:
        prompt_lines.extend([
            "",
            "## 已保存的前一次 AI 延伸分析",
            "- 下面這段只能當補充脈絡，不能覆蓋平台事實。",
            "- 若這段與本次平台資料不一致，請以本次平台資料為準。",
            saved_reply["responseMarkdown"],
        ])

    prompt_lines.extend([
        "",
        "## 最後提醒",
        "- 如果平台沒有先跑過 AI 延伸分析，也請直接根據上面的平台判讀、課表片段與關鍵片段生成圖卡內容。",
        "- 不要因為缺少額外 AI 回覆，就自行補足不存在的背景故事。",
        "- 請優先做出一張資訊清楚、教練感明確的圖卡，而不是一張把所有數字塞滿的報表。",
    ])

    return "\n".join(prompt_lines)


def weekly_training_card_prompt(
    weekly,
    intelligence,
    review,
    distribution_rows,
    key_session_rows,
    workout_structure_summary_rows,
    knowledge_summary=None,
    monthly_overview=None,
    saved_reply=None,
):
    if not weekly or not intelligence or not review:
        return ""

    period_text = f"{weekly['start_date']} – {weekly['end_date']}"
    total_km = f"{format_number(weekly['total_km'], 1)} km"
    load_text = format_number(weekly["training_load"], 0) or "—"
    activities_text = str(weekly["activities"] or 0)
    avg_pace_text = format_pace_seconds(weekly["avg_pace_sec_per_km"]) or "—"
    avg_hr_text = "" if weekly["avg_hr"] is None else str(int(round(weekly["avg_hr"])))
    confidence = "High"
    if intelligence["load_delta"] is None or intelligence["km_delta"] is None:
        confidence = "Medium"

    key_session_lines = []
    seen = set()
    for row in key_session_rows or []:
        activity_id = row["activity_id"]
        if activity_id in seen:
            continue
        seen.add(activity_id)
        key_session_lines.append(
            f"- {format_short_datetime(row['activity_start_time'])} {str(row['activity_name'] or row['activity_type'] or '活動')}："
            f"{str(row['workout_type_name_en'] or '未標註')}，{format_number(row['distance_km'], 2)} km，"
            f"配速 {format_pace_seconds(row['avg_pace_sec_per_km']) or '—'}，負荷 {format_number(row['training_load'], 1) or '—'}"
        )
        if len(key_session_lines) >= 4:
            break

    pattern_insights = workout_structure_pattern_insights(workout_structure_summary_rows, "本週")

    prompt_lines = [
        "請把以下週訓練分析整理成一張可直接發布的週訓練圖卡內容。",
        "輸出目標：16:9 橫式 Facebook 圖卡，深藍／藍灰科技感背景，專業、清楚、乾淨，不要可愛風、漫畫風或過度裝飾。",
        "請只根據我提供的內容整理，不要自行補故事、情緒、傷病、恢復狀態或未提供的訓練背景。",
        "如果資料不足，請保守處理並明確寫未提供，不要硬推論。",
        "請把內容整理成真正適合上圖卡的短文案，不要把完整分析逐段重貼。",
        "請固定使用以下圖卡架構：1. 本週摘要 2. 本週位置 3. 結構重點 4. 關鍵課 5. 教練知識 6. 下週提醒。",
        "",
        "## 本週摘要",
        f"- 標題：本週訓練回顧",
        f"- 週期：{period_text}",
        f"- 活動數：{activities_text}",
        f"- 里程：{total_km}",
        f"- 負荷：{load_text}",
        f"- 平均配速 / 平均心率：{avg_pace_text} / {avg_hr_text or '—'}",
        "",
        "## 平台已整理的週判讀",
        f"- 判讀：{review['verdict']}",
        f"- 信心：{confidence}",
        f"- 學習：{review['learning']}",
        f"- 焦點：{review['focus']}",
        f"- 原因：{review['why']}",
        f"- 下一步：{review['looking_forward']}",
        "",
        "## 圖卡要強調的三件事",
        f"- 這週真正留下來的是什麼：{review['learning']}",
        f"- 為什麼平台會這樣判讀：{review['why']}",
        f"- 下週應該記住什麼：{review['looking_forward']}",
    ]

    if knowledge_summary:
        prompt_lines.extend([
            "",
            "## 教練知識",
            f"- 重點：{knowledge_summary['headline']}",
            f"- 說明：{knowledge_summary['detail']}",
        ])

    if pattern_insights or workout_structure_summary_rows:
        prompt_lines.extend([
            "",
            "## 課表結構重點",
            "- 這裡要用教練語氣整理本週課表型態，不要只列名稱。",
        ])
        prompt_lines.extend(f"- {line}" for line in pattern_insights)
        for row in workout_structure_summary_rows[:4]:
            prompt_lines.append(
                f"- {row['date']} {row['activity']}（{row['workout']}）：{row['summary']}"
            )

    if key_session_lines:
        prompt_lines.extend([
            "",
            "## 關鍵課",
            *key_session_lines,
        ])

    if monthly_overview:
        prompt_lines.extend([
            "",
            "## 月脈絡",
            f"- 這週所在的月度位置：{monthly_overview.get('verdict') or '—'}",
            f"- 月度摘要：{monthly_overview.get('verdict_reason') or '—'}",
        ])

    if saved_reply and saved_reply.get("responseMarkdown"):
        prompt_lines.extend([
            "",
            "## 已保存的前一次 AI 延伸分析",
            "- 以下只能當補充脈絡，不能覆蓋平台事實。",
            saved_reply["responseMarkdown"],
        ])

    prompt_lines.extend([
        "",
        "## 風格要求",
        "- 繁體中文",
        "- 每個區塊請寫成能直接放上圖卡的短句",
        "- 整體語氣要像專業跑步教練，不像系統報表",
        "- 不要把所有數字塞滿，重點是讓人一眼看懂這週學到了什麼",
        "- 最後請補一行適合放在卡片底部的收尾句",
    ])

    return "\n".join(prompt_lines)


def monthly_training_card_prompt(
    monthly,
    intelligence,
    progress_row,
    distribution_rows,
    key_session_rows,
    workout_structure_summary_rows,
    related_week_rows,
    coach_memory=None,
    knowledge_summary=None,
    saved_reply=None,
):
    if not monthly or not intelligence:
        return ""

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
            f"目前仍屬於正常累積。因為本月只完成 {format_number(progress_pct, 0)}%，目前負荷與里程都還在可接受區間。"
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

    confidence = "Medium" if intelligence["is_partial_month"] else "High"
    pattern_insights = workout_structure_pattern_insights(workout_structure_summary_rows, "本月")

    key_session_lines = []
    seen = set()
    for row in key_session_rows or []:
        activity_id = row["activity_id"]
        if activity_id in seen:
            continue
        seen.add(activity_id)
        key_session_lines.append(
            f"- {format_short_datetime(row['activity_start_time'])} {str(row['activity_name'] or row['activity_type'] or '活動')}："
            f"{str(row['workout_type_name_en'] or '未標註')}，{format_number(row['distance_km'], 2)} km，"
            f"配速 {format_pace_seconds(row['avg_pace_sec_per_km']) or '—'}，負荷 {format_number(row['training_load'], 1) or '—'}"
        )
        if len(key_session_lines) >= 4:
            break

    week_lines = []
    for row in related_week_rows or []:
        week_lines.append(
            f"- {row['start_date']} – {row['end_date']}：{str(row['verdict'] or '本週')}，"
            f"活動 {row['activities']}，{format_number(row['total_km'], 2) or '—'} km，"
            f"負荷 {format_number(row['training_load'], 1) or '—'}"
        )
        if len(week_lines) >= 4:
            break

    prompt_lines = [
        "請把以下月訓練分析整理成一張可直接發布的月訓練圖卡內容。",
        "輸出目標：16:9 橫式 Facebook 圖卡，深藍／藍灰科技感背景，專業、清楚、乾淨，不要可愛風、漫畫風或過度裝飾。",
        "請只根據我提供的內容整理，不要自行補故事、情緒、傷病、恢復狀態或未提供的訓練背景。",
        "如果月份仍在進行中，請把它寫成進度點，不要假裝是完整月總結。",
        "請把內容整理成真正適合上圖卡的短文案，不要把完整分析逐段重貼。",
        "請固定使用以下圖卡架構：1. 本月摘要 2. 本月位置 3. 課表型態 4. 關鍵週與關鍵課 5. 教練知識 6. 下月提醒。",
        "",
        "## 本月摘要",
        f"- 標題：本月訓練回顧",
        f"- 月份：{monthly['month_key']}",
        f"- 狀態：{'進行中' if intelligence['is_partial_month'] else '完整'}",
        f"- 里程：{format_number(monthly['total_km'], 1)} km",
        f"- 時間：{format_duration_hms(monthly['total_time_sec']) or '—'}",
        f"- 負荷：{format_number(monthly['training_load'], 0) or '—'}",
        f"- 活動數：{monthly['activities'] or 0}",
        f"- 平均配速 / 平均心率：{format_pace_seconds(monthly['avg_pace_sec_per_km']) or '—'} / {'' if monthly['avg_hr'] is None else int(round(monthly['avg_hr']))}",
        f"- 品質課 / 長跑：{quality_sessions} / {long_runs}",
        "",
        "## 平台已整理的月判讀",
        f"- 位置：{verdict}",
        f"- 階段：{phase}",
        f"- 信心：{confidence}",
        f"- 判讀原因：{verdict_reason}",
    ]

    if coach_memory:
        prompt_lines.extend([
            f"- 上個月：{coach_memory.get('previous_month_key') or '—'}",
            f"- 後續追蹤：{coach_memory.get('follow_up') or '—'}",
        ])

    if knowledge_summary:
        prompt_lines.extend([
            "",
            "## 教練知識",
            f"- 重點：{knowledge_summary['headline']}",
            f"- 說明：{knowledge_summary['detail']}",
        ])

    if pattern_insights or workout_structure_summary_rows:
        prompt_lines.extend([
            "",
            "## 課表型態重點",
            "- 這裡要先整理本月代表型態在做什麼，不要只列課名或課表代號。",
        ])
        prompt_lines.extend(f"- {line}" for line in pattern_insights)
        for row in workout_structure_summary_rows[:4]:
            prompt_lines.append(
                f"- {row['date']} {row['activity']}（{row['workout']}）：{row['summary']}"
            )

    if week_lines:
        prompt_lines.extend([
            "",
            "## 關鍵週",
            *week_lines,
        ])

    if key_session_lines:
        prompt_lines.extend([
            "",
            "## 關鍵課",
            *key_session_lines,
        ])

    if saved_reply and saved_reply.get("responseMarkdown"):
        prompt_lines.extend([
            "",
            "## 已保存的前一次 AI 延伸分析",
            "- 以下只能當補充脈絡，不能覆蓋平台事實。",
            saved_reply["responseMarkdown"],
        ])

    prompt_lines.extend([
        "",
        "## 風格要求",
        "- 繁體中文",
        "- 每個區塊請寫成能直接放上圖卡的短句",
        "- 整體語氣要像專業跑步教練，不像系統報表",
        "- 不要把所有數字塞滿，重點是讓人一眼看懂這個月走到哪裡",
        "- 最後請補一行適合放在卡片底部的收尾句",
    ])

    return "\n".join(prompt_lines)


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


def format_location_name_from_address(address, display_name="", concise=False):
    if not isinstance(address, dict):
        address = {}
    if concise:
        concise_parts = []
        for key in ("state", "county", "city", "town", "city_district", "district", "suburb"):
            value = str(address.get(key) or "").strip()
            if value and value not in concise_parts:
                concise_parts.append(value)
        if concise_parts:
            return " / ".join(concise_parts[:2])
    parts = []
    for key in ("state", "county", "city", "town", "suburb", "city_district", "district", "quarter", "neighbourhood", "road", "pedestrian"):
        value = str(address.get(key) or "").strip()
        if value and value not in parts:
            parts.append(value)
    if parts:
        return " / ".join(parts[:4])
    display_name = str(display_name or "").strip()
    if display_name:
        return display_name.split(",")[0].strip()
    return ""


@lru_cache(maxsize=512)
def reverse_geocode_location_label(latitude, longitude):
    try:
        lat = round(float(latitude), 5)
        lon = round(float(longitude), 5)
    except (TypeError, ValueError):
        return ""
    url = (
        "https://nominatim.openstreetmap.org/reverse?"
        + urlencode(
            {
                "format": "jsonv2",
                "lat": f"{lat:.5f}",
                "lon": f"{lon:.5f}",
                "zoom": "18",
                "addressdetails": "1",
                "accept-language": "zh-TW,zh,en",
            }
        )
    )
    try:
        with urlopen(Request(url, headers={"User-Agent": "Running Analytics/1.0"}), timeout=8) as response:
            payload = json.load(response)
    except Exception:
        return ""
    return format_location_name_from_address(payload.get("address") or {}, payload.get("display_name") or "")


@lru_cache(maxsize=512)
def reverse_geocode_location_label_concise(latitude, longitude):
    try:
        lat = round(float(latitude), 5)
        lon = round(float(longitude), 5)
    except (TypeError, ValueError):
        return ""
    url = (
        "https://nominatim.openstreetmap.org/reverse?"
        + urlencode(
            {
                "format": "jsonv2",
                "lat": f"{lat:.5f}",
                "lon": f"{lon:.5f}",
                "zoom": "16",
                "addressdetails": "1",
                "accept-language": "zh-TW,zh,en",
            }
        )
    )
    try:
        with urlopen(Request(url, headers={"User-Agent": "Running Analytics/1.0"}), timeout=8) as response:
            payload = json.load(response)
    except Exception:
        return ""
    return format_location_name_from_address(payload.get("address") or {}, payload.get("display_name") or "", concise=True)


def connect():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    ensure_activity_gps_columns(connection)
    ensure_semantic_layer(connection)
    ensure_dropdown_sources(connection)
    ensure_workout_purpose_map(connection)
    ensure_coach_knowledge_shoe_memory(connection)
    ensure_activity_metadata_provenance(connection)
    ensure_activity_wsi_table(connection)
    connection.commit()
    return connection


def first_form_value(form, key, default=""):
    values = form.get(key)
    if not values:
        return default
    return values[0]


def _default_dropdown_options():
    options = {}
    for key, value in DEFAULT_DROPDOWN_OPTIONS.items():
        options[key] = dict(value) if isinstance(value, dict) else list(value)
    return options


def _load_legacy_dropdown_options():
    if not CONFIG_PATH.exists():
        return {}
    try:
        loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    options = {}
    for key in ("shoes", "workout_types", "garmin_rpe", "garmin_feel", "training_focus"):
        if isinstance(loaded.get(key), list):
            options[key] = [str(item).strip() for item in loaded[key] if str(item).strip()]
    if isinstance(loaded.get("workout_focus_map"), dict):
        options["workout_focus_map"] = {
            str(map_key).strip(): [str(item).strip() for item in map_value if str(item).strip()]
            for map_key, map_value in loaded["workout_focus_map"].items()
            if str(map_key).strip() and isinstance(map_value, list)
        }
    return options


def ensure_dropdown_sources(connection):
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {DROPDOWN_SOURCE_TABLE} (
            source_key TEXT PRIMARY KEY,
            source_json TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    existing_keys = {
        row["source_key"]
        for row in connection.execute(f"SELECT source_key FROM {DROPDOWN_SOURCE_TABLE}").fetchall()
    }
    seed_options = _load_legacy_dropdown_options() if not existing_keys else {}
    for key, default_value in DEFAULT_DROPDOWN_OPTIONS.items():
        if key in existing_keys:
            continue
        value = seed_options.get(key, default_value)
        connection.execute(
            f"""
            INSERT INTO {DROPDOWN_SOURCE_TABLE} (source_key, source_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(source_key) DO UPDATE SET
                source_json = excluded.source_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, json.dumps(value, ensure_ascii=False)),
        )


def ensure_feedback_dictionary_options(connection, seed_options=None):
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {FEEDBACK_DICTIONARY_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dictionary_key TEXT NOT NULL,
            label TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(dictionary_key, label)
        )
        """
    )
    seed_options = seed_options or {}
    for dictionary_key, default_values in FEEDBACK_DICTIONARY_DEFAULTS.items():
        existing_count = connection.execute(
            f"SELECT COUNT(*) AS count FROM {FEEDBACK_DICTIONARY_TABLE} WHERE dictionary_key = ?",
            (dictionary_key,),
        ).fetchone()["count"]
        if existing_count:
            continue
        values = seed_options.get(dictionary_key)
        if not isinstance(values, list) or not values:
            values = default_values
        for label in values:
            value = str(label or "").strip()
            if not value:
                continue
            connection.execute(
                f"""
                INSERT INTO {FEEDBACK_DICTIONARY_TABLE} (dictionary_key, label, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(dictionary_key, label) DO UPDATE SET
                    updated_at = CURRENT_TIMESTAMP
                """,
                (dictionary_key, value),
            )


def feedback_dictionary_rows(connection, dictionary_key):
    ensure_feedback_dictionary_options(connection)
    return connection.execute(
        f"""
        SELECT id, label
        FROM {FEEDBACK_DICTIONARY_TABLE}
        WHERE dictionary_key = ?
        ORDER BY id
        """,
        (dictionary_key,),
    ).fetchall()


def save_feedback_dictionary_option(connection, dictionary_key, label, option_id=None):
    dictionary_key = str(dictionary_key or "").strip()
    value = str(label or "").strip()
    if dictionary_key not in FEEDBACK_DICTIONARY_DEFAULTS:
        raise ValueError("找不到這個字典。")
    if not value:
        raise ValueError("請先輸入項目名稱。")
    ensure_feedback_dictionary_options(connection)
    if option_id:
        existing = connection.execute(
            f"SELECT id FROM {FEEDBACK_DICTIONARY_TABLE} WHERE id = ? AND dictionary_key = ?",
            (int(option_id), dictionary_key),
        ).fetchone()
        if not existing:
            raise ValueError("找不到要更新的項目。")
        duplicate = connection.execute(
            f"""
            SELECT id FROM {FEEDBACK_DICTIONARY_TABLE}
            WHERE dictionary_key = ? AND lower(label) = lower(?) AND id != ?
            """,
            (dictionary_key, value, int(option_id)),
        ).fetchone()
        if duplicate:
            raise ValueError("這個項目已經存在。")
        connection.execute(
            f"""
            UPDATE {FEEDBACK_DICTIONARY_TABLE}
            SET label = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND dictionary_key = ?
            """,
            (value, int(option_id), dictionary_key),
        )
        return int(option_id)
    duplicate = connection.execute(
        f"""
        SELECT id FROM {FEEDBACK_DICTIONARY_TABLE}
        WHERE dictionary_key = ? AND lower(label) = lower(?)
        """,
        (dictionary_key, value),
    ).fetchone()
    if duplicate:
        raise ValueError("這個項目已經存在。")
    connection.execute(
        f"""
        INSERT INTO {FEEDBACK_DICTIONARY_TABLE} (dictionary_key, label, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        """,
        (dictionary_key, value),
    )
    inserted = connection.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    return int(inserted)


def delete_feedback_dictionary_option(connection, dictionary_key, option_id):
    dictionary_key = str(dictionary_key or "").strip()
    if dictionary_key not in FEEDBACK_DICTIONARY_DEFAULTS:
        raise ValueError("找不到這個字典。")
    connection.execute(
        f"DELETE FROM {FEEDBACK_DICTIONARY_TABLE} WHERE id = ? AND dictionary_key = ?",
        (int(option_id), dictionary_key),
    )


def _normalize_dropdown_source_value(key, value):
    default_value = DEFAULT_DROPDOWN_OPTIONS.get(key, [])
    if isinstance(default_value, dict):
        if not isinstance(value, dict):
            return dict(default_value)
        normalized = {}
        for map_key, map_value in value.items():
            normalized_key = str(map_key).strip()
            if not normalized_key:
                continue
            if isinstance(map_value, list):
                normalized[normalized_key] = [str(item).strip() for item in map_value if str(item).strip()]
            else:
                normalized[normalized_key] = normalize_option_lines(map_value)
        return normalized
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if value in (None, ""):
        return list(default_value) if isinstance(default_value, list) else dict(default_value)
    return normalize_option_lines(value)


def _read_dropdown_source_rows(connection):
    ensure_dropdown_sources(connection)
    rows = connection.execute(
        f"""
        SELECT source_key, source_json
        FROM {DROPDOWN_SOURCE_TABLE}
        """
    ).fetchall()
    options = _default_dropdown_options()
    for row in rows:
        key = str(row["source_key"] or "").strip()
        if not key:
            continue
        try:
            value = json.loads(row["source_json"] or "null")
        except json.JSONDecodeError:
            continue
        options[key] = _normalize_dropdown_source_value(key, value)
    return options


def load_metadata_dropdown_options(connection=None):
    close_connection = False
    if connection is None:
        connection = sqlite3.connect(DB_PATH)
        connection.row_factory = sqlite3.Row
        close_connection = True
    try:
        options = _read_dropdown_source_rows(connection)
        ensure_feedback_dictionary_options(connection, options)
        for dictionary_key in FEEDBACK_DICTIONARY_DEFAULTS:
            options[dictionary_key] = [
                str(row["label"]).strip()
                for row in feedback_dictionary_rows(connection, dictionary_key)
                if str(row["label"]).strip()
            ]
        return options
    finally:
        if close_connection:
            connection.commit()
            connection.close()


def save_metadata_dropdown_options(options, connection=None):
    close_connection = False
    if connection is None:
        connection = sqlite3.connect(DB_PATH)
        connection.row_factory = sqlite3.Row
        close_connection = True
    try:
        current = _read_dropdown_source_rows(connection)
        merged = dict(current)
        for key, value in (options or {}).items():
            if key in DEFAULT_DROPDOWN_OPTIONS:
                merged[key] = _normalize_dropdown_source_value(key, value)
        ensure_dropdown_sources(connection)
        for key, value in merged.items():
            connection.execute(
                f"""
                INSERT INTO {DROPDOWN_SOURCE_TABLE} (source_key, source_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(source_key) DO UPDATE SET
                    source_json = excluded.source_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, json.dumps(value, ensure_ascii=False)),
            )
    finally:
        if close_connection:
            connection.commit()
            connection.close()


def normalize_option_lines(text):
    lines = []
    for raw_line in str(text or "").splitlines():
        value = str(raw_line or "").strip()
        if value:
            lines.append(value)
    return lines


def option_lines_text(values):
    return "\n".join(str(value).strip() for value in values if str(value).strip())


def append_shoe_option(label, connection=None):
    value = str(label or "").strip()
    if not value:
        raise ValueError("請先輸入鞋款名稱。")

    options = load_metadata_dropdown_options(connection)
    existing = {canonical_label(item).lower() for item in options.get("shoes", [])}
    if canonical_label(value).lower() in existing:
        raise ValueError("這雙鞋已經在清單裡了。")

    updated_shoes = list(options.get("shoes", []))
    updated_shoes.append(value)
    options["shoes"] = updated_shoes
    save_metadata_dropdown_options(options, connection)
    return value


def label_primary(value):
    value = str(value or "").strip()
    if not value:
        return ""
    return re.split(r"[（(]", value, maxsplit=1)[0].strip()


def canonical_label(value):
    return label_primary(value).replace("₂", "2")


KNOWN_SHOE_BRANDS = (
    "adidas",
    "asics",
    "brooks",
    "hoka",
    "mizuno",
    "new balance",
    "nike",
    "on",
    "puma",
    "saucony",
)


def parse_shoe_brand_model(label):
    primary = label_primary(label) or str(label or "").strip()
    normalized = re.sub(r"\s+", " ", primary).strip()
    lowered = normalized.lower()
    for brand in KNOWN_SHOE_BRANDS:
        prefix = f"{brand} "
        if lowered.startswith(prefix):
            model = normalized[len(prefix):].strip()
            if model:
                return normalized[: len(brand)].upper() if brand == "hoka" else normalized[: len(brand)], model
    return "", normalized


def workout_type_display_name(row):
    candidates = [
        "name_zh",
        "name_en",
        "workout_name_zh",
        "workout_name_en",
        "workout_type_code",
    ]
    for key in candidates:
        try:
            value = row[key]
        except Exception:
            value = None
        if value not in (None, ""):
            return str(value)
    return ""


def training_purpose_display_name(row):
    candidates = [
        "name_zh",
        "name_en",
        "primary_training_purpose_name_zh",
        "primary_training_purpose_name_en",
        "secondary_training_purpose_name_zh",
        "secondary_training_purpose_name_en",
        "training_purpose_code",
    ]
    for key in candidates:
        try:
            value = row[key]
        except Exception:
            value = None
        if value not in (None, ""):
            return str(value)
    return ""


def workout_intensity_display_label(value):
    return WORKOUT_INTENSITY_LABELS_ZH.get(str(value or ""), str(value or ""))


def purpose_category_display_label(value):
    return PURPOSE_CATEGORY_LABELS_ZH.get(str(value or ""), str(value or ""))


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
    brand, model = parse_shoe_brand_model(label)
    primary = model or label_primary(label) or str(label or "").strip()
    return {
        "shoe_code": code_from_label(primary, "shoe"),
        "brand": brand,
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
    brand_value = row["brand"] if str(row["brand"] or "").strip() else existing["brand"]
    model_value = row["model"] if str(row["model"] or "").strip() else existing["model"]
    nickname_value = row["nickname"] if str(row["nickname"] or "").strip() else existing["nickname"]
    category_value = row["category"] if str(row["category"] or "").strip() else existing["category"]
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
            brand_value,
            model_value,
            nickname_value,
            category_value,
            row["shoe_code"],
        ),
    )


def save_shoe_dimension(connection, shoe_id, category):
    category_value = str(category or "").strip()
    connection.execute(
        """
        UPDATE shoe
        SET
            category = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (category_value, shoe_id),
    )


def reconcile_reference_choice(connection, table, code_column, row, update_existing=True):
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
    if not update_existing:
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
            update_existing=False,
        )
    for label in dropdown_options.get("training_focus", []):
        reconcile_reference_choice(
            connection,
            "training_purpose",
            "training_purpose_code",
            training_purpose_dimension_row(label),
            update_existing=False,
        )


def workout_purpose_default_codes(workout_key):
    normalized = normalize_choice_key(workout_key)
    if not normalized:
        return None, None
    for key, value in WORKOUT_PURPOSE_DEFAULTS.items():
        if key in normalized:
            return value
    if "recovery" in normalized:
        return "recovery", "maintenance"
    if any(token in normalized for token in ("easy", "warmup", "warm-up", "warm up")):
        return "aerobic_base", "maintenance"
    if any(token in normalized for token in ("long", "lsd", "endurance")):
        return "endurance", "aerobic_base"
    if any(token in normalized for token in ("tempo", "threshold", "cruise")):
        return "threshold", "race_specific"
    if "interval" in normalized:
        return "vo2max", "speed"
    if "fartlek" in normalized:
        return "speed", "running_economy"
    if "race" in normalized:
        return "race", "race_specific"
    return "maintenance", None


def ensure_workout_purpose_map(connection):
    ensure_metadata_dimensions(connection, load_metadata_dropdown_options(connection))
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS workout_type_training_purpose_map (
            workout_type_id INTEGER PRIMARY KEY,
            primary_training_purpose_id INTEGER,
            secondary_training_purpose_id INTEGER,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workout_type_id) REFERENCES workout_type(id) ON DELETE CASCADE,
            FOREIGN KEY (primary_training_purpose_id) REFERENCES training_purpose(id) ON DELETE SET NULL,
            FOREIGN KEY (secondary_training_purpose_id) REFERENCES training_purpose(id) ON DELETE SET NULL
        )
        """
    )
    workout_rows = connection.execute(
        """
        SELECT
            id,
            workout_type_code,
            name_en,
            name_zh
        FROM workout_type
        ORDER BY COALESCE(sort_order, 999), name_en, workout_type_code
        """
    ).fetchall()
    for row in workout_rows:
        existing = connection.execute(
            "SELECT workout_type_id FROM workout_type_training_purpose_map WHERE workout_type_id = ?",
            (row["id"],),
        ).fetchone()
        if existing:
            continue
        primary_code, secondary_code = workout_purpose_default_codes(
            f"{row['workout_type_code']} {row['name_en']} {row['name_zh']}"
        )
        primary_id = dimension_id_by_code(connection, "training_purpose", "training_purpose_code", primary_code)
        secondary_id = dimension_id_by_code(connection, "training_purpose", "training_purpose_code", secondary_code)
        connection.execute(
            """
            INSERT INTO workout_type_training_purpose_map (
                workout_type_id,
                primary_training_purpose_id,
                secondary_training_purpose_id,
                updated_at
            ) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (row["id"], primary_id, secondary_id),
        )


def ensure_coach_knowledge_shoe_memory(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS coach_knowledge_shoe_memory (
            workout_type_id INTEGER NOT NULL,
            primary_training_purpose_id INTEGER NOT NULL,
            shoe_id INTEGER NOT NULL,
            confirmation_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (workout_type_id, primary_training_purpose_id, shoe_id),
            FOREIGN KEY (workout_type_id) REFERENCES workout_type(id) ON DELETE CASCADE,
            FOREIGN KEY (primary_training_purpose_id) REFERENCES training_purpose(id) ON DELETE CASCADE,
            FOREIGN KEY (shoe_id) REFERENCES shoe(id) ON DELETE CASCADE
        )
        """
    )
    existing = connection.execute(
        "SELECT COUNT(*) AS count FROM coach_knowledge_shoe_memory"
    ).fetchone()["count"]
    if existing:
        return
    connection.execute(
        """
        INSERT INTO coach_knowledge_shoe_memory (
            workout_type_id,
            primary_training_purpose_id,
            shoe_id,
            confirmation_count,
            created_at,
            updated_at
        )
        SELECT
            workout_type_id,
            primary_training_purpose_id,
            shoe_id,
            COUNT(*) AS confirmation_count,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM activity_review_view
        WHERE shoe_id IS NOT NULL
          AND workout_type_id IS NOT NULL
          AND primary_training_purpose_id IS NOT NULL
        GROUP BY workout_type_id, primary_training_purpose_id, shoe_id
        """
    )


def ensure_activity_metadata_provenance(connection):
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {ACTIVITY_METADATA_PROVENANCE_TABLE} (
            activity_id INTEGER NOT NULL REFERENCES activity(id) ON DELETE CASCADE,
            field_name TEXT NOT NULL CHECK (field_name IN ('shoe', 'workout_type', 'primary_purpose', 'secondary_purpose')),
            source TEXT NOT NULL,
            source_detail TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (activity_id, field_name)
        )
        """
    )
    existing = connection.execute(
        f"SELECT COUNT(*) AS count FROM {ACTIVITY_METADATA_PROVENANCE_TABLE}"
    ).fetchone()["count"]
    if existing:
        return

    legacy_rows = connection.execute(
        """
        SELECT
            activity.id AS activity_id,
            activity.activity_start_time,
            activity.updated_at,
            review.shoe_id,
            review.workout_type_id,
            review.primary_training_purpose_id
        FROM activity
        JOIN activity_review_view AS review
            ON review.activity_id = activity.id
        """
    ).fetchall()
    for row in legacy_rows:
        activity_start_time = str(row["activity_start_time"] or "")
        updated_at = str(row["updated_at"] or "")
        likely_auto_fill = (
            row["shoe_id"] is not None
            and activity_start_time
            and updated_at
            and activity_start_time < LEGACY_SHOE_FILL_CUTOFF
            and updated_at >= LEGACY_SHOE_FILL_CUTOFF
        )

        if row["shoe_id"] is not None:
            connection.execute(
                f"""
                INSERT INTO {ACTIVITY_METADATA_PROVENANCE_TABLE} (
                    activity_id,
                    field_name,
                    source,
                    source_detail,
                    created_at,
                    updated_at
                ) VALUES (?, 'shoe', ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    row["activity_id"],
                    "coach_memory_auto_fill" if likely_auto_fill else "legacy_unknown",
                    "Heuristic backfill from legacy shoe updates." if likely_auto_fill else "Historical source not recorded.",
                ),
            )
        if row["workout_type_id"] is not None:
            connection.execute(
                f"""
                INSERT INTO {ACTIVITY_METADATA_PROVENANCE_TABLE} (
                    activity_id,
                    field_name,
                    source,
                    source_detail,
                    created_at,
                    updated_at
                ) VALUES (?, 'workout_type', 'legacy_unknown', 'Historical source not recorded.', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (row["activity_id"],),
            )
        if row["primary_training_purpose_id"] is not None:
            connection.execute(
                f"""
                INSERT INTO {ACTIVITY_METADATA_PROVENANCE_TABLE} (
                    activity_id,
                    field_name,
                    source,
                    source_detail,
                    created_at,
                    updated_at
                ) VALUES (?, 'primary_purpose', 'legacy_unknown', 'Historical source not recorded.', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (row["activity_id"],),
            )


def activity_metadata_provenance_map(connection, activity_id):
    if not activity_id:
        return {}
    rows = connection.execute(
        f"""
        SELECT
            field_name,
            source,
            source_detail,
            updated_at
        FROM {ACTIVITY_METADATA_PROVENANCE_TABLE}
        WHERE activity_id = ?
        """,
        (activity_id,),
    ).fetchall()
    return {
        row["field_name"]: {
            "source": row["source"],
            "source_detail": row["source_detail"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    }


def record_activity_metadata_provenance(connection, activity_id, field_name, source, source_detail=""):
    if not activity_id or not field_name:
        return
    source_value = str(source or "").strip()
    if not source_value:
        return
    ensure_activity_metadata_provenance(connection)
    connection.execute(
        f"""
        INSERT INTO {ACTIVITY_METADATA_PROVENANCE_TABLE} (
            activity_id,
            field_name,
            source,
            source_detail,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(activity_id, field_name) DO UPDATE SET
            source = excluded.source,
            source_detail = excluded.source_detail,
            updated_at = CURRENT_TIMESTAMP
        """,
        (activity_id, field_name, source_value, source_detail or None),
    )


def clear_activity_metadata_provenance(connection, activity_id, field_name):
    if not activity_id or not field_name:
        return
    connection.execute(
        f"DELETE FROM {ACTIVITY_METADATA_PROVENANCE_TABLE} WHERE activity_id = ? AND field_name = ?",
        (activity_id, field_name),
    )


def ensure_activity_gps_columns(connection):
    table_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'activity'"
    ).fetchone()
    if not table_exists:
        return
    existing_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(activity)").fetchall()
    }
    for column_name in ("start_latitude", "start_longitude", "end_latitude", "end_longitude"):
        if column_name in existing_columns:
            continue
        connection.execute(f"ALTER TABLE activity ADD COLUMN {column_name} REAL")


def provenance_source_label(source):
    return ACTIVITY_METADATA_PROVENANCE_LABELS.get(str(source or "").strip(), "來源待確認")


def coach_knowledge_shoe_memory_row(connection, workout_type_id, primary_purpose_id):
    if workout_type_id is None or primary_purpose_id is None:
        return None
    return connection.execute(
        """
        SELECT
            coach_knowledge_shoe_memory.shoe_id,
            coach_knowledge_shoe_memory.confirmation_count,
            coach_knowledge_shoe_memory.updated_at,
            shoe.shoe_code,
            shoe.brand,
            shoe.model,
            shoe.nickname
        FROM coach_knowledge_shoe_memory
        JOIN shoe ON shoe.id = coach_knowledge_shoe_memory.shoe_id
        WHERE coach_knowledge_shoe_memory.workout_type_id = ?
          AND coach_knowledge_shoe_memory.primary_training_purpose_id = ?
        ORDER BY coach_knowledge_shoe_memory.confirmation_count DESC,
                 coach_knowledge_shoe_memory.updated_at DESC,
                 coach_knowledge_shoe_memory.shoe_id
        LIMIT 1
        """,
        (workout_type_id, primary_purpose_id),
    ).fetchone()


def record_coach_knowledge_shoe_memory(connection, activity_id):
    row = connection.execute(
        """
        SELECT
            activity_id,
            shoe_id,
            workout_type_id,
            primary_training_purpose_id
        FROM activity_review_view
        WHERE activity_id = ?
        """,
        (activity_id,),
    ).fetchone()
    if not row:
        return False
    if row["shoe_id"] is None or row["workout_type_id"] is None or row["primary_training_purpose_id"] is None:
        return False
    ensure_coach_knowledge_shoe_memory(connection)
    connection.execute(
        """
        INSERT INTO coach_knowledge_shoe_memory (
            workout_type_id,
            primary_training_purpose_id,
            shoe_id,
            confirmation_count,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(workout_type_id, primary_training_purpose_id, shoe_id)
        DO UPDATE SET
            confirmation_count = confirmation_count + 1,
            updated_at = CURRENT_TIMESTAMP
        """,
        (row["workout_type_id"], row["primary_training_purpose_id"], row["shoe_id"]),
    )
    return True


def apply_coach_knowledge_shoe_memory(connection):
    ensure_coach_knowledge_shoe_memory(connection)
    missing_rows = connection.execute(
        """
        SELECT
            activity_id,
            workout_type_id,
            primary_training_purpose_id
        FROM activity_review_view
        WHERE shoe_id IS NULL
          AND workout_type_id IS NOT NULL
          AND primary_training_purpose_id IS NOT NULL
        ORDER BY activity_start_time DESC
        """
    ).fetchall()
    changed = 0
    for row in missing_rows:
        memory_row = coach_knowledge_shoe_memory_row(
            connection,
            row["workout_type_id"],
            row["primary_training_purpose_id"],
        )
        if not memory_row:
            continue
        result = connection.execute(
            """
            UPDATE activity
            SET shoe_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND shoe_id IS NULL
            """,
            (memory_row["shoe_id"], row["activity_id"]),
        )
        changed += int(result.rowcount or 0)
    return changed


def save_workout_purpose_mapping(connection, workout_type_code, primary_purpose_code, secondary_purpose_code):
    ensure_workout_purpose_map(connection)
    workout_type_id = dimension_id_by_code(connection, "workout_type", "workout_type_code", workout_type_code)
    if workout_type_id is None:
        return
    primary_id = None if value_is_blank(primary_purpose_code) else dimension_id_by_code(connection, "training_purpose", "training_purpose_code", primary_purpose_code)
    secondary_id = None if value_is_blank(secondary_purpose_code) else dimension_id_by_code(connection, "training_purpose", "training_purpose_code", secondary_purpose_code)
    connection.execute(
        """
        INSERT INTO workout_type_training_purpose_map (
            workout_type_id,
            primary_training_purpose_id,
            secondary_training_purpose_id,
            updated_at
        ) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(workout_type_id) DO UPDATE SET
            primary_training_purpose_id = excluded.primary_training_purpose_id,
            secondary_training_purpose_id = excluded.secondary_training_purpose_id,
            updated_at = CURRENT_TIMESTAMP
        """,
        (workout_type_id, primary_id, secondary_id),
    )


def save_workout_type_dimension(connection, workout_type_code, name_en, name_zh, intensity_category):
    code = str(workout_type_code or "").strip()
    name_en_value = str(name_en or "").strip()
    name_zh_value = str(name_zh or "").strip()
    if not name_en_value and not name_zh_value:
        raise ValueError("請至少輸入課表名稱。")
    if not code:
        code = code_from_label(name_en_value or name_zh_value, "workout")
    if not name_en_value:
        name_en_value = name_zh_value or code
    if not name_zh_value:
        name_zh_value = name_en_value
    intensity_value = str(intensity_category or "").strip() or "Moderate"
    existing = connection.execute(
        "SELECT id FROM workout_type WHERE workout_type_code = ?",
        (code,),
    ).fetchone()
    if existing:
        connection.execute(
            """
            UPDATE workout_type
            SET
                name_en = ?,
                name_zh = ?,
                intensity_category = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE workout_type_code = ?
            """,
            (name_en_value, name_zh_value, intensity_value, code),
        )
        return code
    row = workout_type_dimension_row(name_en_value or name_zh_value)
    row["workout_type_code"] = code
    row["name_en"] = name_en_value
    row["name_zh"] = name_zh_value
    row["intensity_category"] = intensity_value
    columns = list(row)
    placeholders = ", ".join("?" for _ in columns)
    connection.execute(
        f"INSERT INTO workout_type ({', '.join(columns)}) VALUES ({placeholders})",
        [row[column] for column in columns],
    )
    return code


def save_training_purpose_dimension(connection, training_purpose_code, name_en, name_zh, purpose_category):
    code = str(training_purpose_code or "").strip()
    name_en_value = str(name_en or "").strip()
    name_zh_value = str(name_zh or "").strip()
    if not name_en_value and not name_zh_value:
        raise ValueError("請至少輸入訓練目的名稱。")
    if not code:
        code = code_from_label(name_en_value or name_zh_value, "purpose")
    if not name_en_value:
        name_en_value = name_zh_value or code
    if not name_zh_value:
        name_zh_value = name_en_value
    category_value = str(purpose_category or "").strip() or "Maintenance"
    existing = connection.execute(
        "SELECT id FROM training_purpose WHERE training_purpose_code = ?",
        (code,),
    ).fetchone()
    if existing:
        connection.execute(
            """
            UPDATE training_purpose
            SET
                name_en = ?,
                name_zh = ?,
                purpose_category = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE training_purpose_code = ?
            """,
            (name_en_value, name_zh_value, category_value, code),
        )
        return code
    row = training_purpose_dimension_row(name_en_value or name_zh_value)
    row["training_purpose_code"] = code
    row["name_en"] = name_en_value
    row["name_zh"] = name_zh_value
    row["purpose_category"] = category_value
    columns = list(row)
    placeholders = ", ".join("?" for _ in columns)
    connection.execute(
        f"INSERT INTO training_purpose ({', '.join(columns)}) VALUES ({placeholders})",
        [row[column] for column in columns],
    )
    return code


def delete_workout_type_dimension(connection, workout_type_code):
    workout_row = connection.execute(
        "SELECT id FROM workout_type WHERE workout_type_code = ?",
        (workout_type_code,),
    ).fetchone()
    if not workout_row:
        return 0
    workout_type_id = workout_row["id"]
    affected_activities = connection.execute(
        "SELECT COUNT(*) AS count FROM activity WHERE workout_type_id = ?",
        (workout_type_id,),
    ).fetchone()["count"]
    connection.execute(
        "UPDATE activity SET workout_type_id = NULL, updated_at = CURRENT_TIMESTAMP WHERE workout_type_id = ?",
        (workout_type_id,),
    )
    connection.execute(
        "DELETE FROM workout_type_training_purpose_map WHERE workout_type_id = ?",
        (workout_type_id,),
    )
    connection.execute(
        "DELETE FROM workout_type WHERE id = ?",
        (workout_type_id,),
    )
    return int(affected_activities or 0)


def delete_training_purpose_dimension(connection, training_purpose_code):
    purpose_row = connection.execute(
        "SELECT id FROM training_purpose WHERE training_purpose_code = ?",
        (training_purpose_code,),
    ).fetchone()
    if not purpose_row:
        return 0
    training_purpose_id = purpose_row["id"]
    affected_activity_purposes = connection.execute(
        "SELECT COUNT(*) AS count FROM activity_training_purpose WHERE training_purpose_id = ?",
        (training_purpose_id,),
    ).fetchone()["count"]
    connection.execute(
        "DELETE FROM activity_training_purpose WHERE training_purpose_id = ?",
        (training_purpose_id,),
    )
    connection.execute(
        """
        DELETE FROM workout_type_training_purpose_map
        WHERE primary_training_purpose_id = ? OR secondary_training_purpose_id = ?
        """,
        (training_purpose_id, training_purpose_id),
    )
    connection.execute(
        "DELETE FROM training_purpose WHERE id = ?",
        (training_purpose_id,),
    )
    return int(affected_activity_purposes or 0)


def metadata_choice_sets(connection):
    dropdown_options = load_metadata_dropdown_options(connection)
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
            name_zh,
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
            name_zh,
            purpose_category
        FROM training_purpose
        ORDER BY COALESCE(sort_order, 999), name_en, training_purpose_code
        """
    ).fetchall()
    workout_purpose_maps = connection.execute(
        """
        SELECT
            wt.workout_type_code,
            wt.name_en AS workout_name_en,
            wt.name_zh AS workout_name_zh,
            wt.intensity_category,
            primary_purpose.training_purpose_code AS primary_training_purpose_code,
            primary_purpose.name_en AS primary_training_purpose_name_en,
            primary_purpose.name_zh AS primary_training_purpose_name_zh,
            secondary_purpose.training_purpose_code AS secondary_training_purpose_code,
            secondary_purpose.name_en AS secondary_training_purpose_name_en,
            secondary_purpose.name_zh AS secondary_training_purpose_name_zh
        FROM workout_type AS wt
        LEFT JOIN workout_type_training_purpose_map AS map
            ON map.workout_type_id = wt.id
        LEFT JOIN training_purpose AS primary_purpose
            ON primary_purpose.id = map.primary_training_purpose_id
        LEFT JOIN training_purpose AS secondary_purpose
            ON secondary_purpose.id = map.secondary_training_purpose_id
        ORDER BY COALESCE(wt.sort_order, 999), wt.name_en, wt.workout_type_code
        """
    ).fetchall()
    return dropdown_options, shoes, workouts, purposes, workout_purpose_maps


def metadata_candidates(connection, scope="unassigned", limit=40, offset=0):
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
            workout_type_name_zh,
            primary_training_purpose_id,
            primary_training_purpose_code,
            primary_training_purpose_name_en,
            primary_training_purpose_name_zh,
            secondary_training_purpose_codes,
            secondary_training_purpose_names_en,
            secondary_training_purpose_names_zh
        FROM activity_review_view
        {clause}
        ORDER BY activity_start_time DESC
        LIMIT ?
        OFFSET ?
        """,
        (limit, offset),
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


def metadata_scope_total(scope_counts, scope):
    if scope_counts is None:
        return 0
    mapping = {
        "unassigned": "unassigned",
        "missing_shoe": "missing_shoe",
        "missing_workout": "missing_workout",
        "missing_purpose": "missing_purpose",
        "all": "total",
        "complete": "complete",
    }
    key = mapping.get(scope, "unassigned")
    return int(scope_counts[key] or 0)


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
            workout_type_name_zh,
            primary_training_purpose_id,
            primary_training_purpose_code,
            primary_training_purpose_name_en,
            primary_training_purpose_name_zh,
            secondary_training_purpose_codes,
            secondary_training_purpose_names_en,
            secondary_training_purpose_names_zh
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
    provenance_source="manual",
):
    ensure_metadata_dimensions(connection, load_metadata_dropdown_options(connection))
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
    purpose_codes = []
    if primary_purpose_code:
        purpose_codes.append(primary_purpose_code)
    if secondary_purpose_code and secondary_purpose_code != primary_purpose_code:
        purpose_codes.append(secondary_purpose_code)
    replace_activity_training_purposes_by_code(connection, activity_id, purpose_codes, provenance_source)

    if shoe_code:
        record_activity_metadata_provenance(connection, activity_id, "shoe", provenance_source)
    else:
        clear_activity_metadata_provenance(connection, activity_id, "shoe")

    if workout_type_code:
        record_activity_metadata_provenance(connection, activity_id, "workout_type", provenance_source)
    else:
        clear_activity_metadata_provenance(connection, activity_id, "workout_type")


def replace_activity_training_purposes_by_code(connection, activity_id, purpose_codes, provenance_source="manual"):
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
    if purpose_codes:
        record_activity_metadata_provenance(connection, activity_id, "primary_purpose", provenance_source)
        if len(purpose_codes) > 1:
            record_activity_metadata_provenance(connection, activity_id, "secondary_purpose", provenance_source)
        else:
            clear_activity_metadata_provenance(connection, activity_id, "secondary_purpose")
    else:
        clear_activity_metadata_provenance(connection, activity_id, "primary_purpose")
        clear_activity_metadata_provenance(connection, activity_id, "secondary_purpose")
    record_coach_knowledge_shoe_memory(connection, activity_id)


def apply_batch_metadata_update(
    connection,
    activity_ids,
    shoe_action,
    workout_action,
    primary_action,
    secondary_action,
    provenance_source="manual",
):
    if not activity_ids:
        return 0
    ensure_metadata_dimensions(connection, load_metadata_dropdown_options(connection))
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
            replace_activity_training_purposes_by_code(connection, activity_id, labels, provenance_source)
        if shoe_action != "__KEEP__":
            if shoe_action == "__CLEAR__":
                clear_activity_metadata_provenance(connection, activity_id, "shoe")
            else:
                record_activity_metadata_provenance(connection, activity_id, "shoe", provenance_source)
        if workout_action != "__KEEP__":
            if workout_action == "__CLEAR__":
                clear_activity_metadata_provenance(connection, activity_id, "workout_type")
            else:
                record_activity_metadata_provenance(connection, activity_id, "workout_type", provenance_source)
        if not purpose_should_replace:
            record_coach_knowledge_shoe_memory(connection, activity_id)
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


def weekly_history_with_labels(connection, rows):
    labeled = []
    for row in rows or []:
        intelligence = selected_week_intelligence(connection, row["week_offset"])
        review = weekly_review_payload(row, intelligence) if intelligence else None
        labeled.append({
            "row": row,
            "coach_label": review["verdict"] if review else "—",
        })
    return labeled


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


def coach_knowledge_summary(connection, start_date, end_date, period_label):
    if not start_date or not end_date:
        return None

    rows = connection.execute(
        """
        SELECT
            activity_id,
            activity_date,
            activity_start_time,
            shoe_id,
            shoe_display_name,
            workout_type_id,
            workout_type_name_en,
            workout_type_name_zh,
            primary_training_purpose_id,
            primary_training_purpose_name_en,
            primary_training_purpose_name_zh
        FROM activity_review_view
        WHERE activity_date BETWEEN ? AND ?
        ORDER BY activity_start_time ASC
        """,
        (start_date, end_date),
    ).fetchall()

    complete_rows = [
        row for row in rows
        if row["shoe_id"] is not None
        and row["workout_type_id"] is not None
        and row["primary_training_purpose_id"] is not None
    ]

    if not complete_rows:
        return {
            "headline": f"{period_label}的教練知識還在累積",
            "detail": "目前還沒有完整確認的活動可以回流到判讀，先讓第一批確認慢慢堆起來。",
            "count": 0,
            "proof_lines": [],
            "confirmed_activities": [],
        }

    workout_counts = Counter()
    purpose_counts = Counter()
    shoe_counts = Counter()

    for row in complete_rows:
        workout_label = str(row["workout_type_name_zh"] or row["workout_type_name_en"] or "未標註").strip()
        purpose_label = str(row["primary_training_purpose_name_zh"] or row["primary_training_purpose_name_en"] or "未標註").strip()
        shoe_label = str(row["shoe_display_name"] or "未標註").strip()
        workout_counts[workout_label] += 1
        purpose_counts[purpose_label] += 1
        shoe_counts[shoe_label] += 1

    shoe_types = len(shoe_counts)
    workout_types = len(workout_counts)
    purpose_types = len(purpose_counts)

    proof_lines = [
        f"✓ {len(complete_rows)} 堂已確認活動",
        f"✓ 已確認內容涵蓋 {shoe_types} 種鞋款 / {workout_types} 種課表 / {purpose_types} 種目的",
    ]

    if workout_counts:
        workout_label, workout_count = workout_counts.most_common(1)[0]
        proof_lines.append(f"✓ 最常見課表：{workout_label}（{workout_count} 堂）")
    if purpose_counts:
        purpose_label, purpose_count = purpose_counts.most_common(1)[0]
        proof_lines.append(f"✓ 最常見目的：{purpose_label}（{purpose_count} 堂）")
    if shoe_counts:
        shoe_label, shoe_count = shoe_counts.most_common(1)[0]
        shoe_suffix = "次" if shoe_count == 1 else "次"
        proof_lines.append(f"✓ 最常見鞋款：{shoe_label}（{shoe_count} {shoe_suffix}）")

    headline = f"{period_label}的判讀已建立在 {len(complete_rows)} 堂已確認活動上"
    detail = f"已確認內容涵蓋 {shoe_types} 種鞋款、{workout_types} 種課表、{purpose_types} 種目的；最常見鞋款是 {shoe_counts.most_common(1)[0][0]}（{shoe_counts.most_common(1)[0][1]} 次）。" if shoe_counts else "這個區間的已確認知識正在累積。"

    return {
        "headline": headline,
        "detail": detail,
        "count": len(complete_rows),
        "proof_lines": proof_lines,
        "confirmed_activities": complete_rows,
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


def weekly_review_payload(weekly, intelligence, knowledge_summary=None):
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
    knowledge_headline = None
    knowledge_detail = None
    if knowledge_summary:
        knowledge_headline = knowledge_summary["headline"]
        knowledge_detail = knowledge_summary["detail"]
        if knowledge_summary["count"]:
            why = f"{why} {knowledge_headline} {knowledge_detail}"

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
        "knowledge_headline": knowledge_headline,
        "knowledge_detail": knowledge_detail,
        "knowledge_count": knowledge_summary["count"] if knowledge_summary else 0,
        "cause_question": "什麼真正讓你學會了這件事？",
        "evidence_intro": evidence_intro,
        "reasoning_steps": [
            ("先看學習", "#weekly-learning"),
            ("再看形成原因", "#weekly-cause"),
            ("再看關鍵課", "#weekly-key-activities"),
            ("AI 延伸分析", "#weekly-ai-handoff"),
        ],
    }


def activity_split_summary(split_rows):
    analysis_rows = activity_analysis_splits(split_rows)
    if not analysis_rows:
        return {
            "pace_change_sec": None,
            "hr_change": None,
            "first_pace": None,
            "last_pace": None,
        }
    first = analysis_rows[0]
    last = analysis_rows[-1]
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


def activity_focus_splits(activity, split_rows, workout_split_rows=None):
    structured_rows = structured_focus_splits(split_rows, workout_split_rows or [])
    if structured_rows:
        return structured_rows
    analysis_rows = activity_analysis_splits(split_rows)
    if not analysis_rows:
        return []
    workout = str(activity["workout_type_name_en"] or activity["activity_type"] or "").lower()
    threshold_workout = any(token in workout for token in ("tempo", "threshold", "marathon pace"))
    interval_workout = any(token in workout for token in ("interval", "repetition", "fartlek"))
    quality_workout = threshold_workout or interval_workout
    long_run = any(token in workout for token in ("long run", "lsd")) or float(activity["distance_km"] or 0) >= 18
    easy_run = any(token in workout for token in ("easy", "recovery"))
    if quality_workout:
        if threshold_workout and len(analysis_rows) >= 10:
            return analysis_rows[2:-2]
        if interval_workout and len(analysis_rows) >= 8:
            return analysis_rows[1:-1]
        if len(analysis_rows) >= 8:
            return analysis_rows[2:-2]
        if len(analysis_rows) >= 6:
            return analysis_rows[1:-1]
    if long_run:
        if len(analysis_rows) >= 10:
            return analysis_rows[1:-1]
        if len(analysis_rows) >= 6:
            return analysis_rows[1:]
    if easy_run and len(analysis_rows) >= 6:
        return analysis_rows[1:-1]
    return analysis_rows


def activity_focus_segment_labels(activity, focus_rows, all_rows, workout_split_rows=None):
    if not focus_rows:
        return {
            "start": "起跑節奏",
            "middle": "中段反應",
            "finish": "收尾狀態",
        }
    if structured_focus_splits(all_rows, workout_split_rows or []):
        return {
            "start": "主段起點",
            "middle": "主段中段",
            "finish": "主段收尾",
        }
    if len(focus_rows) == len(all_rows):
        return {
            "start": "起跑節奏",
            "middle": "中段反應",
            "finish": "收尾狀態",
        }
    workout = str(activity["workout_type_name_en"] or activity["activity_type"] or "").lower()
    threshold_workout = any(token in workout for token in ("tempo", "threshold", "marathon pace"))
    interval_workout = any(token in workout for token in ("interval", "repetition", "fartlek"))
    quality_workout = threshold_workout or interval_workout
    long_run = any(token in workout for token in ("long run", "lsd")) or float(activity["distance_km"] or 0) >= 18
    if quality_workout:
        return {
            "start": "主體起點",
            "middle": "主體中段",
            "finish": "主體收尾",
        }
    if long_run:
        return {
            "start": "耐力進入點",
            "middle": "耐力中段",
            "finish": "耐力後段",
        }
    return {
        "start": "進入主體",
        "middle": "主體中段",
        "finish": "離開主體前",
    }


def split_segment_kind(row):
    distance_m = float(row["split_distance_m"] or 0)
    elapsed_sec = float(row["elapsed_time_sec"] or 0)
    if distance_m <= 0:
        return "unknown"
    if distance_m < 30 or (distance_m < 60 and elapsed_sec <= 10):
        return "residual"
    if distance_m < 150 and elapsed_sec <= 30:
        return "stride"
    if distance_m < 400 and 45 <= elapsed_sec <= 120:
        return "recovery"
    if distance_m < 200:
        return "short"
    return "main"


def is_residual_split(row, min_distance_m=200):
    return split_segment_kind(row) != "main"


def activity_analysis_splits(split_rows):
    if not split_rows:
        return []
    full_rows = [row for row in split_rows if split_segment_kind(row) == "main"]
    return full_rows or split_rows


def use_km_labels_for_split_rows(split_rows):
    main_rows = [row for row in (split_rows or []) if split_segment_kind(row) == "main"]
    if not main_rows:
        return False
    return all(980 <= float(row["split_distance_m"] or 0) <= 1020 for row in main_rows)


def activity_split_label(row, split_rows=None):
    kind = split_segment_kind(row)
    distance_m = float(row["split_distance_m"] or 0)
    if kind == "stride":
        seconds = format_number(row["elapsed_time_sec"], 0) or ""
        return f"Stride 段（{seconds}s）" if seconds else "Stride 段"
    if kind == "recovery":
        seconds = format_number(row["elapsed_time_sec"], 0) or ""
        return f"恢復段（{seconds}s）" if seconds else "恢復段"
    if kind == "short":
        distance_m = format_number(row["split_distance_m"], 0) or "0"
        return f"短片段（{distance_m} m）"
    if kind == "residual":
        distance_m = format_number(row["split_distance_m"], 0) or "0"
        return f"尾端殘段（{distance_m} m）"
    if 980 <= distance_m <= 1020 and use_km_labels_for_split_rows(split_rows):
        return f"KM {row['split_index']}"
    return f"片段 {row['split_index']}"


def split_total_time_sec(split_rows):
    total = 0.0
    has_value = False
    for row in split_rows or []:
        if row["elapsed_time_sec"] is not None:
            total += float(row["elapsed_time_sec"])
            has_value = True
    return total if has_value else None


def split_activity_max_hr(split_rows):
    values = [float(row["max_hr"]) for row in (split_rows or []) if row["max_hr"] is not None]
    return max(values) if values else None


def split_activity_metric_max(split_rows, key):
    values = [float(row[key]) for row in (split_rows or []) if row[key] is not None]
    return max(values) if values else None


def split_activity_metric_min(split_rows, key):
    values = [float(row[key]) for row in (split_rows or []) if row[key] is not None]
    return min(values) if values else None


def split_activity_metric_sum(split_rows, key):
    total = 0.0
    has_value = False
    for row in split_rows or []:
        value = row[key]
        if value is None:
            continue
        total += float(value)
        has_value = True
    return total if has_value else None


def split_activity_metric_avg(split_rows, key):
    values = [float(row[key]) for row in (split_rows or []) if row[key] is not None]
    return (sum(values) / len(values)) if values else None


def activity_review_payload(activity, split_rows, workout_split_rows=None):
    workout = str(activity["workout_type_name_en"] or activity["activity_type"] or "").lower()
    distance = float(activity["distance_km"] or 0)
    training_load = float(activity["training_load"] or 0)
    temperature = activity["temperature_c"]
    stamina_start = activity["stamina_start_pct"]
    stamina_end = activity["stamina_end_pct"]
    stamina_drop = None
    if stamina_start is not None and stamina_end is not None:
        stamina_drop = float(stamina_start) - float(stamina_end)
    structured_focus = structured_focus_splits(split_rows, workout_split_rows or [])
    structured_active_rows = structured_active_segment_rows(workout_split_rows or [])
    has_structured_recovery = any(
        workout_segment_kind(row) == "recovery" for row in (workout_split_rows or [])
    )
    has_short_active_segments = any(
        workout_segment_kind(row) == "active"
        and float(row["total_distance_m"] or 0) < 300
        and float(row["total_timer_time_sec"] or 0) <= 30
        for row in (workout_split_rows or [])
    )
    displayed_workout_rows = display_workout_splits(workout_split_rows or [])
    focus_rows = activity_focus_splits(activity, split_rows, workout_split_rows)
    split_summary = activity_split_summary(focus_rows or split_rows)
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
    elif easy_run and has_short_active_segments:
        learning = "你練到的不是單純把輕鬆跑做完。你練到的是：先把主體節奏跑穩，再用短加速把動作節奏接回來。"
        focus = "這堂課真正留下來的，是穩定主體後把動作重新叫醒。"
        reminder = "下一堂課，只記住一件事：先把 easy 的穩定感守住，再決定要不要把步伐打開。"
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
    elif easy_run and has_short_active_segments:
        why = "這堂課真正有價值的地方，不只是前面的 easy 有沒有穩住，而是最後有沒有把快速動作節奏自然接回來。"
    else:
        why = "這堂課真正重要的，不是數字漂不漂亮，而是它有沒有替整體節奏留下東西。"

    analysis_rows = focus_rows or activity_analysis_splits(split_rows)
    last_split_index = analysis_rows[-1]["split_index"] if analysis_rows else None
    middle_split_index = analysis_rows[len(analysis_rows) // 2]["split_index"] if len(analysis_rows) >= 3 else last_split_index

    cards = []
    if analysis_rows:
        if pace_change is not None:
            pace_label = "後段仍穩" if pace_change <= 8 else "後段回落"
            if structured_active_rows:
                first_active = structured_active_rows[0]
                last_active = structured_active_rows[-1]
                first_active_pace = None if first_active["avg_speed_mps"] in (None, 0) else 1000.0 / float(first_active["avg_speed_mps"])
                last_active_pace = None if last_active["avg_speed_mps"] in (None, 0) else 1000.0 / float(last_active["avg_speed_mps"])
                active_change = None
                if first_active_pace is not None and last_active_pace is not None:
                    active_change = float(last_active_pace) - float(first_active_pace)
                trailing_note = ""
                if len(structured_active_rows) >= 2:
                    previous_active = structured_active_rows[-2]
                    previous_active_pace = None if previous_active["avg_speed_mps"] in (None, 0) else 1000.0 / float(previous_active["avg_speed_mps"])
                    if previous_active_pace is not None and last_active_pace is not None:
                        trailing_change = float(last_active_pace) - float(previous_active_pace)
                        if abs(trailing_change) <= 3:
                            trailing_note = "但後半段已重新穩定，最後一組沒有再明顯回落。"
                            pace_label = "先回落後穩住"
                if len(structured_active_rows) == 1 and pace_change is not None:
                    active_change = pace_change
                if active_change is not None:
                    segment_scope = (
                        "第一組主段到最後一組主段"
                        if len(structured_active_rows) >= 2 and has_structured_recovery
                        else "主段前段到主段後段"
                    )
                    pace_note = (
                        f"{segment_scope}約慢了 {format_number(abs(active_change), 0)} 秒。{trailing_note}".strip()
                        if active_change >= 0 else
                        f"{segment_scope}最後仍比前段快 {format_number(abs(active_change), 0)} 秒。"
                    )
                else:
                    pace_note = "主段節奏有變化，但目前還不能完整比較第一組與最後一組。"
            else:
                pace_note = (
                    f"第一公里到最後一公里約慢了 {format_number(abs(pace_change), 0)} 秒。"
                    if pace_change >= 0 else
                    f"最後一公里仍比開頭快 {format_number(abs(pace_change), 0)} 秒。"
                )
        else:
            pace_label = "節奏待補"
            pace_note = "目前還沒有足夠分段可以比較前後段。"
        cards.append({
            "title": "節奏反應",
            "value": pace_label,
            "note": pace_note,
            "fragment_anchor": "#fragment-finish",
            "evidence_anchor": f"#split-{last_split_index}" if last_split_index is not None else "#activity-evidence",
            "segment_label": "主段收尾" if structured_focus else ("主體收尾" if focus_rows and len(focus_rows) != len(activity_analysis_splits(split_rows)) else "收尾狀態"),
        })

    if training_load:
        load_label = f"負荷 {format_number(training_load, 0)}"
        if distance >= 16:
            load_note = "這堂課本身已經足夠形成耐力或品質壓力。"
        elif easy_run and (
            training_load >= 120
            or (activity["training_effect_aerobic"] is not None and float(activity["training_effect_aerobic"]) >= 3.0)
            or (stamina_drop is not None and stamina_drop >= 20)
        ):
            load_note = "這不是高強度品質課，但仍留下了可辨識的有氧刺激。"
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
            "segment_label": "主段中段" if structured_focus else ("主體中段" if focus_rows and len(focus_rows) != len(activity_analysis_splits(split_rows)) else "中段反應"),
        })

    if is_hot or stamina_drop is not None or hr_change is not None:
        body_parts = []
        if is_hot:
            body_parts.append(f"氣溫 {format_number(temperature, 0)}°C")
        if stamina_drop is not None:
            body_parts.append(f"體力 -{format_number(stamina_drop, 0)}")
        if hr_change is not None:
            hr_scope = "主段起點到主段收尾" if structured_focus else "首末完整公里"
            if hr_change >= 0:
                body_parts.append(f"{hr_scope} HR +{format_number(hr_change, 0)} bpm")
            else:
                body_parts.append(f"{hr_scope} HR {format_number(hr_change, 0)} bpm")
        body_label = " · ".join(body_parts) if body_parts else "身體有回應"
        body_note = (
            "環境與身體回應一起決定了今天該怎麼理解，不只是看單一配速。"
            if is_hot else
            "課程脈絡與身體回應一起決定了今天該怎麼理解，不只是看單一配速。"
        )
        cards.append({
            "title": "身體訊號",
            "value": body_label,
            "note": body_note,
            "fragment_anchor": "#fragment-middle",
            "evidence_anchor": f"#split-{middle_split_index}" if middle_split_index is not None else "#activity-evidence",
            "segment_label": "主段中段" if structured_focus else ("主體中段" if focus_rows and len(focus_rows) != len(activity_analysis_splits(split_rows)) else "中段反應"),
        })

    evidence_intro = "我會這樣看，不是因為單一數字，而是因為這堂課的節奏、刺激與身體回應指向同一個學習。"
    structure_note = ""
    if displayed_workout_rows:
        if easy_run and has_short_active_segments:
            structure_note = "這堂課的主體先看 easy 段，課尾另有短加速與恢復片段，所以主體判讀不會把 stride 混進來。"
        elif has_structured_recovery and len(structured_active_rows) >= 2:
            structure_note = "這堂課有明確主段與恢復切分，所以判讀會先按課表結構理解，再回頭核對原始分段。"
        elif structured_focus:
            structure_note = "這堂課的判讀會先讀課表主體，再用原始分段補證據，不會把暖身、恢復或收操混成同一段。"

    return {
        "learning_question": "這堂課，我真正練到了什麼？",
        "cause_question": "什麼真正讓你學會了這件事？",
        "learning": learning,
        "focus": focus,
        "why": why,
        "looking_forward": reminder,
        "structure_note": structure_note,
        "evidence_intro": evidence_intro,
        "cards": cards[:3],
        "reads_workout_structure": bool(structured_focus),
        "reasoning_steps": [
            ("先看學習", "#activity-learning"),
            ("再看形成原因", "#activity-cause"),
            ("再看關鍵片段", "#activity-segments"),
            ("最後回到證據", "#activity-evidence"),
            ("AI 延伸分析", "#activity-ai-handoff"),
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


def selected_month_distribution(connection, month_key=None, limit=None):
    target_month = selected_month_summary(connection, month_key)
    if not target_month:
        return []
    query = """
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
    """
    params = [target_month["month_start"], target_month["month_end"]]
    if limit is not None:
        query += "\nLIMIT ?"
        params.append(limit)
    return connection.execute(query, tuple(params)).fetchall()


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


def monthly_overview_payload(monthly, intelligence, progress_row, knowledge_summary=None):
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

    knowledge_headline = None
    knowledge_detail = None
    if knowledge_summary:
        knowledge_headline = knowledge_summary["headline"]
        knowledge_detail = knowledge_summary["detail"]

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
        "knowledge_headline": knowledge_headline,
        "knowledge_detail": knowledge_detail,
        "knowledge_count": knowledge_summary["count"] if knowledge_summary else 0,
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
            "target_surface": "weekly",
        }

    primary = ranked[0]
    secondary = ranked[1] if len(ranked) > 1 else None

    def tighten_evidence_line(text):
        return str(text).strip().rstrip("。")

    def surface_link(target_surface):
        if target_surface == "weekly":
            return "查看本週反思", "/?" + urlencode({"page": "weekly"}) + "#weekly-learning"
        if target_surface == "monthly":
            return "查看本月定位", "/?" + urlencode({"page": "monthly"}) + "#monthly-position"
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
        "target_surface": primary.target_surface,
    }


def ai_reply_saved_panel(title, existing_reply=None, return_page="", activity_id="", week="", month=""):
    if not existing_reply:
        return ""
    raw_markdown = existing_reply.get("responseMarkdown", "")
    rendered = render_simple_markdown(raw_markdown)
    saved_at = existing_reply.get("updatedAt", "")
    saved_note = f"儲存於 {saved_at.replace('T', ' ')}" if saved_at else "已儲存"
    if not rendered:
        return ""
    return f"""
      <section class="panel-section">
        <h2>上次 AI 延伸分析</h2>
        <div class="review-card ai-reply-preview">
          <span>{html.escape(saved_note)}</span>
          <strong>{html.escape(title)}</strong>
          <div class="ai-reply-rendered">{rendered}</div>
          <div class="ai-reply-attachments">
            <strong>附加圖檔</strong>
            {render_ai_reply_attachments(existing_reply.get("scope", ""), existing_reply.get("analysisNodeId", ""), return_page, activity_id, week, month)}
          </div>
          <details class="ai-reply-raw">
            <summary>看原始 markdown</summary>
            <textarea readonly>{html.escape(raw_markdown)}</textarea>
          </details>
        </div>
      </section>
    """


def ai_reply_capture_panel(surface, identifier, title, return_page, existing_reply=None, activity_id="", week="", month=""):
    rendered = ""
    raw_markdown = ""
    saved_note = "還沒有貼回過 AI 回覆。"
    if existing_reply:
        raw_markdown = existing_reply.get("responseMarkdown", "")
        rendered = render_simple_markdown(raw_markdown)
        saved_at = existing_reply.get("updatedAt", "")
        saved_note = f"上次儲存：{saved_at.replace('T', ' ')}" if saved_at else "已儲存 AI 回覆"
    action_title = "貼回新的 AI 回覆" if existing_reply else "貼回 AI 回覆"
    lead = (
        "把更新後的 AI 回覆貼在這裡。你可以直接貼上整段內容，不必手動刪除前面的閱讀版。平台會依序尋找：最後一個 "
        "<code>running-intelligence-reply</code> 區塊、最後一個 markdown 區塊，若都沒有，才會使用完整貼上內容。"
        if existing_reply
        else "把你和 AI 繼續分析後的完整回覆貼在這裡。你可以直接貼上整段內容，不必手動刪除前面的閱讀版。平台會依序尋找：最後一個 "
        "<code>running-intelligence-reply</code> 區塊、最後一個 markdown 區塊，若都沒有，才會使用完整貼上內容。"
    )

    return f"""
      <section class="panel-section">
        <h2>{action_title}</h2>
        <div class="review-card ai-handoff-card">
          <span>AI Conversation Loop</span>
          <strong>把你跟 AI 往下聊出的結果存回這一頁</strong>
          <p>{lead}</p>
          <form method="post" action="/ai-replies/save" class="ai-reply-form remember-scroll-form">
            <input type="hidden" name="surface" value="{html.escape(surface, quote=True)}">
            <input type="hidden" name="identifier" value="{html.escape(identifier, quote=True)}">
            <input type="hidden" name="title" value="{html.escape(title, quote=True)}">
            <input type="hidden" name="page" value="{html.escape(return_page, quote=True)}">
            <input type="hidden" name="activity_id" value="{html.escape(str(activity_id), quote=True)}">
            <input type="hidden" name="week" value="{html.escape(str(week), quote=True)}">
            <input type="hidden" name="month" value="{html.escape(str(month), quote=True)}">
            <input type="hidden" name="scroll_y" value="">
            <label class="inline-field">
              <span>貼上 AI 回覆</span>
              <textarea name="ai_reply_raw" data-ai-reply-input="1" placeholder="把 AI 回覆整段貼進來。平台會先解析出實際要保存的內容。">{html.escape(raw_markdown)}</textarea>
            </label>
            <div class="ai-reply-parse-state" data-ai-reply-state>尚未貼上 AI 回覆</div>
            <div class="ai-reply-parsed-preview" data-ai-reply-preview hidden>
              <span>即將保存的內容</span>
              <textarea readonly data-ai-reply-preview-text></textarea>
            </div>
            <div class="ai-handoff-actions">
              <button class="primary-action" type="submit">儲存 AI 回覆</button>
            </div>
          </form>
          <form method="post" action="/ai-replies/upload-image" enctype="multipart/form-data" class="ai-reply-image-form remember-scroll-form">
            <input type="hidden" name="surface" value="{html.escape(surface, quote=True)}">
            <input type="hidden" name="identifier" value="{html.escape(identifier, quote=True)}">
            <input type="hidden" name="title" value="{html.escape(title, quote=True)}">
            <input type="hidden" name="page" value="{html.escape(return_page, quote=True)}">
            <input type="hidden" name="activity_id" value="{html.escape(str(activity_id), quote=True)}">
            <input type="hidden" name="week" value="{html.escape(str(week), quote=True)}">
            <input type="hidden" name="month" value="{html.escape(str(month), quote=True)}">
            <input type="hidden" name="scroll_y" value="">
            <label class="inline-field">
              <span>附加圖檔</span>
              <input type="file" name="ai_reply_image" accept="image/*">
            </label>
            <div class="ai-handoff-actions">
              <button class="secondary-action" type="submit">上傳圖檔</button>
            </div>
          </form>
          <div class="ai-reply-attachments">
            <strong>目前附加圖檔</strong>
            {render_ai_reply_attachments(surface, identifier, return_page, activity_id, week, month)}
          </div>
          <p class="note">{html.escape(saved_note)}</p>
        </div>
      </section>
    """


def overview_reasoning_route_panel(attention, weekly_review, monthly_overview, latest_activity):
    if not attention:
        return ""

    latest_activity_href = None
    latest_activity_line = ""
    if latest_activity:
        latest_activity_href = "/?" + urlencode({"page": "activity", "activity": latest_activity["activity_id"]})
        latest_activity_line = (
            f"{format_short_datetime(latest_activity['activity_start_time'])} · "
            f"{format_number(latest_activity['distance_km'], 2)} km"
        )

    routes = []
    target_surface = attention.get("target_surface") or "weekly"
    if target_surface == "monthly":
        routes.append({
            "label": "第一步",
            "title": "先看月回顧",
            "body": monthly_overview["verdict_reason"] if monthly_overview else "先確認你現在位於哪個訓練位置。",
            "href": "/?" + urlencode({"page": "monthly"}) + "#monthly-position",
        })
        routes.append({
            "label": "第二步",
            "title": "再看本週怎麼接",
            "body": weekly_review["focus"] if weekly_review else "再確認這一週有沒有把這個方向接住。",
            "href": "/?" + urlencode({"page": "weekly"}) + "#weekly-learning",
        })
        if latest_activity_href:
            routes.append({
                "label": "第三步",
                "title": "最後回到單堂課",
                "body": f"如果想一路追到底，就回到最近那堂課：{latest_activity_line}",
                "href": latest_activity_href + "#activity-learning",
            })
    elif target_surface == "shoes":
        routes.append({
            "label": "第一步",
            "title": "先看鞋款頁",
            "body": "先確認今天需要留意的是哪雙鞋，以及目前鞋款資料夠不夠乾淨。",
            "href": "/?" + urlencode({"page": "shoes"}),
        })
        routes.append({
            "label": "第二步",
            "title": "必要時回到資料標註",
            "body": "如果鞋款判讀還不夠乾淨，再補鞋款與課表標註。",
            "href": "/?" + urlencode({"page": "settings"}),
        })
    else:
        routes.append({
            "label": "第一步",
            "title": "先看週回顧",
            "body": weekly_review["focus"] if weekly_review else "先確認這週真正留下來的學習是什麼。",
            "href": "/?" + urlencode({"page": "weekly"}) + "#weekly-learning",
        })
        if latest_activity_href:
            routes.append({
                "label": "第二步",
                "title": "再追到那堂關鍵課",
                "body": f"如果想知道這個學習是怎麼長出來的，就回到最近那堂課：{latest_activity_line}",
                "href": latest_activity_href + "#activity-learning",
            })
        routes.append({
            "label": "第三步",
            "title": "最後回到月位置",
            "body": monthly_overview["verdict_reason"] if monthly_overview else "最後再確認這週學習放回整個月後，方向有沒有對齊。",
            "href": "/?" + urlencode({"page": "monthly"}) + "#monthly-position",
        })

    return f"""
      <section class="panel-section">
        <h2>如果你要一路追下去</h2>
        <div class="coach-desk-route-grid">
          {"".join(
              f'''
              <a class="coach-route-card" href="{html.escape(route["href"], quote=True)}">
                <span>{html.escape(route["label"])}</span>
                <strong>{html.escape(route["title"])}</strong>
                <p>{html.escape(route["body"])}</p>
              </a>
              '''
              for route in routes
          )}
        </div>
      </section>
    """


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


def overview_ai_handoff_text(attention, weekly_review, monthly_overview, latest_activity, saved_reply=None):
    if not attention:
        return ""

    def safe_text(value, fallback="—"):
        if value is None:
            return fallback
        text = str(value).strip()
        return text if text else fallback

    target_surface = attention.get("target_surface") or "weekly"
    surface_label_map = {
        "activity": "單堂課",
        "weekly": "週回顧",
        "monthly": "月回顧",
        "shoes": "鞋款",
    }
    target_label = surface_label_map.get(target_surface, "下一頁")

    prompt_lines = [
        "請根據以下已治理的跑步資料，用繁體中文做進一步分析。",
        "請先回答今天最該先把注意力放在哪裡，再說明為什麼，最後建議我應該先往哪一頁繼續看。",
        "只能根據我提供的內容分析，不要自行發明額外訓練、健康或心理狀態。",
    ]
    prompt_lines.extend(
        coach_prompt_reference_lines(
            "總覽 AI 交棒",
            "今天焦點、下一步入口與跨頁教練脈絡",
            [
                "先回答今天最該先把注意力放在哪裡",
                "再說明為什麼平台會把這個焦點推到前面",
                "最後建議先往哪一頁繼續看",
                "如果有額外觀察，請明確區分平台判讀與你補充的觀察",
            ],
            [
                "今日焦點 / 為什麼是現在 / 主要入口 / 延伸連結",
                "週脈絡",
                "月脈絡",
                "最新活動",
            ],
            [
                "只能根據提供內容分析，不要自行發明額外訓練、健康或心理狀態。",
                "如果不同 context 彼此有張力，請指出張力，不要直接覆蓋平台目前的注意力判斷。",
            ],
        )
    )
    prompt_lines.extend([
        "",
        "## 總覽事實",
        f"- 今日焦點：{safe_text(attention.get('title'))}",
        f"- 為什麼是現在：{safe_text(attention.get('why'))}",
        f"- 主要入口：{target_label}",
        f"- 延伸連結：{safe_text(attention.get('cta'))}",
    ])

    if attention.get("secondary_note"):
        prompt_lines.append(f"- 次要補充：{safe_text(attention.get('secondary_note'))}")

    if attention.get("evidence"):
        prompt_lines.extend([
            "",
            "## 教練注意力",
            *[f"- {item}" for item in attention["evidence"]],
        ])

    if weekly_review:
        prompt_lines.extend([
            "",
            "## 週脈絡",
            f"- 焦點：{safe_text(weekly_review.get('focus'))}",
            f"- 學習：{safe_text(weekly_review.get('learning'))}",
            f"- 下一步：{safe_text(weekly_review.get('looking_forward'))}",
        ])

    if monthly_overview:
        prompt_lines.extend([
            "",
            "## 月脈絡",
            f"- 位置：{safe_text(monthly_overview.get('verdict'))}",
            f"- 階段：{safe_text(monthly_overview.get('phase'))}",
            f"- 摘要：{safe_text(monthly_overview.get('verdict_reason'))}",
        ])
        if monthly_overview.get("progress_pct") is not None:
            prompt_lines.append(f"- 進度：{format_number(monthly_overview['progress_pct'], 0)}%")

    if latest_activity:
        prompt_lines.extend([
            "",
            "## 最新活動",
            f"- 日期：{safe_text(format_short_datetime(latest_activity['activity_start_time']))}",
            f"- 活動：{safe_text(latest_activity['activity_name'] or latest_activity['activity_type'] or '活動')}",
            f"- 距離：{format_number(latest_activity['distance_km'], 2) or '—'} km",
            f"- 配速：{format_pace_seconds(latest_activity['avg_pace_sec_per_km']) or '—'}",
            f"- 心率：{'' if latest_activity['avg_hr'] is None else int(round(latest_activity['avg_hr']))}",
            f"- 負荷：{format_number(latest_activity['training_load'], 1) or '—'}",
            f"- 課表：{safe_text(latest_activity['workout_type_name_en'] or '未標註')}",
            f"- 目的：{safe_text(latest_activity['primary_training_purpose_name_en'] or '未標註')}",
            f"- 鞋款：{safe_text(latest_activity['shoe_display_name'] or '未標註')}",
        ])

    append_previous_ai_response(prompt_lines, saved_reply)

    prompt_lines.extend([
        "",
        "## 指示",
        "- 先講今天最該先把注意力放在哪裡。",
        "- 再解釋平台為什麼會先把這個焦點推到前面。",
        "- 最後建議我應該先去單堂課、週回顧、月回顧或鞋款哪一頁繼續看。",
        "- 如果你從週、月或最新活動脈絡看見平台尚未明說、但值得注意的補充，可以提出。",
        "- 但請明確區分：哪些是平台已經判讀的，哪些是你根據脈絡額外補充的觀察。",
        "- 如果不同脈絡彼此有張力，請指出張力，不要直接覆蓋平台目前的注意力判斷。",
    ])
    prompt_lines.extend([""] + ai_handoff_response_format_instructions())

    return "\n".join(prompt_lines)


def overview_ai_handoff_panel(attention, weekly_review, monthly_overview, latest_activity, saved_reply=None):
    handoff_text = overview_ai_handoff_text(attention, weekly_review, monthly_overview, latest_activity, saved_reply)
    if not handoff_text:
        return ""

    saved_panel = ai_reply_saved_panel("今天的總覽 AI 回覆", saved_reply, "home")
    capture_panel = ai_reply_capture_panel("overview", date.today().isoformat(), "今天的總覽 AI 回覆", "home", saved_reply)

    return f"""
      {saved_panel}
      <section class="panel-section" id="overview-ai-handoff">
        <h2>AI 延伸分析</h2>
        <div class="review-card ai-handoff-card">
          <span>AI 交棒</span>
          <strong>把今天的注意力焦點直接交給你習慣的 AI</strong>
          <p>如果你看完總覽後，想沿著平台已經整理好的注意力、上下文與下一步入口繼續往下聊，這裡就是完整交棒內容。</p>
          <div class="ai-handoff-block">
            <div class="ai-handoff-block-head">
              <div>
                <strong>完整交棒內容</strong>
                <p class="note">包含今天焦點、週／月脈絡與最近一堂課。</p>
              </div>
              <div class="ai-handoff-actions">
                <button class="secondary-action" type="button" onclick="copyAiHandoff('overview-ai-handoff-text')">複製給 AI</button>
              </div>
            </div>
            <details class="ai-handoff-preview">
              <summary>先看會交出去的內容</summary>
              <textarea id="overview-ai-handoff-text" readonly>{html.escape(handoff_text)}</textarea>
            </details>
          </div>
          <p class="note" id="overview-ai-handoff-status">先看完總覽，再複製交給你習慣的 AI 繼續分析。</p>
        </div>
      </section>
      {capture_panel}
    """


def coach_desk_panel(attention, weekly_review, monthly_overview, monthly_review, story, latest_activity, saved_reply=None):
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
    activity_href = "/?" + urlencode({"page": "activity", "activity": latest_activity["activity_id"]}) if latest_activity else ""

    weekly_line = weekly_review["focus"] if weekly_review else "先讓這週的節奏說話。"
    monthly_line = first_sentence(monthly_review["coach_summary"]) if monthly_review else "先把這個月的方向看清楚。"
    activity_line = ""
    if latest_activity:
        activity_line = (
            f"{format_short_datetime(latest_activity['activity_start_time'])} · "
            f"{format_number(latest_activity['distance_km'], 2)} km · "
            f"{format_pace_seconds(latest_activity['avg_pace_sec_per_km'])}"
        )
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
          {f'''
          <a class="coach-route-card" href="{html.escape(activity_href, quote=True)}">
            <span>單堂課</span>
            <strong>剛剛那堂課留下了什麼</strong>
            <p>{html.escape(activity_line)}</p>
          </a>
          ''' if latest_activity else ""}
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
      {overview_reasoning_route_panel(attention, weekly_review, monthly_overview, latest_activity)}
      {overview_ai_handoff_panel(attention, weekly_review, monthly_overview, latest_activity, saved_reply)}
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
    status = "CoachOS Import Studio 已就緒" if rac_is_running() else "從這裡進入 CoachOS Import Studio"
    note = (
        "把 FIT 轉成 Excel、補活動資訊、寫回 SQLite，然後再回到 CoachOS 繼續看活動、週回顧與月回顧。"
    )
    return f"""
      <section class="panel-section">
        <h2>資料入口</h2>
        <div class="coach-attention-card">
          <span>資料匯入工具</span>
          <strong>先進入 CoachOS Import Studio</strong>
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
          <p>這不是錯誤。先進入資料匯入工具匯入第一批 FIT，平台就會開始長出活動、週回顧、月回顧與總覽。</p>
          <ul class="coach-attention-evidence">
            <li>先選一個或幾個 FIT 檔</li>
            <li>轉成 Excel 並寫回 SQLite</li>
            <li>回到平台重新整理，就能開始看教練式回顧</li>
          </ul>
          <div class="coach-attention-footer">
            <a class="desk-link" href="/open-rac">先進入資料匯入工具</a>
            <small>第一批資料匯入後，首頁會自動變成真正的總覽。</small>
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
            workout_type_name_zh,
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
            workout_type_name_zh,
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
                review.activity_id,
                activity.garmin_activity_id,
                activity.source_file_name,
                activity.data_source,
                activity.excel_schema_version,
                review.activity_start_time,
                review.activity_type,
                review.activity_name,
                review.distance_km,
                review.duration_sec,
                review.workout_type_id,
                review.workout_type_code,
                review.shoe_id,
                review.shoe_code,
                review.workout_type_name_en,
                review.workout_type_name_zh,
                review.shoe_display_name,
                review.primary_training_purpose_id,
                review.primary_training_purpose_code,
                review.primary_training_purpose_name_en,
                review.primary_training_purpose_name_zh,
                review.secondary_training_purpose_names_en,
                review.secondary_training_purpose_names_zh,
                review.avg_pace_sec_per_km,
                review.avg_hr,
                review.max_hr,
                review.training_load,
                review.training_effect_aerobic,
                review.training_effect_anaerobic,
                review.recovery_time_hr,
                review.stamina_start_pct,
                review.stamina_end_pct,
                review.temperature_c,
                review.humidity_pct,
                review.wind_speed_mps,
                review.wind_direction_deg,
                review.weather_description,
                review.avg_cadence_spm,
                review.avg_stride_length_mm,
                review.avg_gct_ms,
                review.avg_vertical_oscillation_mm,
                review.avg_vertical_ratio_pct,
                review.start_latitude,
                review.start_longitude,
                review.end_latitude,
                review.end_longitude,
                activity.critical_power_w,
                review.nutrition,
                review.notes,
                review.garmin_feeling,
                review.garmin_perceived_effort
            FROM activity_review_view AS review
            JOIN activity
              ON activity.id = review.activity_id
            WHERE review.activity_id = ?
            """,
            (activity_id,),
        ).fetchone()
        if row:
            return row
    return connection.execute(
        """
        SELECT
            review.activity_id,
            activity.garmin_activity_id,
            activity.source_file_name,
            activity.data_source,
            activity.excel_schema_version,
            review.activity_start_time,
            review.activity_type,
            review.activity_name,
            review.distance_km,
            review.duration_sec,
            review.workout_type_id,
            review.workout_type_code,
            review.shoe_id,
            review.shoe_code,
            review.workout_type_name_en,
            review.workout_type_name_zh,
            review.shoe_display_name,
            review.primary_training_purpose_id,
            review.primary_training_purpose_code,
            review.primary_training_purpose_name_en,
            review.primary_training_purpose_name_zh,
            review.secondary_training_purpose_names_en,
            review.secondary_training_purpose_names_zh,
            review.avg_pace_sec_per_km,
            review.avg_hr,
            review.max_hr,
            review.training_load,
            review.training_effect_aerobic,
            review.training_effect_anaerobic,
            review.recovery_time_hr,
            review.stamina_start_pct,
            review.stamina_end_pct,
            review.temperature_c,
            review.humidity_pct,
            review.wind_speed_mps,
            review.wind_direction_deg,
            review.weather_description,
            review.avg_cadence_spm,
            review.avg_stride_length_mm,
            review.avg_gct_ms,
            review.avg_vertical_oscillation_mm,
            review.avg_vertical_ratio_pct,
            review.start_latitude,
            review.start_longitude,
            review.end_latitude,
            review.end_longitude,
            activity.critical_power_w,
            review.nutrition,
            review.notes,
            review.garmin_feeling,
            review.garmin_perceived_effort
        FROM activity_review_view AS review
        JOIN activity
          ON activity.id = review.activity_id
        ORDER BY review.activity_start_time DESC
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
            elapsed_time_sec,
            elapsed_pace_sec_per_km,
            avg_hr,
            max_hr,
            avg_power_w,
            avg_cadence_spm,
            avg_stride_length_mm,
            avg_gct_ms,
            avg_vertical_ratio_pct,
            avg_vertical_oscillation_mm,
            elevation_gain_m,
            elevation_loss_m,
            stamina_start_pct,
            stamina_end_pct
        FROM kilometer_split_view
        WHERE activity_id = ?
        ORDER BY split_index
        """,
        (activity_id,),
    ).fetchall()


def workout_structure_splits(connection, activity_id):
    if not activity_id:
        return []
    return connection.execute(
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


def summarize_workout_structure_rows(workout_rows):
    rows = display_workout_splits(workout_rows or [])
    if not rows:
        return ""
    warmup_distance = 0.0
    cooldown_distance = 0.0
    main_distances = []
    stride_count = 0
    recovery_count = 0
    recovery_distance = 0.0
    other_parts = []
    for row in rows:
        kind = workout_segment_kind(row)
        distance_m = float(row["total_distance_m"] or 0)
        duration_sec = float(row["total_timer_time_sec"] or 0)
        if kind == "warmup":
            warmup_distance += distance_m
            continue
        if kind == "cooldown":
            cooldown_distance += distance_m
            continue
        if kind == "recovery":
            recovery_count += 1
            recovery_distance += distance_m
            continue
        if kind == "active":
            if distance_m < 300 and duration_sec <= 30:
                stride_count += 1
            else:
                main_distances.append(distance_m)
            continue
        label = str(workout_split_label(row) or "").strip()
        if not label:
            continue
        if label.lower().startswith("rwd_"):
            continue
        other_parts.append(label)

    parts = []
    if warmup_distance > 0:
        parts.append(f"WU {format_number(warmup_distance / 1000, 2)} km")
    if main_distances:
        if len(main_distances) == 1:
            if not stride_count and recovery_count == 0 and warmup_distance == 0 and cooldown_distance == 0:
                parts.append(f"連續跑步 {format_number(main_distances[0] / 1000, 2)} km")
            else:
                parts.append(f"主段 {format_number(main_distances[0] / 1000, 2)} km")
        else:
            main_km = " / ".join(format_number(distance / 1000, 2) for distance in main_distances[:4])
            suffix = " ..." if len(main_distances) > 4 else ""
            parts.append(f"主段 {len(main_distances)} 組（{main_km} km{suffix}）")
    if stride_count:
        stride_text = f"{stride_count} 次 Stride"
        if recovery_count:
            stride_text += f" + {recovery_count} 段恢復"
        parts.append(stride_text)
    elif recovery_count:
        recovery_km = format_number(recovery_distance / 1000, 2) if recovery_distance > 0 else "—"
        parts.append(f"{recovery_count} 段恢復（共 {recovery_km} km）")
    if cooldown_distance > 0:
        parts.append(f"CD {format_number(cooldown_distance / 1000, 2)} km")
    if other_parts:
        parts.append(" / ".join(other_parts[:2]))
    return "；".join(parts)


def key_session_workout_structure_summary(connection, key_session_rows, limit=4):
    if not connection or not key_session_rows:
        return []
    summary_rows = []
    seen = set()
    for row in key_session_rows:
        activity_id = row["activity_id"]
        if not activity_id or activity_id in seen:
            continue
        seen.add(activity_id)
        workout_rows = workout_structure_splits(connection, activity_id)
        summary = summarize_workout_structure_rows(workout_rows)
        if not summary:
            continue
        summary_rows.append({
            "activity_id": activity_id,
            "activity": str(row["activity_name"] or row["activity_type"] or "活動"),
            "date": format_short_datetime(row["activity_start_time"]),
            "workout": str(row["workout_type_name_en"] or "未標註"),
            "summary": summary,
        })
        if len(summary_rows) >= limit:
            break
    return summary_rows


def workout_structure_pattern_insights(summary_rows, period_label="本週"):
    if not summary_rows:
        return []
    lines = []
    has_stride = any("Stride" in row["summary"] for row in summary_rows)
    interval_rows = [row for row in summary_rows if "主段 " in row["summary"] and "組（" in row["summary"]]
    long_main_rows = []
    continuous_rows = []
    for row in summary_rows:
        summary = row["summary"]
        if "連續跑步 " in summary:
            continuous_rows.append(row)
            continue
        if "主段 " in summary and "組（" not in summary and "Stride" not in summary:
            long_main_rows.append(row)

    if interval_rows:
        workouts = "、".join(row["workout"] for row in interval_rows[:2])
        lines.append(f"{period_label}的品質刺激不是單點出現，而是用明確主段組合反覆建立，像 {workouts} 這樣的課表型態很清楚。")
    if has_stride:
        lines.append(f"{period_label}不只是在累積主體里程，還有課尾短加速把動作節奏重新接回來。")
    if continuous_rows:
        workouts = "、".join(row["workout"] for row in continuous_rows[:2])
        lines.append(f"{period_label}也保留了連續跑完的主體課，像 {workouts} 這類課表更像是在穩穩維持整體節奏。")
    if long_main_rows:
        workouts = "、".join(row["workout"] for row in long_main_rows[:2])
        lines.append(f"{period_label}也保留了較長的連續主體，像 {workouts} 這類課表更像是在維持整體節奏與耐力主線。")
    if not lines:
        lines.append(f"{period_label}目前已有可辨識的課表型態，代表判讀不只是看課名，也開始看主段、恢復與收尾是怎麼組成的。")
    return lines[:3]


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
        return '<p class="note">目前沒有分段可畫趨勢。</p>'
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
        ("settings", "設定"),
    ]
    links = []
    for slug, label in items:
        is_active = slug == page
        css_class = "nav-link active" if is_active else "nav-link"
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
        <p class="note">週回顧只保留最近 5 週，讓這一頁專注在短期學習。更早以前的資料先留在背景裡，不打斷這一週真正留下來的東西。</p>
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


def monthly_briefing_why_points(monthly, intelligence, progress_row, coach_memory=None, knowledge_summary=None):
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

    if knowledge_summary and knowledge_summary.get("count"):
        points.append(
            f"教練知識已累積 {knowledge_summary['count']} 堂已確認活動，月回顧的判讀會更偏向已確認的訓練脈絡。"
        )

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
        href = "/?" + urlencode({"page": "weekly", "week": row["week_offset"]}) + "#weekly-learning"
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


def weekly_reasoning_rows(intelligence, distribution_rows):
    if not intelligence:
        return []

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
            return ("down", f"較基準 {format_delta_pct(delta)}")
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

    return [
        {"label": "負荷節奏", "level": load_level, "note": load_note},
        {"label": "跑量節奏", "level": km_level, "note": km_note},
        {"label": "刺激安排", "level": stimulus_level_value, "note": stimulus_note},
    ]


def weekly_learning_driver_card(intelligence, distribution_rows):
    if not intelligence:
        return ""

    load_delta = intelligence["load_delta"]
    reasoning_rows = weekly_reasoning_rows(intelligence, distribution_rows)

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
          {"".join(driver_row(row["label"], row["level"], row["note"]) for row in reasoning_rows)}
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


def weekly_ai_handoff_text(
    weekly,
    intelligence,
    review,
    distribution_rows,
    key_session_rows,
    workout_structure_summary_rows,
    history_rows,
    history_rows_with_labels=None,
    monthly_overview=None,
    overview_attention=None,
    knowledge_summary=None,
    wsi_summary=None,
    include_raw_data=False,
    saved_reply=None,
):
    if not weekly or not intelligence or not review:
        return ""

    period_text = f"{weekly['start_date']} – {weekly['end_date']}"
    total_km = f"{format_number(weekly['total_km'], 1)} km"
    load_text = format_number(weekly["training_load"], 0) or "—"
    activities_text = str(weekly["activities"] or 0)
    avg_pace_text = format_pace_seconds(weekly["avg_pace_sec_per_km"]) or "—"
    avg_hr_text = "" if weekly["avg_hr"] is None else str(int(round(weekly["avg_hr"])))
    distribution_snapshot = weekly_distribution_snapshot(distribution_rows)
    confidence = "High"
    if intelligence["load_delta"] is None or intelligence["km_delta"] is None:
        confidence = "Medium"

    cause_lines = [
        f"- {row['label']}：{row['note']}"
        for row in weekly_reasoning_rows(intelligence, distribution_rows)
    ]
    if review["verdict"] == "吸收週":
        rhythm_note = "品質課有回來，但恢復與輕鬆跑仍維持主要節奏。"
    elif review["verdict"] == "建構週":
        rhythm_note = "本週的刺激有往前推，但恢復安排還沒有被擠掉。"
    else:
        top_purpose = distribution_snapshot["top_purpose"]
        rhythm_label_map = {
            "Aerobic Base": "有氧基礎",
            "Endurance": "耐力",
            "Recovery": "恢復",
            "Threshold": "門檻",
            "Race Specific": "比賽專項",
            "Unassigned": "未標註",
        }
        top_label = rhythm_label_map.get(top_purpose, top_purpose or "目前訓練")
        rhythm_note = f"目前仍以{top_label}為主，這週學習也主要是從這裡長出來。"
    cause_lines.append(f"- 整體節奏：{rhythm_note}")

    grouped_sessions = {}
    session_label_map = {
        "Longest Run": "最長一課",
        "Highest Load": "最高負荷",
        "Fastest Quality": "最快品質課",
        "Lowest HR Easy": "最低心率輕鬆跑",
    }
    session_reason_map = {
        "Longest Run": "它代表這週耐力主線是否還在。",
        "Highest Load": "它最能說明這週真正把壓力放在哪裡。",
        "Fastest Quality": "它是這週品質刺激最清楚的一堂。",
        "Lowest HR Easy": "它最能證明這週有沒有把恢復接住。",
    }
    for row in key_session_rows or []:
        key = str(row["key_session_type"])
        group_key = row["activity_id"]
        if group_key not in grouped_sessions:
            grouped_sessions[group_key] = {
                "activity": str(row["activity_name"] or row["activity_type"] or "活動"),
                "date": format_short_datetime(row["activity_start_time"]),
                "workout": str(row["workout_type_name_en"] or "未標註"),
                "distance": format_number(row["distance_km"], 2) or "—",
                "pace": format_pace_seconds(row["avg_pace_sec_per_km"]) or "—",
                "hr": "" if row["avg_hr"] is None else int(round(row["avg_hr"])),
                "load": format_number(row["training_load"], 1) or "—",
                "shoe": str(row["shoe_display_name"] or "未標註"),
                "labels": [],
                "reasons": [],
            }
        grouped_sessions[group_key]["labels"].append(session_label_map.get(key, key))
        reason = session_reason_map.get(key, "它補上了這週學習真正成立的那個片段。")
        if reason not in grouped_sessions[group_key]["reasons"]:
            grouped_sessions[group_key]["reasons"].append(reason)

    key_session_lines = []
    for session in grouped_sessions.values():
        key_session_lines.append(
            "- {labels}：{activity}；{date}；{workout}；{distance} km；配速 {pace}；HR {hr}；負荷 {load}；鞋款 {shoe}；Reasons：{reasons}".format(
                labels=" / ".join(session["labels"]),
                activity=session["activity"],
                date=session["date"],
                workout=session["workout"],
                distance=session["distance"],
                pace=session["pace"],
                hr=session["hr"],
                load=session["load"],
                shoe=session["shoe"],
                reasons=" / ".join(session["reasons"]),
            )
        )

    context_lines = []
    if overview_attention:
        context_lines.append(f"- 總覽焦點：{overview_attention.get('title') or '—'}")
    if monthly_overview:
        context_lines.append(f"- 月度位置：{monthly_overview.get('verdict') or '—'}")
        context_lines.append(f"- 月度摘要：{monthly_overview.get('verdict_reason') or '—'}")

    if knowledge_summary:
        context_lines.append(f"- 教練知識：{knowledge_summary['headline']}")
        context_lines.append(f"- 已確認知識：{knowledge_summary['detail']}")

    prompt_lines = [
        "請根據以下已治理的跑步資料，用繁體中文做進一步分析。",
        "請先回答這週真正留下來的是什麼，再說明原因，最後只留一個下週提醒。",
        "只能根據我提供的內容分析，不要自行發明額外訓練、健康或心理狀態。",
    ]
    prompt_lines.extend(
        coach_prompt_reference_lines(
            "週回顧 AI 交棒",
            "這週真正留下來的學習、原因與下週提醒",
            [
                "先回答這週真正留下來的是什麼",
                "再說明原因",
                "最後只留一個下週提醒",
                "優先沿著 教練理解 → 推理 → 關鍵活動 → 證據 的順序理解",
            ],
            [
                "週期區間、活動數、里程、負荷、平均心率",
                "教練理解",
                "推理",
                "支撐這個學習的關鍵活動",
                "上下文",
                "證據",
            ],
            [
                "如果 platform 判讀已經足以支持結論，不要因為 raw evidence 有更多資訊而重建另一套與平台相反的故事。",
                "若 evidence 與平台判讀有衝突，請優先指出衝突，不要直接覆蓋平台判讀。",
            ],
        )
    )
    prompt_lines.extend([
        "",
        "## 本週快照",
        f"- 週期：{period_text}",
        f"- 活動數：{activities_text}",
        f"- 里程：{total_km}",
        f"- 負荷：{load_text}",
        f"- 平均心率：{avg_hr_text}",
        f"- 相對基準負荷：{format_delta_pct(intelligence['load_delta']) if intelligence['load_delta'] is not None else '基準建立中'}",
        f"- 相對基準里程：{format_delta_pct(intelligence['km_delta']) if intelligence['km_delta'] is not None else '—'}",
        "",
        "## 教練理解",
        f"- 問題：{review['learning_question']}",
        f"- 判讀：{review['verdict']}",
        f"- 信心：{confidence}",
        f"- 學習：{review['learning']}",
        f"- 焦點：{review['focus']}",
        f"- 原因：{review['why']}",
        f"- 下一步：{review['looking_forward']}",
        "",
        "## 推理",
        *cause_lines,
    ])

    if knowledge_summary:
        prompt_lines.extend([
            "",
            "## 教練知識",
            f"- 重點：{knowledge_summary['headline']}",
            f"- 說明：{knowledge_summary['detail']}",
        ])

    wsi_lines = wsi_period_prompt_lines(wsi_summary)
    if wsi_lines:
        prompt_lines.extend([
            "",
            "## 訓練序列理解",
            *wsi_lines,
        ])

    if key_session_lines:
        prompt_lines.extend([
            "",
            "## 支撐這個學習的關鍵活動",
            *key_session_lines,
        ])

    if workout_structure_summary_rows:
        pattern_insights = workout_structure_pattern_insights(workout_structure_summary_rows, "本週")
        prompt_lines.extend([
            "",
            "## 課表結構模式",
        ])
        prompt_lines.extend(f"- {line}" for line in pattern_insights)
        for row in workout_structure_summary_rows:
            prompt_lines.append(
                f"- {row['date']} {row['activity']}（{row['workout']}）：{row['summary']}"
            )

    if context_lines:
        prompt_lines.extend([
            "",
            "## 上下文",
            *context_lines,
        ])

    if include_raw_data and history_rows:
        prompt_lines.extend([
            "",
            "## 證據",
            "### 最近 5 週節奏",
            "| 週別 | Coach | 期間 | 活動數 | KM | 時間 | 配速 | 平均心率 | 負荷 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ])
        labeled_rows = history_rows_with_labels or [{"row": row, "coach_label": "—"} for row in history_rows]
        for item in labeled_rows:
            row = item["row"]
            prompt_lines.append(
                "| {week} | {coach} | {period} | {activities} | {km} | {duration} | {pace} | {hr} | {load} |".format(
                    week=week_label_from_offset(row["week_offset"]),
                    coach=item["coach_label"],
                    period=f"{row['start_date']} – {row['end_date']}",
                    activities=row["activities"],
                    km=format_number(row["total_km"], 2) or "—",
                    duration=format_duration_hms(row["total_time_sec"]) or "—",
                    pace=format_pace_seconds(row["avg_pace_sec_per_km"]) or "—",
                    hr="" if row["avg_hr"] is None else row["avg_hr"],
                    load="" if row["training_load"] is None else row["training_load"],
                )
            )
        if distribution_rows:
            prompt_lines.extend([
                "",
                "### 這週訓練結構",
                "| 課表 | 目的 | 活動數 | KM | 平均負荷 |",
                "| --- | --- | --- | --- | --- |",
            ])
            for row in distribution_rows:
                prompt_lines.append(
                    "| {workout} | {purpose} | {count} | {km} | {load} |".format(
                        workout=str(row["workout_type_name_en"] or "未標註"),
                        purpose=str(row["primary_training_purpose_name_en"] or "未標註"),
                        count=row["activity_count"],
                        km=format_number(row["total_km"], 2) or "—",
                        load=format_number(row["avg_training_load"], 1) or "—",
                    )
                )

    append_previous_ai_response(prompt_lines, saved_reply)

    prompt_lines.extend([
        "",
        "## 指示",
        "- 先講這週真正留下來的是什麼。",
        "- 再解釋為什麼平台會這樣判讀。",
        "- 最後只留一個下週提醒。",
        "- 優先沿著 教練理解 → 推理 → 關鍵活動 → 證據 的順序理解。",
        "- 如果你從最近 5 週節奏看見平台尚未明說、但值得注意的變化，可以補充提出。",
        "- 如果平台判讀已經足以支持結論，不要因為原始證據有更多資訊而重建另一套與平台相反的故事。",
        "- 但請明確區分：哪些是平台已經判讀的，哪些是你根據證據額外補充的觀察。",
        "- 如果證據與平台判讀有衝突，請優先指出衝突，不要直接覆蓋平台判讀。",
    ])
    prompt_lines.extend([""] + ai_handoff_response_format_instructions())

    return "\n".join(prompt_lines)


def weekly_ai_handoff_panel(
    weekly,
    intelligence,
    review,
    distribution_rows,
    key_session_rows,
    workout_structure_summary_rows,
    history_rows,
    history_rows_with_labels=None,
    monthly_overview=None,
    overview_attention=None,
    knowledge_summary=None,
    wsi_summary=None,
    saved_reply=None,
):
    handoff_text = weekly_ai_handoff_text(
        weekly,
        intelligence,
        review,
        distribution_rows,
        key_session_rows,
        workout_structure_summary_rows,
        history_rows,
        history_rows_with_labels,
        monthly_overview,
        overview_attention,
        knowledge_summary,
        wsi_summary,
        include_raw_data=True,
        saved_reply=saved_reply,
    )
    weekly_card_prompt = weekly_training_card_prompt(
        weekly,
        intelligence,
        review,
        distribution_rows,
        key_session_rows,
        workout_structure_summary_rows,
        knowledge_summary,
        monthly_overview,
        saved_reply,
    )
    if not handoff_text:
        return ""

    title = f"{weekly['start_date']} – {weekly['end_date']} 週回顧 AI 回覆"
    saved_panel = ai_reply_saved_panel(title, saved_reply, "weekly", week=str(weekly["week_offset"]))
    capture_panel = ai_reply_capture_panel("weekly", f"{weekly['start_date']}:{weekly['end_date']}", title, "weekly", saved_reply, week=str(weekly['week_offset']))

    return f"""
      {saved_panel}
      <section class="panel-section" id="weekly-ai-handoff">
        <h2>AI 延伸分析</h2>
        <div class="review-card ai-handoff-card">
          <span>AI 交棒</span>
          <strong>把這週的教練學習脈絡直接交給你習慣的 AI</strong>
          <p>如果你看完這週後，想沿著平台已經整理好的學習、關鍵課與最近五週 evidence 繼續往下聊，這裡就是完整交棒內容。</p>
          <div class="ai-handoff-block">
            <div class="ai-handoff-block-head">
              <div>
                <strong>完整交棒內容</strong>
                <p class="note">包含這週判讀、形成原因、關鍵課與最近 5 週 evidence。</p>
              </div>
              <div class="ai-handoff-actions">
                <button class="secondary-action" type="button" onclick="copyAiHandoff('weekly-ai-handoff')">複製給 AI</button>
              </div>
            </div>
            <details class="ai-handoff-preview">
              <summary>先看會交出去的內容</summary>
              <textarea id="weekly-ai-handoff" readonly>{html.escape(handoff_text)}</textarea>
            </details>
          </div>
          <p class="note" id="weekly-ai-handoff-status">先看完這週，再複製交給你習慣的 AI 繼續分析。</p>
        </div>
        <div class="review-card ai-handoff-card">
          <span>週訓練圖卡提示</span>
          <strong>把這週分析交給圖像 AI 做成週訓練圖卡</strong>
          <p>這個 prompt 會把本週位置、課表型態、關鍵課與下週提醒整理成適合 16:9 圖卡的文案。</p>
          <div class="ai-handoff-block">
            <div class="ai-handoff-block-head">
              <div>
                <strong>週圖卡 prompt</strong>
                <p class="note">不會直接重貼完整交棒內容，而是改寫成適合圖像 AI 的圖卡內容。</p>
              </div>
              <div class="ai-handoff-actions">
                <button class="secondary-action" type="button" onclick="copyAiHandoff('weekly-training-card-prompt')">複製給 AI</button>
              </div>
            </div>
            <details class="ai-handoff-preview">
              <summary>先看週圖卡 prompt</summary>
              <textarea id="weekly-training-card-prompt" readonly>{html.escape(weekly_card_prompt)}</textarea>
            </details>
          </div>
          <p class="note">如果你想快速做一張本週訓練圖卡，直接用這段就可以，不需要先跑完整 AI 交棒。</p>
        </div>
      </section>
      {capture_panel}
    """


def monthly_ai_handoff_text(monthly, intelligence, progress_row, distribution_rows, key_session_rows, workout_structure_summary_rows, related_week_rows, coach_memory=None, knowledge_summary=None, wsi_summary=None, include_raw_data=False, saved_reply=None):
    if not monthly or not intelligence:
        return ""

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

    confidence = "Medium" if intelligence["is_partial_month"] else "High"

    letter = monthly_letter_payload(monthly, intelligence, verdict, phase, progress_pct)

    week_lines = [
        "- {period}：{verdict}；活動 {activities}；{km} km；負荷 {load}；{note}".format(
            period=f"{row['start_date']} – {row['end_date']}",
            verdict=str(row["verdict"] or "本週"),
            activities=row["activities"],
            km=format_number(row["total_km"], 2) or "—",
            load=format_number(row["training_load"], 1) or "—",
            note=str(row["note"] or ""),
        )
        for row in related_week_rows or []
    ]

    grouped_sessions = {}
    session_label_map = {
        "Longest Run": "最長一課",
        "Highest Load": "最高負荷",
        "Fastest Quality": "最快品質課",
        "Lowest HR Easy": "最低心率輕鬆跑",
    }
    session_reason_map = {
        "Longest Run": "它最能回答這個月的耐力主線有沒有真的站住。",
        "Highest Load": "它最能代表這個月真正把壓力推到哪裡。",
        "Fastest Quality": "它最能代表這個月品質刺激是怎麼回來的。",
        "Lowest HR Easy": "它最能檢查這個月有沒有把恢復保留下來。",
    }
    for row in key_session_rows or []:
        key = str(row["key_session_type"])
        group_key = row["activity_id"]
        if group_key not in grouped_sessions:
            grouped_sessions[group_key] = {
                "activity": str(row["activity_name"] or row["activity_type"] or "活動"),
                "date": format_short_datetime(row["activity_start_time"]),
                "workout": str(row["workout_type_name_en"] or "未標註"),
                "distance": format_number(row["distance_km"], 2) or "—",
                "pace": format_pace_seconds(row["avg_pace_sec_per_km"]) or "—",
                "hr": "" if row["avg_hr"] is None else int(round(row["avg_hr"])),
                "load": format_number(row["training_load"], 1) or "—",
                "shoe": str(row["shoe_display_name"] or "未標註"),
                "labels": [],
                "reasons": [],
            }
        grouped_sessions[group_key]["labels"].append(session_label_map.get(key, key))
        reason = session_reason_map.get(key, "它補上了這個月位置真正成立的那個片段。")
        if reason not in grouped_sessions[group_key]["reasons"]:
            grouped_sessions[group_key]["reasons"].append(reason)

    key_session_lines = []
    for session in grouped_sessions.values():
        key_session_lines.append(
            "- {labels}：{activity}；{date}；{workout}；{distance} km；配速 {pace}；HR {hr}；負荷 {load}；鞋款 {shoe}；Reasons：{reasons}".format(
                labels=" / ".join(session["labels"]),
                activity=session["activity"],
                date=session["date"],
                workout=session["workout"],
                distance=session["distance"],
                pace=session["pace"],
                hr=session["hr"],
                load=session["load"],
                shoe=session["shoe"],
                reasons=" / ".join(session["reasons"]),
            )
        )

    prompt_lines = [
        "請根據以下已治理的跑步資料，用繁體中文做進一步分析。",
        "請先回答這個月目前位於什麼訓練位置，再說明原因，最後只留一個下個月提醒。",
        "只能根據我提供的內容分析，不要自行發明額外訓練、健康或心理狀態。",
    ]
    prompt_lines.extend(
        coach_prompt_reference_lines(
            "月回顧 AI 交棒",
            "這個月的位置、原因與下個月提醒",
            [
                "先回答這個月目前位於什麼訓練位置",
                "再說明原因",
                "最後只留一個下個月提醒",
                "優先看月度位置，再回到關鍵活動與週次脈絡",
            ],
            [
                "月份、狀態、里程、時間、負荷、活動數、平均配速、平均心率",
                "教練位置",
                "推理",
                "支撐這個位置的關鍵週",
                "支撐這個位置的關鍵活動",
                "證據",
            ],
            [
                "若資料不足，請把月度判讀視為進度檢查，不要硬推完整結論。",
                "如果 evidence 與平台判讀有衝突，請優先指出衝突，不要直接覆蓋平台判讀。",
            ],
        )
    )
    prompt_lines.extend([
        "",
        "## 月度事實",
        f"- 月份：{monthly['month_key']}",
        f"- 狀態：{'進行中' if intelligence['is_partial_month'] else '完整'}",
        f"- 截至：{monthly['latest_date']}" if monthly["latest_date"] else "- 截至：—",
        f"- 里程：{format_number(monthly['total_km'], 1)} km",
        f"- 時間：{format_duration_hms(monthly['total_time_sec']) or '—'}",
        f"- 負荷：{format_number(monthly['training_load'], 0) or '—'}",
        f"- 活動數：{monthly['activities'] or 0}",
        f"- 平均配速：{format_pace_seconds(monthly['avg_pace_sec_per_km']) or '—'}",
        f"- 平均心率：{'' if monthly['avg_hr'] is None else int(round(monthly['avg_hr']))}",
        f"- 相對基準負荷：{format_delta_pct(intelligence['load_delta']) if intelligence['load_delta'] is not None else '基準建立中'}",
        f"- 相對基準里程：{format_delta_pct(intelligence['km_delta']) if intelligence['km_delta'] is not None else '—'}",
        f"- 品質課數：{quality_sessions}",
        f"- 長跑數：{long_runs}",
        "",
        "## 教練位置",
        f"- 位置：{verdict}",
        f"- 階段：{phase}",
        f"- 信心：{confidence}",
        f"- 開場：{letter['opening']}",
        f"- 學習：{intelligence['coach_summary']}",
        f"- 判讀原因：{verdict_reason}",
        f"- 下一步：{letter['looking_forward']}",
    ])

    if coach_memory:
        prompt_lines.extend([
            f"- 上個月：{coach_memory['previous_month_key']}",
            f"- 上月建議：{coach_memory['previous_recommendation']}",
            f"- 後續追蹤：{coach_memory['follow_up']}",
        ])

    if knowledge_summary:
        prompt_lines.extend([
            f"- 教練知識：{knowledge_summary['headline']}",
            f"- 已確認知識：{knowledge_summary['detail']}",
        ])

    wsi_lines = wsi_period_prompt_lines(wsi_summary)
    if wsi_lines:
        prompt_lines.extend([
            "",
            "## 訓練序列理解",
            *wsi_lines,
        ])

    reasoning_lines = []
    if intelligence["is_partial_month"]:
        completion = format_number(progress_pct, 0) if progress_pct is not None else "—"
        reasoning_lines.append(f"本月目前完成約 {completion}%，先把這次判讀視為進度檢查，不急著下完整月結論。")
    if coach_memory and coach_memory.get("follow_up"):
        reasoning_lines.append(f"從上月延續來看：{coach_memory['follow_up']}")
    load_delta = intelligence["load_delta"]
    km_delta = intelligence["km_delta"]
    if load_delta is not None:
        if load_delta > 15:
            reasoning_lines.append(f"訓練負荷較前 3 個月平均增加 {format_delta_pct(load_delta)}，目前屬於明顯往前推進的建構。")
        elif load_delta < -15:
            reasoning_lines.append(f"訓練負荷較前 3 個月平均下降 {abs(load_delta):.0f}%，更像有意識地吸收與調整。")
        else:
            reasoning_lines.append("訓練負荷大致貼近前 3 個月基準，整體節奏仍維持在可延續範圍內。")
    if km_delta is not None:
        if km_delta > 10:
            reasoning_lines.append(f"里程較基準增加 {format_delta_pct(km_delta)}，目前的增加不只來自單次刺激，而是整體累積。")
        elif km_delta < -10:
            reasoning_lines.append(f"里程較基準下降 {abs(km_delta):.0f}%，但目前判讀更重視這是否屬於刻意收整。")
        else:
            reasoning_lines.append("里程變化不大，代表本月方向主要不是靠單純多跑來改變。")
    quality_sessions = int(progress_row["current_quality_sessions"] or 0) if progress_row else 0
    long_runs = int(progress_row["current_long_runs"] or 0) if progress_row else 0
    if quality_sessions >= 3:
        reasoning_lines.append(f"本月已有 {quality_sessions} 次品質刺激，代表速度工作已經回到訓練結構裡。")
    elif quality_sessions >= 1:
        reasoning_lines.append(f"本月已有 {quality_sessions} 次品質刺激，刺激正在回來，但還沒有壓過整體節奏。")
    elif long_runs >= 2:
        reasoning_lines.append(f"本月保留了 {long_runs} 次長跑，耐力主線仍然連續。")
    elif long_runs == 1:
        reasoning_lines.append("本月至少保留一次長跑，代表耐力主線沒有完全中斷。")

    prompt_lines.extend([
        "",
        "## 推理",
        *[f"- {point}" for point in reasoning_lines[:4]],
    ])

    if week_lines:
        prompt_lines.extend([
            "",
            "## 支撐這個位置的關鍵週",
            *week_lines,
        ])

    if key_session_lines:
        prompt_lines.extend([
            "",
            "## 支撐這個位置的關鍵活動",
            *key_session_lines,
        ])

    if workout_structure_summary_rows:
        pattern_insights = workout_structure_pattern_insights(workout_structure_summary_rows, "本月")
        prompt_lines.extend([
            "",
            "## 課表結構模式",
        ])
        prompt_lines.extend(f"- {line}" for line in pattern_insights)
        for row in workout_structure_summary_rows:
            prompt_lines.append(
                f"- {row['date']} {row['activity']}（{row['workout']}）：{row['summary']}"
            )

    if include_raw_data and distribution_rows:
        prompt_lines.extend([
            "",
            "## 證據",
            "### 本月訓練結構",
            "| 課表 | 目的 | 活動數 | KM | 平均負荷 |",
            "| --- | --- | --- | --- | --- |",
        ])
        for row in distribution_rows:
            prompt_lines.append(
                "| {workout} | {purpose} | {count} | {km} | {load} |".format(
                    workout=str(row["workout_type_name_en"] or "未標註"),
                    purpose=str(row["primary_training_purpose_name_en"] or "未標註"),
                    count=row["activity_count"],
                    km=format_number(row["total_km"], 2) or "—",
                    load=format_number(row["avg_training_load"], 1) or "—",
                )
            )

    append_previous_ai_response(prompt_lines, saved_reply)

    prompt_lines.extend([
        "",
        "## 指示",
        "- 先講這個月目前位於什麼訓練位置。",
        "- 再解釋平台為什麼會這樣判讀。",
        "- 最後只留一個下個月提醒。",
        "- 優先沿著 教練位置 → 推理 → 關鍵週 → 關鍵活動 → 證據 的順序理解。",
        "- 目前月份仍在進行中時，避免把目前進度描述成完整月結論。",
        "- 如果你從 key weeks、key activities 或本月訓練結構看見平台尚未明說、但值得注意的變化，可以補充提出。",
        "- 但請明確區分：哪些是平台已經判讀的，哪些是你根據證據額外補充的觀察。",
        "- 如果證據與平台判讀有衝突，請優先指出衝突，不要直接覆蓋平台判讀。",
    ])
    prompt_lines.extend([""] + ai_handoff_response_format_instructions())

    return "\n".join(prompt_lines)


def monthly_ai_handoff_panel(monthly, intelligence, progress_row, distribution_rows, key_session_rows, workout_structure_summary_rows, related_week_rows, coach_memory=None, knowledge_summary=None, wsi_summary=None, saved_reply=None):
    handoff_text = monthly_ai_handoff_text(
        monthly,
        intelligence,
        progress_row,
        distribution_rows,
        key_session_rows,
        workout_structure_summary_rows,
        related_week_rows,
        coach_memory,
        knowledge_summary,
        wsi_summary,
        include_raw_data=True,
        saved_reply=saved_reply,
    )
    monthly_card_prompt = monthly_training_card_prompt(
        monthly,
        intelligence,
        progress_row,
        distribution_rows,
        key_session_rows,
        workout_structure_summary_rows,
        related_week_rows,
        coach_memory,
        knowledge_summary,
        saved_reply,
    )
    if not handoff_text:
        return ""

    title = f'{monthly["month_key"]} 月回顧 AI 回覆'
    saved_panel = ai_reply_saved_panel(title, saved_reply, "monthly", month=str(monthly["month_key"]))
    capture_panel = ai_reply_capture_panel("monthly", str(monthly["month_key"]), title, "monthly", saved_reply, month=str(monthly["month_key"]))

    return f"""
      {saved_panel}
      <section class="panel-section" id="monthly-ai-handoff">
        <h2>AI 延伸分析</h2>
        <div class="review-card ai-handoff-card">
          <span>AI 交棒</span>
          <strong>把這個月的教練位置判讀直接交給你習慣的 AI</strong>
          <p>如果你看完這個月後，想沿著平台已經整理好的位置、形成原因、關鍵週與關鍵課繼續往下聊，這裡就是完整交棒內容。</p>
          <div class="ai-handoff-block">
            <div class="ai-handoff-block-head">
              <div>
                <strong>完整交棒內容</strong>
                <p class="note">包含月判讀、形成原因、關鍵週、關鍵課與本月訓練結構。</p>
              </div>
              <div class="ai-handoff-actions">
                <button class="secondary-action" type="button" onclick="copyAiHandoff('monthly-ai-handoff-text')">複製給 AI</button>
              </div>
            </div>
            <details class="ai-handoff-preview">
              <summary>先看會交出去的內容</summary>
              <textarea id="monthly-ai-handoff-text" readonly>{html.escape(handoff_text)}</textarea>
            </details>
          </div>
          <p class="note" id="monthly-ai-handoff-status">先看完這個月，再複製交給你習慣的 AI 繼續分析。</p>
        </div>
        <div class="review-card ai-handoff-card">
          <span>月訓練圖卡提示</span>
          <strong>把這個月分析交給圖像 AI 做成月訓練圖卡</strong>
          <p>這個 prompt 會把月度位置、代表型態、關鍵週與關鍵課整理成適合 16:9 圖卡的文案。</p>
          <div class="ai-handoff-block">
            <div class="ai-handoff-block-head">
              <div>
                <strong>月圖卡 prompt</strong>
                <p class="note">會保留月度判讀的重點，但避免把整份月 handoff 原封不動丟給圖像 AI。</p>
              </div>
              <div class="ai-handoff-actions">
                <button class="secondary-action" type="button" onclick="copyAiHandoff('monthly-training-card-prompt')">複製給 AI</button>
              </div>
            </div>
            <details class="ai-handoff-preview">
              <summary>先看月圖卡 prompt</summary>
              <textarea id="monthly-training-card-prompt" readonly>{html.escape(monthly_card_prompt)}</textarea>
            </details>
          </div>
          <p class="note">如果你想快速做一張本月訓練圖卡，直接用這段就可以，不需要先跑完整 AI 交棒。</p>
        </div>
      </section>
      {capture_panel}
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
              <td>{f'<a class="inline-jump-link" href="/?page=activity&activity={int(row["activity_id"])}#activity-learning">看這堂課</a>' if row["activity_id"] else ''}</td>
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


def activity_key_segments(activity, split_rows, workout_split_rows=None):
    all_rows = activity_analysis_splits(split_rows)
    analysis_rows = activity_focus_splits(activity, split_rows, workout_split_rows) or all_rows
    if not analysis_rows:
        return []
    labels = activity_focus_segment_labels(activity, analysis_rows, all_rows, workout_split_rows)
    rows = []
    first = analysis_rows[0]
    last = analysis_rows[-1]
    rows.append({
        "anchor": "fragment-start",
        "label": labels["start"],
        "section": structured_segment_label_for_split(first, split_rows, workout_split_rows or []),
        "metric": f"配速 {format_pace_seconds(first['elapsed_pace_sec_per_km']) or '—'} · HR {'' if first['avg_hr'] is None else int(round(first['avg_hr']))}",
        "note": "先看這堂課是怎麼進入今天真正要訓練的主體。",
        "split_anchor": f"split-{first['split_index']}",
    })
    if len(analysis_rows) >= 3:
        middle = analysis_rows[len(analysis_rows) // 2]
        rows.append({
            "anchor": "fragment-middle",
            "label": labels["middle"],
            "section": structured_segment_label_for_split(middle, split_rows, workout_split_rows or []),
            "metric": f"配速 {format_pace_seconds(middle['elapsed_pace_sec_per_km']) or '—'} · HR {'' if middle['avg_hr'] is None else int(round(middle['avg_hr']))}",
            "note": "中段通常最能看出今天真正的刺激有沒有成立。",
            "split_anchor": f"split-{middle['split_index']}",
        })
    rows.append({
        "anchor": "fragment-finish",
        "label": labels["finish"],
        "section": structured_segment_label_for_split(last, split_rows, workout_split_rows or []),
        "metric": f"配速 {format_pace_seconds(last['elapsed_pace_sec_per_km']) or '—'} · HR {'' if last['avg_hr'] is None else int(round(last['avg_hr']))}",
        "note": "這一段最能看出今天主體刺激最後有沒有被守住。",
        "split_anchor": f"split-{last['split_index']}",
    })
    return rows


def activity_fragment_table(activity, split_rows, workout_split_rows=None):
    rows = activity_key_segments(activity, split_rows, workout_split_rows)
    if not rows:
        return '<p class="note">目前還沒有足夠的分段可以建立關鍵片段。</p>'

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


def raw_data_metric_value(value):
    text = "" if value is None else str(value).strip()
    return text


def raw_data_row(label, value, value_class=""):
    text = raw_data_metric_value(value)
    if not text:
        return ""
    value_class_attr = f' class="{value_class}"' if value_class else ""
    return f"""
      <div class="raw-data-row">
        <span>{html.escape(label)}</span>
        <strong{value_class_attr}>{html.escape(text)}</strong>
      </div>
    """


def raw_data_group(title, rows):
    row_html = "".join(row for row in rows if row)
    if not row_html:
        return ""
    return f"""
      <section class="raw-data-group">
        <h3>{html.escape(title)}</h3>
        <div class="raw-data-group-body">
          {row_html}
        </div>
      </section>
    """


def raw_data_column(groups):
    group_html = "".join(group for group in groups if group)
    if not group_html:
        return ""
    return f'<div class="raw-data-column">{group_html}</div>'


def activity_facts_panel(activity, split_rows=None, workout_split_rows=None):
    if not activity:
        return ""
    split_rows = split_rows or []
    workout_split_rows = workout_split_rows or []
    def activity_value(key, fallback=None):
        try:
            value = activity[key]
        except (KeyError, IndexError, TypeError):
            return fallback
        return fallback if value is None else value

    location_name = ""
    if activity_value("start_latitude") is not None and activity_value("start_longitude") is not None:
        location_name = reverse_geocode_location_label(activity_value("start_latitude"), activity_value("start_longitude"))
    if not location_name and activity_value("end_latitude") is not None and activity_value("end_longitude") is not None:
        location_name = reverse_geocode_location_label(activity_value("end_latitude"), activity_value("end_longitude"))
    location_display = location_name or (
        f"{format_number(activity_value('start_latitude'), 5)}, {format_number(activity_value('start_longitude'), 5)}"
        if activity_value("start_latitude") is not None and activity_value("start_longitude") is not None
        else "未提供"
    )
    chips = [
        detail_chip("開始時間", str(activity["activity_start_time"]).replace("T", " ")[:16]),
        detail_chip("距離", f"{format_number(activity['distance_km'], 2)} km"),
        detail_chip("時間", format_hours(activity["duration_sec"])),
        detail_chip("平均配速", format_pace_seconds(activity["avg_pace_sec_per_km"])),
        detail_chip("平均 HR", "" if activity["avg_hr"] is None else int(round(activity["avg_hr"]))),
        detail_chip("負荷", "" if activity["training_load"] is None else format_number(activity["training_load"], 0)),
        detail_chip("地點", location_display),
        detail_chip("課表", activity["workout_type_name_zh"] or activity["workout_type_name_en"] or activity["activity_type"] or "未標註"),
        detail_chip("鞋款", activity["shoe_display_name"] or "未標註"),
    ]
    if activity["primary_training_purpose_name_en"]:
        chips.append(detail_chip("主要目的", activity["primary_training_purpose_name_zh"] or activity["primary_training_purpose_name_en"]))

    def pace_value(seconds):
        return format_pace_seconds(seconds)

    split_paces = [row["elapsed_pace_sec_per_km"] for row in activity_analysis_splits(split_rows) if row["elapsed_pace_sec_per_km"] is not None]
    best_split_pace = min(split_paces) if split_paces else activity["avg_pace_sec_per_km"]
    best_split_speed = (3600.0 / best_split_pace) if best_split_pace else None
    max_split_hr = split_activity_max_hr(split_rows)
    max_split_power = split_activity_metric_max(split_rows, "avg_power_w")
    max_split_cadence = split_activity_metric_max(split_rows, "avg_cadence_spm")
    total_elevation_gain = split_activity_metric_sum(split_rows, "elevation_gain_m")
    total_elevation_loss = split_activity_metric_sum(split_rows, "elevation_loss_m")
    avg_split_power = split_activity_metric_avg(split_rows, "avg_power_w")

    avg_pace = activity["avg_pace_sec_per_km"]
    avg_speed = 3600.0 / float(avg_pace) if avg_pace not in (None, "") and float(avg_pace) > 0 else None
    duration_text = format_duration_hms(activity["duration_sec"])
    distance_text = format_number(activity["distance_km"], 2)
    load_text = format_number(activity["training_load"], 0)

    pace_group = raw_data_group(
        "配速",
        [
            raw_data_row("平均配速", pace_value(avg_pace)),
            raw_data_row("平均移動配速", pace_value(avg_pace)),
            raw_data_row("平均坡度調整配速", pace_value(avg_pace)),
            raw_data_row("最佳配速", pace_value(best_split_pace)),
        ],
    )
    speed_group = raw_data_group(
        "速度",
        [
            raw_data_row("平均速度", "" if avg_speed is None else f"{format_number(avg_speed, 1)} km/h"),
            raw_data_row("平均移動速度", "" if avg_speed is None else f"{format_number(avg_speed, 1)} km/h"),
            raw_data_row("平均坡度調整速度", "" if avg_speed is None else f"{format_number(avg_speed, 1)} km/h"),
            raw_data_row("最高速度", "" if best_split_speed is None else f"{format_number(best_split_speed, 1)} km/h"),
        ],
    )
    time_group = raw_data_group(
        "計時",
        [
            raw_data_row("總計時間", duration_text),
            raw_data_row("移動時間", duration_text),
            raw_data_row("經過時間", duration_text),
        ],
    )
    run_walk_group = raw_data_group(
        "跑步/步行偵測",
        [
            raw_data_row("跑步時間", duration_text),
        ],
    )
    heart_rate_group = raw_data_group(
        "心率",
        [
            raw_data_row("平均心率", "" if activity["avg_hr"] is None else f"{int(round(activity['avg_hr']))} bpm"),
            raw_data_row("活動最高心率", "" if max_split_hr is None else f"{int(round(max_split_hr))} bpm"),
        ],
    )
    stamina_group = raw_data_group(
        "體力",
        [
            raw_data_row("起始上限", "" if activity["stamina_start_pct"] is None else f"{format_number(activity['stamina_start_pct'], 0)}%"),
            raw_data_row("結束上限", "" if activity["stamina_end_pct"] is None else f"{format_number(activity['stamina_end_pct'], 0)}%"),
            raw_data_row(
                "最低體力",
                "" if activity["stamina_start_pct"] is None and activity["stamina_end_pct"] is None else f"{format_number(min([value for value in [activity['stamina_start_pct'], activity['stamina_end_pct']] if value is not None]), 0)}%",
            ),
        ],
    )
    training_effect_group = raw_data_group(
        "訓練效果",
        [
            raw_data_row("有氧", "" if activity["training_effect_aerobic"] is None else format_number(activity["training_effect_aerobic"], 1)),
            raw_data_row("無氧", "" if activity["training_effect_anaerobic"] is None else format_number(activity["training_effect_anaerobic"], 1)),
            raw_data_row("運動負荷", load_text),
        ],
    )
    power_group = raw_data_group(
        "功率",
        [
            raw_data_row("平均功率", "" if avg_split_power is None else f"{format_number(avg_split_power, 0)} W"),
            raw_data_row("最大功率", "" if max_split_power is None else f"{format_number(max_split_power, 0)} W"),
            raw_data_row("個人臨界功率", "" if activity["critical_power_w"] is None else f"{format_number(activity['critical_power_w'], 0)} W"),
        ],
    )
    dynamics_group = raw_data_group(
        "跑步動態",
        [
            raw_data_row("平均步頻", "" if activity["avg_cadence_spm"] is None else f"{format_number(activity['avg_cadence_spm'], 1)} spm"),
            raw_data_row("最高步頻", "" if max_split_cadence is None else f"{format_number(max_split_cadence, 1)} spm"),
            raw_data_row("平均步幅", "" if activity["avg_stride_length_mm"] is None else f"{format_number(float(activity['avg_stride_length_mm']) / 1000.0, 2)} m"),
            raw_data_row("平均移動效率", "" if activity["avg_vertical_ratio_pct"] is None else f"{format_number(activity['avg_vertical_ratio_pct'], 1)}%"),
            raw_data_row("平均垂直振幅", "" if activity["avg_vertical_oscillation_mm"] is None else f"{format_number(float(activity['avg_vertical_oscillation_mm']) / 10.0, 1)} cm"),
            raw_data_row("平均觸地時間", "" if activity["avg_gct_ms"] is None else f"{format_number(activity['avg_gct_ms'], 1)} ms"),
        ],
    )
    impact_group = raw_data_group(
        "衝擊負荷",
        [
            raw_data_row("負荷", load_text),
        ],
    )
    elevation_group = raw_data_group(
        "高度",
        [
            raw_data_row("總爬升", "" if total_elevation_gain is None else f"{format_number(total_elevation_gain, 0)} m"),
            raw_data_row("總下降", "" if total_elevation_loss is None else f"{format_number(total_elevation_loss, 0)} m"),
        ],
    )
    training_interval_group = raw_data_group(
        "訓練間隔",
        [
            raw_data_row("跑步時間", duration_text),
            raw_data_row("跑步距離", f"{distance_text} km"),
            raw_data_row("跑步配速", pace_value(avg_pace)),
        ],
    )
    temperature_group = raw_data_group(
        "溫度",
        [
            raw_data_row("平均溫度", "" if activity["temperature_c"] is None else f"{format_number(activity['temperature_c'], 0)} °C"),
        ],
    )

    raw_details = "".join([
        raw_data_column([pace_group, speed_group, time_group, run_walk_group, heart_rate_group]),
        raw_data_column([stamina_group, training_effect_group, power_group, dynamics_group]),
        raw_data_column([impact_group, elevation_group, temperature_group, training_interval_group]),
    ])

    split_tab = f"""
      <div class="raw-data-tab-panel" data-raw-panel="split" hidden>
        <p class="note raw-data-split-note">先看課表片段，再往下看每公里原始分段，會比只看公里數更接近這堂課原本的設計。</p>
        {activity_workout_structure_table(workout_split_rows)}
        <p class="note raw-data-split-note">下面這張是每公里原始分段，所以 2K 主段會拆成兩列 1K，0.5K 恢復也會保留成半公里。</p>
        {activity_split_table(split_rows)}
      </div>
    """
    chart_tab = f"""
      <div class="raw-data-tab-panel" data-raw-panel="chart" hidden>
        <p class="note raw-data-split-note">圖表用來看節奏、心率和功率怎麼一起走。</p>
        {trend_svg(split_rows)}
      </div>
    """

    return f"""
      <section class="panel-section" id="activity-raw">
        <h2>原始資料</h2>
        <p class="note">先保留你跑完會先看的重點，更多 Garmin 細節收起來，想核對時再展開。</p>
        <div class="review-card metric-collection raw-data-card">
          <div class="reasoning-jump-row">
            <a class="inline-jump-link" href="#activity-summary">活動摘要</a>
            <a class="inline-jump-link" href="#activity-review">教練判讀</a>
            <a class="inline-jump-link" href="#activity-knowledge">教練知識</a>
            <a class="inline-jump-link" href="#activity-evidence">證據</a>
            <a class="inline-jump-link" href="#activity-ai-handoff">AI 延伸</a>
          </div>
          <div class="detail-chips raw-data-key-chips">
            {"".join(chips)}
          </div>
          <button class="secondary-action raw-data-toggle" type="button" data-raw-target="activity-raw-details" data-open-label="隱藏細節" data-closed-label="顯示 Garmin 細節">顯示 Garmin 細節</button>
          <div class="raw-data-details-panel" id="activity-raw-details" hidden>
            <div class="raw-data-tablist" role="tablist" aria-label="Garmin 細節">
              <button class="raw-data-tab active" type="button" data-raw-tab="data">數據</button>
              <button class="raw-data-tab" type="button" data-raw-tab="split">分段</button>
              <button class="raw-data-tab" type="button" data-raw-tab="chart">圖表</button>
            </div>
            <div class="raw-data-tab-panels">
              <div class="raw-data-tab-panel" data-raw-panel="data">
                <div class="raw-data-columns">
                  {raw_details}
                </div>
              </div>
              {split_tab}
              {chart_tab}
            </div>
          </div>
        </div>
      </section>
    """


def normalize_choice_key(value):
    text = "" if value is None else str(value).strip().lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def choice_row_code(row, kind):
    if kind == "shoe":
        return row["shoe_code"]
    if kind == "workout":
        return row["workout_type_code"]
    if kind == "purpose":
        return row["training_purpose_code"]
    return None


def choice_row_label(row, kind):
    if kind == "shoe":
        return shoe_display_name(row)
    if kind in {"workout", "purpose"}:
        return str(row["name_zh"] or row["name_en"] or "")
    return ""


def label_for_choice_code(rows, kind, code, fallback=""):
    if not code:
        return fallback
    for row in rows:
        if str(choice_row_code(row, kind) or "") == str(code):
            label = choice_row_label(row, kind)
            if label:
                return label
            break
    return fallback


def match_choice_code(rows, kind, wanted_label):
    wanted = normalize_choice_key(wanted_label)
    if not wanted:
        return None
    direct_match = None
    partial_match = None
    for row in rows:
        label = normalize_choice_key(choice_row_label(row, kind))
        code = choice_row_code(row, kind)
        if not code:
            continue
        if label == wanted:
            return code
        if wanted in label or label in wanted:
            direct_match = direct_match or code
        elif partial_match is None and (wanted[:8] and wanted[:8] in label):
            partial_match = code
    return direct_match or partial_match


def first_choice_code(rows, kind, active_only=False):
    if kind == "shoe":
        preferred = [row for row in rows if row["is_active"]]
        if preferred:
            return choice_row_code(preferred[0], kind)
    if rows:
        return choice_row_code(rows[0], kind)
    return None


def infer_purpose_choice_code(purpose_rows, workout_label, review):
    workout_key = normalize_choice_key(workout_label)
    candidate_labels = []
    if any(token in workout_key for token in ("tempo", "threshold", "interval", "quality", "work")):
        candidate_labels.extend(["Threshold", "Tempo", "Quality"])
    elif any(token in workout_key for token in ("easy", "recovery", "rest", "shake")):
        candidate_labels.extend(["Recovery", "Easy"])
    elif any(token in workout_key for token in ("long", "lsd", "endurance", "steady")):
        candidate_labels.extend(["Endurance", "Long Run"])
    else:
        learning_key = normalize_choice_key(review.get("learning", ""))
        if "threshold" in learning_key or "tempo" in learning_key:
            candidate_labels.extend(["Threshold", "Tempo"])
    candidate_labels.extend(["Threshold", "Tempo", "Endurance", "Easy", "Recovery"])
    for candidate in candidate_labels:
        code = match_choice_code(purpose_rows, "purpose", candidate)
        if code:
            return code
    return first_choice_code(purpose_rows, "purpose")


def infer_workout_choice_code(workout_rows, activity, review):
    workout_label = str(activity["workout_type_name_en"] or activity["activity_type"] or "").lower()
    distance = float(activity["distance_km"] or 0)
    training_load = float(activity["training_load"] or 0)
    pace_sec = activity["avg_pace_sec_per_km"]
    pace_minutes = (float(pace_sec) / 60.0) if pace_sec not in (None, "") and float(pace_sec) > 0 else None
    quality_workout = any(token in workout_label for token in ("tempo", "interval", "repetition", "fartlek", "marathon pace"))
    long_run = any(token in workout_label for token in ("long run", "lsd")) or distance >= 18
    easy_run = any(token in workout_label for token in ("easy", "recovery"))
    if quality_workout or training_load >= 240 or (pace_minutes is not None and pace_minutes <= 5.2 and distance >= 8):
        candidates = ["Tempo Run", "Interval", "Marathon Pace", "Fartlek"]
    elif long_run or distance >= 16:
        candidates = ["Long Run", "LSD", "Progression Run"]
    elif easy_run or distance < 12 or training_load < 200:
        candidates = ["Easy Run", "Recovery Run", "LSD"]
    else:
        candidates = ["Easy Run", "Long Run", "Tempo Run"]
    for candidate in candidates:
        wanted = normalize_choice_key(candidate)
        for row in workout_rows:
            workout_code = str(row["workout_type_code"] or "").strip()
            workout_name = normalize_choice_key(
                row["workout_name_zh"] or row["workout_name_en"] or ""
            )
            if not workout_code:
                continue
            if workout_name == wanted or wanted in workout_name or workout_name in wanted:
                return workout_code
    return first_choice_code(workout_rows, "workout")


def activity_coach_knowledge_state(activity, review, shoe_rows, workout_rows, purpose_rows):
    workout_label = str(activity["workout_type_name_zh"] or activity["workout_type_name_en"] or activity["activity_type"] or "").strip()
    shoe_label = str(activity["shoe_display_name"] or "").strip()
    purpose_label = str(activity["primary_training_purpose_name_zh"] or activity["primary_training_purpose_name_en"] or "").strip()
    workout_context = workout_label if workout_label and workout_label not in {"活動", "Activity", "Run"} else ""

    shoe_code = activity["shoe_code"]
    workout_code = activity["workout_type_code"] or first_choice_code(workout_rows, "workout")
    purpose_code = activity["primary_training_purpose_code"] or infer_purpose_choice_code(purpose_rows, workout_label, review)

    shoe_choice_label = shoe_label
    if not shoe_choice_label:
        shoe_choice_label = label_for_choice_code(shoe_rows, "shoe", shoe_code, "未標註鞋款") if shoe_code else "未標註鞋款"
    workout_choice_label = workout_label or label_for_choice_code(workout_rows, "workout", workout_code, "未標註課表")
    purpose_choice_label = purpose_label or label_for_choice_code(purpose_rows, "purpose", purpose_code, "未標註目的")

    steps = {
        "shoe": {
            "icon": "🏃",
            "label": "鞋款",
            "title": shoe_choice_label or "未標註鞋款",
            "reason": (
                f"最近幾堂 {workout_context} 都在用這雙鞋。" if workout_context else "CoachOS 先從最有把握的鞋款訊號起手。"
            ),
            "code": shoe_code,
            "current": shoe_label or "CoachOS 目前還不知道這堂課的鞋款。",
            "rows": shoe_rows,
            "learned": f"這堂課的鞋款已經被 CoachOS 記住了：{shoe_choice_label}。" if shoe_code else "這堂課的鞋款還沒被記住。",
            "next_label": "課表",
            "continue_href": f'/?page=activity&activity={int(activity["activity_id"])}&coach_step=workout#activity-knowledge',
        },
        "workout": {
            "icon": "⚡",
            "label": "課表",
            "title": workout_choice_label or "未標註課表",
            "reason": (
                f"距離、負荷與配速都讓這堂課看起來像 {workout_context}。"
                if workout_context
                else "CoachOS 先把這堂課的型態補起來。"
            ),
            "code": workout_code,
            "current": workout_context or "CoachOS 目前還不知道這堂課的課表。",
            "rows": workout_rows,
            "learned": f"這堂課的課表已經被 CoachOS 記住了：{workout_choice_label}。",
            "next_label": "訓練目的",
            "continue_href": f'/?page=activity&activity={int(activity["activity_id"])}&coach_step=purpose#activity-knowledge',
        },
        "purpose": {
            "icon": "🎯",
            "label": "訓練目的",
            "title": purpose_choice_label or "未標註目的",
            "reason": (
                f"這堂課的結構更像 {purpose_choice_label}。"
                if purpose_choice_label
                else "CoachOS 先把這堂課真正要訓練什麼補起來。"
            ),
            "code": purpose_code,
            "current": purpose_label or "CoachOS 目前還不知道這堂課的訓練目的。",
            "rows": purpose_rows,
            "learned": f"這堂課的訓練目的已經被 CoachOS 記住了：{purpose_choice_label}。",
            "next_label": "證據",
            # Keep the learned state when jumping to evidence so the panel does not reset
            # back to the first step after the user leaves the completion card.
            "continue_href": f'/?page=activity&activity={int(activity["activity_id"])}&coach_step=purpose_learned#activity-evidence',
        },
    }
    return steps


def activity_coach_knowledge_panel(activity, split_rows, shoe_rows, workout_rows, purpose_rows, coach_step=None):
    if not activity:
        return ""

    review = activity_review_payload(activity, split_rows)
    explicit_step = coach_step is not None and str(coach_step).strip() != ""
    step_key = str(coach_step or "").strip()
    learned_mode = False
    if step_key.endswith("_learned"):
        learned_mode = True
        step_key = step_key.replace("_learned", "")
    if step_key not in {"shoe", "workout", "purpose"}:
        step_key = ""
        learned_mode = False

    has_shoe = activity["shoe_id"] is not None
    has_workout = activity["workout_type_id"] is not None
    has_purpose = activity["primary_training_purpose_id"] is not None
    fully_learned = has_shoe and has_workout and has_purpose
    activity_id = int(activity["activity_id"])
    missing_shoe = step_key == "shoe" and not has_shoe
    missing_workout = step_key == "workout" and not has_workout
    missing_purpose = step_key == "purpose" and not has_purpose

    if not explicit_step and not learned_mode:
        if fully_learned:
            step_key = "purpose"
        elif not has_shoe:
            step_key = "shoe"
        elif not has_workout:
            step_key = "workout"
        elif not has_purpose:
            step_key = "purpose"
        else:
            step_key = "purpose"

    if missing_shoe:
        metadata_href = "/?" + urlencode({
            "page": "metadata",
            "edit": activity_id,
            "scope": "missing_shoe",
        }) + "#metadata-edit"
        return f"""
          <section class="panel-section" id="activity-knowledge">
            <h2>教練知識</h2>
            <p class="note">先選一個最像的，確認後 CoachOS 才會記住這堂課。</p>
            <div class="review-card knowledge-conversation-card">
              <span>這堂課的鞋款 · 🏃</span>
              <strong>這堂課還沒有鞋款，先去標註這堂課的鞋款</strong>
              <p>CoachOS 不會在空白上確認。先補上鞋款，這堂課才會進入真正的學習流程。</p>
              <div class="knowledge-because">
                <span>因為</span>
                <p>目前鞋款欄位是空的，沒有可學習的對象。</p>
              </div>
              <div class="knowledge-actions">
                <a class="primary-action remember-scroll-link" href="{html.escape(metadata_href, quote=True)}">去標註鞋款</a>
                <a class="secondary-action remember-scroll-link" href="/?page=activity&activity={activity_id}&coach_step=workout#activity-knowledge">先略過</a>
              </div>
            </div>
          </section>
        """

    if missing_workout:
        metadata_href = "/?" + urlencode({
            "page": "metadata",
            "edit": activity_id,
            "scope": "missing_workout",
        }) + "#metadata-edit"
        return f"""
          <section class="panel-section" id="activity-knowledge">
            <h2>教練知識</h2>
            <p class="note">先選一個最像的，確認後 CoachOS 才會記住這堂課。</p>
            <div class="review-card knowledge-conversation-card">
              <span>這堂課的課表 · ⚡</span>
              <strong>這堂課還沒有課表，先去標註這堂課的課表</strong>
              <p>CoachOS 不會在空白上確認。先補上課表，這堂課才有辦法進入學習流程。</p>
              <div class="knowledge-because">
                <span>因為</span>
                <p>目前課表欄位是空的，沒有可學習的對象。</p>
              </div>
              <div class="knowledge-actions">
                <a class="primary-action remember-scroll-link" href="{html.escape(metadata_href, quote=True)}">去標註課表</a>
                <a class="secondary-action remember-scroll-link" href="/?page=activity&activity={activity_id}&coach_step=purpose#activity-knowledge">先略過</a>
              </div>
            </div>
          </section>
        """

    if missing_purpose:
        metadata_href = "/?" + urlencode({
            "page": "metadata",
            "edit": activity_id,
            "scope": "missing_purpose",
        }) + "#metadata-edit"
        return f"""
          <section class="panel-section" id="activity-knowledge">
            <h2>教練知識</h2>
            <p class="note">先選一個最像的，確認後 CoachOS 才會記住這堂課。</p>
            <div class="review-card knowledge-conversation-card">
              <span>這堂課的訓練目的 · 🎯</span>
              <strong>這堂課還沒有訓練目的，先去標註這堂課的目的</strong>
              <p>CoachOS 不會在空白上確認。先補上訓練目的，這堂課才會進入真正的學習流程。</p>
              <div class="knowledge-because">
                <span>因為</span>
                <p>目前訓練目的欄位是空的，沒有可學習的對象。</p>
              </div>
              <div class="knowledge-actions">
                <a class="primary-action remember-scroll-link" href="{html.escape(metadata_href, quote=True)}">去標註目的</a>
                <a class="secondary-action remember-scroll-link" href="/?page=activity&activity={activity_id}&coach_step=purpose_learned#activity-evidence">先略過</a>
              </div>
            </div>
          </section>
        """

    if fully_learned and not explicit_step and not learned_mode:
        review_href = f'/?page=activity&activity={activity_id}&coach_step=purpose_learned#activity-evidence'
        return f"""
          <section class="panel-section" id="activity-knowledge">
            <h2>教練知識</h2>
            <p class="note">這堂課已經有完整標註，CoachOS 會直接讀。</p>
            <div class="review-card knowledge-learned-card">
              <span class="knowledge-complete-badge">✓ 已完整標註 · 這堂課可直接讀取</span>
              <strong>這堂課已經有完整資料了</strong>
              <p>如果要更新鞋款、課表或訓練目的，可以直接重新調整；如果只是要看證據，現在可以直接往下看。</p>
              <div class="knowledge-complete-next">
                <span>目前狀態</span>
                <strong>完整標註</strong>
                <p>這堂課已經有可讀的鞋款、課表與訓練目的，不需要再確認一次。</p>
              </div>
              <div class="knowledge-complete-next">
                <span>下一步</span>
                <strong>查看證據 / 重新調整</strong>
                <p>若想修正資料，從重新調整開始；若想直接看證據，往下即可。</p>
              </div>
              <div class="knowledge-actions">
                <a class="secondary-action remember-scroll-link" href="{html.escape(review_href, quote=True)}">查看證據</a>
                <a class="primary-action remember-scroll-link" href="/?page=activity&activity={activity_id}&coach_step=shoe#activity-knowledge">重新調整</a>
              </div>
            </div>
          </section>
        """

    state = activity_coach_knowledge_state(activity, review, shoe_rows, workout_rows, purpose_rows)[step_key]
    activity_id = int(activity["activity_id"])
    confirm_action = "choose" if learned_mode else "confirm"

    if learned_mode:
        return f"""
          <section class="panel-section" id="activity-knowledge">
            <h2>教練知識</h2>
            <p class="note">先選一個最像的，確認後 CoachOS 才會記住這堂課。</p>
            <div class="review-card knowledge-learned-card">
              <span class="knowledge-complete-badge">✓ 已完成 · 這堂課的{html.escape(state["label"])} · {html.escape(state["icon"])}</span>
              <strong>{html.escape(state["learned"])}</strong>
              <div class="knowledge-because">
                <span>因為</span>
                <p>{html.escape(state["reason"])}</p>
              </div>
              <p>已寫入 SQLite · 這堂課的判讀已經更完整。</p>
              <div class="knowledge-complete-next">
                <span>目前狀態</span>
                <strong>這堂課已經先記住了</strong>
                <p>這堂課已經問過一次了。若要重新調整，按下面的按鈕就可以重來。</p>
              </div>
              <div class="knowledge-complete-next">
                <span>證據</span>
                <strong>{html.escape(state["next_label"])}</strong>
                <p>這一步已經完成，現在直接去看這堂課的證據。</p>
              </div>
              <div class="knowledge-actions">
                <a class="secondary-action remember-scroll-link" href="{html.escape(state["continue_href"], quote=True)}">查看證據</a>
                <a class="primary-action remember-scroll-link" href="/?page=activity&activity={activity_id}&coach_step=shoe#activity-knowledge">重新調整</a>
              </div>
            </div>
          </section>
        """

    chooser_options = []
    for row in state["rows"]:
        code = choice_row_code(row, step_key)
        label = choice_row_label(row, step_key)
        if not code or not label:
            continue
        selected = " selected" if str(code) == str(state["code"]) else ""
        chooser_options.append(f'<option value="{html.escape(str(code), quote=True)}"{selected}>{html.escape(label)}</option>')

    chooser_select = "".join(chooser_options) or '<option value="">沒有可選項目</option>'
    current_text = state["current"]
    if not current_text:
        current_text = "CoachOS doesn't know yet."
    current_block = ""
    if current_text and current_text != state["title"]:
        current_block = f'<p class="knowledge-current">{html.escape(current_text)}</p>'

    return f"""
      <section class="panel-section" id="activity-knowledge">
        <h2>教練知識</h2>
        <p class="note">先選一個最像的，確認後 CoachOS 才會記住這堂課。</p>
        <div class="review-card knowledge-conversation-card">
          <span>這堂課的{html.escape(state["label"])} · {html.escape(state["icon"])}</span>
          <strong>{html.escape(state["title"])}</strong>
          {current_block}
          <div class="knowledge-actions">
            <form class="knowledge-action-form remember-scroll-form" method="post" action="/activity/coach-knowledge">
              <input type="hidden" name="activity_id" value="{activity_id}">
              <input type="hidden" name="coach_step" value="{html.escape(step_key, quote=True)}">
              <input type="hidden" name="choice_code" value="{html.escape(str(state["code"] or ""), quote=True)}">
              <input type="hidden" name="scroll_y" value="">
              <button class="primary-action" type="submit" name="action" value="{confirm_action}">確認選擇</button>
              <button class="secondary-action" type="submit" name="action" value="skip">先略過</button>
            </form>
          </div>
          <form class="knowledge-choice-form remember-scroll-form" method="post" action="/activity/coach-knowledge">
            <input type="hidden" name="activity_id" value="{activity_id}">
            <input type="hidden" name="coach_step" value="{html.escape(step_key, quote=True)}">
            <input type="hidden" name="action" value="choose">
            <input type="hidden" name="scroll_y" value="">
            <label class="inline-field">
              <span>改選其他</span>
              <select name="choice_code">
                {chooser_select}
              </select>
            </label>
            <div class="form-actions">
              <button type="submit">確認選擇</button>
            </div>
          </form>
          <p class="note">先選一個最像的，按「確認選擇」就會記住；要改就直接換下拉選單。</p>
        </div>
      </section>
    """


def activity_split_table(split_rows):
    if not split_rows:
        return '<p class="note">目前還沒有每公里分段可以往下看。</p>'
    body = []
    for row in split_rows:
        cadence = "" if row["avg_cadence_spm"] is None else format_number(row["avg_cadence_spm"], 1)
        label = activity_split_label(row, split_rows)
        kind = split_segment_kind(row)
        distance_text = (
            f"{format_number((row['split_distance_m'] or 0) / 1000, 2)} km"
            if kind == "main"
            else f"{format_number(row['split_distance_m'], 0)} m"
        )
        body.append(
            f"""
            <tr id="split-{row["split_index"]}">
              <td>{html.escape(label)}</td>
              <td>{html.escape(distance_text)}</td>
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
              <th>片段</th>
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


def workout_split_label(row):
    split_type = str(row["split_type"] or "").strip().lower()
    if split_type == "interval_warmup":
        return "Warm-up"
    if split_type == "interval_active":
        return "主段"
    if split_type == "interval_recovery":
        return "恢復"
    if split_type == "interval_cooldown":
        return "Cool-down"
    if split_type == "rwd_run":
        return "整體跑步"
    if split_type == "rwd_walk":
        return "步行 / 起始"
    return row["split_type"] or f"片段 {row['split_index']}"


def workout_display_label(row, workout_split_rows=None):
    label = workout_split_label(row)
    distance_m = float(row["total_distance_m"] or 0)
    duration_sec = float(row["total_timer_time_sec"] or 0)
    if workout_segment_kind(row) == "active" and distance_m < 300 and duration_sec <= 30:
        return "Stride"
    rows = display_workout_splits(workout_split_rows or [])
    if len(rows) == 1 and workout_segment_kind(row) == "active":
        return "連續跑步"
    return label


def display_workout_splits(workout_split_rows):
    rows = []
    for row in workout_split_rows or []:
        split_type = str(row["split_type"] or "").strip().lower()
        distance_m = row["total_distance_m"]
        duration_sec = row["total_timer_time_sec"]
        speed_mps = row["avg_speed_mps"]
        if split_type in {"rwd_run", "rwd_walk", "rwd_stand", ""}:
            continue
        # Drop zero-length / zero-time placeholder rows that sometimes appear
        # in treadmill FIT workout messages.
        if (distance_m in (None, 0, 0.0)) and (duration_sec in (None, 0, 0.0)) and speed_mps in (None, 0, 0.0):
            continue
        rows.append(row)
    return rows


def workout_segment_kind(row):
    split_type = str(row["split_type"] or "").strip().lower()
    if split_type == "interval_warmup":
        return "warmup"
    if split_type == "interval_active":
        return "active"
    if split_type == "interval_recovery":
        return "recovery"
    if split_type == "interval_cooldown":
        return "cooldown"
    if split_type == "rwd_run":
        return "overall_run"
    if split_type == "rwd_walk":
        return "walk"
    return "other"


def split_rows_with_bounds(split_rows):
    total = 0.0
    rows = []
    for row in split_rows or []:
        distance = float(row["split_distance_m"] or 0)
        start = total
        end = total + max(distance, 0.0)
        rows.append((row, start, end))
        total = end
    return rows


def workout_split_rows_with_bounds(workout_split_rows):
    total = 0.0
    rows = []
    for row in display_workout_splits(workout_split_rows):
        distance = float(row["total_distance_m"] or 0)
        start = total
        end = total + max(distance, 0.0)
        rows.append((row, start, end))
        total = end
    return rows


def structured_focus_workout_segments(workout_split_rows):
    bounded = workout_split_rows_with_bounds(workout_split_rows)
    active = [item for item in bounded if workout_segment_kind(item[0]) == "active"]
    if active:
        substantial_active = []
        for item in active:
            row = item[0]
            distance_m = float(row["total_distance_m"] or 0)
            duration_sec = float(row["total_timer_time_sec"] or 0)
            # Treat substantial workout blocks as the real session structure,
            # while excluding very short stride-like active snippets.
            if distance_m >= 300 or duration_sec >= 60:
                substantial_active.append(item)
        if substantial_active:
            return substantial_active
        return active
    mainish = [item for item in bounded if workout_segment_kind(item[0]) in {"warmup", "active", "cooldown"}]
    return mainish or bounded


def structured_active_segment_rows(workout_split_rows):
    return [item[0] for item in structured_focus_workout_segments(workout_split_rows) if workout_segment_kind(item[0]) == "active"]


def workout_segment_overlap(split_start, split_end, segment_start, segment_end):
    return max(0.0, min(split_end, segment_end) - max(split_start, segment_start))


def structured_focus_splits(split_rows, workout_split_rows):
    if not split_rows or not workout_split_rows:
        return []
    focus_segments = structured_focus_workout_segments(workout_split_rows)
    if not focus_segments:
        return []
    raw_rows = split_rows_with_bounds(split_rows)
    selected = []
    seen = set()
    for segment, segment_start, segment_end in focus_segments:
        for row, row_start, row_end in raw_rows:
            overlap = workout_segment_overlap(row_start, row_end, segment_start, segment_end)
            if overlap <= 0:
                continue
            key = row["split_index"]
            if key in seen:
                continue
            seen.add(key)
            selected.append(row)
    selected_main = activity_analysis_splits(selected)
    if selected_main:
        selected = selected_main
    if len(focus_segments) == 1 and len(selected) >= 6:
        last_distance = float(selected[-1]["split_distance_m"] or 0)
        if 980 <= last_distance <= 1020:
            return selected[1:]
        return selected[1:-1]
    return selected


def structured_segment_for_split(row, split_rows, workout_split_rows):
    if not row or not split_rows or not workout_split_rows:
        return None
    raw_bounds = {item[0]["split_index"]: item for item in split_rows_with_bounds(split_rows)}
    current = raw_bounds.get(row["split_index"])
    if not current:
        return None
    _raw_row, row_start, row_end = current
    best = None
    best_overlap = 0.0
    for segment, segment_start, segment_end in workout_split_rows_with_bounds(workout_split_rows):
        overlap = workout_segment_overlap(row_start, row_end, segment_start, segment_end)
        if overlap > best_overlap:
            best = segment
            best_overlap = overlap
    return best


def structured_segment_label_for_split(row, split_rows, workout_split_rows):
    segment = structured_segment_for_split(row, split_rows, workout_split_rows)
    if not segment:
        return activity_split_label(row, split_rows)
    segment_label = workout_display_label(segment, workout_split_rows)
    raw_label = activity_split_label(row, split_rows)
    if raw_label.startswith("片段 ") or raw_label.startswith("KM "):
        return f"{segment_label} · {raw_label}"
    return raw_label


def activity_workout_structure_table(workout_split_rows):
    rows = display_workout_splits(workout_split_rows)
    if not rows:
        return '<p class="note">這堂課目前沒有可讀的課表片段，先看下面的原始分段。</p>'
    body = []
    for index, row in enumerate(rows, start=1):
        distance_text = (
            f"{format_number((row['total_distance_m'] or 0) / 1000, 2)} km"
            if (row["total_distance_m"] or 0) >= 1000
            else f"{format_number(row['total_distance_m'], 0)} m"
        )
        pace_text = format_pace_seconds(
            None if row["avg_speed_mps"] in (None, 0) else int(round(1000.0 / float(row["avg_speed_mps"])))
        )
        body.append(
            f"""
            <tr>
              <td>{index}</td>
              <td>{html.escape(str(workout_display_label(row, workout_split_rows)))}</td>
              <td>{html.escape(distance_text)}</td>
              <td>{html.escape(format_duration_hms(row["total_timer_time_sec"]))}</td>
              <td>{html.escape(pace_text)}</td>
            </tr>
            """
        )
    return f"""
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>課表片段</th>
              <th>距離</th>
              <th>時間</th>
              <th>片段配速</th>
            </tr>
          </thead>
          <tbody>{"".join(body)}</tbody>
        </table>
      </div>
    """


def activity_ai_handoff_text(
    activity,
    review,
    split_rows,
    workout_split_rows=None,
    weekly_review=None,
    monthly_overview=None,
    wsi=None,
    include_raw_data=False,
    saved_reply=None,
):
    if not activity or not review:
        return ""

    def raw_text(value, fallback="—"):
        if value is None:
            return fallback
        text = str(value).strip()
        return text if text else fallback

    temperature_text = f"{format_number(activity['temperature_c'], 0)}°C" if activity["temperature_c"] is not None else None
    humidity_text = f"{format_number(activity['humidity_pct'], 0)}%" if activity["humidity_pct"] is not None else None
    wind_speed_text = format_number(activity["wind_speed_mps"], 1) if activity["wind_speed_mps"] is not None else None
    wind_direction_text = format_number(activity["wind_direction_deg"], 0) if activity["wind_direction_deg"] is not None else None
    cadence_text = format_number(activity["avg_cadence_spm"], 1) if activity["avg_cadence_spm"] is not None else None
    stride_text = format_number(activity["avg_stride_length_mm"], 1) if activity["avg_stride_length_mm"] is not None else None
    gct_text = format_number(activity["avg_gct_ms"], 1) if activity["avg_gct_ms"] is not None else None
    vosc_text = format_number(activity["avg_vertical_oscillation_mm"], 1) if activity["avg_vertical_oscillation_mm"] is not None else None
    vratio_text = format_number(activity["avg_vertical_ratio_pct"], 1) if activity["avg_vertical_ratio_pct"] is not None else None
    recorded_duration_text = format_duration_hms(activity["duration_sec"])
    split_total_text = format_duration_hms(split_total_time_sec(split_rows))
    stored_activity_max_hr_text = raw_text(activity["max_hr"])
    activity_max_hr_text = raw_text("" if split_activity_max_hr(split_rows) is None else int(round(split_activity_max_hr(split_rows))))

    activity_name = str(activity["activity_name"] or activity["activity_type"] or "活動")
    workout_name = str(activity["workout_type_name_en"] or activity["activity_type"] or "活動")
    start_time = format_short_datetime(activity["activity_start_time"])
    distance_text = f"{format_number(activity['distance_km'], 2)} km"
    load_text = format_number(activity["training_load"], 0) or "—"
    pace_text = format_pace_seconds(activity["avg_pace_sec_per_km"]) or "—"
    hr_text = "" if activity["avg_hr"] is None else str(int(round(activity["avg_hr"])))
    shoe_text = str(activity["shoe_display_name"] or "未標註")
    purpose_text = str(activity["primary_training_purpose_name_en"] or "未標註")
    secondary_purpose_text = str(activity["secondary_training_purpose_names_en"] or "").strip()

    cause_lines = []
    for card in review.get("cards", []):
        cause_lines.append(f"- {card['title']}：{card['value']}；{card['note']}")

    segment_lines = []
    for row in activity_key_segments(activity, split_rows, workout_split_rows or []):
        segment_lines.append(
            f"- {row['label']}（{row['section']}）：{row['metric']}；{row['note']}"
        )

    context_lines = []
    if weekly_review:
        context_lines.append(f"- 本週學習：{weekly_review['focus']}")
    if monthly_overview:
        context_lines.append(f"- 本月位置：{monthly_overview['verdict']}；{monthly_overview['verdict_reason']}")

    prompt_lines = [
        "請根據以下已治理的跑步資料，用繁體中文做進一步分析。",
        "請先回答這堂課的整體判讀，再說明原因，最後給一個下一步提醒。",
        "只能根據我提供的內容分析，不要自行發明額外訓練、健康或心理狀態。",
    ]
    prompt_lines.extend(
        coach_prompt_reference_lines(
            "活動 AI 交棒",
            "這堂課的整體判讀、原因與下一步提醒",
            [
                "先回答這堂課真正留下來的是什麼",
                "再說明為什麼平台會這樣判讀",
                "最後只留一個下一堂課提醒",
                "若原始資料與平台判讀有衝突，先指出衝突",
            ],
            [
                "活動事實",
                "教練理解",
                "推理",
                "關鍵片段",
                "上下文",
                "證據",
            ],
            [
                "不要只看配速，必須整合心率、功率、跑姿、體力、天氣與課表目的。",
                "若資料不足，明確說明不足處，不要硬推論。",
            ],
        )
    )
    prompt_lines.extend([
        "",
        "## 活動事實",
        f"- 活動：{activity_name}",
        f"- 開始時間：{start_time}",
        f"- 類型：{workout_name}",
        f"- 距離：{distance_text}",
        f"- 負荷：{load_text}",
        f"- 平均配速：{pace_text}",
        f"- 平均心率：{hr_text}",
        f"- 鞋款：{shoe_text}",
        f"- 主要目的：{purpose_text}",
    ])
    if secondary_purpose_text:
        prompt_lines.append(f"- 次要目的：{secondary_purpose_text}")

    wsi_text = localized_wsi_values(wsi)
    prompt_lines.extend([
        "",
        "## 訓練序列理解",
        f"- 主要角色：{wsi_text['mission'] if wsi_text else '目前沒有足夠資料'}",
        f"- 教練讀法：{wsi_text['phrase'] if wsi_text else '目前沒有足夠資料'}",
        f"- 任務完成度：{wsi_text['status'] if wsi_text else '目前沒有足夠資料'}",
        f"- 序列狀態：{wsi_text['continuity'] if wsi_text else '目前沒有足夠資料'}",
        f"- 資料信心：{'建議先補標註' if wsi_text and wsi_text['evidenceQuality'] == 'needs_annotation' else '可用' if wsi_text else '目前沒有足夠資料'}",
        f"- 資料提醒：{wsi_text['evidenceNote'] if wsi_text and wsi_text['evidenceNote'] else '無'}",
        f"- 判讀原因：{wsi_text['reasoning'] if wsi_text else '目前沒有足夠的前後文，暫不過度宣告。'}",
        "",
        "## 教練理解",
        f"- 問題：{review['learning_question']}",
        f"- 學習：{review['learning']}",
        f"- 焦點：{review['focus']}",
        f"- 原因：{review['why']}",
        f"- 下一步：{review['looking_forward']}",
    ])
    if review.get("structure_note"):
        prompt_lines.append(f"- 結構說明：{review['structure_note']}")
    prompt_lines.extend([
        "",
        "## 推理",
        *cause_lines,
    ])

    if segment_lines:
        prompt_lines.extend([
            "",
            "## 關鍵片段",
            *segment_lines,
        ])

    if context_lines:
        prompt_lines.extend([
            "",
            "## 上下文",
            *context_lines,
        ])

    if include_raw_data and split_rows:
        prompt_lines.extend([
            "",
            "## 證據",
            "### 完整活動資料",
            f"- Garmin Activity ID：{raw_text(activity['garmin_activity_id'])}",
            f"- 來源檔案：{raw_text(activity['source_file_name'])}",
            f"- 資料來源：{raw_text(activity['data_source'])}",
            f"- Excel 結構版本：{raw_text(activity['excel_schema_version'])}",
            f"- 記錄時間：{raw_text(recorded_duration_text)}",
            f"- 分段總時間：{raw_text(split_total_text)}",
            f"- 氣溫：{raw_text(temperature_text)}",
            f"- 濕度：{raw_text(humidity_text)}",
            f"- 風速：{raw_text(wind_speed_text)}",
            f"- 風向：{raw_text(wind_direction_text)}",
            f"- 天氣：{raw_text(activity['weather_description'])}",
            f"- 已存活動最高心率：{stored_activity_max_hr_text}",
            f"- 活動最高心率：{activity_max_hr_text}",
            f"- 個人臨界功率設定：{raw_text(activity['critical_power_w'])}",
            f"- 有氧訓練效果：{raw_text(activity['training_effect_aerobic'])}",
            f"- 無氧訓練效果：{raw_text(activity['training_effect_anaerobic'])}",
            f"- 恢復時間：{raw_text(activity['recovery_time_hr'])}",
            f"- 體力起始：{raw_text(activity['stamina_start_pct'])}",
            f"- 體力結束：{raw_text(activity['stamina_end_pct'])}",
            f"- 平均步頻：{raw_text(cadence_text)}",
            f"- 平均步幅：{raw_text(stride_text)}",
            f"- 平均觸地時間：{raw_text(gct_text)}",
            f"- 平均垂直振幅：{raw_text(vosc_text)}",
            f"- 平均垂直比：{raw_text(vratio_text)}",
            f"- Garmin 感受：{raw_text(activity['garmin_feeling'])}",
            f"- Garmin RPE：{raw_text(activity['garmin_perceived_effort'])}",
            f"- 次要訓練目的：{raw_text(secondary_purpose_text)}",
            f"- 補給：{raw_text(activity['nutrition'])}",
            f"- 備註：{raw_text(activity['notes'])}",
            "",
            "### 完整每公里分段原始資料",
            "| 片段 | 距離 | 時間 | 配速 | 平均心率 | 最高心率 | 功率 | 步頻 | 步幅 | 觸地時間 | 垂直比 | 垂直振幅 | 爬升 | 下降 | 體力起始 | 體力結束 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ])
        for row in split_rows:
            prompt_lines.append(
                "| {label} | {distance} | {elapsed} | {pace} | {hr} | {max_hr} | {power} | {cadence} | {stride} | {gct} | {vratio} | {vosc} | {gain} | {loss} | {stamina_start} | {stamina_end} |".format(
                    label=activity_split_label(row, split_rows),
                    distance=(
                        f"{format_number((row['split_distance_m'] or 0) / 1000, 3)} km"
                        if not is_residual_split(row)
                        else f"{format_number(row['split_distance_m'], 0)} m"
                    ),
                    elapsed=raw_text(format_duration_hms(row["elapsed_time_sec"])),
                    pace=format_pace_seconds(row["elapsed_pace_sec_per_km"]) or "—",
                    hr="" if row["avg_hr"] is None else int(round(row["avg_hr"])),
                    max_hr="" if row["max_hr"] is None else int(round(row["max_hr"])),
                    power="" if row["avg_power_w"] is None else int(round(row["avg_power_w"])),
                    cadence="" if row["avg_cadence_spm"] is None else format_number(row["avg_cadence_spm"], 1),
                    stride="" if row["avg_stride_length_mm"] is None else format_number(row["avg_stride_length_mm"], 1),
                    gct="" if row["avg_gct_ms"] is None else format_number(row["avg_gct_ms"], 1),
                    vratio="" if row["avg_vertical_ratio_pct"] is None else format_number(row["avg_vertical_ratio_pct"], 1),
                    vosc="" if row["avg_vertical_oscillation_mm"] is None else format_number(row["avg_vertical_oscillation_mm"], 1),
                    gain="0" if row["elevation_gain_m"] in (None, "") else format_number(row["elevation_gain_m"], 1),
                    loss="0" if row["elevation_loss_m"] in (None, "") else format_number(row["elevation_loss_m"], 1),
                    stamina_start="" if row["stamina_start_pct"] is None else row["stamina_start_pct"],
                    stamina_end="" if row["stamina_end_pct"] is None else row["stamina_end_pct"],
                )
            )

    append_previous_ai_response(prompt_lines, saved_reply)

    prompt_lines.extend([
        "",
        "## 指示",
        "- 先講這堂課真正留下來的是什麼。",
        "- 再解釋為什麼平台會這樣判讀。",
        "- 最後只留一個下一堂課提醒。",
        "- 如果你從原始分段看見平台尚未明說、但值得注意的節奏或身體訊號，可以補充提出。",
        "- 但請明確區分：哪些是平台已經判讀的，哪些是你根據原始資料額外補充的觀察。",
        "- 如果原始資料與平台判讀有衝突，請優先指出衝突，不要直接覆蓋平台判讀。",
    ])
    prompt_lines.extend([""] + ai_handoff_response_format_instructions())

    return "\n".join(prompt_lines)


WSI_MISSION_LABELS = {
    "Build": ("建立能力", "這堂是主刺激，負責把能力往前推。"),
    "Prepare": ("準備下一堂", "這堂不是主菜，而是在幫下一個訓練目標保留可用入口。"),
    "Recover": ("吸收恢復", "這堂的重點是整理前面留下的負荷，讓身體重新變得可用。"),
    "Activate": ("重新啟動", "這堂在把腿感、節奏或跑步狀態接回來。"),
}

WSI_STATUS_LABELS = {
    "Completed": ("已完成", "今天的任務有完成。"),
    "Partial": ("部分完成", "方向是對的，但執行成本讓完成度需要保守看。"),
}

WSI_CONTINUITY_LABELS = {
    "Ready": ("已準備好", "這堂課把序列送進下一步可用狀態。"),
    "Maintained": ("維持住", "序列沒有被打斷，但也先不過度宣告已準備好。"),
    "Overloaded": ("負荷偏高", "這堂課可能讓後續銜接承受額外壓力。"),
}

WSI_EVIDENCE_LABELS = {
    "usable": ("資料足夠", "目前資料足以支撐這次序列判讀。"),
    "needs_annotation": ("建議補標註", "這筆活動需要更多課表或目的脈絡，判讀先保守看。"),
}


def wsi_label(mapping, value):
    label, description = mapping.get(value, (value, ""))
    return label, description


def localized_wsi_values(wsi):
    if not wsi:
        return None
    mission_label, _mission_description = wsi_label(WSI_MISSION_LABELS, wsi["missionCategory"])
    status_label, _status_description = wsi_label(WSI_STATUS_LABELS, wsi["missionStatus"])
    continuity_label, _continuity_description = wsi_label(WSI_CONTINUITY_LABELS, wsi["continuityState"])
    return {
        "mission": mission_label,
        "status": status_label,
        "continuity": continuity_label,
        "phrase": wsi["missionPhrase"],
        "reasoning": wsi["sequenceReasoning"],
        "evidenceQuality": wsi.get("evidenceQuality", "usable"),
        "evidenceNote": wsi.get("evidenceNote", ""),
    }


def wsi_context_workout(wsi, key):
    context = wsi.get("context") if wsi else None
    if not isinstance(context, dict):
        return None
    workout = context.get(key)
    return workout if isinstance(workout, dict) else None


def wsi_context_label(workout, short=False):
    if not workout:
        return ""
    date_text = str(workout.get("activity_date") or workout.get("activity_start_time") or "")[:10]
    label = (
        workout.get("workout_type_name_zh")
        or workout.get("workout_type_name_en")
        or workout.get("activity_name")
        or workout.get("activity_type")
        or "活動"
    )
    distance = workout.get("distance_km")
    distance_text = ""
    try:
        if distance not in (None, ""):
            distance_text = f"{float(distance):g} km"
    except (TypeError, ValueError):
        distance_text = ""
    if short:
        return str(label)
    details = []
    if date_text:
        details.append(date_text)
    details.append(str(label))
    if distance_text:
        details.append(distance_text)
    return " · ".join(details)


def wsi_product_outcome(continuity_state):
    if continuity_state == "Ready":
        return "已準備好下一堂"
    if continuity_state == "Overloaded":
        return "後續銜接要保守"
    return "序列維持住"


def wsi_product_coach_explanation(wsi):
    mission = wsi.get("missionCategory")
    status = wsi.get("missionStatus")
    continuity = wsi.get("continuityState")
    previous = wsi_context_workout(wsi, "previousWorkout")
    next_workout = wsi_context_workout(wsi, "nextWorkout")
    previous_label = wsi_context_label(previous, short=True)
    next_label = wsi_context_label(next_workout, short=True)

    if mission == "Prepare":
        if next_label:
            lead = f"今天不是增加能力的一天，而是替{next_label}保留最佳入口。"
        else:
            lead = "今天的主要任務不是增加能力，而是在目前序列中保留下一步訓練的可用入口。"
        if status == "Partial":
            return f"{lead}方向是對的，但這堂執行成本偏高，所以先把完成度保守看，不直接宣告已完全準備好。"
        if continuity == "Ready":
            return f"{lead}這堂課有完成它的銜接任務，因此可以把序列推到下一步可用狀態。"
        return f"{lead}序列沒有被打斷，但目前仍先保守判定為維持住。"
    if mission == "Build":
        lead = "今天是主刺激，重點是把能力往前推。"
        if continuity == "Overloaded":
            return f"{lead}但這堂也讓後續承受比較多壓力，下一步銜接要保守一點。"
        return f"{lead}任務本身有完成，但建立能力不等於立刻準備好下一堂，所以序列狀態先看成維持住。"
    if mission == "Recover":
        if previous_label:
            return f"今天的重點不是再堆更多刺激，而是整理{previous_label}後留下的負荷。這樣讀，比單純把它看成輕鬆跑，更能保住整段序列的恢復意義。"
        return "今天的重點不是再堆更多刺激，而是讓身體重新變得可用。這樣讀，比單純把它看成輕鬆跑，更接近教練會看的序列意義。"
    if mission == "Activate":
        return "今天的重點是把腿感、節奏或跑步狀態重新接回來。它不一定是主刺激，也不一定是在準備特定一堂，而是在讓訓練節奏重新啟動。"
    return wsi.get("missionPhrase") or wsi.get("sequenceReasoning") or "目前資料仍需要保守判讀。"


def wsi_period_summary(connection, start_date, end_date, period_label):
    if not start_date or not end_date:
        return None
    rows = connection.execute(
        """
        SELECT
            r.activity_id,
            r.activity_date,
            r.distance_km,
            COALESCE(r.workout_type_name_zh, r.activity_type, '活動') AS workout_label,
            w.mission_category,
            w.mission_status,
            w.continuity_state,
            w.evidence_quality
        FROM activity_review_view r
        LEFT JOIN activity_wsi w ON w.activity_id = r.activity_id
        WHERE r.activity_date BETWEEN ? AND ?
        ORDER BY r.activity_start_time
        """,
        (start_date, end_date),
    ).fetchall()
    if not rows:
        return None

    usable_rows = [row for row in rows if row["evidence_quality"] == "usable"]
    mission_counts = Counter(
        row["mission_category"]
        for row in usable_rows
        if row["mission_category"]
    )
    status_counts = Counter(
        row["mission_status"]
        for row in usable_rows
        if row["mission_status"]
    )
    continuity_counts = Counter(
        row["continuity_state"]
        for row in usable_rows
        if row["continuity_state"]
    )
    evidence_counts = Counter(
        row["evidence_quality"] or "needs_annotation"
        for row in rows
    )
    mission_examples = {}
    for row in usable_rows:
        mission = row["mission_category"]
        if not mission:
            continue
        mission_examples.setdefault(mission, []).append({
            "activityId": row["activity_id"],
            "date": row["activity_date"],
            "label": row["workout_label"],
            "distanceKm": row["distance_km"],
        })
    missing_wsi = sum(1 for row in rows if not row["mission_category"])
    dominant_mission = None
    dominant_missions = []
    if mission_counts:
        mission_order = {"Build": 0, "Prepare": 1, "Recover": 2, "Activate": 3}
        max_count = max(mission_counts.values())
        dominant_missions = [
            mission
            for mission, count in sorted(
                mission_counts.items(),
                key=lambda item: (mission_order.get(item[0], 99), item[0]),
            )
            if count == max_count
        ]
        dominant_mission = dominant_missions[0]

    usable_count = evidence_counts.get("usable", 0)
    needs_annotation_count = evidence_counts.get("needs_annotation", 0) + missing_wsi

    return {
        "periodLabel": period_label,
        "startDate": start_date,
        "endDate": end_date,
        "total": len(rows),
        "missionCounts": dict(mission_counts),
        "missionExamples": mission_examples,
        "statusCounts": dict(status_counts),
        "continuityCounts": dict(continuity_counts),
        "usableCount": usable_count,
        "needsAnnotationCount": needs_annotation_count,
        "missingWsiCount": missing_wsi,
        "dominantMission": dominant_mission,
        "dominantMissions": dominant_missions,
    }


def wsi_period_interpretation(summary):
    if not summary:
        return ""
    total = summary["total"]
    if total == 0:
        return "這段期間還沒有活動可以形成序列理解。"
    if not summary["dominantMission"]:
        return "這段期間已有活動，但還沒有足夠的序列理解結果。先重算 WSI 或補齊活動標註後，週/月判讀會更完整。"

    mission_label, _mission_description = wsi_label(
        WSI_MISSION_LABELS,
        summary["dominantMission"],
    )
    mission_count = summary["missionCounts"].get(summary["dominantMission"], 0)
    ready_count = summary["continuityCounts"].get("Ready", 0)
    overloaded_count = summary["continuityCounts"].get("Overloaded", 0)
    partial_count = summary["statusCounts"].get("Partial", 0)
    needs_annotation_count = summary["needsAnnotationCount"]

    if summary["dominantMission"] == "Build":
        base = f"{summary['periodLabel']}有 {mission_count} 堂主要在建立能力，代表這段時間的主刺激比較明確。"
    elif summary["dominantMission"] == "Prepare":
        base = f"{summary['periodLabel']}有 {mission_count} 堂主要在銜接下一個訓練目標，重點是讓後面的課接得起來。"
    elif summary["dominantMission"] == "Recover":
        base = f"{summary['periodLabel']}有 {mission_count} 堂主要在吸收恢復，表示恢復義務在這段訓練裡很重要。"
    elif summary["dominantMission"] == "Activate":
        base = f"{summary['periodLabel']}有 {mission_count} 堂主要在重新啟動節奏，重點是把腿感與跑步狀態接回來。"
    else:
        base = f"{summary['periodLabel']}最多的是「{mission_label}」，共有 {mission_count} 堂。"

    modifiers = []
    if ready_count:
        modifiers.append(f"{ready_count} 堂把序列推到可用狀態")
    if partial_count:
        modifiers.append(f"{partial_count} 堂完成度需要保守看")
    if overloaded_count:
        modifiers.append(f"{overloaded_count} 堂對後續銜接形成壓力")
    if needs_annotation_count:
        modifiers.append(f"{needs_annotation_count} 堂需要補標註或重算後再提高信心")

    if modifiers:
        return f"{base} 另外，{ '，'.join(modifiers) }。"
    return base


def monthly_wsi_learning(summary):
    if not summary or summary.get("periodLabel") != "本月" or not summary.get("dominantMission"):
        return None
    total = max(1, int(summary.get("total") or 0))
    mission_counts = summary.get("missionCounts", {})
    prepare_count = int(mission_counts.get("Prepare", 0) or 0)
    build_count = int(mission_counts.get("Build", 0) or 0)
    recover_count = int(mission_counts.get("Recover", 0) or 0)
    activate_count = int(mission_counts.get("Activate", 0) or 0)
    ready_count = int(summary.get("continuityCounts", {}).get("Ready", 0) or 0)
    partial_count = int(summary.get("statusCounts", {}).get("Partial", 0) or 0)
    dominant = summary["dominantMission"]
    dominant_missions = set(summary.get("dominantMissions") or [dominant])

    if {"Build", "Recover"}.issubset(dominant_missions):
        title = "建構與吸收並重的訓練月"
        body = "這個月不是單純往前推，也不是單純恢復；主刺激與恢復義務同時很明顯，代表訓練一邊建立能力，一邊整理累積的負荷。"
    elif {"Build", "Prepare"}.issubset(dominant_missions):
        title = "建構與銜接並重的訓練月"
        body = "這個月既有明確主刺激，也有足夠銜接課把後面的訓練接起來。重點不是單次突破，而是讓刺激能持續成立。"
    elif dominant == "Prepare" and prepare_count / total >= 0.38:
        title = "以銜接為主的建構月"
        body = "這個月不是一直堆主刺激，而是反覆把身體送進下一堂可用狀態，讓品質與耐力課能持續成立。"
    elif dominant == "Build":
        title = "主刺激明確的建構月"
        body = "這個月的重點比較直接：用多堂主刺激把能力往前推。接下來真正要看的，是恢復與銜接有沒有跟上。"
    elif dominant == "Recover":
        title = "以吸收為主的調整月"
        body = "這個月最常出現的是恢復義務，代表訓練不是只往前堆，而是在整理前面累積的負荷，讓身體重新變得可用。"
    elif dominant == "Activate":
        title = "以重新啟動為主的銜接月"
        body = "這個月有較多課在把腿感、節奏或跑步狀態接回來，重點是恢復訓練節奏，而不是直接堆更大的刺激。"
    else:
        label, _description = wsi_label(WSI_MISSION_LABELS, dominant)
        title = f"以{label}為主的訓練月"
        body = "這個月的主要訓練角色已經開始浮現，但仍需要更多標註與前後脈絡來提高月層級判讀品質。"

    supporting = []
    if build_count:
        supporting.append(f"{build_count} 堂主刺激負責把能力往前推")
    if prepare_count:
        supporting.append(f"{prepare_count} 堂銜接課負責讓下一堂接得起來")
    if recover_count:
        supporting.append(f"{recover_count} 堂恢復課負責整理負荷")
    if activate_count:
        supporting.append(f"{activate_count} 堂重新啟動負責接回節奏")
    if ready_count:
        supporting.append(f"{ready_count} 堂把序列推到可用狀態")
    if partial_count:
        supporting.append(f"{partial_count} 堂完成度需要保守看")

    return {
        "title": title,
        "body": body,
        "supporting": supporting[:4],
    }


def wsi_period_prompt_lines(summary):
    if not summary:
        return []
    dominant_label = "—"
    dominant_missions = summary.get("dominantMissions") or ([summary["dominantMission"]] if summary["dominantMission"] else [])
    if dominant_missions:
        dominant_label = " / ".join(
            wsi_label(WSI_MISSION_LABELS, mission)[0]
            for mission in dominant_missions
        )
    mission_parts = []
    for mission in ["Build", "Prepare", "Recover", "Activate"]:
        count = summary["missionCounts"].get(mission, 0)
        if not count:
            continue
        label, _description = wsi_label(WSI_MISSION_LABELS, mission)
        mission_parts.append(f"{label} {count}")
    continuity_parts = []
    for state in ["Ready", "Maintained", "Overloaded"]:
        count = summary["continuityCounts"].get(state, 0)
        if not count:
            continue
        label, _description = wsi_label(WSI_CONTINUITY_LABELS, state)
        continuity_parts.append(f"{label} {count}")
    lines = [
        f"- 期間：{summary['startDate']} – {summary['endDate']}",
        f"- 主要序列角色：{dominant_label}",
        f"- 任務分布：{', '.join(mission_parts) if mission_parts else '尚未形成'}",
        f"- 序列狀態：{', '.join(continuity_parts) if continuity_parts else '尚未形成'}",
        f"- 資料信心：{summary['usableCount']}/{summary['total']} 可用；需要補標註 {summary['needsAnnotationCount']} 堂",
        f"- 序列讀法：{wsi_period_interpretation(summary)}",
    ]
    learning = monthly_wsi_learning(summary)
    if learning:
        lines.extend([
            f"- 本月位置：{learning['title']}",
            f"- 月層級教練判讀：{learning['body']}",
        ])
    return lines


def wsi_period_panel(summary):
    if not summary:
        return ""

    mission_order = ["Build", "Prepare", "Recover", "Activate"]
    mission_items = []
    for mission in mission_order:
        count = summary["missionCounts"].get(mission, 0)
        if not count:
            continue
        label, description = wsi_label(WSI_MISSION_LABELS, mission)
        examples = []
        for item in summary.get("missionExamples", {}).get(mission, [])[:4]:
            distance = format_number(item.get("distanceKm"), 2)
            distance_text = f" · {distance} km" if distance else ""
            activity_href = "/?" + urlencode({"page": "activity", "activity": item.get("activityId")})
            examples.append(
                f"""
                <li>
                  <a href="{html.escape(activity_href, quote=True)}">
                    <span>{html.escape(str(item.get("date") or ""))}</span>
                    <strong>{html.escape(str(item.get("label") or "活動"))}{html.escape(distance_text)}</strong>
                  </a>
                </li>
                """
            )
        hidden_count = max(0, count - len(examples))
        hidden_note = f'<li class="wsi-mission-more">另外 {hidden_count} 堂</li>' if hidden_count else ""
        example_html = f"""
              <ul class="wsi-mission-list">
                {"".join(examples)}
                {hidden_note}
              </ul>
        """ if examples else ""
        mission_items.append(
            f"""
            <div class="review-card">
              <span>{html.escape(label)}</span>
              <strong>{html.escape(str(count))} 堂</strong>
              <p>{html.escape(description)}</p>
              {example_html}
            </div>
            """
        )
    if not mission_items:
        mission_items.append(
            """
            <div class="review-card">
              <span>尚未形成分布</span>
              <strong>—</strong>
              <p>這段期間還沒有可用的 WSI 結果。</p>
            </div>
            """
        )

    dominant_label = "—"
    dominant_missions = summary.get("dominantMissions") or ([summary["dominantMission"]] if summary["dominantMission"] else [])
    if dominant_missions:
        dominant_label = " / ".join(
            wsi_label(WSI_MISSION_LABELS, mission)[0]
            for mission in dominant_missions
        )

    period_label = summary["periodLabel"]
    interpretation = wsi_period_interpretation(summary)
    monthly_learning = monthly_wsi_learning(summary)
    monthly_learning_html = ""
    if monthly_learning:
        supporting_html = ""
        if monthly_learning["supporting"]:
            supporting_html = f"""
              <div class="wsi-month-supporting">
                {"".join(f"<span>{html.escape(item)}</span>" for item in monthly_learning["supporting"])}
              </div>
            """
        monthly_learning_html = f"""
          <div class="wsi-month-hero">
            <span>這個月的位置</span>
            <strong>{html.escape(monthly_learning["title"])}</strong>
            <p>{html.escape(monthly_learning["body"])}</p>
            {supporting_html}
          </div>
        """
    annotation_hint = ""
    if summary["needsAnnotationCount"]:
        low_confidence_count = int(summary["needsAnnotationCount"])
        annotation_hint = f"""
          <p class="note">有 {low_confidence_count} 堂資料信心較低。這通常不是 WSI 壞掉，而是活動標註或前後脈絡還不夠清楚。</p>
        """

    return f"""
      <section class="panel-section" id="{html.escape(period_label)}-sequence-intelligence">
        <h2>{html.escape(period_label)}訓練重點</h2>
        <p class="note">這裡不是重算單堂課，而是把這段期間的活動放回前後脈絡裡，看主要在建立能力、準備下一堂、吸收恢復，還是重新啟動節奏。</p>
        {monthly_learning_html}
        <div class="metric-grid training-kpi-grid briefing-evidence-grid">
          {activity_driver_card('主要序列角色', dominant_label, f'{period_label}出現最多的訓練序列角色。')}
          {activity_driver_card('資料信心', f"{summary['usableCount']}/{summary['total']} 可用", '可用代表目前標註與前後活動足以支撐序列判讀。')}
          {activity_driver_card('需要補標註', f"{summary['needsAnnotationCount']} 堂", '這些活動會先保守判讀，補標註後週/月理解會更穩。')}
        </div>
        <div class="coach-summary review-summary">
          <span>這段期間的序列讀法</span>
          <p>{html.escape(interpretation)}</p>
          {annotation_hint}
        </div>
        <div class="metric-grid briefing-evidence-grid">
          {"".join(mission_items)}
        </div>
      </section>
    """


def activity_wsi_panel(wsi, activity_id=None):
    if not wsi:
        return ""
    mission_label, mission_description = wsi_label(WSI_MISSION_LABELS, wsi["missionCategory"])
    status_label, status_description = wsi_label(WSI_STATUS_LABELS, wsi["missionStatus"])
    continuity_label, continuity_description = wsi_label(WSI_CONTINUITY_LABELS, wsi["continuityState"])
    evidence_label, evidence_description = wsi_label(
        WSI_EVIDENCE_LABELS,
        wsi.get("evidenceQuality", "usable"),
    )
    needs_annotation = wsi.get("evidenceQuality") == "needs_annotation"
    confidence_class = "watch" if needs_annotation else "balanced"
    continuity_class = {
        "Ready": "ready",
        "Maintained": "maintained",
        "Overloaded": "overloaded",
    }.get(wsi["continuityState"], "maintained")
    outcome_headline = wsi_product_outcome(wsi["continuityState"])
    coach_explanation = wsi_product_coach_explanation(wsi)
    previous = wsi_context_workout(wsi, "previousWorkout")
    next_workout = wsi_context_workout(wsi, "nextWorkout")
    previous_label = wsi_context_label(previous) or "目前沒有前一堂資料"
    next_label = wsi_context_label(next_workout) or "目前沒有已知後續活動"
    annotation_link = ""
    if needs_annotation and activity_id:
        annotation_href = "/?" + urlencode({"page": "metadata", "edit": activity_id, "scope": "all"}) + "#metadata-edit"
        annotation_link = f'<a class="button secondary" href="{html.escape(annotation_href, quote=True)}">先補這筆標註</a>'
    evidence_warning = ""
    if needs_annotation:
        evidence_warning = f"""
          <div class="coach-summary review-summary">
            <span>判讀信心較低</span>
            <p>{html.escape(wsi.get('evidenceNote') or '這筆活動需要先補標註，WSI 才會更穩。')}</p>
            {annotation_link}
          </div>
        """
    refresh_form = ""
    if activity_id:
        refresh_form = f"""
          <form method="post" action="/activity/recompute-wsi" class="knowledge-action-form remember-scroll-form">
            <input type="hidden" name="activity_id" value="{int(activity_id)}">
            <input type="hidden" name="scroll_y" value="">
            <button class="secondary-action" type="submit">重新產生序列理解</button>
          </form>
        """
    return f"""
      <section class="panel-section" id="activity-sequence-intelligence">
        <h2>訓練序列理解</h2>
        <div class="review-card knowledge-conversation-card activity-compact-card wsi-product-card">
          <div class="wsi-card-head">
            <div>
              <span>這不是單堂課評分，而是把這堂課放回前後訓練裡看。</span>
              <p class="note">CoachOS 會先看前一堂、這一堂與目前已知的後續活動，再判斷今天是在建立能力、準備下一堂、吸收恢復，還是重新啟動節奏。</p>
            </div>
            <span class="status-badge {confidence_class}">{html.escape(evidence_label)}</span>
          </div>
          {evidence_warning}
          <div class="wsi-hero">
            <span>今天這堂課的位置</span>
            <strong>{html.escape(mission_label)}</strong>
            <p>{html.escape(wsi['missionPhrase'])}</p>
          </div>
          <div class="wsi-outcome-card {html.escape(continuity_class)}">
            <span>現在可以往下一堂了嗎？</span>
            <strong>{html.escape(outcome_headline)}</strong>
            <p>{html.escape(continuity_description)}</p>
          </div>
          <div class="metric-grid briefing-evidence-grid wsi-status-grid">
            {activity_driver_card('任務完成度', status_label, status_description)}
            {activity_driver_card('序列狀態', continuity_label, continuity_description)}
          </div>
          <div class="knowledge-because">
            <span>教練怎麼看</span>
            <p>{html.escape(coach_explanation)}</p>
          </div>
          <div class="wsi-evidence-row">
            <span>前一堂：{html.escape(previous_label)}</span>
            <span>下一堂：{html.escape(next_label)}</span>
          </div>
          <details class="wsi-raw-reasoning">
            <summary>查看平台判讀依據</summary>
            <p>{html.escape(wsi['sequenceReasoning'])}</p>
            <p class="note">資料信心：{html.escape(evidence_label)}。{html.escape(evidence_description)}</p>
          </details>
          <div class="knowledge-actions">
            {refresh_form}
          </div>
        </div>
      </section>
    """


def activity_ai_handoff_panel(activity, review, split_rows, workout_split_rows=None, weekly_review=None, monthly_overview=None, wsi=None, saved_reply=None):
    handoff_text = activity_ai_handoff_text(
        activity,
        review,
        split_rows,
        workout_split_rows,
        weekly_review,
        monthly_overview,
        wsi,
        include_raw_data=True,
        saved_reply=saved_reply,
    )
    daily_card_prompt = activity_daily_training_card_prompt(
        activity,
        review,
        split_rows,
        workout_split_rows,
        weekly_review,
        monthly_overview,
        saved_reply,
    )
    if not handoff_text:
        return ""

    escaped_text = html.escape(handoff_text)
    escaped_daily_card_prompt = html.escape(daily_card_prompt) if daily_card_prompt else ""
    title = f'{format_short_datetime(activity["activity_start_time"])} 單堂課 AI 回覆'
    saved_panel = ai_reply_saved_panel(title, saved_reply, "activity", activity_id=str(activity["activity_id"]))
    capture_panel = ai_reply_capture_panel("activity", str(activity["activity_id"]), title, "activity", saved_reply, activity_id=str(activity["activity_id"]))

    return f"""
      {saved_panel}
      <section class="panel-section" id="activity-ai-handoff">
        <h2>AI 延伸分析</h2>
        <div class="review-card ai-handoff-card">
          <span>AI 交棒</span>
          <strong>把這堂課的教練脈絡直接交給你習慣的 AI</strong>
          <p>如果你看完這堂課後，想沿著平台已經整理好的判讀、片段與完整活動資料繼續往下聊，這裡就是完整交棒內容。</p>
          <div class="ai-handoff-block">
            <div class="ai-handoff-block-head">
              <div>
                <strong>完整交棒內容</strong>
                <p class="note">包含教練判讀、形成原因、關鍵片段、上下文、完整活動欄位與完整分段證據。</p>
              </div>
              <div class="ai-handoff-actions">
                <button class="secondary-action" type="button" onclick="copyAiHandoff('activity-ai-handoff')">複製給 AI</button>
              </div>
            </div>
            <details class="ai-handoff-preview">
              <summary>先看會交出去的內容</summary>
              <textarea id="activity-ai-handoff" readonly>{escaped_text}</textarea>
            </details>
          </div>
          <p class="note" id="activity-ai-handoff-status">先看完這堂課，再複製交給你習慣的 AI 繼續分析。</p>
        </div>
        <div class="review-card ai-handoff-card">
          <span>每日訓練圖卡提示</span>
          <strong>把這堂課交給圖像 AI 做成每日訓練圖卡</strong>
          <p>這個 prompt 會直接帶入今日摘要、課表結構、平台判讀與關鍵片段；即使還沒先跑 AI 延伸分析，也能直接拿去做圖卡。</p>
          <div class="ai-handoff-block">
            <div class="ai-handoff-block-head">
              <div>
                <strong>圖卡 prompt</strong>
                <p class="note">平台自己的判讀已經會先放進去；若你之前存過 AI 回覆，也只會當補充脈絡。</p>
              </div>
              <div class="ai-handoff-actions">
                <button class="secondary-action" type="button" onclick="copyAiHandoff('activity-daily-card-prompt')">複製給 AI</button>
              </div>
            </div>
            <details class="ai-handoff-preview">
              <summary>先看圖卡 prompt</summary>
              <textarea id="activity-daily-card-prompt" readonly>{escaped_daily_card_prompt}</textarea>
            </details>
          </div>
          <p class="note">如果你只想做一張每日訓練圖卡，直接複製這段就能用；不需要先經過完整 AI 交棒。</p>
        </div>
      </section>
      {capture_panel}
    """


def activity_review_panel(
    activity,
    split_rows,
    workout_split_rows,
    activity_rows,
    selected_activity_id,
    shoe_rows,
    workout_rows,
    purpose_rows,
    coach_step=None,
    weekly_review=None,
    monthly_overview=None,
    wsi=None,
    saved_reply=None,
):
    if not activity:
        return """
        <section class="panel-section">
          <h2>活動摘要</h2>
          <p class="note">目前還沒有活動可以建立回顧。</p>
        </section>
        """

    review = activity_review_payload(activity, split_rows, workout_split_rows)
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
      {activity_facts_panel(activity, split_rows, workout_split_rows)}
      <section class="panel-section" id="activity-summary">
        <h2>活動摘要</h2>
        <div class="review-card knowledge-conversation-card activity-compact-card activity-summary-card">
          <span>快速判讀</span>
          <strong>{html.escape(str(activity["activity_name"] or activity["activity_type"] or "活動"))}</strong>
          <p>{html.escape(review["focus"])}</p>
          <div class="knowledge-because">
            <span>為什麼重要</span>
            <p>{html.escape(review["why"])}</p>
          </div>
        </div>
      </section>
      <section class="panel-section" id="activity-review">
        <h2>教練判讀</h2>
        <div class="review-card knowledge-conversation-card activity-compact-card activity-review-card" id="activity-learning">
          <span>先回答一件事</span>
          <strong>{html.escape(review["learning_question"])}</strong>
          <p>{html.escape(review["learning"])}</p>
          {'<p class="note">這次判讀先讀課表片段，再回頭核對原始分段，所以主段、恢復與收操會分開理解。</p>' if review.get("reads_workout_structure") else ''}
          {f'<p class="note">{html.escape(review["structure_note"])}</p>' if review.get("structure_note") else ''}
          <div class="reasoning-jump-row">
            {"".join(f'<a class="inline-jump-link" href="{html.escape(href, quote=True)}">{html.escape(label)}</a>' for label, href in review["reasoning_steps"])}
          </div>
          <div class="knowledge-because">
            <span>教練判讀</span>
            <p>{html.escape(review["why"])}</p>
          </div>
          <div class="knowledge-because">
            <span>下一堂課，只記住一件事</span>
            <p>{html.escape(review["looking_forward"])}</p>
          </div>
        </div>
      </section>
      {activity_coach_knowledge_panel(activity, split_rows, shoe_rows, workout_rows, purpose_rows, coach_step)}
      <section class="panel-section" id="activity-evidence">
        <h2>證據</h2>
        <p class="note">{html.escape(review["evidence_intro"])}</p>
        <h3 class="subsection-title">什麼真正讓你學會了這件事？</h3>
        <div class="metric-grid training-kpi-grid briefing-evidence-grid">
          {"".join(activity_driver_card(card["title"], card["value"], card["note"], card.get("fragment_anchor"), card.get("evidence_anchor"), card.get("segment_label")) for card in review["cards"])}
        </div>
        <h3 class="subsection-title">教練看了哪些關鍵片段</h3>
        <p class="note">先看教練停在哪幾段，再一路往下核對那一段的實際分段。</p>
        {activity_fragment_table(activity, split_rows, workout_split_rows)}
      </section>
      {activity_wsi_panel(wsi, activity["activity_id"] if activity else None)}
      {activity_ai_handoff_panel(activity, review, split_rows, workout_split_rows, weekly_review, monthly_overview, wsi, saved_reply)}
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
              <p>旅程記住的不是單一數字，而是你正在長出來的能力。</p>
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


def monthly_review_panel(monthly, intelligence, progress_row, assignment_quality_row, history_rows, distribution_rows, key_session_rows, workout_structure_summary_rows, related_week_rows, available_month_rows, selected_month, knowledge_summary=None, coach_memory=None, wsi_summary=None, saved_reply=None):
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

    if knowledge_summary and knowledge_summary.get("count"):
        verdict_reason = (
            f"{verdict_reason} 這個判讀也已經把 {knowledge_summary['count']} 堂已確認活動的教練知識一起納入。"
        )

    letter = monthly_letter_payload(monthly, intelligence, verdict, phase, progress_pct)
    why_points = monthly_briefing_why_points(monthly, intelligence, progress_row, coach_memory, knowledge_summary)

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
        ("AI 延伸分析", "#monthly-ai-handoff"),
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
            <div class="coach-summary review-summary">
              <span>教練知識</span>
              <strong>{html.escape(knowledge_summary["headline"] if knowledge_summary else "這個月的教練知識還在累積")}</strong>
              <p>{html.escape(knowledge_summary["detail"] if knowledge_summary else "先讓已確認的活動慢慢堆起來，月回顧就會更容易讀懂。")}</p>
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
      {wsi_period_panel(wsi_summary)}
      {monthly_ai_handoff_panel(monthly, intelligence, progress_row, distribution_rows, key_session_rows, workout_structure_summary_rows, related_week_rows, coach_memory, knowledge_summary, wsi_summary, saved_reply)}
    """


def weekly_review_panel(
    weekly,
    intelligence,
    history_rows,
    distribution_rows,
    key_session_rows,
    workout_structure_summary_rows,
    selected_week="0",
    history_rows_with_labels=None,
    knowledge_summary=None,
    monthly_overview=None,
    overview_attention=None,
    wsi_summary=None,
    saved_reply=None,
):
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
    review = weekly_review_payload(weekly, intelligence, knowledge_summary)
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
              <span>教練知識</span>
              <strong>{html.escape(knowledge_summary["headline"] if knowledge_summary else review["knowledge_headline"] or "這週的教練知識還在累積")}</strong>
              <p>{html.escape(knowledge_summary["detail"] if knowledge_summary else review["knowledge_detail"] or "先讓已確認的活動慢慢累積起來。")}</p>
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
      {wsi_period_panel(wsi_summary)}
      {weekly_ai_handoff_panel(weekly, intelligence, review, distribution_rows, key_session_rows, workout_structure_summary_rows, history_rows, history_rows_with_labels, monthly_overview, overview_attention, knowledge_summary, wsi_summary, saved_reply)}
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


def shoes_page_panel(rows, intelligence_rows, workout_rows, status_rows, scope_counts=None, message=""):
    used_rows = [row for row in rows if (row["run_count"] or 0) > 0]
    active_rows = [row for row in rows if row["is_active"]]
    tagged_rows = [row for row in intelligence_rows if (row["tagged_activity_count"] or 0) > 0]
    missing_shoe_count = int((scope_counts["missing_shoe"] or 0) if scope_counts else 0)
    unassigned_count = int((scope_counts["unassigned"] or 0) if scope_counts else 0)

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
                    "最低標註觸地時間",
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
        form_id = f"shoe-status-form-{row['id']}"
        status_editor_rows.append(
            f"""
            <tr>
              <td>{html.escape(display_name)}</td>
              <td>
                <form id="{html.escape(form_id, quote=True)}" method="post" action="/shoes/save-status" class="inline-status-form remember-scroll-form">
                  <input type="hidden" name="shoe_id" value="{row["id"]}">
                  <input type="hidden" name="scroll_y" value="">
                </form>
                {metadata_select("category", SHOE_CATEGORY_OPTIONS, row["category"] or "", allow_blank=True, form_id=form_id)}
              </td>
              <td>
                  <label class="inline-field">
                    <span>狀態</span>
                    <select name="is_active" form="{html.escape(form_id, quote=True)}">
                      <option value="1"{active_selected}>服役中</option>
                      <option value="0"{retired_selected}>已退役</option>
                    </select>
                  </label>
              </td>
              <td>
                  <label class="inline-field">
                    <span>退役日期</span>
                    <input type="date" name="retire_date" form="{html.escape(form_id, quote=True)}" value="{html.escape(str(row["retire_date"] or ""), quote=True)}">
                  </label>
              </td>
              <td>
                  <button type="submit" form="{html.escape(form_id, quote=True)}">儲存</button>
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
    next_cleanup_text = (
        f"目前還有 {missing_shoe_count} 筆歷史活動缺鞋款，補完後鞋款比較才會開始變乾淨。"
        if missing_shoe_count > 0
        else "鞋款資料已經補齊，接下來可以回頭整理課表與訓練目的，讓比較更乾淨。"
    )
    next_cleanup_href = (
        "/?" + urlencode({"page": "metadata", "scope": "missing_shoe"})
        if missing_shoe_count > 0
        else "/?" + urlencode({"page": "metadata", "scope": "unassigned"})
    )
    next_cleanup_label = "去補歷史鞋款標註" if missing_shoe_count > 0 else "查看還有哪些標註沒補"
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
            <form method="post" action="/shoes/add" class="metadata-form remember-scroll-form">
              <input type="hidden" name="scroll_y" value="">
              <label>
                <span>鞋款名稱</span>
                <input type="text" name="shoe_name" placeholder="例如：Adidas Boston 13" required>
              </label>
              <label>
                <span>初始化分類</span>
                {metadata_select("category", SHOE_CATEGORY_OPTIONS, "", allow_blank=True)}
              </label>
              <div class="form-actions">
                <button type="submit">新增鞋款</button>
              </div>
            </form>
          </div>
          <div class="weekly-review-side">
            <div class="review-card">
              <span>新增後會影響</span>
              <strong>活動 / 週回顧 / 月回顧</strong>
              <p>鞋款補齊後，單堂課、週回顧與鞋款頁的判讀都會更完整。</p>
            </div>
            <div class="review-card">
              <span>下一步</span>
              <strong>{missing_shoe_count if missing_shoe_count > 0 else unassigned_count}</strong>
              <p>{html.escape(next_cleanup_text)}</p>
              <p><a href="{html.escape(next_cleanup_href, quote=True)}">{html.escape(next_cleanup_label)}</a></p>
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
          <p class="note">若設定還不夠，先到設定中心補鞋款與課表，這裡的判讀就會自然變清楚。</p>
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
        <p class="note">先把鞋況整理乾淨，之後補歷史活動設定時，設定中心就能區分服役中與已退役鞋款。</p>
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
                <th>觸地時間</th>
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
    href = "/?" + urlencode({"page": "metadata", "scope": scope}) + "#metadata-batch"
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
        missing.append("鞋款")
    if row["workout_type_id"] is None:
        missing.append("課表")
    if row["primary_training_purpose_id"] is None:
        missing.append("目的")
    if not missing:
        return "完整"
    return "缺少：" + "、".join(missing)


def metadata_select(name, options, selected_code="", allow_blank=False, include_keep=False, form_id=""):
    tags = []
    if include_keep:
        tags.append('<option value="__KEEP__">（保留原值）</option>')
        tags.append('<option value="__CLEAR__">（清空）</option>')
    elif allow_blank:
        tags.append('<option value="">（無）</option>')
    for option in options:
        if isinstance(option, dict):
            code = option.get("code", "")
            label = option.get("label", "")
            extra = option.get("extra", "")
        else:
            code = option[0] if len(option) > 0 else ""
            label = option[1] if len(option) > 1 else code
            extra = option[2] if len(option) > 2 else ""
        text = label if not extra else f"{label} · {extra}"
        selected = " selected" if selected_code == code else ""
        form_attr = f' form="{html.escape(form_id, quote=True)}"' if form_id else ""
        tags.append(
            f'<option value="{html.escape(code, quote=True)}"{selected}>{html.escape(text)}</option>'
        )
    form_attr = f' form="{html.escape(form_id, quote=True)}"' if form_id else ""
    return f'<select name="{html.escape(name, quote=True)}"{form_attr}>{"".join(tags)}</select>'


def metadata_edit_suggestions(connection, selected_row, workout_purpose_rows):
    if not selected_row:
        return {}

    review_row = connection.execute(
        """
        SELECT *
        FROM activity_review_view
        WHERE activity_id = ?
        """,
        (selected_row["activity_id"],),
    ).fetchone()
    base_row = review_row or selected_row

    suggestions = {
        "shoe_code": str(selected_row["shoe_code"] or ""),
        "workout_type_code": str(selected_row["workout_type_code"] or ""),
        "primary_purpose_code": str(selected_row["primary_training_purpose_code"] or ""),
        "secondary_purpose_code": "",
        "notes": {},
    }

    review = activity_review_payload(base_row, [])
    if not suggestions["workout_type_code"]:
        inferred_workout = infer_workout_choice_code(workout_purpose_rows, base_row, review)
        if inferred_workout:
            suggestions["workout_type_code"] = inferred_workout
            suggestions["notes"]["workout_type_code"] = "CoachOS 先依距離和負荷預填課表。"

    selected_secondary_codes = parse_secondary_codes(selected_row["secondary_training_purpose_codes"])
    if selected_secondary_codes:
        suggestions["secondary_purpose_code"] = str(selected_secondary_codes[0] or "")

    workout_to_purposes = {}
    purpose_to_workout = {}
    for row in workout_purpose_rows:
        workout_code = str(row["workout_type_code"] or "").strip()
        primary_code = str(row["primary_training_purpose_code"] or "").strip()
        secondary_code = str(row["secondary_training_purpose_code"] or "").strip()
        if workout_code and workout_code not in workout_to_purposes:
            workout_to_purposes[workout_code] = {
                "primary": primary_code,
                "secondary": secondary_code,
            }
        for purpose_code in (primary_code, secondary_code):
            if purpose_code and purpose_code not in purpose_to_workout:
                purpose_to_workout[purpose_code] = workout_code

    if not suggestions["workout_type_code"]:
        inferred_workout = purpose_to_workout.get(suggestions["primary_purpose_code"]) or purpose_to_workout.get(suggestions["secondary_purpose_code"])
        if inferred_workout:
            suggestions["workout_type_code"] = inferred_workout
            suggestions["notes"]["workout_type_code"] = "CoachOS 先依訓練目的預填課表。"

    mapped = workout_to_purposes.get(suggestions["workout_type_code"] or "")
    if mapped:
        if not suggestions["primary_purpose_code"] and mapped.get("primary"):
            suggestions["primary_purpose_code"] = mapped["primary"]
            suggestions["notes"]["primary_purpose_code"] = "CoachOS 先依課表預填主要目的。"
        if not suggestions["secondary_purpose_code"] and mapped.get("secondary"):
            suggestions["secondary_purpose_code"] = mapped["secondary"]
            suggestions["notes"]["secondary_purpose_code"] = "CoachOS 先依課表預填次要目的。"

    workout_type_id = dimension_id_by_code(connection, "workout_type", "workout_type_code", suggestions["workout_type_code"])
    primary_purpose_id = dimension_id_by_code(connection, "training_purpose", "training_purpose_code", suggestions["primary_purpose_code"])
    if not suggestions["shoe_code"] and workout_type_id and primary_purpose_id:
        memory_row = coach_knowledge_shoe_memory_row(connection, workout_type_id, primary_purpose_id)
        if memory_row:
            suggestions["shoe_code"] = str(memory_row["shoe_code"] or "")
            suggestions["notes"]["shoe_code"] = "CoachOS 先依相似組合預填鞋款。"

    return suggestions


def workout_purpose_mapping_panel(workout_purpose_rows, purpose_rows):
    if not workout_purpose_rows:
        return """
          <section class="panel-section">
            <h2>課表 / 目的對照</h2>
            <p class="note">目前還沒有可設定的課表對照。</p>
          </section>
        """

    purpose_options = [
        {
            "code": row["training_purpose_code"],
            "label": training_purpose_display_name(row),
            "extra": purpose_category_display_label(row["purpose_category"]),
        }
        for row in purpose_rows
    ]
    rows_html = []
    for row in workout_purpose_rows:
        primary_selected = row["primary_training_purpose_code"] or ""
        secondary_selected = row["secondary_training_purpose_code"] or ""
        rows_html.append(
            f"""
            <tr>
              <td class="workout-purpose-label">
                <strong>{html.escape(workout_type_display_name(row))}</strong>
                <span>{html.escape(workout_intensity_display_label(row["intensity_category"]))}</span>
              </td>
              <td>
                <form class="workout-purpose-map-form remember-scroll-form" method="post" action="/metadata/workout-purpose-map">
                  <input type="hidden" name="workout_type_code" value="{html.escape(str(row["workout_type_code"]), quote=True)}">
                  <input type="hidden" name="scroll_y" value="">
                  <label class="stacked-field">
                    <span>主要目的</span>
                    {metadata_select("primary_purpose_code", purpose_options, primary_selected, allow_blank=True)}
                  </label>
                  <label class="stacked-field">
                    <span>次要目的</span>
                    {metadata_select("secondary_purpose_code", purpose_options, secondary_selected, allow_blank=True)}
                  </label>
                  <div class="form-actions compact">
                    <button type="submit">儲存對照</button>
                  </div>
                </form>
              </td>
            </tr>
            """
        )

    return f"""
      <section class="panel-section">
        <h2>課表 / 目的對照</h2>
        <p class="note">每種課表都可以先設定一個主要目的和一個次要目的。這裡的對照會用在活動判讀與預設推論上。</p>
        <div class="table-wrap workout-purpose-map-table">
          <table>
            <thead>
              <tr>
                <th>課表</th>
                <th>主要 / 次要目的</th>
              </tr>
            </thead>
            <tbody>{"".join(rows_html)}</tbody>
          </table>
        </div>
      </section>
    """


def metadata_dimension_overview_panel(workout_rows, purpose_rows):
    workout_rows_html = []
    for row in workout_rows:
        form_id = f"workout-type-form-{html.escape(str(row['workout_type_code']), quote=True)}"
        workout_rows_html.append(
            f"""
            <tr>
              <td><strong>{html.escape(str(row["workout_type_code"]))}</strong></td>
              <td><input type="text" name="name_en" form="{form_id}" value="{html.escape(str(row["name_en"] or ""))}" placeholder="Workout Type"></td>
              <td><input type="text" name="name_zh" form="{form_id}" value="{html.escape(str(row["name_zh"] or ""))}" placeholder="課表名稱"></td>
              <td>{metadata_select("intensity_category", WORKOUT_INTENSITY_OPTIONS, row["intensity_category"] or "", allow_blank=False, form_id=form_id)}</td>
              <td>
                <form id="{form_id}" method="post" action="/metadata/workout-type" class="remember-scroll-form">
                  <input type="hidden" name="scroll_y" value="">
                  <input type="hidden" name="workout_type_code" value="{html.escape(str(row["workout_type_code"]), quote=True)}">
                  <button type="submit">儲存</button>
                  <button type="submit" formaction="/metadata/delete-workout-type" formmethod="post">刪除</button>
                </form>
              </td>
            </tr>
            """
        )

    purpose_rows_html = []
    for row in purpose_rows:
        form_id = f"training-purpose-form-{html.escape(str(row['training_purpose_code']), quote=True)}"
        purpose_rows_html.append(
            f"""
            <tr>
              <td><strong>{html.escape(str(row["training_purpose_code"]))}</strong></td>
              <td><input type="text" name="name_en" form="{form_id}" value="{html.escape(str(row["name_en"] or ""))}" placeholder="Training Purpose"></td>
              <td><input type="text" name="name_zh" form="{form_id}" value="{html.escape(str(row["name_zh"] or ""))}" placeholder="訓練目的"></td>
              <td>{metadata_select("purpose_category", PURPOSE_CATEGORY_OPTIONS, row["purpose_category"] or "", allow_blank=False, form_id=form_id)}</td>
              <td>
                <form id="{form_id}" method="post" action="/metadata/training-purpose" class="remember-scroll-form">
                  <input type="hidden" name="scroll_y" value="">
                  <input type="hidden" name="training_purpose_code" value="{html.escape(str(row["training_purpose_code"]), quote=True)}">
                  <button type="submit">儲存</button>
                  <button type="submit" formaction="/metadata/delete-training-purpose" formmethod="post">刪除</button>
                </form>
              </td>
            </tr>
            """
        )

    return f"""
      <section class="panel-section">
        <h2>課表庫</h2>
        <p class="note">這裡只維護課表本身。可以新增、修改中文 / 英文名稱與強度，不會碰到目的對照。</p>
        <form method="post" action="/metadata/workout-type" class="metadata-form dimension-create-form remember-scroll-form">
          <input type="hidden" name="scroll_y" value="">
          <label>
            <span>新課表代碼</span>
            <input type="text" name="workout_type_code" placeholder="留白會自動產生">
          </label>
          <label>
            <span>英文名稱</span>
            <input type="text" name="name_en" placeholder="Tempo Run">
          </label>
          <label>
            <span>中文名稱</span>
            <input type="text" name="name_zh" placeholder="節奏跑">
          </label>
          <label>
            <span>強度</span>
            {metadata_select("intensity_category", WORKOUT_INTENSITY_OPTIONS, "Moderate")}
          </label>
          <div class="form-actions">
            <button type="submit">新增課表</button>
          </div>
        </form>
        <div class="table-wrap compact-table-wrap">
          <table class="dimension-table">
            <thead>
              <tr>
                <th>代碼</th>
                <th>英文名稱</th>
                <th>中文名稱</th>
                <th>強度</th>
                <th>動作</th>
              </tr>
            </thead>
            <tbody>{''.join(workout_rows_html)}</tbody>
          </table>
        </div>
      </section>

      <section class="panel-section">
        <h2>目的庫</h2>
        <p class="note">這裡只維護訓練目的本身。可以新增、修改中文 / 英文名稱與目的類別，不會碰到課表對照。</p>
        <form method="post" action="/metadata/training-purpose" class="metadata-form dimension-create-form remember-scroll-form">
          <input type="hidden" name="scroll_y" value="">
          <label>
            <span>新目的代碼</span>
            <input type="text" name="training_purpose_code" placeholder="留白會自動產生">
          </label>
          <label>
            <span>英文名稱</span>
            <input type="text" name="name_en" placeholder="Threshold">
          </label>
          <label>
            <span>中文名稱</span>
            <input type="text" name="name_zh" placeholder="乳酸閾值">
          </label>
          <label>
            <span>類別</span>
            {metadata_select("purpose_category", PURPOSE_CATEGORY_OPTIONS, "Maintenance")}
          </label>
          <div class="form-actions">
            <button type="submit">新增目的</button>
          </div>
        </form>
        <div class="table-wrap compact-table-wrap">
          <table class="dimension-table">
            <thead>
              <tr>
                <th>代碼</th>
                <th>英文名稱</th>
                <th>中文名稱</th>
                <th>類別</th>
                <th>動作</th>
              </tr>
            </thead>
            <tbody>{''.join(purpose_rows_html)}</tbody>
          </table>
        </div>
      </section>
    """


def metadata_page_panel(
    candidates,
    selected_row,
    selected_provenance,
    selected_suggestions,
    shoes,
    workouts,
    purposes,
    workout_purpose_rows,
    quality_row,
    scope_counts,
    scope,
    message,
    page_number,
    page_size,
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
            "label": workout_type_display_name(row),
            "extra": workout_intensity_display_label(row["intensity_category"]),
        }
        for row in workouts
    ]
    purpose_options = [
        {
            "code": row["training_purpose_code"],
            "label": training_purpose_display_name(row),
            "extra": purpose_category_display_label(row["purpose_category"]),
        }
        for row in purposes
    ]

    scope_cards = [
        metadata_scope_link("unassigned", scope, scope_counts["unassigned"] or 0, "只看未標註", "最適合優先補資料"),
        metadata_scope_link("missing_shoe", scope, scope_counts["missing_shoe"] or 0, "先補鞋款", "最快改善鞋款分析"),
        metadata_scope_link("missing_workout", scope, scope_counts["missing_workout"] or 0, "先補課表", "讓週 / 月回顧更準"),
        metadata_scope_link("missing_purpose", scope, scope_counts["missing_purpose"] or 0, "先補目的", "讓教練判讀更有語境"),
        metadata_scope_link("complete", scope, scope_counts["complete"] or 0, "已標註", "直接看可讀的活動"),
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
    total_in_scope = metadata_scope_total(scope_counts, scope)
    total_pages = max(1, (total_in_scope + page_size - 1) // page_size) if page_size > 0 else 1
    current_page = min(max(1, page_number), total_pages)
    current_start = ((current_page - 1) * page_size) + 1 if total_in_scope > 0 else 0
    current_end = min(current_page * page_size, total_in_scope) if total_in_scope > 0 else 0

    helper_text = "先從『缺鞋款』開始補，鞋款分析會最有感。"
    if scope == "missing_workout":
        helper_text = "這一批先補課表類型，週回顧與月信的語氣會立刻更準。"
    elif scope == "missing_purpose":
        helper_text = "這一批先補訓練目的，平台才知道這堂課為什麼而跑。"
    elif scope == "all":
        helper_text = "這裡適合回頭校正最近活動；如果想省力，先切回上面的缺項範圍。"
    elif scope == "complete":
        helper_text = "這一批已經可直接支援更深的週 / 月 / 旅程判讀。"

    prev_link = ""
    next_link = ""
    if current_page > 1:
        prev_link = "/?" + urlencode({"page": "metadata", "scope": scope, "batch": current_page - 1})
    if current_page < total_pages:
        next_link = "/?" + urlencode({"page": "metadata", "scope": scope, "batch": current_page + 1})

    table_rows = []
    for row in candidates:
        edit_link = "/?" + urlencode({"page": "metadata", "edit": row["activity_id"], "scope": scope, "batch": current_page}) + "#metadata-edit"
        selected_class = " selected-row" if selected_row and row["activity_id"] == selected_row["activity_id"] else ""
        table_rows.append(
            f"""
            <tr class="clickable-row{selected_class}" onclick="window.location.href='{html.escape(edit_link, quote=True)}'">
              <td><input type="checkbox" name="activity_id" value="{row['activity_id']}" onclick="event.stopPropagation();"></td>
              <td class="time-cell"><a href="{html.escape(edit_link, quote=True)}">{format_activity_time(row["activity_start_time"])}</a></td>
              <td>{html.escape(str(row["activity_name"] or row["activity_type"] or ""))}</td>
              <td>{format_number(row["distance_km"], 2)}</td>
              <td>{html.escape(str(row["shoe_display_name"] or "未標註"))}</td>
              <td>{html.escape(str(row["workout_type_name_zh"] or row["workout_type_name_en"] or "未標註"))}</td>
              <td>{html.escape(str(row["primary_training_purpose_name_zh"] or row["primary_training_purpose_name_en"] or "未標註"))}</td>
              <td>{html.escape(metadata_status_label(row))}</td>
            </tr>
            """
        )

    selected_html = ""
    if selected_row:
        selected_secondary_codes = parse_secondary_codes(selected_row["secondary_training_purpose_codes"])
        secondary_selected = selected_secondary_codes[0] if selected_secondary_codes else ""
        suggested_shoe_code = str((selected_suggestions or {}).get("shoe_code") or "")
        suggested_workout_code = str((selected_suggestions or {}).get("workout_type_code") or "")
        suggested_primary_code = str((selected_suggestions or {}).get("primary_purpose_code") or "")
        suggested_secondary_code = str((selected_suggestions or {}).get("secondary_purpose_code") or "")
        suggested_shoe_label = label_for_choice_code(shoes, "shoe", suggested_shoe_code, "未標註")
        suggested_workout_label = label_for_choice_code(workouts, "workout", suggested_workout_code, "未標註")
        suggested_primary_label = label_for_choice_code(purposes, "purpose", suggested_primary_code, "未標註")
        shoe_selected = str(selected_row["shoe_code"] or suggested_shoe_code or "")
        workout_selected = str(selected_row["workout_type_code"] or suggested_workout_code or "")
        primary_selected = str(selected_row["primary_training_purpose_code"] or suggested_primary_code or "")
        secondary_selected = str(secondary_selected or suggested_secondary_code or "")
        shoe_source = provenance_source_label((selected_provenance or {}).get("shoe", {}).get("source"))
        workout_source = provenance_source_label((selected_provenance or {}).get("workout_type", {}).get("source"))
        primary_source = provenance_source_label((selected_provenance or {}).get("primary_purpose", {}).get("source"))
        suggestion_notes = (selected_suggestions or {}).get("notes", {})
        suggestion_banner = ""
        if not selected_row["shoe_code"] or not selected_row["workout_type_code"] or not selected_row["primary_training_purpose_code"]:
            suggestion_banner = "CoachOS 已先幫你預填可能的值，確認後再儲存就好。"
        workout_purpose_defaults = {
            str(row["workout_type_code"] or ""): {
                "primary": str(row["primary_training_purpose_code"] or ""),
                "secondary": str(row["secondary_training_purpose_code"] or ""),
            }
            for row in workout_purpose_rows
            if str(row["workout_type_code"] or "")
        }
        workout_purpose_defaults_json = json.dumps(workout_purpose_defaults, ensure_ascii=False)
        selected_html = f"""
          <section class="panel-section" id="metadata-edit">
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
                {f'<div class="coach-summary review-summary"><span>預填建議</span><p>{html.escape(suggestion_banner)}</p></div>' if suggestion_banner else ""}
                <div class="detail-chips">
                  {detail_chip("開始時間", str(selected_row["activity_start_time"]).replace("T", " ")[:16])}
                  {detail_chip("距離", f"{format_number(selected_row['distance_km'], 2)} km")}
                  {detail_chip("負荷", "" if selected_row["training_load"] is None else selected_row["training_load"])}
                </div>
                <form id="metadata-edit-form" method="post" action="/metadata/save" class="metadata-form remember-scroll-form">
                  <input type="hidden" name="activity_id" value="{selected_row["activity_id"]}">
                  <input type="hidden" name="scope" value="{html.escape(scope, quote=True)}">
                  <input type="hidden" name="batch" value="{current_page}">
                  <input type="hidden" name="scroll_y" value="">
                  <label>
                    <span>鞋款</span>
                    {metadata_select("shoe_code", shoe_options, shoe_selected, allow_blank=True)}
                  </label>
                  <label>
                    <span>課表類型</span>
                    {metadata_select("workout_type_code", workout_options, workout_selected, allow_blank=True, form_id="metadata-edit-form")}
                  </label>
                  <label>
                    <span>主要訓練目的</span>
                    {metadata_select("primary_purpose_code", purpose_options, primary_selected, allow_blank=True, form_id="metadata-edit-form")}
                  </label>
                  <label>
                    <span>次要訓練目的</span>
                    {metadata_select("secondary_purpose_code", purpose_options, secondary_selected, allow_blank=True, form_id="metadata-edit-form")}
                  </label>
                  <div class="form-actions">
                    <button type="submit">儲存標註</button>
                  </div>
                </form>
                <script>
                  (() => {{
                    const form = document.getElementById("metadata-edit-form");
                    if (!form) return;
                    const workoutSelect = form.querySelector('select[name="workout_type_code"]');
                    const primarySelect = form.querySelector('select[name="primary_purpose_code"]');
                    const secondarySelect = form.querySelector('select[name="secondary_purpose_code"]');
                    const purposeDefaults = {workout_purpose_defaults_json};
                    if (!workoutSelect || !primarySelect || !secondarySelect) return;

                    workoutSelect.addEventListener("change", () => {{
                      const defaults = purposeDefaults[workoutSelect.value] || {{"primary": "", "secondary": ""}};
                      primarySelect.value = defaults.primary || "";
                      secondarySelect.value = defaults.secondary || "";
                    }});
                  }})();
                </script>
              </div>
              <div class="weekly-review-side">
                <div class="review-card">
                  <span>目前鞋款</span>
                  <strong>{html.escape(str(selected_row["shoe_display_name"] or suggested_shoe_label or "未標註"))}</strong>
                  <p>來源：{html.escape(shoe_source)}</p>
                  {"<p class=\"note\">這筆鞋款看起來像較早前補上的，建議回頭確認。</p>" if shoe_source == "CoachOS 先前補的" else ""}
                  {"<p class=\"note\">" + html.escape(suggestion_notes.get("shoe_code", "")) + "</p>" if suggestion_notes.get("shoe_code") else ""}
                  <p>歷史活動可以標到已退役鞋款</p>
                </div>
                <div class="review-card">
                  <span>目前課表</span>
                  <strong>{html.escape(str(selected_row["workout_type_name_zh"] or selected_row["workout_type_name_en"] or suggested_workout_label or "未標註"))}</strong>
                  <p>來源：{html.escape(workout_source)}</p>
                  {"<p class=\"note\">" + html.escape(suggestion_notes.get("workout_type_code", "")) + "</p>" if suggestion_notes.get("workout_type_code") else ""}
                  <p>描述這堂課怎麼跑</p>
                </div>
                <div class="review-card">
                  <span>目前目的</span>
                  <strong>{html.escape(str(selected_row["primary_training_purpose_name_zh"] or selected_row["primary_training_purpose_name_en"] or suggested_primary_label or "未標註"))}</strong>
                  <p>來源：{html.escape(primary_source)}</p>
                  {"<p class=\"note\">" + html.escape(suggestion_notes.get("primary_purpose_code", "")) + "</p>" if suggestion_notes.get("primary_purpose_code") else ""}
                  <p>{html.escape(str(selected_row["secondary_training_purpose_names_zh"] or selected_row["secondary_training_purpose_names_en"] or "目前沒有次要目的"))}</p>
                </div>
              </div>
            </div>
          </section>
        """

    pagination_html = f"""
        <div class="table-pager">
          <div class="table-pager-meta">
            <strong>目前顯示 {current_start}-{current_end}</strong>
            <span>共 {total_in_scope} 筆 · 第 {current_page}/{total_pages} 批</span>
          </div>
          <div class="table-pager-actions">
            {"<a class=\"pager-link\" href=\"" + html.escape(prev_link, quote=True) + "\">上一批</a>" if prev_link else '<span class="pager-link disabled">上一批</span>'}
            {"<a class=\"pager-link\" href=\"" + html.escape(next_link, quote=True) + "\">下一批</a>" if next_link else '<span class="pager-link disabled">下一批</span>'}
          </div>
        </div>
    """

    return f"""
      {message_html}
      <section class="panel-section">
        <h2>設定工作台</h2>
        <div class="weekly-review-grid">
          <div class="weekly-review-main">
            <div class="review-header">
              <div>
                <span class="eyebrow">設定補齊工作台</span>
                <strong>集中調整鞋款、課表、目的與對照</strong>
              </div>
              <span class="status-badge balanced">目前顯示 {len(candidates)} / {total_in_scope} 筆</span>
            </div>
            <div class="metric-grid training-kpi-grid">
              {metadata_metric_card("總活動數", total, "所有已匯入活動")}
              {metadata_metric_card("完整標註", f"{fully_tagged}/{total}", f"{coverage}% 已可進入判讀")}
              {metadata_metric_card("未標註", unassigned, "仍缺課表或目的語境")}
              {metadata_metric_card("目前範圍", current_scope_name, "可先依缺項縮小範圍")}
            </div>
            <div class="coach-summary review-summary">
              <span>設定原則</span>
              <p>設定頁只調你真的知道的字典與對照。看不到答案的活動，就先保留原狀，讓平台誠實反映目前的 Source of Truth。</p>
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
              <strong>可調整</strong>
              <p>只要資料匯入工具下拉選單有的鞋，都能用來調整歷史資料</p>
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

      <section class="panel-section" id="metadata-batch">
        <h2>批次補標</h2>
        <p class="note">先選幾筆活動，再把相同標註一次套用。若只想更新其中一項，就把其他欄位留在保留原值。</p>
        <form method="post" action="/metadata/batch" class="remember-scroll-form">
          <input type="hidden" name="scope" value="{html.escape(scope, quote=True)}">
          <input type="hidden" name="batch" value="{current_page}">
          <input type="hidden" name="scroll_y" value="">
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
        {pagination_html}
      </section>
    """


def settings_page_panel(dropdown_options, workout_rows, purpose_rows, workout_purpose_rows, feedback_difficulty_rows, feedback_feel_rows, message=""):
    message_html = f'<section class="status">{html.escape(message)}</section>' if message else ""
    return f"""
      {message_html}
      <section class="panel-section">
        <h2>設定中心</h2>
        <div class="weekly-review-grid">
          <div class="weekly-review-main">
            <div class="review-header">
              <div>
                <span class="eyebrow">設定字典</span>
                <strong>課表、目的與對照都放在這裡</strong>
              </div>
              <span class="status-badge balanced">字典管理</span>
            </div>
            <div class="coach-summary review-summary">
              <span>設定原則</span>
              <p>這一頁只管理字典與對照，不碰單筆活動的標註流程。鞋款請到鞋款頁整理；課表與目的在下方字典區；感受難度與感覺如何在這一區獨立維護。</p>
            </div>
          </div>
          <div class="weekly-review-side">
            <div class="review-card">
              <span>課表</span>
              <strong>獨立維護</strong>
              <p>可以先改名字、強度與分類，不影響活動標註頁。</p>
            </div>
            <div class="review-card">
              <span>目的</span>
              <strong>獨立維護</strong>
              <p>課表 / 目的對照另外設定，避免一對一綁死。</p>
            </div>
            <div class="review-card">
              <span>鞋款</span>
              <strong>回到鞋款頁</strong>
              <p>鞋款維護會跟鞋款頁的狀態一起走，不在這裡重複管理。</p>
            </div>
          </div>
        </div>
      </section>

      {feedback_dictionary_tables_panel(feedback_difficulty_rows, feedback_feel_rows)}

      {metadata_dimension_overview_panel(workout_rows, purpose_rows)}

      {workout_purpose_mapping_panel(workout_purpose_rows, purpose_rows)}
    """


def feedback_dictionary_tables_panel(feedback_difficulty_rows, feedback_feel_rows):
    return f"""
      <section class="panel-section">
        <h2>回饋字典</h2>
        <p class="note">這裡只管理跑步回饋用的兩個字典。每一列都可以新增、修改、刪除，和課表、目的一樣。</p>
        <div class="feedback-dictionary-grid">
          {feedback_dictionary_panel("garmin_rpe", "感受難度", "例如 1 - 非常輕鬆", feedback_difficulty_rows)}
          {feedback_dictionary_panel("garmin_feel", "感覺如何", "例如 普通", feedback_feel_rows)}
        </div>
      </section>
    """


def feedback_dictionary_panel(dictionary_key, title, placeholder, rows):
    create_form_id = f"feedback-create-{html.escape(dictionary_key, quote=True)}"
    row_entries = []
    for row in rows:
        row_form_id = f"feedback-row-{dictionary_key}-{html.escape(str(row['id']), quote=True)}"
        row_entries.append(
            f"""
            <tr>
              <td>
                <input type="text" name="label" form="{row_form_id}" value="{html.escape(str(row['label'] or ''), quote=True)}" placeholder="{html.escape(placeholder, quote=True)}">
              </td>
              <td class="row-action-cell">
                <form id="{row_form_id}" method="post" action="/settings/feedback-dictionary-option" class="remember-scroll-form">
                  <input type="hidden" name="dictionary_key" value="{html.escape(dictionary_key, quote=True)}">
                  <input type="hidden" name="option_id" value="{html.escape(str(row['id']), quote=True)}">
                  <input type="hidden" name="scroll_y" value="">
                  <button type="submit" name="action" value="update">儲存</button>
                  <button type="submit" name="action" value="delete" formaction="/settings/feedback-dictionary-option" formmethod="post">刪除</button>
                </form>
              </td>
            </tr>
            """
        )

    return f"""
      <section class="panel-section feedback-dictionary-panel">
        <h3>{html.escape(title)}</h3>
        <form id="{create_form_id}" method="post" action="/settings/feedback-dictionary-option" class="feedback-dictionary-create-form remember-scroll-form">
          <input type="hidden" name="dictionary_key" value="{html.escape(dictionary_key, quote=True)}">
          <input type="hidden" name="scroll_y" value="">
          <label>
            <span>新增項目</span>
            <input type="text" name="label" placeholder="{html.escape(placeholder, quote=True)}">
          </label>
          <div class="form-actions">
            <button type="submit" name="action" value="create">新增</button>
          </div>
        </form>
        <div class="table-wrap dimension-table feedback-dictionary-table">
          <table>
            <thead>
              <tr>
                <th>項目</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>{"".join(row_entries) if row_entries else '<tr><td colspan=\"2\">目前沒有項目。</td></tr>'}</tbody>
          </table>
        </div>
      </section>
    """


def base_styles():
    return """
    :root {
      color-scheme: light;
      --ink: #16243a;
      --muted: #5f7088;
      --line: rgba(22, 36, 58, 0.10);
      --accent: #3cc9c7;
      --accent-deep: #143255;
      --accent-soft: #e8fbf7;
      --teal: #11a89f;
      --mint: #c8f4dc;
      --page: #f5f8fc;
      --surface: rgba(255, 255, 255, 0.82);
      --surface-strong: #ffffff;
      --shadow: 0 20px 44px rgba(18, 35, 58, 0.08);
      --shadow-strong: 0 26px 54px rgba(18, 35, 58, 0.12);
    }
    * { box-sizing: border-box; }
    html {
      scroll-behavior: smooth;
    }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans TC", sans-serif;
      background:
        radial-gradient(circle at 16% 0%, rgba(60, 201, 199, 0.12), transparent 30%),
        radial-gradient(circle at 92% 18%, rgba(60, 201, 199, 0.08), transparent 26%),
        linear-gradient(180deg, #ffffff 0%, #f9fcfc 58%, #f1fbf9 100%),
        var(--page);
      color: var(--ink);
      min-height: 100vh;
    }
    main {
      position: relative;
      z-index: 0;
      width: min(1180px, calc(100vw - 32px));
      margin: 26px auto 44px;
    }
    .hero {
      margin: 0 0 18px;
      padding: 28px 30px;
      border: 1px solid rgba(22, 36, 58, 0.08);
      border-radius: 28px;
      color: var(--ink);
      background: linear-gradient(180deg, #ffffff 0%, #f9fcfc 55%, #f1fbf9 100%);
      box-shadow: var(--shadow);
      min-height: 240px;
      position: relative;
      overflow: hidden;
    }
    .hero::after {
      content: "";
      position: absolute;
      right: -44px;
      bottom: -44px;
      width: 240px;
      height: 240px;
      border-radius: 999px;
      background: radial-gradient(circle, rgba(60, 201, 199, 0.10) 0%, rgba(60, 201, 199, 0.04) 45%, transparent 72%);
      pointer-events: none;
    }
    .hero h1 {
      margin: 0;
      font-size: 38px;
      line-height: 1.1;
      letter-spacing: 0;
    }
    .hero p {
      max-width: 720px;
      margin: 16px 0 0;
      color: var(--muted);
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
      background: rgba(255, 255, 255, 0.84);
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0;
    }
    .nav-link.active {
      background: linear-gradient(135deg, var(--accent-deep), var(--teal));
      border-color: transparent;
      color: #fff;
    }
    .nav-link-secondary {
      color: var(--accent-deep);
      background: rgba(60, 201, 199, 0.10);
    }
    .metric-card {
      min-height: 82px;
      display: grid;
      align-content: space-between;
      padding: 16px;
      border: 1px solid rgba(22, 36, 58, 0.08);
      border-radius: 18px;
      background: var(--surface-strong);
      box-shadow: var(--shadow);
    }
    .metric-grid {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
      margin: 0 0 18px;
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
      background: rgba(255, 255, 255, 0.76);
    }
    .compact-metrics .metric-card strong {
      font-size: 18px;
    }
    .hero-shell {
      display: grid;
      grid-template-columns: 1fr;
      gap: 18px;
      align-items: stretch;
      margin: 0 0 18px;
    }
    .hero-card {
      display: grid;
      grid-template-columns: minmax(300px, 0.4fr) minmax(0, 0.6fr);
      gap: 12px;
      align-items: start;
      min-height: 320px;
      padding: 24px 30px;
      border-radius: 30px;
      border: 1px solid rgba(22, 36, 58, 0.08);
      background:
        linear-gradient(180deg, #ffffff 0%, #fbfdfe 56%, #f3fbfa 100%),
        var(--surface);
      backdrop-filter: blur(16px);
      box-shadow: var(--shadow);
      overflow: hidden;
      position: relative;
    }
    .hero-card::before {
      content: "";
      position: absolute;
      inset: auto -10% -34% auto;
      width: 360px;
      height: 360px;
      border-radius: 999px;
      background: radial-gradient(circle, rgba(60, 201, 199, 0.08) 0, rgba(60, 201, 199, 0.03) 46%, transparent 74%);
      pointer-events: none;
    }
    .hero-card::after {
      content: "";
      position: absolute;
      inset: 18px;
      border-radius: 22px;
      border: 1px solid rgba(20, 50, 85, 0.05);
      pointer-events: none;
    }
    .hero-card-copy,
    .hero-card-mark {
      position: relative;
      z-index: 1;
    }
    .hero-card-copy {
      display: grid;
      align-content: start;
      justify-items: start;
      gap: 22px;
      color: var(--ink);
      padding-top: 2px;
    }
    .hero-brand-image {
      width: min(214px, 92%);
      height: auto;
      display: block;
      margin-bottom: 4px;
    }
    .hero-copy-stack {
      display: grid;
      gap: 16px;
      align-content: start;
      justify-items: start;
      max-width: 420px;
    }
    .hero-page-chip {
      display: inline-flex;
      align-items: center;
      min-height: 38px;
      padding: 0 15px;
      border-radius: 999px;
      background: rgba(60, 201, 199, 0.14);
      color: var(--teal);
      font-size: 12.5px;
      font-weight: 900;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .hero-page-title {
      margin: 0;
      color: var(--ink);
      font-size: clamp(40px, 3.8vw, 60px);
      line-height: 1.06;
      letter-spacing: -0.035em;
      font-weight: 900;
    }
    .hero-page-hint {
      margin: 0;
      color: var(--muted);
      font-size: 16.5px;
      line-height: 1.6;
      font-weight: 700;
      max-width: 36ch;
      margin-top: 2px;
    }
    .hero-card-mark {
      position: relative;
      display: grid;
      align-content: center;
      justify-items: end;
      text-align: right;
      min-height: 260px;
    }
    .hero-banner-art {
      width: min(700px, 100%);
      height: auto;
      max-height: 280px;
      object-fit: contain;
      filter: none;
      opacity: 1;
      pointer-events: none;
      user-select: none;
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
    .ai-reply-parse-state {
      margin: 4px 0 0;
      padding: 10px 12px;
      border: 1px solid rgba(22, 36, 58, 0.08);
      border-radius: 18px;
      background: rgba(232, 251, 247, 0.8);
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      line-height: 1.5;
    }
    .ai-reply-parsed-preview {
      display: grid;
      gap: 8px;
      margin-top: 10px;
      padding: 12px;
      border: 1px solid rgba(22, 36, 58, 0.08);
      border-radius: 18px;
      background: rgba(248, 251, 253, 0.92);
    }
    .ai-reply-parsed-preview span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .ai-reply-parsed-preview textarea {
      min-height: 180px;
      width: 100%;
      border: 1px solid rgba(22, 36, 58, 0.08);
      border-radius: 18px;
      padding: 12px;
      background: #fff;
      color: var(--ink);
      font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      resize: vertical;
    }
    .table-wrap {
      overflow-x: auto;
      border: 1px solid rgba(22, 36, 58, 0.08);
      border-radius: 18px;
      background: var(--surface-strong);
      box-shadow: var(--shadow);
    }
    .table-wrap tr:target {
      background: #fff8ef;
      outline: 2px solid #f3c7ae;
      outline-offset: -2px;
    }
    .compact-table-wrap {
      box-shadow: none;
      border-radius: 14px;
    }
    .compact-table-wrap table {
      min-width: 0;
    }
    .compact-table-wrap th,
    .compact-table-wrap td {
      padding: 7px 8px;
      font-size: 13px;
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
      background: rgba(245, 248, 252, 0.96);
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
      border: 1px solid rgba(22, 36, 58, 0.08);
      border-radius: 18px;
      background: var(--surface-strong);
      box-shadow: var(--shadow);
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
    .raw-data-card {
      min-height: 0;
      align-content: start;
      gap: 14px;
    }
    .raw-data-key-chips {
      margin-bottom: 0;
    }
    .raw-data-details-panel {
      display: grid;
      gap: 10px;
    }
    .raw-data-details-panel[hidden] {
      display: none !important;
    }
    .raw-data-toggle {
      width: fit-content;
    }
    .raw-data-tablist {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }
    .raw-data-tab {
      min-height: 36px;
      padding: 0 14px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff;
      color: var(--ink);
      font: inherit;
      font-size: 12px;
      font-weight: 800;
      cursor: pointer;
    }
    .raw-data-tab.active {
      background: var(--ink);
      color: #fff;
      border-color: var(--ink);
    }
    .raw-data-tab-panels {
      display: grid;
      gap: 14px;
    }
    .raw-data-tab-panel[hidden] {
      display: none !important;
    }
    .raw-data-columns {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 44px;
      align-items: start;
    }
    .raw-data-column {
      display: grid;
      gap: 12px;
      align-content: start;
      min-width: 0;
    }
    .raw-data-group {
      display: grid;
      gap: 4px;
      padding: 0;
      border: 0;
      background: transparent;
    }
    .raw-data-group h3 {
      margin: 0 0 4px;
      padding: 0 0 8px;
      border-bottom: 1px solid var(--line);
      color: var(--ink);
      font-size: 15px;
      line-height: 1.25;
      font-weight: 900;
    }
    .raw-data-group-body {
      display: grid;
      gap: 0;
    }
    .raw-data-split-note {
      margin: 0;
    }
    .raw-data-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 18px;
      align-items: baseline;
      min-height: 38px;
      padding: 8px 0;
      border-bottom: 1px solid rgba(22, 36, 58, 0.08);
    }
    .raw-data-row:last-child {
      border-bottom: 0;
    }
    .raw-data-row span {
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
      line-height: 1.3;
      min-width: 0;
    }
    .raw-data-row strong {
      color: var(--ink);
      font-size: 9px;
      line-height: 1.2;
      font-weight: 900;
      white-space: nowrap;
      text-align: right;
      padding-left: 8px;
    }
    .raw-data-row strong.raw-data-larger {
      font-size: 10px;
    }
    .activity-compact-card {
      min-height: 0;
      align-content: start;
      gap: 10px;
    }
    .activity-compact-card strong {
      font-size: 20px;
      line-height: 1.25;
    }
    .wsi-product-card {
      gap: 16px;
    }
    .wsi-card-head {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: start;
    }
    .wsi-card-head .note {
      margin-top: 8px;
    }
    .wsi-hero {
      display: grid;
      gap: 8px;
      padding: 18px;
      border-radius: 20px;
      border: 1px solid #cfe1ed;
      background: linear-gradient(135deg, #eef8f6 0%, #f7fbfd 100%);
    }
    .wsi-hero span,
    .wsi-outcome-card span,
    .wsi-raw-reasoning summary {
      color: var(--muted);
      font-size: 12px;
      font-weight: 900;
      letter-spacing: 0.02em;
      text-transform: uppercase;
    }
    .wsi-hero strong {
      color: var(--ink);
      font-size: clamp(34px, 4.4vw, 58px);
      letter-spacing: -0.04em;
      line-height: 0.95;
    }
    .wsi-hero p {
      margin: 0;
      color: var(--ink);
      font-size: 18px;
      font-weight: 850;
      line-height: 1.5;
    }
    .wsi-outcome-card {
      display: grid;
      gap: 8px;
      padding: 18px;
      border-radius: 20px;
      border: 1px solid var(--line);
      background: #fff;
      box-shadow: 0 14px 36px rgba(22, 36, 58, 0.08);
    }
    .wsi-outcome-card.ready {
      border-color: #bce5db;
      background: linear-gradient(135deg, #e7f8f2 0%, #f7fcf9 100%);
    }
    .wsi-outcome-card.maintained {
      border-color: #cfe1ed;
      background: linear-gradient(135deg, #eef6fb 0%, #ffffff 100%);
    }
    .wsi-outcome-card.overloaded {
      border-color: #f3c7ae;
      background: linear-gradient(135deg, #fff1e8 0%, #ffffff 100%);
    }
    .wsi-outcome-card strong {
      color: var(--ink);
      font-size: clamp(28px, 3.2vw, 44px);
      letter-spacing: -0.035em;
      line-height: 1;
    }
    .wsi-outcome-card p {
      margin: 0;
      color: var(--muted);
      font-size: 16px;
      font-weight: 800;
      line-height: 1.55;
    }
    .wsi-status-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .wsi-evidence-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      padding-top: 4px;
    }
    .wsi-evidence-row span {
      display: inline-flex;
      min-height: 34px;
      align-items: center;
      padding: 0 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #f8fbfd;
      color: var(--muted);
      font-size: 13px;
      font-weight: 850;
    }
    .wsi-raw-reasoning {
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: #fbfdfe;
    }
    .wsi-raw-reasoning summary {
      cursor: pointer;
    }
    .wsi-raw-reasoning p {
      margin: 10px 0 0;
      color: var(--muted);
      font-weight: 750;
      line-height: 1.6;
    }
    .wsi-mission-list {
      display: grid;
      gap: 8px;
      margin: 4px 0 0;
      padding: 0;
      list-style: none;
    }
    .wsi-mission-list li {
      margin: 0;
      padding: 0;
    }
    .wsi-mission-list a,
    .wsi-mission-more {
      display: grid;
      gap: 2px;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: #f8fbfd;
      color: inherit;
    }
    .wsi-mission-list a:hover {
      border-color: #b6d2e2;
      background: #eef6fb;
    }
    .wsi-mission-list span {
      color: var(--muted);
      font-size: 11px;
      font-weight: 900;
      letter-spacing: 0.02em;
      text-transform: uppercase;
    }
    .wsi-mission-list strong {
      color: var(--ink);
      font-size: 15px;
      line-height: 1.25;
    }
    .wsi-mission-more {
      color: var(--muted);
      font-size: 13px;
      font-weight: 850;
    }
    .wsi-month-hero {
      display: grid;
      gap: 10px;
      margin: 14px 0;
      padding: 22px;
      border: 1px solid #cfe1ed;
      border-radius: 24px;
      background: linear-gradient(135deg, #eef6fb 0%, #f8fcfb 100%);
      box-shadow: 0 16px 36px rgba(22, 36, 58, 0.07);
    }
    .wsi-month-hero span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 900;
      letter-spacing: 0.02em;
      text-transform: uppercase;
    }
    .wsi-month-hero strong {
      color: var(--ink);
      font-size: clamp(30px, 3.6vw, 50px);
      letter-spacing: -0.04em;
      line-height: 0.98;
    }
    .wsi-month-hero p {
      max-width: 900px;
      margin: 0;
      color: var(--ink);
      font-size: 18px;
      font-weight: 850;
      line-height: 1.55;
    }
    .wsi-month-supporting {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 4px;
    }
    .wsi-month-supporting span {
      display: inline-flex;
      align-items: center;
      min-height: 34px;
      padding: 0 12px;
      border-radius: 999px;
      border: 1px solid #cfe1ed;
      background: #fff;
      color: var(--muted);
      font-size: 13px;
      font-weight: 850;
      letter-spacing: 0;
      text-transform: none;
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
      align-items: start;
    }
    .activity-summary-grid {
      display: flex;
      gap: 12px;
      align-items: flex-start;
    }
    .activity-summary-grid .weekly-review-main {
      flex: 1 1 0;
    }
    .activity-summary-grid .weekly-review-side {
      flex: 0 0 min(38vw, 360px);
    }
    .activity-summary-grid .coach-summary {
      min-height: 0;
    }
    .summary-chips {
      margin-top: 4px;
    }
    .weekly-review-main,
    .weekly-review-side {
      display: grid;
      gap: 12px;
      align-content: start;
      align-items: start;
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
    .knowledge-conversation-card,
    .knowledge-learned-card {
      gap: 12px;
      align-content: start;
    }
    .knowledge-conversation-card strong,
    .knowledge-learned-card strong {
      font-size: 24px;
      line-height: 1.15;
    }
    .knowledge-complete-badge {
      display: inline-flex;
      align-items: center;
      width: fit-content;
      padding: 7px 12px;
      border-radius: 999px;
      background: #e9f7ef;
      color: #176b45;
      font-size: 12px;
      font-weight: 900;
      letter-spacing: 0.02em;
      text-transform: uppercase;
    }
    .knowledge-complete-next {
      display: grid;
      gap: 4px;
      padding: 12px 14px;
      border-radius: 18px;
      background: #f7fafc;
      border: 1px solid var(--line);
    }
    .knowledge-complete-next span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.02em;
      text-transform: uppercase;
    }
    .knowledge-complete-next strong {
      font-size: 18px;
      line-height: 1.2;
    }
    .knowledge-complete-next p {
      margin: 0;
      color: var(--muted);
      font-size: 14px;
      font-weight: 700;
      line-height: 1.5;
    }
    .knowledge-current {
      color: var(--ink);
      font-size: 16px;
      font-weight: 800;
      line-height: 1.55;
    }
    .knowledge-because {
      display: grid;
      gap: 6px;
      padding: 12px 0 0;
      border-top: 1px solid var(--line);
    }
    .knowledge-because span,
    .knowledge-chooser summary {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.02em;
      text-transform: uppercase;
    }
    .knowledge-because p {
      margin: 0;
      color: var(--ink);
      line-height: 1.65;
      font-weight: 700;
    }
    .knowledge-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }
    .knowledge-action-form,
    .knowledge-choice-form {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: end;
    }
    .knowledge-chooser {
      padding-top: 10px;
      border-top: 1px solid var(--line);
    }
    .knowledge-chooser summary {
      cursor: pointer;
      margin-bottom: 10px;
    }
    .subsection-title {
      margin: 16px 0 8px;
      font-size: 15px;
      line-height: 1.35;
      color: var(--ink);
      font-weight: 900;
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
    .table-pager {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-top: 12px;
      flex-wrap: wrap;
    }
    .table-pager-meta {
      display: grid;
      gap: 2px;
    }
    .table-pager-meta strong {
      font-size: 14px;
    }
    .table-pager-meta span {
      color: var(--muted);
      font-size: 13px;
    }
    .table-pager-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .pager-link {
      min-height: 36px;
      display: inline-flex;
      align-items: center;
      padding: 0 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff;
      color: var(--ink);
      font-size: 13px;
      font-weight: 800;
    }
    .pager-link.disabled {
      color: var(--muted);
      background: #f7fafb;
      pointer-events: none;
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
    .metadata-form input[type="text"],
    .metadata-form input[type="number"],
    .metadata-form textarea,
    .metadata-batch-bar input[type="text"],
    .dimension-create-form input[type="text"] {
      width: 100%;
      min-height: 38px;
      padding: 0 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      font: inherit;
    }
    .metadata-form textarea {
      min-height: 220px;
      padding: 12px;
      resize: vertical;
      font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }
    .feedback-dictionary-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      align-items: start;
    }
    .feedback-dictionary-grid label {
      display: grid;
      gap: 6px;
    }
    .feedback-dictionary-grid label span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .feedback-dictionary-panel {
      display: grid;
      gap: 12px;
      align-content: start;
    }
    .feedback-dictionary-panel h3 {
      margin: 0;
      font-size: 22px;
      line-height: 1.2;
    }
    .feedback-dictionary-create-form {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: end;
      margin: 0;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 8px 22px rgba(31, 41, 51, 0.05);
    }
    .feedback-dictionary-create-form label {
      display: grid;
      gap: 6px;
    }
    .feedback-dictionary-create-form label span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .feedback-dictionary-create-form input[type="text"] {
      width: 100%;
      min-height: 38px;
      padding: 0 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      font: inherit;
    }
    .feedback-dictionary-create-form .form-actions {
      align-self: end;
    }
    .feedback-dictionary-create-form .form-actions button {
      min-width: 104px;
    }
    .feedback-dictionary-table input[type="text"] {
      width: 100%;
      min-height: 38px;
      padding: 0 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      font: inherit;
    }
    .feedback-dictionary-table .row-action-cell {
      width: 172px;
      white-space: nowrap;
    }
    .feedback-dictionary-table .row-action-cell form {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .dimension-create-form {
      grid-template-columns: repeat(4, minmax(0, 1fr));
      margin: 0 0 12px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 8px 22px rgba(31, 41, 51, 0.05);
    }
    .dimension-create-form .form-actions {
      align-self: end;
    }
    .dimension-create-form .form-actions button {
      width: 100%;
    }
    .dimension-table input[type="text"],
    .dimension-table select {
      width: 100%;
      min-height: 34px;
      padding: 0 8px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      font: inherit;
    }
    .dimension-table td:last-child,
    .dimension-table th:last-child {
      white-space: nowrap;
      width: 92px;
    }
    .workout-purpose-map-table table td {
      vertical-align: top;
    }
    .workout-purpose-label {
      display: grid;
      gap: 4px;
      min-width: 160px;
    }
    .workout-purpose-label strong {
      font-size: 18px;
      line-height: 1.25;
    }
    .workout-purpose-label span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .workout-purpose-map-form {
      display: grid;
      gap: 10px;
    }
    .stacked-field {
      display: grid;
      gap: 6px;
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
    .primary-action {
      min-height: 40px;
      padding: 0 14px;
      border: 0;
      border-radius: 8px;
      background: linear-gradient(135deg, var(--accent-deep), var(--teal));
      color: #fff;
      font: inherit;
      font-weight: 800;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      text-decoration: none;
    }
    .form-actions button:hover {
      opacity: 0.94;
    }
    .secondary-action {
      min-height: 40px;
      padding: 0 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      font: inherit;
      font-weight: 800;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      text-decoration: none;
    }
    .secondary-action:hover {
      background: #f7fafb;
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
    .ai-handoff-card {
      display: grid;
      gap: 12px;
    }
    .ai-handoff-actions {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }
    .ai-handoff-block {
      display: grid;
      gap: 10px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }
    .ai-handoff-block-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
      flex-wrap: wrap;
    }
    .ai-handoff-block-head > div:first-child {
      display: grid;
      gap: 4px;
    }
    .ai-handoff-block-head strong {
      font-size: 18px;
      line-height: 1.2;
    }
    .ai-handoff-preview {
      display: grid;
      gap: 10px;
    }
    .ai-handoff-preview summary {
      cursor: pointer;
      color: var(--ink);
      font-weight: 800;
    }
    .ai-handoff-preview textarea {
      width: 100%;
      min-height: 280px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      resize: vertical;
    }
    .ai-reply-form {
      display: grid;
      gap: 12px;
    }
    .ai-reply-image-form {
      display: grid;
      gap: 12px;
      padding-top: 4px;
    }
    .ai-reply-form textarea,
    .ai-reply-raw textarea {
      width: 100%;
      min-height: 220px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      resize: vertical;
    }
    .ai-reply-form input[type="file"],
    .ai-reply-image-form input[type="file"] {
      width: 100%;
      padding: 10px 0;
      border: 0;
      background: transparent;
    }
    .ai-reply-preview {
      display: grid;
      gap: 10px;
    }
    .ai-reply-rendered {
      display: grid;
      gap: 8px;
      color: var(--ink);
    }
    .ai-reply-rendered h3,
    .ai-reply-rendered h4,
    .ai-reply-rendered h5 {
      margin: 0;
    }
    .ai-reply-rendered p,
    .ai-reply-rendered ul,
    .ai-reply-rendered li {
      margin: 0;
      font-weight: 400;
      line-height: 1.6;
    }
    .ai-reply-rendered strong {
      font-size: inherit;
      line-height: inherit;
      font-weight: 800;
    }
    .ai-reply-rendered ul {
      padding-left: 20px;
    }
    .ai-reply-raw {
      display: grid;
      gap: 10px;
    }
    .ai-reply-raw summary {
      cursor: pointer;
      color: var(--ink);
      font-weight: 800;
    }
    .ai-reply-attachments {
      display: grid;
      gap: 10px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }
    .ai-reply-attachments > strong {
      font-size: 14px;
    }
    .ai-attachment-gallery {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      justify-items: start;
    }
    .ai-attachment-card {
      margin: 0;
      display: grid;
      gap: 8px;
      justify-items: start;
    }
    .ai-attachment-card a {
      display: grid;
      place-items: center;
      width: 100%;
      justify-items: start;
    }
    .ai-attachment-card img {
      display: block;
      max-width: 100%;
      max-height: 180px;
      width: auto;
      height: auto;
      object-fit: contain;
      border-radius: 10px;
      border: 1px solid var(--line);
      background: #eef3f7;
    }
    .ai-attachment-card figcaption {
      display: grid;
      gap: 2px;
      color: var(--muted);
      font-size: 12px;
      width: 100%;
    }
    .ai-attachment-delete-form {
      margin: 0;
    }
    .ai-attachment-delete-button {
      min-height: 32px;
      padding: 0 10px;
      font-size: 12px;
    }
    code {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 13px;
      color: var(--ink);
    }
    .today-status,
    .today-suggestion,
    .today-latest,
    .coach-desk-card,
    .coach-attention-card,
    .coach-route-card,
    .intelligence-panel,
    .intelligence-metric,
    .coach-summary,
    .review-header,
    .review-card,
    .driver-row,
    .journey-step,
    .journey-turning-point,
    .journey-session-card,
    .coach-timeline-step,
    .scope-link,
    .month-selector-bar,
    .metadata-form,
    .metadata-batch-bar,
    .ai-handoff-block,
    .ai-handoff-preview textarea,
    .ai-reply-form textarea,
    .ai-reply-raw textarea,
    .table-wrap,
    .chart-panel,
    .status,
    .pager-link,
    .inline-jump-link,
    .detail-chip,
    .inline-field select,
    .inline-field input,
    .month-selector-form select,
    .metadata-form select,
    .metadata-batch-bar select {
      border-radius: 18px;
    }
    .today-status,
    .today-suggestion,
    .today-latest,
    .coach-desk-card,
    .coach-attention-card,
    .coach-route-card,
    .intelligence-panel,
    .review-header,
    .review-card,
    .driver-row,
    .journey-step,
    .journey-turning-point,
    .journey-session-card,
    .coach-timeline-step,
    .scope-link,
    .month-selector-bar,
    .metadata-form,
    .metadata-batch-bar,
    .ai-handoff-block,
    .table-wrap,
    .chart-panel,
    .status,
    .metric-card {
      border-color: rgba(22, 36, 58, 0.08);
      box-shadow: var(--shadow);
      background: var(--surface-strong);
    }
    .review-card,
    .coach-desk-card,
    .coach-attention-card,
    .coach-route-card,
    .journey-step,
    .journey-turning-point,
    .journey-session-card,
    .coach-timeline-step,
    .scope-link {
      backdrop-filter: blur(16px);
    }
    .review-card span,
    .coach-desk-card span,
    .coach-attention-card > span,
    .coach-route-card span,
    .journey-step span,
    .journey-turning-point span,
    .journey-session-card span,
    .coach-timeline-step span,
    .scope-link span,
    .metric-card span,
    .intelligence-metric span,
    .coach-summary span {
      letter-spacing: 0.06em;
    }
    .review-card strong,
    .coach-desk-card strong,
    .coach-attention-card strong,
    .coach-route-card strong,
    .journey-step strong,
    .journey-turning-point strong,
    .journey-session-card strong,
    .coach-timeline-step strong,
    .scope-link strong {
      letter-spacing: -0.01em;
    }
    .hero-card-mark p {
      margin: 0;
      color: rgba(80, 96, 120, 0.88);
      line-height: 1.55;
      font-size: 14px;
      max-width: 320px;
    }
    @media (max-width: 760px) {
      main { width: min(100vw - 20px, 1040px); margin: 18px auto; }
      .hero { padding: 20px; border-radius: 18px; min-height: 0; }
      .hero-shell,
      .hero-card {
        grid-template-columns: 1fr;
      }
    .hero-card-mark {
        justify-items: start;
        text-align: left;
        min-height: 0;
      }
      .hero-banner-art {
        width: min(480px, 92vw);
      }
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
      .raw-data-columns { grid-template-columns: 1fr; }
      .raw-data-toggle { width: 100%; }
      .raw-data-tablist { width: 100%; }
      .raw-data-tab { flex: 1 1 calc(33.333% - 8px); }
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
    .ai-handoff-block-head { grid-template-columns: 1fr; }
  }
    """


def page_hero(page):
    page_labels = {
        "home": ("今日焦點", "今天先看恢復", "先把恢復顧好，再看本週真正留下了什麼。"),
        "activity": ("活動", "這堂課留下了什麼", "把單次活動整理成可理解的回顧。"),
        "weekly": ("週回顧", "這週留下了什麼", "先看本週狀態，再看下一步。"),
        "monthly": ("月回顧", "現在走到哪裡", "用月度節奏看趨勢與轉折。"),
        "journey": ("訓練旅程", "時間怎麼串起來", "把每個月串成一段旅程。"),
        "shoes": ("鞋款", "鞋款如何分工", "讓鞋款資訊變成決策。"),
        "training": ("訓練結構", "訓練結構", "先看結構，再看缺口。"),
        "metadata": ("標註", "今天要補哪些標註", "把活動補齊，讓系統更誠實。"),
        "settings": ("設定", "今天調哪些設定", "把字典與對照集中在同一處。"),
    }
    page_slug, page_title, page_hint = page_labels.get(page, page_labels["home"])
    cta_map = {
        "home": ("查看本週反思", "/?page=weekly"),
        "activity": ("查看本週回顧", "/?page=weekly"),
        "weekly": ("查看月回顧", "/?page=monthly"),
        "monthly": ("查看旅程", "/?page=journey"),
        "journey": ("查看設定", "/?page=settings"),
        "shoes": ("查看訓練頁", "/?page=training"),
        "training": ("開始補標註", "/?page=metadata"),
        "metadata": ("開始補標註", "/?page=metadata"),
        "settings": ("開始調整設定", "/?page=settings"),
    }
    cta_label, cta_href = cta_map.get(page, cta_map["home"])
    logo_src = f"/assets/{COACHOS_LOGO}" if (ASSETS_DIR / COACHOS_LOGO).exists() else "/assets/coachos_logo_transparent.png"
    journey_src = f"/assets/{COACHOS_JOURNEY}" if (ASSETS_DIR / COACHOS_JOURNEY).exists() else "/assets/coachos_banner.png"
    return f"""
    <section class="hero-shell">
      <section class="hero-card">
        <div class="hero-card-copy">
          <img class="hero-brand-image" src="{html.escape(logo_src, quote=True)}" alt="CoachOS">
          <div class="hero-copy-stack">
            <div class="hero-page-chip">{html.escape(page_slug)}</div>
            <h2 class="hero-page-title">{html.escape(page_title)}</h2>
            <p class="hero-page-hint">{html.escape(page_hint)}</p>
            <a class="desk-link" href="{html.escape(cta_href, quote=True)}">{html.escape(cta_label)}</a>
          </div>
        </div>
        <div class="hero-card-mark">
          <img class="hero-banner-art" src="{html.escape(journey_src, quote=True)}" alt="CoachOS journey">
        </div>
      </section>
    </section>
    """


def render_dashboard(activity_id="", page="home", edit_activity_id="", scope="unassigned", message="", month="", week="", batch="1", coach_step=None, scroll_y=""):
    handoff_script = """
  <script>
    function extractAiReplyMarkdown(raw) {
      const text = (raw || "").trim();
      if (!text) return { mode: "empty", markdown: "" };
      const taggedPatterns = [
        /```running-intelligence-reply\\s*\\n([\\s\\S]*?)```/gi,
        /```markdown\\s*\\n([\\s\\S]*?)```/gi,
        /```md\\s*\\n([\\s\\S]*?)```/gi,
      ];
      for (let i = 0; i < taggedPatterns.length; i += 1) {
        const matches = [...text.matchAll(taggedPatterns[i])];
        if (matches.length) {
          return { mode: i === 0 ? "tagged" : "markdown", markdown: matches[matches.length - 1][1].trim() };
        }
      }
      const generic = [...text.matchAll(/```[a-zA-Z0-9_-]*\\s*\\n([\\s\\S]*?)```/g)];
      if (generic.length) {
        return { mode: "generic", markdown: generic[generic.length - 1][1].trim() };
      }
      return { mode: "raw", markdown: text };
    }

    function refreshAiReplyPreview(form) {
      const input = form.querySelector("[data-ai-reply-input]");
      const state = form.querySelector("[data-ai-reply-state]");
      const preview = form.querySelector("[data-ai-reply-preview]");
      const previewText = form.querySelector("[data-ai-reply-preview-text]");
      if (!input || !state || !preview || !previewText) return;
      const parsed = extractAiReplyMarkdown(input.value || "");
      if (parsed.mode === "empty") {
        state.textContent = "尚未貼上 AI 回覆";
        preview.hidden = true;
        previewText.value = "";
        return;
      }
      if (parsed.mode === "tagged") {
        state.textContent = "已辨識 AI 回覆區塊。找到最後一個 running-intelligence-reply，以下內容將被保存。";
      } else if (parsed.mode === "markdown" || parsed.mode === "generic") {
        state.textContent = "已辨識 Markdown 區塊。未找到 running-intelligence-reply，將改用最後一個 markdown 區塊。";
      } else {
        state.textContent = "未找到可辨識的 Markdown 區塊。平台將保存你貼上的完整內容，請先確認下方預覽是否正確。";
      }
      preview.hidden = false;
      previewText.value = parsed.markdown;
    }

    document.addEventListener("input", function (event) {
      const input = event.target.closest("[data-ai-reply-input]");
      if (!input) return;
      const form = input.closest("form");
      if (form) refreshAiReplyPreview(form);
    });

    document.addEventListener("DOMContentLoaded", function () {
      document.querySelectorAll("form.ai-reply-form").forEach(refreshAiReplyPreview);
    });

    async function copyAiHandoff(id) {
      const el = document.getElementById(id);
      const status =
        document.getElementById(id + "-status") ||
        document.getElementById("activity-ai-handoff-status") ||
        document.getElementById("weekly-ai-handoff-status") ||
        document.getElementById("monthly-ai-handoff-status") ||
        document.getElementById("overview-ai-handoff-status");
      if (!el) return;
      const text = typeof el.value === "string" && el.value.length ? el.value : (el.textContent || "").trim();
      if (!text) {
        if (status) status.textContent = "這段 handoff 目前是空的，請重新整理後再試一次。";
        return;
      }
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(text);
        } else {
          throw new Error("clipboard-unavailable");
        }
        if (status) status.textContent = "已複製，現在可以直接貼到你習慣的 AI。";
      } catch (error) {
        el.focus();
        el.select();
        let copied = false;
        try {
          copied = document.execCommand("copy");
        } catch (_ignored) {
          copied = false;
        }
        if (status) {
          status.textContent = copied
            ? "已複製，現在可以直接貼到你習慣的 AI。"
            : "這台瀏覽器不支援直接複製，已幫你選取內容。";
        }
      }
    }

    function restoreCoachScroll() {
      const params = new URLSearchParams(window.location.search);
      const raw = params.get("scroll_y");
      if (raw === null) return;
      const value = Number.parseInt(raw, 10);
      if (Number.isNaN(value)) return;
      window.requestAnimationFrame(() => {
        window.scrollTo({ top: value, left: 0, behavior: "auto" });
      });
      window.setTimeout(() => {
        window.scrollTo({ top: value, left: 0, behavior: "auto" });
      }, 60);
    }

    function stashCoachScroll(form) {
      if (!form) return;
      const input = form.querySelector('input[name="scroll_y"]');
      if (!input) return;
      input.value = String(Math.max(0, Math.round(window.scrollY || 0)));
    }

    document.addEventListener("submit", function (event) {
      const form = event.target.closest("form.remember-scroll-form");
      if (!form) return;
      stashCoachScroll(form);
    });

    document.addEventListener("click", function (event) {
      const link = event.target.closest("a.remember-scroll-link");
      if (!link) return;
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const current = new URL(link.href, window.location.href);
      current.searchParams.set("scroll_y", String(Math.max(0, Math.round(window.scrollY || 0))));
      link.href = current.toString();
    });

    document.addEventListener("click", function (event) {
      const button = event.target.closest("button.raw-data-toggle");
      if (!button || event.defaultPrevented) return;
      const targetId = button.getAttribute("data-raw-target");
      if (!targetId) return;
      const panel = document.getElementById(targetId);
      if (!panel) return;
      const isHidden = panel.hasAttribute("hidden");
      if (isHidden) {
        panel.removeAttribute("hidden");
        button.textContent = button.getAttribute("data-open-label") || "隱藏細節";
        setRawDataTab(panel, "data");
      } else {
        panel.setAttribute("hidden", "");
        button.textContent = button.getAttribute("data-closed-label") || "顯示細節";
      }
    });

    function setRawDataTab(panel, activeTab) {
      if (!panel) return;
      const tabs = panel.querySelectorAll("button.raw-data-tab");
      const panels = panel.querySelectorAll(".raw-data-tab-panel");
      tabs.forEach(function (tab) {
        const isActive = tab.getAttribute("data-raw-tab") === activeTab;
        tab.classList.toggle("active", isActive);
        tab.setAttribute("aria-selected", isActive ? "true" : "false");
      });
      panels.forEach(function (tabPanel) {
        const isActive = tabPanel.getAttribute("data-raw-panel") === activeTab;
        if (isActive) {
          tabPanel.removeAttribute("hidden");
        } else {
          tabPanel.setAttribute("hidden", "");
        }
      });
    }

    function openRawDataPanelForTarget(target) {
      if (!target) return;
      const detailPanel = target.closest(".raw-data-details-panel");
      if (!detailPanel) return;
      if (detailPanel.hasAttribute("hidden")) {
        detailPanel.removeAttribute("hidden");
      }
      const rawCard = detailPanel.closest(".raw-data-card");
      const toggle = rawCard ? rawCard.querySelector("button.raw-data-toggle") : null;
      if (toggle) {
        toggle.textContent = toggle.getAttribute("data-open-label") || "隱藏細節";
      }
      const tabPanel = target.closest(".raw-data-tab-panel");
      if (tabPanel) {
        const activeTab = tabPanel.getAttribute("data-raw-panel");
        if (activeTab) {
          setRawDataTab(detailPanel, activeTab);
        }
      }
    }

    document.addEventListener("click", function (event) {
      const tab = event.target.closest("button.raw-data-tab");
      if (!tab || event.defaultPrevented) return;
      const panel = tab.closest(".raw-data-details-panel");
      if (!panel) return;
      const activeTab = tab.getAttribute("data-raw-tab");
      if (!activeTab) return;
      setRawDataTab(panel, activeTab);
    });

    document.addEventListener("click", function (event) {
      const link = event.target.closest("a.inline-jump-link");
      if (!link || event.defaultPrevented) return;
      const href = link.getAttribute("href") || "";
      if (!href.startsWith("#")) return;
      const target = document.getElementById(href.slice(1));
      if (!target) return;
      openRawDataPanelForTarget(target);
      window.setTimeout(function () {
        target.scrollIntoView({ block: "start", behavior: "smooth" });
      }, 20);
    });

    window.history.scrollRestoration = "manual";
    document.addEventListener("DOMContentLoaded", restoreCoachScroll);
    window.addEventListener("load", restoreCoachScroll);
  </script>
"""

    if not DB_PATH.exists():
        return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CoachOS</title>
  <style>{base_styles()}</style>
  {handoff_script}
</head>
<body>
  <main>
    {page_hero(page)}
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
    weekly_rows_with_labels = []
    week_rows = []
    selected_week = ""
    activity_shoe_rows = []
    activity_workout_rows = []
    activity_purpose_rows = []
    distribution_rows = []
    weekly_key_session_rows = []
    weekly_workout_structure_summary_rows = []
    weekly_wsi_summary = None
    month_rows = []
    monthly = None
    selected_month = ""
    monthly_review = None
    monthly_memory = None
    monthly_rows = []
    monthly_distribution_rows = []
    monthly_progress_row = None
    monthly_key_session_rows = []
    monthly_workout_structure_summary_rows = []
    monthly_related_week_rows = []
    monthly_assignment_quality_row = None
    monthly_wsi_summary = None
    journey_selected_story = None
    journey_timeline_rows = []
    journey_turning_rows = []
    training_balance_rows = []
    training_quality_row = None
    recent_training_rows = []
    overview_ai_reply = None
    activity_ai_reply = None
    weekly_ai_reply = None
    monthly_ai_reply = None
    shoe_rows = []
    shoe_status_data = []
    shoe_intelligence_rows = []
    shoe_workout_rows = []
    settings_dropdown_options = load_metadata_dropdown_options()
    metadata_shoes = []
    metadata_workouts = []
    metadata_purposes = []
    metadata_workout_purpose_rows = []
    feedback_difficulty_rows = []
    feedback_feel_rows = []
    metadata_rows = []
    metadata_selected = None
    metadata_scope_data = None
    shoes_scope_data = None
    metadata_page_number = max(1, int(batch)) if str(batch).isdigit() else 1
    metadata_page_size = 60
    coach_step = None if coach_step in ("", None) else str(coach_step)
    scroll_y = str(scroll_y or "")
    recent = []
    activity_rows = []
    latest_activity = None
    selected = None
    split_rows = []
    workout_split_rows = []
    wsi = None
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
            weekly_rows_with_labels = weekly_history_with_labels(connection, weekly_rows)
            distribution_rows = selected_week_distribution(connection, selected_week or None, limit=6)
            weekly_key_session_rows = selected_week_key_sessions(connection, selected_week or None)
            weekly_workout_structure_summary_rows = key_session_workout_structure_summary(connection, weekly_key_session_rows)
            if weekly:
                weekly_wsi_summary = wsi_period_summary(
                    connection,
                    weekly["start_date"],
                    weekly["end_date"],
                    "本週",
                )

        elif page == "activity":
            activity_rows = available_activities(connection)
            selected = selected_activity(connection, int(activity_id) if str(activity_id).isdigit() else None)
            split_rows = splits(connection, selected["activity_id"] if selected else None)
            workout_split_rows = workout_structure_splits(connection, selected["activity_id"] if selected else None)
            if selected:
                wsi = get_activity_wsi(connection, selected["activity_id"])
                if not wsi:
                    wsi = recompute_activity_wsi(connection, selected["activity_id"])
                    connection.commit()
            _dropdown_options, activity_shoe_rows, activity_workout_rows, activity_purpose_rows, _activity_workout_purpose_rows = metadata_choice_sets(connection)
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
            monthly_workout_structure_summary_rows = key_session_workout_structure_summary(connection, monthly_key_session_rows)
            journey_timeline_rows = journey_timeline(connection)
            journey_turning_rows = journey_turning_points(connection, selected_month or None, limit=6)

        elif page == "monthly":
            month_rows = available_months(connection)
            monthly = selected_month_summary(connection, month or None)
            selected_month = str(monthly["month_key"]) if monthly else (str(month_rows[0]["month_key"]) if month_rows else "")
            monthly_review = selected_month_intelligence(connection, selected_month or None)
            monthly_memory = monthly_coach_memory(connection, selected_month or None)
            monthly_rows = monthly_history(connection)
            monthly_distribution_rows = selected_month_distribution(connection, selected_month or None)
            monthly_progress_row = selected_month_progress(connection, selected_month or None)
            monthly_key_session_rows = selected_month_key_sessions(connection, selected_month or None)
            monthly_workout_structure_summary_rows = key_session_workout_structure_summary(connection, monthly_key_session_rows)
            monthly_related_week_rows = selected_month_related_weeks(connection, selected_month or None, limit=5)
            monthly_assignment_quality_row = selected_month_assignment_quality(connection, selected_month or None)
            if monthly:
                monthly_wsi_summary = wsi_period_summary(
                    connection,
                    monthly["month_start"],
                    monthly["month_end"],
                    "本月",
                )

        elif page == "shoes":
            shoe_rows = shoes_overview(connection)
            shoe_status_data = shoe_status_rows(connection)
            shoe_intelligence_rows = shoe_intelligence(connection)
            shoe_workout_rows = shoe_workout_comparison(connection, limit=12)
            shoes_scope_data = metadata_scope_counts(connection)

        elif page == "training":
            distribution_rows = training_distribution(connection, limit=6)
            training_balance_rows = training_balance(connection)
            training_quality_row = training_assignment_quality(connection)
            recent_training_rows = recent_training_intent(connection, limit=8)

        elif page == "metadata":
            _dropdown_options, metadata_shoes, metadata_workouts, metadata_purposes, metadata_workout_purpose_rows = metadata_choice_sets(connection)
            metadata_scope_data = metadata_scope_counts(connection)
            total_in_scope = metadata_scope_total(metadata_scope_data, scope)
            total_pages = max(1, (total_in_scope + metadata_page_size - 1) // metadata_page_size) if metadata_page_size > 0 else 1
            metadata_page_number = min(metadata_page_number, total_pages)
            metadata_rows = metadata_candidates(
                connection,
                scope=scope,
                limit=metadata_page_size,
                offset=(metadata_page_number - 1) * metadata_page_size,
            )
            training_quality_row = training_assignment_quality(connection)
            metadata_selected = metadata_activity(
                connection,
                int(edit_activity_id) if str(edit_activity_id).isdigit() else (metadata_rows[0]["activity_id"] if metadata_rows else 0),
            ) if (edit_activity_id or metadata_rows) else None
            metadata_selected_provenance = activity_metadata_provenance_map(
                connection,
                metadata_selected["activity_id"] if metadata_selected else None,
            ) if metadata_selected else {}
            metadata_selected_suggestions = metadata_edit_suggestions(
                connection,
                metadata_selected,
                metadata_workout_purpose_rows,
            ) if metadata_selected else {}

        elif page == "settings":
            settings_dropdown_options, metadata_shoes, metadata_workouts, metadata_purposes, metadata_workout_purpose_rows = metadata_choice_sets(connection)
            feedback_difficulty_rows = feedback_dictionary_rows(connection, "garmin_rpe")
            feedback_feel_rows = feedback_dictionary_rows(connection, "garmin_feel")
            metadata_scope_data = metadata_scope_counts(connection)

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

        weekly_knowledge_summary = coach_knowledge_summary(
            connection,
            weekly["start_date"],
            weekly["end_date"],
            "本週",
        ) if weekly else None
        monthly_knowledge_summary = coach_knowledge_summary(
            connection,
            monthly["month_start"],
            monthly["month_end"],
            "本月",
        ) if monthly else None

    weekly_review = weekly_review_payload(weekly, intelligence, weekly_knowledge_summary) if weekly and intelligence else None
    monthly_overview = monthly_overview_payload(monthly, monthly_review, monthly_progress_row, monthly_knowledge_summary) if monthly and monthly_review else None
    if selected:
        activity_ai_reply = get_ai_reply("activity", str(selected["activity_id"]))
    if weekly:
        weekly_ai_reply = get_ai_reply("weekly", f"{weekly['start_date']}:{weekly['end_date']}")
    if monthly:
        monthly_ai_reply = get_ai_reply("monthly", str(monthly["month_key"]))
    if page == "home":
        overview_ai_reply = get_ai_reply("overview", date.today().isoformat())

    html_start = f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CoachOS</title>
  <style>{base_styles()}</style>
  {handoff_script}
</head>
<body>
  <main>
    {page_hero(page)}
    {page_nav(page)}
"""
    message_html = f'<section class="status">{html.escape(message)}</section>' if message else ""

    if page == "weekly":
        return f"""{html_start}
    {weekly_selector_bar(week_rows, selected_week, "weekly")}
    {weekly_review_panel(weekly, intelligence, weekly_rows, distribution_rows, weekly_key_session_rows, weekly_workout_structure_summary_rows, selected_week, weekly_rows_with_labels, weekly_knowledge_summary, monthly_overview, overview_attention, weekly_wsi_summary, weekly_ai_reply)}
    {archive_metric_strip(summary)}
  </main>
</body>
</html>"""

    if page == "activity":
        return f"""{html_start}
    {activity_review_panel(selected, split_rows, workout_split_rows, activity_rows, selected["activity_id"] if selected else "", activity_shoe_rows, activity_workout_rows, activity_purpose_rows, coach_step, weekly_review, monthly_overview, wsi, activity_ai_reply)}
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
    {monthly_review_panel(monthly, monthly_review, monthly_progress_row, monthly_assignment_quality_row, monthly_rows, monthly_distribution_rows, monthly_key_session_rows, monthly_workout_structure_summary_rows, monthly_related_week_rows, month_rows, selected_month, monthly_knowledge_summary, monthly_memory, monthly_wsi_summary, monthly_ai_reply)}
  </main>
</body>
</html>"""

    if page == "shoes":
        return f"""{html_start}
    {shoes_page_panel(shoe_rows, shoe_intelligence_rows, shoe_workout_rows, shoe_status_data, shoes_scope_data, message)}
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
        metadata_selected_provenance,
        metadata_selected_suggestions,
        metadata_shoes,
        metadata_workouts,
        metadata_purposes,
        metadata_workout_purpose_rows,
        training_quality_row,
        metadata_scope_data,
        scope,
        message,
        metadata_page_number,
        metadata_page_size,
    )}
    {archive_metric_strip(summary)}
  </main>
</body>
</html>"""

    if page == "settings":
        return f"""{html_start}
    {settings_page_panel(settings_dropdown_options, metadata_workouts, metadata_purposes, metadata_workout_purpose_rows, feedback_difficulty_rows, feedback_feel_rows, message)}
    {archive_metric_strip(summary)}
  </main>
</body>
</html>"""

    return f"""{html_start}
    {message_html}
    {rac_entry_panel()}
    {coach_desk_panel(overview_attention, weekly_review, monthly_overview, monthly_review, journey_selected_story, latest_activity, overview_ai_reply)}
    {archive_metric_strip(summary)}
  </main>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            return

    def safe_write(self, data):
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            return

    def send_html(self, content, status=200):
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.safe_write(data)

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
        self.safe_write(data)

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/assets/"):
            self.send_asset(ASSETS_DIR / parsed.path.removeprefix("/assets/"))
            return
        if parsed.path == "/ai-replies-file":
            query = parse_qs(parsed.query)
            surface = (query.get("surface") or [""])[0]
            identifier = (query.get("identifier") or [""])[0]
            filename = (query.get("filename") or [""])[0]
            target = ai_reply_attachment_dir(surface, identifier) / filename
            try:
                resolved = target.resolve()
                root = AI_REPLIES_DIR.resolve()
                if not resolved.is_file() or not resolved.is_relative_to(root):
                    raise FileNotFoundError
                data = resolved.read_bytes()
            except (OSError, FileNotFoundError):
                self.send_html(render_dashboard(message="找不到附加圖檔"), status=404)
                return
            content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.safe_write(data)
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
        if page not in {"home", "activity", "journey", "weekly", "monthly", "shoes", "training", "metadata", "settings"}:
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
                (query.get("batch") or ["1"])[0],
                (query.get("coach_step") or [None])[0],
                (query.get("scroll_y") or [""])[0],
            )
        )

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)

        if parsed.path == "/ai-replies/save":
            form = parse_qs(body.decode("utf-8"))
            surface = first_form_value(form, "surface", "").strip()
            identifier = first_form_value(form, "identifier", "").strip()
            title = first_form_value(form, "title", "").strip() or "AI 回覆"
            page = first_form_value(form, "page", "home").strip() or "home"
            activity_id = first_form_value(form, "activity_id", "").strip()
            week = first_form_value(form, "week", "").strip()
            month = first_form_value(form, "month", "").strip()
            scroll_y = first_form_value(form, "scroll_y", "").strip()
            raw_text = first_form_value(form, "ai_reply_raw", "")

            if not surface or not identifier or not raw_text.strip():
                message = "貼回內容是空的，先把 AI 回覆貼進來再存。"
            else:
                save_ai_reply(surface, identifier, title, raw_text)
                message = "已把 AI 回覆存回這一頁"

            params = {"page": page, "message": message}
            if activity_id:
                params["activity"] = activity_id
            if week:
                params["week"] = week
            if month:
                params["month"] = month
            if scroll_y:
                params["scroll_y"] = scroll_y
            self.redirect("/?" + urlencode(params))
            return

        if parsed.path == "/ai-replies/upload-image":
            form = parse_multipart_form_data(body, self.headers.get("Content-Type", ""))
            surface = first_form_value(form, "surface", "").strip()
            identifier = first_form_value(form, "identifier", "").strip()
            title = first_form_value(form, "title", "").strip() or "AI 回覆"
            page = first_form_value(form, "page", "home").strip() or "home"
            activity_id = first_form_value(form, "activity_id", "").strip()
            week = first_form_value(form, "week", "").strip()
            month = first_form_value(form, "month", "").strip()
            scroll_y = first_form_value(form, "scroll_y", "").strip()
            uploaded = form.get("ai_reply_image")
            uploaded_file = None
            if isinstance(uploaded, list) and uploaded:
                uploaded_file = uploaded[0]

            if not surface or not identifier or uploaded_file is None or not getattr(uploaded_file, "filename", ""):
                message = "還沒選到圖檔，先挑一張圖片再上傳。"
            else:
                try:
                    save_ai_reply_attachment(surface, identifier, uploaded_file)
                    message = "圖檔已附加到這一頁"
                except ValueError as exc:
                    message = str(exc)
                except Exception:
                    message = "上傳圖檔時出了點問題，請再試一次。"

            params = {"page": page, "message": message}
            if activity_id:
                params["activity"] = activity_id
            if week:
                params["week"] = week
            if month:
                params["month"] = month
            if scroll_y:
                params["scroll_y"] = scroll_y
            self.redirect("/?" + urlencode(params))
            return

        if parsed.path == "/ai-replies/delete-image":
            form = parse_qs(body.decode("utf-8"))
            surface = first_form_value(form, "surface", "").strip()
            identifier = first_form_value(form, "identifier", "").strip()
            filename = first_form_value(form, "filename", "").strip()
            page = first_form_value(form, "page", "home").strip() or "home"
            activity_id = first_form_value(form, "activity_id", "").strip()
            week = first_form_value(form, "week", "").strip()
            month = first_form_value(form, "month", "").strip()
            scroll_y = first_form_value(form, "scroll_y", "").strip()

            if not surface or not identifier or not filename:
                message = "找不到要刪除的圖檔。"
            else:
                try:
                    delete_ai_reply_attachment(surface, identifier, filename)
                    message = "圖檔已刪除"
                except FileNotFoundError:
                    message = "找不到要刪除的圖檔。"
                except Exception:
                    message = "刪除圖檔時出了點問題，請再試一次。"

            params = {"page": page, "message": message}
            if activity_id:
                params["activity"] = activity_id
            if week:
                params["week"] = week
            if month:
                params["month"] = month
            if scroll_y:
                params["scroll_y"] = scroll_y
            self.redirect("/?" + urlencode(params))
            return

        if parsed.path == "/shoes/add":
            form = parse_qs(body.decode("utf-8"))
            scroll_y = first_form_value(form, "scroll_y", "").strip()
            category = first_form_value(form, "category", "").strip()
            try:
                with connect() as connection:
                    shoe_name = append_shoe_option(first_form_value(form, "shoe_name"), connection)
                    ensure_metadata_dimensions(connection, load_metadata_dropdown_options(connection))
                    if category:
                        shoe_row = shoe_dimension_row(shoe_name)
                        save_shoe_dimension(
                            connection,
                            dimension_id_by_code(connection, "shoe", "shoe_code", shoe_row["shoe_code"]),
                            category,
                        )
                    connection.commit()
                message = f"已新增鞋款：{shoe_name}" + (f"（{category}）" if category else "")
            except ValueError as exc:
                message = str(exc)
            except Exception:
                message = "新增鞋款時出了點問題，請再試一次。"
            params = {"page": "shoes", "message": message}
            if scroll_y:
                params["scroll_y"] = scroll_y
            location = "/?" + urlencode(params)
            self.redirect(location)
            return

        if parsed.path == "/shoes/save-status":
            form = parse_qs(body.decode("utf-8"))
            shoe_id = int(first_form_value(form, "shoe_id", "0") or "0")
            is_active = 1 if first_form_value(form, "is_active", "1") == "1" else 0
            retire_date = first_form_value(form, "retire_date", "").strip() or None
            category = first_form_value(form, "category", "").strip()
            scroll_y = first_form_value(form, "scroll_y", "").strip()

            with connect() as connection:
                save_shoe_dimension(connection, shoe_id, category)
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

            params = {"page": "shoes", "message": "鞋款設定已儲存"}
            if scroll_y:
                params["scroll_y"] = scroll_y
            location = "/?" + urlencode(params)
            self.redirect(location)
            return

        if parsed.path == "/activity/coach-knowledge":
            form = parse_qs(body.decode("utf-8"))
            activity_id = int(first_form_value(form, "activity_id", "0") or "0")
            coach_step = first_form_value(form, "coach_step", "shoe")
            action = first_form_value(form, "action", "confirm")
            choice_code = first_form_value(form, "choice_code", "").strip()
            scroll_y = first_form_value(form, "scroll_y", "").strip()

            next_stage = {
                "shoe": "workout",
                "workout": "purpose",
                "purpose": "purpose_learned",
            }.get(coach_step, "shoe")
            learned_stage = f"{coach_step}_learned" if coach_step in {"shoe", "workout", "purpose"} else "shoe_learned"

            with connect() as connection:
                current = selected_activity(connection, activity_id)
                if current and action in {"confirm", "choose"} and choice_code:
                    if coach_step == "shoe":
                        update_single_activity_metadata(
                            connection,
                            activity_id,
                            choice_code,
                            current["workout_type_code"] or "",
                            current["primary_training_purpose_code"] or "",
                            "",
                            provenance_source="coach_knowledge",
                        )
                    elif coach_step == "workout":
                        update_single_activity_metadata(
                            connection,
                            activity_id,
                            current["shoe_code"] or "",
                            choice_code,
                            current["primary_training_purpose_code"] or "",
                            "",
                            provenance_source="coach_knowledge",
                        )
                    elif coach_step == "purpose":
                        update_single_activity_metadata(
                            connection,
                            activity_id,
                            current["shoe_code"] or "",
                            current["workout_type_code"] or "",
                            choice_code,
                            "",
                            provenance_source="coach_knowledge",
                        )
                    recompute_activity_wsi(connection, activity_id)
                    connection.commit()

            if action == "skip" and coach_step in {"shoe", "workout", "purpose"}:
                redirect_step = next_stage
            else:
                redirect_step = learned_stage
            redirect_anchor = "#activity-evidence" if redirect_step == "purpose_learned" else "#activity-knowledge"

            location = "/?" + urlencode(
                {
                    "page": "activity",
                    "activity": activity_id,
                    "coach_step": redirect_step,
                    "scroll_y": scroll_y,
                }
            ) + redirect_anchor
            self.redirect(location)
            return

        if parsed.path == "/metadata/save":
            form = parse_qs(body.decode("utf-8"))
            activity_id = int(first_form_value(form, "activity_id", "0") or "0")
            scope = first_form_value(form, "scope", "unassigned")
            batch = first_form_value(form, "batch", "1")
            scroll_y = first_form_value(form, "scroll_y", "").strip()
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
                    provenance_source="manual",
                )
                recompute_activity_wsi(connection, activity_id)
                connection.commit()

            location = "/?" + urlencode(
                {
                    "page": "metadata",
                    "edit": activity_id,
                    "scope": scope,
                    "batch": batch,
                    "message": "標註已儲存",
                }
            )
            if scroll_y:
                location += "&" + urlencode({"scroll_y": scroll_y})
            self.redirect(location)
            return

        if parsed.path == "/activity/recompute-wsi":
            form = parse_qs(body.decode("utf-8"))
            activity_id = int(first_form_value(form, "activity_id", "0") or "0")
            scroll_y = first_form_value(form, "scroll_y", "").strip()
            with connect() as connection:
                recompute_activity_wsi(connection, activity_id)
                connection.commit()
            location = "/?" + urlencode(
                {
                    "page": "activity",
                    "activity": activity_id,
                    "message": "訓練序列理解已重新產生",
                }
            ) + "#activity-sequence-intelligence"
            if scroll_y:
                location += "&" + urlencode({"scroll_y": scroll_y})
            self.redirect(location)
            return

        if parsed.path == "/metadata/batch":
            form = parse_qs(body.decode("utf-8"))
            scope = first_form_value(form, "scope", "unassigned")
            batch = first_form_value(form, "batch", "1")
            scroll_y = first_form_value(form, "scroll_y", "").strip()
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
                    provenance_source="manual",
                )
                for activity_id in activity_ids:
                    recompute_activity_wsi(connection, activity_id)
                connection.commit()

            message = "尚未選取活動" if updated == 0 else f"已更新 {updated} 筆活動"
            location = "/?" + urlencode(
                {
                    "page": "metadata",
                    "scope": scope,
                    "batch": batch,
                    "message": message,
                }
            )
            if scroll_y:
                location += "&" + urlencode({"scroll_y": scroll_y})
            self.redirect(location)
            return

        if parsed.path == "/metadata/workout-purpose-map":
            form = parse_qs(body.decode("utf-8"))
            workout_type_code = first_form_value(form, "workout_type_code", "").strip()
            primary_purpose_code = first_form_value(form, "primary_purpose_code", "").strip()
            secondary_purpose_code = first_form_value(form, "secondary_purpose_code", "").strip()
            scroll_y = first_form_value(form, "scroll_y", "").strip()

            with connect() as connection:
                save_workout_purpose_mapping(
                    connection,
                    workout_type_code,
                    primary_purpose_code,
                    secondary_purpose_code,
                )
                connection.commit()

            self.redirect(
                "/?" + urlencode(
                    {
                        "page": "settings",
                        "message": "課表與目的對照已儲存",
                    }
                )
                + (("&" + urlencode({"scroll_y": scroll_y})) if scroll_y else "")
            )
            return

        if parsed.path == "/metadata/workout-type":
            form = parse_qs(body.decode("utf-8"))
            scroll_y = first_form_value(form, "scroll_y", "").strip()
            workout_type_code = first_form_value(form, "workout_type_code", "").strip()
            name_en = first_form_value(form, "name_en", "").strip()
            name_zh = first_form_value(form, "name_zh", "").strip()
            intensity_category = first_form_value(form, "intensity_category", "Moderate").strip()
            try:
                with connect() as connection:
                    save_workout_type_dimension(
                        connection,
                        workout_type_code,
                        name_en,
                        name_zh,
                        intensity_category,
                    )
                    connection.commit()
                message = "課表庫已儲存"
            except Exception as exc:
                message = str(exc)
            params = {"page": "settings", "message": message}
            if scroll_y:
                params["scroll_y"] = scroll_y
            self.redirect("/?" + urlencode(params))
            return

        if parsed.path == "/metadata/training-purpose":
            form = parse_qs(body.decode("utf-8"))
            scroll_y = first_form_value(form, "scroll_y", "").strip()
            training_purpose_code = first_form_value(form, "training_purpose_code", "").strip()
            name_en = first_form_value(form, "name_en", "").strip()
            name_zh = first_form_value(form, "name_zh", "").strip()
            purpose_category = first_form_value(form, "purpose_category", "Maintenance").strip()
            try:
                with connect() as connection:
                    save_training_purpose_dimension(
                        connection,
                        training_purpose_code,
                        name_en,
                        name_zh,
                        purpose_category,
                    )
                    connection.commit()
                message = "目的庫已儲存"
            except Exception as exc:
                message = str(exc)
            params = {"page": "settings", "message": message}
            if scroll_y:
                params["scroll_y"] = scroll_y
            self.redirect("/?" + urlencode(params))
            return

        if parsed.path == "/metadata/delete-workout-type":
            form = parse_qs(body.decode("utf-8"))
            scroll_y = first_form_value(form, "scroll_y", "").strip()
            workout_type_code = first_form_value(form, "workout_type_code", "").strip()
            try:
                with connect() as connection:
                    detached = delete_workout_type_dimension(connection, workout_type_code)
                    connection.commit()
                message = f"已刪除課表，並解除 {detached} 筆活動的對應"
            except Exception as exc:
                message = str(exc)
            params = {"page": "settings", "message": message}
            if scroll_y:
                params["scroll_y"] = scroll_y
            self.redirect("/?" + urlencode(params))
            return

        if parsed.path == "/metadata/delete-training-purpose":
            form = parse_qs(body.decode("utf-8"))
            scroll_y = first_form_value(form, "scroll_y", "").strip()
            training_purpose_code = first_form_value(form, "training_purpose_code", "").strip()
            try:
                with connect() as connection:
                    detached = delete_training_purpose_dimension(connection, training_purpose_code)
                    connection.commit()
                message = f"已刪除目的，並解除 {detached} 筆活動的對應"
            except Exception as exc:
                message = str(exc)
            params = {"page": "settings", "message": message}
            if scroll_y:
                params["scroll_y"] = scroll_y
            self.redirect("/?" + urlencode(params))
            return

        if parsed.path == "/settings/feedback-dictionary-option":
            form = parse_qs(body.decode("utf-8"))
            scroll_y = first_form_value(form, "scroll_y", "").strip()
            dictionary_key = first_form_value(form, "dictionary_key", "").strip()
            action = first_form_value(form, "action", "create").strip()
            label = first_form_value(form, "label", "").strip()
            option_id = first_form_value(form, "option_id", "").strip()

            with connect() as connection:
                if action == "delete":
                    delete_feedback_dictionary_option(connection, dictionary_key, option_id)
                    message = "項目已刪除"
                else:
                    saved_id = save_feedback_dictionary_option(
                        connection,
                        dictionary_key,
                        label,
                        option_id if action == "update" else None,
                    )
                    message = "項目已儲存"
                ensure_feedback_dictionary_options(connection, load_metadata_dropdown_options(connection))
                connection.commit()

            params = {
                "page": "settings",
                "message": message,
            }
            if scroll_y:
                params["scroll_y"] = scroll_y
            self.redirect("/?" + urlencode(params))
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
    parser = argparse.ArgumentParser(description="Run the CoachOS dashboard.")
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
    print(f"CoachOS Dashboard: {url}")
    print(f"SQLite database: {DB_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()
