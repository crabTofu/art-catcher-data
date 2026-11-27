"""Shared helpers: polite fetching, HTML clean-up and date parsing. Standard library only."""

from __future__ import annotations

import html
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from dataclasses import dataclass
from datetime import date
from urllib.parse import urljoin, urlparse

USER_AGENT = "ArtJournalData/0.1 (monthly exhibition listings; +https://github.com/crabTofu/art-catcher-data)"
MIN_DELAY = 3.0  # seconds between requests to the same host, unless robots.txt asks for more


@dataclass
class Listing:
    """One exhibition as read from a museum site, before dates are parsed."""
    title: str
    venue: str
    url: str
    dates: str  # the date text as shown on the site, e.g. "Until 3 Jan 2027"
    start: date | None = None  # set by readers that get exact dates (e.g. <time datetime>)
    end: date | None = None


class Fetcher:
    """Fetches pages slowly, once per URL, and only where robots.txt allows."""

    def __init__(self) -> None:
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._last: dict[str, float] = {}
        self._cache: dict[str, str] = {}

    def get(self, url: str) -> str:
        if url in self._cache:
            return self._cache[url]
        host = urlparse(url).netloc
        robots = self._robots_for(url)
        if robots and not robots.can_fetch(USER_AGENT, url):
            raise PermissionError(f"robots.txt disallows {url}")
        delay = max(MIN_DELAY, float(robots.crawl_delay(USER_AGENT) or 0) if robots else 0)
        wait = self._last.get(host, 0) + delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-GB"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                text = response.read().decode(response.headers.get_content_charset() or "utf-8", "replace")
        finally:
            self._last[host] = time.monotonic()
        self._cache[url] = text
        return text

    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        parts = urlparse(url)
        root = f"{parts.scheme}://{parts.netloc}"
        if root not in self._robots:
            parser = urllib.robotparser.RobotFileParser(root + "/robots.txt")
            try:
                request = urllib.request.Request(root + "/robots.txt", headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(request, timeout=15) as response:
                    parser.parse(response.read().decode("utf-8", "replace").splitlines())
            except urllib.error.HTTPError as error:
                # Per the robots.txt convention: 4xx means no rules, other errors mean stay away.
                if 400 <= error.code < 500:
                    parser.parse([])
                else:
                    raise
            self._robots[root] = parser
        return self._robots[root]


# MARK: HTML

def text(fragment: str) -> str:
    """Visible text of an HTML fragment, on one line."""
    fragment = re.sub(r"(?is)<(script|style|svg)\b.*?</\1>", " ", fragment)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(fragment)).strip()


def absolute(base: str, href: str) -> str:
    return urljoin(base, html.unescape(href))


def warn(message: str) -> None:
    print(f"  ! {message}", file=sys.stderr)


# MARK: Dates

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_MONTH = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_DATE = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{_MONTH}(?:,?\s+(\d{{4}}))?", re.I)
_DAY_RANGE = re.compile(rf"\b(\d{{1,2}})\s*[–—-]\s*(\d{{1,2}})\s+{_MONTH}(?:\s+(\d{{4}}))?", re.I)
_MONTH_YEAR = re.compile(rf"\b{_MONTH}\s+(\d{{4}})\b", re.I)
_WEEKDAY =re.compile(r"\b(mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)[a-z]*,?\s+", re.I)


def _month(token: str) -> int:
    return MONTHS[token[:3].lower()]


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_range(raw: str, today: date) -> tuple[date | None, date | None]:
    """Reads the start and end out of date text such as "7 Oct - 14 Feb 2027",
    "Until 3 Jan 2027", "Closes Sunday, 10 January 2027" or "Opens 5 March 2027".
    A missing start means the show is already open; a missing end means it isn't known."""
    s = _WEEKDAY.sub("", raw)
    lower = s.lower()

    # "5 – 20 March 2027": the first day borrows the month and year.
    m = _DAY_RANGE.search(s)
    if m:
        month = _month(m.group(3))
        year = int(m.group(4)) if m.group(4) else _nearest_year(month, int(m.group(2)), today, future=True)
        return _safe_date(year, month, int(m.group(1))), _safe_date(year, month, int(m.group(2)))

    # "24 September 2027 - January 2028": the end is only given as a month.
    m = re.search(rf"{_DATE.pattern}\s*[–—-]\s*{_MONTH}\s+(\d{{4}})\b", s, re.I)
    if m:
        start_year = int(m.group(3)) if m.group(3) else int(m.group(5))
        end_month, end_year = _month(m.group(4)), int(m.group(5))
        next_month = date(end_year + (end_month == 12), end_month % 12 + 1, 1)
        return _safe_date(start_year, _month(m.group(2)), int(m.group(1))), date.fromordinal(next_month.toordinal() - 1)

    found = [(int(d), _month(mon), int(y) if y else None) for d, mon, y in _DATE.findall(s)]
    if not found:
        # "Until October 2027": take the last day of that month.
        m = _MONTH_YEAR.search(s)
        if m and re.search(r"\b(until|closes|ends)\b", lower):
            month, year = _month(m.group(1)), int(m.group(2))
            next_month = date(year + (month == 12), month % 12 + 1, 1)
            return None, date.fromordinal(next_month.toordinal() - 1)
        return None, None

    if len(found) >= 2:
        (sd, sm, sy), (ed, em, ey) = found[0], found[1]
        if ey is None:
            ey = _nearest_year(em, ed, today, future=True)
        if sy is None:
            sy = ey - 1 if (sm, sd) > (em, ed) else ey
        return _safe_date(sy, sm, sd), _safe_date(ey, em, ed)

    d, mon, y = found[0]
    if re.search(r"\b(until|closes|closing|ends|to)\b", lower):
        return None, _safe_date(y or _nearest_year(mon, d, today, future=True), mon, d)
    if re.search(r"\b(opens|opening|from|starts|coming)\b", lower):
        return _safe_date(y or _nearest_year(mon, d, today, future=True), mon, d), None
    return None, None  # a single date with no keyword: too ambiguous to guess


def _nearest_year(month: int, day: int, today: date, future: bool) -> int:
    """The year that puts day/month on or after today (or within the past few months)."""
    candidate = _safe_date(today.year, month, day) or date(today.year, month, 28)
    if future and (candidate - today).days < -120:
        return today.year + 1
    return today.year


# MARK: Cards

def cards(page: str, start: str) -> list[str]:
    """The HTML between successive matches of `start` (a regex), each match included."""
    starts = [m.start() for m in re.finditer(start, page)]
    return [page[a:b] for a, b in zip(starts, starts[1:] + [len(page)])]


def first(pattern: str, chunk: str, group: int = 1) -> str | None:
    m = re.search(pattern, chunk, re.S)
    return m.group(group) if m else None


_RANGE_IN_TEXT = re.compile(
    rf"\d{{1,2}}\s+{_MONTH}(?:\s+\d{{4}})?\s*[–—-]\s*\d{{1,2}}\s+{_MONTH}\s+\d{{4}}", re.I)


def find_range(page_text: str) -> str | None:
    """The first "23 May – 29 November 2026"-style range in a page's text (weekdays ignored)."""
    m = _RANGE_IN_TEXT.search(_WEEKDAY.sub("", page_text))
    return m.group(0) if m else None
