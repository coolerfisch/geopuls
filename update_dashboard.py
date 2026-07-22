import os
import json
import re
from datetime import datetime
from groq import Groq
import feedparser

# HTML-Tags entfernen
def clean_html(raw_html):
    if not raw_html:
        return ""
    clean_text = re.sub(r'<[^>]+>', '', raw_html)
    return clean_text.strip()

# 1. Quellenspiegel (35+ globale Feeds)
rss_urls = {
    # 🌍 1. BRICS & GLOBALER SÜDEN
    "Economic Times (Indien & BRICS)": "https://economictimes.indiatimes.com/rssfeedstopstories.cms",
    "CGTN World (China Staatl.)": "https://news.cgtn.com/rss/World.xml",
    "Xinhua World (China Staatl.)": "http://www.xinhuanet.com/english/rss/worldrss.xml",
    "TASS World (Russland Staatl.)": "https://tass.com/rss/v2.xml",
    "Al Jazeera (Global South)": "https://www.aljazeera.com/xml/rss/all.xml",
    "The Cradle (Nahost Geopolitik)": "https://thecradle.co/feed",
    "Geopolitical Economy Report": "https://geopoliticaleconomy.com/feed/",
    "South China Morning Post (SCMP)": "https://www.scmp.com/rss/91/feed",
    "Asia Times (Indopazifik)": "https://asiatimes.com/feed/",

    # 🏛️ 2. WESTLICHE PRIMÄRQUELLEN & DIPLOMATIE
    "White House (US-Präsident)": "https://www.whitehouse.gov/briefing-room/feed/",
    "US Department of State": "https://www.state.gov/rss-feed/press-releases/feed/",
    "Federal Reserve (US Fed)": "https://www.federalreserve.gov/feeds/press_all.xml",
    "EU-Kommission (Press Corner)": "https://ec.europa.eu/commission/presscorner/api/rss",
    "Europäischer Rat (Consilium)": "https://www.consilium.europa.eu/en/rss/",
    "World Economic Forum (WEF)": "https://www.weforum.org/agenda/feed/",
    "Schweizer Bundesrat (Admin.ch)": "https://www.admin.ch/gov/de/start/dokumentation/medienmitteilungen.rss.html",
    "Münchner Sicherheitskonferenz (MSC)": "https://securityconference.org/news/rss/",

    # 📈 3. WESTLICHER MAINSTREAM & FINANZEN
    "CNBC (US Finance)": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "Foreign Policy (US Geopolitik)": "https://foreignpolicy.com/feed/",
    "Nikkei Asia (Japan/Tech)": "https://asia.nikkei.com/rss/feed/nar",
    "Handelsblatt (DE Finanzen)": "https://www.handelsblatt.com/contentexport/feed/finanzen",
    "Finanzmarktwelt (FMW)": "https://finanzmarktwelt.de/feed/",
    "NZZ (International)": "https://www.nzz.ch/international.rss",
    "FAZ (Ausland)": "https://www.faz.net/rss/aktuell/politik/ausland/",
    "Tagesschau (Ausland)": "https://www.tagesschau.de/ausland/index.xml",
    "BBC World News": "http://feeds.bbci.co.uk/news/world/rss.xml",

    # 🔓 4. UNABHÄNGIGE & ALTERNATIVE ANALYSTEN
    "ZeroHedge": "http://feeds.feedburner.com/zerohedge/feed",
    "UnHerd": "https://unherd.com/feed/",
    "Antiwar.com": "https://news.antiwar.com/feed/",
    "NachDenkSeiten": "https://www.nachdenkseiten.de/?feed=rss2",
    "Apolut": "https://apolut.net/feed/",
    "Anti-Spiegel": "https://anti-spiegel.ru/feed/",
    "Telepolis": "https://www.telepolis.de/index.rss",
    "Tichys Einblick": "https://www.tichyseinblick.de/feed/",
    "Overton Magazin": "https://overton-magazin.de/feed/"
}

browser_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
feed_context = ""

print("Hole tagesaktuelle News aus allen 4 Säulen...")
for source_name, url in rss_urls.items():
    try:
        feed = feedparser.parse(url, agent=browser_agent)
        feed_context += f"\n--- Aktuelle Publikationen von {source_name} ---\n"
        for entry in feed.entries[:2]:
            title = entry.get('title', '')
            raw_summary = entry.get('summary', '') or entry.get('description', '')
            summary = clean_html(raw_summary)
            feed_context += f"- Titel: {title}\n  Inhalt: {summary[:220]}...\n"
    except Exception as e:
        print(f"Fehler bei {source_name}: {e}")

