import os
import json
from datetime import datetime
from groq import Groq

# Groq Client initialisieren
api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY nicht in den Umgebungsvariablen gefunden!")

client = Groq(api_key=api_key)

prompt = """
Du bist der Chef-Analyst des GeoPuls Dashboards.
Erstelle eine tagesaktuelle, institutionelle Synthese der weltweiten Finanz- und Geopolitik-Lage.

Gib das Ergebnis AUSSCHLIESSLICH als korrektes JSON zurück.

Exaktes Schema:
{
  "timestamp": "",
  "global_risk_score": 68,
  "market_regime": "Stagflations-Druck",
  "top_overweight": "Gold, Uran & Chips",
  "top_risk": "Refinanzierung / Debt Turms",
  "daily_executive_summary": "Prägnante Zusammenfassung der wichtigsten Entwicklungen der letzten 24h.",
  "assets": [
    { "name": "Gold & Silber", "signal": "GREEN", "signal_text": "🟢 Sehr Attraktiv", "trend": "Stark Steigend", "driver": "Zentralbankkäufe & Dedollarisierung" },
    { "name": "KI & Halbleiter", "signal": "GREEN", "signal_text": "🟢 Attraktiv", "trend": "Steigend", "driver": "Monetarisierung KI-Hardware" },
    { "name": "Uran & Energie", "signal": "GREEN", "signal_text": "🟢 Attraktiv", "trend": "Stark Steigend", "driver": "Angebotsdefizit vs. Reaktorboom" },
    { "name": "S&P 500 / Nasdaq", "signal": "AMBER", "signal_text": "🟡 Neutral", "trend": "Seitwärts", "driver": "Hohe KGV-Bewertung" },
    { "name": "Bitcoin & Krypto", "signal": "AMBER", "signal_text": "🟡 Neutral", "trend": "Volatil", "driver": "M2-Geldmengen-Korrelation" },
    { "name": "High-Yield Bonds", "signal": "RED", "signal_text": "🔴 Unattraktiv", "trend": "Fallend", "driver": "Refinanzierungsdruck" },
    { "name": "Gewerbeimmobilien", "signal": "RED", "signal_text": "🔴 Meiden", "trend": "Stark Fallend", "driver": "Leerstand & Zinsen" }
  ],
  "regions": [
    { "name": "USA", "signal": "GREEN", "signal_text": "🟢 Grün", "summary": "Tech-Dominanz, Resilienz, tiefe Kapitalmärkte." },
    { "name": "Japan & Indien", "signal": "GREEN", "signal_text": "🟢 Grün", "summary": "Profiteure von Supply-Chain-Shift & Reformen." },
    { "name": "ASEAN", "signal": "GREEN", "signal_text": "🟢 Grün", "summary": "Starker Kapitalzufluss durch Friendshoring." },
    { "name": "Kern-Europa (DE/FR)", "signal": "RED", "signal_text": "🔴 Rot", "summary": "Deindustrialisierung & hohe Energiekosten." },
    { "name": "China (Binnenmarkt)", "signal": "RED", "signal_text": "🔴 Rot", "summary": "FDI-Abfluss, Immobilienkrise, Deflationsdruck." }
  ],
  "scenarios": [
    { "title": "Zweite Inflationswelle (Stagflation)", "prob": 35 },
    { "title": "KI-Produktivitätsboom (Goldilocks)", "prob": 30 },
    { "title": "Kreditklemme & Tiefenrezession", "prob": 20 },
    { "title": "Eskalation Taiwan-Konflikt", "prob": 15 }
  ]
}
"""

print("Rufe Groq API mit Llama 3.3 70B auf...")
chat_completion = client.chat.completions.create(
    messages=[
        {"role": "system", "content": "Du bist ein präzises Makro-Analyse-System, das ausschließlich valides JSON generiert."},
        {"role": "user", "content": prompt}
    ],
    model="llama-3.3-70b-versatile",
    response_format={"type": "json_object"}
)

data = json.loads(chat_completion.choices[0].message.content)
data["timestamp"] = datetime.utcnow().strftime("%d.%m.%Y - %H:%M UTC")

# data.json speichern
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("GeoPuls data.json erfolgreich erstellt!")
