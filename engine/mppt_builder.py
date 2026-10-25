import os
import json
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

# ==========================================
# ENVIRONMENT CONFIGURATION
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "https://hanifsalman11.github.io/mppt-charge-index").rstrip("/")
INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY", "a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9").strip()
CUSTOM_SOLAR = os.environ.get("CUSTOM_SOLAR", "").strip()
PAGES_PER_RUN = int(os.environ.get("PAGES_PER_RUN", "3"))

DOCS_DIR = "docs"
DATA_DIR = "data"
PUBLISHED_FILE = os.path.join(DATA_DIR, "published_controllers.json")
MONETIZATION_FILE = os.path.join(DATA_DIR, "monetization.json")

# Format: (Setup / Controller Name, Solar Array Watts, Battery Bank Volts, Max PV Input Volts, Rated MPPT Amps, Panel Config)
SEED_CONTROLLERS = [
    ("Victron SmartSolar MPPT 100/50 (100V 50A)", 700, 12, 100, 50, "2S2P (4x 175W Panels)"),
    ("Victron SmartSolar MPPT 100/30 (100V 30A)", 400, 12, 100, 30, "2S (2x 200W Panels)"),
    ("Victron SmartSolar MPPT 150/35 (150V 35A)", 1000, 24, 150, 35, "3S2P (6x 175W Panels)"),
    ("Victron SmartSolar MPPT 150/60 Tr (150V 60A)", 1600, 24, 150, 60, "4S (4x 400W Panels)"),
    ("Victron SmartSolar MPPT 150/100 (150V 100A)", 2800, 24, 150, 100, "3S3P (9x 310W Panels)"),
    ("Victron SmartSolar MPPT 250/100 (250V 100A)", 5800, 48, 250, 100, "5S3P (15x 390W Panels)"),
    ("Renogy Rover Li 40 Amp MPPT Charge Controller", 520, 12, 100, 40, "2S2P (4x 130W Panels)"),
    ("Renogy Rover Li 60 Amp 12V/24V/36V/48V MPPT", 800, 12, 150, 60, "4S (4x 200W Panels)"),
    ("Renogy Rover 100 Amp High-Voltage MPPT Controller", 1300, 12, 150, 100, "3S2P (6x 220W Panels)"),
    ("EPEVER Tracer 4210AN 40A MPPT Charge Controller", 520, 12, 100, 40, "2S2P (4x 130W Panels)"),
    ("EPEVER Tracer 6415AN 60A 150V MPPT Controller", 1600, 24, 150, 60, "4S (4x 400W Panels)"),
    ("EPEVER Tracer 10420AN 100A 200V MPPT Controller", 5000, 48, 200, 100, "4S3P (12x 415W Panels)"),
    ("Victron BlueSolar MPPT 75/15 (75V 15A) Setup", 220, 12, 75, 15, "2S (2x 110W Panels)"),
    ("BougeRV 40A MPPT Solar Charge Controller (12V/24V)", 550, 12, 100, 40, "2S2P (4x 140W Panels)"),
    ("BougeRV 60A MPPT Negative-Ground Controller", 800, 12, 150, 60, "4S (4x 200W Panels)"),
    ("PowMr 60A MPPT 12V/24V/36V/48V Solar Controller", 1600, 24, 160, 60, "4S (4x 400W Panels)"),
    ("MidNite Solar Classic 150 MPPT (150V 96A) Setup", 2500, 24, 150, 96, "3S2P (6x 415W Panels)"),
    ("OutBack Power FLEXmax 80 (150V 80A) MPPT Setup", 4000, 48, 150, 80, "3S4P (12x 335W Panels)"),
    ("Morningstar TriStar MPPT 60A 150V Controller", 1600, 24, 150, 60, "4S (4x 400W Panels)"),
    ("Redarc Manager30 & BCDC1240D Dual-Input MPPT", 500, 12, 32, 40, "4P Parallel (4x 125W)"),
    ("400W Solar Array (2x 200W) 12V RV MPPT Sizing", 400, 12, 100, 30, "2S Series (2x 200W)"),
    ("600W Solar Array (3x 200W) 12V Camper MPPT Sizing", 600, 12, 100, 50, "3S Series (3x 200W)"),
    ("800W Solar Array (4x 200W) 12V/24V MPPT Sizing", 800, 12, 150, 60, "2S2P or 4S (4x 200W)"),
    ("1000W Solar Array (5x 200W) 24V Cabin MPPT Sizing", 1000, 24, 150, 40, "5S Series (5x 200W)"),
    ("1200W Solar Array (3x 400W) 24V Off-Grid MPPT Sizing", 1200, 24, 150, 50, "3S Series (3x 400W)"),
    ("1600W Solar Array (4x 400W) 24V/48V MPPT Sizing", 1600, 24, 150, 60, "2S2P or 3S (4x 400W)"),
    ("2000W Solar Array (5x 400W) 48V Off-Grid MPPT Sizing", 2000, 48, 250, 45, "5S Series (5x 400W)"),
    ("2400W Solar Array (6x 400W) 48V Cabin MPPT Sizing", 2400, 48, 250, 50, "3S2P (6x 400W)"),
    ("3000W Solar Array (8x 375W) 48V Homestead MPPT", 3000, 48, 250, 65, "4S2P (8x 375W)"),
    ("4000W Solar Array (10x 400W) 48V Whole-Cabin MPPT", 4000, 48, 250, 85, "5S2P (10x 400W)")
]


def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Could not parse {filepath}: {e}")
    return default


def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    return re.sub(r"[\s-]+", "-", text).strip("-")


def safe_float(val, default=600.0):
    try:
        cleaned = re.sub(r"[^0-9.]", "", str(val))
        return float(cleaned) if cleaned else float(default)
    except Exception:
        return float(default)


def build_amazon_url(search_keywords, mon_cfg):
    domain = mon_cfg.get("marketplace_domain", "www.amazon.com")
    tag = mon_cfg.get("amazon_associate_tag", "YOUR_AMAZON_TAG-20")
    encoded_q = urllib.parse.quote_plus(search_keywords)
    return f"https://{domain}/s?k={encoded_q}&tag={tag}"


