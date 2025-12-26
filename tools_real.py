# tools.py
import os
import re
from typing import List, Dict, Optional
from functools import lru_cache
from dotenv import load_dotenv
from serpapi import GoogleSearch

load_dotenv()

# ===== CONFIG =====
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
if not SERPAPI_KEY:
    raise ValueError("⚠️ SERPAPI_KEY not found in .env")

# Store priority order (most preferred first)
STORE_PRIORITY = ["Walmart", "Kroger", "Amazon", "Target", "Instacart"]

# Fallback mock prices (if SerpApi fails)
MOCK_PRICES = {
    "milk": 3.5, "eggs": 2.8, "bread": 2.2, "bananas": 0.6,
    "coffee": 8.99, "tomatoes": 2.5, "rice": 4.0, "pasta": 1.8,
    "cheese": 4.2, "chicken": 5.99, "apple": 1.2, "orange": 1.3
}


# ===== CACHED REAL PRICE LOOKUP =====
@lru_cache(maxsize=256)
def _fetch_price_from_serpapi(item: str, store_filter: Optional[str] = None) -> Optional[Dict]:
    """
    Fetch real price from SerpApi with caching.
    Returns dict with keys: item, store, price, link, title
    """
    params = {
        "engine": "google_shopping",
        "q": item,
        "api_key": SERPAPI_KEY,
        "google_domain": "google.com",
        "gl": "us",
        "hl": "en",
        "num": 20
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        shopping_results = results.get("shopping_results", [])

        # Apply store filter if provided
        if store_filter:
            shopping_results = [
                r for r in shopping_results
                if store_filter.lower() in r.get("source", "").lower()
            ]

        valid_results = []
        for r in shopping_results:
            price_str = r.get("price", "")
            if not price_str:
                continue
            # Extract numeric price from "$12.99" or "12,99 €"
            price_match = re.search(r"[\d,\.]+", price_str)
            if not price_match:
                continue
            price_clean = price_match.group().replace(",", "")
            try:
                price = float(price_clean)
                valid_results.append({
                    "item": item,
                    "store": r.get("source", "Unknown"),
                    "price": price,
                    "link": r.get("link", ""),
                    "title": r.get("title", item)
                })
            except ValueError:
                continue

        if not valid_results:
            return None

        # Return cheapest
        return min(valid_results, key=lambda x: x["price"])

    except Exception as e:
        print(f"⚠️ SerpApi error for '{item}' (store={store_filter}): {e}")
        return None


def mock_price_lookup(item: str, store: str) -> Dict[str, any]:
    """Fallback mock pricing."""
    base = MOCK_PRICES.get(item.lower(), 5.0)
    variation = {"Walmart": 0.95, "Amazon": 1.1, "Kroger": 1.0, "Target": 1.05}.get(store, 1.0)
    price = round(base * variation * (0.95 + (hash(item) % 100) / 100), 2)
    return {
        "item": item,
        "store": store,
        "price": price,
        "link": "#",
        "title": f"Mock {item.title()}"
    }


def find_best_basket(grocery_list: List[str], avoid_stores: List[str] = None) -> Dict:
    """
    Build optimized basket using real (cached) prices + fallback.
    """
    avoid_stores = [s.lower() for s in (avoid_stores or [])]
    basket = {}
    total = 0.0

    for item in grocery_list:
        best_option = None
        best_price = float('inf')

        # Try preferred stores first
        for store in STORE_PRIORITY:
            if store.lower() in avoid_stores:
                continue
            result = _fetch_price_from_serpapi(item, store_filter=store)
            if result and result["price"] < best_price:
                best_price = result["price"]
                best_option = result

        # If no store-specific result, try any store (but respect avoid list)
        if not best_option:
            result = _fetch_price_from_serpapi(item, store_filter=None)
            if result and result["store"].lower() not in avoid_stores:
                best_option = result

        # Final fallback to mock
        if not best_option:
            # Pick first non-avoided store
            fallback_store = next((s for s in STORE_PRIORITY if s.lower() not in avoid_stores), "Walmart")
            best_option = mock_price_lookup(item, fallback_store)

        basket[item] = best_option
        total += best_option["price"]

    return {"basket": basket, "total_cost": round(total, 2)}