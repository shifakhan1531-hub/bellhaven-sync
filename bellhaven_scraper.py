import json
import re
import time
import requests
from bs4 import BeautifulSoup

BASE = "https://analyst-assessment-production.up.railway.app"


def get_soup(url):
    """Download a page and return it in a form we can search."""
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def find_community_links(soup):
    """Find every link that points to a single community page."""
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/communities/" in href:
            full = href if href.startswith("http") else BASE + href
            links.add(full.split("?")[0])
    return links


def get_all_links():
    """Walk through every directory page, plus the homepage."""
    links = set()

    # Directory pages: keep going until there is no "Next" link
    page = 1
    while True:
        soup = get_soup(f"{BASE}/communities?page={page}")
        found = find_community_links(soup)
        if not found:
            break
        links |= found
        has_next = any("Next" in a.get_text() for a in soup.find_all("a"))
        if not has_next:
            break
        page += 1
        time.sleep(0.3)  # be polite to the server

    # Homepage may feature communities missing from the directory
    links |= find_community_links(get_soup(BASE))
    return sorted(links)


def parse_community(url):
    """Visit one community page and pull out the details."""
    soup = get_soup(url)
    name = soup.find("h1").get_text(strip=True)

    # Turn the page into a list of text lines
    lines = [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]

    street = city = state = zip_code = ""
    care = []

    if "Address" in lines:
        i = lines.index("Address")
        street = lines[i + 1]
        m = re.match(r"(.+),\s*([A-Z]{2})\s+(\d{5})", lines[i + 2])
        if m:
            city, state, zip_code = m.groups()

    if "Care Offerings" in lines:
        i = lines.index("Care Offerings") + 1
        while i < len(lines) and lines[i] not in ("Administrator", "Phone"):
            care.append(lines[i])
            i += 1

    return {
        "name": name,
        "address": street,
        "city": city,
        "state": state,
        "zip": zip_code,
        "care_offerings": care,
        "url": url,
    }


def main():
    links = get_all_links()
    print(f"Found {len(links)} community pages")

    results = []
    for link in links:
        try:
            results.append(parse_community(link))
            time.sleep(0.2)
        except Exception as e:
            print("FAILED:", link, e)

    with open("locations.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Saved {len(results)} locations to locations.json")


if __name__ == "__main__":
    main()