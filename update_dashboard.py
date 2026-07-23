import os
import json
import re
from datetime import datetime
import anthropic
import feedparser
import requests
import yfinance as yf

# HTML-Tags entfernen
def clean_html(raw_html):
    if not raw_html:
        return ""
    clean_text = re.sub(r'<[^>]+>', '', raw_html)
    return clean_text.strip()

# A. ECHTE LIVE-MARKTDATEN & ROHSTOFF-BASKET
def get_live_market_data():
    market_summary = ""
    tickers = {
        "Gold (USD/oz)": "GC=F",
        "Silber (USD/oz)": "SI=F",
        "Brent Öl (USD/bbl)": "BZ=F",
        "WTI Öl (USD/bbl)": "CL=F",
        "US Erdgas (USD/MMBtu)": "NG=F",
        "Kupfer (USD/lb)": "HG=F",
        "Weizen (USD/bu)": "ZW=F",
        "S&P 500 Index": "^GSPC",
        "Bitcoin (USD)": "BTC-USD",
        "US 10Y Anleihe": "^TNX",
        "VIX (Angstindex)": "^VIX"
    }
    print("Hole echte Finanz- & Rohstoffmarktdaten via yfinance...")
    try:
        for name, ticker in tickers.items():
            try:
                data = yf.Ticker(ticker).history(period="5d")
                if not data.empty and len(data) >= 2:
                    close_curr = data['Close'].iloc[-1]
                    close_prev = data['Close'].iloc[-2]
                    change_pct = ((close_curr - close_prev) / close_prev) * 100
                    market_summary += f"- {name}: {close_curr:.2f} ({change_pct:+.2f}% heute)\n"
            except Exception as e_tick:
                print(f"Hinweis: Ticker {ticker} fehlerhaft: {e_tick}")
    except Exception as e_all:
        print(f"yfinance Fehler: {e_all}")
        market_summary = "- Finanzdaten aktuell eingeschränkt verfügbar.\n"

    return market_summary if market_summary else "- Finanzdaten im Wartestand.\n"

live_market_context = get_live_market_data()

