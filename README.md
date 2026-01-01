SCOUT – Keyword-Based Collectibles Search

SCOUT is a lightweight intelligence terminal for tracking hard-to-find items (collectibles, badges, signs, niche hardware, etc.) across the web using keyword searches on a recurring schedule.

The core idea is simple:

Define what you’re looking for, define where to look, and let SCOUT keep an eye out.

What SCOUT Does Today

SCOUT currently performs Google-based searches via SerpAPI, scoped to specific websites, using user-defined keywords.

In practical terms, this means:

You define keywords (e.g., Pentium badge, IBM sign)

You define sites/domains to watch (e.g., vintage-computer.com, newegg.com)

SCOUT runs Google searches like:

site:vintage-computer.com Pentium badge


Results are collected, stored, and displayed

You can run searches on demand or later on a schedule

This model works especially well for:

Collectibles

Obscure inventory pages

Old static websites

Hobbyist and niche communities

Low-volume, high-signal searches

What SCOUT Does Not Do (Yet)

SCOUT does not yet perform native marketplace searches, such as:

eBay marketplace API

Amazon marketplace API

Etsy marketplace API

Those engines are supported by SerpAPI and are planned, but currently disabled in the UI to avoid ambiguity about what is actually being searched.

They will be enabled incrementally once each collector method is implemented and verified.

Search Engines vs. Search Targets (Important Concept)

SCOUT deliberately separates:

Search Engine (How)

The mechanism used to perform the search.

Currently implemented:

Google (via SerpAPI)

Planned:

eBay (SerpAPI)

Amazon (SerpAPI)

Etsy (SerpAPI / limited)

Search Targets (Where)

The sites or domains being searched through the engine.

Examples:

vintage-computer.com

newegg.com

random-antique-site.org

Right now, all targets are searched via Google.

Features

Keyword library with enable/disable controls

Site/domain registry

Ad-hoc (“run now”) searches

Persistent archive of findings

Live feed showing only the current run

SQLite backend

Streamlit UI

Verbose logging with optional debug mode

Log purge from UI

Designed for scheduled execution (scheduler wiring in progress)

Requirements

Python 3.10+

Streamlit

SQLite

SerpAPI account

Configuration
SerpAPI Key

SCOUT expects your SerpAPI key to be stored in:

.streamlit/secrets.toml


Example:

SERPAPI_KEY = "your_api_key_here"


Restart Streamlit after adding or changing the key.

Running SCOUT
streamlit run app.py

Roadmap (Intentional and Incremental)

Planned additions, in order:

Native eBay marketplace collector (SerpAPI)

Native Amazon marketplace collector (SerpAPI)

Per-site collection method selection

Scheduled/background execution

Notification hooks (email / webhook)

These will be added one engine at a time to keep behavior explicit and debuggable.

Philosophy

SCOUT is intentionally:

Transparent about what it is searching

Conservative about adding complexity

Focused on real-world usefulness over abstraction

If it ever becomes unclear what SCOUT is doing, that’s considered a bug.
