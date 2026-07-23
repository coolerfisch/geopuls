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
# API CLIENTS INITIALISIERUNG
# ============================================================
groq_key = os.environ.get("GROQ_API_KEY", "").strip().strip('"').strip("'")
anth_key = os.environ.get("ANTHROPIC_API_KEY", "").strip().strip('"').strip("'")
gemini_key = os.environ.get("GEMINI_API_KEY", "").strip().strip('"').strip("'")
deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip().strip('"').strip("'")

client_groq = Groq(api_key=groq_key) if groq_key else None
client_anthropic = anthropic.Anthropic(api_key=anth_key) if anth_key else None

# Gemini Client (Google AI Studio API via OpenAI-Schnittstelle)
client_gemini = OpenAI(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    api_key=gemini_key
) if gemini_key else None

# DeepSeek Direkt-Client (api.deepseek.com)
client_deepseek = OpenAI(
    base_url="https://api.deepseek.com",
    api_key=deepseek_key
) if deepseek_key else None

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
# B. LIVE MILITÄR- & RECON-FLUGDATEN (OPENSKY NETWORK ADS-B)
# ============================================================
def get_live_military_flights():
    print("Hole live ADS-B Militär- & Aufklärungsflüge via OpenSky Network...")
    url = "[https://opensky-network.org/api/states/all](https://opensky-network.org/api/states/all)"
    mil_prefixes = ("FORTE", "NATO", "HOMER", "JAKE", "LAGR", "NCHO", "DUKE", "RCH", "BRK", "CMB", "REDYE", "MAGE", "VALK", "DRAGON", "SENTRY")
    flights = []
    
    # OpenSky Login aus Umgebungsvariablen (Secrets) einlesen
    opensky_user = os.environ.get("OPENSKY_USER", "").strip()
    opensky_pass = os.environ.get("OPENSKY_PASSWORD", "").strip()
    auth_data = (opensky_user, opensky_pass) if opensky_user and opensky_pass else None

    try:
        # Bounding Box: Europa, Schwarzes Meer, Ost-Mittelmeer, Nahost (Lat 20-70, Lng -10-50)
        params = {"lamin": 20.0, "lomin": -10.0, "lamax": 70.0, "lomax": 50.0}
        
        # Abfrage mit Authentifizierung für höhere Rate Limits
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
                    alt = s[7]       # in Metern
                    on_ground = s[8]
                    velocity = s[9]  # in m/s
                    heading = s[10]  # True Track Grad

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

    # Fallback-Daten, falls Transponder stummgeschaltet sind oder API-Limit greift
    if not flights:
        print("Hinweis: Transponder passiv oder API-Limit. Nutze simulierte OSINT-Patrouillen.")
        flights = [
            {"callsign": "FORTE12 (US Global Hawk)", "icao24": "ae5420", "country": "United States", "lat": 43.8, "lng": 29.8, "altitude_m": 16000, "speed_kmh": 620, "heading": 85, "is_live": False},
            {"callsign": "NATO AWACS 01", "icao24": "4d03c2", "country": "NATO", "lat": 54.2, "lng": 20.1, "altitude_m": 10500, "speed_kmh": 780, "heading": 120, "is_live": False},
            {"callsign": "USAF C-17 Airlift", "icao24": "ae1176", "country": "United States", "lat": 50.1, "lng": 19.8, "altitude_m": 9200, "speed_kmh": 830, "heading": 270, "is_live": False}
        ]

    return flights[:8]

live_recon_flights = get_live_military_flights()

