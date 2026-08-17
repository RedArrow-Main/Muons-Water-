"""CLI runner for the data pipeline.

Usage:
    python -m app.ingest.run --date 2026-08-01
    python -m app.ingest.run --from 2026-07-01 --to 2026-07-29
"""
from __future__ import annotations

import argparse
import traceback
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.connection import SessionLocal
from app.ingest.county_loader import load_counties
from app.ingest.noaa_nws import fetch_nws_forecast
from app.ingest.open_meteo import fetch_history, fetch_forecast
from app.ingest.usdm import fetch_drought
from app.ingest.ssurgo import load_soils
from app.ingest.counties_data import get_counties
from sqlalchemy import text


def _log_run(session: Session, source: str, started_at: datetime, rows: int, status: str, error: str | None = None):
    session.execute(
        text("""
            INSERT INTO ingest_runs (source, started_at, finished_at, rows_upserted, status, error_message)
            VALUES (:source, :started, :finished, :rows, :status, :error)
        """),
        {
            "source": source,
            "started": started_at,
            "finished": datetime.utcnow(),
            "rows": rows,
            "status": status,
            "error": error,
        },
    )
    session.commit()


def _run_counties(session: Session) -> int:
    return load_counties(session)


def _run_ssurgo(session: Session) -> int:
    return load_soils(session)


def _run_nws(session: Session, counties: list[dict]) -> int:
    total = 0
    for county in counties:
        try:
            total += fetch_nws_forecast(session, county)
        except Exception as exc:
            print(f"  NWS error for {county['fips']}: {exc}")
    return total


def _run_open_meteo_history(session: Session, counties: list[dict], from_date: str, to_date: str) -> int:
    total = 0
    for county in counties:
        try:
            total += fetch_history(session, county, from_date, to_date)
        except Exception as exc:
            print(f"  Open-Meteo history error for {county['fips']}: {exc}")
    return total


def _run_open_meteo_forecast(session: Session, counties: list[dict]) -> int:
    total = 0
    for county in counties:
        try:
            total += fetch_forecast(session, county)
        except Exception as exc:
            print(f"  Open-Meteo forecast error for {county['fips']}: {exc}")
    return total


def _run_usdm(session: Session, counties: list[dict], from_date: str, to_date: str) -> int:
    total = 0
    for county in counties:
        try:
            total += fetch_drought(session, county, from_date, to_date)
        except Exception as exc:
            print(f"  USDM error for {county['fips']}: {exc}")
    return total


def run(source: str | None = None, date: str | None = None,
        from_date: str | None = None, to_date: str | None = None,
        states: list[str] | None = None):
    session = SessionLocal()
    counties = get_counties()
    if states:
        states_set = {s.upper() for s in states}
        counties = [c for c in counties if c["state"] in states_set]
    try:
        connectors = ["county_loader", "noaa_nws", "open_meteo", "usdm", "ssurgo"] if source == "all" or source is None else [source]

        run_date = date or to_date or datetime.utcnow().strftime("%Y-%m-%d")
        hist_from = from_date or "2024-01-01"
        hist_to = run_date

        print(f"Pipeline run: date={run_date}, from={hist_from}, to={hist_to}, source={source}")

        for conn_name in connectors:
            started = datetime.utcnow()
            rows = 0
            status = "ok"
            error_msg = None
            print(f"\n--- {conn_name} ---")
            try:
                if conn_name == "county_loader":
                    rows = _run_counties(session)
                elif conn_name == "ssurgo":
                    rows = _run_ssurgo(session)
                elif conn_name == "noaa_nws":
                    rows = _run_nws(session, counties)
                elif conn_name == "open_meteo":
                    rows += _run_open_meteo_forecast(session, counties)
                    rows += _run_open_meteo_history(session, counties, hist_from, hist_to)
                elif conn_name == "usdm":
                    rows = _run_usdm(session, counties, hist_from, hist_to)
                else:
                    print(f"  Unknown source: {conn_name}")
                    continue
            except Exception as exc:
                status = "error"
                error_msg = str(exc)
                traceback.print_exc()
            finally:
                _log_run(session, conn_name, started, rows, status, error_msg)
                print(f"  => {rows} rows, status={status}")

        print("\n--- Summary ---")
        result = session.execute(text("SELECT source, status, rows_upserted FROM ingest_runs ORDER BY id DESC LIMIT 5"))
        for row in result:
            print(f"  {row[0]}: {row[1]} ({row[2]} rows)")
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="FurrowCast data pipeline")
    parser.add_argument("--date", help="Run date (YYYY-MM-DD)")
    parser.add_argument("--from", dest="from_date", help="Backfill start date")
    parser.add_argument("--to", dest="to_date", help="Backfill end date")
    parser.add_argument("--source", choices=["county_loader", "noaa_nws", "open_meteo", "usdm", "ssurgo", "all"],
                        help="Run only this connector")
    parser.add_argument("--state", help="Comma-separated state codes to scope connectors (e.g. NY)")
    args = parser.parse_args()
    states = args.state.split(",") if args.state else None
    run(source=args.source, date=args.date, from_date=args.from_date, to_date=args.to_date, states=states)


if __name__ == "__main__":
    main()
