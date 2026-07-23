import os
import json
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
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

# Automatische Reparatur für eventuell abgeschnittene JSON-Strings
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

# B. HIGH-PRECISION MULTI-DOMAIN QUELLENMATRIX (90+ SPEZIAL-FEEDS)
SOURCES = [
    # 🏛️ 1. ZENTRALBANKEN & MAKRO-INSTITUTIONEN (Gewicht: 1.0)
    {"name": "Federal Reserve Press", "url": "[https://www.federalreserve.gov/feeds/press_all.xml](https://www.federalreserve.gov/feeds/press_all.xml)", "cat": "Zentralbank", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "EZB (Europäische Zentralbank)", "url": "[https://www.ecb.europa.eu/rss/press.html](https://www.ecb.europa.eu/rss/press.html)", "cat": "Zentralbank", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "BIS (Bank f. Intl. Zahlungsausgleich)", "url": "[https://www.bis.org/doclist/all.rss](https://www.bis.org/doclist/all.rss)", "cat": "Zentralbank", "weight": 1.00, "bias": "OFFIZIELL"},
    {"name": "IMF News", "url": "[https://www.imf.org/en/News/rss](https://www.imf.org/en/News/rss)", "cat": "Intl. Org", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "Weltbank News", "url": "[https://www.worldbank.org/en/news/rss](https://www.worldbank.org/en/news/rss)", "cat": "Intl. Org", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "OECD Newsroom", "url": "[https://www.oecd.org/newsroom/index.xml](https://www.oecd.org/newsroom/index.xml)", "cat": "Intl. Org", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "EU-Kommission Press", "url": "[https://ec.europa.eu/commission/presscorner/api/rss](https://ec.europa.eu/commission/presscorner/api/rss)", "cat": "Regierung/EU", "weight": 1.00, "bias": "WESTERN"},
    {"name": "Europäischer Rat", "url": "[https://www.consilium.europa.eu/en/rss/](https://www.consilium.europa.eu/en/rss/)", "cat": "Regierung/EU", "weight": 1.00, "bias": "WESTERN"},
    {"name": "White House Briefing", "url": "[https://www.whitehouse.gov/briefing-room/feed/](https://www.whitehouse.gov/briefing-room/feed/)", "cat": "Regierung", "weight": 1.00, "bias": "WESTERN"},
    {"name": "US Department of State", "url": "[https://www.state.gov/rss-feed/press-releases/feed/](https://www.state.gov/rss-feed/press-releases/feed/)", "cat": "Diplomatie", "weight": 1.00, "bias": "WESTERN"},
    {"name": "Schweizer Bundesrat", "url": "[https://www.admin.ch/gov/de/start/dokumentation/medienmitteilungen.rss.html](https://www.admin.ch/gov/de/start/dokumentation/medienmitteilungen.rss.html)", "cat": "Regierung", "weight": 1.00, "bias": "WESTERN"},

    # 🛡️ 2. MILITÄR, OSINT, SATELLITEN & KATASTROPHEN (Gewicht: 0.85 - 0.95)
    {"name": "NASA FIRMS Fire & Hazards", "url": "[https://earthobservatory.nasa.gov/feeder/natural_hazards.rss](https://earthobservatory.nasa.gov/feeder/natural_hazards.rss)", "cat": "OSINT / Satellit", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "USGS Earthquakes (M5.5+)", "url": "[https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/5.5_day.atom](https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/5.5_day.atom)", "cat": "Seismik / Warnsystem", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "GDACS Global Disaster Alerts", "url": "[https://www.gdacs.org/xml/rss.xml](https://www.gdacs.org/xml/rss.xml)", "cat": "Frühwarnung", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "ISW (Institute f. Study of War)", "url": "[https://www.understandingwar.org/rss.xml](https://www.understandingwar.org/rss.xml)", "cat": "OSINT / Militär", "weight": 0.85, "bias": "WESTERN"},
    {"name": "US Naval Institute News", "url": "[https://news.usni.org/feed](https://news.usni.org/feed)", "cat": "Marine / AIS OSINT", "weight": 0.85, "bias": "WESTERN"},
    {"name": "Naval News", "url": "[https://www.navalnews.com/feed/](https://www.navalnews.com/feed/)", "cat": "Schifffahrt & Marine", "weight": 0.85, "bias": "WESTERN"},
    {"name": "War on the Rocks", "url": "[https://warontherocks.com/feed/](https://warontherocks.com/feed/)", "cat": "Militäranalyse", "weight": 0.85, "bias": "WESTERN"},
    {"name": "Bellingcat OSINT", "url": "[https://www.bellingcat.com/feed/](https://www.bellingcat.com/feed/)", "cat": "OSINT / Satellit", "weight": 0.85, "bias": "ALTERNATIVE"},
    {"name": "Critical Threats Project", "url": "[https://www.criticalthreats.org/rss/articles](https://www.criticalthreats.org/rss/articles)", "cat": "Militär OSINT", "weight": 0.85, "bias": "WESTERN"},

    # 💻 3. CYBER WARFARE, HYBRIDE BEDROHUNGEN & INFRASTRUKTUR (Gewicht: 0.90)
    {"name": "CISA Cyber Alerts (US)", "url": "[https://www.cisa.gov/cybersecurity-advisories/all.xml](https://www.cisa.gov/cybersecurity-advisories/all.xml)", "cat": "Cyber / Infrastruktur", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "CERT-EU Security Alerts", "url": "[https://cert.europa.eu/publications/warnings/feed.xml](https://cert.europa.eu/publications/warnings/feed.xml)", "cat": "Cyber / Infrastruktur", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "Dark Reading Cyber Intelligence", "url": "[https://www.darkreading.com/rss.xml](https://www.darkreading.com/rss.xml)", "cat": "Cyber Warfare", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Submarine Telecoms Cable News", "url": "[https://subtelforum.com/feed/](https://subtelforum.com/feed/)", "cat": "Seekabel / Infrastruktur", "weight": 0.90, "bias": "MAINSTREAM"},
    {"name": "Offshore Energy Today", "url": "[https://www.offshore-energy.biz/feed/](https://www.offshore-energy.biz/feed/)", "cat": "Energie / Pipelines", "weight": 0.85, "bias": "MAINSTREAM"},

    # 🚢 4. MARITIME SECURITY & LOGISTIK (Gewicht: 0.85 - 0.95)
    {"name": "UKMTO (UK Maritime Trade Ops)", "url": "[https://news.google.com/rss/search?q=when:24h+UKMTO+OR+%22Maritime+Trade+Operations%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:24h+UKMTO+OR+%22Maritime+Trade+Operations%22&hl=en-US&gl=US&ceid=US:en)", "cat": "Schifffahrt OSINT", "weight": 0.95, "bias": "OFFIZIELL"},
    {"name": "gCaptain Maritime News", "url": "[https://gcaptain.com/feed/](https://gcaptain.com/feed/)", "cat": "Schifffahrt", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Splash247 Shipping Intelligence", "url": "[https://splash247.com/feed/](https://splash247.com/feed/)", "cat": "Schifffahrt", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Maritime Executive", "url": "[https://maritime-executive.com/rss](https://maritime-executive.com/rss)", "cat": "Schifffahrt", "weight": 0.85, "bias": "MAINSTREAM"},

    # ✈️ 5. LUFTFAHRT, GPS-JAMMING & AIRSPACE OSINT (Gewicht: 0.85 - 0.90)
    {"name": "Flightradar24 News & Incidents", "url": "[https://www.flightradar24.com/blog/feed/](https://www.flightradar24.com/blog/feed/)", "cat": "Luftfahrt OSINT", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Aviation Safety Network (ASN)", "url": "[https://news.google.com/rss/search?q=when:24h+site:aviation-safety.net+OR+%22airspace+closure%22+OR+%22NOTAM%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:24h+site:aviation-safety.net+OR+%22airspace+closure%22+OR+%22NOTAM%22&hl=en-US&gl=US&ceid=US:en)", "cat": "Luftfahrt OSINT", "weight": 0.90, "bias": "OFFIZIELL"},
    {"name": "GPSJam & Electronic Warfare Alerts", "url": "[https://news.google.com/rss/search?q=when:24h+%22GPS+jamming%22+OR+%22ADS-B+spoofing%22+OR+%22NOTAM%22&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:24h+%22GPS+jamming%22+OR+%22ADS-B+spoofing%22+OR+%22NOTAM%22&hl=en-US&gl=US&ceid=US:en)", "cat": "EW / Luftfahrt", "weight": 0.85, "bias": "ALTERNATIVE"},

    # 📰 6. NACHRICHTENAGENTUREN (Gewicht: 0.95)
    {"name": "AP News World", "url": "[https://news.google.com/rss/search?q=when:24h+source:Associated+Press&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:24h+source:Associated+Press&hl=en-US&gl=US&ceid=US:en)", "cat": "Agentur", "weight": 0.95, "bias": "MAINSTREAM"},
    {"name": "Reuters World", "url": "[https://news.google.com/rss/search?q=when:24h+source:Reuters&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:24h+source:Reuters&hl=en-US&gl=US&ceid=US:en)", "cat": "Agentur", "weight": 0.95, "bias": "MAINSTREAM"},
    {"name": "AFP World", "url": "[https://news.google.com/rss/search?q=when:24h+source:Agence+France-Presse&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=when:24h+source:Agence+France-Presse&hl=en-US&gl=US&ceid=US:en)", "cat": "Agentur", "weight": 0.95, "bias": "MAINSTREAM"},
    {"name": "Kyodo News (Japan)", "url": "[https://english.kyodonews.net/rss/news.xml](https://english.kyodonews.net/rss/news.xml)", "cat": "Agentur", "weight": 0.95, "bias": "MAINSTREAM"},

    # 🌍 7. BRICS, DIPLOMATIE & GLOBALER SÜDEN (Gewicht: 0.85 - 1.00)
    {"name": "Kremlin News", "url": "[http://en.kremlin.ru/rss/news](http://en.kremlin.ru/rss/news)", "cat": "Regierung", "weight": 1.00, "bias": "BRICS"},
    {"name": "Russisches Außenministerium", "url": "[https://mid.ru/en/rss.php](https://mid.ru/en/rss.php)", "cat": "Diplomatie", "weight": 1.00, "bias": "BRICS"},
    {"name": "Chinesisches Außenministerium", "url": "[https://www.fmprc.gov.cn/eng/zxmz/rss.xml](https://www.fmprc.gov.cn/eng/zxmz/rss.xml)", "cat": "Diplomatie", "weight": 1.00, "bias": "BRICS"},
    {"name": "Indisches Außenministerium", "url": "[https://www.mea.gov.in/rss.xml](https://www.mea.gov.in/rss.xml)", "cat": "Diplomatie", "weight": 1.00, "bias": "BRICS"},
    {"name": "CGTN World", "url": "[https://news.cgtn.com/rss/World.xml](https://news.cgtn.com/rss/World.xml)", "cat": "Staatsmedien", "weight": 0.85, "bias": "BRICS"},
    {"name": "TASS World", "url": "[https://tass.com/rss/v2.xml](https://tass.com/rss/v2.xml)", "cat": "Staatsmedien", "weight": 0.85, "bias": "BRICS"},
    {"name": "Economic Times (Indien)", "url": "[https://economictimes.indiatimes.com/rssfeedstopstories.cms](https://economictimes.indiatimes.com/rssfeedstopstories.cms)", "cat": "Medien", "weight": 0.85, "bias": "BRICS"},
    {"name": "Al Jazeera", "url": "[https://www.aljazeera.com/xml/rss/all.xml](https://www.aljazeera.com/xml/rss/all.xml)", "cat": "Medien", "weight": 0.85, "bias": "BRICS"},
    {"name": "South China Morning Post", "url": "[https://www.scmp.com/rss/91/feed](https://www.scmp.com/rss/91/feed)", "cat": "Medien", "weight": 0.85, "bias": "BRICS"},
    {"name": "The Cradle", "url": "[https://thecradle.co/feed](https://thecradle.co/feed)", "cat": "Fachmedien", "weight": 0.85, "bias": "BRICS"},
    {"name": "Asia Times", "url": "[https://asiatimes.com/feed/](https://asiatimes.com/feed/)", "cat": "Fachmedien", "weight": 0.85, "bias": "BRICS"},

    # 🏛️ 8. THINK TANKS & AKADEMIE (Gewicht: 0.75)
    {"name": "CSIS Org", "url": "[https://www.csis.org/rss.xml](https://www.csis.org/rss.xml)", "cat": "Think Tank", "weight": 0.75, "bias": "WESTERN"},
    {"name": "CFR (Council Foreign Relations)", "url": "[https://www.cfr.org/rss.xml](https://www.cfr.org/rss.xml)", "cat": "Think Tank", "weight": 0.75, "bias": "WESTERN"},
    {"name": "ECFR Europe", "url": "[https://ecfr.eu/feed/](https://ecfr.eu/feed/)", "cat": "Think Tank", "weight": 0.75, "bias": "WESTERN"},
    {"name": "SWP Berlin", "url": "[https://www.swp-berlin.org/rss.xml](https://www.swp-berlin.org/rss.xml)", "cat": "Think Tank", "weight": 0.75, "bias": "WESTERN"},
    {"name": "World Economic Forum", "url": "[https://www.weforum.org/agenda/feed/](https://www.weforum.org/agenda/feed/)", "cat": "Think Tank", "weight": 0.75, "bias": "WESTERN"},

    # 📈 9. MAINSTREAM FINANZEN & POLITIK (Gewicht: 0.85)
    {"name": "CNBC Finance", "url": "[https://www.cnbc.com/id/100003114/device/rss/rss.html](https://www.cnbc.com/id/100003114/device/rss/rss.html)", "cat": "Finanzen", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Foreign Policy", "url": "[https://foreignpolicy.com/feed/](https://foreignpolicy.com/feed/)", "cat": "Politik", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Nikkei Asia", "url": "[https://asia.nikkei.com/rss/feed/nar](https://asia.nikkei.com/rss/feed/nar)", "cat": "Finanzen", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Handelsblatt", "url": "[https://www.handelsblatt.com/contentexport/feed/finanzen](https://www.handelsblatt.com/contentexport/feed/finanzen)", "cat": "Finanzen", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Finanzmarktwelt", "url": "[https://finanzmarktwelt.de/feed/](https://finanzmarktwelt.de/feed/)", "cat": "Finanzen", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "NZZ", "url": "[https://www.nzz.ch/international.rss](https://www.nzz.ch/international.rss)", "cat": "Medien", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "FAZ", "url": "[https://www.faz.net/rss/aktuell/politik/ausland/](https://www.faz.net/rss/aktuell/politik/ausland/)", "cat": "Medien", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "Tagesschau", "url": "[https://www.tagesschau.de/ausland/index.xml](https://www.tagesschau.de/ausland/index.xml)", "cat": "Medien", "weight": 0.85, "bias": "MAINSTREAM"},
    {"name": "BBC World", "url": "[http://feeds.bbci.co.uk/news/world/rss.xml](http://feeds.bbci.co.uk/news/world/rss.xml)", "cat": "Medien", "weight": 0.85, "bias": "MAINSTREAM"},

    # 👥 10. REDDIT OSINT & FINANZ COMMUNITIES (Gewicht: 0.60)
    {"name": "Reddit r/geopolitics", "url": "[https://www.reddit.com/r/geopolitics/hot.rss?limit=5](https://www.reddit.com/r/geopolitics/hot.rss?limit=5)", "cat": "Community OSINT", "weight": 0.60, "bias": "MIXED"},
    {"name": "Reddit r/OSINT", "url": "[https://www.reddit.com/r/OSINT/hot.rss?limit=5](https://www.reddit.com/r/OSINT/hot.rss?limit=5)", "cat": "Community OSINT", "weight": 0.60, "bias": "MIXED"},
    {"name": "Reddit r/CredibleDefense", "url": "[https://www.reddit.com/r/CredibleDefense/hot.rss?limit=5](https://www.reddit.com/r/CredibleDefense/hot.rss?limit=5)", "cat": "Militär OSINT", "weight": 0.65, "bias": "WESTERN"},
    {"name": "Reddit r/LessCredibleDefence", "url": "[https://www.reddit.com/r/LessCredibleDefence/hot.rss?limit=5](https://www.reddit.com/r/LessCredibleDefence/hot.rss?limit=5)", "cat": "Militär OSINT", "weight": 0.60, "bias": "MIXED"},
    {"name": "Reddit r/Economics", "url": "[https://www.reddit.com/r/Economics/hot.rss?limit=5](https://www.reddit.com/r/Economics/hot.rss?limit=5)", "cat": "Makro Community", "weight": 0.60, "bias": "MIXED"},
    {"name": "Reddit r/Macroeconomics", "url": "[https://www.reddit.com/r/Macroeconomics/hot.rss?limit=5](https://www.reddit.com/r/Macroeconomics/hot.rss?limit=5)", "cat": "Makro Community", "weight": 0.60, "bias": "MIXED"},
    {"name": "Reddit r/Commodities", "url": "[https://www.reddit.com/r/Commodities/hot.rss?limit=5](https://www.reddit.com/r/Commodities/hot.rss?limit=5)", "cat": "Rohstoff Community", "weight": 0.60, "bias": "MIXED"},
    {"name": "Reddit r/worldnews", "url": "[https://www.reddit.com/r/worldnews/hot.rss?limit=5](https://www.reddit.com/r/worldnews/hot.rss?limit=5)", "cat": "World News", "weight": 0.55, "bias": "MAINSTREAM"},

    # 🔓 11. INVESTIGATIV, BLOGS & ALTERNATIVE ANALYSTEN (Gewicht: 0.40 - 0.55)
    {"name": "Multipolar Magazin", "url": "[https://multipolar-magazin.de/feed](https://multipolar-magazin.de/feed)", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Manova / Rubikon", "url": "[https://www.manova.news/feed](https://www.manova.news/feed)", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Berliner Tageszeitung", "url": "[https://www.berlinertageszeitung.de/rss.xml](https://www.berlinertageszeitung.de/rss.xml)", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Hintergrund Magazin", "url": "[https://www.hintergrund.de/feed/](https://www.hintergrund.de/feed/)", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Republik (Schweiz)", "url": "[https://www.republik.ch/feed](https://www.republik.ch/feed)", "cat": "Investigativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "The Grayzone", "url": "[https://thegrayzone.com/feed/](https://thegrayzone.com/feed/)", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "The Intercept", "url": "[https://theintercept.com/feed/?lang=en](https://theintercept.com/feed/?lang=en)", "cat": "Investigativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "MintPress News", "url": "[https://www.mintpressnews.com/feed/](https://www.mintpressnews.com/feed/)", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "ZeroHedge", "url": "[http://feeds.feedburner.com/zerohedge/feed](http://feeds.feedburner.com/zerohedge/feed)", "cat": "Alternativ / Makro", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "UnHerd", "url": "[https://unherd.com/feed/](https://unherd.com/feed/)", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Antiwar.com", "url": "[https://news.antiwar.com/feed/](https://news.antiwar.com/feed/)", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "NachDenkSeiten", "url": "[https://www.nachdenkseiten.de/?feed=rss2](https://www.nachdenkseiten.de/?feed=rss2)", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Apolut", "url": "[https://apolut.net/feed/](https://apolut.net/feed/)", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Anti-Spiegel", "url": "[https://anti-spiegel.ru/feed/](https://anti-spiegel.ru/feed/)", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Telepolis", "url": "[https://www.telepolis.de/index.rss](https://www.telepolis.de/index.rss)", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Tichys Einblick", "url": "[https://www.tichyseinblick.de/feed/](https://www.tichyseinblick.de/feed/)", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Overton Magazin", "url": "[https://overton-magazin.de/feed/](https://overton-magazin.de/feed/)", "cat": "Alternativ", "weight": 0.55, "bias": "ALTERNATIVE"},
    {"name": "Moon of Alabama", "url": "[https://www.moonofalabama.org/atom.xml](https://www.moonofalabama.org/atom.xml)", "cat": "Blogger", "weight": 0.40, "bias": "ALTERNATIVE"},
    {"name": "Caitlin Johnstone", "url": "[https://caitlinjohnstone.com.au/feed/](https://caitlinjohnstone.com.au/feed/)", "cat": "Blogger", "weight": 0.40, "bias": "ALTERNATIVE"}
]

browser_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 ArgusGridOSINTBot/1.0"

# C. PARALLEL SCRAPING METHODE VIA THREADPOOLEXECUTOR
def fetch_single_feed(src):
    feed_str = ""
    try:
        feed = feedparser.parse(src["url"], agent=browser_agent)
        if feed.entries:
            feed_str += f"\n--- QUELLE: {src['name']} | Kat: {src['cat']} | Prio-Gewicht: {src['weight']} | Bias: {src['bias']} ---\n"
            for entry in feed.entries[:2]:
                title = entry.get('title', '')
                raw_summary = entry.get('summary', '') or entry.get('description', '')
                summary = clean_html(raw_summary)
                feed_str += f"- [{src['cat']}] {title}: {summary[:120]}...\n"
    except Exception as e:
        print(f"Hinweis bei Feed {src['name']}: {e}")
    return feed_str

print("Hole und strukturiere News aus dem gewichteten Voll-Quellenpool (parallel via ThreadPoolExecutor)...")
feed_context = ""

with ThreadPoolExecutor(max_workers=25) as executor:
    future_to_src = {executor.submit(fetch_single_feed, src): src for src in SOURCES}
    for future in as_completed(future_to_src):
        res = future.result()
        if res:
            feed_context += res

if len(feed_context) > 40000:
    feed_context = feed_context[:40000] + "\n... [Quellenkontext zur Token-Schonung leicht gekürzt]"

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
      "headline": "Kurze Überschrift",
      "actors": ["USA", "China"],
      "category": "Handelskrieg / Technologie",
      "confidence_score": 0.92,
      "severity": 85,
      "sources_count": 12
    }
  ],
  "impact_chains": [
    {
      "trigger": "Auslösendes Ereignis",
      "steps": [
        "Erstfolge",
        "Zweitfolge",
        "Drittfolge"
      ],
      "primary_beneficiaries": ["WTI Öl", "Gold"],
      "primary_detractors": ["Airlines", "Chemie"]
    }
  ],
  "probability_matrix": [
    { "scenario": "Szenario 1", "probability_pct": 68, "trend": "RISING" }
  ],
  "daily_executive_summary": "Kurze, prägnante Synthese der geopolitischen Lage (max. 3-4 Sätze).",
  "global_risk_score": 78,
  "market_regime": "Marktregime",
  "top_overweight": "Gewinner-Assets",
  "top_risk": "Hauptrisiko",
  "defcon_status": {"level": 3, "label": "DEFCON 3 - Erhöhte Wachsamkeit", "nuclear_risk_percent": 18, "primary_driver": "Treiber"},
  "narrative_divergence": [
    {"topic": "Schauplatz 1", "mainstream_view": "Mainstream Sichten", "brics_view": "BRICS Sicht", "alternative_view": "Alternative Sicht"}
  ],
  "domestic_politics": [
    {"country_region": "Region 1", "topic": "Thema", "status": "Status", "impact": "Impact"}
  ],
  "stock_picks": {
    "top_5_buys": [{"ticker": "T1", "name": "N1", "sector": "S1", "reason": "Kurze Begründung"}],
    "flop_5_sells": [{"ticker": "S1", "name": "N1", "sector": "S1", "reason": "Kurze Begründung"}]
  },
  "conflict_hotspots": [
    {"region": "R1", "actors": "A1", "escalation_level": "KRITISCH", "catalyst": "C1", "impact": "I1", "lat": 31.5, "lng": 34.75}
  ],
  "systemic_risks": [
    {"topic": "T1", "category": "C1", "risk_level": "HOCH", "status": "S1", "impact": "I1"}
  ],
  "assets": [
    {"name": "Gold & Silber", "signal": "GREEN", "signal_text": "🟢 Attraktiv", "trend": "T", "driver": "D"}
  ],
  "scenarios": [
    {"title": "S1", "prob": 40}
  ]
}
"""

raw_text = None
generator_used = "Claude"

anth_key = os.environ.get("ANTHROPIC_API_KEY")
if not anth_key:
    raise ValueError("ANTHROPIC_API_KEY wurde nicht in den Umgebungsvariablen gefunden!")

client_anthropic = anthropic.Anthropic(api_key=anth_key)

system_instruction = (
    "Du bist der Chef-Analyst und OSINT-Spezialist eines hochmodernen Geopolitik-Lagezentrums ('Argus Grid'). "
    "DEINE AUFGABE: Berechne den synthetischen GeoScore (0-100), erstelle aus den Rohnachrichten einen deduplizierten Event-Graphen, berechne mehrstufige Kausalitätsketten (Impact Chains) und gewichte alle Erkenntnisse anhand der Quellenprioritäten. "
    "Analysiere dabei die Eingaben aus ALLEN Domänen: Satelliten-Hitzedaten (NASA FIRMS), Cyber-Attacken (CISA, CERT-EU), Seekabel/Energienetze, Schifffahrt/UKMTO, Luftraum-Sperrungen (NOTAMs, GPS-Jamming) und Seismik. "
    "WICHTIGSTE FORM-VORGABE: HALTE DICH IN ALLEN TEXTFELDERN UND BEGRÜNDUNGEN EXTREM PRÄGNANT UND KURZ (max. 1-2 Sätze pro Feld). Das JSON darf keinesfalls mitten im Satz abgeschnitten werden! "
    "Antworte AUSSCHLIESSLICH im rein validen JSON-Format basierend auf diesem Schema:\n" + json_template_desc
)

# ANTHROPIC MODELL-IDs
claude_models = [
    "claude-sonnet-4-6",
    "claude-3-7-sonnet-20250219",
    "claude-3-5-sonnet-20241022"
]

for model_name in claude_models:
    try:
        print(f"Generiere Argus Grid Lagebild mit Anthropic {model_name}...")
        response = client_anthropic.messages.create(
            model=model_name,
            max_tokens=8192,
            system=system_instruction,
            messages=[{"role": "user", "content": f"Live-Rohstoffe & Marktdaten:\n{live_market_context}\n\nGewichteter Multi-Domänen OSINT-Kontext:\n{feed_context}"}]
        )
        raw_text = response.content[0].text.strip()
        generator_used = f"Anthropic ({model_name})"
        break
    except Exception as e:
        print(f"Hinweis: {model_name} nicht erreichbar oder abgelehnt: {e}")

if not raw_text:
    raise RuntimeError("Fehler: Anthropic konnte keine Antwort generieren. Bitte Key & Modell-Berechtigungen prüfen.")

# Sicheres Parsen & Reparieren des JSON
data = repair_and_parse_json(raw_text)

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

print(f"Argus Grid Lagezentrum erfolgreich mit 90+ Multi-Domänen Feeds ({generator_used}) aktualisiert!")
