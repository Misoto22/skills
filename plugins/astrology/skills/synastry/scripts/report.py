#!/usr/bin/env python3
"""Render two resolved charts as one plain-text synastry data file.

Data only. Element balance, modality balance, stellium calls, and every other
reading are left to whoever reads the file — separating the arithmetic from the
interpretation is what keeps an inference from being filed as a measurement.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from astro_math import (
    Aspect,
    degrees_in_sign,
    dignities,
    find_aspects,
    format_degrees,
    house_of,
    is_critical,
    is_diurnal,
    lots,
    sign_of,
)

LANGUAGES = ("en", "zh")

PLANETS = (
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
)
ANGLES = ("Ascendant", "Descendant", "Imum_Coeli", "Medium_Coeli")
POINTS = (
    "Chiron",
    "Ceres",
    "Pallas",
    "Juno",
    "Vesta",
    "Lilith",
    "North_Node",
    "South_Node",
    "Vertex",
    "East_Point",
)
LOTS = (
    "Lot_of_Spirit",
    "Lot_of_Fortune",
    "Lot_of_Marriage",
    "Lot_of_Death",
    "Lot_of_Sons",
    "Lot_of_Daughters",
)

# What takes part in the synastry pass. Descendant, Imum Coeli, and the South
# Node each sit exactly opposite a body already listed, so including them would
# report every contact twice under a second name.
ASPECT_BODIES = (
    *PLANETS,
    "Chiron",
    "Ceres",
    "Pallas",
    "Juno",
    "Vesta",
    "Lilith",
    "North_Node",
    "Vertex",
    "Ascendant",
    "Medium_Coeli",
)
# Overlay is about where one person lands in another's life, so it reads the ten
# planets and the two angles rather than the whole point list.
OVERLAY_BODIES = (*PLANETS, "Ascendant", "Medium_Coeli")

ANGLE_ABBREVIATIONS: Mapping[str, str] = {
    "Ascendant": "Asc",
    "Descendant": "Dsc",
    "Imum_Coeli": "IC",
    "Medium_Coeli": "MC",
}

GLYPHS: Mapping[str, str] = {
    "Sun": "☉",
    "Moon": "☽",
    "Mercury": "☿",
    "Venus": "♀",
    "Mars": "♂",
    "Jupiter": "♃",
    "Saturn": "♄",
    "Uranus": "♅",
    "Neptune": "♆",
    "Pluto": "♇",
    "Chiron": "⚷",
    "Ceres": "⚳",
    "Pallas": "⚴",
    "Juno": "⚶",
    "Vesta": "⚵",
    "Lilith": "⚸",
    "North_Node": "☊",
    "South_Node": "☋",
}

SIGN_GLYPHS: Mapping[str, str] = {
    "Ari": "♈",
    "Tau": "♉",
    "Gem": "♊",
    "Can": "♋",
    "Leo": "♌",
    "Vir": "♍",
    "Lib": "♎",
    "Sco": "♏",
    "Sag": "♐",
    "Cap": "♑",
    "Aqu": "♒",
    "Pis": "♓",
}

SIGN_NAMES: Mapping[str, Mapping[str, str]] = {
    "en": {
        "Ari": "Aries",
        "Tau": "Taurus",
        "Gem": "Gemini",
        "Can": "Cancer",
        "Leo": "Leo",
        "Vir": "Virgo",
        "Lib": "Libra",
        "Sco": "Scorpio",
        "Sag": "Sagittarius",
        "Cap": "Capricorn",
        "Aqu": "Aquarius",
        "Pis": "Pisces",
    },
    "zh": {
        "Ari": "白羊",
        "Tau": "金牛",
        "Gem": "双子",
        "Can": "巨蟹",
        "Leo": "狮子",
        "Vir": "处女",
        "Lib": "天秤",
        "Sco": "天蝎",
        "Sag": "射手",
        "Cap": "摩羯",
        "Aqu": "水瓶",
        "Pis": "双鱼",
    },
}

BODY_NAMES: Mapping[str, Mapping[str, str]] = {
    "en": {
        "Sun": "Sun",
        "Moon": "Moon",
        "Mercury": "Mercury",
        "Venus": "Venus",
        "Mars": "Mars",
        "Jupiter": "Jupiter",
        "Saturn": "Saturn",
        "Uranus": "Uranus",
        "Neptune": "Neptune",
        "Pluto": "Pluto",
        "Chiron": "Chiron",
        "Ceres": "Ceres",
        "Pallas": "Pallas",
        "Juno": "Juno",
        "Vesta": "Vesta",
        "Lilith": "Lilith",
        "North_Node": "North Node",
        "South_Node": "South Node",
        "Vertex": "Vertex",
        "East_Point": "East Point",
        "Ascendant": "Ascendant",
        "Descendant": "Descendant",
        "Imum_Coeli": "Imum Coeli",
        "Medium_Coeli": "Midheaven",
        "Lot_of_Spirit": "Lot of Spirit",
        "Lot_of_Fortune": "Lot of Fortune",
        "Lot_of_Marriage": "Lot of Marriage",
        "Lot_of_Death": "Lot of Death",
        "Lot_of_Sons": "Lot of Sons",
        "Lot_of_Daughters": "Lot of Daughters",
    },
    "zh": {
        "Sun": "太阳",
        "Moon": "月亮",
        "Mercury": "水星",
        "Venus": "金星",
        "Mars": "火星",
        "Jupiter": "木星",
        "Saturn": "土星",
        "Uranus": "天王星",
        "Neptune": "海王星",
        "Pluto": "冥王星",
        "Chiron": "凯龙星",
        "Ceres": "谷神星",
        "Pallas": "智神星",
        "Juno": "婚神星",
        "Vesta": "灶神星",
        "Lilith": "莉莉丝",
        "North_Node": "北交点",
        "South_Node": "南交点",
        "Vertex": "宿命点",
        "East_Point": "东方点",
        "Ascendant": "上升",
        "Descendant": "下降",
        "Imum_Coeli": "天底",
        "Medium_Coeli": "天顶",
        "Lot_of_Spirit": "精神点",
        "Lot_of_Fortune": "福点",
        "Lot_of_Marriage": "婚姻点",
        "Lot_of_Death": "死亡点",
        "Lot_of_Sons": "儿子点",
        "Lot_of_Daughters": "女儿点",
    },
}

ASPECT_NAMES: Mapping[str, Mapping[str, str]] = {
    "en": {
        "conjunction": "conjunction",
        "opposition": "opposition",
        "trine": "trine",
        "square": "square",
        "sextile": "sextile",
        "semi-sextile": "semi-sextile",
        "semi-square": "semi-square",
        "quintile": "quintile",
        "sesquiquadrate": "sesquiquadrate",
        "biquintile": "biquintile",
        "quincunx": "quincunx",
    },
    "zh": {
        "conjunction": "合",
        "opposition": "冲",
        "trine": "拱",
        "square": "刑",
        "sextile": "六合",
        "semi-sextile": "十二分相",
        "semi-square": "半刑",
        "quintile": "五分相",
        "sesquiquadrate": "补八分相",
        "biquintile": "倍五分相",
        "quincunx": "梅花",
    },
}

STATE_NAMES: Mapping[str, Mapping[str, str]] = {
    "en": {
        "domicile": "domicile",
        "exaltation": "exaltation",
        "detriment": "detriment",
        "fall": "fall",
        "retrograde": "retrograde",
        "critical": "critical degree",
    },
    "zh": {
        "domicile": "入庙",
        "exaltation": "入旺",
        "detriment": "陷落",
        "fall": "入弱",
        "retrograde": "逆行",
        "critical": "临界度数",
    },
}

TEXT: Mapping[str, Mapping[str, str]] = {
    "en": {
        "title": "Natal charts and synastry data",
        "engine": "Engine",
        "houses": "House system",
        "note_header": "Data only. Element balance, modality balance, and stellium calls are the reader's.",
        "natal": "Natal chart",
        "basics": "Birth data",
        "birth_time": "Local birth time",
        "birth_place": "Birth place",
        "residence": "Current residence",
        "timezone": "Time zone",
        "utc_offset": "UTC offset",
        "coordinates": "Coordinates",
        "big_three": "Big three",
        "planets": "Planets",
        "angles": "Angles",
        "points": "Asteroids and sensitive points",
        "unavailable": "Not resolved, ephemeris data file missing",
        "lots": "Classical lots",
        "sect": "Sect",
        "diurnal": "diurnal formulas",
        "nocturnal": "nocturnal formulas",
        "cusps": "House cusps",
        "occupants": "House occupants",
        "empty": "empty",
        "synastry": "Synastry",
        "aspects": "Cross-chart aspects, tightest orb first",
        "orb_note": "Ptolemaic aspects within {major}°, minor aspects within {minor}°.",
        "count": "{count} aspects",
        "overlays": "House overlays",
        "overlay_into": "{source} bodies falling in the houses of {target}",
        "column_body": "Body",
        "column_sign": "Sign",
        "column_degree": "Degree",
        "column_house": "House",
        "column_state": "State",
        "column_aspect": "Aspect",
        "column_orb": "Orb",
        "house_short": "H{number}",
        "end": "End of data",
    },
    "zh": {
        "title": "本命星盘与合盘数据",
        "engine": "计算引擎",
        "houses": "宫位系统",
        "note_header": "本文件只是数据。元素分布、三态分布、stellium 标记由读者另行判断。",
        "natal": "本命盘",
        "basics": "出生信息",
        "birth_time": "当地出生时间",
        "birth_place": "出生地",
        "residence": "现居地",
        "timezone": "时区",
        "utc_offset": "与 UTC 偏移",
        "coordinates": "经纬度",
        "big_three": "三大要素",
        "planets": "十大行星",
        "angles": "四大尖轴",
        "points": "小行星与敏感点",
        "unavailable": "未能解析 · 缺少星历数据文件",
        "lots": "阿拉伯点",
        "sect": "昼夜",
        "diurnal": "日生盘公式",
        "nocturnal": "夜生盘公式",
        "cusps": "十二宫宫头",
        "occupants": "宫位天体分布",
        "empty": "空",
        "synastry": "合盘",
        "aspects": "合盘相位 · 按 orb 由紧到松",
        "orb_note": "主相位容许 {major}°、次相位容许 {minor}°。",
        "count": "共 {count} 条",
        "overlays": "宫位互入",
        "overlay_into": "{source} 的天体落入 {target} 的宫位",
        "column_body": "天体",
        "column_sign": "星座",
        "column_degree": "度数",
        "column_house": "宫位",
        "column_state": "状态",
        "column_aspect": "相位",
        "column_orb": "orb",
        "house_short": "{number} 宫",
        "end": "数据结束",
    },
}

RULE = "=" * 72


def display_width(text: str) -> int:
    """Terminal columns a string occupies, counting a wide character as two."""

    return sum(2 if _is_wide(character) else 1 for character in text)


def _is_wide(character: str) -> bool:
    code = ord(character)
    return (
        0x1100 <= code <= 0x115F
        or 0x2E80 <= code <= 0xA4CF
        or 0xAC00 <= code <= 0xD7A3
        or 0xF900 <= code <= 0xFAFF
        or 0xFE30 <= code <= 0xFE6F
        or 0xFF00 <= code <= 0xFF60
        or 0xFFE0 <= code <= 0xFFE6
    )


def pad(text: str, width: int) -> str:
    return text + " " * max(0, width - display_width(text))


def render(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    language: str = "en",
    major_orb: float = 8.0,
    minor_orb: float = 3.0,
    engine: str = "Swiss Ephemeris",
) -> str:
    """Render both natal blocks and the synastry block as one document."""

    if language not in LANGUAGES:
        raise ValueError(f"language must be one of {list(LANGUAGES)}; got {language!r}")
    words = TEXT[language]
    lines = [
        RULE,
        f"  {words['title']}: {left['name']} x {right['name']}",
        RULE,
        f"  {words['engine']}: {engine}",
        f"  {words['houses']}: {left['house_system']}",
        f"  {words['note_header']}",
        "",
    ]
    for chart in (left, right):
        lines.extend(natal_block(chart, language=language))
    lines.extend(synastry_block(left, right, language=language, major_orb=major_orb, minor_orb=minor_orb))
    lines.extend([RULE, f"  {words['end']}", RULE, ""])
    return "\n".join(lines)


def natal_block(chart: Mapping[str, Any], *, language: str) -> list[str]:
    """One person's chart: birth data, placements, cusps, and occupants."""

    words = TEXT[language]
    longitudes: Mapping[str, float] = chart["longitudes"]
    cusps: Sequence[float] = chart["cusps"]
    retrograde = set(chart.get("retrograde", ()))
    label = _labeller(language)

    lines = [RULE, f"  {words['natal']}: {chart['name']}", RULE, "", f"■ {words['basics']}"]
    for key, value in (
        ("birth_time", chart["birth_local"]),
        ("birth_place", chart["birth_place"]),
        ("residence", chart.get("residence", "-")),
        ("timezone", chart["timezone"]),
        ("utc_offset", f"{chart['utc_offset_hours']:+.2f} h"),
        ("coordinates", f"{chart['latitude']:.4f}, {chart['longitude']:.4f}"),
    ):
        lines.append(f"  {pad(words[key], 20)}{value}")

    lines += ["", f"■ {words['big_three']}"]
    for body in ("Sun", "Moon", "Ascendant"):
        lines.append(f"  {pad(label(body), 14)}{_placement(longitudes[body], cusps, language)}")

    lines += ["", f"■ {words['planets']}", _planet_header(language), "  " + "-" * 66]
    for body in PLANETS:
        lines.append(_planet_row(body, longitudes[body], cusps, body in retrograde, language))

    lines += ["", f"■ {words['angles']}"]
    for body in ANGLES:
        placement = _placement(longitudes[body], cusps, language)
        lines.append(f"  {pad(ANGLE_ABBREVIATIONS[body], 5)}{pad(label(body), 12)}{placement}")

    lines += ["", f"■ {words['points']}"]
    for body in POINTS:
        if body not in longitudes:
            continue
        placement = _placement(longitudes[body], cusps, language)
        lines.append(f"  {pad(GLYPHS.get(body, ' '), 2)}{pad(label(body), 14)}{placement}")

    # An omission has to be stated. A body absent without a line reads as a body
    # with nothing to report, which is the opposite of what happened.
    unavailable = list(chart.get("unavailable", ()))
    if unavailable:
        joiner = "、" if language == "zh" else ", "
        lines.append(f"  {words['unavailable']}: {joiner.join(label(body) for body in unavailable)}")

    diurnal = is_diurnal(longitudes["Sun"], cusps)
    computed = lots(
        ascendant=longitudes["Ascendant"],
        sun=longitudes["Sun"],
        moon=longitudes["Moon"],
        venus=longitudes["Venus"],
        jupiter=longitudes["Jupiter"],
        saturn=longitudes["Saturn"],
        diurnal=diurnal,
    )
    lines += ["", f"■ {words['lots']}"]
    for name in LOTS:
        lines.append(f"  {pad(label(name), 18)}{_placement(computed[name], cusps, language)}")
    lines.append(f"  ({words['sect']}: {words['diurnal'] if diurnal else words['nocturnal']})")

    lines += ["", f"■ {words['cusps']}"]
    for number, cusp in enumerate(cusps, start=1):
        house = words["house_short"].format(number=number)
        lines.append(f"  {pad(house, 8)}{_sign_and_degree(cusp, language)}")

    lines += ["", f"■ {words['occupants']}"]
    joiner = "、" if language == "zh" else ", "
    for number, occupants in enumerate(_occupants(longitudes, cusps, language), start=1):
        house = words["house_short"].format(number=number)
        lines.append(f"  {pad(house, 8)}{joiner.join(occupants) or words['empty']}")

    lines.append("")
    return lines


