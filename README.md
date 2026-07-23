# 🌐 ARGUS GRID // Systemic Intelligence Engine (v3.0)

![Architecture](https://img.shields.io/badge/Architecture-Multi--LLM%20Ensemble-38bdf8?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Active%20OSINT%20Pipeline-22c55e?style=for-the-badge)
![Feeds](https://img.shields.io/badge/Feeds-140%2B%20Global%20Sources-a855f7?style=for-the-badge)
![ADS-B](https://img.shields.io/badge/Tracking-OpenSky%20Live%20ADS--B-eab308?style=for-the-badge)

**ARGUS GRID** ist eine hochgradig automatisierte, unvoreingenommene **Systemic Intelligence Engine**, die globale Geopolitik, Makroökonomie, Konfliktherde, Fluchtbewegungen und Militäroperationen in Echtzeit analysiert.

Das System kombiniert ein ausbalanciertes Netzwerk aus über 140 weltweiten Primärquellen mit Live-Finanzdaten, OpenSky ADS-B Flugtracking und einem orchestrierten **Multi-LLM-Komitee** (DeepSeek V4 Pro, Claude Sonnet 5, Gemini 3.6 Flash, Llama 3.3 70B via Groq).


## 📡 Abgedecktes Quellenspektrum & Data Ingestion

ARGUS GRID aggregiert über 140 weltweite RSS-Feeds in Echtzeit. Um eine unvoreingenommene Lagebeurteilung (No-Bias Policy) zu gewährleisten, ist der Quellenpool ausgewogen über Geografien, politische Ausrichtungen und Fachthemen verteilt:

| Kategorie | Enthaltene Akteure / Portale | Fokus & Nutzen |
| :--- | :--- | :--- |
| 🇺🇸 **USA Polit-Spektrum** | CNN, MSNBC, Fox News, WSJ, National Review, Reason | Gegenüberstellung von Left-Liberal, Conservative & Libertarian |
| 🇪🇺 **DACH & UK Presse** | taz, Der Spiegel, SZ, FAZ, Die Welt, NZZ, Handelsblatt, Guardian, Telegraph | Ausgewogene DACH/UK-Analysen (Progressiv, Konservativ, Business) |
| 🏛️ **Zentralbanken & Gov** | Fed, EZB, BoE, PBOC (China), BoJ, BIS, IMF, White House, EU-Kommission | Offizielle Geldpolitik, Makro-Daten & Regierungsentscheidungen |
| 🚶 **Migration & Humanitär** | UNHCR, IOM Displacement Matrix (DTM), ReliefWeb, Frontex | Frühwarnindikatoren für verdeckte Fluchtbewegungen & Krisen |
| 📊 **Energie & Logistik** | EIA, IEA, OPEC, Baker Hughes, AGSI+ Gas, Freightos, Baltic Dry | Rohstoff-Schocks, Frachtraten & physische Nadelöhre |
| 🛡️ **OSINT & Militär** | ISW, Oryx, Bellingcat, USNI, UKMTO, CISA Cyber, NASA FIRMS | Satellitenauswertung, Materialverluste, Cyber & EW-Alerts |
| 🌍 **BRICS & Diplomatisch** | Xinhua, Global Times, TASS, Kremlin, IRNA, SCMP, Al Jazeera | Erfassung der geopolitischen Perspektive von Nicht-NATO-Staaten |
| 🔍 **Investigativ & Konträr** | The Intercept, Scheerpost, UnHerd, Telepolis, ZeroHedge, Substack-Analysten | Falsifikations-Gegenmodelle & Erkennung alternativer Narrative |

> **Vollständige Transparenz:** Die exakte, tagesaktuelle Liste aller eingebundenen RSS-Endpoints befindet sich direkt im Quellcode unter [`update_dashboard.py`](./update_dashboard.py).

---

┌─────────────────────────────────────────────────────────────────────────────┐
│ 📡 INGESTION: 140+ RSS Feeds • yFinance Live-Märkte • OpenSky ADS-B        │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │  (Parallel Fetching via ThreadPool)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ ⚡ STUFE 1: Groq LPU (Llama 3.3 70B)                                        │
│    Extreme Datenkomprimierung & Entrauschung (~90.000 Zeichen ➔ ~3.000 W.)   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                 ┌─────────────────────┴─────────────────────┐
                 ▼                                           ▼
┌───────────────────────────────────┐     ┌───────────────────────────────────┐
│ ♟️ STUFE 2a: DeepSeek V4 Pro       │     │ 🌐 STUFE 2b: Gemini 3.6 Flash     │
│    Spieltheoretisches Gutachten   │     │    Makro-Schocks, Rohstoffe,      │
│    (6-Säulen-Konfliktanalyse)    │     │    Vertreibung & Souveränität     │
└─────────────────┬─────────────────┘     └─────────────────┬─────────────────┘
                  │                                         │
                  └────────────────────┬────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🧠 STUFE 3: Claude Sonnet 5 (Chef-Synthesizer)                              │
│    Validierung, Balancierung aller Narrative (Dem/GOP/BRICS) & JSON-Bau    │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
                        📄 data.json ➔ 🌐 Frontend (Leaflet.js)


---

## ♟️ Spieltheoretisches Gutachten (DeepSeek Engine)

Das Dashboard beinhaltet eine wissenschaftlich fundierte, spieltheoretische Deep-Dive-Analyse akuter Krisenherde, die über 6 methodische Säulen aufgebaut ist:

1. **Akteur-Granularität:** Zerlegung von Nationalstaaten in interne Fraktionen (Exekutive, Militärführung, Parteiflügel, Lobbies), um monolitische Fehlannahmen zu vermeiden.
2. **Zeithorizont-Konflikt:** Strikt getrennte Evaluierung von Kurzfrist-Anreizen (4–8 Wochen / Ein-Runden-Spiel) versus Langfrist-Anreizen (*Schatten der Zukunft*).
3. **Quantifizierte Payoff-Matrix:** Bipolare Nutzenbewertung auf einer Skala von **-3** *(existenzieller Verlust)* bis **+3** *(maximaler Gewinn)* mit visueller Balkendiagramm-Darstellung.
4. **Signaltheorie & Information:** Beseitigung von Informationsasymmetrien durch die Trennung von **Cheap Talk** *(Rhetorik, Bluffs)* und **Costly Signals** *(reale Kosten-Handlungen wie Truppenverlegungen oder Sanktionen)*.
5. **Gleichgewicht & Bindung:** Identifikation von **Nash-Gleichgewichten** und Offenlegung des **Commitment-Problems** (warum Parteien trotz gegenseitigen Schadens nicht deeskalieren können).
6. **Falsifikations-Gegenmodell:** Pflichtmäßige Konstruktion einer alternativen Lesart zur aktiven Vermeidung von Confirmation Bias.

---

## ⚡ Weitere Kernfunktionen & Features

* 🗺️ **Taktische Live-Radar-Karte:**
  * **Pulsierende Kriegszonen:** Automatische visuelle Hervorhebung aktiver Konflikt- und Fluchtherde.
  * **Animierte Fluchtkorridore:** Dynamische Vektoren zur Kartierung weltweiter Migration (UNHCR/IOM DTM).
  * **Live OpenSky ADS-B Tracking:** Echtzeit-Positionsdaten und Kursausrichtung aktiver Aufklärungs- und Militärmaschinen (FORTE, NATO AWACS, Strategic Airlift).
* 🏛️ **Innenpolitik & Regimestabilität:**
  * Erfassung von Wahlzyklen, Parteienkämpfen und Gesetzgebungsdruck in den USA, der EU, Großbritannien, den BRICS-Staaten, Nahost und Afrika.
* ⚖️ **No-Bias Quellenspektrum:**
  * Ausgewogene Gegenüberstellung von **Links/Progressiv**, **Konservativ/Rechts** und **Liberal/Mitte** bei allen Großmächten.
* 📈 **Dynamische Aktien-Rotation:**
  * Lageabhängige Sektor-Gewichtung (Shipping, Defense, Rohstoffe, Tech, Energie).

---

## 🔑 Required Environment Variables (GitHub Secrets)

| Secret Name | Beschreibung |
| :--- | :--- |
| `GROQ_API_KEY` | Fast Filtering & Summarization (Llama 3.3 70B) |
| `ANTHROPIC_API_KEY` | Final Synthesis & JSON Generation (Claude Sonnet 5) |
| `GEMINI_API_KEY` | Macro & Migration Intelligence (Gemini 3.6 Flash) |
| `DEEPSEEK_API_KEY` | Game Theory Deep Dive (DeepSeek V4 Pro) |
| `OPENSKY_USER` | *(Optional)* Account für höhere ADS-B Rate-Limits |
| `OPENSKY_PASSWORD` | *(Optional)* OpenSky Passwort |

---

## ⚙️ GitHub Actions Automation (`.github/workflows/update.yml`)

```yaml
name: Update Argus Grid Dashboard

on:
  schedule:
    - cron: '0 */4 * * *' # Alle 4 Stunden
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repo
        uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Dependencies
        run: |
          pip install requests feedparser yfinance anthropic groq openai

      - name: Run Dashboard Pipeline
        env:
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
          OPENSKY_USER: ${{ secrets.OPENSKY_USER }}
          OPENSKY_PASSWORD: ${{ secrets.OPENSKY_PASSWORD }}
        run: python update_dashboard.py

      - name: Commit and Push Data
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"
          git add data.json
          git commit -m "auto: Sync Argus Grid Live Intelligence Data [skip ci]" || exit 0
          git push
💻 Lokale Entwicklung & Start
Repository klonen:

Bash
git clone [https://github.com/coolerfisch/argus-grid.git](https://github.com/coolerfisch/argus-grid.git)
cd argus-grid
Pip-Pakete installieren:

Bash
pip install requests feedparser yfinance anthropic groq openai
Pipeline manuell ausführen:

Bash
python update_dashboard.py
Lokalen Webserver starten (um CORS-Restriktionen im Browser zu vermeiden):

Bash
python -m http.server 8000
Dashboard im Browser unter http://localhost:8000 öffnen.

⚠️ System- & Haftungsausschluss (Disclaimer)
Keine Finanz- oder Anlageberatung: Sämtliche auf ARGUS GRID dargestellten Inhalte, Aktien-Rotationen, Stress-Test-Szenarien und Kennzahlen dienen ausschließlich akademischen, strategischen und Forschungszwecken im Rahmen automatisierter OSINT-Analysen (Open Source Intelligence).

Automatisierte Verarbeitung: Die Auswertungen basieren auf Algorithmen und LLM-Synthesen. Es wird keine Haftung für die Richtigkeit, Vollständigkeit oder Aktualität der Primärdaten übernommen.
