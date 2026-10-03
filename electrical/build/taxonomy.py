"""
Classification rules for Toyota electrical wiring diagram (EWD) circuits.

A circuit title as printed at the top of an EWD page, e.g.
    RADIATOR FAN AND AIR CONDITIONER (AUTOMATIC AIR CONDITIONER, FOR PUSH TYPE OF BLOWER CONTROL SW)
is normalized, matched to a system rule (key, display name, rail category)
and its parenthetical is parsed into a variant: engine, drive, market,
transmission, A/C type, blower-control type, cruise-control type, options.
"""
from __future__ import annotations

import re

# Rail order. Keys are stable ids used by the UI.
CATEGORIES = [
    ("reference", "Reference"),
    ("locations", "Locations"),
    ("power", "Power Distribution"),
    ("engine", "Engine Electrical"),
    ("lighting", "Lighting"),
    ("body", "Body Electrical"),
    ("instruments", "Instruments & Audio"),
    ("chassis", "Chassis & Safety"),
    ("hvac", "HVAC"),
    ("overall", "Overall Wiring"),
    ("other", "Other"),
]
CATEGORY_NAMES = dict(CATEGORIES)

# (system key, display name, category, title regex, fixed applicability)
# Matched against the normalized title with its parenthetical removed.
# First match wins.
RULES = [
    ("foreword", "Foreword", "reference", r"FOREWORD", {}),
    ("introduction", "Introduction", "reference", r"INTRODUCTION", {}),
    ("how-to-use", "How to Use This Manual", "reference", r"HOW TO USE.*", {}),
    ("troubleshooting", "Troubleshooting", "reference", r"TROUBLE ?SHOOTING", {}),
    ("abbreviations", "Abbreviations", "reference", r"ABBREVIATIONS?", {}),
    ("glossary", "Glossary of Terms and Symbols", "reference", r"GLOSSARY.*", {}),
    ("index", "Index", "reference", r"INDEX", {}),
    ("wire-harness-repair", "Wire Harness & Connector Repair", "reference",
     r"WIRE HARNESS REPAIR.*", {}),

    ("component-locator", "Electrical Component Locator", "locations",
     r"ELECTRICAL COMPONENT LOCAT(?:OR|ION)", {}),

    ("relay-locations", "Relay Locations", "locations", r"RELAY LOCATIONS?", {}),
    ("wiring-routing", "Electrical Wiring Routing", "locations",
     r"ELECTRICAL WIR(?:E|ING) ROUTING", {}),
    ("ground-points", "Ground Points", "locations", r"GROUND POINTS?", {}),

    ("power-flow", "Power Source — Current Flow Chart", "power",
     r"POWER SOURCE CURRENT FLOW CHART", {}),
    ("power-source", "Power Source (Fuses & Fusible Links)", "power",
     r"POWER SOURCE", {}),

    ("starting-ignition", "Starting & Ignition", "engine", r"STARTING AND IGNITION", {}),
    ("charging", "Charging", "engine", r"CHARGING", {}),
    ("cooling-fan", "Engine Cooling Fan", "engine", r"ENGINE COOLING FAN", {}),
    ("engine-control", "Engine Control (ECU)", "engine", r"ENGINE CONTROL", {}),
    ("ect", "ECT (Electronic Controlled Transmission)", "engine",
     r"ECT(?: ELECTRONIC(?:ALLY)? CONTROLLED TRANSMISSION)?", {"trans": ["A/T"]}),
    ("overdrive", "Overdrive", "engine", r"OVERDRIVE", {"trans": ["A/T"]}),
    ("shift-lock", "Shift Lock", "engine", r"SHIFT LOCK", {"trans": ["A/T"]}),

    ("illumination", "Illumination", "lighting", r"ILLUMINATION", {}),
    ("taillight", "Taillight", "lighting", r"TAILLIGHTS?", {}),
    ("headlight-canada", "Headlight & Fog Light (Canada)", "lighting",
     r"HEADLIGHT AND FOG LIGHT", {"market": ["CANADA"]}),
    ("headlight-usa", "Headlight (USA)", "lighting", r"HEADLIGHTS?", {}),
    ("fog-light", "Fog Light (USA)", "lighting", r"FOG LIGHTS?", {}),
    ("stop-light", "Stop Light", "lighting", r"STOP ?LIGHTS?", {}),
    ("back-up-light", "Back-Up Light", "lighting", r"BACK-?UP LIGHTS?", {}),
    ("turn-hazard", "Turn Signal & Hazard Warning", "lighting",
     r"TURN SIGNAL AND HAZARD WARNING LIGHTS?", {}),
    ("interior-light", "Interior Light", "lighting", r"INTERIOR LIGHTS?", {}),
    ("light-reminder", "Light Reminder Buzzer", "lighting", r"LIGHT REMINDER.*", {}),

    ("power-window", "Power Window", "body", r"POWER WINDOWS?", {"option": "power_window"}),
    ("door-lock", "Door Lock", "body", r"(?:POWER )?DOOR LOCK.*", {"option": "door_lock"}),
    ("rear-wiper", "Rear Wiper & Washer", "body", r"REAR WIPER AND WASHER", {}),
    ("front-wiper", "Front Wiper & Washer", "body", r"(?:FRONT )?WIPER AND WASHER", {}),
    ("unlock-seatbelt-warning", "Unlock & Seat Belt Warning", "body",
     r"UNLOCK AND SEAT BELT WARNING", {}),
    ("tension-reducer", "Electric Tension Reducer", "body",
     r"ELECTRIC TENSION REDUCER", {}),
    ("rear-defogger", "Rear Window Defogger", "body", r"REAR WINDOW DEFOGGER", {}),
    ("power-seat", "Power Seat", "body", r"POWER SEATS?", {"option": "power_seat"}),
    ("remote-mirror", "Remote Control Mirror", "body",
     r"(?:REMOTE CONTROL|POWER) MIRRORS?", {}),
    ("sun-roof", "Sun Roof", "body", r"SUN ?ROOF", {"option": "sunroof"}),
    ("auto-tilt", "Auto Tilt-Away Steering", "body", r"AUTO TILT ?AWAY STEERING", {}),
    ("top-stack", "Top Stack (Convertible Top)", "body", r"TOP STACK",
     {"body": ["CONVERTIBLE"]}),
    ("horn", "Horn", "body", r"HORNS?", {}),
    ("column-switches", "Combination Switch (Steering Column)", "body",
     r"(?:STEERING COLUMN|COMBINATION) SWITCH(?:ES)?", {}),
    ("lighter-clock", "Cigarette Lighter & Clock", "body",
     r"CIGARETTE LIGHTER AND CLOCK", {}),
    ("theft-deterrent", "Theft Deterrent", "body", r"THEFT DETERRENT.*", {}),

    ("combination-meter", "Combination Meter", "instruments", r"COMBINATION METER", {}),
    ("auto-antenna", "Auto Antenna", "instruments", r"(?:AUTO|POWER) ANTENNA", {}),
    ("radio", "Radio & Player", "instruments", r"RADIO.*", {}),

    ("cruise-control", "Cruise Control", "chassis", r"CRUISE CONTROL",
     {"option": "cruise"}),
    ("abs", "ABS (Anti-Lock Brakes)", "chassis", r"ABS.*|ANTI-?LOCK BRAKE.*",
     {"option": "abs"}),
    ("srs", "SRS Airbag", "chassis", r"SRS.*", {}),

    ("hvac-auto", "A/C & Radiator Fan — Automatic A/C", "hvac",
     r"RADIATOR FAN AND AIR CONDITIONER", {"ac": ["AUTO"]}),
    ("hvac-manual", "A/C & Radiator Fan — Manual A/C", "hvac",
     r"RADIATOR FAN AND AIR CONDITIONER", {"ac": ["MANUAL"]}),
    ("heater", "Heater (w/o A/C)", "hvac", r"HEATER.*", {"ac": ["NONE"]}),
    ("radiator-fan", "Radiator Fan (w/o A/C)", "hvac",
     r"RADIATOR FAN(?: AND CONDENSER FAN)?", {"ac": ["NONE"]}),

    ("overall-wiring", "Overall Wiring Diagram", "overall", r"OVERALL WIRING DIAGRAM.*", {}),
]
_COMPILED = [(k, n, c, re.compile(r"^(?:" + rx + r")$"), fx) for k, n, c, rx, fx in RULES]

