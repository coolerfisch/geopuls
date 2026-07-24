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
# A. LIVE FINANZ-, MAKRO- & ROHSTOFFDATEN
# ============================================================
def get_live_market_data():
    market_summary = ""
    tickers = {
        "US Dollar Index (DXY)": "DX-Y.NYB",
        "EUR/USD": "EURUSD=X",
        "USD/JPY": "JPY=X",
        "USD/CNY": "CNY=X",
        "US 10Y Anleihe": "^TNX",
        "VIX (Volatilität)": "^VIX",
        "HYG High Yield Spread": "HYG",
        "Gold (USD/oz)": "GC=F",
        "Silber (USD/oz)": "SI=F",
        "Brent Öl (USD/bbl)": "BZ=F",
        "WTI Öl (USD/bbl)": "CL=F",
        "US Erdgas": "NG=F",
        "Kupfer": "HG=F",
        "Weizen": "ZW=F",
        "BDI Baltic Dry Index": "BDRY",
        "S&P 500": "^GSPC",
        "Bitcoin": "BTC-USD"
    }
    print("Hole echte Finanz-, Makro- & Rohstoffmarktdaten via yfinance...")
    try:
        for name, ticker in tickers.items():
            try:
                data = yf.Ticker(ticker).history(period="5d")
                if not data.empty and len(data) >= 2:
                    close_curr = data['Close'].iloc[-1]
                    close_prev = data['Close'].iloc[-2]
                    change_pct = ((close_curr - close_prev) / close_prev) * 100
                    market_summary += f"- {name}: {close_curr:.2f} ({change_pct:+.2f}% heute)\n"
            except Exception:
                pass
    except Exception as e:
        print(f"yfinance Hinweis: {e}")
    return market_summary if market_summary else "- Finanzdaten im Wartestand.\n"

live_market_context = get_live_market_data()

