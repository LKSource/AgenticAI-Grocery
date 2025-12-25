# state.py
from typing import List, Optional, TypedDict
from langchain_core.messages import BaseMessage

class GroceryState(TypedDict):
    messages: List[BaseMessage]
    grocery_list: List[str]
    budget: Optional[float]
    avoid_stores: List[str]
    current_basket: dict
    total_cost: float