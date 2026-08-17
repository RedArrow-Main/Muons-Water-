"""USDM drought status connector.

The USDA Drought Monitor statistics API (usdmdataservices.unl.edu) returns
CSV (one row per week per area), NOT XML. Each row carries area-percent
coverage for D0–D4; the dominant level is the highest-severity band with
coverage > 0.
"""
from __future__ import annotations

import csv
import io
import logging
import time
from datetime import date

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

USDM_URL = (
    "https://usdmdataservices.unl.edu/api/CountyStatistics/"
    "GetDroughtSeverityStatisticsByArea"
    "?aoi={fips}&startdate={start}&enddate={end}&statisticsType=1"
)


def _parse_usdm_csv(text: str) -> list[dict]:
    """Parse the USDM CSV response into drought-status rows.

    CSV columns: MapDate,FIPS,County,State,None,D0,D1,D2,D3,D4,
    ValidStart,ValidEnd,StatisticFormatID
    Returns [], not raises, on malformed input.
    """
    rows: list[dict] = []
    try:
        reader = csv.DictReader(io.StringIO(text))
        for r in reader:
            valid_end = (r.get("ValidEnd") or "").strip()
            if not valid_end:
                continue
            d_vals: dict[str, float] = {}
            for level in ("D0", "D1", "D2", "D3", "D4"):
                raw = (r.get(level) or "0").strip()
                try:
                    d_vals[level] = float(raw)
                except ValueError:
                    d_vals[level] = 0.0
            usdm_level = "NONE"
            for level in ("D4", "D3", "D2", "D1", "D0"):
                if d_vals.get(level, 0.0) > 0:
                    usdm_level = level
                    break
            rows.append({"week_ending": valid_end[:10], "usdm_level": usdm_level})
    except (csv.Error, ValueError):
        return []
    return rows


def fetch_drought(session: Session, county: dict, start_date: str, end_date: str) -> int:
    fips = county["fips"]

    start_fmt = date.fromisoformat(start_date).strftime("%m/%d/%Y")
    end_fmt = date.fromisoformat(end_date).strftime("%m/%d/%Y")

    url = USDM_URL.format(fips=fips, start=start_fmt, end=end_fmt)

    try:
        with httpx.Client() as client:
            resp = client.get(url, timeout=10)
            resp.raise_for_status()
            csv_text = resp.text
    except httpx.HTTPError as exc:
        logger.warning("USDM fetch failed for %s: %s", fips, exc)
        return 0

    rows = _parse_usdm_csv(csv_text)
    if not rows:
        logger.warning("No USDM data parsed for %s", fips)
        return 0

    stmt = text("""
        INSERT INTO drought_status (county_fips, week_ending, usdm_level)
        VALUES (:fips, :week, :level)
        ON CONFLICT (county_fips, week_ending) DO UPDATE SET
            usdm_level = EXCLUDED.usdm_level
    """)
    count = 0
    for row in rows:
        session.execute(stmt, {
            "fips": fips,
            "week": row["week_ending"],
            "level": row["usdm_level"],
        })
        count += 1
    session.commit()
    time.sleep(0.5)
    return count