def discover_google_mppt_queries():
    discovered = []
    seeds = [
        "what size mppt charge controller for ",
        "victron smartsolar mppt ",
        "renogy rover mppt ",
        "solar charge controller calculator for "
    ]
    for seed in seeds:
        try:
            url = f"http://suggestqueries.google.com/complete/search?client=firefox&hl=en&gl=us&q={urllib.parse.quote(seed)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for suggestion in data[1]:
                    cleaned = suggestion.lower()
                    for pref in seeds:
                        if "what size" in pref or "calculator" in pref:
                            cleaned = cleaned.replace(pref, "")
                    cleaned = re.sub(
                        r"\b(calculator|size|sizing|chart|manual|review|reddit|for)\b",
                        "",
                        cleaned
                    ).strip()
                    if 5 <= len(cleaned) <= 42:
                        w_match = re.search(r"(\d{3,4})\s*w", cleaned)
                        w_val = int(w_match.group(1)) if w_match else 800
                        v_bat = 12 if w_val <= 800 else (24 if w_val <= 2000 else 48)
                        amps_calc = int(round((w_val / (v_bat * 1.12)) / 10.0) * 10)
                        amps_calc = max(20, min(100, amps_calc))
                        discovered.append((cleaned.title(), w_val, v_bat, 150, amps_calc, "2S2P Series-Parallel"))
        except Exception as e:
            print(f"[WARN] Google Suggest notice: {e}")
    return discovered


def build_deterministic_mppt_data(solar_tuple):
    """Mesin Fisika Fotovoltaik NEC Article 690 & Hukum Ohm MPPT (100% bebas gagal)."""
    item_name, array_watts, batt_volts, max_pv_volts, mppt_amps, panel_cfg = solar_tuple

    # Tegangan pengisian bulk LiFePO4 (14.2V untuk 12V, 28.4V untuk 24V, 56.8V untuk 48V)
    charge_volts = round(batt_volts * 1.18, 1)
    # Arus output aktual ke baterai (Amps = Array Watts * 0.96 efisiensi / Charge Volts)
    actual_charge_amps = round((array_watts * 0.96) / charge_volts, 1)
    # NEC 690.8 Breaker/Fuse Output ke Baterai (1.25x dari Rated MPPT Amps)
    batt_breaker_amps = int(round(mppt_amps * 1.25, -1))

    # Ukuran kabel tembaga antara MPPT dan Baterai (<2% voltage drop)
    if mppt_amps <= 30:
        batt_wire_awg = "10 AWG / 8 AWG Tinned Copper"
    elif mppt_amps <= 50:
        batt_wire_awg = "6 AWG Tinned Marine Copper"
    elif mppt_amps <= 70:
        batt_wire_awg = "4 AWG Tinned Marine Copper"
    else:
        batt_wire_awg = "2 AWG or 1/0 AWG Pure Copper"

    # Batas panel seri dengan faktor koreksi suhu dingin NEC 690.7 (1.18x pada -10°C / 14°F)
    max_stc_voc_allowed = round(max_pv_volts / 1.18, 1)
    daily_kwh_harvest = round((array_watts * 4.5 * 0.85) / 1000.0, 2)

    return {
        "controller_name": item_name,
        "seo_title": f"{item_name} MPPT Amps, Max Solar Voc & Wire Gauge Calculator (2026)",
        "meta_description": f"Calculate exact MPPT charge current ({actual_charge_amps}A @ {batt_volts}V), NEC 690.7 cold-weather Voc limit ({max_stc_voc_allowed}V STC / {max_pv_volts}V Max), and {batt_wire_awg} cable for {item_name}.",
        "specs": {
            "solar_array_watts": array_watts,
            "battery_bank_volts": batt_volts,
            "max_pv_input_volts": max_pv_volts,
            "max_stc_voc_limit": max_stc_voc_allowed,
            "rated_mppt_amps": mppt_amps,
            "actual_charge_amps": actual_charge_amps,
            "recommended_breaker_amps": batt_breaker_amps,
            "recommended_wire_awg": batt_wire_awg,
            "panel_configuration": panel_cfg,
            "daily_kwh_yield": daily_kwh_harvest
        },
        "nec_verdict": f"Pairing a {array_watts:,}W solar array with a {batt_volts}V LiFePO4 battery bank ({charge_volts}V absorption) produces up to {actual_charge_amps} Amps of DC charging current (~{daily_kwh_harvest} kWh/day in 4.5 peak sun hours). The {item_name} ({max_pv_volts}V / {mppt_amps}A rated) requires keeping total series-string STC Open-Circuit Voltage ($V_{{oc}}$) below {max_stc_voc_allowed}V so freezing winter mornings (+18% NEC 690.7 cold voltage spike) never exceed the {max_pv_volts}V MOSFET ceiling. Wire the battery output using {batt_wire_awg} protected by a {batt_breaker_amps}A DC circuit breaker.",
        "hardware_bundle": [
            {
                "badge": f"{max_pv_volts}V / {mppt_amps}A MPPT",
                "title": f"{max_pv_volts}V {mppt_amps}-Amp Smart Bluetooth MPPT Solar Charge Controller (12V/24V/48V)",
                "price_range": "$119 - $549",
                "amazon_query": f"{max_pv_volts}V {mppt_amps}A MPPT Solar Charge Controller Victron Renogy",
                "solar_note": f"Tracks maximum power point with 98% conversion efficiency and programmable {charge_volts}V LiFePO4 absorption profile."
            },
            {
                "badge": f"{array_watts}W Solar Array",
                "title": f"200W / 400W N-Type Bifacial Monocrystalline Solar Panels ({panel_cfg} String)",
                "price_range": "$159 - $699",
                "amazon_query": "200W 400W Bifacial Monocrystalline Solar Panel 12V 24V",
                "solar_note": f"Generates ~{daily_kwh_harvest} kWh daily when wired in {panel_cfg} to boost early-morning MPPT startup voltage."
            },
            {
                "badge": f"{batt_volts}V LiFePO4 Bank",
                "title": f"{batt_volts}V 100Ah / 200Ah Deep-Cycle LiFePO4 Battery with Low-Temp Cut-Off BMS",
                "price_range": "$229 - $899",
                "amazon_query": f"{batt_volts}V 100Ah 200Ah LiFePO4 Battery Built-in BMS",
                "solar_note": f"Accepts full {actual_charge_amps}A MPPT charge current at 99% coulombic efficiency without lead-acid voltage sag."
            },
            {
                "badge": "PV Wire & DC Breakers",
                "title": f"10 AWG Solar PV Wire + {batt_wire_awg.split()[0]} AWG Battery Cable & {batt_breaker_amps}A DC Polarized Breaker",
                "price_range": "$49 - $139",
                "amazon_query": f"10 AWG Solar Panel Wire MC4 {batt_breaker_amps}A DC Circuit Breaker Disconnect",
                "solar_note": f"Provides NEC 690 rapid PV disconnect and <2% voltage drop between controller terminals and battery busbar."
            }
        ],
        "nec_checklist": [
            f"Never use Operating Voltage ($V_{{mp}}$) to calculate series string limits! Always multiply panel Open-Circuit Voltage ($V_{{oc}}$) by the number of panels in series and add an 18% cold-temperature safety buffer (max {max_stc_voc_allowed}V STC for a {max_pv_volts}V controller).",
            f"Connect the {batt_volts}V battery bank to the MPPT controller FIRST before connecting the solar panels; this allows the microcontroller to auto-detect system voltage and prevents unbuffered PV surge damage.",
            f"Install a {batt_breaker_amps}A DC-rated circuit breaker or Class-T/MRBF fuse on the positive battery cable using {batt_wire_awg} within 7 inches of the battery busbar.",
            "If wiring 3 or more solar strings in parallel (3P+), install inline 15A or 20A MC4 branch fuses on each string to prevent backfeed current into a shaded or shorted panel."
        ],
        "faqs": [
            {
                "q": f"How many watts of solar panels can the {item_name} handle on 12V vs 24V vs 48V?",
                "a": f"Because an MPPT controller is rated by output amperage ({mppt_amps}A), doubling your battery bank voltage doubles the solar wattage it can process! At {mppt_amps}A, it handles ~{mppt_amps * 14}W on a 12V battery, ~{mppt_amps * 28}W on a 24V battery, and up to ~{mppt_amps * 56}W on a 48V battery bank."
            },
            {
                "q": f"Why is there a {max_stc_voc_allowed}V STC limit on a {max_pv_volts}V rated MPPT controller?",
                "a": f"Solar cells act like semiconductors whose voltage increases by ~0.32% for every 1°C drop below 25°C (77°F). On a freezing -10°C (14°F) winter morning, a string rated at {max_stc_voc_allowed}V STC spikes to {max_pv_volts}V. Exceeding {max_pv_volts}V permanently destroys the MPPT input stage."
            },
            {
                "q": f"Can I over-panel the {item_name} with more solar watts than its nominal rating?",
                "a": f"Yes, you can safely over-panel wattage by 20% to 30% to boost cloudy-day production— the MPPT will simply clip/limit output current to its {mppt_amps}A ceiling during peak noon sun—PROVIDED you NEVER exceed the {max_pv_volts}V cold-weather input voltage limit."
            }
        ]
    }