# ============================================================
# C. ERWEITERTER, BALANCIERTER QUELLENPOOL (140+ FEEDS)
# ============================================================
SOURCES = [
    # 🇺🇸 USA: POLITISCHES SPEKTRUM (DEMOKRATEN, REPUBLIKANER, LIBERTÄR)
    {"name": "CNN World", "url": "[http://rss.cnn.com/rss/edition.rss](http://rss.cnn.com/rss/edition.rss)", "cat": "US/Politik", "weight": 0.95, "bias": "US-LEFT-LIBERAL"},
    {"name": "MSNBC / NBC News", "url": "[https://feeds.nbcnews.com/nbcnews/public/news](https://feeds.nbcnews.com/nbcnews/public/news)", "cat": "US/Politik", "weight": 0.90, "bias": "US-LEFT-LIBERAL"},
    {"name": "New York Times World", "url": "[https://rss.nytimes.com/services/xml/rss/nyt/World.xml](https://rss.nytimes.com/services/xml/rss/nyt/World.xml)", "cat": "US/Presse", "weight": 0.95, "bias": "US-LEFT-LIBERAL"},
    {"name": "Fox News Latest", "url": "[https://moxie.foxnews.com/google-publisher/latest.xml](https://moxie.foxnews.com/google-publisher/latest.xml)", "cat": "US/Politik", "weight": 0.95, "bias": "US-CONSERVATIVE"},
    {"name": "National Review", "url": "[https://www.nationalreview.com/feed/](https://www.nationalreview.com/feed/)", "cat": "US/Politik", "weight": 0.85, "bias": "US-CONSERVATIVE"},
    {"name": "The Washington Times", "url": "[https://www.washingtontimes.com/rss/headlines/news/](https://www.washingtontimes.com/rss/headlines/news/)", "cat": "US/Politik", "weight": 0.85, "bias": "US-CONSERVATIVE"},
    {"name": "Wall Street Journal News", "url": "[https://news.google.com/rss/search?q=when:24h+site:wsj.com&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:24h+site:wsj.com&hl=en-US&gl=US&ceid=US:en)", "cat": "US/Finanzen", "weight": 0.95, "bias": "US-CONSERVATIVE"},
    {"name": "Reason Magazine", "url": "[https://reason.com/feed/](https://reason.com/feed/)", "cat": "US/Debatte", "weight": 0.85, "bias": "US-LIBERTARIAN"},
    {"name": "Bloomberg Markets", "url": "[https://news.google.com/rss/search?q=when:24h+site:bloomberg.com&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:24h+site:bloomberg.com&hl=en-US&gl=US&ceid=US:en)", "cat": "US/Finanzen", "weight": 0.95, "bias": "CENTER-LIBERAL"},

    # 🇩🇪 DEUTSCHLAND / DACH: POLITISCHES SPEKTRUM
    {"name": "taz die tageszeitung", "url": "[https://taz.de/rss.xml](https://taz.de/rss.xml)", "cat": "DE/Politik", "weight": 0.85, "bias": "DE-LEFT-PROGRESSIVE"},
    {"name": "Der Spiegel Top", "url": "[https://www.spiegel.de/schlagzeilen/tops/index.rss](https://www.spiegel.de/schlagzeilen/tops/index.rss)", "cat": "DE/Medien", "weight": 0.90, "bias": "DE-LEFT-LIBERAL"},
    {"name": "Süddeutsche Zeitung (SZ)", "url": "[https://news.google.com/rss/search?q=when:24h+site:sueddeutsche.de&hl=de&gl=DE&ceid=DE:de](https://news.google.com/rss/search?q=when:24h+site:sueddeutsche.de&hl=de&gl=DE&ceid=DE:de)", "cat": "DE/Presse", "weight": 0.90, "bias": "DE-LEFT-LIBERAL"},
    {"name": "FAZ Politik", "url": "[https://www.faz.net/rss/aktuell/politik/](https://www.faz.net/rss/aktuell/politik/)", "cat": "DE/Presse", "weight": 0.90, "bias": "DE-CONSERVATIVE"},
    {"name": "Die Welt News", "url": "[https://www.welt.de/feeds/topnews.rss](https://www.welt.de/feeds/topnews.rss)", "cat": "DE/Presse", "weight": 0.85, "bias": "DE-CONSERVATIVE"},
    {"name": "NZZ International", "url": "[https://www.nzz.ch/international.rss](https://www.nzz.ch/international.rss)", "cat": "CH/Presse", "weight": 0.95, "bias": "DE-CONSERVATIVE-LIBERAL"},
    {"name": "Die Zeit Online", "url": "[https://newsfeed.zeit.de/index](https://newsfeed.zeit.de/index)", "cat": "DE/Presse", "weight": 0.90, "bias": "DE-CENTER-LIBERAL"},
    {"name": "Handelsblatt Top", "url": "[https://www.handelsblatt.com/contentexport/feed/top-themen](https://www.handelsblatt.com/contentexport/feed/top-themen)", "cat": "DE/Finanzen", "weight": 0.90, "bias": "DE-LIBERAL-BUSINESS"},

    # 🇬🇧 GROSSBRITANNIEN (UK): POLITISCHES SPEKTRUM
    {"name": "The Guardian World", "url": "[https://www.theguardian.com/world/rss](https://www.theguardian.com/world/rss)", "cat": "UK/Presse", "weight": 0.90, "bias": "UK-LEFT-LIBERAL"},
    {"name": "The Telegraph News", "url": "[https://news.google.com/rss/search?q=when:24h+site:telegraph.co.uk&hl=en-GB&gl=GB&ceid=GB:en](https://news.google.com/rss/search?q=when:24h+site:telegraph.co.uk&hl=en-GB&gl=GB&ceid=GB:en)", "cat": "UK/Presse", "weight": 0.90, "bias": "UK-CONSERVATIVE"},
    {"name": "The Spectator", "url": "[https://www.spectator.co.uk/feed/](https://www.spectator.co.uk/feed/)", "cat": "UK/Debatte", "weight": 0.85, "bias": "UK-CONSERVATIVE"},
    {"name": "BBC World News", "url": "[http://feeds.bbci.co.uk/news/world/rss.xml](http://feeds.bbci.co.uk/news/world/rss.xml)", "cat": "UK/Medien", "weight": 0.95, "bias": "MAINSTREAM-CENTER"},
    {"name": "Financial Times", "url": "[https://news.google.com/rss/search?q=when:24h+site:ft.com&hl=en-GB&gl=GB&ceid=GB:en](https://news.google.com/rss/search?q=when:24h+site:ft.com&hl=en-GB&gl=GB&ceid=GB:en)", "cat": "UK/Finanzen", "weight": 0.95, "bias": "CENTER-LIBERAL"},

    # 🏛️ ZENTRALBANKEN & MAKRO-INSTITUTIONEN
    {"name": "Federal Reserve Press", "url": "[https://www.federalreserve.gov/feeds/press_all.xml](https://www.federalreserve.gov/feeds/press_all.xml)", "cat": "Zentralbank", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "Fed Speeches & Minutes", "url": "[https://www.federalreserve.gov/feeds/speeches.xml](https://www.federalreserve.gov/feeds/speeches.xml)", "cat": "Zentralbank", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "EZB (Europäische Zentralbank)", "url": "[https://www.ecb.europa.eu/rss/press.html](https://www.ecb.europa.eu/rss/press.html)", "cat": "Zentralbank", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "Bank of England (BoE)", "url": "[https://www.bankofengland.co.uk/rss/news](https://www.bankofengland.co.uk/rss/news)", "cat": "Zentralbank", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "People's Bank of China (PBOC)", "url": "[https://news.google.com/rss/search?q=when:7d+%22People%27s+Bank+of+China%22+OR+PBOC&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+%22People%27s+Bank+of+China%22+OR+PBOC&hl=en-US&gl=US&ceid=US:en)", "cat": "Zentralbank", "weight": 1.00, "bias": "BRICS"},
    {"name": "Bank of Japan (BoJ)", "url": "[https://news.google.com/rss/search?q=when:7d+site:boj.or.jp+OR+%22Bank+of+Japan%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+site:boj.or.jp+OR+%22Bank+of+Japan%22&hl=en-US&gl=US&ceid=US:en)", "cat": "Zentralbank", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "Atlanta Fed GDPNow & NY Fed", "url": "[https://news.google.com/rss/search?q=when:7d+%22GDPNow%22+OR+%22New+York+Fed%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+%22GDPNow%22+OR+%22New+York+Fed%22&hl=en-US&gl=US&ceid=US:en)", "cat": "Makro/Fed", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "BIS (Bank f. Intl. Zahlungsausgleich)", "url": "[https://www.bis.org/doclist/all.rss](https://www.bis.org/doclist/all.rss)", "cat": "Zentralbank", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "IMF News", "url": "[https://www.imf.org/en/News/rss](https://www.imf.org/en/News/rss)", "cat": "Intl. Org", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "Weltbank News", "url": "[https://www.worldbank.org/en/news/rss](https://www.worldbank.org/en/news/rss)", "cat": "Intl. Org", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "OECD Newsroom", "url": "[https://www.oecd.org/newsroom/index.xml](https://www.oecd.org/newsroom/index.xml)", "cat": "Intl. Org", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "EU-Kommission Press", "url": "[https://ec.europa.eu/commission/presscorner/api/rss](https://ec.europa.eu/commission/presscorner/api/rss)", "cat": "Regierung/EU", "weight": 1.00, "bias": "WESTERN"},
    {"name": "Europäischer Rat", "url": "[https://www.consilium.europa.eu/en/rss/](https://www.consilium.europa.eu/en/rss/)", "cat": "Regierung/EU", "weight": 1.00, "bias": "WESTERN"},
    {"name": "White House Briefing", "url": "[https://www.whitehouse.gov/briefing-room/feed/](https://www.whitehouse.gov/briefing-room/feed/)", "cat": "Regierung", "weight": 1.00, "bias": "WESTERN"},
    {"name": "US Department of State", "url": "[https://www.state.gov/rss-feed/press-releases/feed/](https://www.state.gov/rss-feed/press-releases/feed/)", "cat": "Diplomatie", "weight": 1.00, "bias": "WESTERN"},
    {"name": "Schweizer Bundesrat", "url": "[https://www.admin.ch/gov/de/start/dokumentation/medienmitteilungen.rss.html](https://www.admin.ch/gov/de/start/dokumentation/medienmitteilungen.rss.html)", "cat": "Regierung", "weight": 1.00, "bias": "WESTERN"},

    # 🚶 MIGRATION, VERTREIBUNG & HUMANITÄR (UNHCR / IOM / RELIEFWEB)
    {"name": "UNHCR Press Releases", "url": "[https://news.google.com/rss/search?q=when:7d+site:unhcr.org+%22refugee%22+OR+%22displacement%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+site:unhcr.org+%22refugee%22+OR+%22displacement%22&hl=en-US&gl=US&ceid=US:en)", "cat": "Migration / UNHCR", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "IOM Displacement Tracking Matrix (DTM)", "url": "[https://news.google.com/rss/search?q=when:7d+site:iom.int+OR+%22Displacement+Tracking+Matrix%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+site:iom.int+OR+%22Displacement+Tracking+Matrix%22&hl=en-US&gl=US&ceid=US:en)", "cat": "Migration / IOM", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "ReliefWeb Global Crises & Displacement", "url": "[https://reliefweb.int/updates/rss.xml](https://reliefweb.int/updates/rss.xml)", "cat": "Humanitär / UN OCHA", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "Frontex & Border Migration Routes", "url": "[https://news.google.com/rss/search?q=when:7d+Frontex+OR+%22irregular+border+crossings%22+OR+%22migrant+route%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+Frontex+OR+%22irregular+border+crossings%22+OR+%22migrant+route%22&hl=en-US&gl=US&ceid=US:en)", "cat": "Migration / Grenzen", "weight": 0.90, "bias": "MAINSTREAM"},

    # 📊 ENERGIE, ROHSTOFFE & LOGISTIK
    {"name": "EIA Petroleum Status Report", "url": "[https://news.google.com/rss/search?q=when:7d+site:eia.gov+%22Weekly+Petroleum+Status+Report%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+site:eia.gov+%22Weekly+Petroleum+Status+Report%22&hl=en-US&gl=US&ceid=US:en)", "cat": "Energie / EIA", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "IEA Oil Market Reports", "url": "[https://news.google.com/rss/search?q=when:7d+site:iea.org+%22Oil+Market+Report%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+site:iea.org+%22Oil+Market+Report%22&hl=en-US&gl=US&ceid=US:en)", "cat": "Energie / IEA", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "OPEC Monthly Market Reports", "url": "[https://news.google.com/rss/search?q=when:7d+OPEC+%22Monthly+Oil+Market+Report%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+OPEC+%22Monthly+Oil+Market+Report%22&hl=en-US&gl=US&ceid=US:en)", "cat": "Energie / OPEC", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "Baker Hughes Rig Count", "url": "[https://news.google.com/rss/search?q=when:7d+%22Baker+Hughes%22+%22Rig+Count%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+%22Baker+Hughes%22+%22Rig+Count%22&hl=en-US&gl=US&ceid=US:en)", "cat": "Energie / Öl", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "GIE European Gas Storage (AGSI+)", "url": "[https://news.google.com/rss/search?q=when:7d+%22Gas+Infrastructure+Europe%22+OR+%22gas+storage%22+EU&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+%22Gas+Infrastructure+Europe%22+OR+%22gas+storage%22+EU&hl=en-US&gl=US&ceid=US:en)", "cat": "Energie / Gas", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "Freightos Shipping Index", "url": "[https://news.google.com/rss/search?q=when:7d+%22Freightos%22+OR+%22container+freight+rate%22+OR+%22Baltic+Dry%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+%22Freightos%22+OR+%22container+freight+rate%22+OR+%22Baltic+Dry%22&hl=en-US&gl=US&ceid=US:en)", "cat": "Logistik / Container", "weight": 0.90, "bias": "MAINSTREAM"},
    {"name": "Baltic Dry Direct & Dry Bulk", "url": "[https://news.google.com/rss/search?q=when:7d+%22Baltic+Dry+Index%22+OR+%22capesize%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+%22Baltic+Dry+Index%22+OR+%22capesize%22&hl=en-US&gl=US&ceid=US:en)", "cat": "Logistik", "weight": 0.90, "bias": "MAINSTREAM"},
    {"name": "FAO Food Price Index", "url": "[https://news.google.com/rss/search?q=when:7d+site:fao.org+%22Food+Price+Index%22+OR+%22Crop+Prospects%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+site:fao.org+%22Food+Price+Index%22+OR+%22Crop+Prospects%22&hl=en-US&gl=US&ceid=US:en)", "cat": "Agrar / FAO", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "USDA Crop & WASDE Reports", "url": "[https://news.google.com/rss/search?q=when:7d+site:usda.gov+%22WASDE%22+OR+%22Crop+Production%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+site:usda.gov+%22WASDE%22+OR+%22Crop+Production%22&hl=en-US&gl=US&ceid=US:en)", "cat": "Agrar / USDA", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "MOVE Index & Bond Market Stress Alerts", "url": "[https://news.google.com/rss/search?q=when:7d+%22MOVE+index%22+OR+%22high+yield+spreads%22+OR+%22Credit+Default+Swap%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+%22MOVE+index%22+OR+%22high+yield+spreads%22+OR+%22Credit+Default+Swap%22&hl=en-US&gl=US&ceid=US:en)", "cat": "Bond Stress", "weight": 0.90, "bias": "MAINSTREAM"},

    # 🛡️ MILITÄR, OSINT, SATELLITEN, CYBER & SEESICHERHEIT
    {"name": "Oryx Blog (Equipment Losses)", "url": "[https://www.oryxspioenkop.com/feeds/posts/default](https://www.oryxspioenkop.com/feeds/posts/default)", "cat": "OSINT / Militär", "weight": 0.90, "bias": "ALTERNATIVE"},
    {"name": "Covert Cabal & Perun Defense OSINT", "url": "[https://news.google.com/rss/search?q=when:7d+%22Covert+Cabal%22+OR+%22Perun%22+defense&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+%22Covert+Cabal%22+OR+%22Perun%22+defense&hl=en-US&gl=US&ceid=US:en)", "cat": "OSINT / Analyse", "weight": 0.85, "bias": "ALTERNATIVE"},
    {"name": "Lloyd's List Shipping Intelligence", "url": "[https://news.google.com/rss/search?q=when:7d+site:lloydslist.maritimeintelligence.informa.com+OR+%22Lloyd%27s+List%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+site:lloydslist.maritimeintelligence.informa.com+OR+%22Lloyd%27s+List%22&hl=en-US&gl=US&ceid=US:en)", "cat": "Schifffahrt", "weight": 0.90, "bias": "MAINSTREAM"},
    {"name": "MarineTraffic Blog & Alerts", "url": "[https://www.marinetraffic.com/blog/feed/](https://www.marinetraffic.com/blog/feed/)", "cat": "Marine OSINT", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "NASA FIRMS Fire & Hazards", "url": "[https://earthobservatory.nasa.gov/feeder/natural_hazards.rss](https://earthobservatory.nasa.gov/feeder/natural_hazards.rss)", "cat": "OSINT / Satellit", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "USGS Earthquakes (M5.5+)", "url": "[https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/5.5_day.atom](https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/5.5_day.atom)", "cat": "Seismik / Warnsystem", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "GDACS Global Disaster Alerts", "url": "[https://www.gdacs.org/xml/rss.xml](https://www.gdacs.org/xml/rss.xml)", "cat": "Frühwarnung", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "ISW (Institute f. Study of War)", "url": "[https://www.understandingwar.org/rss.xml](https://www.understandingwar.org/rss.xml)", "cat": "OSINT / Militär", "weight": 0.85, "bias": "WESTERN"},
    {"name": "US Naval Institute News", "url": "[https://news.usni.org/feed](https://news.usni.org/feed)", "cat": "Marine / AIS OSINT", "weight": 0.85, "bias": "WESTERN"},
    {"name": "Naval News", "url": "[https://www.navalnews.com/feed/](https://www.navalnews.com/feed/)", "cat": "Schifffahrt & Marine", "weight": 0.85, "bias": "WESTERN"},
    {"name": "War on the Rocks", "url": "[https://warontherocks.com/feed/](https://warontherocks.com/feed/)", "cat": "Militäranalyse", "weight": 0.85, "bias": "WESTERN"},
    {"name": "Bellingcat OSINT", "url": "[https://www.bellingcat.com/feed/](https://www.bellingcat.com/feed/)", "cat": "OSINT / Satellit", "weight": 0.85, "bias": "ALTERNATIVE"},
    {"name": "Critical Threats Project", "url": "[https://news.google.com/rss/search?q=when:7d+%22Critical+Threats%22+OR+AEI&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+%22Critical+Threats%22+OR+AEI&hl=en-US&gl=US&ceid=US:en)", "cat": "Militäranalyse", "weight": 0.85, "bias": "WESTERN"},
    {"name": "CISA Cyber Alerts (US)", "url": "[https://www.cisa.gov/cybersecurity-advisories/all.xml](https://www.cisa.gov/cybersecurity-advisories/all.xml)", "cat": "Cyber / Infrastruktur", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "CERT-EU Security Alerts", "url": "[https://cert.europa.eu/publications/warnings/feed.xml](https://cert.europa.eu/publications/warnings/feed.xml)", "cat": "Cyber / Infrastruktur", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "Dark Reading Cyber Intelligence", "url": "[https://www.darkreading.com/rss.xml](https://www.darkreading.com/rss.xml)", "cat": "Cyber", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Submarine Telecoms Cable News", "url": "[https://subtelforum.com/feed/](https://subtelforum.com/feed/)", "cat": "Infrastruktur", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Offshore Energy Today", "url": "[https://www.offshore-energy.biz/feed/](https://www.offshore-energy.biz/feed/)", "cat": "Infrastruktur", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "UKMTO (UK Maritime Trade Ops)", "url": "[https://news.google.com/rss/search?q=when:24h+UKMTO+OR+%22Maritime+Trade+Operations%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:24h+UKMTO+OR+%22Maritime+Trade+Operations%22&hl=en-US&gl=US&ceid=US:en)", "cat": "Schifffahrt OSINT", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "gCaptain Maritime News", "url": "[https://gcaptain.com/feed/](https://gcaptain.com/feed/)", "cat": "Schifffahrt", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Splash247 Shipping Intelligence", "url": "[https://splash247.com/feed/](https://splash247.com/feed/)", "cat": "Schifffahrt", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Maritime Executive", "url": "[https://maritime-executive.com/rss](https://maritime-executive.com/rss)", "cat": "Schifffahrt", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Flightradar24 Blog", "url": "[https://www.flightradar24.com/blog/feed/](https://www.flightradar24.com/blog/feed/)", "cat": "Luftfahrt OSINT", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Aviation Safety Network (ASN)", "url": "[https://news.google.com/rss/search?q=when:7d+%22Aviation+Safety+Network%22+OR+NOTAM&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+%22Aviation+Safety+Network%22+OR+NOTAM&hl=en-US&gl=US&ceid=US:en)", "cat": "Luftfahrt", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "GPSJam & Electronic Warfare Alerts", "url": "[https://news.google.com/rss/search?q=when:24h+%22GPS+jamming%22+OR+%22ADS-B+spoofing%22+OR+%22NOTAM%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:24h+%22GPS+jamming%22+OR+%22ADS-B+spoofing%22+OR+%22NOTAM%22&hl=en-US&gl=US&ceid=US:en)", "cat": "EW / Luftfahrt", "weight": 0.85, "bias": "ALTERNATIVE"},

    # 🌍 WELT-NACHRICHTENAGENTUREN & DIPLOMATIE (GLOBAL COVERAGE)
    {"name": "AP News World", "url": "[https://news.google.com/rss/search?q=when:24h+source:Associated+Press&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:24h+source:Associated+Press&hl=en-US&gl=US&ceid=US:en)", "cat": "Agentur", "weight": 0.95, "bias": "MAINSTREAM"},
    {"name": "Reuters World", "url": "[https://news.google.com/rss/search?q=when:24h+source:Reuters&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:24h+source:Reuters&hl=en-US&gl=US&ceid=US:en)", "cat": "Agentur", "weight": 0.95, "bias": "MAINSTREAM"},
    {"name": "Agence France-Presse (AFP)", "url": "[https://news.google.com/rss/search?q=when:24h+source:AFP&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:24h+source:AFP&hl=en-US&gl=US&ceid=US:en)", "cat": "Agentur", "weight": 0.95, "bias": "MAINSTREAM"},
    {"name": "Xinhua & Global Times (China)", "url": "[https://news.google.com/rss/search?q=when:24h+site:xinhuanet.com+OR+site:globaltimes.cn&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:24h+site:xinhuanet.com+OR+site:globaltimes.cn&hl=en-US&gl=US&ceid=US:en)", "cat": "Agentur/BRICS", "weight": 0.90, "bias": "BRICS"},
    {"name": "IRNA & Anadolu Agency (Nahost/BRICS)", "url": "[https://news.google.com/rss/search?q=when:24h+site:irna.ir+OR+site:aa.com.tr&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:24h+site:irna.ir+OR+site:aa.com.tr&hl=en-US&gl=US&ceid=US:en)", "cat": "Agentur/BRICS", "weight": 0.85, "bias": "BRICS"},
    {"name": "Kyodo News (Japan)", "url": "[https://english.kyodonews.net/rss/news.xml](https://english.kyodonews.net/rss/news.xml)", "cat": "Agentur", "weight": 0.90, "bias": "MAINSTREAM"},
    {"name": "Kremlin News", "url": "[http://en.kremlin.ru/rss/news](http://en.kremlin.ru/rss/news)", "cat": "Regierung", "weight": 1.00, "bias": "BRICS"},
    {"name": "Russisches Außenministerium (MID)", "url": "[https://news.google.com/rss/search?q=when:7d+%22Russian+Foreign+Ministry%22+OR+MID&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+%22Russian+Foreign+Ministry%22+OR+MID&hl=en-US&gl=US&ceid=US:en)", "cat": "Diplomatie", "weight": 1.00, "bias": "BRICS"},
    {"name": "Chinesisches Außenministerium", "url": "[https://www.fmprc.gov.cn/eng/zxmz/rss.xml](https://www.fmprc.gov.cn/eng/zxmz/rss.xml)", "cat": "Diplomatie", "weight": 1.00, "bias": "BRICS"},
    {"name": "Indisches Außenministerium (MEA)", "url": "[https://news.google.com/rss/search?q=when:7d+site:mea.gov.in&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:7d+site:mea.gov.in&hl=en-US&gl=US&ceid=US:en)", "cat": "Diplomatie", "weight": 0.95, "bias": "BRICS"},
    {"name": "CGTN World", "url": "[https://www.cgtn.com/xml/rss/news.xml](https://www.cgtn.com/xml/rss/news.xml)", "cat": "Medien", "weight": 0.85, "bias": "BRICS"},
    {"name": "TASS World", "url": "[https://tass.com/rss/v2.xml](https://tass.com/rss/v2.xml)", "cat": "Agentur", "weight": 0.85, "bias": "BRICS"},
    {"name": "Economic Times (Indien)", "url": "[https://economictimes.indiatimes.com/news/defence/rssfeeds/12216583.cms](https://economictimes.indiatimes.com/news/defence/rssfeeds/12216583.cms)", "cat": "Finanzen/BRICS", "weight": 0.85, "bias": "BRICS"},
    {"name": "Al Jazeera", "url": "[https://www.aljazeera.com/xml/rss/all.xml](https://www.aljazeera.com/xml/rss/all.xml)", "cat": "Medien", "weight": 0.85, "bias": "BRICS"},
    {"name": "South China Morning Post", "url": "[https://www.scmp.com/rss/91/feed](https://www.scmp.com/rss/91/feed)", "cat": "Medien", "weight": 0.85, "bias": "BRICS"},
    {"name": "The Cradle", "url": "[https://thecradle.co/feed](https://thecradle.co/feed)", "cat": "Geopolitik", "weight": 0.80, "bias": "ALTERNATIVE"},
    {"name": "Asia Times", "url": "[https://asiatimes.com/feed/](https://asiatimes.com/feed/)", "cat": "Geopolitik", "weight": 0.85, "bias": "MAINSTREAM"},

    # 💡 THINK TANKS & QUALITÄTSPRESSE
    {"name": "Quincy Institute (Responsible Statecraft)", "url": "[https://quincyinst.org/feed/](https://quincyinst.org/feed/)", "cat": "Think Tank", "weight": 0.90, "bias": "ALTERNATIVE"},
    {"name": "Carnegie Endowment", "url": "[https://carnegieendowment.org/rss/solr.xml](https://carnegieendowment.org/rss/solr.xml)", "cat": "Think Tank", "weight": 0.90, "bias": "WESTERN"},
    {"name": "Chatham House", "url": "[https://www.chathamhouse.org/rss.xml](https://www.chathamhouse.org/rss.xml)", "cat": "Think Tank", "weight": 0.90, "bias": "WESTERN"},
    {"name": "Bruegel (EU Wirtschaft)", "url": "[https://www.bruegel.org/rss.xml](https://www.bruegel.org/rss.xml)", "cat": "Think Tank/EU", "weight": 0.90, "bias": "WESTERN"},
    {"name": "CSIS Org", "url": "[https://www.csis.org/nerve/rss](https://www.csis.org/nerve/rss)", "cat": "Think Tank", "weight": 0.90, "bias": "WESTERN"},
    {"name": "CFR (Council on Foreign Relations)", "url": "[https://www.cfr.org/rss/publication/feed](https://www.cfr.org/rss/publication/feed)", "cat": "Think Tank", "weight": 0.90, "bias": "WESTERN"},
    {"name": "ECFR Europe", "url": "[https://ecfr.eu/feed/](https://ecfr.eu/feed/)", "cat": "Think Tank", "weight": 0.90, "bias": "WESTERN"},
    {"name": "SWP Berlin", "url": "[https://www.swp-berlin.org/de/rss.xml](https://www.swp-berlin.org/de/rss.xml)", "cat": "Think Tank", "weight": 0.90, "bias": "WESTERN"},
    {"name": "World Economic Forum (WEF)", "url": "[https://www.weforum.org/feed/](https://www.weforum.org/feed/)", "cat": "Think Tank", "weight": 0.85, "bias": "WESTERN"},
    {"name": "CNBC Finance", "url": "[https://www.cnbc.com/id/10000664/device/rss/rss.html](https://www.cnbc.com/id/10000664/device/rss/rss.html)", "cat": "Finanzen", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Foreign Policy", "url": "[https://foreignpolicy.com/feed/](https://foreignpolicy.com/feed/)", "cat": "Magazin", "weight": 0.85, "bias": "WESTERN"},
    {"name": "Nikkei Asia", "url": "[https://asia.nikkei.com/rss/feed/nar](https://asia.nikkei.com/rss/feed/nar)", "cat": "Finanzen/Asien", "weight": 0.90, "bias": "MAINSTREAM"},
    {"name": "Finanzmarktwelt", "url": "[https://finanzmarktwelt.de/feed/](https://finanzmarktwelt.de/feed/)", "cat": "Finanzen DE", "weight": 0.80, "bias": "ALTERNATIVE"},

    # 💬 OSINT & COMMUNITY REDDIT FEEDS
    {"name": "Reddit r/geopolitics", "url": "[https://www.reddit.com/r/geopolitics/.rss](https://www.reddit.com/r/geopolitics/.rss)", "cat": "Community", "weight": 0.60, "bias": "ALTERNATIVE"},
    {"name": "Reddit r/OSINT", "url": "[https://www.reddit.com/r/OSINT/.rss](https://www.reddit.com/r/OSINT/.rss)", "cat": "Community", "weight": 0.60, "bias": "ALTERNATIVE"},
    {"name": "Reddit r/CredibleDefense", "url": "[https://www.reddit.com/r/CredibleDefense/.rss](https://www.reddit.com/r/CredibleDefense/.rss)", "cat": "Community", "weight": 0.65, "bias": "WESTERN"},
    {"name": "Reddit r/LessCredibleDefence", "url": "[https://www.reddit.com/r/LessCredibleDefence/.rss](https://www.reddit.com/r/LessCredibleDefence/.rss)", "cat": "Community", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Reddit r/Economics", "url": "[https://www.reddit.com/r/Economics/.rss](https://www.reddit.com/r/Economics/.rss)", "cat": "Community", "weight": 0.60, "bias": "ALTERNATIVE"},
    {"name": "Reddit r/Macroeconomics", "url": "[https://www.reddit.com/r/Macroeconomics/.rss](https://www.reddit.com/r/Macroeconomics/.rss)", "cat": "Community", "weight": 0.60, "bias": "ALTERNATIVE"},
    {"name": "Reddit r/Commodities", "url": "[https://www.reddit.com/r/Commodities/.rss](https://www.reddit.com/r/Commodities/.rss)", "cat": "Community", "weight": 0.60, "bias": "ALTERNATIVE"},

    # 🔍 ALTERNATIVE, INVESTIGATIVE & KONTRÄRE MEDIEN
    {"name": "Scheerpost", "url": "[https://scheerpost.com/feed/](https://scheerpost.com/feed/)", "cat": "Investigativ", "weight": 0.75, "bias": "ALTERNATIVE"},
    {"name": "Naked Capitalism", "url": "[https://www.nakedcapitalism.com/feed](https://www.nakedcapitalism.com/feed)", "cat": "Makro/Investigativ", "weight": 0.80, "bias": "ALTERNATIVE"},
    {"name": "Consortium News", "url": "[https://consortiumnews.com/feed/](https://consortiumnews.com/feed/)", "cat": "Investigativ", "weight": 0.75, "bias": "ALTERNATIVE"},
    {"name": "Glenn Greenwald Substack", "url": "[https://greenwald.substack.com/feed](https://greenwald.substack.com/feed)", "cat": "Journalismus", "weight": 0.80, "bias": "ALTERNATIVE"},
    {"name": "Aaron Maté Substack", "url": "[https://mate.substack.com/feed](https://mate.substack.com/feed)", "cat": "Journalismus", "weight": 0.75, "bias": "ALTERNATIVE"},
    {"name": "The Duran Geopolitics", "url": "[https://theduran.com/feed/](https://theduran.com/feed/)", "cat": "Geopolitik", "weight": 0.70, "bias": "BRICS"},
    {"name": "ZeroHedge", "url": "[http://feeds.feedburner.com/zerohedge/feed](http://feeds.feedburner.com/zerohedge/feed)", "cat": "Alternativ / Makro", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "The Intercept", "url": "[https://theintercept.com/feed/?lang=en](https://theintercept.com/feed/?lang=en)", "cat": "Investigativ", "weight": 0.75, "bias": "ALTERNATIVE"},
    {"name": "The Grayzone", "url": "[https://thegrayzone.com/feed/](https://thegrayzone.com/feed/)", "cat": "Investigativ", "weight": 0.50, "bias": "BRICS"},
    {"name": "Republik (Schweiz)", "url": "[https://www.republik.ch/feed](https://www.republik.ch/feed)", "cat": "Investigativ CH", "weight": 0.80, "bias": "WESTERN"},
    {"name": "MintPress News", "url": "[https://www.mintpressnews.com/feed/](https://www.mintpressnews.com/feed/)", "cat": "Alternativ", "weight": 0.50, "bias": "BRICS"},
    {"name": "UnHerd", "url": "[https://unherd.com/feed/](https://unherd.com/feed/)", "cat": "Debatte", "weight": 0.75, "bias": "ALTERNATIVE"},
    {"name": "Antiwar.com", "url": "[https://www.antiwar.com/blog/feed/](https://www.antiwar.com/blog/feed/)", "cat": "Friedenspolitik", "weight": 0.60, "bias": "ALTERNATIVE"},
    {"name": "NachDenkSeiten", "url": "[https://www.nachdenkseiten.de/?feed=rss2](https://www.nachdenkseiten.de/?feed=rss2)", "cat": "Medienkritik DE", "weight": 0.60, "bias": "ALTERNATIVE"},
    {"name": "Apolut", "url": "[https://apolut.net/feed/](https://apolut.net/feed/)", "cat": "Alternativ DE", "weight": 0.50, "bias": "ALTERNATIVE"},
    {"name": "Anti-Spiegel", "url": "[https://www.anti-spiegel.ru/feed/](https://www.anti-spiegel.ru/feed/)", "cat": "Alternativ DE/RU", "weight": 0.45, "bias": "BRICS"},
    {"name": "Telepolis", "url": "[https://www.telepolis.de/news-atom.xml](https://www.telepolis.de/news-atom.xml)", "cat": "Magazin DE", "weight": 0.70, "bias": "ALTERNATIVE"},
    {"name": "Tichys Einblick", "url": "[https://www.tichyseinblick.de/feed/](https://www.tichyseinblick.de/feed/)", "cat": "Debatte DE", "weight": 0.60, "bias": "ALTERNATIVE"},
    {"name": "Overton Magazin", "url": "[https://overton-magazin.de/feed/](https://overton-magazin.de/feed/)", "cat": "Geopolitik DE", "weight": 0.65, "bias": "ALTERNATIVE"},
    {"name": "Multipolar Magazin", "url": "[https://multipolar-magazin.de/feed](https://multipolar-magazin.de/feed)", "cat": "Geopolitik DE", "weight": 0.60, "bias": "BRICS"},
    {"name": "Manova / Rubikon", "url": "[https://www.manova.news/artikel.rss](https://www.manova.news/artikel.rss)", "cat": "Alternativ DE", "weight": 0.50, "bias": "ALTERNATIVE"},
    {"name": "Berliner Tageszeitung", "url": "[https://www.berlinertageszeitung.de/index.php?option=com_ninja_rsssyndicator&feed_id=1&format=raw](https://www.berlinertageszeitung.de/index.php?option=com_ninja_rsssyndicator&feed_id=1&format=raw)", "cat": "Medien DE", "weight": 0.60, "bias": "ALTERNATIVE"},
    {"name": "Hintergrund Magazin", "url": "[https://www.hintergrund.de/feed/](https://www.hintergrund.de/feed/)", "cat": "Geopolitik DE", "weight": 0.65, "bias": "ALTERNATIVE"},
    {"name": "Moon of Alabama", "url": "[https://www.moonofalabama.org/index.rdf](https://www.moonofalabama.org/index.rdf)", "cat": "Militär-Blog", "weight": 0.65, "bias": "BRICS"},
    {"name": "Caitlin Johnstone", "url": "[https://caitlinjohnstone.com.au/feed/](https://caitlinjohnstone.com.au/feed/)", "cat": "Kolumne", "weight": 0.55, "bias": "ALTERNATIVE"}
]

browser_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ArgusGridOSINTBot/3.0"

def fetch_feed(src):
    try:
        res = requests.get(src["url"], headers={"User-Agent": browser_agent}, timeout=6)
        if res.status_code == 200:
            feed = feedparser.parse(res.content)
            if feed.entries:
                out = f"\n--- QUELLE: {src['name']} | Kat: {src['cat']} | Bias: {src['bias']} ---\n"
                for entry in feed.entries[:3]:
                    title = entry.get('title', '')
                    raw_summary = entry.get('summary', '') or entry.get('description', '')
                    summary = clean_html(raw_summary)
                    out += f"- {title}: {summary[:150]}...\n"
                return out
    except Exception:
        pass
    return ""

print(f"Hole Feeds aus allen {len(SOURCES)} RSS-Quellen parallel...")
raw_feed_text = ""
with ThreadPoolExecutor(max_workers=45) as executor:
    futures = [executor.submit(fetch_feed, src) for src in SOURCES]
    for future in as_completed(futures):
        res_str = future.result()
        if res_str:
            raw_feed_text += res_str

print(f"Insgesamt {len(raw_feed_text)} Zeichen Rohdaten aus allen Feeds geladen.")

# ============================================================
# STUFE 1: GROQ PRE-FILTERING (LLAMA 3.3 70B)
# ============================================================
def filter_feeds(text):
    if not client_groq:
        print("Hinweis: Kein Groq Key. Überspringe Stufe-1 Pre-Filter.")
        return text[:50000]
    print("Filtere alle Feeds via Groq (Llama 3.3 70B)...")
    prompt = """Du bist ein weltweites OSINT-Filter-Modul. 

WICHTIGER ZEITANKER: Wir schreiben das Jahr 2026! US-Präsident ist Donald Trump (Trump-Administration). Ignoriere veraltete Vorgehensweisen oder vergangene Wahlen (wie Midterms 2024 oder Biden-Regierung).

Deine Aufgabe: Filtere die Feeds unvoreingenommen, ausgewogen und GLOBAL.
Vergleiche die Positionen von Links (Demokraten/Progressive), Rechts (Republikaner/Konservative) und Mitte/Liberalen bei Großmächten (USA, EU, UK, BRICS).

LÖSCHE Triviales, Sport, PR, Lokalkriminalität.
BEHALTE UNBEDINGT:
1. INNENPOLITISCHER DRUCK & PARTEIENKÄMPFE: Wahlzyklen, Parteikongresse, Gesetzgebungsblockaden, Regierungsinstabilitäten (USA, EU, BRICS, Nahost, Afrika).
2. ESKALATIONSSPIRALEN & SPIELTHEORIE: Truppen, NOTAMs, GPS-Jamming, Sanktionen, Manöver.
3. HYBRIDE/NEUE BRENNPUNKTE: Pufferstaaten (Moldawien, Kaukasus), EnKLaven, Machtvakua, Cyber, maritime Nadelöhre.
4. FLÜCHTLINGSSTRÖME & VERTREIBUNG: UNHCR/IOM DTM, Massenflucht als Frühwarnindikator.
5. MONETÄRE & DIGITALE SOUVERÄNITÄT: CBDCs, EU-Chatkontrolle/Verschlüsselungsverbot, US-Verschuldung, BRICS Pay, SWIFT.
6. MAKRO, ROHSTOFFE & LOGISTIK: Zinsen, Anleihestress, Rig Count, Gas-Storage, Frachtraten.
Gib das Ergebnis als strukturierte Stichpunkte zurück (max 3000 Wörter). Deutsch oder Englisch."""
    try:
        res = client_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": text[:90000]}],
            temperature=0.1,
            max_tokens=4000
        )
        filtered = res.choices[0].message.content
        print(f"Groq Filter erfolgreich! Text komprimiert auf {len(filtered)} Zeichen.")
        return filtered
    except Exception as e:
        print(f"Groq-Filter Fehler: {e}. Nutze ungefilterte Feeds.")
        return text[:50000]

filtered_context = filter_feeds(raw_feed_text)

# ============================================================
# STUFE 2a: DEEPSEEK-R1 / V4 (SPIELTHEORIE & KALTE LOGIK)
# ============================================================
def run_deepseek_game_theory(context):
    if not client_deepseek:
        print("Hinweis: DeepSeek Key (DEEPSEEK_API_KEY) nicht konfiguriert.")
        return "DeepSeek Spieltheorie-Analyse nicht verfügbar."
    print("Starte DeepSeek-R1 Spieltheorie-Analyse (deepseek-reasoner)...")
    gt_prompt = """WICHTIGER ZEITANKER & REALITÄTS-CHECK:
- Wir schreiben das Jahr 2026.
- US-Präsident ist Donald Trump (Trump-Administration).
- Erwähne NIEMALS veraltete Akteure oder Ereignisse wie 'Biden-Administration' oder 'Midterms 2024'!

Analysiere das akuteste globale Krisenereignis aus den Feeds streng spieltheoretisch.
Setze folgende 6 Prinzipien um:
1. AKTEUR-GRANULARITÄT: Zerlege Staaten in interne Fraktionen (Exekutive, Militär, Parteiflügel, Lobby).
2. ZEITHORIZONT: Analysiere separat 4-8 Wochen (Ein-Runden-Spiel) vs. Langfristig (Schatten der Zukunft).
3. PAYOFF-QUANTIFIZIERUNG: Skala -3 (Existenzieller Verlust) bis +3 (Maximaler Gewinn).
4. INFORMATIONSSTAND: Cheap Talk (Rhetorik) vs. Costly Signals (echte Kosten).
5. GLEICHGEWICHT: Nash-Gleichgewicht & Commitment-Problem.
6. GEGENMODELL: Konstruiere die stärkste Falsifikations-Gegenlesart.
Formuliere als kompaktes, strukturiertes Gutachten."""
    try:
        res = client_deepseek.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {"role": "system", "content": gt_prompt},
                {"role": "user", "content": context}
            ]
        )
        return res.choices[0].message.content
    except Exception as e:
        print(f"DeepSeek R1 Fehler: {e}")
        return "Spieltheorie-Analyse über Primärpfad generieren."

deepseek_analysis = run_deepseek_game_theory(filtered_context)

# ============================================================
# STUFE 2b: GEMINI 2.0 FLASH (MAKRO, MIGRATION & ROHSTOFFE)
# ============================================================
def run_gemini_macro(context, markets):
    if not client_gemini:
        print("Hinweis: Gemini Key nicht konfiguriert.")
        return "Gemini Makro-Analyse nicht verfügbar."
    print("Starte Gemini 2.0 Flash Makro- & Migrations-Scan...")
    macro_prompt = """WICHTIGER ZEITANKER: Wir schreiben das Jahr 2026. US-Präsident ist Donald Trump.

Analysiere die Feeds und Live-Finanzdaten auf:
1. Makroökonomische Schocks (Zinsen, Inflation, Rohstoff-Nadelöhre, Seewege).
2. Fluchtbewegungen & Vertreibung (UNHCR/IOM) als Frühwarnindikatoren für verdeckte Eskalationen.
3. Digitale Souveränität (CBDCs, Überwachungsgesetze, Kapitalverkehrskontrollen).
Fasse die Erkenntnisse kurz und prägnant zusammen."""
    try:
        res = client_gemini.chat.completions.create(
            model="gemini-2.0-flash",
            messages=[{"role": "system", "content": macro_prompt}, {"role": "user", "content": f"MARKETS:\n{markets}\nFEEDS:\n{context}"}],
            temperature=0.2
        )
        return res.choices[0].message.content
    except Exception as e:
        print(f"Gemini Fehler: {e}")
        return "Makro-Analyse über Primärpfad generieren."

gemini_analysis = run_gemini_macro(filtered_context, live_market_context)

# ============================================================
# STUFE 3: CLAUDE 3.5 SONNET (CHEF-SYNTHESIZER ➔ DATA.JSON)
# ============================================================
orchestrator_prompt = """Du bist die 'Argus Grid Systemic Intelligence Engine' (Chef-Analyst).
Synthetisiere die Berichte der Spezial-Analysten (DeepSeek Spieltheorie + Gemini Makro/Migration) und die Live-Feeds zu einer unvoreingenommenen Gesamtlage.

WICHTIGER ZEITANKER & FAKTEN-GUARDRAIL:
- Es ist das Jahr 2026. US-Präsident ist Donald Trump (Trump-Administration).
- Korrigiere und eliminiere jegliche Halluzinationen oder veraltete Referenzen aus Vorgängermodellen (z. B. Biden, Midterms 2024 etc.).

DEINE AUFGABE:
- Integriere die spieltheoretischen Payoffs (-3 bis +3) und das Gegenmodell.
- ERFASSE KONFLIKTHERDE MIT KLARER STATUS-TRENNUNG (`status_type`): 'AKTIV' vs. 'POTENZIELL'.
- ANALYSIERE DIE INNENPOLITIK UND DAS MEDIENSPEKTRUM (USA, EU, UK, BRICS, NAHER OSTEN, AFRIKA):
  Balanciere Positionen von Demokraten/Progressiven, Republikanern/Konservativen und Liberalen bei Wahlzyklen, Parteiendynamiken und Gesetzen unvoreingenommen aus.
- DYNAMISCHE AKTIEN-ROTIERUNG: Wähle NIEMALS starr dieselben Aktien! Nutze betroffene Branchen (Shipping: FRO, ZIM; Rüstung: RHM.DE, LMT; Rohstoffe: CCJ, MP, ALB; Tech/Cyber: PLTR, CRWD).

ANTWORTE AUSSCHLIESSLICH IM REIN VALIDEN JSON-FORMAT:
{
  "daily_executive_summary": "3 prägnante Sätze zur Lage.",
  "market_regime": "Stagflationär / Geopolitische Fragmentierung / Regulierungsdruck",
  "geoscore": {"current_score": 78, "status_label": "ERHÖHT", "previous_48h": 74},
  "defcon_status": {"level": 3, "label": "DEFCON 3", "nuclear_risk_percent": 15, "primary_driver": "Hauptursache"},
  "top_overweight": "Gold, Rohstoffe & Defense",
  "top_risk": "Systemisches Hauptrisiko",

  "game_theory_deep_dive": {
    "focal_situation": "Titel des analysierten Ereignisses",
    "1_fractionated_actors": [
      {"entity": "Akteur", "factions": [{"faction_name": "Fraktion", "divergent_interest": "Interessensabweichung", "payoff_matrix_short_term": {"action_escalate": -1, "action_cooperate": 2, "action_delay": 0}, "confidence": 85}]}
    ],
    "2_time_horizon_conflict": {"short_term_one_shot_4_to_8_weeks": "Kurzfristig", "long_term_repeated_game": "Langfristig", "horizon_contradiction": "Widerspruch"},
    "3_game_structure_and_payoffs": {
      "type": "Chicken Game / Gefangenendilemma",
      "justification": "Begründung",
      "payoff_assessment_scale_minus_3_to_plus_3": [{"scenario_combination": "Akteur A vs B", "payoff_actor_A": 2, "payoff_actor_B": -2, "confidence": 80}]
    },
    "4_signaling_and_information": {"information_asymmetry": "Unvollständig", "cheap_talk": ["Bluffs"], "costly_signals": ["Reale Kosten-Handlungen"]},
    "5_equilibria_and_commitment": {"plausible_nash_equilibria": "Nash-Gleichgewicht", "commitment_problem": "Bindungsproblem", "confidence": 85},
    "6_falsification_counter_model": {"alternative_interpretation": "Stärkste Gegenlesart", "necessary_conditions": "Bedingungen für Gegenlesart"},
    "behavioral_framing_check": "Verhalten ist konsistent mit Nutzenfunktion"
  },

  "domestic_politics_analysis": [
    {
      "region_actor": "USA / EU / UK / BRICS / Naher Osten / Afrika",
      "key_event_trend": "Innenpolitisches Ereignis / Parteiendynamik (Dem/GOP/Left/Right)",
      "regime_stability": "STABIL / FRAGIL / ESKALATIV",
      "geopolitical_impact": "Konkrete Auswirkung auf Außenpolitik & Märkte"
    }
  ],

  "stress_testing_scenarios": [
    {
      "scenario_name": "Szenario Name", "probability_pct": 40, "timeframe": "1-3 Monate",
      "trigger_events": ["Auslöser 1"], "cascade_chain": ["Kaskade 1", "Kaskade 2"],
      "winners_long": [{"asset": "Asset", "reason": "Grund"}],
      "losers_short": [{"asset": "Asset", "reason": "Grund"}],
      "hedging_strategy": "Absicherung"
    }
  ],

  "conflict_hotspots": [
    {
      "region": "Region",
      "actors": "Akteure",
      "status_type": "AKTIV",
      "escalation_level": "HOCH",
      "catalyst": "Auslöser / Treiber",
      "impact": "Folge / Risiko",
      "lat": 47.01,
      "lng": 28.86
    }
  ],

  "digital_and_monetary_sovereignty": [
    {"topic": "CBDC / Chatkontrolle / Schulden", "actor": "Institution", "trend": "Beschleunigt", "systemic_impact": "Bürgerrechte/Geld", "market_implication": "Kapitalreaktion"}
  ],

  "stock_picks": {
    "top_5_buys": [{"ticker": "TICKER", "name": "Name", "sector": "Sektor", "reason": "Tagesaktueller Grund"}],
    "flop_5_sells": [{"ticker": "TICKER", "name": "Name", "sector": "Sektor", "reason": "Tagesaktueller Grund"}]
  }
}
"""

user_payload = f"""
--- EXPERTEN-INPUT 1: DEEPSEEK SPIELTHEORIE ---
{deepseek_analysis}

--- EXPERTEN-INPUT 2: GEMINI MAKRO & MIGRATION ---
{gemini_analysis}

--- LIVE FINANZDATEN ---
{live_market_context}

--- GEFILTERTE HARTE FEEDS ---
{filtered_context}
"""

print("Generiere finale Re-Synthese mit Claude 3.5 Sonnet...")
final_json_text = None

if client_anthropic:
    try:
        res = client_anthropic.messages.create(
            model="claude-3-5-sonnet-latest",
            max_tokens=8192,
            system=orchestrator_prompt,
            messages=[{"role": "user", "content": user_payload}]
        )
        final_json_text = res.content[0].text.strip()
    except Exception as e:
        print(f"Claude primär fehlgeschlagen: {e}")

# Fallback auf DeepSeek V3, falls Claude ausfällt
if not final_json_text and client_deepseek:
    print("Nutze DeepSeek V3 Fallback für Finales JSON...")
    try:
        completion = client_deepseek.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": orchestrator_prompt},
                {"role": "user", "content": user_payload}
            ],
            temperature=0.2
        )
        final_json_text = completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"DeepSeek Fallback Fehler: {e}")

if not final_json_text:
    raise RuntimeError("Kritischer Fehler: Keine API konnte das finale JSON erzeugen.")

data = repair_and_parse_json(final_json_text)
data["timestamp"] = datetime.utcnow().strftime("%d.%m.%Y - %H:%M UTC")

# DIREKT-INJEKTION DER LIVE ADS-B FLUGDATEN IN DIE DATA.JSON
data["live_recon_flights"] = live_recon_flights

# JSON Speichern
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"✅ Argus Grid Multi-LLM Intelligence Engine erfolgreich gelaufen! ({len(live_recon_flights)} Flugspuren erfasst)")
