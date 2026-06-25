"""
Core Vedic (Jyotish) chart + Vimshottari Dasha calculation engine.
Reused/refactored from the manual scripts used to build Tarun's, his brother's,
and his son's readings earlier in this project.

Pure functions, no web framework dependencies, so this can be unit-tested
and reused from the Flask app.
"""
import datetime
import swisseph as swe

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio",
         "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu",
    "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta",
    "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha",
    "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada",
    "Uttara Bhadrapada", "Revati",
]

DASHA_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
DASHA_YEARS = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
               "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}
NAK_LORDS = (DASHA_ORDER * 3)[:27]

PLANET_IDS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN, "Rahu": swe.MEAN_NODE,
}

FLAG_SID = swe.FLG_SWIEPH | swe.FLG_SIDEREAL


def _sign_deg(lon_deg):
    lon_deg = lon_deg % 360
    idx = int(lon_deg // 30)
    return SIGNS[idx], lon_deg % 30, idx


def _nak_info(lon_deg):
    lon_deg = lon_deg % 360
    seg = 360 / 27.0
    idx = int(lon_deg // seg)
    rem = lon_deg % seg
    pada = int(rem // (seg / 4)) + 1
    return NAKSHATRAS[idx], pada, idx, NAK_LORDS[idx]


def compute_natal_chart(year, month, day, hour, minute, utc_offset_hours, lat, lon):
    """
    hour/minute = local birth time (24h). utc_offset_hours = e.g. 5.5 for IST.
    Returns dict with per-planet sign/house/nakshatra info, ascendant, and
    whole-sign house-of-planet mapping.
    """
    local_hour = hour + minute / 60.0
    utc_hour = local_hour - utc_offset_hours
    jd = swe.julday(year, month, day, utc_hour)

    swe.set_sid_mode(swe.SIDM_LAHIRI)

    natal = {}
    for name, pid in PLANET_IDS.items():
        xx, _ = swe.calc_ut(jd, pid, FLAG_SID)
        lon_p, speed = xx[0], xx[3]
        sign, deg, sidx = _sign_deg(lon_p)
        nak, pada, nidx, nlord = _nak_info(lon_p)
        natal[name] = {"lon": round(lon_p, 4), "sign": sign, "deg": round(deg, 2),
                        "nak": nak, "pada": pada, "nak_lord": nlord, "retro": speed < 0}

    rahu_lon = natal["Rahu"]["lon"]
    ketu_lon = (rahu_lon + 180) % 360
    sign, deg, sidx = _sign_deg(ketu_lon)
    nak, pada, nidx, nlord = _nak_info(ketu_lon)
    natal["Ketu"] = {"lon": round(ketu_lon, 4), "sign": sign, "deg": round(deg, 2),
                      "nak": nak, "pada": pada, "nak_lord": nlord, "retro": True}

    cusps, ascmc = swe.houses_ex(jd, lat, lon, b"P", flags=swe.FLG_SIDEREAL)
    asc_lon = ascmc[0]
    asign, adeg, aidx = _sign_deg(asc_lon)
    anak, apada, anidx, anlord = _nak_info(asc_lon)
    ascendant = {"lon": round(asc_lon, 4), "sign": asign, "deg": round(adeg, 2),
                 "nak": anak, "pada": apada}

    houses = {}
    for name, info in natal.items():
        psidx = SIGNS.index(info["sign"])
        houses[name] = (psidx - aidx) % 12 + 1

    return {
        "jd": jd,
        "ascendant": ascendant,
        "lagna_sign": asign,
        "lagna_idx": aidx,
        "planets": natal,
        "houses": houses,
        "moon_lon": natal["Moon"]["lon"],
    }


def _add_years(d, years):
    return d + datetime.timedelta(days=years * 365.2425)


def vimshottari_dasha(birth_date, moon_lon, levels=3, today=None, years_ahead=20):
    """
    Returns the current Mahadasha / Antardasha / Pratyantardasha (if levels>=3)
    active as of `today` (default: today's date), plus the full Mahadasha
    timeline for reference.
    """
    if today is None:
        today = datetime.date.today()

    nak_size = 360 / 27.0
    nak_idx = int(moon_lon // nak_size)
    frac_elapsed = (moon_lon % nak_size) / nak_size
    start_lord = NAK_LORDS[nak_idx]
    total = DASHA_YEARS[start_lord]
    balance = (1 - frac_elapsed) * total

    md_list = []
    cur = birth_date
    first_end = _add_years(birth_date, balance)
    md_list.append((start_lord, birth_date, first_end))
    cur = first_end
    idx0 = DASHA_ORDER.index(start_lord)
    full_order = DASHA_ORDER[idx0 + 1:] + DASHA_ORDER[:idx0 + 1]
    for _ in range(8):
        for p in full_order:
            nxt = _add_years(cur, DASHA_YEARS[p])
            md_list.append((p, cur, nxt))
            cur = nxt

    current_md = next((m for m in md_list if m[1] <= today < m[2]), md_list[-1])

    result = {"mahadasha": {"lord": current_md[0], "start": current_md[1], "end": current_md[2]}}

    if levels >= 2:
        p_md, md_start, md_end = current_md
        md_total = DASHA_YEARS[p_md]
        idx_md = DASHA_ORDER.index(p_md)
        ad_seq = DASHA_ORDER[idx_md:] + DASHA_ORDER[:idx_md]
        cur = md_start
        current_ad = None
        for p in ad_seq:
            length = md_total * DASHA_YEARS[p] / 120.0
            nxt = _add_years(cur, length)
            if cur <= today < nxt:
                current_ad = (p, cur, nxt)
            cur = nxt
        if current_ad is None:
            current_ad = (p_md, md_start, md_end)
        result["antardasha"] = {"lord": current_ad[0], "start": current_ad[1], "end": current_ad[2]}

        if levels >= 3:
            p_ad, ad_start, ad_end = current_ad
            ad_days = (ad_end - ad_start).days
            idx_ad = DASHA_ORDER.index(p_ad)
            pd_seq = DASHA_ORDER[idx_ad:] + DASHA_ORDER[:idx_ad]
            cur = ad_start
            current_pd = None
            for p in pd_seq:
                length_days = ad_days * DASHA_YEARS[p] / 120.0
                nxt = cur + datetime.timedelta(days=length_days)
                if cur <= today < nxt:
                    current_pd = (p, cur, nxt)
                cur = nxt
            if current_pd is None:
                current_pd = (p_ad, ad_start, ad_end)
            result["pratyantardasha"] = {"lord": current_pd[0], "start": current_pd[1], "end": current_pd[2]}

    result["timeline"] = md_list[:12]
    return result
