import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime

print("1. Hole tagesaktuelle Marktdaten von öffentlichen Schnittstellen...")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def get_yahoo_quote(ticker):
    """Holt tagesaktuelle Kurse über die öffentliche Yahoo Finance Query API"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            result = data['chart']['result'][0]
            prices = result['indicators']['quote'][0]['close']
            valid_prices = [p for p in prices if p is not None]
            if len(valid_prices) >= 2:
                current = valid_prices[-1]
                prev = valid_prices[-2]
                change_pct = ((current - prev) / prev) * 100
                return current, change_pct
    except Exception as e:
        print(f"Hinweis: Konnte {ticker} nicht laden ({e}). Nutze Fallback.")
    return None, 0.0

# Abruf der wichtigsten Finanz-Indikatoren
gold_price, gold_pct = get_yahoo_quote("GC=F")       # Gold
oil_price, oil_pct = get_yahoo_quote("CL=F")         # WTI Rohöl
vix_index, vix_pct = get_yahoo_quote("^VIX")         # Volatilität
sp500, sp500_pct = get_yahoo_quote("^GSPC")          # S&P 500
us10y, us10y_pct = get_yahoo_quote("^TNX")           # US 10Y Yield

print("2. Hole Finanz- & Geopolitik-Schlagzeilen aus RSS-Feed...")

news_titles = []
try:
    rss_url = "https://news.google.com/rss/search?q=geopolitics+macroeconomics+markets&hl=en-US&gl=US&ceid=US:en"
    res = requests.get(rss_url, headers=headers, timeout=10)
    if res.status_code == 200:
        root = ET.fromstring(res.content)
        for item in root.findall('.//item')[:5]:
            title = item.find('title').text
            if title:
                news_titles.append(title)
except Exception as e:
    print(f"RSS Feed Fehler ({e})")

print("3. Berechne Scores & Ampeln...")

base_risk = 50
if vix_index:
    if vix_index > 25: base_risk += 15
    elif vix_index > 20: base_risk += 8
    elif vix_index < 14: base_risk -= 5

if us10y and us10y > 4.2:
    base_risk += 10

if oil_price and oil_price > 85:
    base_risk += 8

risk_score = min(max(base_risk, 10), 95)

if us10y and us10y > 4.0 and oil_pct > 0:
    regime = "Stagflations-Druck"
elif sp500_pct > 0 and vix_index and vix_index < 16:
    regime = "Goldilocks / Risk-On"
else:
    regime = "Makro-Konsolidierung"

output_data = {
    "timestamp": datetime.utcnow().strftime("%d. %B %Y - %H:%M UTC"),
    "global_risk_score": risk_score,
    "market_regime": regime,
    "top_overweight": "Gold, Uran & Chips",
    "top_risk": "Refinanzierung / US-Zinsen" if (us10y and us10y > 4.0) else "Geopolitische Spannungen",
    "daily_executive_summary": f"Der globale Risiko-Index steht bei {risk_score}/100. US 10-Year Rendite liegt bei {us10y:.2f}% ({us10y_pct:+.1f}%), Gold verändert sich um {gold_pct:+.1f}% und WTI Öl um {oil_pct:+.1f}%. Wichtigste Themen im Fokus: {', '.join(news_titles[:2]) if news_titles else 'Lieferketten-Resilienz und Notenbankpolitik'}.",
    "assets": [
        { "name": "Gold & Silber", "signal": "GREEN", "signal_text": "🟢 Sehr Attraktiv", "trend": f"{'Stark Steigend' if gold_pct > 0 else 'Konsolidierung'}", "driver": f"Kassakurs: ${gold_price:.1f} ({gold_pct:+.1f}%) | Zentralbankkäufe" if gold_price else "Dedollarisierung & Safe Haven Demand" },
        { "name": "KI & Halbleiter", "signal": "GREEN", "signal_text": "🟢 Attraktiv", "trend": "Steigend", "driver": "Hohe Investitionen in Hardware-Infrastruktur" },
        { "name": "Uran & Energie", "signal": "GREEN", "signal_text": "🟢 Attraktiv", "trend": "Stark Steigend", "driver": f"Ölpreis: ${oil_price:.1f} ({oil_pct:+.1f}%) | Angebotsdefizit" if oil_price else "Strukturelles Marktdefizit" },
        { "name": "S&P 500 / Nasdaq", "signal": "AMBER", "signal_text": "🟡 Neutral", "trend": f"{'Leicht Steigend' if sp500_pct > 0 else 'Leicht Fallend'}", "driver": f"S&P 500: {sp500:.0f} ({sp500_pct:+.1f}%) | Zins-Sensitivität" if sp500 else "Bewertungen vs. Unternehmensgewinne" },
        { "name": "Bitcoin & Krypto", "signal": "AMBER", "signal_text": "🟡 Neutral", "trend": "Volatil", "driver": "M2-Geldmengen-Korrelation & ETF-Zuflüsse" },
        { "name": "High-Yield Bonds", "signal": "RED", "signal_text": "🔴 Unattraktiv", "trend": "Fallend", "driver": f"VIX: {vix_index:.1f} | Refinanzierungsdruck bei Unternehmen" if vix_index else "Zinslast & Kreditausfallrisiken" },
        { "name": "Gewerbeimmobilien", "signal": "RED", "signal_text": "🔴 Meiden", "trend": "Stark Fallend", "driver": "Hohes Zinsniveau & Leerstände im Sektor Office" }
    ],
    "regions": [
        { "name": "USA", "signal": "GREEN", "signal_text": "🟢 Grün", "summary": "Starke Tech-Dominanz und Energieunabhängigkeit stützen den Binnenmarkt." },
        { "name": "Japan & Indien", "signal": "GREEN", "signal_text": "🟢 Grün", "summary": "Hauptprofiteure von Supply-Chain-Verlagerungen und Corporate-Governance-Reformen." },
        { "name": "ASEAN", "signal": "GREEN", "signal_text": "🟢 Grün", "summary": "Hoher Kapitalzufluss durch Friendshoring (Vietnam, Malaysia, Indonesien)." },
        { "name": "Kern-Europa (DE/FR)", "signal": "RED", "signal_text": "🔴 Rot", "summary": "Strukturelle Belastung durch hohe Energiekosten und schwache Industrie." },
        { "name": "China (Binnenmarkt)", "signal": "RED", "signal_text": "🔴 Rot", "summary": "Anhaltender FDI-Abfluss, Immobilienkrise und schwacher Binnenkonsum." }
    ],
    "scenarios": [
        { "title": "Zweite Inflationswelle (Stagflation)", "prob": 35 },
        { "title": "KI-Produktivitätsboom (Goldilocks)", "prob": 30 },
        { "title": "Kreditklemme & Tiefenrezession", "prob": 20 },
        { "title": "Eskalation Taiwan-Konflikt", "prob": 15 }
    ]
}

print("4. Speichere Ergebnisse in data.json...")
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

print("ERFOLG: data.json sauber generiert!")
