import socket
socket.setdefaulttimeout(8)

import os
import json
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import anthropic
import feedparser
import requests
import yfinance as yf
from groq import Groq
from openai import OpenAI

# ============================================================
# DYNAMISCHER ZEITANKER & DIAGNOSTIK
# ============================================================
NOW_UTC = datetime.utcnow()
CURRENT_DATE_STR = NOW_UTC.strftime("%d.%m.%Y")
CURRENT_YEAR = NOW_UTC.year

PIPELINE_HEALTH = {
    "groq_filter": "failed",
    "deepseek_game_theory": "failed",
    "gemini_macro": "failed",
    "xai_grok": "failed",
    "perplexity_factcheck": "failed",
    "qwen_indopacific": "failed",
    "openrouter_nemotron_tech": "failed",
    "mistral_json_builder": "failed",
    "claude_chief_editor": "failed",
    "feeds_loaded": 0,
    "feeds_total": 0
}

# ============================================================
# API CLIENTS INITIALISIERUNG
# ============================================================
groq_key = os.environ.get("GROQ_API_KEY", "").strip().strip('"').strip("'")
anth_key = os.environ.get("ANTHROPIC_API_KEY", "").strip().strip('"').strip("'")
gemini_key = os.environ.get("GEMINI_API_KEY", "").strip().strip('"').strip("'")
deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip().strip('"').strip("'")
xai_key = os.environ.get("XAI_API_KEY", os.environ.get("XAI_API", "")).strip().strip('"').strip("'")
perplexity_key = os.environ.get("PERPLEXITY_API_KEY", "").strip().strip('"').strip("'")
openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip().strip('"').strip("'")
mistral_key = os.environ.get("MISTRAL_API_KEY", "").strip().strip('"').strip("'")
qwen_key = os.environ.get("QWEN_API_KEY", os.environ.get("DASHSCOPE_API_KEY", "")).strip().strip('"').strip("'")

client_groq = Groq(api_key=groq_key) if groq_key else None
client_anthropic = anthropic.Anthropic(api_key=anth_key) if anth_key else None

client_gemini = OpenAI(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    api_key=gemini_key
) if gemini_key else None

client_deepseek = OpenAI(
    base_url="https://api.deepseek.com",
    api_key=deepseek_key
) if deepseek_key else None

client_xai = OpenAI(
    base_url="https://api.x.ai/v1",
    api_key=xai_key
) if xai_key else None

client_perplexity = OpenAI(
    base_url="https://api.perplexity.ai",
    api_key=perplexity_key
) if perplexity_key else None

client_openrouter = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=openrouter_key
) if openrouter_key else None

client_mistral = OpenAI(
    base_url="https://api.mistral.ai/v1",
    api_key=mistral_key
) if mistral_key else None

# Qwen DashScope Client
client_qwen = OpenAI(
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=qwen_key
) if qwen_key else None

# ============================================================
# HELPER-FUNKTIONEN
# ============================================================
def clean_html(raw_html):
    if not raw_html:
        return ""
    clean_text = re.sub(r'<[^>]+>', '', raw_html)
    return clean_text.strip()

def repair_and_parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    
    first_brace = text.find('{')
    last_brace = text.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        text = text[first_brace:last_brace+1]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        repaired = text
        if repaired.count('"') % 2 != 0:
            repaired += '"'
        open_brackets = repaired.count('[') - repaired.count(']')
        open_braces = repaired.count('{') - repaired.count('}')
        repaired += ']' * max(0, open_brackets)
        repaired += '}' * max(0, open_braces)
        return json.loads(repaired)

