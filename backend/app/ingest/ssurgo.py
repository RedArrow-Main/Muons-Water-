"""SSURGO soil AWC connector (precomputed dataset approach)."""
from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.orm import Session

STATE_DEFAULTS = {
    "AL": ("sandy loam", 0.14), "AK": ("loam", 0.20), "AZ": ("sandy loam", 0.13),
    "AR": ("silt loam", 0.15), "CA": ("sandy loam", 0.17), "CO": ("sandy loam", 0.15),
    "CT": ("loam", 0.18), "DE": ("sandy loam", 0.17), "DC": ("loam", 0.18),
    "FL": ("sandy loam", 0.13), "GA": ("sandy loam", 0.14), "HI": ("silt loam", 0.15),
    "ID": ("sandy loam", 0.19), "IL": ("silt loam", 0.20), "IN": ("silt loam", 0.19),
    "IA": ("silt loam", 0.20), "KS": ("silt loam", 0.17), "KY": ("silt loam", 0.17),
    "LA": ("silt loam", 0.14), "ME": ("silt loam", 0.18), "MD": ("sandy loam", 0.17),
    "MA": ("loam", 0.18), "MI": ("sandy loam", 0.19), "MN": ("silt loam", 0.20),
    "MS": ("silt loam", 0.14), "MO": ("silt loam", 0.18), "MT": ("silt loam", 0.17),
    "NE": ("silt loam", 0.20), "NV": ("sandy loam", 0.14), "NH": ("silt loam", 0.18),
    "NJ": ("sandy loam", 0.17), "NM": ("sandy loam", 0.13), "NY": ("silt loam", 0.18),
    "NC": ("sandy loam", 0.16), "ND": ("silt loam", 0.19), "OH": ("silt loam", 0.18),
    "OK": ("silt loam", 0.16), "OR": ("sandy loam", 0.19), "PA": ("silt loam", 0.18),
    "RI": ("sandy loam", 0.18), "SC": ("sandy loam", 0.15), "SD": ("silt loam", 0.19),
    "TN": ("silt loam", 0.17), "TX": ("silt loam", 0.15), "UT": ("sandy loam", 0.15),
    "VT": ("silt loam", 0.18), "VA": ("silt loam", 0.17), "WA": ("sandy loam", 0.19),
    "WV": ("silt loam", 0.16), "WI": ("silt loam", 0.20), "WY": ("sandy loam", 0.16),
    "AS": ("sandy loam", 0.13), "GU": ("sandy loam", 0.13), "MP": ("sandy loam", 0.13),
    "PR": ("sandy loam", 0.13), "VI": ("sandy loam", 0.13),
}

