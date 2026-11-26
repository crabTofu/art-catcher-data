"""Readers for London museum and gallery sites. Each returns the exhibitions listed on the
site's own pages, as `Listing`s with the date text the site shows.

When a site is redesigned its reader returns nothing (or fails), and the run report says so:
fix the patterns here against the new markup.

Sites that block automated requests (British Museum, Royal Academy, National Portrait
Gallery, Southbank Centre, Dulwich Picture Gallery) are kept by hand in london/manual.json.
"""

from __future__ import annotations

import json
import re
from typing import Callable

from common import Fetcher, Listing, absolute, cards, find_range, first, text

Reader = Callable[[Fetcher], list[Listing]]


def tate(fetch: Fetcher) -> list[Listing]:
    base = "https://www.tate.org.uk/whats-on?event_type=exhibition"
    found: list[Listing] = []
    for page in range(1, 6):
        html = fetch.get(f"{base}&page={page}")
        page_cards = cards(html, r'<div class="card(?: [^"]*)?">\s*<div class="card__inner">')
        for card in page_cards:
            title = first(r'card__title--maintitle">(.*?)</span>', card)
            href = first(r'<a href="(/whats-on/[^"]+)"', card)
            venue = first(r'event-info__venue">.*?<span>(.*?)</span>', card)
            dates = first(r'event-info__date">.*?<span>(.*?)</span>', card)
            tag = first(r'<div class="card-tags">\s*<span>(.*?)</span>', card)
            # Exhibition-related events (relaxed hours, members' views) carry the same tag.
            if (title and href and venue and dates and tag and text(tag) in ("Exhibition", "Exhibitions")
                    and text(venue) in ("Tate Modern", "Tate Britain")
                    and not re.match(r"(Relaxed Hours|Members)\b", text(title))):
                found.append(Listing(text(title), text(venue), absolute(base, href), text(dates)))
        if f"page={page + 1}" not in html:
            break
    return found


def national_gallery(fetch: Fetcher) -> list[Listing]:
    url = "https://www.nationalgallery.org.uk/exhibitions"
    html = fetch.get(url)
    found = []
    for card in cards(html, r'<article\s+class="card [^"]*exhibition-card'):
        href = first(r'href="(/exhibitions/[^"]+)"', card)
        title = first(r'class="exhibition-heading">(.*?)</h3>', card)
        dates = first(r'class="exhibition-date">(.*?)</div>', card)
        tag = first(r'<div class="tags">(.*?)</div>', card) or ""
        if href and title and dates and "Exhibition" in text(tag):
            found.append(Listing(text(title), "National Gallery", absolute(url, href), text(dates)))
    return found


def barbican(fetch: Fetcher) -> list[Listing]:
    url = "https://www.barbican.org.uk/whats-on/art-design"
    html = fetch.get(url)
    found = []
    for card in cards(html, r'<a class="promo-card__url" href="'):
        href = first(r'href="(/whats-on/\d{4}/event/[^"]+)"', card)  # /series/ are talk programmes
        title = first(r'class="product-title">(.*?)</div>', card)
        dates = first(r'class="date-range">(.*?)</span>\s*</div>', card)
        if href and title and dates:
            found.append(Listing(text(title), "Barbican Art Gallery", absolute(url, href), text(dates)))
    return found


def vam(fetch: Fetcher) -> list[Listing]:
    url = "https://www.vam.ac.uk/whatson?type=exhibition"
    html = fetch.get(url)
    found = []
    for card in cards(html, r'<a href="/exhibitions/'):
        href = first(r'<a href="(/exhibitions/[^"]+)"', card)
        title = first(r'class="b-card__heading">(.*?)</h3>', card)
        dates = first(r'icon--calendar".*?item-text">(.*?)</p>', card)
        venue = first(r'icon--pin".*?item-text">(.*?)</p>', card)
        # V&A Dundee isn't in London.
        if href and title and dates and venue and "Dundee" not in venue:
            found.append(Listing(text(title), text(venue), absolute(url, href), text(dates)))
    return found