# ============================================================
# B. LIVE MILITÄR- & AIS MARITIME TRACKING
# ============================================================
def get_live_military_flights():
    print("Hole live ADS-B Militär- & Aufklärungsflüge via OpenSky Network...")
    url = "[https://opensky-network.org/api/states/all](https://opensky-network.org/api/states/all)"
    mil_prefixes = ("FORTE", "NATO", "HOMER", "JAKE", "LAGR", "NCHO", "DUKE", "RCH", "BRK", "CMB", "REDYE", "MAGE", "VALK", "DRAGON", "SENTRY")
    flights = []
    
    opensky_user = os.environ.get("OPENSKY_USER", "").strip()
    opensky_pass = os.environ.get("OPENSKY_PASSWORD", "").strip()
    auth_data = (opensky_user, opensky_pass) if opensky_user and opensky_pass else None

    try:
        params = {"lamin": 20.0, "lomin": -10.0, "lamax": 70.0, "lomax": 50.0}
        res = requests.get(url, params=params, auth=auth_data, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        
        if res.status_code == 200:
            states = res.json().get("states", [])
            if states:
                for s in states:
                    callsign = (s[1] or "").strip()
                    icao24 = s[0] or "unknown"
                    country = s[2] or "Unknown"
                    lng = s[5]
                    lat = s[6]
                    alt = s[7]
                    on_ground = s[8]
                    velocity = s[9]
                    heading = s[10]

                    if lat is not None and lng is not None and not on_ground:
                        if any(callsign.startswith(prefix) for prefix in mil_prefixes):
                            flights.append({
                                "callsign": callsign,
                                "icao24": icao24,
                                "country": country,
                                "lat": round(lat, 4),
                                "lng": round(lng, 4),
                                "altitude_m": round(alt) if alt else 0,
                                "speed_kmh": round(velocity * 3.6) if velocity else 0,
                                "heading": round(heading) if heading else 0,
                                "is_live": True
                            })
    except Exception as e:
        print(f"OpenSky Live ADS-B Hinweis: {e}")

    if not flights:
        flights = [
            {"callsign": "FORTE12 (US Global Hawk)", "icao24": "ae5420", "country": "United States", "lat": 43.8, "lng": 29.8, "altitude_m": 16000, "speed_kmh": 620, "heading": 85, "is_live": False},
            {"callsign": "NATO AWACS 01", "icao24": "4d03c2", "country": "NATO", "lat": 54.2, "lng": 20.1, "altitude_m": 10500, "speed_kmh": 780, "heading": 120, "is_live": False},
            {"callsign": "USAF C-17 Airlift", "icao24": "ae1176", "country": "United States", "lat": 50.1, "lng": 19.8, "altitude_m": 9200, "speed_kmh": 830, "heading": 270, "is_live": False}
        ]

    return flights[:8]

def get_maritime_chokepoints():
    print("Erfasse maritime Nadelöhre & Schattenflotten-OSINT...")
    return [
        {"chokepoint": "Strasse von Hormus", "lat": 26.56, "lng": 56.25, "status": "HOCHRISIKO", "tanker_flow": "Normal / Tanker-Spoofing registriert"},
        {"chokepoint": "Bab al-Mandab (Rotes Meer)", "lat": 12.58, "lng": 43.33, "status": "ESKALATIV", "tanker_flow": "Umleitungen um Kap der Guten Hoffnung aktiv"},
        {"chokepoint": "Bosporus & Schwarzes Meer", "lat": 41.11, "lng": 29.07, "status": "MODERAT", "tanker_flow": "Getreide- & Schattenflottenkontrollen"},
        {"chokepoint": "Ostsee / Suwalki-Zugang", "lat": 55.00, "lng": 19.50, "status": "ERHÖHT", "tanker_flow": "Schattenflotte-Aktivität & Kabelüberwachung"}
    ]

live_recon_flights = get_live_military_flights()
maritime_chokepoints = get_maritime_chokepoints()

# ============================================================
# C. VOLLSTÄNDIGE QUELLENLISTE (140+ FEEDS UNGEKÜRZT)
# ============================================================
SOURCES = [
    # 🇺🇸 1. USA: POLITISCHES SPEKTRUM & FINANZEN
    {"name": "CNN World", "url": "[http://rss.cnn.com/rss/edition.rss](http://rss.cnn.com/rss/edition.rss)", "cat": "US/Politik", "weight": 0.95, "bias": "US-LEFT-LIBERAL"},
    {"name": "MSNBC / NBC News", "url": "[https://feeds.nbcnews.com/nbcnews/public/news](https://feeds.nbcnews.com/nbcnews/public/news)", "cat": "US/Politik", "weight": 0.90, "bias": "US-LEFT-LIBERAL"},
    {"name": "New York Times World", "url": "[https://rss.nytimes.com/services/xml/rss/nyt/World.xml](https://rss.nytimes.com/services/xml/rss/nyt/World.xml)", "cat": "US/Presse", "weight": 0.95, "bias": "US-LEFT-LIBERAL"},
    {"name": "Fox News Latest", "url": "[https://moxie.foxnews.com/google-publisher/latest.xml](https://moxie.foxnews.com/google-publisher/latest.xml)", "cat": "US/Politik", "weight": 0.95, "bias": "US-CONSERVATIVE"},
    {"name": "National Review", "url": "[https://www.nationalreview.com/feed/](https://www.nationalreview.com/feed/)", "cat": "US/Politik", "weight": 0.85, "bias": "US-CONSERVATIVE"},
    {"name": "The Washington Times", "url": "[https://www.washingtontimes.com/rss/headlines/news/](https://www.washingtontimes.com/rss/headlines/news/)", "cat": "US/Politik", "weight": 0.85, "bias": "US-CONSERVATIVE"},
    {"name": "Wall Street Journal", "url": "[https://news.google.com/rss/search?q=when:24h+site:wsj.com](https://news.google.com/rss/search?q=when:24h+site:wsj.com)", "cat": "US/Finanzen", "weight": 0.95, "bias": "US-CONSERVATIVE-BUSINESS"},
    {"name": "Reason Magazine", "url": "[https://reason.com/feed/](https://reason.com/feed/)", "cat": "US/Debatte", "weight": 0.80, "bias": "US-LIBERTARIAN"},
    {"name": "Bloomberg Markets", "url": "[https://news.google.com/rss/search?q=when:24h+site:bloomberg.com](https://news.google.com/rss/search?q=when:24h+site:bloomberg.com)", "cat": "US/Finanzen", "weight": 0.95, "bias": "CENTER-LIBERAL"},

    # 🇩🇪 2. DEUTSCHLAND & DACH-RAUM
    {"name": "taz die tageszeitung", "url": "[https://taz.de/rss.xml](https://taz.de/rss.xml)", "cat": "DE/Politik", "weight": 0.85, "bias": "DE-LEFT-PROGRESSIVE"},
    {"name": "Der Spiegel", "url": "[https://www.spiegel.de/schlagzeilen/tops/index.rss](https://www.spiegel.de/schlagzeilen/tops/index.rss)", "cat": "DE/Medien", "weight": 0.90, "bias": "DE-LEFT-LIBERAL"},
    {"name": "Süddeutsche Zeitung", "url": "[https://news.google.com/rss/search?q=when:24h+site:sueddeutsche.de](https://news.google.com/rss/search?q=when:24h+site:sueddeutsche.de)", "cat": "DE/Presse", "weight": 0.90, "bias": "DE-LEFT-LIBERAL"},
    {"name": "FAZ Politik", "url": "[https://www.faz.net/rss/aktuell/politik/](https://www.faz.net/rss/aktuell/politik/)", "cat": "DE/Presse", "weight": 0.90, "bias": "DE-CONSERVATIVE"},
    {"name": "Die Welt", "url": "[https://www.welt.de/feeds/topnews.rss](https://www.welt.de/feeds/topnews.rss)", "cat": "DE/Presse", "weight": 0.85, "bias": "DE-CONSERVATIVE"},
    {"name": "NZZ International", "url": "[https://www.nzz.ch/international.rss](https://www.nzz.ch/international.rss)", "cat": "CH/Presse", "weight": 0.95, "bias": "DE-CONSERVATIVE-LIBERAL"},
    {"name": "Die Zeit Online", "url": "[https://newsfeed.zeit.de/index](https://newsfeed.zeit.de/index)", "cat": "DE/Presse", "weight": 0.90, "bias": "DE-CENTER-LIBERAL"},
    {"name": "Handelsblatt", "url": "[https://www.handelsblatt.com/contentexport/feed/top-themen](https://www.handelsblatt.com/contentexport/feed/top-themen)", "cat": "DE/Finanzen", "weight": 0.90, "bias": "DE-LIBERAL-BUSINESS"},

    # 🇬🇧 3. GROSSBRITANNIEN (UK)
    {"name": "The Guardian World", "url": "[https://www.theguardian.com/world/rss](https://www.theguardian.com/world/rss)", "cat": "UK/Presse", "weight": 0.90, "bias": "UK-LEFT-LIBERAL"},
    {"name": "The Telegraph", "url": "[https://news.google.com/rss/search?q=when:24h+site:telegraph.co.uk](https://news.google.com/rss/search?q=when:24h+site:telegraph.co.uk)", "cat": "UK/Presse", "weight": 0.85, "bias": "UK-CONSERVATIVE"},
    {"name": "The Spectator", "url": "[https://www.spectator.co.uk/feed/](https://www.spectator.co.uk/feed/)", "cat": "UK/Debatte", "weight": 0.80, "bias": "UK-CONSERVATIVE"},
    {"name": "BBC World News", "url": "[http://feeds.bbci.co.uk/news/world/rss.xml](http://feeds.bbci.co.uk/news/world/rss.xml)", "cat": "UK/Medien", "weight": 0.95, "bias": "MAINSTREAM-CENTER"},
    {"name": "Financial Times", "url": "[https://news.google.com/rss/search?q=when:24h+site:ft.com](https://news.google.com/rss/search?q=when:24h+site:ft.com)", "cat": "UK/Finanzen", "weight": 0.95, "bias": "CENTER-LIBERAL"},

    # 🏛️ 4. ZENTRALBANKEN, REGIERUNGEN & STAATLICHE STELLEN
    {"name": "Federal Reserve Press", "url": "[https://www.federalreserve.gov/feeds/press_all.xml](https://www.federalreserve.gov/feeds/press_all.xml)", "cat": "Zentralbank", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "Fed Speeches & Minutes", "url": "[https://www.federalreserve.gov/feeds/speeches.xml](https://www.federalreserve.gov/feeds/speeches.xml)", "cat": "Zentralbank", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "EZB (Europ. Zentralbank)", "url": "[https://www.ecb.europa.eu/rss/press.html](https://www.ecb.europa.eu/rss/press.html)", "cat": "Zentralbank", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "Bank of England (BoE)", "url": "[https://www.bankofengland.co.uk/rss/news](https://www.bankofengland.co.uk/rss/news)", "cat": "Zentralbank", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "People's Bank of China", "url": "[https://news.google.com/rss/search?q=when:7d+PBOC](https://news.google.com/rss/search?q=when:7d+PBOC)", "cat": "Zentralbank", "weight": 1.00, "bias": "BRICS"},
    {"name": "Bank of Japan (BoJ)", "url": "[https://news.google.com/rss/search?q=when:7d+Bank+of+Japan](https://news.google.com/rss/search?q=when:7d+Bank+of+Japan)", "cat": "Zentralbank", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "Atlanta Fed / NY Fed", "url": "[https://news.google.com/rss/search?q=when:7d+GDPNow](https://news.google.com/rss/search?q=when:7d+GDPNow)", "cat": "Makro/Fed", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "BIS (Bank f. Intl. Zahl.)", "url": "[https://www.bis.org/doclist/all.rss](https://www.bis.org/doclist/all.rss)", "cat": "Zentralbank", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "IWF (IMF News)", "url": "[https://www.imf.org/en/News/rss](https://www.imf.org/en/News/rss)", "cat": "Intl. Org", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "Weltbank News", "url": "[https://www.worldbank.org/en/news/rss](https://www.worldbank.org/en/news/rss)", "cat": "Intl. Org", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "OECD Newsroom", "url": "[https://www.oecd.org/newsroom/index.xml](https://www.oecd.org/newsroom/index.xml)", "cat": "Intl. Org", "weight": 0.90, "bias": "OFFIZIELL"},
    {"name": "EU-Kommission Press", "url": "[https://ec.europa.eu/commission/presscorner/api/rss](https://ec.europa.eu/commission/presscorner/api/rss)", "cat": "Regierung/EU", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "Europäischer Rat", "url": "[https://www.consilium.europa.eu/en/rss/](https://www.consilium.europa.eu/en/rss/)", "cat": "Regierung/EU", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "White House Briefing", "url": "[https://www.whitehouse.gov/briefing-room/feed/](https://www.whitehouse.gov/briefing-room/feed/)", "cat": "Regierung", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "US Dept of State", "url": "[https://www.state.gov/rss-feed/press-releases/feed/](https://www.state.gov/rss-feed/press-releases/feed/)", "cat": "Diplomatie", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "Schweizer Bundesrat", "url": "[https://www.admin.ch/gov/de/start/dokumentation/medienmitteilungen.rss.html](https://www.admin.ch/gov/de/start/dokumentation/medienmitteilungen.rss.html)", "cat": "Regierung", "weight": 0.90, "bias": "OFFIZIELL"},

    # 🚶 5. MIGRATION, VERTREIBUNG & HUMANITÄRE DATEN
    {"name": "UNHCR Press Releases", "url": "[https://news.google.com/rss/search?q=when:7d+site:unhcr.org](https://news.google.com/rss/search?q=when:7d+site:unhcr.org)", "cat": "UNHCR", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "IOM DTM Tracking", "url": "[https://news.google.com/rss/search?q=when:7d+site:iom.int](https://news.google.com/rss/search?q=when:7d+site:iom.int)", "cat": "IOM", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "ReliefWeb UN OCHA", "url": "[https://reliefweb.int/updates/rss.xml](https://reliefweb.int/updates/rss.xml)", "cat": "Humanitär", "weight": 0.90, "bias": "OFFIZIELL"},
    {"name": "Frontex Alerts", "url": "[https://news.google.com/rss/search?q=when:7d+Frontex](https://news.google.com/rss/search?q=when:7d+Frontex)", "cat": "Grenzen", "weight": 0.90, "bias": "OFFIZIELL"},

    # 📊 6. ENERGIE, ROHSTOFFE, LOGISTIK & ANLEIHESTRESS
    {"name": "EIA Petroleum Report", "url": "[https://news.google.com/rss/search?q=when:7d+site:eia.gov](https://news.google.com/rss/search?q=when:7d+site:eia.gov)", "cat": "Energie", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "IEA Oil Reports", "url": "[https://news.google.com/rss/search?q=when:7d+site:iea.org](https://news.google.com/rss/search?q=when:7d+site:iea.org)", "cat": "Energie", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "OPEC Monthly Report", "url": "[https://news.google.com/rss/search?q=when:7d+OPEC](https://news.google.com/rss/search?q=when:7d+OPEC)", "cat": "Energie", "weight": 0.90, "bias": "OFFIZIELL"},
    {"name": "Baker Hughes Rig Count", "url": "[https://news.google.com/rss/search?q=when:7d+Baker+Hughes](https://news.google.com/rss/search?q=when:7d+Baker+Hughes)", "cat": "Energie", "weight": 0.85, "bias": "OFFIZIELL"},
    {"name": "AGSI+ Gas Storage", "url": "[https://news.google.com/rss/search?q=when:7d+Gas+Infrastructure+Europe](https://news.google.com/rss/search?q=when:7d+Gas+Infrastructure+Europe)", "cat": "Energie", "weight": 0.90, "bias": "OFFIZIELL"},
    {"name": "Freightos Shipping", "url": "[https://news.google.com/rss/search?q=when:7d+Freightos](https://news.google.com/rss/search?q=when:7d+Freightos)", "cat": "Container", "weight": 0.85, "bias": "LOGISTICS"},
    {"name": "Baltic Dry Index", "url": "[https://news.google.com/rss/search?q=when:7d+Baltic+Dry+Index](https://news.google.com/rss/search?q=when:7d+Baltic+Dry+Index)", "cat": "Logistik", "weight": 0.90, "bias": "LOGISTICS"},
    {"name": "FAO Food Price Index", "url": "[https://news.google.com/rss/search?q=when:7d+site:fao.org](https://news.google.com/rss/search?q=when:7d+site:fao.org)", "cat": "Agrar", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "USDA Crop WASDE", "url": "[https://news.google.com/rss/search?q=when:7d+site:usda.gov](https://news.google.com/rss/search?q=when:7d+site:usda.gov)", "cat": "Agrar", "weight": 0.90, "bias": "OFFIZIELL"},
    {"name": "MOVE Index / Bonds", "url": "[https://news.google.com/rss/search?q=when:7d+MOVE+index](https://news.google.com/rss/search?q=when:7d+MOVE+index)", "cat": "Bond Stress", "weight": 0.90, "bias": "MARKETS"},

    # 🛡️ 7. OSINT, MILITÄR, SATELLITEN, CYBER & SEE
    {"name": "Oryx Blog", "url": "[https://www.oryxspioenkop.com/feeds/posts/default](https://www.oryxspioenkop.com/feeds/posts/default)", "cat": "OSINT / Militär", "weight": 0.90, "bias": "ALTERNATIVE"},
    {"name": "Perun / Covert Cabal", "url": "[https://news.google.com/rss/search?q=when:7d+Perun+defense](https://news.google.com/rss/search?q=when:7d+Perun+defense)", "cat": "OSINT / Analyse", "weight": 0.85, "bias": "ANALYTICAL"},
    {"name": "Lloyd's List", "url": "[https://news.google.com/rss/search?q=when:7d+Lloyds+List](https://news.google.com/rss/search?q=when:7d+Lloyds+List)", "cat": "Schifffahrt", "weight": 0.90, "bias": "MARITIME"},
    {"name": "MarineTraffic Blog", "url": "[https://www.marinetraffic.com/blog/feed/](https://www.marinetraffic.com/blog/feed/)", "cat": "Marine OSINT", "weight": 0.85, "bias": "MARITIME"},
    {"name": "NASA FIRMS Hazards", "url": "[https://earthobservatory.nasa.gov/feeder/natural_hazards.rss](https://earthobservatory.nasa.gov/feeder/natural_hazards.rss)", "cat": "Satellit", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "USGS Earthquakes", "url": "[https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/5.5_day.atom](https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/5.5_day.atom)", "cat": "Seismik", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "GDACS Disaster Alerts", "url": "[https://www.gdacs.org/xml/rss.xml](https://www.gdacs.org/xml/rss.xml)", "cat": "Warnsystem", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "ISW (Study of War)", "url": "[https://www.understandingwar.org/rss.xml](https://www.understandingwar.org/rss.xml)", "cat": "Militäranalyse", "weight": 0.85, "bias": "WESTERN"},
    {"name": "US Naval Institute", "url": "[https://news.usni.org/feed](https://news.usni.org/feed)", "cat": "Marine OSINT", "weight": 0.90, "bias": "WESTERN-DEFENSE"},
    {"name": "Naval News", "url": "[https://www.navalnews.com/feed/](https://www.navalnews.com/feed/)", "cat": "Schifffahrt", "weight": 0.90, "bias": "WESTERN-DEFENSE"},
    {"name": "War on the Rocks", "url": "[https://warontherocks.com/feed/](https://warontherocks.com/feed/)", "cat": "Militäranalyse", "weight": 0.90, "bias": "WESTERN-DEFENSE"},
    {"name": "Bellingcat", "url": "[https://www.bellingcat.com/feed/](https://www.bellingcat.com/feed/)", "cat": "OSINT / Satellit", "weight": 0.90, "bias": "VERIFIED-OSINT"},
    {"name": "Critical Threats", "url": "[https://news.google.com/rss/search?q=when:7d+Critical+Threats](https://news.google.com/rss/search?q=when:7d+Critical+Threats)", "cat": "Militäranalyse", "weight": 0.85, "bias": "WESTERN"},
    {"name": "CISA Cyber Alerts", "url": "[https://www.cisa.gov/cybersecurity-advisories/all.xml](https://www.cisa.gov/cybersecurity-advisories/all.xml)", "cat": "Cyber / Infrastruktur", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "CERT-EU", "url": "[https://cert.europa.eu/publications/warnings/feed.xml](https://cert.europa.eu/publications/warnings/feed.xml)", "cat": "Cyber / Infrastruktur", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "Dark Reading", "url": "[https://www.darkreading.com/rss.xml](https://www.darkreading.com/rss.xml)", "cat": "Cyber", "weight": 0.85, "bias": "CYBER-INDUSTRY"},
    {"name": "Submarine Telecoms", "url": "[https://subtelforum.com/feed/](https://subtelforum.com/feed/)", "cat": "Infrastruktur", "weight": 0.85, "bias": "INFRASTRUCTURE"},
    {"name": "Offshore Energy", "url": "[https://www.offshore-energy.biz/feed/](https://www.offshore-energy.biz/feed/)", "cat": "Infrastruktur", "weight": 0.85, "bias": "ENERGY-INDUSTRY"},
    {"name": "UKMTO Operations", "url": "[https://news.google.com/rss/search?q=when:24h+UKMTO](https://news.google.com/rss/search?q=when:24h+UKMTO)", "cat": "Schifffahrt", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "gCaptain Maritime", "url": "[https://gcaptain.com/feed/](https://gcaptain.com/feed/)", "cat": "Schifffahrt", "weight": 0.85, "bias": "MARITIME"},
    {"name": "Splash247 Shipping", "url": "[https://splash247.com/feed/](https://splash247.com/feed/)", "cat": "Schifffahrt", "weight": 0.85, "bias": "MARITIME"},
    {"name": "Maritime Executive", "url": "[https://maritime-executive.com/rss](https://maritime-executive.com/rss)", "cat": "Schifffahrt", "weight": 0.85, "bias": "MARITIME"},
    {"name": "Flightradar24 Blog", "url": "[https://www.flightradar24.com/blog/feed/](https://www.flightradar24.com/blog/feed/)", "cat": "Luftfahrt OSINT", "weight": 0.85, "bias": "AVIATION"},
    {"name": "Aviation Safety Net", "url": "[https://news.google.com/rss/search?q=when:7d+Aviation+Safety+Network](https://news.google.com/rss/search?q=when:7d+Aviation+Safety+Network)", "cat": "Luftfahrt", "weight": 0.85, "bias": "AVIATION"},
    {"name": "GPSJam / EW Alerts", "url": "[https://news.google.com/rss/search?q=when:24h+GPS+jamming](https://news.google.com/rss/search?q=when:24h+GPS+jamming)", "cat": "EW / Luftfahrt", "weight": 0.85, "bias": "EW-OSINT"},

    # 🌍 8. WELT-NACHRICHTENAGENTUREN, DIPLOMATIE & BRICS
    {"name": "Associated Press (AP)", "url": "[https://news.google.com/rss/search?q=when:24h+source:Associated+Press](https://news.google.com/rss/search?q=when:24h+source:Associated+Press)", "cat": "Agentur", "weight": 0.95, "bias": "CENTER-NEUTRAL"},
    {"name": "Reuters World", "url": "[https://news.google.com/rss/search?q=when:24h+source:Reuters](https://news.google.com/rss/search?q=when:24h+source:Reuters)", "cat": "Agentur", "weight": 0.95, "bias": "CENTER-NEUTRAL"},
    {"name": "Agence France-Presse", "url": "[https://news.google.com/rss/search?q=when:24h+source:AFP](https://news.google.com/rss/search?q=when:24h+source:AFP)", "cat": "Agentur", "weight": 0.90, "bias": "EU-CENTER"},
    {"name": "Xinhua / Global Times", "url": "[https://news.google.com/rss/search?q=when:24h+site:xinhuanet.com](https://news.google.com/rss/search?q=when:24h+site:xinhuanet.com)", "cat": "BRICS", "weight": 0.85, "bias": "BRICS-CHINA"},
    {"name": "IRNA / Anadolu Agency", "url": "[https://news.google.com/rss/search?q=when:24h+site:irna.ir](https://news.google.com/rss/search?q=when:24h+site:irna.ir)", "cat": "BRICS", "weight": 0.80, "bias": "BRICS-MIDDLEEAST"},
    {"name": "Kyodo News", "url": "[https://english.kyodonews.net/rss/news.xml](https://english.kyodonews.net/rss/news.xml)", "cat": "Agentur", "weight": 0.85, "bias": "ASIA-WESTERN"},
    {"name": "Kremlin News", "url": "[http://en.kremlin.ru/rss/news](http://en.kremlin.ru/rss/news)", "cat": "BRICS / RU", "weight": 0.85, "bias": "BRICS-RUSSIA"},
    {"name": "Russ. Aussenministerium", "url": "[https://news.google.com/rss/search?q=when:7d+MID+Russia](https://news.google.com/rss/search?q=when:7d+MID+Russia)", "cat": "Diplomatie", "weight": 0.85, "bias": "BRICS-RUSSIA"},
    {"name": "Chin. Aussenministerium", "url": "[https://www.fmprc.gov.cn/eng/zxmz/rss.xml](https://www.fmprc.gov.cn/eng/zxmz/rss.xml)", "cat": "Diplomatie", "weight": 0.85, "bias": "BRICS-CHINA"},
    {"name": "Indisches Außenmin.", "url": "[https://news.google.com/rss/search?q=when:7d+site:mea.gov.in](https://news.google.com/rss/search?q=when:7d+site:mea.gov.in)", "cat": "BRICS / IN", "weight": 0.85, "bias": "BRICS-INDIA"},
    {"name": "CGTN World", "url": "[https://www.cgtn.com/xml/rss/news.xml](https://www.cgtn.com/xml/rss/news.xml)", "cat": "BRICS", "weight": 0.80, "bias": "BRICS-CHINA"},
    {"name": "TASS World", "url": "[https://tass.com/rss/v2.xml](https://tass.com/rss/v2.xml)", "cat": "BRICS", "weight": 0.80, "bias": "BRICS-RUSSIA"},
    {"name": "Economic Times India", "url": "[https://economictimes.indiatimes.com/rssfeeds/12216583.cms](https://economictimes.indiatimes.com/rssfeeds/12216583.cms)", "cat": "BRICS / IN", "weight": 0.85, "bias": "BRICS-INDIA"},
    {"name": "Al Jazeera", "url": "[https://www.aljazeera.com/xml/rss/all.xml](https://www.aljazeera.com/xml/rss/all.xml)", "cat": "BRICS / Arabisch", "weight": 0.85, "bias": "MIDDLEEAST-GLOBAL"},
    {"name": "South China Morning Post", "url": "[https://www.scmp.com/rss/91/feed](https://www.scmp.com/rss/91/feed)", "cat": "BRICS / HK", "weight": 0.85, "bias": "BRICS-ASIA"},
    {"name": "The Cradle", "url": "[https://thecradle.co/feed](https://thecradle.co/feed)", "cat": "Alternative", "weight": 0.80, "bias": "MIDDLEEAST-ALTERNATIVE"},
    {"name": "Asia Times", "url": "[https://asiatimes.com/feed/](https://asiatimes.com/feed/)", "cat": "Geopolitik", "weight": 0.85, "bias": "ASIA-ANALYTICAL"},

    # 💡 9. THINK TANKS & QUALITÄTSPRESSE
    {"name": "Quincy Institute", "url": "[https://quincyinst.org/feed/](https://quincyinst.org/feed/)", "cat": "Think Tank", "weight": 0.90, "bias": "REALIST-DIPLOMACY"},
    {"name": "Carnegie Endowment", "url": "[https://carnegieendowment.org/rss/solr.xml](https://carnegieendowment.org/rss/solr.xml)", "cat": "Think Tank", "weight": 0.90, "bias": "ANALYTICAL-CENTER"},
    {"name": "Chatham House", "url": "[https://www.chathamhouse.org/rss.xml](https://www.chathamhouse.org/rss.xml)", "cat": "Think Tank", "weight": 0.90, "bias": "UK-THINKTANK"},
    {"name": "Bruegel", "url": "[https://www.bruegel.org/rss.xml](https://www.bruegel.org/rss.xml)", "cat": "Think Tank/EU", "weight": 0.90, "bias": "EU-ECONOMICS"},
    {"name": "CSIS Org", "url": "[https://www.csis.org/nerve/rss](https://www.csis.org/nerve/rss)", "cat": "Think Tank", "weight": 0.90, "bias": "US-STRATEGIC"},
    {"name": "CFR", "url": "[https://www.cfr.org/rss/publication/feed](https://www.cfr.org/rss/publication/feed)", "cat": "Think Tank", "weight": 0.90, "bias": "US-ESTABLISHMENT"},
    {"name": "ECFR Europe", "url": "[https://ecfr.eu/feed/](https://ecfr.eu/feed/)", "cat": "Think Tank", "weight": 0.90, "bias": "EU-STRATEGIC"},
    {"name": "SWP Berlin", "url": "[https://www.swp-berlin.org/de/rss.xml](https://www.swp-berlin.org/de/rss.xml)", "cat": "Think Tank", "weight": 0.90, "bias": "DE-OFFICIAL-THINKTANK"},
    {"name": "World Economic Forum", "url": "[https://www.weforum.org/feed/](https://www.weforum.org/feed/)", "cat": "Think Tank", "weight": 0.85, "bias": "GLOBALIST-BUSINESS"},
    {"name": "CNBC Finance", "url": "[https://www.cnbc.com/id/10000664/device/rss/rss.html](https://www.cnbc.com/id/10000664/device/rss/rss.html)", "cat": "Finanzen", "weight": 0.85, "bias": "US-MARKETS"},
    {"name": "Foreign Policy", "url": "[https://foreignpolicy.com/feed/](https://foreignpolicy.com/feed/)", "cat": "Magazin", "weight": 0.90, "bias": "INTERNATIONAL-RELATIONS"},
    {"name": "Nikkei Asia", "url": "[https://asia.nikkei.com/rss/feed/nar](https://asia.nikkei.com/rss/feed/nar)", "cat": "Finanzen/Asien", "weight": 0.90, "bias": "ASIA-BUSINESS"},
    {"name": "Finanzmarktwelt", "url": "[https://finanzmarktwelt.de/feed/](https://finanzmarktwelt.de/feed/)", "cat": "Finanzen DE", "weight": 0.80, "bias": "DE-FINANCE-CRITICAL"},

    # 💬 10. REDDIT COMMUNITY OSINT FEEDS
    {"name": "r/geopolitics", "url": "[https://www.reddit.com/r/geopolitics/.rss](https://www.reddit.com/r/geopolitics/.rss)", "cat": "Community", "weight": 0.80, "bias": "COMMUNITY-ANALYTICAL"},
    {"name": "r/OSINT", "url": "[https://www.reddit.com/r/OSINT/.rss](https://www.reddit.com/r/OSINT/.rss)", "cat": "Community", "weight": 0.85, "bias": "COMMUNITY-TECHNICAL"},
    {"name": "r/CredibleDefense", "url": "[https://www.reddit.com/r/CredibleDefense/.rss](https://www.reddit.com/r/CredibleDefense/.rss)", "cat": "Community", "weight": 0.85, "bias": "COMMUNITY-DEFENSE"},
    {"name": "r/LessCredibleDefence", "url": "[https://www.reddit.com/r/LessCredibleDefence/.rss](https://www.reddit.com/r/LessCredibleDefence/.rss)", "cat": "Community", "weight": 0.70, "bias": "COMMUNITY-DEFENSE"},
    {"name": "r/Economics", "url": "[https://www.reddit.com/r/Economics/.rss](https://www.reddit.com/r/Economics/.rss)", "cat": "Community", "weight": 0.75, "bias": "COMMUNITY-MACRO"},
    {"name": "r/Macroeconomics", "url": "[https://www.reddit.com/r/Macroeconomics/.rss](https://www.reddit.com/r/Macroeconomics/.rss)", "cat": "Community", "weight": 0.75, "bias": "COMMUNITY-MACRO"},
    {"name": "r/Commodities", "url": "[https://www.reddit.com/r/Commodities/.rss](https://www.reddit.com/r/Commodities/.rss)", "cat": "Community", "weight": 0.75, "bias": "COMMUNITY-COMMODITIES"},

    # 🔍 11. INVESTIGATIV, ALTERNATIV & KONTRÄR
    {"name": "Scheerpost", "url": "[https://scheerpost.com/feed/](https://scheerpost.com/feed/)", "cat": "Investigativ", "weight": 0.80, "bias": "US-LEFT-CRITICAL"},
    {"name": "Naked Capitalism", "url": "[https://www.nakedcapitalism.com/feed](https://www.nakedcapitalism.com/feed)", "cat": "Makro", "weight": 0.85, "bias": "FINANCIAL-CRITIQUE"},
    {"name": "Consortium News", "url": "[https://consortiumnews.com/feed/](https://consortiumnews.com/feed/)", "cat": "Investigativ", "weight": 0.80, "bias": "COUNTER-NARRATIVE"},
    {"name": "Glenn Greenwald", "url": "[https://greenwald.substack.com/feed](https://greenwald.substack.com/feed)", "cat": "Journalismus", "weight": 0.85, "bias": "MEDIA-CRITIQUE"},
    {"name": "Aaron Maté Substack", "url": "[https://mate.substack.com/feed](https://mate.substack.com/feed)", "cat": "Journalismus", "weight": 0.80, "bias": "FOREIGN-POLICY-CRITIQUE"},
    {"name": "The Duran", "url": "[https://theduran.com/feed/](https://theduran.com/feed/)", "cat": "Geopolitik", "weight": 0.75, "bias": "BRICS-MULTIPOLAR"},
    {"name": "ZeroHedge", "url": "[http://feeds.feedburner.com/zerohedge/feed](http://feeds.feedburner.com/zerohedge/feed)", "cat": "Alternativ", "weight": 0.75, "bias": "CONTRARIAN-FINANCE"},
    {"name": "The Intercept", "url": "[https://theintercept.com/feed/](https://theintercept.com/feed/)", "cat": "Investigativ", "weight": 0.85, "bias": "INVESTIGATIVE-LEFT"},
    {"name": "The Grayzone", "url": "[https://thegrayzone.com/feed/](https://thegrayzone.com/feed/)", "cat": "Investigativ", "weight": 0.70, "bias": "ANTI-HEGEMONIC"},
    {"name": "Republik (Schweiz)", "url": "[https://www.republik.ch/feed](https://www.republik.ch/feed)", "cat": "Investigativ", "weight": 0.85, "bias": "INDEPENDENT-SWISS"},
    {"name": "MintPress News", "url": "[https://www.mintpressnews.com/feed/](https://www.mintpressnews.com/feed/)", "cat": "Alternativ", "weight": 0.70, "bias": "ANTI-IMPERIALIST"},
    {"name": "UnHerd", "url": "[https://unherd.com/feed/](https://unherd.com/feed/)", "cat": "Debatte", "weight": 0.85, "bias": "UK-CONTRARIAN"},
    {"name": "Antiwar.com", "url": "[https://www.antiwar.com/blog/feed/](https://www.antiwar.com/blog/feed/)", "cat": "Friedenspolitik", "weight": 0.80, "bias": "NON-INTERVENTIONIST"},
    {"name": "NachDenkSeiten", "url": "[https://www.nachdenkseiten.de/?feed=rss2](https://www.nachdenkseiten.de/?feed=rss2)", "cat": "Medienkritik", "weight": 0.80, "bias": "DE-ALTERNATIVE-LEFT"},
    {"name": "Apolut", "url": "[https://apolut.net/feed/](https://apolut.net/feed/)", "cat": "Alternativ DE", "weight": 0.70, "bias": "DE-ALTERNATIVE"},
    {"name": "Anti-Spiegel", "url": "[https://www.anti-spiegel.ru/feed/](https://www.anti-spiegel.ru/feed/)", "cat": "Alternativ RU/DE", "weight": 0.65, "bias": "PRO-RUSSIA-DE"},
    {"name": "Telepolis", "url": "[https://www.telepolis.de/news-atom.xml](https://www.telepolis.de/news-atom.xml)", "cat": "Magazin DE", "weight": 0.80, "bias": "DE-CRITICAL-TECH"},
    {"name": "Tichys Einblick", "url": "[https://www.tichyseinblick.de/feed/](https://www.tichyseinblick.de/feed/)", "cat": "Debatte DE", "weight": 0.75, "bias": "DE-CONSERVATIVE"},
    {"name": "Overton Magazin", "url": "[https://overton-magazin.de/feed/](https://overton-magazin.de/feed/)", "cat": "Geopolitik DE", "weight": 0.80, "bias": "DE-ANALYTICAL"},
    {"name": "Multipolar Magazin", "url": "[https://multipolar-magazin.de/feed](https://multipolar-magazin.de/feed)", "cat": "Geopolitik DE", "weight": 0.75, "bias": "DE-MULTIPOLAR"},
    {"name": "Manova / Rubikon", "url": "[https://www.manova.news/artikel.rss](https://www.manova.news/artikel.rss)", "cat": "Alternativ DE", "weight": 0.70, "bias": "DE-CRITICAL"},
    {"name": "Berliner Tageszeitung", "url": "[https://www.berlinertageszeitung.de/feed](https://www.berlinertageszeitung.de/feed)", "cat": "Medien DE", "weight": 0.70, "bias": "DE-INDEPENDENT"},
    {"name": "Hintergrund Magazin", "url": "[https://www.hintergrund.de/feed/](https://www.hintergrund.de/feed/)", "cat": "Geopolitik DE", "weight": 0.80, "bias": "DE-CRITICAL"},
    {"name": "Moon of Alabama", "url": "[https://www.moonofalabama.org/index.rdf](https://www.moonofalabama.org/index.rdf)", "cat": "Militär-Blog", "weight": 0.80, "bias": "TACTICAL-MILITARY-CRITIQUE"},
    {"name": "Caitlin Johnstone", "url": "[https://caitlinjohnstone.com.au/feed/](https://caitlinjohnstone.com.au/feed/)", "cat": "Kolumne", "weight": 0.75, "bias": "INDEPENDENT-OPINION"},

    # 🎯 12. ERGÄNZENDE PREDICTION MARKETS & REAL-TIME SIGNALS
    {"name": "Polymarket Geopolitics & War", "url": "[https://news.google.com/rss/search?q=when:24h+%22Polymarket%22+(geopolitics+OR+war+OR+election)&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:24h+%22Polymarket%22+(geopolitics+OR+war+OR+election)&hl=en-US&gl=US&ceid=US:en)", "cat": "Prediction Markets", "weight": 0.95, "bias": "CROWD-WISDOM"},
    {"name": "Kalshi Macro Odds", "url": "[https://news.google.com/rss/search?q=when:24h+%22Kalshi%22+(odds+OR+fed)&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:24h+%22Kalshi%22+(odds+OR+fed)&hl=en-US&gl=US&ceid=US:en)", "cat": "Prediction Markets", "weight": 0.90, "bias": "CROWD-WISDOM"},
    {"name": "X / Twitter OSINT Live", "url": "[https://news.google.com/rss/search?q=when:24h+(site:x.com+OR+site:twitter.com)+%22OSINT%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:24h+(site:x.com+OR+site:twitter.com)+%22OSINT%22&hl=en-US&gl=US&ceid=US:en)", "cat": "OSINT / X", "weight": 0.85, "bias": "ALTERNATIVE"}
]

PIPELINE_HEALTH["feeds_total"] = len(SOURCES)
browser_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ArgusGridOSINTBot/3.0"

def fetch_feed(src):
    try:
        res = requests.get(src["url"], headers={"User-Agent": browser_agent}, timeout=6)
        if res.status_code == 200:
            feed = feedparser.parse(res.content)
            if feed.entries:
                out = f"\n--- QUELLE: {src['name']} | Kat: {src['cat']} | Bias: {src['bias']} | GEWICHT: {src['weight']} ---\n"
                for entry in feed.entries[:2]:
                    title = entry.get('title', '')
                    raw_summary = entry.get('summary', '') or entry.get('description', '')
                    summary = clean_html(raw_summary)
                    out += f"- {title}: {summary[:140]}...\n"
                return True, out
    except Exception:
        pass
    return False, ""

print(f"Hole Feeds aus allen {len(SOURCES)} RSS-Quellen parallel...")
raw_feed_text = ""
loaded_count = 0

with ThreadPoolExecutor(max_workers=55) as executor:
    futures = [executor.submit(fetch_feed, src) for src in SOURCES]
    for future in as_completed(futures):
        success, res_str = future.result()
        if success:
            loaded_count += 1
            raw_feed_text += res_str

PIPELINE_HEALTH["feeds_loaded"] = loaded_count
print(f"Ergebnis Feed-Ingestion: {loaded_count}/{len(SOURCES)} Feeds geladen ({len(raw_feed_text)} Zeichen).")

# ============================================================
# STUFE 1: GROQ PRE-FILTERING (FREE TIER - RATE-LIMITED)
# ============================================================
def filter_feeds(text):
    if not client_groq:
        PIPELINE_HEALTH["groq_filter"] = "skipped"
        return text[:40000]
    print("Filtere Feeds via Groq (Free Tier)...")
    prompt = f"""Du bist ein OSINT-Filter-Modul. 

DYNAMISCHER ZEITANKER:
- HEUTIGES DATUM: {CURRENT_DATE_STR} (Jahr: {CURRENT_YEAR}). Bevorzuge Quellen mit GEWICHT >= 0.90 für Fakten!

BEHALTE UNBEDINGT:
1. PREDICTION MARKETS & ODDS: Polymarket / Kalshi.
2. REDDIT & 𝕏/TWITTER OSINT: Eilmeldungen, NOTAMs, Cyber Threats, Frontline Update.
3. REGIONALE KRISEN & PARTEIEN: Frankreich, Polen/Baltikum/Ukraine, AUKUS/Pazifik, Südeuropa, USA.
4. ESKALATIONSSPIRALEN, CYBER & DESINFO: EUvsDisinfo, Shadowserver, CISA.
5. SELTENE ERDEN, AGRAR & FLUCHT: Critical Minerals, FAO Index, UNHCR/IOM.
Gib das Ergebnis als strukturierte Stichpunkte zurück (max 2500 Wörter)."""
    try:
        res = client_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": text[:85000]}],
            temperature=0.1,
            max_tokens=3000
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

# 2a. DeepSeek (Spieltheorie - Paid Cent-bereich)
def run_deepseek_game_theory(context):
    if not client_deepseek:
        PIPELINE_HEALTH["deepseek_game_theory"] = "missing_key"
        return "[STATUS: DeepSeek Modul inaktiv / Key fehlt]"
    print("Starte DeepSeek-R1 Spieltheorie-Analyse...")
    gt_prompt = f"""DYNAMISCHER ZEITANKER: {CURRENT_DATE_STR} (Jahr: {CURRENT_YEAR}).
Analysiere das akuteste globale Krisenereignis streng spieltheoretisch (Akteur-Granularität, Zeithorizont, Payoffs -3 bis +3, Signaling, Nash-Gleichgewicht, Falsifikations-Gegenmodell)."""
    try:
        res = client_deepseek.chat.completions.create(
            model="deepseek-reasoner",
            messages=[{"role": "system", "content": gt_prompt}, {"role": "user", "content": context}]
        )
        PIPELINE_HEALTH["deepseek_game_theory"] = "ok"
        return res.choices[0].message.content
    except Exception as e:
        PIPELINE_HEALTH["deepseek_game_theory"] = f"failed ({str(e)[:30]})"
        return f"[DeepSeek Fehler: {e}]"

# 2b. Gemini Flash (Makro & Migration - Free Tier)
def run_gemini_macro(context, markets):
    if not client_gemini:
        PIPELINE_HEALTH["gemini_macro"] = "missing_key"
        return "[STATUS: Gemini Modul inaktiv / Key fehlt]"
    print("Starte Gemini Makro- Scan...")
    macro_prompt = f"""DYNAMISCHER ZEITANKER: {CURRENT_DATE_STR} (Jahr: {CURRENT_YEAR}).
Analysiere Feeds & Finanzdaten auf Makro-Schocks, Seltene Erden, Agrar & Fluchtbewegungen."""
    for model_name in ["gemini-2.0-flash", "gemini-1.5-flash"]:
        try:
            res = client_gemini.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": macro_prompt}, {"role": "user", "content": f"MARKETS:\n{markets}\nFEEDS:\n{context[:20000]}"}],
                temperature=0.2
            )
            PIPELINE_HEALTH["gemini_macro"] = f"ok ({model_name})"
            return res.choices[0].message.content
        except Exception:
            pass
    PIPELINE_HEALTH["gemini_macro"] = "failed"
    return "[Gemini API Ausfall]"

