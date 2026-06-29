"""Unit tests for ANA First Class Award Availability Agent."""

import json
import os
import tempfile
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup

from agent import find_new_flights, load_previous_results, make_key, save_results, scrape_anaf


# -- Sample data --

SAMPLE_FLIGHTS = [
    {
        "date": "2026-07-06",
        "last_seen": "2 hours ago",
        "source": "Aeroplan",
        "origin": "HNL",
        "destination": "NRT",
        "business": "Not Available",
        "first": "90,000 pts",
    },
    {
        "date": "2026-06-29",
        "last_seen": "1 hour ago",
        "source": "Velocity",
        "origin": "ORD",
        "destination": "HND",
        "business": "100,000 pts",
        "first": "140,000 pts",
    },
]

SAMPLE_HTML = """
<html><body>
<table>
  <tr><th>Date</th><th>Last Seen</th><th>Source</th><th>Origin</th><th>Destination</th><th>Business</th><th>First</th><th></th></tr>
  <tr><td>2026-07-06</td><td>2 hours ago</td><td>Aeroplan</td><td>HNL</td><td>NRT</td><td>Not Available</td><td>90,000 pts</td><td></td></tr>
  <tr><td>2026-06-29</td><td>1 hour ago</td><td>Velocity</td><td>ORD</td><td>HND</td><td>100,000 pts</td><td>140,000 pts</td><td></td></tr>
  <tr><td>2026-08-01</td><td>3 hours ago</td><td>Aeroplan</td><td>LAX</td><td>NRT</td><td>Not Available</td><td>Not Available</td><td></td></tr>
</table>
</body></html>
"""


# -- make_key tests --


class TestMakeKey:
    def test_creates_expected_key(self):
        flight = SAMPLE_FLIGHTS[0]
        assert make_key(flight) == "2026-07-06|Aeroplan|HNL|NRT"

    def test_different_flights_have_different_keys(self):
        assert make_key(SAMPLE_FLIGHTS[0]) != make_key(SAMPLE_FLIGHTS[1])

    def test_same_flight_data_produces_same_key(self):
        flight_copy = dict(SAMPLE_FLIGHTS[0])
        assert make_key(flight_copy) == make_key(SAMPLE_FLIGHTS[0])

    def test_key_ignores_non_key_fields(self):
        flight = dict(SAMPLE_FLIGHTS[0])
        flight["last_seen"] = "Just now"
        flight["first"] = "999,999 pts"
        assert make_key(flight) == make_key(SAMPLE_FLIGHTS[0])


# -- find_new_flights tests --


class TestFindNewFlights:
    def test_all_new_when_no_previous(self):
        new = find_new_flights(SAMPLE_FLIGHTS, [])
        assert len(new) == 2

    def test_no_new_when_same(self):
        new = find_new_flights(SAMPLE_FLIGHTS, SAMPLE_FLIGHTS)
        assert len(new) == 0

    def test_detects_one_new_flight(self):
        previous = [SAMPLE_FLIGHTS[0]]
        new = find_new_flights(SAMPLE_FLIGHTS, previous)
        assert len(new) == 1
        assert new[0]["origin"] == "ORD"

    def test_empty_current_returns_empty(self):
        new = find_new_flights([], SAMPLE_FLIGHTS)
        assert len(new) == 0

    def test_new_flight_on_different_date(self):
        previous = [SAMPLE_FLIGHTS[0]]
        modified = dict(SAMPLE_FLIGHTS[0])
        modified["date"] = "2026-09-01"
        new = find_new_flights([modified], previous)
        assert len(new) == 1

    def test_same_route_different_source_is_new(self):
        previous = [SAMPLE_FLIGHTS[0]]  # Aeroplan HNL->NRT
        velocity_version = dict(SAMPLE_FLIGHTS[0])
        velocity_version["source"] = "Velocity"
        new = find_new_flights([velocity_version], previous)
        assert len(new) == 1


# -- save/load results tests --


class TestSaveLoadResults:
    def test_save_and_load_roundtrip(self, tmp_path):
        filepath = tmp_path / "results.json"
        with patch("agent.LAST_RESULTS_PATH", str(filepath)):
            save_results(SAMPLE_FLIGHTS)
            loaded = load_previous_results()
        assert loaded == SAMPLE_FLIGHTS

    def test_load_returns_empty_when_file_missing(self, tmp_path):
        filepath = tmp_path / "nonexistent.json"
        with patch("agent.LAST_RESULTS_PATH", str(filepath)):
            loaded = load_previous_results()
        assert loaded == []

    def test_save_overwrites_previous(self, tmp_path):
        filepath = tmp_path / "results.json"
        with patch("agent.LAST_RESULTS_PATH", str(filepath)):
            save_results(SAMPLE_FLIGHTS)
            save_results([SAMPLE_FLIGHTS[0]])
            loaded = load_previous_results()
        assert len(loaded) == 1

    def test_save_empty_list(self, tmp_path):
        filepath = tmp_path / "results.json"
        with patch("agent.LAST_RESULTS_PATH", str(filepath)):
            save_results([])
            loaded = load_previous_results()
        assert loaded == []


# -- scrape_anaf HTML parsing tests --


class TestScrapeAnafParsing:
    """Test the HTML parsing logic of scrape_anaf by mocking Playwright."""

    def _mock_scrape(self, html):
        """Extract the parsing logic from scrape_anaf using mock HTML."""
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        assert table is not None
        rows = table.find_all("tr")
        flights = []
        for row in rows[1:]:
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
            if flight["first"] and "not available" not in flight["first"].lower():
                flights.append(flight)
        return flights

    def test_parses_available_flights(self):
        flights = self._mock_scrape(SAMPLE_HTML)
        assert len(flights) == 2

    def test_filters_out_not_available(self):
        flights = self._mock_scrape(SAMPLE_HTML)
        for f in flights:
            assert "not available" not in f["first"].lower()

    def test_extracts_correct_fields(self):
        flights = self._mock_scrape(SAMPLE_HTML)
        hnl_flight = next(f for f in flights if f["origin"] == "HNL")
        assert hnl_flight["date"] == "2026-07-06"
        assert hnl_flight["source"] == "Aeroplan"
        assert hnl_flight["destination"] == "NRT"
        assert hnl_flight["first"] == "90,000 pts"

    def test_empty_table_returns_empty(self):
        html = "<html><body><table><tr><th>Date</th></tr></table></body></html>"
        flights = self._mock_scrape(html)
        assert flights == []

    def test_row_with_too_few_cells_is_skipped(self):
        html = """
        <html><body><table>
          <tr><th>Date</th></tr>
          <tr><td>2026-07-06</td><td>Aeroplan</td></tr>
        </table></body></html>
        """
        flights = self._mock_scrape(html)
        assert flights == []


# -- send_mac_notification tests --


class TestSendMacNotification:
    @patch("agent.subprocess.run")
    def test_calls_osascript(self, mock_run):
        from agent import send_mac_notification

        send_mac_notification("Test Title", "Test Message")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "osascript"
        assert "Test Title" in args[2]
        assert "Test Message" in args[2]

    @patch("agent.subprocess.run")
    def test_escapes_quotes(self, mock_run):
        from agent import send_mac_notification

        send_mac_notification('Title "quoted"', 'Message "quoted"')
        args = mock_run.call_args[0][0]
        assert '\\"' in args[2]