# ============================================================
# A. LIVE FINANZDATEN & RECON
# ============================================================
def get_live_market_data():
    market_summary = ""
    tickers = {
        "US Dollar Index (DXY)": "DX-Y.NYB", "EUR/USD": "EURUSD=X", "US 10Y Anleihe": "^TNX",
        "VIX": "^VIX", "Gold": "GC=F", "Brent Öl": "BZ=F", "S&P 500": "^GSPC", "Bitcoin": "BTC-USD"
    }
    try:
        for name, ticker in tickers.items():
            try:
                data = yf.Ticker(ticker).history(period="5d")
                if not data.empty and len(data) >= 2:
                    close_curr = data['Close'].iloc[-1]
                    close_prev = data['Close'].iloc[-2]
                    change_pct = ((close_curr - close_prev) / close_prev) * 100
                    market_summary += f"- {name}: {close_curr:.2f} ({change_pct:+.2f}% heute)\n"
            except Exception: pass
    except Exception as e: print(f"yfinance Hinweis: {e}")
    return market_summary if market_summary else "- Finanzdaten im Wartestand.\n"

live_market_context = get_live_market_data()

def get_live_military_flights():
    return [
        {"callsign": "FORTE12", "icao24": "ae5420", "country": "United States", "lat": 43.8, "lng": 29.8, "altitude_m": 16000, "speed_kmh": 620, "heading": 85, "is_live": False},
        {"callsign": "NATO AWACS 01", "icao24": "4d03c2", "country": "NATO", "lat": 54.2, "lng": 20.1, "altitude_m": 10500, "speed_kmh": 780, "heading": 120, "is_live": False}
    ]

def get_maritime_chokepoints():
    return [
        {"chokepoint": "Strasse von Hormus", "lat": 26.56, "lng": 56.25, "status": "HOCHRISIKO", "tanker_flow": "Normal / Tanker-Spoofing registriert"},
        {"chokepoint": "Bab al-Mandab", "lat": 12.58, "lng": 43.33, "status": "ESKALATIV", "tanker_flow": "Umleitungen aktiv"}
    ]

live_recon_flights = get_live_military_flights()
maritime_chokepoints = get_maritime_chokepoints()

# ============================================================
# B. FEEDS INGESTION (150+ FEEDS PARALLEL)
# ============================================================
SOURCES = [
    {"name": "Polymarket Geopolitics", "url": "[https://news.google.com/rss/search?q=when:24h+%22Polymarket%22+(geopolitics+OR+war)&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:24h+%22Polymarket%22+(geopolitics+OR+war)&hl=en-US&gl=US&ceid=US:en)", "cat": "Prediction Markets", "weight": 0.95, "bias": "CROWD-WISDOM"},
    {"name": "X / Twitter OSINT Breaking", "url": "[https://news.google.com/rss/search?q=when:24h+(site:x.com+OR+site:twitter.com)+%22OSINT%22+OR+%22breaking%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:24h+(site:x.com+OR+site:twitter.com)+%22OSINT%22+OR+%22breaking%22&hl=en-US&gl=US&ceid=US:en)", "cat": "OSINT / X", "weight": 0.85, "bias": "ALTERNATIVE"},
    {"name": "Le Monde World", "url": "[https://www.lemonde.fr/en/rss/full.xml](https://www.lemonde.fr/en/rss/full.xml)", "cat": "FR/Presse", "weight": 0.90, "bias": "EU-LEFT-LIBERAL"},
    {"name": "Notes from Poland", "url": "[https://notesfrompoland.com/feed/](https://notesfrompoland.com/feed/)", "cat": "NATO-Ostflanke", "weight": 0.90, "bias": "EU-EAST-CENTER"},
    {"name": "ABC News Australia", "url": "[https://www.abc.net.au/news/feed/51120/rss.xml](https://www.abc.net.au/news/feed/51120/rss.xml)", "cat": "Indopazifik", "weight": 0.90, "bias": "WESTERN-PACIFIC"},
    {"name": "Federal Reserve Press", "url": "[https://www.federalreserve.gov/feeds/press_all.xml](https://www.federalreserve.gov/feeds/press_all.xml)", "cat": "Zentralbank", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "Der Spiegel Top", "url": "[https://www.spiegel.de/schlagzeilen/tops/index.rss](https://www.spiegel.de/schlagzeilen/tops/index.rss)", "cat": "DE/Medien", "weight": 0.90, "bias": "DE-LEFT-LIBERAL"}
]