# 2. Groq Client initialisieren
api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY nicht in den Umgebungsvariablen gefunden!")

client = Groq(api_key=api_key)

# 3. Prompt mit DEFCON- / Weltkriegs-Bewertung
prompt = f"""
Du bist der Chef-Strategist und OSINT-Analyst des GeoPuls Frühwarn-Dashboards.

DEIN AUFTRAG:
Analysiere die Feeds aus BRICS, Regierungs-Primärquellen, Mainstream und alternativen Medien.

SCHLÜSSEL-AUFGABE: DEFCON & WELTKRIEGS-RISIKO BEWERTE
Analysiere das direkte Risiko eines Dritten Weltkriegs bzw. eines nuklearen Schlagabtauschs zwischen Supermächten (USA/NATO vs. Russland/China/Iran).
Bewerte die Lage auf einer Skala von DEFCON 5 (Sicher) bis DEFCON 1 (Nuklearer Schlagabtausch unmittelbar).
Setze das Feld "defcon_status":
- level: Ganzzahl (1 bis 5)
- label: String (z. B. "DEFCON 3 - Erhöhte Alarmstufe")
- nuclear_risk_percent: Geschätzte prozentuale Wahrscheinlichkeit einer direkten Nukleareskalation (z. B. 12)
- primary_driver: Kurze Begründung (Doktrinänderungen, ICBM-Tests, Manöver, Drohungen)

STRIKTE REGEL FÜR 'conflict_hotspots' (MINDESTENS 4 EINTRÄGE):
1. Naher Osten / Iran & Israel
2. Ukraine / NATO-Ostflanke
3. Taiwan-Straße / Indopazifik
4. Rotes Meer / Bab al-Mandab

STRIKTE REGEL FÜR 'systemic_risks' (3 PFLICHT-KATEGORIEN):
1. Territoriales/Diplomatisches Pulverfass (z.B. Moldawien & Transnistrien, Westbalkan, Kaukasus).
2. Rechtlich-Systemische Kontrolle (z.B. EU-Chatkontrolle, CBDC, Bargeldgrenzen).
3. Asymmetrischer Strategischer Hebel (z.B. Seltene Erden Monopole, Schattenflotten, Seekabel).

Meldungen der Quellen:
{feed_context}

GIB DAS ERGEBNIS AUSSCHLIESSLICH ALS VALIDES JSON ZURÜCK.

Exaktes Schema:
{{
  "defcon_status": {{
    "level": 3,
    "label": "DEFCON 3 - Erhöhte Einsatzbereitschaft",
    "nuclear_risk_percent": 15,
    "primary_driver": "Nukleare Doktrin-Anpassungen, Manöver der Strategischen Bomber & Rhetorik"
  }},
  "conflict_hotspots": [
    {{
      "region": "Naher Osten / Iran & Israel",
      "actors": "USA / Israel vs. Iran / Achse des Widerstands",
      "escalation_level": "KRITISCH",
      "catalyst": "Aktuelle Vorfälle oder Schläge",
      "impact": "Brent-Öl und Seewege"
    }},
    {{
      "region": "Ukraine / NATO-Ostflanke",
      "actors": "Russland vs. Ukraine / NATO-Unterstützer",
      "escalation_level": "HOCH",
      "catalyst": "Frontverlauf und Rüstungsentscheidungen",
      "impact": "Energiemärkte und europäische Stabilität"
    }},
    {{
      "region": "Taiwan-Straße & Indopazifik",
      "actors": "China vs. Taiwan / USA & Japan",
      "escalation_level": "MITTEL-HOCH",
      "catalyst": "Militärmanöver und Sanktionen",
      "impact": "Halbleiter-Lieferketten"
    }},
    {{
      "region": "Rotes Meer / Bab al-Mandab",
      "actors": "Houthi vs. Marine-Allianz",
      "escalation_level": "HOCH",
      "catalyst": "Schiffsangriffe",
      "impact": "Frachtraten & Supply Chains"
    }}
  ],
  "systemic_risks": [
    {{
      "topic": "Moldawien & Transnistrien",
      "category": "Geopolitische Region",
      "risk_level": "HOCH",
      "status": "Diplomatische Spannungen & Hybride Einwirkung",
      "impact": "Gefahr einer zweiten Front im Schwarzmeerraum"
    }},
    {{
      "topic": "EU-Chatkontrolle & Verschlüsselungsverbot",
      "category": "Digitale Kontrolle",
      "risk_level": "HOCH",
      "status": "Gesetzgebungsverfahren in Brüssel",
      "impact": "Aufweichung der Ende-zu-Ende-Verschlüsselung"
    }},
    {{
      "topic": "Seltene Erden Monopol & Rohstoff-Hebel",
      "category": "Strategischer Hebel",
      "risk_level": "MITTEL-HOCH",
      "status": "Exportkontrollen & Rivalität",
      "impact": "Lieferengpässe bei High-Tech und Rüstung"
    }}
  ],
  "timestamp": "",
  "global_risk_score": 79,
  "market_regime": "Multipolare Stagflation & Zins-Unsicherheit",
  "top_overweight": "Gold, Energie, Rohstoffe & Verteidigung",
  "top_risk": "Versorgungsschock / Geopolitische Blockbildung",
  "daily_executive_summary": "Tagesaktuelle Synthese.",
  "assets": [
    {{ "name": "Gold & Silber", "signal": "GREEN", "signal_text": "🟢 Sehr Attraktiv", "trend": "Stark Steigend", "driver": "Haupttreiber" }},
    {{ "name": "KI & Halbleiter", "signal": "GREEN", "signal_text": "🟢 Attraktiv", "trend": "Steigend", "driver": "Haupttreiber" }},
    {{ "name": "Uran & Energie", "signal": "GREEN", "signal_text": "🟢 Attraktiv", "trend": "Stark Steigend", "driver": "Haupttreiber" }},
    {{ "name": "S&P 500 / Nasdaq", "signal": "AMBER", "signal_text": "🟡 Neutral", "trend": "Volatil", "driver": "Haupttreiber" }},
    {{ "name": "Bitcoin & Krypto", "signal": "AMBER", "signal_text": "🟡 Neutral", "trend": "Volatil", "driver": "Haupttreiber" }},
    {{ "name": "High-Yield Bonds", "signal": "RED", "signal_text": "🔴 Unattraktiv", "trend": "Fallend", "driver": "Haupttreiber" }},
    {{ "name": "Gewerbeimmobilien", "signal": "RED", "signal_text": "🔴 Meiden", "trend": "Stark Fallend", "driver": "Haupttreiber" }}
  ],
  "regions": [
    {{ "name": "USA", "signal": "GREEN", "signal_text": "🟢 Grün", "summary": "Einschätzung" }},
    {{ "name": "BRICS & Globaler Süden", "signal": "GREEN", "signal_text": "🟢 Grün", "summary": "Einschätzung" }},
    {{ "name": "Japan & Indien / ASEAN", "signal": "GREEN", "signal_text": "🟢 Grün", "summary": "Einschätzung" }},
    {{ "name": "Kern-Europa (DE/FR/CH)", "signal": "RED", "signal_text": "🔴 Rot", "summary": "Einschätzung" }},
    {{ "name": "China (Binnenmarkt)", "signal": "RED", "signal_text": "🔴 Rot", "summary": "Einschätzung" }}
  ],
  "scenarios": [
    {{ "title": "Ausweitung Nahost-Konflikt (Ölschock >100$)", "prob": 40 }},
    {{ "title": "Zweite Inflationswelle / Multipolare Stagflation", "prob": 30 }},
    {{ "title": "Direkte NATO-Eskalation / Militärischer Zwischenfall", "prob": 15 }},
    {{ "title": "BRICS-Handelswährung / Beschleunigte Dedollarisierung", "prob": 15 }}
  ]
}}
"""

print("Rufe Groq API auf...")
chat_completion = client.chat.completions.create(
    messages=[
        {"role": "system", "content": "Du bist ein hochpräzises OSINT-Geopolitikmodell. Du ermittelst sachlich den aktuellen DEFCON-Zustand und das nukleare/strategische Welt-Risiko."},
        {"role": "user", "content": prompt}
    ],
    model="llama-3.3-70b-versatile",
    response_format={"type": "json_object"}
)

data = json.loads(chat_completion.choices[0].message.content)

# Fallback für defcon_status
if "defcon_status" not in data:
    data["defcon_status"] = {
        "level": 3,
        "label": "DEFCON 3 - Erhöhte Wachsamkeit",
        "nuclear_risk_percent": 15,
        "primary_driver": "Spannungen zwischen Atom-Mächten & NATO-Ostflanke"
    }

data["timestamp"] = datetime.utcnow().strftime("%d.%m.%Y - %H:%M UTC")

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("GeoPuls data.json mit DEFCON-Status erfolgreich gespeichert!")