def generate_mppt_data(solar_tuple):
    if not GEMINI_API_KEY:
        return build_deterministic_mppt_data(solar_tuple)

    item_name, array_watts, batt_volts, max_pv_volts, mppt_amps, panel_cfg = solar_tuple
    charge_volts = round(batt_volts * 1.18, 1)
    actual_amps = round((array_watts * 0.96) / charge_volts, 1)
    brk_amps = int(round(mppt_amps * 1.25, -1))
    max_stc_voc = round(max_pv_volts / 1.18, 1)
    daily_kwh = round((array_watts * 4.5 * 0.85) / 1000.0, 2)
    wire_awg = "6 AWG Tinned Copper" if mppt_amps <= 50 else "4 AWG / 2 AWG Copper"

    prompt = f"""
You are a NABCEP Certified PV Installation Professional & Off-Grid Solar Electrical Engineer (NEC Article 690 Specialist). Create an accurate 2026 MPPT solar charge controller amperage, cold-temperature Voc string limit, and wire gauge guide for: "{item_name}".
Baseline specs: Solar Array={array_watts}W ({panel_cfg}), Battery={batt_volts}V ({charge_volts}V charge), Controller={max_pv_volts}V / {mppt_amps}A, Actual Current={actual_amps}A, Max STC Voc={max_stc_voc}V, Breaker={brk_amps}A, Wire={wire_awg}, Daily Yield={daily_kwh} kWh.
Return ONLY a valid JSON object matching this exact schema:
{{
  "controller_name": "{item_name}",
  "seo_title": "{item_name} MPPT Amps, Max Solar Voc & Wire Gauge Calculator (2026)",
  "meta_description": "Calculate exact MPPT charging amps, NEC 690.7 cold-weather Voc string limits, and copper wire gauge for {item_name}.",
  "specs": {{
    "solar_array_watts": {array_watts},
    "battery_bank_volts": {batt_volts},
    "max_pv_input_volts": {max_pv_volts},
    "max_stc_voc_limit": {max_stc_voc},
    "rated_mppt_amps": {mppt_amps},
    "actual_charge_amps": {actual_amps},
    "recommended_breaker_amps": {brk_amps},
    "recommended_wire_awg": "{wire_awg}",
    "panel_configuration": "{panel_cfg}",
    "daily_kwh_yield": {daily_kwh}
  }},
  "nec_verdict": "3-sentence technical summary stating array watts, battery voltage, charging amps, NEC 690.7 cold-weather Voc ceiling, and required breaker/wire size.",
  "hardware_bundle": [
    {{
      "badge": "{max_pv_volts}V / {mppt_amps}A MPPT",
      "title": "{max_pv_volts}V {mppt_amps}A Smart Bluetooth MPPT Solar Charge Controller",
      "price_range": "$119 - $549",
      "amazon_query": "{max_pv_volts}V {mppt_amps}A MPPT Solar Charge Controller",
      "solar_note": "1-sentence MPPT tracking efficiency note"
    }},
    {{
      "badge": "{array_watts}W Solar Panels",
      "title": "200W / 400W Monocrystalline Bifacial Solar Panel Kit ({panel_cfg})",
      "price_range": "$159 - $699",
      "amazon_query": "200W 400W Monocrystalline Solar Panel Kit",
      "solar_note": "1-sentence daily kWh harvest note"
    }},
    {{
      "badge": "{batt_volts}V LiFePO4 Bank",
      "title": "{batt_volts}V 100Ah / 200Ah Deep-Cycle LiFePO4 Solar Battery",
      "price_range": "$229 - $899",
      "amazon_query": "{batt_volts}V 100Ah LiFePO4 Deep Cycle Battery",
      "solar_note": "1-sentence BMS low-temp protection note"
    }},
    {{
      "badge": "PV Wire & DC Breaker",
      "title": "10 AWG Solar PV Extension Cable + {brk_amps}A DC Circuit Breaker & MC4 Kit",
      "price_range": "$49 - $139",
      "amazon_query": "10 AWG Solar Wire MC4 {brk_amps}A DC Circuit Breaker",
      "solar_note": "1-sentence NEC 690 overcurrent protection note"
    }}
  ],
  "nec_checklist": [
    "Step 1 regarding NEC 690.7 cold-weather Voc string calculation",
    "Step 2 regarding connecting battery bank BEFORE solar array",
    "Step 3 regarding 1.25x DC breaker and AWG battery cable sizing",
    "Step 4 regarding MC4 inline fuses for 3+ parallel strings"
  ],
  "faqs": [
    {{"q": "How many watts of solar can the {item_name} handle on 12V vs 24V vs 48V?", "a": "Exact wattage numbers for 12V, 24V, and 48V battery banks."}},
    {{"q": "How many panels can I wire in series on a {max_pv_volts}V MPPT controller?", "a": "Exact Voc formula with 18% freezing temperature margin."}},
    {{"q": "What size wire and breaker do I need for a {mppt_amps}A MPPT controller?", "a": "Exact AWG copper wire and DC breaker rating."}}
  ]
}}
"""

    for model_id in ["gemini-2.5-flash", "gemini-2.0-flash"]:
        try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "responseMimeType": "application/json"
                }
            }
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=35) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                raw_text = re.sub(r"\s*```$", "", raw_text)
                parsed = json.loads(raw_text)
                if "specs" in parsed and "hardware_bundle" in parsed:
                    return parsed
        except Exception as e:
            print(f"[WARN] Gemini ({model_id}) notice for '{item_name}': {e}")

    return build_deterministic_mppt_data(solar_tuple)


