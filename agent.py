#!/usr/bin/env python3
"""
ANA First Class Award Availability Agent

Scrapes seats.aero/anaf for ANA First Class award availability,
compares with previous results, and sends a macOS notification
when new seats appear.
"""

import json
import os
import subprocess
import sys
from datetime import datetime

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LAST_RESULTS_PATH = os.path.join(SCRIPT_DIR, "last_results.json")
URL = "https://seats.aero/anaf"


def scrape_anaf():
    """Scrape the ANA First Class finder page and return flight data."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        # Wait for Cloudflare challenge to resolve and content to render
        page.wait_for_timeout(20000)
        content = page.content()
        browser.close()

    soup = BeautifulSoup(content, "html.parser")
    table = soup.find("table")

    if not table:
        print("ERROR: Could not find the results table on the page.")
        print("The site may have changed or Cloudflare blocked the request.")
        sys.exit(1)

    rows = table.find_all("tr")
    flights = []

    for row in rows[1:]:  # Skip header row
        cells = row.find_all("td")
        if len(cells) < 7:
            continue

        values = [c.get_text(strip=True) for c in cells]
        flight = {
            "date": values[0],
            "last_seen": values[1],
            "source": values[2],
            "origin": values[3],
            "destination": values[4],
            "business": values[5],
            "first": values[6],
        }

        # Only include rows where First Class is available
        if flight["first"] and "not available" not in flight["first"].lower():
            flights.append(flight)

    return flights


def load_previous_results():
    """Load previous results from disk."""
    if not os.path.exists(LAST_RESULTS_PATH):
        return []
    with open(LAST_RESULTS_PATH, "r") as f:
        return json.load(f)


def save_results(flights):
    """Save current results to disk."""
    with open(LAST_RESULTS_PATH, "w") as f:
        json.dump(flights, f, indent=2)


def make_key(flight):
    """Create a unique key for a flight to detect duplicates."""
    return f"{flight['date']}|{flight['source']}|{flight['origin']}|{flight['destination']}"


def find_new_flights(current, previous):
    """Find flights in current that weren't in previous."""
    prev_keys = {make_key(f) for f in previous}
    return [f for f in current if make_key(f) not in prev_keys]


def send_mac_notification(title, message):
    """Send a macOS notification using osascript."""
    escaped_message = message.replace('"', '\\"')
    escaped_title = title.replace('"', '\\"')
    subprocess.run(
        [
            "osascript",
            "-e",
            f'display notification "{escaped_message}" with title "{escaped_title}"',
        ],
        check=False,
    )


def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 60)
    print("  ANA First Class Award Availability Agent")
    print(f"  {now}")
    print("=" * 60)
    print()

    # Step 1: Scrape
    print("[1/3] Scraping seats.aero/anaf ...")
    current_flights = scrape_anaf()
    print(f"      Found {len(current_flights)} available First Class seat(s).")

    if not current_flights:
        print("\nNo ANA First Class availability found right now.")
        save_results([])
        return

    # Step 2: Compare with previous
    print("[2/3] Comparing with previous results ...")
    previous_flights = load_previous_results()
    new_flights = find_new_flights(current_flights, previous_flights)
    print(f"      {len(new_flights)} NEW seat(s) since last check.")

    # Step 3: Display and notify
    print("[3/3] Results:")
    print()

    if new_flights:
        print("-" * 60)
        print(f"  NEW ANA FIRST CLASS SEATS ({len(new_flights)})")
        print("-" * 60)
        for f in new_flights:
            print(f"  {f['date']}  {f['origin']} -> {f['destination']}  "
                  f"via {f['source']}  {f['first']}")
        print()

        # macOS notification
        routes = ", ".join(
            f"{f['origin']}->{f['destination']} {f['date']}" for f in new_flights
        )
        send_mac_notification(
            f"{len(new_flights)} New ANA F Seat(s)!",
            routes[:200],
        )
    else:
        print("  No new seats since last check.")

    # Show all current availability
    print()
    print("-" * 60)
    print(f"  ALL CURRENT AVAILABILITY ({len(current_flights)})")
    print("-" * 60)
    print(f"  {'Date':<12} {'Route':<12} {'Source':<12} {'First'}")
    print(f"  {'-'*11}  {'-'*11}  {'-'*11}  {'-'*15}")
    for f in current_flights:
        route = f"{f['origin']}->{f['destination']}"
        print(f"  {f['date']:<12} {route:<12} {f['source']:<12} {f['first']}")

    print()

    # Save for next comparison
    save_results(current_flights)
    print(f"Results saved. Next run will compare against these {len(current_flights)} seat(s).")


if __name__ == "__main__":
    main()