def synastry_block(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    language: str,
    major_orb: float,
    minor_orb: float,
) -> list[str]:
    """Cross-chart aspects, then both directions of house overlay."""

    words = TEXT[language]
    label = _labeller(language)
    aspects = find_aspects(
        _aspect_set(left["longitudes"]),
        _aspect_set(right["longitudes"]),
        major_orb=major_orb,
        minor_orb=minor_orb,
    )

    lines = [
        RULE,
        f"  {words['synastry']}: {left['name']} x {right['name']}",
        RULE,
        "",
        f"■ {words['aspects']}",
        f"  {words['orb_note'].format(major=major_orb, minor=minor_orb)}",
        "",
        "  "
        + pad(f"{left['name']} {words['column_body']}", 20)
        + pad(words["column_aspect"], 18)
        + pad(f"{right['name']} {words['column_body']}", 20)
        + words["column_orb"],
        "  " + "-" * 66,
    ]
    lines.extend(_aspect_row(aspect, label, language) for aspect in aspects)
    lines += ["", f"  {words['count'].format(count=len(aspects))}", "", f"■ {words['overlays']}"]

    for source, target in ((right, left), (left, right)):
        lines += ["", f"  {words['overlay_into'].format(source=source['name'], target=target['name'])}"]
        for body in OVERLAY_BODIES:
            longitude = source["longitudes"][body]
            house = words["house_short"].format(number=house_of(longitude, target["cusps"]))
            lines.append(
                f"    {pad(label(body), 14)}{pad(_sign_and_degree(longitude, language), 22)}→ {house}"
            )
    lines.append("")
    return lines


