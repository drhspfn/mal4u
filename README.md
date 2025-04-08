
# mal4u: Asynchronous MyAnimeList Scraper

[![PyPI version](https://badge.fury.io/py/mal4u.svg)](https://badge.fury.io/py/mal4u) 
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An unofficial, asynchronous Python library for scraping data from [MyAnimeList.net](https://myanimelist.net/). Built with `aiohttp` for efficient network requests and `beautifulsoup4` for HTML parsing. Uses Pydantic for data validation and structuring.

**Disclaimer:** This is an unofficial library and is not affiliated with MyAnimeList. Please use responsibly and respect MAL's terms of service. Excessive scraping can lead to IP bans.

## Features

*   **Asynchronous:** Leverages `asyncio` and `aiohttp` for non-blocking network I/O.
*   **Session Management:** Supports both explicit session creation/closing and automatic handling via `async with`.
*   **Modular Parsers:** Designed with a base parser and specific sub-parsers (currently Manga).
*   **Type Hinted:** Fully type-hinted codebase for better developer experience and static analysis.
*   **Data Validation:** Uses Pydantic models (`MangaSearchResult`, `MangaDetails`, etc.) to structure and validate scraped data.
*   **Current Capabilities:**
    *   Search for Manga.
    *   Get detailed information for a specific Manga by ID.

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
from mal4u import MyAnimeListApi, MangaSearchResult, MangaDetails

# Optional: Configure logging for more details
logging.basicConfig(level=logging.INFO)
logging.getLogger('mal4u').setLevel(logging.DEBUG) # See debug logs from the library

async def main():
    async with MyAnimeListApi() as api:
        # Search for manga
        print("Searching for 'Berserk'...")
        search_results: list[MangaSearchResult] = await api.manga.search("Berserk", limit=3)
        if search_results:
            print(f"Found {len(search_results)} results:")
            for result in search_results:
                print(f"- ID: {result.mal_id}, Title: {result.title}, Type: {result.manga_type}, Score: {result.score}")
        else:
            print("Search returned no results.")

        print("\n" + "="*20 + "\n")

        # Get details for a specific manga (using Berserk's ID: 2)
        manga_id_to_get = 2
        print(f"Getting details for Manga ID: {manga_id_to_get}")
        details: MangaDetails | None = await api.manga.get(manga_id_to_get)

        if details:
            print(f"Title: {details.title} ({details.type})")
            print(f"Status: {details.status}")
            print(f"Score: {details.score} (by {details.scored_by} users)")
            print(f"Rank: #{details.rank}, Popularity: #{details.popularity}")
            print(f"Synopsis (first 100 chars): {details.synopsis[:100] if details.synopsis else 'N/A'}...")
            print(f"Genres: {[genre.name for genre in details.genres]}")
        else:
            print(f"Could not retrieve details for Manga ID: {manga_id_to_get}")

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

        # Perform actions
        print("Searching for 'Vinland Saga'...")
        results = await api.manga.search("Vinland Saga", limit=1)
        if results:
            print(f"- Found: {results[0].title} (ID: {results[0].mal_id})")
        else:
            print("Search returned no results.")

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

*   [ ] Implement Anime Parser (`search`, `get`).
*   [ ] Implement Character Parser (`get`).
*   [ ] Add parsers for other MAL sections (People, Studios, etc.).
*   [ ] Implement more robust error handling (e.g., custom exceptions).
*   [ ] Add unit and integration tests.
*   [ ] Improve documentation (detailed docstrings, potentially Sphinx docs).
*   [ ] Add rate limiting awareness/options.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request. (You might want to add more details here later).

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.