SOIL_DATA: dict[str, tuple[str, float]] = {
    "31001": ("silt loam", 0.21), "31003": ("silt loam", 0.19),
    "31005": ("loam", 0.17), "31007": ("sandy loam", 0.12),
    "31009": ("loam", 0.18), "31011": ("silt loam", 0.20),
    "31013": ("sandy loam", 0.11), "31015": ("silt loam", 0.19),
    "31017": ("loam", 0.17), "31019": ("silt loam", 0.21),
    "31021": ("silt loam", 0.22), "31023": ("silt loam", 0.21),
    "31025": ("silt loam", 0.22), "31027": ("silt loam", 0.20),
    "31029": ("sandy loam", 0.13), "31031": ("loam", 0.16),
    "31033": ("sandy loam", 0.12), "31035": ("silt loam", 0.20),
    "31037": ("silt loam", 0.21), "31039": ("silt loam", 0.21),
    "31041": ("loam", 0.17), "31043": ("silt loam", 0.19),
    "31045": ("loam", 0.15), "31047": ("silt loam", 0.20),
    "31049": ("sandy loam", 0.13), "31051": ("silt loam", 0.19),
    "31053": ("silt loam", 0.21), "31055": ("silt loam", 0.22),
    "31057": ("sandy loam", 0.13), "31059": ("silt loam", 0.22),
    "31061": ("silt loam", 0.19), "31063": ("loam", 0.17),
    "31065": ("silt loam", 0.19), "31067": ("silt loam", 0.22),
    "31069": ("sandy loam", 0.12), "31071": ("loam", 0.17),
    "31073": ("silt loam", 0.18), "31075": ("loam", 0.15),
    "31077": ("silt loam", 0.19), "31079": ("silt loam", 0.20),
    "31081": ("silt loam", 0.21), "31083": ("silt loam", 0.20),
    "31085": ("loam", 0.17), "31087": ("sandy loam", 0.13),
    "31089": ("silt loam", 0.19), "31091": ("loam", 0.16),
    "31093": ("silt loam", 0.20), "31095": ("silt loam", 0.21),
    "31097": ("silt loam", 0.22), "31099": ("silt loam", 0.20),
    "31101": ("sandy loam", 0.13), "31103": ("loam", 0.16),
    "31105": ("sandy loam", 0.11), "31107": ("silt loam", 0.19),
    "31109": ("silt loam", 0.22), "31111": ("loam", 0.17),
    "31113": ("loam", 0.16), "31115": ("loam", 0.16),
    "31117": ("loam", 0.17), "31119": ("silt loam", 0.20),
    "31121": ("silt loam", 0.20), "31123": ("sandy loam", 0.12),
    "31125": ("silt loam", 0.20), "31127": ("silt loam", 0.22),
    "31129": ("silt loam", 0.20), "31131": ("silt loam", 0.22),
    "31133": ("silt loam", 0.22), "31135": ("sandy loam", 0.13),
    "31137": ("silt loam", 0.20), "31139": ("silt loam", 0.19),
    "31141": ("silt loam", 0.21), "31143": ("silt loam", 0.21),
    "31145": ("sandy loam", 0.14), "31147": ("silt loam", 0.22),
    "31149": ("loam", 0.16), "31151": ("silt loam", 0.22),
    "31153": ("silt loam", 0.22), "31155": ("silt loam", 0.22),
    "31157": ("sandy loam", 0.11), "31159": ("silt loam", 0.22),
    "31161": ("loam", 0.15), "31163": ("loam", 0.17),
    "31165": ("sandy loam", 0.11), "31167": ("silt loam", 0.20),
    "31169": ("silt loam", 0.21), "31171": ("loam", 0.16),
    "31173": ("silt loam", 0.20), "31175": ("loam", 0.17),
    "31177": ("silt loam", 0.22), "31179": ("silt loam", 0.19),
    "31181": ("silt loam", 0.20), "31183": ("silt loam", 0.19),
    "31185": ("silt loam", 0.21),
    "19001": ("silt loam", 0.21), "19003": ("silt loam", 0.21),
    "19005": ("loam", 0.18), "19007": ("silt loam", 0.21),
    "19009": ("silt loam", 0.20), "19011": ("silt loam", 0.22),
    "19013": ("silt loam", 0.22), "19015": ("silt loam", 0.21),
    "19017": ("silt loam", 0.21), "19019": ("silt loam", 0.22),
    "19021": ("silt loam", 0.20), "19023": ("silt loam", 0.21),
    "19025": ("silt loam", 0.20), "19027": ("silt loam", 0.20),
    "19029": ("silt loam", 0.20), "19031": ("silt loam", 0.22),
    "19033": ("silt loam", 0.21), "19035": ("silt loam", 0.20),
    "19037": ("silt loam", 0.21), "19039": ("silt loam", 0.21),
    "19041": ("silt loam", 0.20), "19043": ("silt loam", 0.22),
    "19045": ("silt loam", 0.22), "19047": ("silt loam", 0.20),
    "19049": ("silt loam", 0.21), "19051": ("silt loam", 0.21),
    "19053": ("silt loam", 0.21), "19055": ("silt loam", 0.22),
    "19057": ("silt loam", 0.22), "19059": ("silt loam", 0.20),
    "19061": ("silt loam", 0.22), "19063": ("silt loam", 0.20),
    "19065": ("silt loam", 0.21), "19067": ("silt loam", 0.20),
    "19069": ("silt loam", 0.21), "19071": ("silt loam", 0.22),
    "19073": ("silt loam", 0.21), "19075": ("silt loam", 0.21),
    "19077": ("silt loam", 0.21), "19079": ("silt loam", 0.20),
    "19081": ("silt loam", 0.20), "19083": ("silt loam", 0.21),
    "19085": ("silt loam", 0.20), "19087": ("silt loam", 0.22),
    "19089": ("silt loam", 0.21), "19091": ("silt loam", 0.20),
    "19093": ("silt loam", 0.20), "19095": ("silt loam", 0.21),
    "19097": ("silt loam", 0.22), "19099": ("silt loam", 0.21),
    "19101": ("silt loam", 0.22), "19103": ("silt loam", 0.22),
    "19105": ("silt loam", 0.22), "19107": ("silt loam", 0.21),
    "19109": ("silt loam", 0.20), "19111": ("silt loam", 0.22),
    "19113": ("silt loam", 0.22), "19115": ("silt loam", 0.22),
    "19117": ("silt loam", 0.21), "19119": ("silt loam", 0.21),
    "19121": ("silt loam", 0.21), "19123": ("silt loam", 0.21),
    "19125": ("silt loam", 0.22), "19127": ("silt loam", 0.21),
    "19129": ("silt loam", 0.20), "19131": ("silt loam", 0.20),
    "19133": ("silt loam", 0.21), "19135": ("silt loam", 0.21),
    "19137": ("silt loam", 0.22), "19139": ("silt loam", 0.20),
    "19141": ("silt loam", 0.20), "19143": ("silt loam", 0.21),
    "19145": ("silt loam", 0.20), "19147": ("silt loam", 0.20),
    "19149": ("silt loam", 0.20), "19151": ("silt loam", 0.22),
    "19153": ("silt loam", 0.21), "19155": ("silt loam", 0.21),
    "19157": ("silt loam", 0.21), "19159": ("silt loam", 0.20),
    "19161": ("silt loam", 0.22), "19163": ("silt loam", 0.20),
    "19165": ("silt loam", 0.20), "19167": ("silt loam", 0.22),
    "19169": ("silt loam", 0.22), "19171": ("silt loam", 0.21),
    "19173": ("silt loam", 0.21), "19175": ("silt loam", 0.22),
    "19177": ("silt loam", 0.21), "19179": ("silt loam", 0.21),
    "19181": ("silt loam", 0.22), "19183": ("silt loam", 0.21),
    "19185": ("silt loam", 0.20), "19187": ("silt loam", 0.20),
    "19189": ("silt loam", 0.21), "19191": ("silt loam", 0.20),
    "19193": ("silt loam", 0.20), "19195": ("silt loam", 0.20),
    "19197": ("silt loam", 0.20),
    "20001": ("silt loam", 0.19), "20003": ("silt loam", 0.19),
    "20005": ("silt loam", 0.20), "20007": ("sandy loam", 0.11),
    "20009": ("silt loam", 0.17), "20011": ("silt loam", 0.19),
    "20013": ("silt loam", 0.19), "20015": ("silt loam", 0.18),
    "20017": ("silt loam", 0.18), "20019": ("silt loam", 0.18),
    "20021": ("silt loam", 0.17), "20023": ("loam", 0.14),
    "20025": ("sandy loam", 0.11), "20027": ("silt loam", 0.18),
    "20029": ("silt loam", 0.18), "20031": ("silt loam", 0.19),
    "20033": ("sandy loam", 0.12), "20035": ("silt loam", 0.18),
    "20037": ("silt loam", 0.17), "20039": ("loam", 0.15),
    "20041": ("silt loam", 0.18), "20043": ("silt loam", 0.19),
    "20045": ("silt loam", 0.19), "20047": ("sandy loam", 0.12),
    "20049": ("silt loam", 0.18), "20051": ("silt loam", 0.17),
    "20053": ("silt loam", 0.17), "20055": ("sandy loam", 0.12),
    "20057": ("sandy loam", 0.12), "20059": ("silt loam", 0.19),
    "20061": ("silt loam", 0.18), "20063": ("loam", 0.15),
    "20065": ("loam", 0.15), "20067": ("sandy loam", 0.11),
    "20069": ("sandy loam", 0.12), "20071": ("loam", 0.14),
    "20073": ("silt loam", 0.18), "20075": ("loam", 0.14),
    "20077": ("sandy loam", 0.12), "20079": ("silt loam", 0.18),
    "20081": ("sandy loam", 0.12), "20083": ("sandy loam", 0.12),
    "20085": ("silt loam", 0.19), "20087": ("silt loam", 0.19),
    "20089": ("silt loam", 0.17), "20091": ("silt loam", 0.19),
    "20093": ("sandy loam", 0.12), "20095": ("sandy loam", 0.12),
    "20097": ("sandy loam", 0.12), "20099": ("silt loam", 0.17),
    "20101": ("loam", 0.15), "20103": ("silt loam", 0.20),
    "20105": ("silt loam", 0.17), "20107": ("silt loam", 0.19),
    "20109": ("loam", 0.14), "20111": ("silt loam", 0.18),
    "20113": ("silt loam", 0.18), "20115": ("silt loam", 0.18),
    "20117": ("silt loam", 0.18), "20119": ("sandy loam", 0.12),
    "20121": ("silt loam", 0.19), "20123": ("silt loam", 0.17),
    "20125": ("silt loam", 0.17), "20127": ("silt loam", 0.18),
    "20129": ("sandy loam", 0.11), "20131": ("silt loam", 0.19),
    "20133": ("silt loam", 0.17), "20135": ("sandy loam", 0.13),
    "20137": ("loam", 0.15), "20139": ("silt loam", 0.19),
    "20141": ("silt loam", 0.17), "20143": ("silt loam", 0.17),
    "20145": ("sandy loam", 0.13), "20147": ("loam", 0.15),
    "20149": ("silt loam", 0.18), "20151": ("sandy loam", 0.13),
    "20153": ("loam", 0.15), "20155": ("silt loam", 0.18),
    "20157": ("silt loam", 0.17), "20159": ("silt loam", 0.17),
    "20161": ("silt loam", 0.18), "20163": ("loam", 0.15),
    "20165": ("sandy loam", 0.13), "20167": ("loam", 0.15),
    "20169": ("silt loam", 0.18), "20171": ("loam", 0.15),
    "20173": ("silt loam", 0.18), "20175": ("sandy loam", 0.11),
    "20177": ("silt loam", 0.19), "20179": ("loam", 0.15),
    "20181": ("loam", 0.14), "20183": ("loam", 0.15),
    "20185": ("sandy loam", 0.13), "20187": ("sandy loam", 0.11),
    "20189": ("sandy loam", 0.11), "20191": ("silt loam", 0.18),
    "20193": ("loam", 0.14), "20195": ("sandy loam", 0.13),
    "20197": ("silt loam", 0.18), "20199": ("loam", 0.14),
    "20201": ("silt loam", 0.18), "20203": ("loam", 0.14),
    "20205": ("silt loam", 0.17), "20207": ("silt loam", 0.18),
    "20209": ("silt loam", 0.19),
}