def build_mppt_html_page(data, slug, mon_cfg):
    ctrl_name = data.get("controller_name", "MPPT Solar Charge Controller")
    sp = data.get("specs", {})
    array_w = int(safe_float(sp.get("solar_array_watts", 800), 800))
    batt_v = int(safe_float(sp.get("battery_bank_volts", 12), 12))
    max_pv_v = int(safe_float(sp.get("max_pv_input_volts", 150), 150))
    max_stc_v = round(safe_float(sp.get("max_stc_voc_limit", 127.0), 127.0), 1)
    mppt_a = int(safe_float(sp.get("rated_mppt_amps", 60), 60))
    actual_a = round(safe_float(sp.get("actual_charge_amps", 55.0), 55.0), 1)
    brk_a = int(safe_float(sp.get("recommended_breaker_amps", 75), 75))
    wire_awg = sp.get("recommended_wire_awg", "6 AWG Tinned Copper")
    panel_cfg = sp.get("panel_configuration", "2S2P Series-Parallel")
    daily_kwh = round(safe_float(sp.get("daily_kwh_yield", 3.1), 3.1), 2)

    header_cta = mon_cfg.get("header_cta", {})
    header_cta_url = build_amazon_url(header_cta.get("search_query", "MPPT+Solar+Charge+Controller+Victron+Renogy"), mon_cfg)

    schema_graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "SoftwareApplication",
                "name": f"{ctrl_name} MPPT Amps & Voc String Calculator",
                "applicationCategory": "UtilitiesApplication",
                "operatingSystem": "Web Browser",
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": f.get("q", ""),
                        "acceptedAnswer": {"@type": "Answer", "text": f.get("a", "")}
                    } for f in data.get("faqs", [])
                ]
            }
        ]
    }

    bundle_html = ""
    for item in data.get("hardware_bundle", []):
        amz_url = build_amazon_url(item.get("amazon_query", item.get("title", "MPPT Charge Controller")), mon_cfg)
        bundle_html += f"""
        <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-amber-500/60 transition">
          <div>
            <div class="flex items-center justify-between gap-2 mb-2">
              <span class="text-xs font-bold uppercase tracking-wider bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2.5 py-0.5 rounded">{item.get('badge', 'Solar BoS')}</span>
              <span class="text-sm font-bold text-emerald-400">{item.get('price_range', '$99+')}</span>
            </div>
            <h3 class="text-base font-bold text-white mt-2">{item.get('title', '')}</h3>
            <p class="text-xs text-slate-400 mt-2 leading-relaxed">☀️ {item.get('solar_note', '')}</p>
          </div>
          <a href="{amz_url}" target="_blank" rel="nofollow sponsored" class="mt-5 block text-center bg-amber-500 hover:bg-amber-400 text-slate-950 font-extrabold py-2.5 px-4 rounded-lg text-sm transition shadow-lg">
            Check Price on Amazon →
          </a>
        </div>"""

    # Build 12V vs 24V vs 48V MPPT Capacity Matrix Table
    mppt_tiers = [
        ("30 Amp MPPT", "400W Max (12V)", "800W Max (24V)", "1,600W Max (48V)", "10 AWG / 8 AWG (40A Breaker)"),
        ("40 Amp MPPT", "550W Max (12V)", "1,100W Max (24V)", "2,200W Max (48V)", "8 AWG Copper (50A Breaker)"),
        ("50 Amp MPPT", "700W Max (12V)", "1,400W Max (24V)", "2,800W Max (48V)", "6 AWG Copper (60A Breaker)"),
        ("60 Amp MPPT", "850W Max (12V)", "1,700W Max (24V)", "3,400W Max (48V)", "6 AWG / 4 AWG (80A Breaker)"),
        ("100 Amp MPPT", "1,400W Max (12V)", "2,800W Max (24V)", "5,800W Max (48V)", "2 AWG Copper (125A Breaker)")
    ]
    matrix_rows_html = ""
    for amp_s, w12_s, w24_s, w48_s, wir_s in mppt_tiers:
        matrix_rows_html += f"""
        <tr class="border-b border-slate-800 hover:bg-slate-800/40">
          <td class="py-3 px-4 font-bold text-white">{amp_s}</td>
          <td class="py-3 px-4 text-amber-400 font-semibold">{w12_s}</td>
          <td class="py-3 px-4 text-emerald-400 font-bold">{w24_s}</td>
          <td class="py-3 px-4 text-cyan-400 font-bold">{w48_s}</td>
          <td class="py-3 px-4 text-xs text-slate-300">{wir_s}</td>
        </tr>"""

    checklist_html = ""
    for idx, step_text in enumerate(data.get("nec_checklist", []), start=1):
        checklist_html += f"""
        <label class="flex items-start gap-3.5 bg-slate-900 border border-slate-800 rounded-xl p-4 cursor-pointer hover:border-slate-700 transition">
          <input type="checkbox" class="mt-1 w-5 h-5 accent-amber-500 rounded cursor-pointer mppt-check">
          <span class="text-sm text-slate-200 leading-relaxed"><strong>NEC 690 Step {idx}:</strong> {step_text}</span>
        </label>"""

    faqs_html = "".join([
        f"<div class='bg-slate-900 border border-slate-800 rounded-xl p-5'><h3 class='font-bold text-white text-base mb-2'>{f.get('q', '')}</h3><p class='text-sm text-slate-300 leading-relaxed'>{f.get('a', '')}</p></div>"
        for f in data.get("faqs", [])
    ])

    canonical_url = f"{SITE_BASE_URL}/{slug}.html"
    amz_domain = mon_cfg.get("marketplace_domain", "www.amazon.com")
    amz_tag = mon_cfg.get("amazon_associate_tag", "YOUR_AMAZON_TAG-20")

    html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{data.get('seo_title', ctrl_name)}</title>
  <meta name="description" content="{data.get('meta_description', '')}">
  <link rel="canonical" href="{canonical_url}">
  <meta property="og:title" content="{data.get('seo_title', ctrl_name)}">
  <meta property="og:description" content="{data.get('meta_description', '')}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canonical_url}">
  <script src="https://cdn.tailwindcss.com"></script>
  <script type="application/ld+json">{json.dumps(schema_graph)}</script>