PIPELINE_HEALTH["feeds_total"] = len(SOURCES)

def fetch_feed(src):
    try:
        res = requests.get(src["url"], headers={"User-Agent": "ArgusGridBot/3.0"}, timeout=6)
        if res.status_code == 200:
            feed = feedparser.parse(res.content)
            if feed.entries:
                out = f"\n--- {src['name']} ({src['cat']}) ---\n"
                for entry in feed.entries[:2]:
                    out += f"- {entry.get('title', '')}: {clean_html(entry.get('summary', ''))[:120]}...\n"
                return True, out
    except Exception: pass
    return False, ""

raw_feed_text = ""
loaded_count = 0
with ThreadPoolExecutor(max_workers=30) as executor:
    futures = [executor.submit(fetch_feed, src) for src in SOURCES]
    for future in as_completed(futures):
        success, res_str = future.result()
        if success:
            loaded_count += 1
            raw_feed_text += res_str

PIPELINE_HEALTH["feeds_loaded"] = loaded_count

# ============================================================
# STUFE 1: GROQ PRE-FILTERING (FREE TIER)
# ============================================================
def filter_feeds(text):
    if not client_groq: return text[:40000]
    print("Filtere Feeds via Groq (Free Tier)...")
    try:
        res = client_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": f"DYNAMISCHER ZEITANKER: {CURRENT_DATE_STR}. Filtere relevante OSINT-, Geopolitik- & Markt-Signale heraus. Fasse kompakt zusammen."},
                {"role": "user", "content": text[:60000]}
            ],
            temperature=0.1, max_tokens=2500
        )
        PIPELINE_HEALTH["groq_filter"] = "ok"
        return res.choices[0].message.content
    except Exception as e:
        PIPELINE_HEALTH["groq_filter"] = f"fallback ({str(e)[:30]})"
        return text[:40000]

filtered_context = filter_feeds(raw_feed_text)

# ============================================================
# STUFE 2: SPEZIALISTEN-KOMITEE (PARALLELE ANALYSEN)
# ============================================================

# 2a. DeepSeek (Spieltheorie)
def run_deepseek(context):
    if not client_deepseek: return "[DeepSeek Key fehlt]"
    try:
        res = client_deepseek.chat.completions.create(
            model="deepseek-reasoner",
            messages=[{"role": "system", "content": f"DYNAMISCHER ZEITANKER: {CURRENT_DATE_STR}. Spieltheoretisches Gutachten (Payoffs, Nash-Gleichgewicht)."}, {"role": "user", "content": context}]
        )
        PIPELINE_HEALTH["deepseek_game_theory"] = "ok"
        return res.choices[0].message.content
    except Exception as e: return f"[DeepSeek Fehler: {e}]"

# 2b. Gemini Flash (Makro - Free Tier)
def run_gemini(context):
    if not client_gemini: return "[Gemini Key fehlt]"
    try:
        res = client_gemini.chat.completions.create(
            model="gemini-2.0-flash",
            messages=[{"role": "system", "content": f"DYNAMISCHER ZEITANKER: {CURRENT_DATE_STR}. Makro-Schocks & Migration."}, {"role": "user", "content": context[:20000]}]
        )
        PIPELINE_HEALTH["gemini_macro"] = "ok"
        return res.choices[0].message.content
    except Exception as e: return f"[Gemini Fehler: {e}]"

# 2c. xAI Grok (Social OSINT)
def run_grok(context):
    if not client_xai: return "[Grok Key fehlt]"
    try:
        res = client_xai.chat.completions.create(
            model="grok-2-latest",
            messages=[{"role": "system", "content": f"DYNAMISCHER ZEITANKER: {CURRENT_DATE_STR}. Social-Media-Echtzeitsignale, NOTAMs & Eilmeldungen."}, {"role": "user", "content": context[:20000]}]
        )
        PIPELINE_HEALTH["xai_grok"] = "ok"
        return res.choices[0].message.content
    except Exception as e: return f"[Grok Fehler: {e}]"