def wallace(fetch: Fetcher) -> list[Listing]:
    # The listing has no dates, so each exhibition page is read (robots.txt asks for 30 s between requests).
    url = "https://www.wallacecollection.org/whats-on/exhibitions-displays/"
    html = fetch.get(url)
    found = []
    for href in dict.fromkeys(re.findall(r'href="(/whats-on/exhibitions-displays/[^"/]+/)"', html)):
        page = fetch.get(absolute(url, href))
        title = first(r"<h1[^>]*>(.*?)</h1>", page)
        dates = find_range(text(page))
        if title and dates:
            found.append(Listing(text(title), "The Wallace Collection", absolute(url, href), dates))
    return found


def design_museum(fetch: Fetcher) -> list[Listing]:
    url = "https://designmuseum.org/exhibitions"
    html = fetch.get(url)
    found = []
    for card in cards(html, r'<div class="page-item clearfix">'):
        href = first(r'<a\s+href="(/exhibitions/[^"]+)"', card)
        title = first(r"<h2[^>]*>(.*?)</h2>", card)
        dates = first(r'<time class="icon-date">(.*?)</time>', card)
        if href and title and dates:
            found.append(Listing(text(title), "Design Museum", absolute(url, href), text(dates)))
    return found


def serpentine(fetch: Fetcher) -> list[Listing]:
    url = "https://www.serpentinegalleries.org/whats-on/"
    html = fetch.get(url)
    found = []
    for card in cards(html, r'<h3 class="teaser__title">'):
        href = first(r'href="(https://www\.serpentinegalleries\.org/whats-on/[^"]+)"', card)
        title = first(r'class="teaser__link"[^>]*>(.*?)</a>', card)
        venue = first(r'class="meta__term">(.*?)</span>', card)
        rows = [text(r) for r in re.findall(r'<div class="meta__row">([^<]+)</div>', card)]
        dates = next((r for r in rows if re.search(r"\d{4}", r)), None)
        if dates and not re.search(r"\buntil\b|[–—-]", dates, re.I):
            continue  # a single-day talk or event, not an exhibition
        # Galleries only: talks and events take place elsewhere or have no venue.
        if href and title and venue and dates and "Gallery" in venue:
            found.append(Listing(text(title), text(venue), href, dates))
    return found


def whitechapel(fetch: Fetcher) -> list[Listing]:
    url = "https://www.whitechapelgallery.org/exhibitions/"
    html = fetch.get(url)
    found = []
    for card in cards(html, r"<div class='oneHalfMedia"):
        href = first(r"<h4 class='category_name'><a href='([^']+)'", card)
        title = first(r"<h4 class='category_name'><a [^>]*>(.*?)</a>", card)
        dates = first(r"<p>(.*?)</p>", card)
        if href and title and dates and "/exhibitions/" in href:
            found.append(Listing(text(title), "Whitechapel Gallery", href, text(dates)))
    return found


def courtauld(fetch: Fetcher) -> list[Listing]:
    # WordPress API for the list (exhibition pages start "exh-"), then each page for its dates.
    api = "https://courtauld.ac.uk/wp-json/wp/v2/events?per_page=100&orderby=date&order=desc&_fields=link,title"
    events = json.loads(fetch.get(api))
    found = []
    for event in events:
        link = event.get("link", "")
        if "/whats-on/exh-" not in link:
            continue
        page = fetch.get(link)
        title = text(event.get("title", {}).get("rendered", ""))
        dates = find_range(text(page))
        if title and dates:
            found.append(Listing(title, "The Courtauld Gallery", link, dates))
    return found


READERS: dict[str, Reader] = {
    "Tate": tate,
    "National Gallery": national_gallery,
    "Barbican": barbican,
    "V&A": vam,
    "Wallace Collection": wallace,
    "Design Museum": design_museum,
    "Serpentine": serpentine,
    "Whitechapel Gallery": whitechapel,
    "The Courtauld": courtauld,
}