# Repair-manual sections (celica-manual record ids) worth opening from a
# wiring circuit. The builder drops ids that are not in the repair library.
REPAIR_LINKS = {
    "starting-ignition": ["Starting_System", "Starting_System (1)",
                          "Clutch_Start_Switch_Mt_Only", "Ignition_System",
                          "Ignition_System_Circuit", "Integrated_Ignition_Assembly",
                          "Distributor", "Onvehicle_Inspection_3sgte"],
    "charging": ["Charging_System", "Generator"],
    "engine-control": ["Electronic_Control_Module_Ecm", "Diagnosis_System_3SGTE_And_5SFE",
                       "Location_Of_Electronic_Control", "Mfi_And_Sfi_Main_Relay",
                       "Circuit_Opening_Relay_3sgte", "Fuel_Pump_Relay_And_Resistor_3s",
                       "Fuel_Pump_3sgte", "Engine_Coolant_Temperature_Sens",
                       "Turbocharging_Pressure_Sensor_3", "Turbocharging_Pressure_Vsv_3sgt",
                       "Tvis_Vsv_3sgte", "Idle_Air_Control_Iac_Valve_3sgt",
                       "Cold_Start_Injector_Time_Switch", "Throttle_Body_3sgte"],
    "abs": ["Antilock_Brake_System_Circuit", "Speed_Sensor_And_Decelerationse",
            "Front_Speed_Sensor", "Control_Relay"],
    "srs": ["Seat_Belts_Components", "seatbelt"],
    "unlock-seatbelt-warning": ["Seat_Belts_Components", "seatbelt"],
    "auto-tilt": ["Auto_Tilt_Away_Steering_Column", "Tilt_Steering_Column"],
    "top-stack": ["theoryof"],
    "hvac-auto": ["Ac_Idleup_Vsv_5sfe", "Cooling_System", "T-AC002-98", "T-AC003-93",
                  "T-AC004-93", "T-AC005-92", "T-AC005-93", "TS-AC009-04"],
    "hvac-manual": ["Ac_Idleup_Vsv_5sfe", "Cooling_System", "T-AC002-98", "T-AC003-93",
                    "T-AC004-93", "T-AC005-92", "T-AC005-93", "TS-AC009-04"],
    "radiator-fan": ["Cooling_System"],
    "wiring-routing": ["Electrical_Wire_Routing", "electric"],
}