def _labeller(language: str) -> Callable[[str], str]:
    names = BODY_NAMES[language]
    return lambda body: names.get(body, body.replace("_", " "))


def _aspect_set(longitudes: Mapping[str, float]) -> dict[str, float]:
    return {body: longitudes[body] for body in ASPECT_BODIES if body in longitudes}


def _aspect_row(aspect: Aspect, label: Callable[[str], str], language: str) -> str:
    return (
        "  "
        + pad(label(aspect.left), 20)
        + pad(ASPECT_NAMES[language][aspect.kind], 18)
        + pad(label(aspect.right), 20)
        + f"{aspect.orb:>5.2f}°"
    )


def _planet_header(language: str) -> str:
    words = TEXT[language]
    return (
        "  "
        + pad(words["column_body"], 16)
        + pad(words["column_sign"], 14)
        + pad(words["column_degree"], 10)
        + pad(words["column_house"], 8)
        + words["column_state"]
    )


def _planet_row(
    body: str,
    longitude: float,
    cusps: Sequence[float],
    retrograde: bool,
    language: str,
) -> str:
    words = TEXT[language]
    states = [STATE_NAMES[language][state] for state in dignities(body, sign_of(longitude))]
    if retrograde:
        states.append(STATE_NAMES[language]["retrograde"])
    if is_critical(longitude):
        states.append(STATE_NAMES[language]["critical"])
    joiner = "、" if language == "zh" else ", "
    return (
        "  "
        + pad(f"{GLYPHS.get(body, ' ')} {BODY_NAMES[language].get(body, body)}", 16)
        + pad(_sign_label(longitude, language), 14)
        + pad(format_degrees(degrees_in_sign(longitude)), 10)
        + pad(words["house_short"].format(number=house_of(longitude, cusps)), 8)
        + (joiner.join(states) or "-")
    )


def _sign_label(longitude: float, language: str) -> str:
    sign = sign_of(longitude)
    return f"{SIGN_NAMES[language][sign]} {SIGN_GLYPHS[sign]}"


def _sign_and_degree(longitude: float, language: str) -> str:
    return f"{_sign_label(longitude, language)} {format_degrees(degrees_in_sign(longitude))}"


def _placement(longitude: float, cusps: Sequence[float], language: str) -> str:
    house = TEXT[language]["house_short"].format(number=house_of(longitude, cusps))
    return f"{pad(_sign_and_degree(longitude, language), 22)}{house}"


def _occupants(
    longitudes: Mapping[str, float],
    cusps: Sequence[float],
    language: str,
) -> list[list[str]]:
    """Which bodies sit in each house. Angles are excluded: an angle is a cusp, not a tenant."""

    label = _labeller(language)
    houses: list[list[str]] = [[] for _ in range(12)]
    for body in (*PLANETS, *POINTS):
        if body not in longitudes:
            continue
        houses[house_of(longitudes[body], cusps) - 1].append(label(body))
    return houses
