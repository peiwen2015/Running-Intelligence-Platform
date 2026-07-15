-- SQLite Schema v1.0
-- Scope: Core Canonical Data Layer v1.0
-- Source: SQLite Mapping Specification v1.0

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS shoe (
    id INTEGER PRIMARY KEY,

    shoe_code TEXT NOT NULL UNIQUE,

    brand TEXT NOT NULL,
    model TEXT NOT NULL,
    nickname TEXT,
    category TEXT NOT NULL,

    size_us REAL CHECK (size_us IS NULL OR size_us > 0),
    width TEXT,
    drop_mm REAL CHECK (drop_mm IS NULL OR drop_mm >= 0),
    weight_g INTEGER CHECK (weight_g IS NULL OR weight_g > 0),

    purchase_date TEXT,
    first_run_date TEXT,
    retire_date TEXT,
    retire_target_distance_km REAL CHECK (
        retire_target_distance_km IS NULL OR retire_target_distance_km >= 0
    ),
    retire_actual_distance_km REAL CHECK (
        retire_actual_distance_km IS NULL OR retire_actual_distance_km >= 0
    ),
    is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)),

    notes TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_shoe_category
    ON shoe(category);

CREATE INDEX IF NOT EXISTS idx_shoe_is_active
    ON shoe(is_active);

