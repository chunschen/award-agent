# ANA First Class Award Availability Agent

A Python agent that monitors [seats.aero](https://seats.aero/anaf) for ANA First Class award seat availability. It detects new seats since the last check and sends a macOS notification when availability appears.

## How It Works

1. Opens `seats.aero/anaf` using a headless browser (Playwright)
2. Scrapes the availability table for First Class award seats
3. Compares results against the previous run to identify **new** seats only
4. Displays results in the terminal and sends a **macOS notification** for new availability

## Sample Output

```
============================================================
  ANA First Class Award Availability Agent
  2026-06-27 13:00:00
============================================================

[1/3] Scraping seats.aero/anaf ...
      Found 5 available First Class seat(s).
[2/3] Comparing with previous results ...
      2 NEW seat(s) since last check.
[3/3] Results:

------------------------------------------------------------
  NEW ANA FIRST CLASS SEATS (2)
------------------------------------------------------------
  2026-07-06  HNL -> NRT  via Aeroplan  90,000 pts
  2026-07-06  HNL -> NRT  via Velocity  100,000 pts
```

## Installation

### Prerequisites

- Python 3.9+
- macOS (for native notifications)

### Setup

```bash
git clone https://github.com/chunschen/award-agent.git
cd award-agent

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

### Run

```bash
source venv/bin/activate
python agent.py
```

The first run will report all current seats as new. Subsequent runs will only alert on newly appeared availability.

## Schedule It (Every 30 Minutes)

```bash
crontab -e
```

Add this line:

```
*/30 * * * * cd ~/Documents/award-agent && ./venv/bin/python agent.py >> agent.log 2>&1
```

Check past runs anytime with:

```bash
cat agent.log
```
