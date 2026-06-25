"""
Template-based reading generator. Turns chart_engine output into readable
English prose -- a free teaser, and a fuller paid reading.

This is deliberately deterministic/template-based (not an LLM call) so it's
free to run at scale and never produces an inconsistent or off-brand result.
A natural upgrade path (noted in the go-live guide) is to send this same
structured data to the Claude API for more varied, conversational prose.
"""

HOUSE_THEMES = {
    1: "self, personality, and physical vitality",
    2: "wealth, family resources, and speech",
    3: "courage, siblings, and communication",
    4: "home, mother, property, and emotional foundation",
    5: "intelligence, creativity, and children",
    6: "daily work, routine, health, and obstacles",
    7: "partnerships, marriage, and business relationships",
    8: "transformation, shared resources, and longevity",
    9: "fortune, higher learning, father, and long journeys",
    10: "career, public standing, and life direction",
    11: "gains, income, and networks",
    12: "foreign connections, expenses, and release",
}

SIGN_TEMPERAMENT = {
    "Aries": "direct, energetic, and quick to act",
    "Taurus": "steady, comfort-seeking, and values-driven",
    "Gemini": "curious, communicative, and adaptable",
    "Cancer": "nurturing, intuitive, and protective",
    "Leo": "confident, expressive, and leadership-oriented",
    "Virgo": "analytical, precise, and service-minded",
    "Libra": "diplomatic, relationship-focused, and balance-seeking",
    "Scorpio": "intense, private, and transformation-driven",
    "Sagittarius": "optimistic, philosophical, and freedom-loving",
    "Capricorn": "disciplined, ambitious, and patient",
    "Aquarius": "independent, idea-driven, and unconventional",
    "Pisces": "imaginative, compassionate, and intuitive",
}

PLANET_CAREER_TENDENCY = {
    "Sun": "government, administration, leadership, and visible authority",
    "Moon": "public-facing, caregiving, or emotionally engaged work",
    "Mars": "engineering, defense, sports, or high-energy competitive fields",
    "Mercury": "commerce, communication, writing, IT, or analytical work",
    "Jupiter": "teaching, law, finance, consulting, or advisory roles",
    "Venus": "arts, design, luxury, beauty, or client relations",
    "Saturn": "long-term, structured, institutional, or labor-intensive fields",
    "Rahu": "unconventional, foreign-connected, or technology-driven fields",
    "Ketu": "research, niche specialization, or behind-the-scenes work",
}

PLANET_KEYWORDS = {
    "Sun": "authority, visibility, and self-expression",
    "Moon": "emotional security, intuition, and adaptability",
    "Mars": "drive, courage, and assertiveness",
    "Mercury": "intellect, communication, and analysis",
    "Jupiter": "wisdom, growth, and good fortune",
    "Venus": "harmony, relationships, and aesthetic sense",
    "Saturn": "discipline, responsibility, and long-term endurance",
    "Rahu": "ambition, unconventional drive, and rapid expansion",
    "Ketu": "detachment, introspection, and specialization",
}


def _ordinal(n):
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th")


def generate_teaser(chart):
    lagna_sign = chart["lagna_sign"]
    moon_sign = chart["planets"]["Moon"]["sign"]
    moon_nak = chart["planets"]["Moon"]["nak"]
    temperament = SIGN_TEMPERAMENT[lagna_sign]

    text = (
        f"Your Ascendant (Lagna) is {lagna_sign} -- this shapes a {temperament} "
        f"approach to life. Your Moon sits in {moon_sign}, in the {moon_nak} "
        f"nakshatra, which governs your emotional and intuitive nature.\n\n"
        f"This free preview only scratches the surface. Your full reading "
        f"covers your complete house-by-house chart, current planetary period "
        f"(dasha), and what it means for your career, finances, and health "
        f"right now."
    )
    return {
        "lagna_sign": lagna_sign,
        "moon_sign": moon_sign,
        "moon_nakshatra": moon_nak,
        "teaser_text": text,
    }


