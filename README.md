# Art Catcher data

Exhibition listings for the Art Catcher app's "What's on" tab, refreshed by hand about once a month. The app downloads `london/exhibitions.json`.

## Refresh (monthly)

```bash
python3 scraper/scrape.py
git diff london/exhibitions.json
```

1. Run the scraper (about 3 minutes; it waits between requests on purpose). It needs only Python 3, with no packages to install.
2. Read the report. `nothing found` or `FAILED` for a site means its page changed. Fix that site's reader in `scraper/sites/london.py`. The previous listings for that site are kept in the meantime.
3. Update `london/manual.json` from the pages listed in it (the museums that block scripts), and update the `checked` dates.
4. Check the diff, then commit and push.

To re-read just some sites: `python3 scraper/scrape.py Tate "National Gallery"`.

## What's in the file

```json
{
  "version": 1,
  "city": "London",
  "updated": "2026-11-26",
  "exhibitions": [
    {
      "id": "3f2c…",
      "title": "Monet: Painting Time",
      "venue": "Tate Modern",
      "url": "https://www.tate.org.uk/whats-on/…",
      "start": "2027-02-25",
      "end": "2027-06-27",
      "dates": "25 Feb – 27 Jun 2027",
      "source": "Tate"
    }
  ]
}
```

- `start: null`: the show is already open (the site only says "Until …").
- `end: null`: the closing date isn't announced.
- Shows that have closed are dropped on each run.
- The list is sorted by closing date.

## Sources

| Read by the scraper | Kept by hand (`manual.json`) |
|---|---|
| Tate Modern and Tate Britain, National Gallery, Barbican, V&A (South Kensington, East), Wallace Collection, Design Museum, Serpentine, Whitechapel, The Courtauld | British Museum, Royal Academy, Hayward Gallery (Southbank), Dulwich Picture Gallery, National Portrait Gallery (blocked even in a browser) |

## Ground rules

- **Facts only:** title, venue, dates and link. No descriptions, images or prices. The museum's own page is the source for details.
- **Polite:** follow `robots.txt` (checked on every request), wait at least 3 s between requests to a site (30 s for the Wallace, as its `robots.txt` asks), identify the scraper in the User-Agent, and run about once a month.
- **No bypassing:** no bypassing of bot checks or CAPTCHAs. Sites that block scripts go in `manual.json`.
- **Credit:** the app names each museum and links to its page. Don't suggest the museums endorse the app.