# Repair-manual sections linked by Toyota section code (all sections with that
# prefix) or by repair-app system name, so newly imported chapters link too.
REPAIR_CODE_LINKS = {
    "charging": ["CH"],
    "starting-ignition": ["ST", "IG"],
    "abs": ["AB"],
    "srs": ["SR"],
    "hvac-auto": ["AC"],
    "hvac-manual": ["AC"],
    "heater": ["AC"],
    "cooling-fan": ["CO"],
}
REPAIR_SYSTEM_LINKS = {
    "engine-control": ["Engine Diagnostics", "Engine Control (ECM)", "Engine Performance"],
    "hvac-auto": ["Air Conditioning"],
    "hvac-manual": ["Air Conditioning"],
}

# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------
_TRANS = {0x2212: "-", 0x2013: "-", 0x2014: "-", 0x2010: "-", 0x2011: "-",
          0x00A0: " ", 0x2019: "'", 0x2018: "'", 0x201C: '"', 0x201D: '"'}


def norm_text(s: str) -> str:
    return s.translate(_TRANS)


def normalize_title(raw: str) -> str:
    t = re.sub(r"\s+", " ", norm_text(raw)).strip().upper()
    t = t.replace("F0R", "FOR").replace("FOGLIGHT", "FOG LIGHT")
    t = t.replace("AIR CONDITIONING", "AIR CONDITIONER")
    t = t.replace("AUTO IR CONDITIONER", "AUTO AIR CONDITIONER")
    t = re.sub(r"^FOG LIGHT AND HEADLIGHT", "HEADLIGHT AND FOG LIGHT", t)
    t = re.sub(r"\((?:FOR )?(USA|CANADA)\)", r"(FOR \1)", t)
    t = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", t))
    return t


def split_title(title: str):
    """'ENGINE CONTROL (5S-FE A/T)' -> ('ENGINE CONTROL', '5S-FE A/T')."""
    m = re.match(r"^(.*?)\s*\((.*)\)\s*$", title)
    if m and m.group(1):
        return m.group(1).strip(), m.group(2).strip()
    return title, ""


# ---------------------------------------------------------------------------
# Variant parsing
# ---------------------------------------------------------------------------
ENGINES = ["3S-GTE", "5S-FE", "4A-FE"]
ENGINE_MODEL = {"3S-GTE": "ST185", "5S-FE": "ST184", "4A-FE": "AT180"}

_ACRONYMS = {"USA", "ABS", "CD", "ECT", "ECU", "EFI", "SRS", "SW", "LH", "RH", "A/C",
             "A/T", "M/T", "O/D", "VSV", "IG", "ACC", "INT", "J/B", "R/B", "LED",
             "CC", "ECM", "EGR", "VIN", "SST", "TDC", "ISC", "IAC", "PCV", "TCCS",
             "DLC", "OBD", "LO", "HI", "MED", "RES", "ACCY"}
_SMALL = {"OF", "AND", "FOR", "AT", "TO", "IN", "THE", "WITH", "BY", "ON", "OR"}


def _pretty_word(w: str, first: bool) -> str:
    if w in _ACRONYMS or re.search(r"\d", w):
        return w
    if w in ("W/", "W/O", "EX."):
        return w.lower().replace("ex.", "Ex.")
    if w in _SMALL and not first:
        return w.lower()
    return w[:1] + w[1:].lower()


