import json
import re
from datetime import datetime
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
import pytz
import requests

URL = "https://collections.humanitix.com/dissent-gigs"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def scrape_dissent_events():
    """Fetches Humanitix JSON configuration data directly to bypass JS execution barriers."""
    session = requests.Session()
    response = session.get(URL, headers=HEADERS)

    if response.status_code != 200:
        print(f"Extraction failed: HTTP Status {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    events = []

    # Humanitix stores framework data in a __NEXT_DATA__ script payload
    script_tag = soup.find("script", id="__NEXT_DATA__")

    if not script_tag:
        print(
            "Target data signature missing. Humanitix structure may have shifted."
        )
        return []

    try:
        # Load internal page layout values directly from raw text block
        json_data = json.loads(script_tag.string)

        # Dig down the nested parameters to grab raw event configurations
        # Path: props -> pageProps -> initialData -> collection -> events
        page_props = json_data.get("props", {}).get("pageProps", {})
        initial_data = page_props.get("initialData", {})
        collection = initial_data.get("collection", {})
        raw_events = collection.get("events", [])

        # If data is structural but collection mapping is flat:
        if not raw_events:
            raw_events = initial_data.get("events", [])

        for item in raw_events:
            title = item.get("name")
            start_iso = item.get(
                "startDate"
            )  # Comes back as a stable '2026-06-04T08:30:00.000Z'
            end_iso = item.get("endDate")
            slug = item.get("slug")

            # Validate that minimum data required exists
            if title and start_iso:
                events.append(
                    {
                        "title": title,
                        "start_iso": start_iso,
                        "end_iso": end_iso,
                        "url": f"https://events.humanitix.com/{slug}"
                        if slug
                        else URL,
                    }
                )

    except Exception as err:
        print(f"Error compiling layout values: {err}")

    return events


def parse_iso_timestamp(iso_str):
    """Safely converts an ISO 8601 string into a fixed Canberra timezone object."""
    if not iso_str:
        return None
    try:
        # Normalize the typical trailing Z / offsets format for python datetime
        clean_iso = iso_str.replace("Z", "+00:00")
        # Parse the raw timestamp structure safely
        dt_utc = datetime.fromisoformat(clean_iso)
        # Shift the UTC baseline timeline directly into native Canberra time
        canberra_tz = pytz.timezone("Australia/Canberra")
        return dt_utc.astimezone(canberra_tz)
    except ValueError:
        print(f"Invalid timestamp format encountered: {iso_str}")
        return None


def generate_ics(events, output_filename="dissent_bar_canberra.ics"):
    """Builds a fully compliant iCalendar container with clear localized start/end fields."""
    cal = Calendar()
    cal.add("prodid", "-//Dissent Bar Canberra Event Bot//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "Dissent Cafe & Bar Gigs")

    for ev in events:
        event = Event()
        start_time = parse_iso_timestamp(ev["start_iso"])
        end_time = parse_iso_timestamp(ev["end_iso"])

        if not start_time:
            continue

        event.add("summary", ev["title"])
        event.add("dtstart", start_time)

        # Set end time or assign a 3.5 hour default timeframe if missing
        if end_time:
            event.add("dtend", end_time)
        else:
            from datetime import timedelta

            event.add("dtend", start_time + timedelta(hours=3, minutes=30))

        event.add("location", "Dissent Cafe and Bar, Canberra, ACT, Australia")
        event.add("description", f"Event Info & Tickets: {ev['url']}")
        event.add("url", ev["url"])

        cal.add_component(event)

    with open(output_filename, "wb") as f:
        f.write(cal.to_ical())
    print(
        f"Export completely successful. Generated {output_filename} containing {len(events)} matches."
    )


if __name__ == "__main__":
    print("Beginning extraction loop on Humanitix Data Hub...")
    live_listings = scrape_dissent_events()
    if live_listings:
        generate_ics(live_listings)
    else:
        print(
            "Extraction yielded 0 events. Ensure page target configuration matches."
        )
