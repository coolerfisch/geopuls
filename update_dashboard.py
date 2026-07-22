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

# 1. Ausbalancierter Quellenspiegel (Mainstream + Unabhängig global)
rss_urls = {
    # --- USA & AMERIKA ---
    "CNBC (US Mainstream Finance)": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "Foreign Policy (US Establishment)": "https://foreignpolicy.com/feed/",
    "ZeroHedge (US Alternative Macro)": "http://feeds.feedburner.com/zerohedge/feed",
    "UnHerd (US/UK Indep. Analysis)": "https://unherd.com/feed/",
    "Antiwar.com (US Indep. Foreign Policy)": "https://news.antiwar.com/feed/",

    # --- BRICS, NAHOST & GLOBALER SÜDEN ---
    "Economic Times (Indien Mainstream)": "https://economictimes.indiatimes.com/rssfeedstopstories.cms",
    "CGTN World (China Staatl./Mainstream)": "https://news.cgtn.com/rss/World.xml",
    "Al Jazeera (Nahost Mainstream)": "https://www.aljazeera.com/xml/rss/all.xml",
    "The Cradle (Nahost Indep. Geopolitik)": "https://thecradle.co/feed",
    "Geopolitical Economy Report (Indep. BRICS)": "https://geopoliticaleconomy.com/feed/",
    "TASS World (Russland Perspektive)": "https://tass.com/rss/v2.xml",

    # --- ASIEN & INDOPAZIFIK ---
    "Nikkei Asia (Japan Mainstream Tech/Eco)": "https://asia.nikkei.com/rss/feed/nar",
    "SCMP (China/Hongkong Regional)": "https://www.scmp.com/rss/91/feed",
    "Asia Times (Indep. Asien Geopolitik)": "https://asiatimes.com/feed/",

    # --- EU & DACH MAINSTREAM & FINANZEN ---
    "Handelsblatt (Finanzen)": "https://www.handelsblatt.com/contentexport/feed/finanzen",
    "Finanzmarktwelt (FMW)": "https://finanzmarktwelt.de/feed/",
    "stock3 (Godmode)": "https://stock3.com/news/feed/",
    "Manager Magazin": "https://www.manager-magazin.de/rss",
    "NZZ (International)": "https://www.nzz.ch/international.rss",
    "FAZ (Ausland)": "https://www.faz.net/rss/aktuell/politik/ausland/",
    "Tagesschau (Ausland)": "https://www.tagesschau.de/ausland/index.xml",
    "BBC World News": "http://feeds.bbci.co.uk/news/world/rss.xml",

    # --- EU & DACH UNABHÄNGIG & ALTERNATIV ---
    "NachDenkSeiten": "https://www.nachdenkseiten.de/?feed=rss2",
    "Apolut": "https://apolut.net/feed/",
    "Achgut": "https://www.achgut.com/rss",
    "Apollo News": "https://apollo-news.net/feed/",
    "Anti-Spiegel": "https://anti-spiegel.ru/feed/",
    "Telepolis": "https://www.telepolis.de/index.rss",
    "Tichys Einblick": "https://www.tichyseinblick.de/feed/",
    "Overton Magazin": "https://overton-magazin.de/feed/"
}

browser_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
feed_context = ""

print("Hole tagesaktuelle News aus 30 ausbalancierten globalen Quellen...")
for source_name, url in rss_urls.items():
    try:
        feed = feedparser.parse(url, agent=browser_agent)
        feed_context += f"\n--- Aktuelle Meldungen von {source_name} ---\n"
        for entry in feed.entries[:2]:  # Top 2 Artikel pro Quelle
            title = entry.get('title', '')
            raw_summary = entry.get('summary', '') or entry.get('description', '')
            summary = clean_html(raw_summary)
            feed_context += f"- Titel: {title}\n  Zusammenfassung: {summary[:220]}...\n"
    except Exception as e:
        print(f"Fehler bei {source_name}: {e}")