# --------------------------------------------------------------------------
# NY real-soil snapshot — captured 2026-08-18 from SSURGO via SoilWeb (UC
# Davis) at each county's centroid. texture = dominant map-unit texture;
# awc = Available Water Storage (0-100cm) / 100, in in/in. Counties whose
# dominant map unit has no simple texture class (rocky complexes, urban land,
# water, unsampled endpoints) fall back to STATE_DEFAULTS below. 41 of 62 NY
# counties have real values; the rest keep ("silt loam", 0.18). Refresh
# live via refresh_county_soils().
# --------------------------------------------------------------------------
NY_COUNTY_SSURGO: dict[str, tuple[str, float]] = {
    "36001": ("silt loam", 0.1633),  # Albany
    "36003": ("gravelly silt loam", 0.1264),  # Allegany
    "36011": ("loam", 0.1349),  # Cayuga
    "36013": ("silt loam", 0.1705),  # Chautauqua
    "36015": ("gravelly silt loam", 0.0981),  # Chemung
    "36017": ("channery silt loam", 0.0775),  # Chenango
    "36019": ("loamy fine sand", 0.0630),  # Clinton
    "36021": ("channery silt loam", 0.0446),  # Columbia
    "36023": ("channery silt loam", 0.0825),  # Cortland
    "36029": ("silt loam", 0.1183),  # Erie
    "36037": ("mucky very fine sandy loam", 0.1616),  # Genesee
    "36039": ("silt loam", 0.0768),  # Greene
    "36041": ("fine sandy loam", 0.1322),  # Hamilton
    "36045": ("silty clay", 0.1420),  # Jefferson
    "36047": ("sandy loam", 0.1563),  # Kings
    "36049": ("loam", 0.1420),  # Lewis
    "36053": ("mucky silt loam", 0.1590),  # Madison
    "36055": ("silt loam", 0.1439),  # Monroe
    "36057": ("silt loam", 0.0842),  # Montgomery
    "36059": ("silt loam", 0.2008),  # Nassau
    "36063": ("silt loam", 0.1470),  # Niagara
    "36067": ("silt loam", 0.1854),  # Onondaga
    "36069": ("loam", 0.1378),  # Ontario
    "36071": ("gravelly silt loam", 0.0975),  # Orange
    "36073": ("silt loam", 0.1470),  # Orleans
    "36075": ("gravelly fine sandy loam", 0.0775),  # Oswego
    "36083": ("very stony loam", 0.1358),  # Rensselaer
    "36085": ("gravelly sandy loam", 0.0763),  # Richmond
    "36091": ("fine sandy loam", 0.1059),  # Saratoga
    "36097": ("gravelly silt loam", 0.1110),  # Schuyler
    "36099": ("silt", 0.1341),  # Seneca
    "36101": ("channery silt loam", 0.0775),  # Steuben
    "36103": ("loam", 0.0998),  # Suffolk
    "36105": ("muck", 0.4000),  # Sullivan
    "36107": ("flaggy silt loam", 0.1210),  # Tioga
    "36109": ("channery silt loam", 0.1071),  # Tompkins
    "36111": ("gravelly loam", 0.0500),  # Ulster
    "36115": ("silty clay loam", 0.1099),  # Washington
    "36117": ("gravelly loam", 0.1297),  # Wayne
    "36121": ("channery silt loam", 0.0911),  # Wyoming
    "36123": ("channery silt", 0.0995),  # Yates
}