def pretty(s: str) -> str:
    """Title-case an all-caps manual phrase, keeping acronyms/codes."""
    s = s.replace("ALL-TRAC", "All-Trac")
    out = []
    for i, w in enumerate(s.split(" ")):
        m = re.match(r"^([(\[]*)(.*?)([)\],.:;]*)$", w)
        lead, core, tail = m.groups()
        if core.upper() in ("W/", "W/O") or re.search(r"\d", core):
            out.append(lead + (core.lower() if core.upper() in ("W/", "W/O") else core) + tail)
            continue
        parts = re.split(r"([/-])", core)
        core = "".join(p if p in "/-" or "All-Trac" in p else
                       _pretty_word(p, i == 0 or bool(lead)) for p in parts) \
            if core not in _ACRONYMS else core
        out.append(lead + core + tail)
    return " ".join(out)


def parse_variant(paren: str) -> dict:
    """Applicability encoded in a title parenthetical."""
    p = paren.upper()
    v = {"engines": [e for e in ENGINES if e in p]}
    if "ALL-TRAC" in p or "4WD" in p:
        v["drive"] = ["ALL-TRAC/4WD"]
    elif "2WD" in p:
        v["drive"] = ["2WD"]
    if "CANADA" in p:
        v["market"] = ["CANADA"]
    elif "USA" in p:
        v["market"] = ["USA"]
    if re.search(r"\bA/T\b", p):
        v["trans"] = ["A/T"]
    elif re.search(r"\bM/T\b", p):
        v["trans"] = ["M/T"]
    if "AUTOMATIC AIR CONDITIONER" in p:
        v["ac"] = ["AUTO"]
    elif "MANUAL AIR CONDITIONER" in p:
        v["ac"] = ["MANUAL"]
    blower = blower_types(p)
    if blower:
        v["blower"] = blower
    if "MOTOR TYPE" in p:
        v["cruise_type"] = "motor"
    elif "VACUUM TYPE" in p:
        v["cruise_type"] = "vacuum"
    if re.search(r"\bW/O CD", p):
        v["cd"] = False
    elif re.search(r"\bW/ CD", p):
        v["cd"] = True
    return {k: val for k, val in v.items() if val not in ([], None)}


def blower_types(text: str) -> list:
    t = text.upper()
    out = []
    if re.search(r"PUSH[- ]TYPE", t):
        out.append("PUSH")
    if re.search(r"DIAL[- ]TYPE", t):
        out.append("DIAL")
    return out


# Systems whose title parenthetical only spells out the name, e.g. "ECT (ELECTRONIC ...)"
_NAME_ONLY_PAREN = {"ect", "abs", "power-flow", "srs"}


def variant_label(key: str, paren: str, v: dict) -> str:
    """Short human label for a circuit variant (shown on chips)."""
    if key in _NAME_ONLY_PAREN and not v.get("engines"):
        return ""
    if key.startswith("hvac-"):
        b = v.get("blower", [])
        if b == ["PUSH"]:
            return "Push-button blower control"
        if b == ["DIAL"]:
            return "Dial blower control"
        if b:
            return "Push-button + dial blower control"
        return ""
    if key == "cruise-control" and v.get("cruise_type"):
        return v["cruise_type"].capitalize() + " type"
    if not paren:
        return ""
    p = re.sub(r"^FOR\s+", "", paren)
    return pretty(p)


def classify(raw_title: str) -> dict:
    """Map a raw circuit title to its system rule + parsed variant."""
    title = normalize_title(raw_title)
    base, paren = split_title(title)
    base_cmp = re.sub(r"[()]", "", base).strip()
    if base_cmp.startswith("POWER SOURCE") and "CURRENT FLOW" in title:
        base_cmp, paren = "POWER SOURCE CURRENT FLOW CHART", ""
    v = parse_variant(paren)
    for key, name, cat, rx, fixed in _COMPILED:
        if not rx.match(base_cmp):
            continue
        if fixed.get("ac") and key.startswith("hvac-"):
            want = fixed["ac"][0]
            if v.get("ac", ["AUTO"])[0] != want:
                continue
        attrs = {k: val for k, val in fixed.items() if k != "option"}
        for k, val in attrs.items():
            v.setdefault(k, val)
        return {"key": key, "name": name, "category": cat, "title": title,
                "paren": paren, "variant": v,
                "variant_label": variant_label(key, paren, v),
                "option": fixed.get("option")}
    slug = re.sub(r"[^a-z0-9]+", "-", base_cmp.lower()).strip("-") or "untitled"
    return {"key": "x-" + slug, "name": pretty(base_cmp) or "Untitled", "category": "other",
            "title": title, "paren": paren, "variant": v,
            "variant_label": variant_label("", paren, v), "option": None}


def group_key(info: dict) -> str:
    """Consecutive pages with the same group key belong to one circuit."""
    return info["key"] + "|" + info["paren"]