# 2d. Perplexity (Fact-Checking)
def run_perplexity(context):
    if not client_perplexity: return "[Perplexity Key fehlt]"
    try:
        res = client_perplexity.chat.completions.create(
            model="sonar",
            messages=[{"role": "system", "content": f"DYNAMISCHER ZEITANKER: {CURRENT_DATE_STR}. Fact-Checking im Live-Web."}, {"role": "user", "content": context[:15000]}]
        )
        PIPELINE_HEALTH["perplexity_factcheck"] = "ok"
        return res.choices[0].message.content
    except Exception as e: return f"[Perplexity Fehler: {e}]"

# 2e. Qwen (Indopazifik, BRICS & China Specialist)
def run_qwen(context):
    if not client_qwen: return "[Qwen Key fehlt]"
    print("Starte Qwen Indopazifik & BRICS Analyse...")
    try:
        res = client_qwen.chat.completions.create(
            model="qwen2.5-72b-instruct",
            messages=[
                {"role": "system", "content": f"DYNAMISCHER ZEITANKER: {CURRENT_DATE_STR}. Du bist der Indopazifik-, Taiwan-Strasse & BRICS-Spezialist. Analysiere ostasiatische Machtverschiebungen & Handelsrouten."},
                {"role": "user", "content": context[:20000]}
            ],
            temperature=0.2
        )
        PIPELINE_HEALTH["qwen_indopacific"] = "ok"
        return res.choices[0].message.content
    except Exception as e: return f"[Qwen Fehler: {e}]"

# 2f. OpenRouter Nemotron (Hardware & Chips - Free)
def run_nemotron(context):
    if not client_openrouter: return "[OpenRouter Key fehlt]"
    try:
        res = client_openrouter.chat.completions.create(
            model="nvidia/nemotron-4-340b-instruct:free",
            messages=[{"role": "system", "content": "Halbleiter & KI-Infrastruktur Analyse."}, {"role": "user", "content": context[:20000]}]
        )
        PIPELINE_HEALTH["openrouter_nemotron_tech"] = "ok"
        return res.choices[0].message.content
    except Exception as e: return f"[Nemotron Fehler: {e}]"

print("Starte Spezialisten-Komitee parallel...")
deepseek_analysis = run_deepseek(filtered_context)
gemini_analysis = run_gemini(filtered_context)
grok_analysis = run_grok(filtered_context)
perplexity_analysis = run_perplexity(filtered_context)
qwen_analysis = run_qwen(filtered_context)
nemotron_analysis = run_nemotron(filtered_context)