SOILWEB_MAPUNIT_URL = (
    "https://casoilresource.lawr.ucdavis.edu/gmap/get_mapunit_data.php"
    "?lat={lat}&lon={lon}"
)
_TEXTURE_VOCAB = (
    "loam", "loamy", "sand", "sandy", "silt", "silty", "clay", "clayey",
    "muck", "mucky", "fine", "coarse", "gravelly", "very", "extremely",
    "stony", "cobbly", "channery", "shaly", "flaggy", "mottled",
)
_TEXTURE_TOKEN_RE = re.compile(
    "|".join(r"\b" + w + r"\b" for w in _TEXTURE_VOCAB), re.IGNORECASE
)
_TEXTURE_BASE_RE = re.compile(r"\b(loam|sand|clay|silt|muck)\w*\s*$", re.IGNORECASE)
_AWS_RE = re.compile(
    r"Available Water Storage \(0-100cm\):.*?([\d.]+)\s*cm", re.DOTALL | re.IGNORECASE
)


def _texture_from_map_unit(mu_name: str | None) -> str | None:
    """Pull the dominant texture phrase from an SSURGO map-unit name.

    Example: "Hudson silt loam, 2 to 6 percent slopes (HuB)" -> "silt loam".
    Returns None for units with no simple texture class (urban land, rock
    outcrop, water, organic complexes we cannot name).
    """
    if not mu_name:
        return None
    body = mu_name.split("(")[0]
    body = re.sub(
        r",?\s*\d+(?:\.\d+)?\s*to\s*\d+(?:\.\d+)?\s*percent slopes?\s*",
        " ",
        body,
    )
    body = re.sub(r"\s+", " ", body).strip()
    tokens = body.split()
    runs: list[str] = []
    i = 0
    while i < len(tokens):
        if _TEXTURE_TOKEN_RE.match(tokens[i]):
            j = i
            while j < len(tokens) and _TEXTURE_TOKEN_RE.match(tokens[j]):
                j += 1
            runs.append(" ".join(tokens[i:j]).lower())
            i = j
        else:
            i += 1
    for phrase in reversed(runs):
        if _TEXTURE_BASE_RE.search(phrase):
            return phrase
    return None


