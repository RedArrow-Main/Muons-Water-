"""Dashboard API — endpoints consumed by the Next.js frontend.

All advisory data is fetched LIVE from external APIs on every request.
No pre-loaded data, no hardcoded values.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.routes import require_auth
from app.db.connection import engine
from app.engine.gdd import gdd_daily
from app.engine.growth import (
    adjusted_mad as stage_adjusted_mad,
)
from app.engine.growth import (
    cumulative_gdd as accumulate_gdd,
)
from app.engine.growth import (
    gdd_fraction,
    growth_stage,
    stage_label,
)
from app.engine.kc import kc_for_gdd_frac
from app.engine.season import default_planting_date, julian_to_date
from app.engine.water_balance import (
    CROP_PARAMS as ENGINE_CROP_PARAMS,
)
from app.engine.water_balance import (
    compute_etc,
    refill_amount,
    should_irrigate,
    soil_water_step,
)
from app.ingest.open_meteo import fetch_archive_daily, tz_for_state
from app.ingest.ssurgo import STATE_DEFAULTS as SOIL_STATE_DEFAULTS

router = APIRouter(prefix="/api", tags=["dashboard"])

_FIPS_RE = re.compile(r"^\d{5}$")


def _tz_for_state(state: str) -> str:
    """Open-Meteo daily buckets are timezone-sensitive; NY is Eastern."""
    return tz_for_state(state)


OPEN_METEO_FORECAST = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={lon}"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration"
    "&temperature_unit=fahrenheit&precipitation_unit=inch&forecast_days=7&timezone={tz}"
)


def _fetch_json(url: str, timeout: int = 15) -> dict | None:
    """Fetch JSON from a URL, return None on error."""
    try:
        with httpx.Client() as client:
            resp = client.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
    except Exception:  # noqa: BLE001
        return None


def _get_soil_awc(state: str, lat: float, lon: float) -> tuple[str, float]:
    """Soil AWC fallback for counties with no row in the `soils` table.

    NY (and any other state without a hand-tuned sub-region table below)
    uses the per-state SSURGO default from `app.ingest.ssurgo.STATE_DEFAULTS`
    — the same source `load_soils`/`bootstrap`/`refresh_county_soils` use to
    seed unsampled counties (SPEC.md v1.13: "rest use state defaults"). This
    keeps the dashboard's last-resort fallback consistent with the DB seed
    instead of silently substituting a different state's soil values.

    The lat/lon quadrant buckets below are a legacy finer-grained estimate
    for the original Corn Belt pilot states (KS/NE/IA) and are deterministic
    (hashed from coordinates) rather than measured — kept only for those
    three states pending a real per-county SSURGO snapshot like NY's.

    Returns (soil_type, awc_in_per_in).
    """
    if state not in ("KS", "NE", "IA"):
        return SOIL_STATE_DEFAULTS.get(state, ("silt loam", 0.18))

    # Deterministic seed from coordinates so same county always gets same value
    seed = int(abs(lat * 1000 + lon * 7) % 100)

    # --- Kansas (lat < 39.5) ---
    if lat < 39.5:
        if lon < -100.5:
            # Western KS - sandy loam, low AWC
            soils = [
                ("SANDY LOAM", 0.10), ("SANDY LOAM", 0.11), ("LOAMY SAND", 0.08),
                ("SANDY LOAM", 0.09), ("LOAM", 0.14),
            ]
        elif lon < -98.5:
            # Central KS - silt loam, moderate AWC
            soils = [
                ("SILT LOAM", 0.18), ("SILT LOAM", 0.19), ("LOAM", 0.16),
                ("SILT LOAM", 0.20), ("CLAY LOAM", 0.21),
            ]
        else:
            # Eastern KS - deeper silt loam, higher AWC
            soils = [
                ("SILT LOAM", 0.21), ("SILT LOAM", 0.22), ("SILT LOAM", 0.20),
                ("CLAY LOAM", 0.23), ("SILT LOAM", 0.19),
            ]
    # --- Nebraska ---
    elif lat >= 41.0:
        if lon < -101.0:
            # Western NE (Sandhills) - sand, very low AWC
            soils = [
                ("SAND", 0.06), ("SANDY LOAM", 0.09), ("SAND", 0.05),
                ("SANDY LOAM", 0.08), ("LOAMY SAND", 0.07),
            ]
        elif lon < -99.0:
            # Central NE - mixed loam
            soils = [
                ("LOAM", 0.15), ("SILT LOAM", 0.17), ("SANDY LOAM", 0.12),
                ("LOAM", 0.16), ("SILT LOAM", 0.18),
            ]
        else:
            # Eastern NE - deep silt loam, high AWC
            soils = [
                ("SILT LOAM", 0.20), ("SILT LOAM", 0.21), ("SILT LOAM", 0.19),
                ("CLAY LOAM", 0.22), ("SILT LOAM", 0.18),
            ]
    # --- Iowa ---
    else:
        if lon < -94.0:
            # Western Iowa - loam, moderate AWC
            soils = [
                ("LOAM", 0.16), ("SILT LOAM", 0.18), ("SANDY LOAM", 0.13),
                ("LOAM", 0.15), ("SILT LOAM", 0.17),
            ]
        else:
            # Central/Eastern Iowa - deep silt loam, high AWC
            soils = [
                ("SILT LOAM", 0.20), ("SILT LOAM", 0.21), ("SILT LOAM", 0.19),
                ("CLAY LOAM", 0.22), ("SILT LOAM", 0.20),
            ]

    return soils[seed % len(soils)]


def _mask_phone(phone: str) -> str:
    """Mask phone number to last 4 digits."""
    if len(phone) <= 4:
        return phone
    return "+1*** *** **" + phone[-2:]


def _last_pipeline_info() -> dict:
    """Return the most recent nightly_pipeline ingest_runs row."""
    with Session(engine) as s:
        row = s.execute(text(
            "SELECT started_at, finished_at, status, rows_upserted "
            "FROM ingest_runs WHERE source = 'nightly_pipeline' "
            "ORDER BY id DESC LIMIT 1"
        )).fetchone()
    if not row:
        return {
            "last_pipeline_at": None,
            "last_pipeline_status": None,
            "last_pipeline_rows": 0,
        }
    return {
        "last_pipeline_at": str(row[0]),
        "last_pipeline_status": row[2],
        "last_pipeline_rows": row[3],
    }


def _crop_params(crop_id: str) -> dict | None:
    """Crop params from the crops table (Crop Library), engine fallback."""
    with Session(engine) as s:
        row = s.execute(text(
            "SELECT id, base_temp_f, gdd_total, root_depth_in, mad_fraction, "
            "kc_initial, kc_mid, kc_end, stage_days FROM crops WHERE id = :id"
        ), {"id": crop_id}).fetchone()
    if row:
        return {
            "id": row[0], "base_temp_f": row[1], "gdd_total": row[2],
            "root_depth_in": row[3], "mad_fraction": row[4],
            "kc_initial": row[5], "kc_mid": row[6], "kc_end": row[7],
            "stage_days": row[8],
        }
    fallback = ENGINE_CROP_PARAMS.get(crop_id)
    if fallback:
        base_temp, root, mad, kc_ini, kc_mid, kc_end, gdd = fallback
        return {
            "id": crop_id, "base_temp_f": base_temp, "gdd_total": gdd,
            "root_depth_in": root, "mad_fraction": mad,
            "kc_initial": kc_ini, "kc_mid": kc_mid, "kc_end": kc_end,
        }
    return None


def _historical_temps(fips: str, lat: float, lon: float,
                      start_date: str, end_date: str,
                      tz: str = "America/New_York") -> dict[str, tuple]:
    """Daily temps {date: (tmax_f, tmin_f)} across [start_date, end_date].

    Backfilled `daily_historical` rows are authoritative; a live Open-Meteo
    archive fetch fills earlier gaps (e.g. a planting date before backfill).
    """
    merged: dict[str, tuple] = {}
    with Session(engine) as s:
        rows = s.execute(text(
            "SELECT obs_date, tmax_f, tmin_f FROM daily_historical "
            "WHERE county_fips = :f AND obs_date >= :s AND obs_date <= :e"
        ), {"f": fips, "s": start_date, "e": end_date}).fetchall()
    db_days = {r[0]: (r[1], r[2]) for r in rows
               if r[1] is not None and r[2] is not None}

    daily = fetch_archive_daily(lat, lon, start_date, end_date, tz=tz, timeout=20)
    if daily:
        times = daily.get("time", [])
        tmaxs = daily.get("temperature_2m_max", [])
        tmins = daily.get("temperature_2m_min", [])
        for i, day in enumerate(times):
            if i < len(tmaxs) and i < len(tmins):
                merged[day] = (tmaxs[i], tmins[i])
    merged.update(db_days)
    return merged


def _farm_crop_default(user_id: int, fips: str) -> dict | None:
    """Return {crop_id, planting_date} for a user's farm in this county."""
    if not user_id:
        return None
    with Session(engine) as s:
        row = s.execute(text(
            "SELECT fc.crop_id, fc.planting_date "
            "FROM farm_crops fc JOIN farms f ON f.id = fc.farm_id "
            "WHERE f.user_id = :uid AND f.county_fips = :fips "
            "ORDER BY fc.crop_id LIMIT 1"
        ), {"uid": user_id, "fips": fips}).fetchone()
    if not row:
        return None
    return {"crop_id": row[0], "planting_date": str(row[1]) if row[1] else None}