# B. VOLLSTÄNDIGER VOLL-QUELLENPOOL (GEWICHTET INKL. EXPANDED REDDIT MATRIX)
SOURCES = [
    # 🏛️ 1. ZENTRALBANKEN & MAKRO-INSTITUTIONEN (Gewicht: 1.0)
    {"name": "Federal Reserve Press", "url": "https://www.federalreserve.gov/feeds/press_all.xml", "cat": "Zentralbank", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "EZB (Europäische Zentralbank)", "url": "https://www.ecb.europa.eu/rss/press.html", "cat": "Zentralbank", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "BIS (Bank f. Intl. Zahlungsausgleich)", "url": "https://www.bis.org/doclist/all.rss", "cat": "Zentralbank", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "IMF News", "url": "https://www.imf.org/en/News/rss", "cat": "Intl. Org", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "Weltbank News", "url": "https://www.worldbank.org/en/news/rss", "cat": "Intl. Org", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "OECD Newsroom", "url": "https://www.oecd.org/newsroom/index.xml", "cat": "Intl. Org", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "EU-Kommission Press", "url": "https://ec.europa.eu/commission/presscorner/api/rss", "cat": "Regierung/EU", "weight": 1.00, "bias": "WESTERN"},
    {"name": "Europäischer Rat", "url": "https://www.consilium.europa.eu/en/rss/", "cat": "Regierung/EU", "weight": 1.00, "bias": "WESTERN"},
    {"name": "White House Briefing", "url": "https://www.whitehouse.gov/briefing-room/feed/", "cat": "Regierung", "weight": 1.00, "bias": "WESTERN"},
    {"name": "US Department of State", "url": "https://www.state.gov/rss-feed/press-releases/feed/", "cat": "Diplomatie", "weight": 1.00, "bias": "WESTERN"},
    {"name": "Schweizer Bundesrat", "url": "https://www.admin.ch/gov/de/start/dokumentation/medienmitteilungen.rss.html", "cat": "Regierung", "weight": 1.00, "bias": "WESTERN"},

    # 📰 2. NACHRICHTENAGENTUREN (Gewicht: 0.95)
    {"name": "AP News World", "url": "https://news.google.com/rss/search?q=when:24h+source:Associated+Press&hl=en-US&gl=US&ceid=US:en", "cat": "Agentur", "weight": 0.95, "bias": "MAINSTREAM"},
    {"name": "Reuters World", "url": "https://news.google.com/rss/search?q=when:24h+source:Reuters&hl=en-US&gl=US&ceid=US:en", "cat": "Agentur", "weight": 0.95, "bias": "MAINSTREAM"},
    {"name": "AFP World", "url": "https://news.google.com/rss/search?q=when:24h+source:Agence+France-Presse&hl=en-US&gl=US&ceid=US:en", "cat": "Agentur", "weight": 0.95, "bias": "MAINSTREAM"},
    {"name": "Kyodo News (Japan)", "url": "https://english.kyodonews.net/rss/news.xml", "cat": "Agentur", "weight": 0.95, "bias": "MAINSTREAM"},

    # 🛡️ 3. OSINT, VERTEIDIGUNG & SATELLITEN (Gewicht: 0.85)
    {"name": "ISW (Institute f. Study of War)", "url": "https://www.understandingwar.org/rss.xml", "cat": "OSINT / Militär", "weight": 0.85, "bias": "WESTERN"},
    {"name": "US Naval Institute News", "url": "https://news.usni.org/feed", "cat": "Marine / AIS OSINT", "weight": 0.85, "bias": "WESTERN"},
    {"name": "Naval News", "url": "https://www.navalnews.com/feed/", "cat": "Schifffahrt & Marine", "weight": 0.85, "bias": "WESTERN"},
    {"name": "War on the Rocks", "url": "https://warontherocks.com/feed/", "cat": "Militäranalyse", "weight": 0.85, "bias": "WESTERN"},
    {"name": "Bellingcat OSINT", "url": "https://www.bellingcat.com/feed/", "cat": "OSINT / Satellit", "weight": 0.85, "bias": "ALTERNATIVE"},
    {"name": "Münchner Sicherheitskonferenz", "url": "https://securityconference.org/news/rss/", "cat": "Sicherheit", "weight": 0.85, "bias": "WESTERN"},

    # 🌍 4. BRICS, DIPLOMATIE & GLOBALER SÜDEN (Gewicht: 0.85 - 1.00)
    {"name": "Kremlin News", "url": "http://en.kremlin.ru/rss/news", "cat": "Regierung", "weight": 1.00, "bias": "BRICS"},
    {"name": "Russisches Außenministerium", "url": "https://mid.ru/en/rss.php", "cat": "Diplomatie", "weight": 1.00, "bias": "BRICS"},
    {"name": "Chinesisches Außenministerium", "url": "https://www.fmprc.gov.cn/eng/zxmz/rss.xml", "cat": "Diplomatie", "weight": 1.00, "bias": "BRICS"},
    {"name": "Indisches Außenministerium", "url": "https://www.mea.gov.in/rss.xml", "cat": "Diplomatie", "weight": 1.00, "bias": "BRICS"},
    {"name": "CGTN World", "url": "https://news.cgtn.com/rss/World.xml", "cat": "Staatsmedien", "weight": 0.85, "bias": "BRICS"},
    {"name": "TASS World", "url": "https://tass.com/rss/v2.xml", "cat": "Staatsmedien", "weight": 0.85, "bias": "BRICS"},
    {"name": "Economic Times (Indien)", "url": "https://economictimes.indiatimes.com/rssfeedstopstories.cms", "cat": "Medien", "weight": 0.85, "bias": "BRICS"},
    {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml", "cat": "Medien", "weight": 0.85, "bias": "BRICS"},
    {"name": "South China Morning Post", "url": "https://www.scmp.com/rss/91/feed", "cat": "Medien", "weight": 0.85, "bias": "BRICS"},
    {"name": "The Cradle", "url": "https://thecradle.co/feed", "cat": "Fachmedien", "weight": 0.85, "bias": "BRICS"},
    {"name": "Asia Times", "url": "https://asiatimes.com/feed/", "cat": "Fachmedien", "weight": 0.85, "bias": "BRICS"},

    # 🏛️ 5. THINK TANKS & AKADEMIE (Gewicht: 0.75)
    {"name": "CSIS Org", "url": "https://www.csis.org/rss.xml", "cat": "Think Tank", "weight": 0.75, "bias": "WESTERN"},
    {"name": "CFR (Council Foreign Relations)", "url": "https://www.cfr.org/rss.xml", "cat": "Think Tank", "weight": 0.75, "bias": "WESTERN"},
    {"name": "ECFR Europe", "url": "https://ecfr.eu/feed/", "cat": "Think Tank", "weight": 0.75, "bias": "WESTERN"},
    {"name": "SWP Berlin", "url": "https://www.swp-berlin.org/rss.xml", "cat": "Think Tank", "weight": 0.75, "bias": "WESTERN"},
    {"name": "World Economic Forum", "url": "https://www.weforum.org/agenda/feed/", "cat": "Think Tank", "weight": 0.75, "bias": "WESTERN"},

    # 📈 6. MAINSTREAM FINANZEN & POLITIK (Gewicht: 0.85)
    {"name": "CNBC Finance", "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "cat": "Finanzen", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Foreign Policy", "url": "https://foreignpolicy.com/feed/", "cat": "Politik", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Nikkei Asia", "url": "https://asia.nikkei.com/rss/feed/nar", "cat": "Finanzen", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Handelsblatt", "url": "https://www.handelsblatt.com/contentexport/feed/finanzen", "cat": "Finanzen", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Finanzmarktwelt", "url": "https://finanzmarktwelt.de/feed/", "cat": "Finanzen", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "NZZ", "url": "https://www.nzz.ch/international.rss", "cat": "Medien", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "FAZ", "url": "https://www.faz.net/rss/aktuell/politik/ausland/", "cat": "Medien", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Tagesschau", "url": "https://www.tagesschau.de/ausland/index.xml", "cat": "Medien", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "BBC World", "url": "http://feeds.bbci.co.uk/news/world/rss.xml", "cat": "Medien", "weight": 0.85, "bias": "MAINSTREAM"},

    # 👥 7. REDDIT OSINT & FINANZ COMMUNITIES (Gewicht: 0.60)
    {"name": "Reddit r/geopolitics", "url": "https://www.reddit.com/r/geopolitics/hot.rss?limit=5", "cat": "Community OSINT", "weight": 0.60, "bias": "MIXED"},
    {"name": "Reddit r/OSINT", "url": "https://www.reddit.com/r/OSINT/hot.rss?limit=5", "cat": "Community OSINT", "weight": 0.60, "bias": "MIXED"},
    {"name": "Reddit r/CredibleDefense", "url": "https://www.reddit.com/r/CredibleDefense/hot.rss?limit=5", "cat": "Militär OSINT", "weight": 0.65, "bias": "WESTERN"},
    {"name": "Reddit r/LessCredibleDefence", "url": "https://www.reddit.com/r/LessCredibleDefence/hot.rss?limit=5", "cat": "Militär OSINT", "weight": 0.60, "bias": "MIXED"},
    {"name": "Reddit r/Economics", "url": "https://www.reddit.com/r/Economics/hot.rss?limit=5", "cat": "Makro Community", "weight": 0.60, "bias": "MIXED"},
    {"name": "Reddit r/Macroeconomics", "url": "https://www.reddit.com/r/Macroeconomics/hot.rss?limit=5", "cat": "Makro Community", "weight": 0.60, "bias": "MIXED"},
    {"name": "Reddit r/Commodities", "url": "https://www.reddit.com/r/Commodities/hot.rss?limit=5", "cat": "Rohstoff Community", "weight": 0.60, "bias": "MIXED"},
    {"name": "Reddit r/worldnews", "url": "https://www.reddit.com/r/worldnews/hot.rss?limit=5", "cat": "World News", "weight": 0.55, "bias": "MAINSTREAM"},

    # 🔓 8. INVESTIGATIV, BLOGS & ALTERNATIVE ANALYSTEN (Gewicht: 0.40 - 0.55)
    {"name": "Multipolar Magazin", "url": "https://multipolar-magazin.de/feed", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Manova / Rubikon", "url": "https://www.manova.news/feed", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Berliner Tageszeitung", "url": "https://www.berlinertageszeitung.de/rss.xml", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Hintergrund Magazin", "url": "https://www.hintergrund.de/feed/", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Republik (Schweiz)", "url": "https://www.republik.ch/feed", "cat": "Investigativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "The Grayzone", "url": "https://thegrayzone.com/feed/", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "The Intercept", "url": "https://theintercept.com/feed/?lang=en", "cat": "Investigativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "MintPress News", "url": "https://www.mintpressnews.com/feed/", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "ZeroHedge", "url": "http://feeds.feedburner.com/zerohedge/feed", "cat": "Alternativ / Makro", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "UnHerd", "url": "https://unherd.com/feed/", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Antiwar.com", "url": "https://news.antiwar.com/feed/", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "NachDenkSeiten", "url": "https://www.nachdenkseiten.de/?feed=rss2", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Apolut", "url": "https://apolut.net/feed/", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Anti-Spiegel", "url": "https://anti-spiegel.ru/feed/", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Telepolis", "url": "https://www.telepolis.de/index.rss", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Tichys Einblick", "url": "https://www.tichyseinblick.de/feed/", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Overton Magazin", "url": "https://overton-magazin.de/feed/", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Moon of Alabama", "url": "https://www.moonofalabama.org/atom.xml", "cat": "Blogger", "weight": 0.40, "bias": "ALTERNATIVE"},
    {"name": "Caitlin Johnstone", "url": "https://caitlinjohnstone.com.au/feed/", "cat": "Blogger", "weight": 0.40, "bias": "ALTERNATIVE"}
]

browser_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 GeoPulsOSINTBot/1.0"
feed_context = ""

print("Hole und strukturiere News aus dem gewichteten Voll-Quellenpool...")
for src in SOURCES:
    try:
        feed = feedparser.parse(src["url"], agent=browser_agent)
        if feed.entries:
            feed_context += f"\n--- QUELLE: {src['name']} | Kat: {src['cat']} | Prio-Gewicht: {src['weight']} | Bias: {src['bias']} ---\n"
            for entry in feed.entries[:2]:
                title = entry.get('title', '')
                raw_summary = entry.get('summary', '') or entry.get('description', '')
                summary = clean_html(raw_summary)
                feed_context += f"- [{src['cat']}] {title}: {summary[:120]}...\n"
    except Exception as e:
        print(f"Hinweis bei Feed {src['name']}: {e}")

if len(feed_context) > 35000:
    feed_context = feed_context[:35000] + "\n... [Quellenkontext zur Token-Schonung leicht gekürzt]"

# ERWEITERTES SCHEMAS FÜR GEOSCORE, EVENT-GRAPH & KAUSALITÄTSKETTEN (PALANTIR LIGHT STAGE 2-7)
json_template_desc = """
{
  "geoscore": {
    "current_score": 78.4,
    "previous_48h": 74.1,
    "status_label": "ERHÖHTES ANSTECKUNGSRISIKO",
    "vectors": {
      "military": 82,
      "energy": 70,
      "geopolitics": 85,
      "financial_stress": 62,
      "trade_conflicts": 75,
      "supply_chains": 68,
      "liquidity": 50
    }
  },
  "event_graph": [
    {
      "event_id": "EVT-2026-001",
      "headline": "Kurze, prägnante Überschrift des gebündelten Ereignisses",
      "actors": ["USA", "China", "TSMC"],
      "category": "Handelskrieg / Technologie",
      "confidence_score": 0.92,
      "severity": 85,
      "sources_count": 12
    },
    {
      "event_id": "EVT-2026-002",
      "headline": "Schifffahrts-Einschränkungen und Tankerversicherungen steigen",
      "actors": ["Houthi", "USA", "UK"],
      "category": "Lieferketten / Energie",
      "confidence_score": 0.88,
      "severity": 78,
      "sources_count": 9
    }
  ],
  "impact_chains": [
    {
      "trigger": "Auslösendes Ereignis aus den Feeds",
      "steps": [
        "Erstfolge (z.B. Transportkosten steigen um +25%)",
        "Zweitfolge (z.B. Raffinerie-Margen verengen sich in Europa)",
        "Drittfolge (z.B. Inflationserwartung steigt, Zinssenkungen verzögert)"
      ],
      "primary_beneficiaries": ["WTI Öl", "Gold", "Rüstung"],
      "primary_detractors": ["Airlines", "Chemie", "Staatsanleihen"]
    }
  ],
  "probability_matrix": [
    { "scenario": "Eskalation Nahost-Schifffahrt", "probability_pct": 68, "trend": "RISING" },
    { "scenario": "Fed-Zinssenkung im nächsten Quartal", "probability_pct": 42, "trend": "FALLING" },
    { "scenario": "Sanktionsausweitung auf Halbleiter-Lieferanten", "probability_pct": 81, "trend": "STABLE" }
  ],
  "daily_executive_summary": "Detaillierte Synthese der geopolitischen Lage...",
  "global_risk_score": 78,
  "market_regime": "Marktregime (z.B. Stagflations-Skepsis & Risiko-Aversion)",
  "top_overweight": "Gewinner-Assets",
  "top_risk": "Hauptrisiko",
  "defcon_status": {"level": 3, "label": "DEFCON 3 - Erhöhte Wachsamkeit", "nuclear_risk_percent": 18, "primary_driver": "Treiber"},
  "narrative_divergence": [
    {"topic": "Schauplatz 1", "mainstream_view": "Mainstream/Agenturen", "brics_view": "BRICS/Diplomatie", "alternative_view": "Unabhängig/Alternativ"},
    {"topic": "Schauplatz 2", "mainstream_view": "Mainstream/Agenturen", "brics_view": "BRICS/Diplomatie", "alternative_view": "Unabhängig/Alternativ"},
    {"topic": "Schauplatz 3", "mainstream_view": "Mainstream/Agenturen", "brics_view": "BRICS/Diplomatie", "alternative_view": "Unabhängig/Alternativ"}
  ],
  "domestic_politics": [
    {"country_region": "Region 1", "topic": "Thema", "status": "Status", "impact": "Impact"},
    {"country_region": "Region 2", "topic": "Thema", "status": "Status", "impact": "Impact"},
    {"country_region": "Region 3", "topic": "Thema", "status": "Status", "impact": "Impact"}
  ],
  "stock_picks": {
    "top_5_buys": [{"ticker": "T1", "name": "N1", "sector": "S1", "reason": "R1"}, {"ticker": "T2", "name": "N2", "sector": "S2", "reason": "R2"}, {"ticker": "T3", "name": "N3", "sector": "S3", "reason": "R3"}, {"ticker": "T4", "name": "N4", "sector": "S4", "reason": "R4"}, {"ticker": "T5", "name": "N5", "sector": "S5", "reason": "R5"}],
    "flop_5_sells": [{"ticker": "S1", "name": "N1", "sector": "S1", "reason": "R1"}, {"ticker": "S2", "name": "N2", "sector": "S2", "reason": "R2"}, {"ticker": "S3", "name": "N3", "sector": "S3", "reason": "R3"}, {"ticker": "S4", "name": "N4", "sector": "S4", "reason": "R4"}, {"ticker": "S5", "name": "N5", "sector": "S5", "reason": "R5"}]
  },
  "conflict_hotspots": [
    {"region": "R1", "actors": "A1", "escalation_level": "KRITISCH", "catalyst": "C1", "impact": "I1", "lat": 31.5, "lng": 34.75},
    {"region": "R2", "actors": "A2", "escalation_level": "HOCH", "catalyst": "C2", "impact": "I2", "lat": 48.37, "lng": 31.16},
    {"region": "R3", "actors": "A3", "escalation_level": "HOCH", "catalyst": "C3", "impact": "I3", "lat": 23.69, "lng": 120.96},
    {"region": "R4", "actors": "A4", "escalation_level": "MITTEL", "catalyst": "C4", "impact": "I4", "lat": 12.58, "lng": 43.33}
  ],
  "systemic_risks": [
    {"topic": "T1", "category": "C1", "risk_level": "HOCH", "status": "S1", "impact": "I1"},
    {"topic": "T2", "category": "C2", "risk_level": "HOCH", "status": "S2", "impact": "I2"},
    {"topic": "T3", "category": "C3", "risk_level": "MITTEL", "status": "S3", "impact": "I3"}
  ],
  "assets": [
    {"name": "Gold & Silber", "signal": "GREEN", "signal_text": "🟢 Attraktiv", "trend": "T", "driver": "D"},
    {"name": "KI & Halbleiter", "signal": "GREEN", "signal_text": "🟢 Attraktiv", "trend": "T", "driver": "D"},
    {"name": "Uran & Energie", "signal": "GREEN", "signal_text": "🟢 Attraktiv", "trend": "T", "driver": "D"},
    {"name": "S&P 500 / Nasdaq", "signal": "AMBER", "signal_text": "🟡 Neutral", "trend": "T", "driver": "D"},
    {"name": "Bitcoin & Krypto", "signal": "AMBER", "signal_text": "🟡 Neutral", "trend": "T", "driver": "D"},
    {"name": "High-Yield Bonds", "signal": "RED", "signal_text": "🔴 Unattraktiv", "trend": "T", "driver": "D"},
    {"name": "Gewerbeimmobilien", "signal": "RED", "signal_text": "🔴 Meiden", "trend": "T", "driver": "D"}
  ],
  "scenarios": [
    {"title": "S1", "prob": 40},
    {"title": "S2", "prob": 30},
    {"title": "S3", "prob": 15},
    {"title": "S4", "prob": 15}
  ]
}
"""

raw_text = None
generator_used = "Claude 3.5 Sonnet"

anth_key = os.environ.get("ANTHROPIC_API_KEY")
if not anth_key:
    raise ValueError("ANTHROPIC_API_KEY wurde nicht in den Umgebungsvariablen gefunden!")

client_anthropic = anthropic.Anthropic(api_key=anth_key)

system_instruction = (
    "Du bist der Chef-Analyst und OSINT-Spezialist eines hochmodernen Geopolitik-Lagezentrums ('Palantir Light'). "
    "DEINE AUFGABE: Berechne den synthetischen GeoScore (0-100), erstelle aus den Rohnachrichten einen deduplizierten Event-Graphen, berechne mehrstufige Kausalitätsketten (Impact Chains) und gewichte alle Erkenntnisse anhand der Quellenprioritäten. "
    "STRIKTE GEWICHTUNGSRULE: Stütze deine Faktenanalyse primär auf Quellen mit hohem Gewicht (0.85 bis 1.0, z.B. Zentralbanken, Regierungen, Agenturen, USNI Marine-OSINT, ISW). "
    "Nutze Blogs & Community-Quellen (0.40 bis 0.60) ausschließlich für die 'alternative_view' in der Narrativ-Matrix und zur Erfassung von Gegen-Narrativen. "
    "Antworte AUSSCHLIESSLICH im rein validen JSON-Format basierend auf diesem Schema:\n" + json_template_desc
)

claude_models = ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"]
for model_name in claude_models:
    try:
        print(f"Generiere Palantir Light Lagebild mit Anthropic {model_name}...")
        response = client_anthropic.messages.create(
            model=model_name,
            max_tokens=4000,
            temperature=0.2,
            system=system_instruction,
            messages=[{"role": "user", "content": f"Live-Rohstoffe & Marktdaten:\n{live_market_context}\n\nGewichteter OSINT-Kontext:\n{feed_context}"}]
        )
        raw_text = response.content[0].text.strip()
        generator_used = f"Anthropic ({model_name})"
        break
    except Exception as e:
        print(f"Hinweis: {model_name} nicht erreichbar: {e}")

if not raw_text:
    raise RuntimeError("Fehler: Anthropic konnte keine Antwort generieren. Bitte Key prüfen.")

if raw_text.startswith("```"):
    raw_text = re.sub(r"^```[a-zA-Z]*\n?", "", raw_text)
    raw_text = re.sub(r"\n?```$", "", raw_text)

data = json.loads(raw_text)

# NORMALISIERUNG ALLER FELDER
if not data.get("daily_executive_summary"):
    data["daily_executive_summary"] = data.get("executive_summary") or data.get("summary") or "Die geopolitische Lage bleibt angespannt."

raw_nd = data.get("narrative_divergence", [])
if isinstance(raw_nd, dict):
    raw_nd = [raw_nd]

normalized_nd = []
for item in raw_nd:
    if isinstance(item, dict):
        normalized_nd.append({
            "topic": item.get("topic") or "Geopolitischer Schauplatz",
            "mainstream_view": item.get("mainstream_view") or item.get("mainstream") or "Fokus auf westliche Ordnung.",
            "brics_view": item.get("brics_view") or item.get("brics") or "Fokus auf multipolare Perspektive.",
            "alternative_view": item.get("alternative_view") or item.get("alternative") or "Fokus auf Kaskadeneffekte."
        })

data["narrative_divergence"] = normalized_nd

GEO_LOOKUP = {
    "nah": (31.5, 34.75), "iran": (32.42, 53.68), "israel": (31.04, 34.85),
    "ukraine": (48.37, 31.16), "taiwan": (23.69, 120.96), "rot": (12.58, 43.33),
    "bab": (12.58, 43.33), "moldaw": (47.01, 28.86), "transnistrien": (46.84, 29.63),
    "balkan": (43.85, 18.35), "kaukasus": (41.71, 44.78), "suwalki": (54.1, 22.9),
    "china": (35.86, 104.19), "korea": (38.31, 127.23)
}

for h in data.get("conflict_hotspots", []):
    try:
        h["lat"] = float(h.get("lat"))
        h["lng"] = float(h.get("lng"))
    except (ValueError, TypeError):
        reg_lower = h.get("region", "").lower()
        found = False
        for key, coords in GEO_LOOKUP.items():
            if key in reg_lower:
                h["lat"], h["lng"] = coords
                found = True
                break
        if not found or h["lat"] == 0.0:
            h["lat"], h["lng"] = 25.0, 45.0

data["timestamp"] = datetime.utcnow().strftime("%d.%m.%Y - %H:%M UTC")

# Historie tracken (inkl. GeoScore)
history_file = "history.json"
history_data = []
if os.path.exists(history_file):
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            history_data = json.load(f)
    except Exception:
        history_data = []

today_str = datetime.utcnow().strftime("%d.%m")
geoscore_val = data.get("geoscore", {}).get("current_score") or data.get("global_risk_score", 75)

if not history_data or history_data[-1].get("date") != today_str:
    history_data.append({
        "date": today_str,
        "score": geoscore_val,
        "defcon": data.get("defcon_status", {}).get("level", 3)
    })
    history_data = history_data[-30:]
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"OSINT Lagezentrum erfolgreich mit GeoScore & Event-Graph (Claude {generator_used}) aktualisiert!")
