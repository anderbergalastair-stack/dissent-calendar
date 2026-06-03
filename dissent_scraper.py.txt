import os
from datetime import datetime
import re
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
import pytz
import requests

# 1. Fetch the Humanitix collection page for Dissent Bar
URL = "https://humanitix.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def scrape_dissent_events():
    response = requests.get(URL, headers=HEADERS)
    if response.status_code != 200:
        print(f"Failed to fetch page: Status {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    events = []

    # Humanitix event cards typically sit inside anchor tags or specific card divs
    # This searches for common Humanitix event container links
    event_cards = soup.find_all("a", href=re.compile(r"/events/"))

    for card in event_cards:
        try:
            # Extract Event Title
            title_tag = card.find(["h2", "h3", "span"], class_=re.compile(r"title|name", re.I))
            title = title_tag.text.strip() if title_tag else "Dissent Bar Event"

            # Extract Event URL
            link = card["href"]
            if not link.startswith("http"):
                link = "https://humanitix.com" + link

            # Extract Date Text
            date_tag = card.find(class_=re.compile(r"date|time", re.I))
            date_text = date_tag.text.strip() if date_tag else ""

            if title and date_text:
                events.append({"title": title, "date_text": date_text, "url": link})
        except Exception as e:
            continue

    return events


def parse_humanitix_date(date_str):
    """
    Parses typical Humanitix date strings (e.g., 'Thu 4th June, 7:00 pm')
    and returns a localized datetime object.
    """
    # Clean up ordinals (st, nd, rd, th) to make parsing easier
    clean_date = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", date_str)
    # Remove day of the week prefix if present (e.g. 'Thu ')
    clean_date = re.sub(r"^[A-Za-z]{3,4}\s+", "", clean_date)

    # Append current year since web guides often omit it
    current_year = datetime.now().year
    clean_date = f"{clean_date} {current_year}"

    # Try parsing format: '4 June, 7:00 pm 2026'
    try:
        dt = datetime.strptime(clean_date, "%d %B, %I:%M %p %Y")
        return pytz.timezone("Australia/Canberra").localize(dt)
    except ValueError:
        # Fallback default if parsing logic fails due to formatting changes
        return datetime.now(pytz.timezone("Australia/Canberra"))


def generate_ics(events, output_filename="dissent_bar_canberra.ics"):
    cal = Calendar()
    cal.add("prodid", "-//Dissent Bar Canberra Scraper//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "Dissent Cafe & Bar Canberra")

    for ev in events:
        event = Event()
        start_time = parse_humanitix_date(ev["date_text"])

        event.add("summary", ev["title"])
        event.add("dtstart", start_time)
        # Default duration to 3 hours if not specified
        event.add(
            "dtend", start_time + datetime.timedelta(hours=3) if start_time else None
        )
        event.add("location", "Dissent Cafe and Bar, Canberra, ACT, Australia")
        event.add("description", f"Tickets & Info: {ev['url']}")
        event.add("url", ev["url"])

        cal.add_component(event)

    with open(output_filename, "wb") as f:
        f.write(cal.to_ical())
    print(f"Successfully generated {output_filename} with {len(events)} events.")


if __name__ == "__main__":
    print("Scraping Dissent Bar events...")
    live_events = scrape_dissent_events()
    if live_events:
        generate_ics(live_events)
    else:
        print("No events found. Check if the page layout has changed.")