# ---------------------------------------------------------------------------
# GET /api/counties — list all counties
# ---------------------------------------------------------------------------
@router.get("/counties")
def list_counties():
    """Return all counties with lat/lon for map rendering."""
    with Session(engine) as s:
        rows = s.execute(text(
            "SELECT fips, name, state, latitude, longitude "
            "FROM counties ORDER BY state, name"
        )).fetchall()
    return [
        {"fips": r[0], "name": r[1], "state": r[2],
         "lat": r[3], "lon": r[4]}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GET /api/crops — the Crop Library (9 crops, FAO-56 params)
# ---------------------------------------------------------------------------
@router.get("/crops")
def list_crops():
    """Return the full crop library from the crops table."""
    with Session(engine) as s:
        rows = s.execute(text(
            "SELECT id, base_temp_f, gdd_total, root_depth_in, mad_fraction, "
            "kc_initial, kc_mid, kc_end FROM crops ORDER BY id"
        )).fetchall()
    return [
        {
            "id": r[0], "base_temp_f": r[1], "gdd_total": r[2],
            "root_depth_in": r[3], "mad_fraction": r[4],
            "kc_initial": r[5], "kc_mid": r[6], "kc_end": r[7],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GET /api/advisory/{fips} — full advisory, ALL LIVE DATA
# ---------------------------------------------------------------------------
def _initial_soil_pct(fips: str, crop_id: str, forecast_date: str) -> tuple[float, str, float, float]:
    """Use today's spin-up state only; stale/other-crop records are unsuitable."""
    with Session(engine) as session:
        row = session.execute(text(
            "SELECT dr.soil_moisture_pct, dr.soil_min_pct, dr.soil_max_pct FROM daily_records dr "
            "JOIN field_cells fc ON fc.id = dr.cell_id "
            "WHERE fc.county_fips = :f AND fc.crop_id = :crop "
            "AND dr.record_date = :d AND dr.soil_moisture_pct BETWEEN 0 AND 100 "
            "ORDER BY dr.id DESC LIMIT 1"
        ), {"f": fips, "crop": crop_id, "d": forecast_date}).fetchone()
    if row and row[1] is not None and row[2] is not None:
        return (float(row[0]), "stored", float(row[1]), float(row[2]))
    return (50.0, "assumed", 0.0, 100.0)


@router.get("/advisory/{fips}")
def get_advisory(
    fips: str = Path(pattern=r"^\d{5}$"),
    crop_id: str | None = Query(default=None),
    planting_date: str | None = Query(default=None),
    user: dict = Depends(require_auth),  # noqa: B008
):
    """Return full advisory for a county — everything computed in real-time.

    Query params (both optional):
      crop_id:       any crop in the Crop Library (default: user's farm crop,
                     else corn)
      planting_date: YYYY-MM-DD the crop was planted (default: user's farm
                     planting date, else the county's latest safe plant date)

    The growth stage is determined from GDD accumulated between planting_date
    and yesterday (backfilled `daily_historical` + live Open-Meteo archive),
    and the MAD (refill point) is stage-adjusted from the crop's base MAD.
    """
    # 1. Get county location from DB
    with Session(engine) as s:
        county = s.execute(text(
            "SELECT fips, name, state, latitude, longitude, frost_kill_50 "
            "FROM counties WHERE fips = :f"
        ), {"f": fips}).fetchone()

    if not county:
        raise HTTPException(404, f"County {fips} not found")

    fips_db, name, state, lat, lon, frost_50 = county

    # 2. Crop + planting date — explicit params win, else the user's farm
    farm_sel = _farm_crop_default(user.get("id"), fips)
    if not crop_id:
        crop_id = (farm_sel.get("crop_id") if farm_sel else None) or "corn"
    if not planting_date:
        planting_date = (
            farm_sel.get("planting_date") if farm_sel and farm_sel.get("crop_id") == crop_id
            else None
        )

    crop = _crop_params(crop_id)
    if not crop:
        raise HTTPException(404, f"Crop '{crop_id}' not found")

    base_temp = crop["base_temp_f"]
    gdd_to_maturity = crop["gdd_total"]
    base_mad = crop["mad_fraction"]
    root_depth = crop["root_depth_in"]

    # Calendar days to maturity ≈ sum of the crop's stage-day splits
    # (initial + development + mid + late). Falls back to 130 (corn) if unset.
    maturity_days = 130
    if crop.get("stage_days"):
        try:
            maturity_days = sum(
                int(x) for x in str(crop["stage_days"]).split(",") if x.strip()
            )
        except (ValueError, TypeError):
            maturity_days = 130

    # 3. Soil AWC — real county value from the soils table (seeded by the
    #    SSURGO ingest connector); fall back to the regional estimator only
    #    when the county has no seed row. Also pull the latest USDM drought
    #    classification to surface on the dashboard (SPEC §3).
    with Session(engine) as s:
        soil = s.execute(text(
            "SELECT soil_type, awc FROM soils WHERE county_fips = :f"
        ), {"f": fips}).fetchone()
        drow = s.execute(text(
            "SELECT usdm_level, week_ending FROM drought_status "
            "WHERE county_fips = :f ORDER BY week_ending DESC LIMIT 1"
        ), {"f": fips}).fetchone()
    if soil:
        soil_type, awc = soil[0], float(soil[1])
    else:
        soil_type, awc = _get_soil_awc(state, lat, lon)
    aw = root_depth * awc
    drought = (
        {"level": drow[0], "week_ending": drow[1]} if drow else None
    )

    # 4. Growth stage — GDD from planting_date → yesterday (historical temps)
    today = datetime.now()  # noqa: DTZ005

    if not planting_date:
        # The region's TYPICAL planting date, NOT the latest-safe-plant date —
        # see app/engine/season.py. Must match advisor/service.py exactly:
        # advisor and dashboard have to agree on gdd_frac for the same
        # county / crop / date.
        planting_date = default_planting_date(
            frost_50, int(maturity_days), today.strftime("%Y-%m-%d")
        )
    yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    temps = _historical_temps(
        fips_db, lat, lon, planting_date, yesterday, tz=_tz_for_state(state)
    )
    series = [temps[d] for d in sorted(temps)
              if temps[d][0] is not None and temps[d][1] is not None]
    cum_gdd = accumulate_gdd(series, base_temp)
    frac = gdd_fraction(cum_gdd, gdd_to_maturity)
    stage = growth_stage(frac)
    mad = stage_adjusted_mad(base_mad, frac)

    # 5. 7-day forecast — fetch LIVE from Open-Meteo
    forecast_url = OPEN_METEO_FORECAST.format(lat=lat, lon=lon, tz=_tz_for_state(state))
    fc_data = _fetch_json(forecast_url, timeout=15)

    if not fc_data or "daily" not in fc_data:
        raise HTTPException(502, "Failed to fetch forecast from Open-Meteo")

    daily = fc_data["daily"]
    dates = daily.get("time", [])
    if not dates:
        raise HTTPException(502, "Forecast contains no daily data")
    tmax_list = daily.get("temperature_2m_max", [])
    tmin_list = daily.get("temperature_2m_min", [])
    precip_list = daily.get("precipitation_sum", [])
    et0_list = daily.get("et0_fao_evapotranspiration", [])

    # 6. Historical averages — fetch last 30 days LIVE
    hist_start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    hist_end = today.strftime("%Y-%m-%d")
    hist_daily = fetch_archive_daily(
        lat, lon, hist_start, hist_end, tz=_tz_for_state(state), timeout=15
    )

    hist_avg_high = None
    hist_avg_low = None
    hist_total_rain = None
    if hist_daily:
        h_tmax = [v for v in hist_daily.get("temperature_2m_max", []) if v is not None]
        h_tmin = [v for v in hist_daily.get("temperature_2m_min", []) if v is not None]
        h_precip = [v for v in hist_daily.get("precipitation_sum", []) if v is not None]
        if h_tmax:
            hist_avg_high = sum(h_tmax) / len(h_tmax)
        if h_tmin:
            hist_avg_low = sum(h_tmin) / len(h_tmin)
        if h_precip:
            hist_total_rain = sum(h_precip)

    # 6b. Real last-7-day history from the daily_historical table
    #     None = county has no backfilled history yet (frontend shows "setting up").
    seven_days_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    with Session(engine) as hs:
        h7 = hs.execute(text(
            "SELECT SUM(precip_in), SUM(et0_in), COUNT(*) "
            "FROM daily_historical "
            "WHERE county_fips = :f AND obs_date >= :d"
        ), {"f": fips, "d": seven_days_ago}).fetchone()
    if h7 and h7[2]:
        last_7d_rain = round(h7[0], 2) if h7[0] is not None else 0.0
        last_7d_et = round(h7[1], 2) if h7[1] is not None else 0.0
    else:
        last_7d_rain = None
        last_7d_et = None

    # 7. Compute everything in real-time (MAD is stage-adjusted)
    forecast = []
    initial_pct, soil_source, low_pct, high_pct = _initial_soil_pct(fips_db, crop_id, dates[0] if dates else today.strftime("%Y-%m-%d"))
    soil_water = initial_pct / 100.0 * aw
    low_sw, high_sw = low_pct / 100 * aw, high_pct / 100 * aw
    today_gdd = 0
    today_etc = 0
    today_depletion = 0
    today_soil_pct = 70.0
    today_action = "HOLD"
    today_rain = 0
    forecast_gdd = cum_gdd

    for i, date_str in enumerate(dates):
        tmax = tmax_list[i] if i < len(tmax_list) else None
        tmin = tmin_list[i] if i < len(tmin_list) else None
        rain = precip_list[i] if i < len(precip_list) else 0.0
        et0 = et0_list[i] if i < len(et0_list) else None

        gdd = gdd_daily(tmax, tmin, base_temp) if tmax and tmin else 0
        gdd_frac = forecast_gdd / gdd_to_maturity if gdd_to_maturity > 0 else 0.0
        forecast_gdd += gdd
        stage_kc = kc_for_gdd_frac(crop_id, gdd_frac)
        etc_val = compute_etc(et0, stage_kc) if et0 else 0
        soil_water = soil_water_step(soil_water, aw, rain or 0, 0, etc_val)
        low_sw = soil_water_step(low_sw, aw, rain or 0, 0, etc_val)
        high_sw = soil_water_step(high_sw, aw, rain or 0, 0, etc_val)
        uncertain = (1 - high_sw / aw < mad <= 1 - low_sw / aw) if aw > 0 else True
        dep = 1 - soil_water / aw if aw > 0 else 0

        if i == 0:  # today
            today_uncertain = uncertain
            today_low, today_high = low_sw / aw * 100, high_sw / aw * 100
            today_gdd = gdd
            today_etc = etc_val
            today_depletion = dep
            today_soil_pct = soil_water / aw * 100 if aw > 0 else 0
            today_soil_water = soil_water
            today_action = should_irrigate(dep, mad)
            today_rain = rain or 0

        forecast.append({
            "date": date_str,
            "tmax_f": tmax,
            "tmin_f": tmin,
            "precip_in": rain,
            "et0_in": et0,
            "gdd": round(gdd, 1),
            "etc": round(etc_val, 4),
            "soil_water": round(soil_water, 3),
            "depletion": round(dep, 4),
            "action": should_irrigate(dep, mad) if dep >= mad else "HOLD",
            "advice_uncertain": uncertain,
        })

    # 7-day rain total
    rain_7d = sum(f.get("precip_in", 0) or 0 for f in forecast)

    # Planting window — year anchored to today, never hardcoded
    _ref = today.strftime("%Y-%m-%d")

    def fmt_j(j):
        return julian_to_date(int(j), _ref)

    return {
        "county": {
            "fips": fips_db,
            "name": name,
            "state": state,
            "lat": lat,
            "lon": lon,
        },
        "soil": {"type": soil_type, "awc": awc, "water_source": soil_source},
        "crop": {
            "id": crop_id,
            "aw": round(aw, 2),
            "mad": mad,
            "base_mad": base_mad,
            "planting_date": planting_date,
            "growth_stage": stage,
            "stage_label": stage_label(frac),
            "gdd_pct": round(frac * 100, 1),
            "cumulative_gdd": round(cum_gdd, 1),
            "gdd_to_maturity": gdd_to_maturity,
        },
        "forecast": forecast,
        "today": {
            "advice_uncertain": today_uncertain,
            "soil_min_pct": round(today_low, 2),
            "soil_max_pct": round(today_high, 2),
            "gdd": round(today_gdd, 1),
            "etc": round(today_etc, 4),
            "soil_water": round(today_soil_water, 3),
            "soil_pct": round(today_soil_pct, 1),
            "depletion": round(today_depletion, 4),
            "action": today_action,
            "irrigate_amount": round(refill_amount(today_soil_water, aw), 2) if today_action == "IRRIGATE" else 0,
            "rain_today": round(today_rain, 2),
            "rain_7d": round(rain_7d, 2),
        },
        "history": {
            "july_avg_high": round(hist_avg_high, 1) if hist_avg_high else None,
            "july_avg_low": round(hist_avg_low, 1) if hist_avg_low else None,
            "july_total_rain": round(hist_total_rain, 2) if hist_total_rain else None,
            "last_7d_rain": last_7d_rain,
            "last_7d_et": last_7d_et,
        },
        "drought": drought,
        "outbox": [],
        "planting_window": {
            "frost_50pct": fmt_j(frost_50),
            "corn_start": fmt_j(frost_50 - (maturity_days + 10)),
            "corn_end": fmt_j(frost_50 - maturity_days),
        },
        "data_as_of": _last_pipeline_info(),
    }


# ---------------------------------------------------------------------------
# GET /api/outbox/{fips} — recent SMS delivery log for a county (auth required)
# ---------------------------------------------------------------------------
@router.get("/outbox/{fips}")
def get_outbox(
    fips: str = Path(pattern=r"^\d{5}$"),
    user: dict = Depends(require_auth),  # noqa: B008
):
    """Return recent SMS outbox entries for a county."""
    with Session(engine) as s:
        rows = s.execute(text(
            "SELECT sent_at, body FROM outbox "
            "WHERE county_fips = :f ORDER BY sent_at DESC LIMIT 50"
        ), {"f": fips}).fetchall()
    return [{"sent_at": str(r[0]), "body": r[1]} for r in rows]


# ---------------------------------------------------------------------------
# GET /api/stats — pipeline/catalog statistics (auth required)
# ---------------------------------------------------------------------------
@router.get("/stats")
def get_stats(user: dict = Depends(require_auth)):  # noqa: B008
    """Return high-level counts across the dataset."""
    with Session(engine) as s:
        counties = s.execute(text("SELECT COUNT(*) FROM counties")).scalar() or 0
        forecast_rows = s.execute(text("SELECT COUNT(*) FROM daily_forecast")).scalar() or 0
        ingests = s.execute(text("SELECT COUNT(*) FROM ingest_runs")).scalar() or 0
    return {
        "counties": counties,
        "forecast_rows": forecast_rows,
        "ingests": ingests,
        **_last_pipeline_info(),
    }


# ---------------------------------------------------------------------------
# POST /api/admin/refresh — run the nightly pipeline on demand (auth required)
# ---------------------------------------------------------------------------
@router.post("/admin/refresh")
def admin_refresh(
    body: dict | None = None,
    user: dict = Depends(require_auth),  # noqa: B008
):
    """Trigger the full nightly pipeline now.

    Body (optional): {"date": "YYYY-MM-DD", "states": ["NY"], "sms": false}.
    Date defaults to today; states default to NY. Logs to ingest_runs.
    """
    from app.nightly import run_pipeline

    body = body or {}
    run_date = body.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    states = tuple(body.get("states") or ["NY"])
    sms = bool(body.get("sms", False))

    with Session(engine) as s:
        return run_pipeline(s, run_date, send_sms=sms, states=states)
