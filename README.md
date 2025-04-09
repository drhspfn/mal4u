# mal4u: Asynchronous MyAnimeList Scraper

[![PyPI version](https://badge.fury.io/py/mal4u.svg)](https://badge.fury.io/py/mal4u)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An unofficial, asynchronous Python library for scraping data from [MyAnimeList.net](https://myanimelist.net/). Built with `aiohttp` for efficient network requests and `beautifulsoup4` for HTML parsing. Uses Pydantic for data validation and structuring.

**Disclaimer:** This is an unofficial library and is not affiliated with MyAnimeList. Please use responsibly and respect MAL's terms of service. Excessive scraping can lead to IP bans.

## Features

*   **Asynchronous:** Leverages `asyncio` and `aiohttp` for non-blocking network I/O.
*   **Session Management:** Supports both explicit session creation/closing and automatic handling via `async with`.
*   **Modular Parsers:** Designed with a base parser and specific sub-parsers for Manga and Anime.
*   **Type Hinted:** Fully type-hinted codebase for better developer experience and static analysis.
*   **Data Validation:** Uses Pydantic models (`MangaSearchResult`, `AnimeSearchResult` (planned), `MangaDetails`, `AnimeDetails`, etc.) to structure and validate scraped data.
*   **Robust Detail Parsing:** Extracts a wide range of information from detail pages, including titles, synopsis, background, stats, related entries, characters, themes, and more for both anime and manga.

## Current Capabilities

*   **Search:**
    *   Search for Manga.
    *    Search for Anime
*   **Details:**
    *   Get detailed information for a specific Manga by ID (using `MangaDetails` model).
    *   Get detailed information for a specific Anime by ID (using `AnimeDetails` model).
*   **Browse/Lists (from overview pages like `manga.php`/`anime.php`):**
    *   Get available Genres (Anime & Manga).
    *   Get available Themes (Anime & Manga).
    *   Get available Demographics (Anime & Manga).
    *   Get a preview list of Magazines (Manga).
    *   *(Planned: Get Studios list (Anime)).*

## Installation

```bash
pip install mal4u
```

## Basic Usage

### Recommended: Using `async with`

This automatically handles session creation and closing.

```python
import asyncio
import logging
from mal4u import MyAnimeListApi, MangaSearchResult, MangaDetails, AnimeDetails

# Optional: Configure logging for more details
logging.basicConfig(level=logging.INFO)
logging.getLogger('mal4u').setLevel(logging.DEBUG) # See debug logs from the library

async def main():
    async with MyAnimeListApi() as api:
        # --- Manga Example ---
        print("Searching for 'Berserk' manga...")
        search_results: list[MangaSearchResult] = await api.manga.search("Berserk", limit=1)
        manga_id_to_get = 2 # Default to Berserk if search fails
        if search_results:
            print(f"- Found: {search_results[0].title} (ID: {search_results[0].mal_id})")
            manga_id_to_get = search_results[0].mal_id
        else:
            print("Search returned no results. Using default ID 2.")

        print(f"\nGetting details for Manga ID: {manga_id_to_get}")
        manga_details: MangaDetails | None = await api.manga.get(manga_id_to_get)

        if manga_details:
            print(f"  Title: {manga_details.title} ({manga_details.type})")
            print(f"  Status: {manga_details.status}")
            print(f"  Score: {manga_details.score} (by {manga_details.scored_by} users)")
            print(f"  Chapters: {manga_details.chapters}, Volumes: {manga_details.volumes}")
            print(f"  Synopsis (start): {manga_details.synopsis[:100] if manga_details.synopsis else 'N/A'}...")
            print(f"  Genres: {[genre.name for genre in manga_details.genres]}")
        else:
            print(f"  Could not retrieve details for Manga ID: {manga_id_to_get}")

        print("\n" + "="*20 + "\n")

        # --- Anime Example ---
        anime_id_to_get = 40852 # Dr. Stone: Stone Wars
        print(f"Getting details for Anime ID: {anime_id_to_get}")
        anime_details: AnimeDetails | None = await api.anime.get(anime_id_to_get)

        if anime_details:
            print(f"  Title: {anime_details.title} ({anime_details.type})")
            print(f"  Status: {anime_details.status}")
            print(f"  Score: {anime_details.score} (by {anime_details.scored_by} users)")
            print(f"  Episodes: {anime_details.episodes}")
            print(f"  Premiered: {anime_details.premiered.name if anime_details.premiered else 'N/A'}")
            print(f"  Synopsis (start): {anime_details.synopsis[:100] if anime_details.synopsis else 'N/A'}...")
            print(f"  Studios: {[studio.name for studio in anime_details.studios]}")
            print(f"  Opening Theme(s): {anime_details.opening_themes}")
        else:
            print(f"  Could not retrieve details for Anime ID: {anime_id_to_get}")


if __name__ == "__main__":
    asyncio.run(main())
```

### Manual Session Management

You need to explicitly create and close the session.

```python
import asyncio
import logging
from mal4u import MyAnimeListApi

logging.basicConfig(level=logging.INFO)

async def main_manual():
    api = MyAnimeListApi()
    try:
        # Explicitly create the session
        await api.create_session()
        print("Session created.")

        # Perform actions (e.g., get anime details)
        anime_id = 5114 # FMA: Brotherhood
        print(f"Getting details for Anime ID: {anime_id}")
        details = await api.anime.get(anime_id)
        if details:
            print(f"- Found: {details.title} (Score: {details.score})")
        else:
            print(f"- Could not retrieve details for Anime ID: {anime_id}")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Ensure the session is closed
        print("Closing session...")
        await api.close()
        print("Session closed.")

if __name__ == "__main__":
    asyncio.run(main_manual())
```

## TODO

*   [x] Search Manga
*   [x] Get Manga Details (`MangaDetails`)
*   [x] Search Anime (`AnimeSearchResult`)
*   [x] Get Anime Details (`AnimeDetails`)
*   [ ] Get Character Details (`CharacterDetails`)
*   [ ] Implement Parsers for other MAL sections (People, Studios, etc.).
*   [ ] Implement more robust error handling (e.g., custom exceptions for 404, parsing failures).
*   [ ] Add unit and integration tests.
*   [ ] Improve documentation (detailed docstrings, potentially Sphinx docs).
*   [ ] Add rate limiting awareness/options.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request. (You might want to add more details here later).

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.