CREATE TABLE IF NOT EXISTS workout_type (
    id INTEGER PRIMARY KEY,

    workout_type_code TEXT NOT NULL UNIQUE,

    name_en TEXT NOT NULL,
    name_zh TEXT NOT NULL,
    description TEXT,

    intensity_category TEXT NOT NULL,
    is_quality_session INTEGER NOT NULL CHECK (is_quality_session IN (0, 1)),
    is_long_run INTEGER NOT NULL CHECK (is_long_run IN (0, 1)),
    is_recovery_focused INTEGER NOT NULL CHECK (is_recovery_focused IN (0, 1)),

    sort_order INTEGER,
    display_color TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workout_type_intensity_category
    ON workout_type(intensity_category);

CREATE INDEX IF NOT EXISTS idx_workout_type_sort_order
    ON workout_type(sort_order);

CREATE TABLE IF NOT EXISTS training_purpose (
    id INTEGER PRIMARY KEY,

    training_purpose_code TEXT NOT NULL UNIQUE,

    name_en TEXT NOT NULL,
    name_zh TEXT NOT NULL,
    description TEXT,

    purpose_category TEXT NOT NULL,
    is_primary_physiological INTEGER NOT NULL CHECK (is_primary_physiological IN (0, 1)),
    is_recovery_related INTEGER NOT NULL CHECK (is_recovery_related IN (0, 1)),
    is_performance_related INTEGER NOT NULL CHECK (is_performance_related IN (0, 1)),

    sort_order INTEGER,
    display_color TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_training_purpose_category
    ON training_purpose(purpose_category);

CREATE INDEX IF NOT EXISTS idx_training_purpose_sort_order
    ON training_purpose(sort_order);

CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY,

    fit_sha256 TEXT NOT NULL UNIQUE,
    garmin_activity_id INTEGER UNIQUE,

    excel_schema_version TEXT NOT NULL,
    source_file_name TEXT NOT NULL,
    data_source TEXT NOT NULL,

    activity_start_time TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    activity_name TEXT,
    distance_km REAL NOT NULL CHECK (distance_km > 0),
    duration_sec INTEGER NOT NULL CHECK (duration_sec > 0),
    workout_type_id INTEGER REFERENCES workout_type(id),
    shoe_id INTEGER REFERENCES shoe(id),

    temperature_c REAL CHECK (temperature_c IS NULL OR temperature_c BETWEEN -20 AND 50),
    humidity_pct REAL CHECK (humidity_pct IS NULL OR humidity_pct BETWEEN 0 AND 100),
    wind_speed_mps REAL CHECK (wind_speed_mps IS NULL OR wind_speed_mps >= 0),
    wind_direction_deg REAL CHECK (wind_direction_deg IS NULL OR wind_direction_deg BETWEEN 0 AND 360),
    weather_description TEXT,

    max_hr INTEGER CHECK (max_hr IS NULL OR max_hr BETWEEN 30 AND 240),
    avg_hr INTEGER CHECK (avg_hr IS NULL OR avg_hr BETWEEN 30 AND 240),
    critical_power_w INTEGER CHECK (critical_power_w IS NULL OR critical_power_w > 0),
    training_effect_aerobic REAL CHECK (
        training_effect_aerobic IS NULL OR training_effect_aerobic BETWEEN 0 AND 5
    ),
    training_effect_anaerobic REAL CHECK (
        training_effect_anaerobic IS NULL OR training_effect_anaerobic BETWEEN 0 AND 5
    ),
    training_load INTEGER CHECK (training_load IS NULL OR training_load >= 0),
    recovery_time_hr REAL CHECK (recovery_time_hr IS NULL OR recovery_time_hr >= 0),
    stamina_start_pct INTEGER CHECK (stamina_start_pct IS NULL OR stamina_start_pct BETWEEN 0 AND 100),
    stamina_end_pct INTEGER CHECK (stamina_end_pct IS NULL OR stamina_end_pct BETWEEN 0 AND 100),

    avg_cadence_spm REAL CHECK (avg_cadence_spm IS NULL OR avg_cadence_spm >= 0),
    avg_stride_length_mm REAL CHECK (avg_stride_length_mm IS NULL OR avg_stride_length_mm >= 0),
    avg_gct_ms REAL CHECK (avg_gct_ms IS NULL OR avg_gct_ms >= 0),
    avg_vertical_oscillation_mm REAL CHECK (
        avg_vertical_oscillation_mm IS NULL OR avg_vertical_oscillation_mm >= 0
    ),
    avg_vertical_ratio_pct REAL CHECK (avg_vertical_ratio_pct IS NULL OR avg_vertical_ratio_pct >= 0),

    garmin_feeling TEXT,
    garmin_perceived_effort TEXT,
    nutrition TEXT,
    notes TEXT,
    start_latitude REAL,
    start_longitude REAL,
    end_latitude REAL,
    end_longitude REAL,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_activity_start_time
    ON activity(activity_start_time);

CREATE INDEX IF NOT EXISTS idx_activity_shoe_id
    ON activity(shoe_id);

CREATE INDEX IF NOT EXISTS idx_activity_workout_type_id
    ON activity(workout_type_id);

CREATE TABLE IF NOT EXISTS activity_metadata_provenance (
    activity_id INTEGER NOT NULL REFERENCES activity(id) ON DELETE CASCADE,
    field_name TEXT NOT NULL CHECK (field_name IN ('shoe', 'workout_type', 'primary_purpose', 'secondary_purpose')),
    source TEXT NOT NULL,
    source_detail TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (activity_id, field_name)
);

CREATE TABLE IF NOT EXISTS activity_training_purpose (
    id INTEGER PRIMARY KEY,

    activity_id INTEGER NOT NULL REFERENCES activity(id),
    training_purpose_id INTEGER NOT NULL REFERENCES training_purpose(id),
    purpose_role TEXT NOT NULL CHECK (purpose_role IN ('PRIMARY', 'SECONDARY')),

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (activity_id, training_purpose_id)
);

CREATE INDEX IF NOT EXISTS idx_activity_training_purpose_activity_id
    ON activity_training_purpose(activity_id);

CREATE INDEX IF NOT EXISTS idx_activity_training_purpose_training_purpose_id
    ON activity_training_purpose(training_purpose_id);

CREATE INDEX IF NOT EXISTS idx_activity_training_purpose_role
    ON activity_training_purpose(purpose_role);

CREATE TABLE IF NOT EXISTS kilometer_split (
    id INTEGER PRIMARY KEY,

    activity_id INTEGER NOT NULL REFERENCES activity(id),
    split_index INTEGER NOT NULL CHECK (split_index > 0),

    split_distance_m REAL NOT NULL CHECK (split_distance_m > 0),
    elapsed_time_sec INTEGER NOT NULL CHECK (elapsed_time_sec > 0),

    avg_hr INTEGER CHECK (avg_hr IS NULL OR avg_hr BETWEEN 30 AND 240),
    max_hr INTEGER CHECK (max_hr IS NULL OR max_hr BETWEEN 30 AND 240),
    avg_power_w INTEGER CHECK (avg_power_w IS NULL OR avg_power_w >= 0),

    avg_cadence_spm REAL CHECK (avg_cadence_spm IS NULL OR avg_cadence_spm >= 0),
    avg_stride_length_mm REAL CHECK (avg_stride_length_mm IS NULL OR avg_stride_length_mm >= 0),
    avg_gct_ms REAL CHECK (avg_gct_ms IS NULL OR avg_gct_ms >= 0),
    avg_vertical_ratio_pct REAL CHECK (avg_vertical_ratio_pct IS NULL OR avg_vertical_ratio_pct >= 0),
    avg_vertical_oscillation_mm REAL CHECK (
        avg_vertical_oscillation_mm IS NULL OR avg_vertical_oscillation_mm >= 0
    ),

    elevation_gain_m REAL CHECK (elevation_gain_m IS NULL OR elevation_gain_m >= 0),
    elevation_loss_m REAL CHECK (elevation_loss_m IS NULL OR elevation_loss_m >= 0),

    stamina_start_pct INTEGER CHECK (stamina_start_pct IS NULL OR stamina_start_pct BETWEEN 0 AND 100),
    stamina_end_pct INTEGER CHECK (stamina_end_pct IS NULL OR stamina_end_pct BETWEEN 0 AND 100),

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (activity_id, split_index)
);

CREATE INDEX IF NOT EXISTS idx_kilometer_split_activity_id
    ON kilometer_split(activity_id);

CREATE TABLE IF NOT EXISTS activity_workout_structure (
    activity_id INTEGER PRIMARY KEY REFERENCES activity(id) ON DELETE CASCADE,
    has_workout_structure INTEGER NOT NULL CHECK (has_workout_structure IN (0, 1)),
    source TEXT NOT NULL DEFAULT 'fit',
    sport TEXT,
    sub_sport TEXT,
    workout_name TEXT,
    workout_description TEXT,
    num_valid_steps INTEGER CHECK (num_valid_steps IS NULL OR num_valid_steps >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS activity_workout_step (
    id INTEGER PRIMARY KEY,
    activity_id INTEGER NOT NULL REFERENCES activity(id) ON DELETE CASCADE,
    step_index INTEGER NOT NULL CHECK (step_index > 0),
    source_message_index INTEGER,
    intensity TEXT,
    duration_type TEXT,
    duration_value INTEGER,
    duration_distance_m REAL CHECK (duration_distance_m IS NULL OR duration_distance_m >= 0),
    duration_time_sec REAL CHECK (duration_time_sec IS NULL OR duration_time_sec >= 0),
    target_type TEXT,
    target_value REAL,
    target_value_low REAL,
    target_value_high REAL,
    target_hr_zone INTEGER,
    repeat_steps INTEGER,
    secondary_target_value REAL,
    custom_target_value_low REAL,
    custom_target_value_high REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (activity_id, step_index)
);

CREATE INDEX IF NOT EXISTS idx_activity_workout_step_activity_id
    ON activity_workout_step(activity_id);

CREATE TABLE IF NOT EXISTS activity_workout_split (
    id INTEGER PRIMARY KEY,
    activity_id INTEGER NOT NULL REFERENCES activity(id) ON DELETE CASCADE,
    split_index INTEGER NOT NULL CHECK (split_index > 0),
    source_message_index INTEGER,
    split_type TEXT,
    num_splits INTEGER,
    total_distance_m REAL CHECK (total_distance_m IS NULL OR total_distance_m >= 0),
    total_timer_time_sec REAL CHECK (total_timer_time_sec IS NULL OR total_timer_time_sec >= 0),
    avg_speed_mps REAL CHECK (avg_speed_mps IS NULL OR avg_speed_mps >= 0),
    sport TEXT,
    sub_sport TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (activity_id, split_index)
);

CREATE INDEX IF NOT EXISTS idx_activity_workout_split_activity_id
    ON activity_workout_split(activity_id);

CREATE VIEW IF NOT EXISTS activity_view AS
SELECT
    activity.*,
    shoe.shoe_code,
    shoe.brand AS shoe_brand,
    shoe.model AS shoe_model,
    shoe.nickname AS shoe_nickname,
    workout_type.workout_type_code,
    workout_type.name_en AS workout_type_name_en,
    workout_type.name_zh AS workout_type_name_zh,
    workout_type.intensity_category,
    workout_type.is_quality_session,
    workout_type.is_long_run,
    workout_type.is_recovery_focused,
    CAST(ROUND(activity.duration_sec * 1.0 / activity.distance_km) AS INTEGER) AS avg_pace_sec_per_km
FROM activity
LEFT JOIN shoe
    ON activity.shoe_id = shoe.id
LEFT JOIN workout_type
    ON activity.workout_type_id = workout_type.id;

CREATE VIEW IF NOT EXISTS kilometer_split_view AS
SELECT
    kilometer_split.*,
    CAST(ROUND(elapsed_time_sec * 1000.0 / split_distance_m) AS INTEGER) AS elapsed_pace_sec_per_km,
    split_distance_m * 1.0 / elapsed_time_sec AS avg_speed_mps
FROM kilometer_split;

CREATE VIEW IF NOT EXISTS activity_training_purpose_view AS
SELECT
    activity_training_purpose.*,
    activity.activity_start_time,
    activity.fit_sha256,
    training_purpose.training_purpose_code,
    training_purpose.name_en AS training_purpose_name_en,
    training_purpose.name_zh AS training_purpose_name_zh,
    training_purpose.purpose_category,
    training_purpose.is_primary_physiological,
    training_purpose.is_recovery_related,
    training_purpose.is_performance_related
FROM activity_training_purpose
JOIN activity
    ON activity_training_purpose.activity_id = activity.id
JOIN training_purpose
    ON activity_training_purpose.training_purpose_id = training_purpose.id;

CREATE VIEW IF NOT EXISTS shoe_statistics_view AS
SELECT
    shoe.id AS shoe_id,
    shoe.shoe_code,
    shoe.brand,
    shoe.model,
    shoe.nickname,
    shoe.category,
    shoe.is_active,
    COUNT(activity.id) AS run_count,
    COALESCE(ROUND(SUM(activity.distance_km), 2), 0) AS total_distance_km,
    MIN(activity.activity_start_time) AS observed_first_run_time,
    MAX(activity.activity_start_time) AS observed_last_run_time,
    ROUND(AVG(activity.avg_hr), 1) AS avg_hr
FROM shoe
LEFT JOIN activity
    ON activity.shoe_id = shoe.id
GROUP BY
    shoe.id,
    shoe.shoe_code,
    shoe.brand,
    shoe.model,
    shoe.nickname,
    shoe.category,
    shoe.is_active;