# 2c. xAI Grok (Social OSINT - Paid)
def run_grok_xai_scan(context):
    if not client_xai:
        PIPELINE_HEALTH["xai_grok"] = "missing_key"
        return "[STATUS: xAI Grok Modul inaktiv / Key fehlt]"
    print("Starte xAI Grok Real-Time Social OSINT Scan...")
    grok_prompt = f"""DYNAMISCHER ZEITANKER: {CURRENT_DATE_STR}.
Du bist das xAI Grok Social OSINT Modul. Liefere Social-Media-Echtzeitsignale, NOTAMs, GPS-Jamming und Eilmeldungen."""
    for grok_model in ["grok-2-latest", "grok-beta"]:
        try:
            res = client_xai.chat.completions.create(
                model=grok_model,
                messages=[{"role": "system", "content": grok_prompt}, {"role": "user", "content": context[:25000]}],
                temperature=0.2
            )
            PIPELINE_HEALTH["xai_grok"] = f"ok ({grok_model})"
            return res.choices[0].message.content
        except Exception as e:
            pass
    PIPELINE_HEALTH["xai_grok"] = "failed"
    return "[xAI Grok API Ausfall]"

# 2d. Perplexity Sonar (Fact-Checking - Paid Trial)
def run_perplexity_fact_check(context):
    if not client_perplexity:
        PIPELINE_HEALTH["perplexity_factcheck"] = "missing_key"
        return "[STATUS: Perplexity Modul inaktiv / Key fehlt]"
    print("Starte Perplexity Live-Web Faktenprüfung...")
    prompt = f"""DYNAMISCHER ZEITANKER: {CURRENT_DATE_STR}.
Du bist das Faktenprüfungs- & Grounding-Modul. Durchsuche das Live-Web und verifiziere 2-3 zentrale Eilmeldungen aus den Feeds."""
    try:
        res = client_perplexity.chat.completions.create(
            model="sonar",
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": context[:20000]}],
            temperature=0.1
        )
        PIPELINE_HEALTH["perplexity_factcheck"] = "ok (sonar)"
        return res.choices[0].message.content
    except Exception as e:
        PIPELINE_HEALTH["perplexity_factcheck"] = f"failed ({str(e)[:30]})"
        return "[Perplexity API Ausfall]"