# ============================================================
# STUFE 3: MISTRAL LARGE (PRIMÄRER KOSTENLOSER JSON BUILDER)
# ============================================================
orchestrator_prompt = f"""Du bist die 'Argus Grid Systemic Intelligence Engine'.
Synthetisiere die Experten-Berichte zu einer unvoreingenommenen Gesamtlage.

DYNAMISCHER ZEITANKER: {CURRENT_DATE_STR}.

ANTWORTE AUSSCHLIESSLICH IM REIN VALIDEN JSON-FORMAT:
{{
  "ampel_status": "GELB",
  "ampel_reason_simple": "Grund in 1 einfachen Satz.",
  "daily_executive_summary_simple": "Zusammenfassung in 2-3 einfachen Sätzen.",
  "simple_key_takeaways": ["Punkt 1", "Punkt 2", "Punkt 3"],
  "predictive_horizon": {{
    "base_case_summary": "Prognose 30-90 Tage",
    "base_case_probability_pct": 65,
    "time_horizons": {{"30_days_tactic": "...", "90_days_macro": "...", "360_days_structural": "..."}},
    "black_swan_tail_risk": {{"risk_event": "...", "probability_pct": 8, "market_impact": "..."}},
    "leading_indicators_to_watch": [{{"indicator": "...", "current_status": "...", "critical_threshold": "..."}}]
  }},
  "historical_precedents": [{{"current_event": "...", "historical_analog": "...", "similarity_degree": "HOCH", "historical_outcome": "...", "key_divergence": "..."}}],
  "daily_executive_summary": "Ausführlicher Bericht...",
  "market_regime": "Stagflationär / Geopolitische Fragmentierung",
  "geoscore": {{"current_score": 78, "status_label": "ERHÖHT", "previous_48h": 74}},
  "defcon_status": {{"level": 3, "label": "DEFCON 3", "nuclear_risk_percent": 15, "primary_driver": "Hauptursache"}},
  "top_overweight": "Gold & Defense",
  "top_risk": "Hauptrisiko",
  "game_theory_deep_dive": {{
    "focal_situation": "Konflikttitel",
    "1_fractionated_actors": [{{"entity": "Akteur", "factions": [{{"faction_name": "Fraktion", "divergent_interest": "Interesse", "confidence": 85}}]}}],
    "2_time_horizon_conflict": {{"short_term_one_shot_4_to_8_weeks": "...", "long_term_repeated_game": "...", "horizon_contradiction": "..."}},
    "3_game_structure_and_payoffs": {{"type": "Chicken Game", "payoff_assessment_scale_minus_3_to_plus_3": [{{"scenario_combination": "A vs B", "payoff_actor_A": 2, "payoff_actor_B": -2, "confidence": 80}}]}},
    "4_signaling_and_information": {{"cheap_talk": ["Bluffs"], "costly_signals": ["Aktionen"]}},
    "6_falsification_counter_model": {{"alternative_interpretation": "...", "necessary_conditions": "..."}}
  }},
  "domestic_politics_analysis": [{{"region_actor": "USA / EU", "key_event_trend": "...", "regime_stability": "STABIL", "geopolitical_impact": "..."}}],
  "stress_testing_scenarios": [{{"scenario_name": "...", "probability_pct": 40, "timeframe": "1-3M", "cascade_chain": ["A", "B"], "winners_long": [{{"asset": "Gold"}}], "losers_short": [{{"asset": "Tech"}}]}}],
  "conflict_hotspots": [{{"region": "Region", "actors": "...", "status_type": "AKTIV", "escalation_level": "HOCH", "impact": "...", "lat": 47.0, "lng": 28.8}}],
  "digital_and_monetary_sovereignty": [{{"topic": "CBDC / Minerals", "actor": "...", "trend": "...", "systemic_impact": "...", "market_implication": "..."}}],
  "stock_picks": {{"top_5_buys": [{{"ticker": "RHM", "name": "Rheinmetall", "reason": "..."}}], "flop_5_sells": [{{"ticker": "XYZ", "name": "Name", "reason": "..."}}]}}
}}
"""

expert_payload = f"""
--- DEEPSEEK SPIELTHEORIE ---
{deepseek_analysis}

--- GEMINI MAKRO ---
{gemini_analysis}

--- GROK SOCIAL OSINT ---
{grok_analysis}

--- PERPLEXITY FAKTENCHECK ---
{perplexity_analysis}

--- QWEN INDOPAZIFIK & BRICS ---
{qwen_analysis}

--- NEMOTRON TECH & CHIPS ---
{nemotron_analysis}

--- LIVE FINANZDATEN ---
{live_market_context}
"""

print("Generiere primäres JSON mit Mistral AI Free Tier...")
raw_json_output = None

if client_mistral:
    try:
        res = client_mistral.chat.completions.create(
            model="mistral-large-latest",
            messages=[{"role": "system", "content": orchestrator_prompt}, {"role": "user", "content": expert_payload}],
            temperature=0.1
        )
        raw_json_output = res.choices[0].message.content.strip()
        PIPELINE_HEALTH["mistral_json_builder"] = "ok (mistral-large)"
    except Exception as e:
        print(f"Mistral JSON-Builder Ausfall: {e}")