def fetch_soilweb_soil(lat: float, lon: float) -> tuple[str | None, float | None]:
    """Live SSURGO dominant-soil lookup at a point via SoilWeb.

    Returns (texture, awc in in/in) or (None, None) when the endpoint is
    unreachable or the dominant map unit has no parseable texture.
    """
    import httpx

    url = SOILWEB_MAPUNIT_URL.format(lat=lat, lon=lon)
    try:
        html = httpx.get(url, timeout=30).text
    except httpx.HTTPError:
        return None, None
    m = re.search(r'class="mu-name">([^<]+)</span>', html)
    if not m:
        return None, None
    texture = _texture_from_map_unit(m.group(1).strip())
    aws = _AWS_RE.search(html)
    awc = round(float(aws.group(1)) / 100.0, 4) if aws else None
    return (texture, awc) if texture else (None, None)


def refresh_county_soils(session: Session, states: list[str] | None = None) -> int:
    """Live-refresh the soils table from SSURGO for the counties in `states`.

    Pass states=None to refresh every county. Counties whose live lookup
    returns nothing usable keep their precomputed snapshot value.
    """
    from .counties_data import get_counties

    stmt = text("""
        INSERT INTO soils (county_fips, soil_type, awc)
        VALUES (:fips, :soil, :awc)
        ON CONFLICT (county_fips) DO UPDATE SET
            soil_type = EXCLUDED.soil_type,
            awc = EXCLUDED.awc
    """)

    count = 0
    failed = 0
    for county in get_counties():
        if states and county["state"] not in states:
            continue
        texture, awc = fetch_soilweb_soil(county["latitude"], county["longitude"])
        if texture is None or awc is None:
            failed += 1
            texture, awc = (
                NY_COUNTY_SSURGO.get(county["fips"])
                or SOIL_DATA.get(county["fips"])
                or STATE_DEFAULTS[county["state"]]
            )
        session.execute(stmt, {"fips": county["fips"], "soil": texture, "awc": awc})
        count += 1
    session.commit()
    print(f"Upserted {count} soil records (live SSURGO; {failed} fell back to snapshot)")
    return count


def load_soils(session: Session) -> int:
    from .counties_data import get_counties

    stmt = text("""
        INSERT INTO soils (county_fips, soil_type, awc)
        VALUES (:fips, :soil, :awc)
        ON CONFLICT (county_fips) DO UPDATE SET
            soil_type = EXCLUDED.soil_type,
            awc = EXCLUDED.awc
    """)

    known_fips = {
        row[0] for row in session.execute(text("SELECT fips FROM counties"))
    }
    count = 0
    for county in get_counties():
        fips = county["fips"]
        if fips not in known_fips:
            continue
        state = county["state"]
        soil_type, awc = (
            NY_COUNTY_SSURGO.get(fips)
            or SOIL_DATA.get(fips)
            or STATE_DEFAULTS[state]
        )
        session.execute(stmt, {"fips": fips, "soil": soil_type, "awc": awc})
        count += 1
    session.commit()
    print(f"Upserted {count} soil records")
    return count
