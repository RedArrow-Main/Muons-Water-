"""SSURGO connector tests: NY snapshot integrity, texture parser, live fetch."""
from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.ingest.counties_data import get_counties
from app.ingest.ssurgo import NY_COUNTY_SSURGO, _texture_from_map_unit

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://user:password@127.0.0.1:5432/furrowcast",
)

engine = create_engine(DATABASE_URL)


def _ny_fips() -> set[str]:
    return {c["fips"] for c in get_counties() if c["state"] == "NY"}


# --- snapshot integrity (pure) -------------------------------------------------


def test_snapshot_has_expected_count():
    assert len(NY_COUNTY_SSURGO) == 41


def test_snapshot_fips_are_ny():
    assert all(f.startswith("36") and len(f) == 5 for f in NY_COUNTY_SSURGO)


def test_snapshot_values_are_sane():
    for soil_type, awc in NY_COUNTY_SSURGO.values():
        assert soil_type
        assert 0.0 < awc <= 1.0


def test_snapshot_covers_all_ny_with_fallback():
    assert len(_ny_fips() - set(NY_COUNTY_SSURGO)) == 21


def test_snapshot_has_real_variety():
    textures = {t for t, _ in NY_COUNTY_SSURGO.values()}
    awcs = {a for _, a in NY_COUNTY_SSURGO.values()}
    assert len(textures) >= 10
    assert len(awcs) >= 10


def test_snapshot_matches_reference_values():
    assert NY_COUNTY_SSURGO["36037"] == ("mucky very fine sandy loam", 0.1616)
    assert NY_COUNTY_SSURGO["36105"] == ("muck", 0.4000)
    assert NY_COUNTY_SSURGO["36103"] == ("loam", 0.0998)
    assert NY_COUNTY_SSURGO["36029"] == ("silt loam", 0.1183)


# --- texture parser (pure) -----------------------------------------------------


def test_texture_map_unit_silt_loam():
    assert _texture_from_map_unit("Hudson silt loam, 2 to 6 percent slopes (HuB)") == "silt loam"


def test_texture_map_unit_loamy_fine_sand():
    assert _texture_from_map_unit("Colonie loamy fine sand, 2 to 6 percent slopes (CmB)") == "loamy fine sand"


def test_texture_map_unit_mucky():
    assert _texture_from_map_unit("Fredon mucky very fine sandy loam, 0 to 3 percent slopes (FdA)") == "mucky very fine sandy loam"


def test_texture_map_unit_channery():
    assert _texture_from_map_unit("Channery silt loam, 3 to 8 percent slopes (CbB)") == "channery silt loam"


def test_texture_map_unit_silty_clay_loam():
    assert _texture_from_map_unit("Dunkirk silty clay loam") == "silty clay loam"


def test_texture_map_unit_silty_clay():
    assert _texture_from_map_unit("Silty clay, 2 to 6 percent slopes") == "silty clay"


def test_texture_map_unit_urban_is_none():
    assert _texture_from_map_unit("Urban land, till substratum, 0 to 5 percent slopes (Ur)") is None


def test_texture_map_unit_water_is_none():
    assert _texture_from_map_unit("Water (W)") is None


def test_texture_map_unit_rock_outcrop_is_none():
    assert _texture_from_map_unit("Rock outcrop, limestone, 8 to 15 percent slopes (RlC)") is None


def test_texture_map_unit_none_is_none():
    assert _texture_from_map_unit(None) is None


# --- live fetch (mocked HTTP) --------------------------------------------------


class _FakeResponse:
    def __init__(self, html: str):
        self.text = html


def _sample_html() -> str:
    return (
        '<span class="mu-name">Hudson silt loam, 2 to 6 percent slopes (HuB)</span>'
        "<div>...Available Water Storage (0-100cm):</span>"
        ' <span class="record"> 16.33 cm </span>...'
    )


def test_fetch_soilweb_soil_parses(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResponse(_sample_html()))

    from app.ingest.ssurgo import fetch_soilweb_soil

    assert fetch_soilweb_soil(42.0, -76.0) == ("silt loam", 0.1633)


def test_fetch_soilweb_soil_http_error(monkeypatch):
    import httpx

    def boom(*a, **k):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(httpx, "get", boom)

    from app.ingest.ssurgo import fetch_soilweb_soil

    assert fetch_soilweb_soil(42.0, -76.0) == (None, None)


def test_fetch_soilweb_soil_no_texture(monkeypatch):
    import httpx

    html = '<span class="mu-name">Urban land, till substratum (Ur)</span>'

    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResponse(html))

    from app.ingest.ssurgo import fetch_soilweb_soil

    assert fetch_soilweb_soil(42.0, -76.0) == (None, None)


# --- DB integration (seeded soils table) ---------------------------------------


def test_soils_rows_cover_all_ny():
    with Session(engine) as db:
        rows = db.execute(text("SELECT county_fips FROM soils")).fetchall()
        fips = {r[0] for r in rows}
    assert _ny_fips().issubset(fips)


def test_soils_ny_have_real_variety():
    with Session(engine) as db:
        rows = db.execute(text(
            "SELECT s.soil_type, s.awc FROM soils s "
            "JOIN counties c ON c.fips = s.county_fips WHERE c.state = 'NY'"
        ))
        soils = {(r[0], float(r[1])) for r in rows}
    assert len(soils) >= 25
    assert len({t for t, _ in soils}) >= 10


def test_soils_reference_counties():
    expected = {
        "36037": ("mucky very fine sandy loam", 0.1616),
        "36103": ("loam", 0.0998),
        "36029": ("silt loam", 0.1183),
        "36105": ("muck", 0.4000),
    }
    with Session(engine) as db:
        for fips, (soil_type, awc) in expected.items():
            row = db.execute(
                text("SELECT soil_type, awc FROM soils WHERE county_fips = :fips"),
                {"fips": fips},
            ).first()
            assert row is not None
            assert row[0] == soil_type
            assert abs(float(row[1]) - awc) < 1e-4
