# tools.py
from typing import List, Dict
import random

STORES = ["Walmart", "Amazon Fresh", "Instacart", "Kroger"]

ITEM_BASE_PRICES = {
    "milk": 3.5, "eggs": 2.8, "bread": 2.2, "bananas": 0.6,
    "chicken breast": 5.99, "rice": 4.0, "pasta": 1.8,
    "tomatoes": 2.5, "cheese": 4.2, "coffee": 8.99,
    "apple": 1.2, "orange": 1.3, "yogurt": 1.5, "butter": 3.0
}

def mock_price_lookup(item: str, store: str) -> Dict[str, float | str]:
    base = ITEM_BASE_PRICES.get(item.lower(), 5.0)
    variation = {"Walmart": 0.95, "Amazon Fresh": 1.1, "Instacart": 1.05, "Kroger": 1.0}.get(store, 1.0)
    price = round(base * variation * (0.95 + random.random() * 0.1), 2)
    return {"item": item, "store": store, "price": price}

def find_best_basket(grocery_list: List[str], avoid_stores: List[str] = None) -> Dict:
    avoid_stores = avoid_stores or []
    basket = {}
    total = 0.0
    for item in grocery_list:
        best_price = float('inf')
        best_option = None
        for store in STORES:
            if store in avoid_stores:
                continue
            option = mock_price_lookup(item, store)
            if option["price"] < best_price:
                best_price = option["price"]
                best_option = option
        if best_option:
            basket[item] = best_option
            total += best_price
    return {"basket": basket, "total_cost": round(total, 2)}