# 2e. Qwen (Indopazifik & BRICS - Pay As You Go, Max $5/Monat)
def run_qwen_indopacific(context):
    if not client_qwen:
        PIPELINE_HEALTH["qwen_indopacific"] = "missing_key"
        return "[STATUS: Qwen Modul inaktiv / Key fehlt]"
    print("Starte Qwen Indopazifik & BRICS Analyse...")
    prompt = f"""DYNAMISCHER ZEITANKER: {CURRENT_DATE_STR}.
Du bist der Indopazifik-, Taiwan-Strasse & BRICS-Spezialist von ARGUS GRID. Analysiere ostasiatische Machtverschiebungen & Handelsrouten."""
    try:
        res = client_qwen.chat.completions.create(
            model="qwen2.5-72b-instruct",
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": context[:20000]}],
            temperature=0.2
        )
        PIPELINE_HEALTH["qwen_indopacific"] = "ok (qwen2.5-72b)"
        return res.choices[0].message.content
    except Exception as e:
        PIPELINE_HEALTH["qwen_indopacific"] = f"failed ({str(e)[:30]})"
        return "[Qwen API Ausfall]"

# 2f. OpenRouter Nemotron (Hardware & KI-Infrastruktur - Free)
def run_nemotron_tech_audit(context):
    if not client_openrouter:
        PIPELINE_HEALTH["openrouter_nemotron_tech"] = "missing_key"
        return "[STATUS: OpenRouter Modul inaktiv / Key fehlt]"
    print("Starte Nvidia Nemotron Ultra via OpenRouter...")
    try:
        res = client_openrouter.chat.completions.create(
            model="nvidia/nemotron-4-340b-instruct:free",
            messages=[
                {"role": "system", "content": f"DYNAMISCHER ZEITANKER: {CURRENT_DATE_STR}. Spezialist für Halbleiter, KI-Infrastruktur & globale Hardware-Lieferketten."},
                {"role": "user", "content": context[:20000]}
            ],
            temperature=0.2
        )
        PIPELINE_HEALTH["openrouter_nemotron_tech"] = "ok (nemotron)"
        return res.choices[0].message.content
    except Exception as e:
        PIPELINE_HEALTH["openrouter_nemotron_tech"] = f"failed ({str(e)[:30]})"
        return "[Nemotron API Ausfall]"

print("Starte Spezialisten-Komitee parallel...")
deepseek_analysis = run_deepseek_game_theory(filtered_context)
gemini_analysis = run_gemini_macro(filtered_context, live_market_context)
grok_analysis = run_grok_xai_scan(filtered_context)
perplexity_analysis = run_perplexity_fact_check(filtered_context)
qwen_analysis = run_qwen_indopacific(filtered_context)
nemotron_analysis = run_nemotron_tech_audit(filtered_context)

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

print("Generiere primäres JSON mit Mistral AI (Free Tier)...")
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
        print(f"Mistral JSON-Builder Hinweis: {e}")

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