# 2. Groq Client initialisieren
api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY nicht in den Umgebungsvariablen gefunden!")

client = Groq(api_key=api_key)

# 3. Prompt für globale Synthese
prompt = f"""
Du bist der Chef-Analyst des GeoPuls Dashboards.
Erstelle eine tagesaktuelle, globale Synthese aus Finanzmärkten, Geopolitik sowie systemischen Zukunftrisiken.

Verarbeite und synthetisiere dabei die Perspektiven sowohl aus etablierten Mainstream-Medien als auch aus unabhängigen/alternativen Analysen aus den USA, Asien, den BRICS-Staaten und Europa:

{feed_context}

GIB DAS ERGEBNIS AUSSCHLIESSLICH ALS VALIDES JSON ZURÜCK.

Regeln für Felder:
1. "conflict_hotspots": Akute globale Brandherde (mind. 4 Einträge; z. B. Naher Osten, Ukraine/NATO, Taiwan/Indopazifik, Rotes Meer).
2. "systemic_risks": Latente Risiken & Strukturkrisen (mind. 3 Einträge; z. B. EU-Chatkontrolle, CBDCs/Digitaler Euro, Moldawien/Balkan, BRICS-Dedollarisierung).

Exaktes Schema:
{{
  "conflict_hotspots": [
    {{
      "region": "Naher Osten / Iran & Israel",
      "actors": "USA / Israel vs. Iran / Achse des Widerstands",
      "escalation_level": "KRITISCH",
      "catalyst": "Militärische Ereignisse und Zündeleien an Seewegen",
      "impact": "Folgen für Brent-Öl, Tanker-Routen und Märkte"
    }}
  ],
  "systemic_risks": [
    {{
      "topic": "EU-Chatkontrolle & Verschlüsselungsverbot",
      "category": "Digitale Freiheit & Datenschutz",
      "risk_level": "HOCH",
      "status": "Gesetzgebungsverfahren in Brüssel",
      "impact": "Aufweichung der Ende-zu-Ende-Verschlüsselung, Risiken für Bürgerrechte."
    }}
  ],
  "timestamp": "",
  "global_risk_score": 79,
  "market_regime": "Multipolare Stagflation & Zins-Unsicherheit",
  "top_overweight": "Gold, Energie, Rohstoffe & Verteidigung",
  "top_risk": "Versorgungsschock / Geopolitische Blockbildung",
  "daily_executive_summary": "Synthese aus Mainstream- und alternativen Berichten weltweit.",
  "assets": [
    {{ "name": "Gold & Silber", "signal": "GREEN", "signal_text": "🟢 Sehr Attraktiv", "trend": "Stark Steigend", "driver": "BRICS-Käufe, Geopolitik & Sichere Häfen" }},
    {{ "name": "KI & Halbleiter", "signal": "GREEN", "signal_text": "🟢 Attraktiv", "trend": "Steigend", "driver": "Asien-HardwareBoom & Tech-Rüstung" }},
    {{ "name": "Uran & Energie", "signal": "GREEN", "signal_text": "🟢 Attraktiv", "trend": "Stark Steigend", "driver": "Angebotsdefizit & Versorgungsängste" }},
    {{ "name": "S&P 500 / Nasdaq", "signal": "AMBER", "signal_text": "🟡 Neutral", "trend": "Volatil", "driver": "US-Bewertung vs. Fed-Zinsaussichten" }},
    {{ "name": "Bitcoin & Krypto", "signal": "AMBER", "signal_text": "🟡 Neutral", "trend": "Volatil", "driver": "Globales Liquiditätsumfeld" }},
    {{ "name": "High-Yield Bonds", "signal": "RED", "signal_text": "🔴 Unattraktiv", "trend": "Fallend", "driver": "Ausfallrisiken & Refinanzierungsdruck" }},
    {{ "name": "Gewerbeimmobilien", "signal": "RED", "signal_text": "🔴 Meiden", "trend": "Stark Fallend", "driver": "Hohes Zinsniveau & Leerstände" }}
  ],
  "regions": [
    {{ "name": "USA", "signal": "GREEN", "signal_text": "🟢 Grün", "summary": "Militärische & Kapitalmarkt-Dominanz, aber Rekordverschuldung." }},
    {{ "name": "BRICS & Globaler Süden", "signal": "GREEN", "signal_text": "🟢 Grün", "summary": "Ausbau alternativer Handelsnetze & Rohstoffkontrolle." }},
    {{ "name": "Japan & Indien / ASEAN", "signal": "GREEN", "signal_text": "🟢 Grün", "summary": "Profiteure der globalen Lieferketten-Umlenkung." }},
    {{ "name": "Kern-Europa (DE/FR)", "signal": "RED", "signal_text": "🔴 Rot", "summary": "Deindustrialisierung, hohe Energiekosten & Standortschwäche." }},
    {{ "name": "China (Binnenmarkt)", "signal": "RED", "signal_text": "🔴 Rot", "summary": "Immobilienkrise, Handelskonflikte & Deflationsdruck." }}
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
        {"role": "system", "content": "Du bist ein präzises Makro-, Finanz- und Geopolitik-Analysesystem, das ausschließlich valides JSON generiert."},
        {"role": "user", "content": prompt}
    ],
    model="llama-3.3-70b-versatile",
    response_format={"type": "json_object"}
)

data = json.loads(chat_completion.choices[0].message.content)

# Fallbacks
if "conflict_hotspots" not in data or not data["conflict_hotspots"]:
    data["conflict_hotspots"] = [
        {"region": "Naher Osten / Iran & Israel", "actors": "USA / Israel vs. Iran / Achse", "escalation_level": "KRITISCH", "catalyst": "Spannungen am Persischen Golf", "impact": "Ölpreis & Seewege"},
        {"region": "Ukraine / NATO-Ostflanke", "actors": "Russland vs. Ukraine / NATO", "escalation_level": "HOCH", "catalyst": "Frontverlauf & Waffenlieferungen", "impact": "Energie- & Agrarmärkte"},
        {"region": "Rotes Meer / Bab al-Mandab", "actors": "Houthi vs. Marine-Allianz", "escalation_level": "HOCH", "catalyst": "Schiffsangriffe", "impact": "Frachtraten & Supply Chain"},
        {"region": "Taiwan-Straße / Indopazifik", "actors": "China vs. Taiwan / USA", "escalation_level": "MITTEL-HOCH", "catalyst": "Militärmanöver", "impact": "Halbleiter-Sektor"}
    ]

if "systemic_risks" not in data or not data["systemic_risks"]:
    data["systemic_risks"] = [
        {"topic": "EU-Chatkontrolle & Verschlüsselungsverbot", "category": "Digitale Freiheit", "risk_level": "HOCH", "status": "Gesetzgebung EU", "impact": "Risiken für Ende-zu-Ende Verschlüsselung."},
        {"topic": "BRICS-Dedollarisierung & Bilateraler Handel", "category": "Geomonetäre Ordnung", "risk_level": "MITTEL-HOCH", "status": "Umstellung Handelsnetze", "impact": "Schleichender Bedeutungsverlust des US-Dollars."},
        {"topic": "CBDC / Digitaler Euro & Bargeld-Limits", "category": "Monetäre Kontrolle", "risk_level": "MITTEL-HOCH", "status": "Vorbereitung EZB", "impact": "Programmierbares Geld & Entzug finanzieller Privatsphäre."}
    ]

data["timestamp"] = datetime.utcnow().strftime("%d.%m.%Y - %H:%M UTC")

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("GeoPuls data.json mit 30 ausbalancierten weltweiten Quellen erfolgreich aktualisiert!")