</head>
<body class="bg-slate-950 text-slate-100 antialiased min-h-screen flex flex-col">
  <header class="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-30">
    <div class="max-w-5xl mx-auto px-4 py-3.5 flex items-center justify-between">
      <a href="index.html" class="text-lg font-black tracking-tight text-white flex items-center gap-2">
        <span class="bg-amber-500 text-slate-950 px-2 py-0.5 rounded font-black">MPPT</span>SolarIndex
      </a>
      <a href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="text-xs sm:text-sm bg-amber-500 hover:bg-amber-400 text-slate-950 font-extrabold px-3.5 py-2 rounded-lg transition">
        {header_cta.get('cta_text', 'Shop MPPT Controllers & Kits →')}
      </a>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 py-10 flex-1 w-full">
    <div class="mb-8">
      <div class="flex flex-wrap items-center gap-2.5 mb-3">
        <span class="text-xs font-extrabold uppercase tracking-widest bg-amber-500 text-slate-950 px-3 py-1 rounded-full">{max_pv_v}V / {mppt_a}A MPPT</span>
        <span class="text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-3 py-1 rounded-full">{array_w:,}W Array @ {batt_v}V ({actual_a}A Charge)</span>
        <span class="text-xs font-semibold bg-slate-800 text-slate-300 px-3 py-1 rounded-full">Max STC Voc: {max_stc_v}V | {wire_awg}</span>
      </div>
      <h1 class="text-3xl sm:text-4xl font-black text-white leading-tight">{data.get('seo_title', ctrl_name)}</h1>
      <div class="mt-4 bg-slate-900 border-l-4 border-amber-500 p-4 rounded-r-xl text-sm text-slate-200 leading-relaxed">
        <strong>NABCEP & NEC Article 690 Verdict:</strong> {data.get('nec_verdict', '')}
      </div>
    </div>

    <!-- INTERACTIVE MPPT AMPS, COLD-WEATHER VOC STRING & WIRE GAUGE CALCULATOR -->
    <section class="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 mb-12 shadow-2xl">
      <h2 class="text-xl font-extrabold text-white mb-2">Interactive {ctrl_name} Amps & Cold $V_{{oc}}$ String Calculator</h2>
      <p class="text-xs text-slate-400 mb-6">Adjust your total solar array wattage, battery bank voltage (12V/24V/48V), series string $V_{{oc}}$, and coldest winter temperature to verify MPPT amperage and NEC 690.7 voltage safety.</p>

      <div class="grid md:grid-cols-2 gap-8 items-center">
        <div class="space-y-5">
          <div>
            <div class="flex justify-between text-sm font-medium mb-1.5">
              <label for="wattsSlider" class="text-slate-300">Total Solar Array Wattage (Watts)</label>
              <span class="text-amber-400 font-bold"><span id="wattsVal">{array_w:,}</span> Watts</span>
            </div>
            <input id="wattsSlider" type="range" min="100" max="5000" step="100" value="{array_w}" class="w-full accent-amber-500 cursor-pointer">
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label for="battVoltSelect" class="block text-xs font-medium text-slate-400 mb-1">Battery Bank Voltage</label>
              <select id="battVoltSelect" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-amber-500">
                <option value="12" {"selected" if batt_v == 12 else ""}>12V LiFePO4 (14.2V Charge)</option>
                <option value="24" {"selected" if batt_v == 24 else ""}>24V LiFePO4 (28.4V Charge)</option>
                <option value="48" {"selected" if batt_v == 48 else ""}>48V LiFePO4 (56.8V Charge)</option>
              </select>
            </div>
            <div>
              <label for="tempSelect" class="block text-xs font-medium text-slate-400 mb-1">Coldest Winter Temp (NEC 690.7)</label>
              <select id="tempSelect" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-amber-500">
                <option value="1.08">32°F / 0°C Mild (+8% Voc)</option>
                <option value="1.14" selected>14°F / -10°C Freezing (+14% Voc)</option>
                <option value="1.20">-13°F / -25°C Extreme (+20% Voc)</option>
              </select>
            </div>
          </div>

          <div>
            <div class="flex justify-between text-sm font-medium mb-1.5">
              <label for="vocSlider" class="text-slate-300">Series String Total STC Open-Circuit Voltage ($V_{{oc}}$)</label>
              <span class="text-amber-400 font-bold"><span id="vocVal">88</span>V STC</span>
            </div>
            <input id="vocSlider" type="range" min="22" max="220" step="2" value="88" class="w-full accent-amber-500 cursor-pointer">
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="bg-slate-950 border border-amber-500/30 rounded-xl p-4">
            <span class="text-xs uppercase text-amber-400 font-bold">Required MPPT Rating</span>
            <div class="text-2xl sm:text-3xl font-black text-white mt-1"><span id="ampsOut">{mppt_a}</span> <span class="text-sm font-normal text-slate-400">Amps</span></div>
            <p id="wireOut" class="text-xs text-amber-400 font-semibold mt-1">{wire_awg} ({brk_a}A Brk)</p>
          </div>

          <div class="bg-slate-950 border border-emerald-500/30 rounded-xl p-4">
            <span class="text-xs uppercase text-emerald-400 font-bold">Cold Peak String $V_{{oc}}$</span>
            <div class="text-2xl sm:text-3xl font-black text-emerald-400 mt-1"><span id="coldVocOut">100.3</span> <span class="text-sm font-normal text-slate-400">V</span></div>
            <p id="vocStatusOut" class="text-xs text-emerald-400 font-semibold mt-1">✅ Safe for 150V MPPT</p>
          </div>
        </div>
      </div>

      <div class="mt-6 bg-amber-950/40 border border-amber-500/30 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div id="mpptAdviceBanner" class="text-sm text-amber-100 font-medium"></div>
        <a id="dynamicMpptBtn" href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="shrink-0 bg-amber-500 hover:bg-amber-400 text-slate-950 font-extrabold px-4 py-2.5 rounded-lg text-xs uppercase tracking-wider transition">
          Shop Matched MPPT Controller on Amazon →
        </a>
      </div>
    </section>

    <!-- 4-CARD HARDWARE BUNDLE -->
    <section class="mb-12">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-extrabold text-white">Complete {ctrl_name} Solar, Battery & Breaker Kit</h2>
        <span class="text-xs text-slate-400">UL-1741 & NEC Article 690 Compliant</span>
      </div>
      <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">{bundle_html}</div>
    </section>

    <!-- 12V vs 24V vs 48V MPPT CAPACITY MATRIX TABLE -->
    <section class="mb-12">
      <h2 class="text-2xl font-extrabold text-white mb-4">MPPT Charge Controller Max Solar Wattage by Battery Voltage (12V / 24V / 48V)</h2>
      <div class="overflow-x-auto bg-slate-900 border border-slate-800 rounded-xl">
        <table class="w-full text-left border-collapse text-sm">
          <thead>
            <tr class="border-b border-slate-800 bg-slate-950/60 text-slate-400 uppercase text-xs">
              <th class="py-3.5 px-4">Controller Rating</th>
              <th class="py-3.5 px-4 text-amber-400">12V Battery Bank Max</th>
              <th class="py-3.5 px-4 text-emerald-400">24V Battery Bank Max</th>
              <th class="py-3.5 px-4 text-cyan-400">48V Battery Bank Max</th>
              <th class="py-3.5 px-4">Battery Cable & Breaker</th>
            </tr>
          </thead>
          <tbody>{matrix_rows_html}</tbody>
        </table>
      </div>
    </section>

    <!-- NEC 690 CHECKLIST -->
    <section class="mb-12">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-extrabold text-white">NABCEP Solar String & MPPT Wiring Safety Checklist</h2>
        <span id="mpptBadge" class="text-xs font-bold bg-slate-800 text-amber-400 px-3 py-1 rounded-full">0 / 4 Completed</span>
      </div>
      <div class="space-y-3">{checklist_html}</div>
    </section>

    <!-- FAQ -->
    <section class="mb-12">
      <h2 class="text-2xl font-extrabold text-white mb-5">Frequently Asked Questions ({ctrl_name})</h2>
      <div class="space-y-4">{faqs_html}</div>
    </section>
  </main>

  <footer class="border-t border-slate-800 py-8 text-center text-xs text-slate-500 px-4">
    <p>© {datetime.now(timezone.utc).year} MPPTSolarIndex. Independent Off-Grid Solar & NEC 690 Engineering Database. As an Amazon Associate, we earn from qualifying purchases.</p>
  </footer>

  <script>
    const amzDomain = "{amz_domain}";
    const amzTag = "{amz_tag}";

    const wattsSlider = document.getElementById('wattsSlider');
    const battVoltSelect = document.getElementById('battVoltSelect');
    const tempSelect = document.getElementById('tempSelect');
    const vocSlider = document.getElementById('vocSlider');
    const wattsVal = document.getElementById('wattsVal');
    const vocVal = document.getElementById('vocVal');
    const ampsOut = document.getElementById('ampsOut');
    const wireOut = document.getElementById('wireOut');
    const coldVocOut = document.getElementById('coldVocOut');
    const vocStatusOut = document.getElementById('vocStatusOut');
    const mpptAdviceBanner = document.getElementById('mpptAdviceBanner');
    const dynamicMpptBtn = document.getElementById('dynamicMpptBtn');

    function recalculateMppt() {{
      const watts = parseInt(wattsSlider.value, 10);
      const battV = parseInt(battVoltSelect.value, 10);
      const coldMult = parseFloat(tempSelect.value);
      const stcVoc = parseInt(vocSlider.value, 10);

      wattsVal.textContent = watts.toLocaleString();
      vocVal.textContent = stcVoc;

      const chargeV = battV * 1.18;
      const rawAmps = (watts * 0.96) / chargeV;
      let stdMpptAmps = 20;
      if (rawAmps <= 20) stdMpptAmps = 20;
      else if (rawAmps <= 32) stdMpptAmps = 30;
      else if (rawAmps <= 42) stdMpptAmps = 40;
      else if (rawAmps <= 52) stdMpptAmps = 50;
      else if (rawAmps <= 65) stdMpptAmps = 60;
      else if (rawAmps <= 85) stdMpptAmps = 80;
      else stdMpptAmps = 100;

      const brkAmps = Math.ceil((stdMpptAmps * 1.25) / 5) * 5;
      let awgStr = "6 AWG Copper";
      if (stdMpptAmps <= 30) awgStr = "10 AWG / 8 AWG";
      else if (stdMpptAmps <= 50) awgStr = "6 AWG Copper";
      else if (stdMpptAmps <= 70) awgStr = "4 AWG Copper";
      else awgStr = "2 AWG Copper";

      const coldVoc = stcVoc * coldMult;
      let reqVoltTier = 100;
      if (coldVoc <= 98) reqVoltTier = 100;
      else if (coldVoc <= 148) reqVoltTier = 150;
      else reqVoltTier = 250;

      ampsOut.textContent = `${{rawAmps.toFixed(1)}}`;
      wireOut.textContent = `Use ${{stdMpptAmps}}A MPPT | ${{awgStr}} (${{brkAmps}}A Brk)`;
      coldVocOut.textContent = coldVoc.toFixed(1);

      if (coldVoc > 250) {{
        vocStatusOut.textContent = "❌ Danger! Exceeds 250V Limit";
        vocStatusOut.className = "text-xs text-red-400 font-bold mt-1";
      }} else {{
        vocStatusOut.textContent = `✅ Requires ${{reqVoltTier}}V+ Rated MPPT`;
        vocStatusOut.className = "text-xs text-emerald-400 font-semibold mt-1";
      }}

      mpptAdviceBanner.innerHTML = `☀️ <strong>NABCEP Spec:</strong> A ${{watts.toLocaleString()}}W array on a <strong>${{battV}}V battery bank</strong> produces <strong>${{rawAmps.toFixed(1)}}A</strong> and peaks at <strong>${{coldVoc.toFixed(1)}}V in winter</strong>. Install a <strong>${{reqVoltTier}}V / ${{stdMpptAmps}}A Smart MPPT Controller</strong> with <strong>${{awgStr}} cable</strong>.`;
      dynamicMpptBtn.href = `https://${{amzDomain}}/s?k=${{reqVoltTier}}V+${{stdMpptAmps}}A+MPPT+Solar+Charge+Controller+Victron+Renogy&tag=${{amzTag}}`;
    }}

    wattsSlider.addEventListener('input', recalculateMppt);
    battVoltSelect.addEventListener('change', recalculateMppt);
    tempSelect.addEventListener('change', recalculateMppt);
    vocSlider.addEventListener('input', recalculateMppt);
    recalculateMppt();

    const checks = document.querySelectorAll('.mppt-check');
    const badge = document.getElementById('mpptBadge');
    checks.forEach(ch => {{
      ch.addEventListener('change', () => {{
        const done = Array.from(checks).filter(c => c.checked).length;
        badge.textContent = `${{done}} / ${{checks.length}} Completed`;
      }});
    }});
  </script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
        f.write(html)