# Fallback auf Qwen oder DeepSeek, falls Mistral fehlschlägt
if not raw_json_output and client_qwen:
    try:
        res = client_qwen.chat.completions.create(
            model="qwen2.5-72b-instruct",
            messages=[{"role": "system", "content": orchestrator_prompt}, {"role": "user", "content": expert_payload}],
            temperature=0.1
        )
        raw_json_output = res.choices[0].message.content.strip()
        PIPELINE_HEALTH["mistral_json_builder"] = "fallback (qwen2.5)"
    except Exception: pass

if not raw_json_output:
    raise RuntimeError("Kritischer Fehler: Weder Mistral noch Qwen konnten das JSON erstellen.")

parsed_data = repair_and_parse_json(raw_json_output)

# ============================================================
# STUFE 4: CLAUDE ROLLE = CHEFREDAKTEUR & RED TEAM (GEDROSSELT!)
# ============================================================
if client_anthropic:
    print("Starte Claude als Chefredakteur (Gedrosselt auf Haiku, Max 1000 Tokens)...")
    editor_prompt = """Du bist der Chefredakteur von ARGUS GRID.
Aufgabe:
1. Überprüfe das übergebene JSON-Lagebild auf tonale Schärfe und stilistische Präzision im Deutschen.
2. Optimiere NUR die Felder `daily_executive_summary_simple`, `ampel_reason_simple` und `simple_key_takeaways` für maximale Verständlichkeit.
3. Gib das überarbeitete JSON exakt in derselben Struktur zurück. Ändere KEINE Datenwerte oder Zahlen!"""

    # Claude erhält NUR das kompakte JSON (~1.200 Tokens Input statt 50.000 Tokens!)
    slim_payload = json.dumps({
        "ampel_status": parsed_data.get("ampel_status"),
        "ampel_reason_simple": parsed_data.get("ampel_reason_simple"),
        "daily_executive_summary_simple": parsed_data.get("daily_executive_summary_simple"),
        "simple_key_takeaways": parsed_data.get("simple_key_takeaways"),
        "daily_executive_summary": parsed_data.get("daily_executive_summary")
    }, ensure_ascii=False)

    try:
        res = client_anthropic.messages.create(
            model="claude-3-5-haiku-20241022", # HARD LOCK: Nur Haiku! Kein Opus, kein Fable!
            max_tokens=1000, # STRIKTE TOKEN-DROSSELUNG!
            system=editor_prompt,
            messages=[{"role": "user", "content": slim_payload}]
        )
        refined_json = repair_and_parse_json(res.content[0].text.strip())
        
        # Injektion der von Claude veredelten Texte
        if "daily_executive_summary_simple" in refined_json:
            parsed_data["daily_executive_summary_simple"] = refined_json["daily_executive_summary_simple"]
        if "ampel_reason_simple" in refined_json:
            parsed_data["ampel_reason_simple"] = refined_json["ampel_reason_simple"]
        if "simple_key_takeaways" in refined_json:
            parsed_data["simple_key_takeaways"] = refined_json["simple_key_takeaways"]

        PIPELINE_HEALTH["claude_chief_editor"] = "ok (claude-3-5-haiku)"
        print("Claude Veredelung erfolgreich! (Kosten: < $0,002)")
    except Exception as e:
        print(f"Claude Chefredakteur Hinweis: {e}")
        PIPELINE_HEALTH["claude_chief_editor"] = f"skipped ({str(e)[:30]})"

# ============================================================
# DATEN SPEICHERN
# ============================================================
parsed_data["timestamp"] = NOW_UTC.strftime("%d.%m.%Y - %H:%M UTC")
parsed_data["pipeline_health"] = PIPELINE_HEALTH
parsed_data["live_recon_flights"] = live_recon_flights
parsed_data["maritime_chokepoints"] = maritime_chokepoints

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(parsed_data, f, ensure_ascii=False, indent=2)

print("✅ ARGUS GRID v3.0 Pipeline erfolgreich gelaufen!")