def _fmt_date(d):
    return d.strftime("%d %b %Y")


def generate_full_reading(chart, dasha, name="there"):
    lagna_sign = chart["lagna_sign"]
    houses = chart["houses"]
    planets = chart["planets"]

    sections = []

    # --- 1. Chart at a glance ---
    sections.append({
        "title": "Your Chart at a Glance",
        "body": (
            f"Hello {name}, your Ascendant (Lagna) is {lagna_sign}, giving you "
            f"a fundamentally {SIGN_TEMPERAMENT[lagna_sign]} approach to life. "
            f"Your Moon is in {planets['Moon']['sign']} ({planets['Moon']['nak']} "
            f"nakshatra), shaping your emotional and instinctive responses."
        ),
    })

    # --- 2. House-by-house planet placements ---
    house_to_planets = {}
    for p, h in houses.items():
        house_to_planets.setdefault(h, []).append(p)

    house_lines = []
    for h in sorted(house_to_planets.keys()):
        plist = house_to_planets[h]
        plist_str = ", ".join(plist)
        theme = HOUSE_THEMES[h]
        keywords = ", ".join(PLANET_KEYWORDS[p] for p in plist)
        house_lines.append(
            f"Your {_ordinal(h)} house ({theme}) holds {plist_str}, bringing themes of "
            f"{keywords} into this area of life."
        )
    sections.append({
        "title": "Planets in Your Houses",
        "body": " ".join(house_lines),
    })

    # --- 3. Career & money signals ---
    career_planets = house_to_planets.get(10, [])
    money_planets = house_to_planets.get(11, []) + house_to_planets.get(2, [])
    career_bits = [PLANET_CAREER_TENDENCY[p] for p in career_planets if p in PLANET_CAREER_TENDENCY]
    career_text = (
        ("Planets in your 10th house point toward " + "; ".join(career_bits) + ".")
        if career_bits else
        "Your 10th house has no planets directly in it -- look to its ruling "
        "sign's lord elsewhere in the chart for your career's deeper driver."
    )
    money_text = (
        f"Your money-related houses (2nd and 11th) contain "
        f"{', '.join(money_planets) if money_planets else 'no direct placements'}, "
        "which shapes how income and gains tend to flow for you."
    )
    sections.append({"title": "Career & Money Signals", "body": career_text + " " + money_text})

    # --- 4. Current dasha ---
    md = dasha["mahadasha"]
    ad = dasha.get("antardasha")
    pd = dasha.get("pratyantardasha")
    dasha_text = (
        f"You are currently in your {md['lord']} Mahadasha "
        f"({_fmt_date(md['start'])} to {_fmt_date(md['end'])})."
    )
    if ad:
        dasha_text += (
            f" Within that, your current Antardasha (sub-period) is {ad['lord']} "
            f"({_fmt_date(ad['start'])} to {_fmt_date(ad['end'])})."
        )
    if pd:
        dasha_text += (
            f" More precisely, the Pratyantardasha active right now is {pd['lord']} "
            f"({_fmt_date(pd['start'])} to {_fmt_date(pd['end'])})."
        )
    dasha_text += (
        f" In Vimshottari Dasha, this period brings {PLANET_KEYWORDS[md['lord']]} "
        "to the forefront of your life experience."
    )
    sections.append({"title": "Your Current Planetary Period (Dasha)", "body": dasha_text})

    # --- 5. Disclaimer ---
    sections.append({
        "title": "A Note on This Reading",
        "body": (
            "This reading is offered for reflection, entertainment, and "
            "spiritual/cultural insight, drawing on traditional Vedic "
            "(Parashari) astrology. It is not medical, legal, or financial "
            "advice, and should not replace guidance from a qualified "
            "professional in those fields."
        ),
    })

    return sections