def rebuild_portal_sitemap_and_rss(published, mon_cfg):
    header_cta = mon_cfg.get("header_cta", {})
    header_cta_url = build_amazon_url(header_cta.get("search_query", "MPPT+Solar+Charge+Controller+Victron+Renogy"), mon_cfg)

    cards_html = ""
    for item in reversed(published):
        cards_html += f"""
        <a href="{item['slug']}.html" class="block bg-slate-900 border border-slate-800 hover:border-amber-500/60 rounded-xl p-5 transition group">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-black uppercase bg-amber-500 text-slate-950 px-2.5 py-0.5 rounded">{item.get('max_pv_v', 150)}V / {item.get('mppt_a', 60)}A MPPT</span>
            <span class="text-xs text-slate-400">{item.get('array_w', 800):,}W @ {item.get('batt_v', 12)}V</span>
          </div>
          <h2 class="text-base font-bold text-white group-hover:text-amber-400 transition">{item['controller_name']}</h2>
          <p class="text-xs text-slate-400 mt-2 line-clamp-2">{item['description']}</p>
          <span class="inline-block mt-4 text-xs font-extrabold text-amber-400">Calculate MPPT Amps & Cold Voc →</span>
        </a>"""

    index_html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MPPTSolarIndex — Solar MPPT Charge Controller Amps, Voc String & Wire Calculator (2026)</title>
  <meta name="description" content="Calculate exact MPPT solar charge controller amperage (12V/24V/48V), NEC 690.7 cold-weather Voc string limits, and copper wire gauge for Victron SmartSolar, Renogy Rover, EPEVER, and off-grid solar arrays.">
  <link rel="canonical" href="{SITE_BASE_URL}/">
  <link rel="alternate" type="application/rss+xml" title="MPPTSolarIndex RSS Feed" href="{SITE_BASE_URL}/rss.xml">
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col">
  <header class="border-b border-slate-800 bg-slate-900/80 sticky top-0 z-30 backdrop-blur">
    <div class="max-w-5xl mx-auto px-4 py-3.5 flex items-center justify-between">
      <div class="text-lg font-black text-white flex items-center gap-2">
        <span class="bg-amber-500 text-slate-950 px-2 py-0.5 rounded font-black">MPPT</span>SolarIndex
      </div>
      <a href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="text-xs sm:text-sm bg-amber-500 hover:bg-amber-400 text-slate-950 font-extrabold px-3.5 py-2 rounded-lg transition">
        {header_cta.get('cta_text', 'Shop MPPT Controllers & Kits →')}
      </a>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 py-12 flex-1 w-full">
    <div class="text-center max-w-2xl mx-auto mb-10">
      <h1 class="text-3xl sm:text-5xl font-black text-white tracking-tight">Solar MPPT Charge Controller, Voc String & Wire Database</h1>
      <p class="text-slate-400 mt-3 text-base sm:text-lg">Select your MPPT controller model or solar panel wattage below to calculate 12V/24V/48V charging amps, freezing-weather series $V_{{oc}}$ limits, and NEC 690 wire/breaker sizes.</p>
      <div class="mt-6">
        <input id="filterInput" type="text" placeholder="Search MPPT model or wattage (e.g. Victron 100/50, Renogy 60A, 800W Solar Array, 1200W, EPEVER...)" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3.5 text-sm text-white focus:outline-none focus:border-amber-500">
      </div>
    </div>

    <div id="mpptGrid" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">{cards_html}</div>
  </main>

  <footer class="border-t border-slate-800 py-8 text-center text-xs text-slate-500">
    <p>© {datetime.now(timezone.utc).year} MPPTSolarIndex. As an Amazon Associate, we earn from qualifying purchases.</p>
  </footer>

  <script>
    const filterInput = document.getElementById('filterInput');
    const cards = Array.from(document.getElementById('mpptGrid').children);
    filterInput.addEventListener('input', (e) => {{
      const q = e.target.value.toLowerCase();
      cards.forEach(c => {{
        c.style.display = c.textContent.toLowerCase().includes(q) ? 'block' : 'none';
      }});
    }});
  </script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls_xml = f"""  <url>
    <loc>{SITE_BASE_URL}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>\n"""

    for item in published:
        urls_xml += f"""  <url>
    <loc>{SITE_BASE_URL}/{item['slug']}.html</loc>
    <lastmod>{item.get('date', today)}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>\n"""

    with open(os.path.join(DOCS_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(f"""<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls_xml}</urlset>""")

    rss_items = ""
    for item in list(reversed(published))[:30]:
        rss_items += f"""    <item>
      <title>{item['title']}</title>
      <link>{SITE_BASE_URL}/{item['slug']}.html</link>
      <guid>{SITE_BASE_URL}/{item['slug']}.html</guid>
      <description>{item['description']}</description>
    </item>\n"""

    rss_xml = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>MPPTSolarIndex Off-Grid Solar & MPPT Sizing Database</title>
    <link>{SITE_BASE_URL}/</link>
    <description>Interactive Solar MPPT Charge Controller Amperage, Cold Voc & Wire Calculators</description>
    <atom:link href="{SITE_BASE_URL}/rss.xml" rel="self" type="application/rss+xml" />
    <atom:link href="https://pubsubhubbub.appspot.com/" rel="hub" />
{rss_items}  </channel>
</rss>"""

    with open(os.path.join(DOCS_DIR, "rss.xml"), "w", encoding="utf-8") as f:
        f.write(rss_xml)

    with open(os.path.join(DOCS_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {SITE_BASE_URL}/sitemap.xml\n")

    with open(os.path.join(DOCS_DIR, f"{INDEXNOW_KEY}.txt"), "w", encoding="utf-8") as f:
        f.write(INDEXNOW_KEY)


def notify_search_engines(new_urls):
    if not SITE_BASE_URL or not new_urls:
        return
    parsed_host = urllib.parse.urlparse(SITE_BASE_URL).netloc
    payload = {
        "host": parsed_host,
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE_BASE_URL}/{INDEXNOW_KEY}.txt",
        "urlList": new_urls
    }
    try:
        req = urllib.request.Request(
            "https://api.indexnow.org/indexnow",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"[INDEXNOW] Pushed {len(new_urls)} URLs (HTTP {resp.status})")
    except Exception as e:
        print(f"[WARN] IndexNow ping notice: {e}")

    try:
        hub_data = urllib.parse.urlencode({
            "hub.mode": "publish",
            "hub.url": f"{SITE_BASE_URL}/rss.xml"
        }).encode("utf-8")
        req_hub = urllib.request.Request(
            "https://pubsubhubbub.appspot.com/",
            data=hub_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST"
        )
        with urllib.request.urlopen(req_hub, timeout=15) as resp_hub:
            print(f"[WEBSUB] Google PubSubHubbub ping status: {resp_hub.status}")
    except Exception as e:
        print(f"[WARN] WebSub ping notice: {e}")


def main():
    published = load_json(PUBLISHED_FILE, [])
    mon_cfg = load_json(MONETIZATION_FILE, {})
    published_slugs = {item["slug"] for item in published}

    candidates = []
    if CUSTOM_SOLAR:
        candidates.append((CUSTOM_SOLAR.strip(), 800, 12, 150, 60, "2S2P (4x 200W Panels)"))
    candidates.extend(SEED_CONTROLLERS)
    candidates.extend(discover_google_mppt_queries())

    new_urls = []
    count = 0

    for solar_tuple in candidates:
        if count >= PAGES_PER_RUN:
            break
        c_name = solar_tuple[0]
        slug = slugify(f"{c_name}-mppt-voc-wire-calculator")
        if slug in published_slugs:
            continue

        print(f"[ENGINE] Generating MPPT solar controller & Voc calculator for: {c_name}...")
        try:
            data = generate_mppt_data(solar_tuple)
            build_mppt_html_page(data, slug, mon_cfg)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            sp = data.get("specs", {})

            published.append({
                "controller_name": data.get("controller_name", c_name),
                "slug": slug,
                "title": data.get("seo_title", f"{c_name} MPPT Calculator"),
                "description": data.get("meta_description", ""),
                "array_w": int(safe_float(sp.get("solar_array_watts", solar_tuple[1]), solar_tuple[1])),
                "batt_v": int(safe_float(sp.get("battery_bank_volts", solar_tuple[2]), solar_tuple[2])),
                "max_pv_v": int(safe_float(sp.get("max_pv_input_volts", solar_tuple[3]), solar_tuple[3])),
                "mppt_a": int(safe_float(sp.get("rated_mppt_amps", solar_tuple[4]), solar_tuple[4])),
                "date": today
            })
            published_slugs.add(slug)
            if SITE_BASE_URL:
                new_urls.append(f"{SITE_BASE_URL}/{slug}.html")
            count += 1
            time.sleep(2)
        except Exception as e:
            print(f"[ERROR] Failed building {c_name}: {e}")

    save_json(PUBLISHED_FILE, published)
    rebuild_portal_sitemap_and_rss(published, mon_cfg)
    if new_urls and SITE_BASE_URL:
        new_urls.append(f"{SITE_BASE_URL}/")
        notify_search_engines(new_urls)
    print(f"[DONE] Published {count} new MPPT solar charge controller calculator pages.")


if __name__ == "__main__":
    main()
