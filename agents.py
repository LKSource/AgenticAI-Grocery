# agents.py
import os
import json
import re
from typing import List, Dict, Any
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from tools import find_best_basket

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-pro-latest",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0
)

KNOWN_ITEMS = {
    "milk", "eggs", "bread", "coffee", "bananas", "tomatoes", "rice", "pasta",
    "cheese", "chicken", "apple", "orange", "yogurt", "butter", "sugar", "salt",
    "lettuce", "carrot", "potato", "onion"
}

def parse_grocery_list(state: Dict[str, Any]) -> Dict[str, Any]:
    messages = state["messages"]
    last_human = [m for m in messages if isinstance(m, HumanMessage)][-1].content
    current_list = state.get("grocery_list", [])
    current_budget = state.get("budget")
    current_avoid = state.get("avoid_stores", [])

    lower_msg = last_human.lower()
    words = lower_msg.split()

    # Start with current state
    new_list = current_list.copy()
    new_avoid = current_avoid.copy()
    new_budget = current_budget

    # Handle "avoid store"
    store_map = {"walmart": "Walmart", "amazon": "Amazon Fresh", "instacart": "Instacart", "kroger": "Kroger"}
    for key, full in store_map.items():
        if f"avoid {key}" in lower_msg and full not in new_avoid:
            new_avoid.append(full)

    # Handle "remove/delete item"
    if "remove" in words or "delete" in words:
        for item in current_list:
            if item in words:
                if item in new_list:
                    new_list.remove(item)

    # Handle "add item(s)"
    if "add" in words:
        try:
            add_idx = words.index("add")
            candidates = words[add_idx + 1:]
            for cand in candidates:
                if cand in ["and", "or", "the", "some", "a", "an", "."]:
                    continue
                if cand and cand not in new_list:
                    if any(kw in cand for kw in KNOWN_ITEMS):
                        new_list.append(cand)
        except ValueError:
            pass

    # If message does NOT contain feedback keywords, treat as NEW LIST
    feedback_keywords = {"avoid", "remove", "delete", "add"}
    if not any(kw in lower_msg for kw in feedback_keywords):
        # Parse as new grocery list
        prompt = ChatPromptTemplate.from_messages([
            ("system", """
You are a grocery assistant. Return ONLY JSON like: {{"items": ["milk", "eggs"], "budget": 20.0}}
If no budget, omit it. If no items, return {{"items": []}}.
            """.strip()),
            ("human", "{input}")
        ])
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({"input": last_human})

        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                extracted = [item.strip().lower() for item in data.get("items", [])]
                valid_items = [item for item in extracted if any(kw in item for kw in KNOWN_ITEMS)]
                if valid_items:
                    new_list = valid_items
                new_budget = data.get("budget", current_budget)
            except:
                pass

    final_budget = float(new_budget) if new_budget is not None else current_budget

    return {
        "grocery_list": new_list,
        "budget": final_budget,
        "avoid_stores": new_avoid
    }


def optimize_basket(state: Dict[str, Any]) -> Dict[str, Any]:
    grocery_list = state.get("grocery_list", [])
    avoid = state.get("avoid_stores", [])
    if not grocery_list:
        return {"current_basket": {}, "total_cost": 0.0}
    result = find_best_basket(grocery_list, avoid_stores=avoid)
    return {
        "current_basket": result["basket"],
        "total_cost": result["total_cost"]
    }


def generate_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    basket = state["current_basket"]
    total = state["total_cost"]
    budget = state.get("budget")

    if not basket:
        msg = "No items to display. Please provide a grocery list (e.g., 'milk, eggs, bread')."
    else:
        lines = [f"🛒 **Optimized Grocery Basket** — Total: **${total:.2f}**"]
        if budget is not None:
            if total > budget:
                overage = total - budget
                lines.append(f"⚠️ **Over budget by ${overage:.2f}!**")
                if basket:
                    costliest = max(basket.items(), key=lambda x: x[1]["price"])
                    item_name = costliest[0].title()
                    save = costliest[1]["price"]
                    lines.append(f"💡 Suggestion: Remove **{item_name}** (${save:.2f}) → new total: ${total - save:.2f}")
            else:
                lines.append("✅ Within budget! Great choice.")
        lines.append("")
        for item, info in basket.items():
            lines.append(f"• **{item.title()}**: ${info['price']:.2f} at {info['store']}")
        lines.append("\nNeed changes? Try:\n- 'Avoid Walmart'\n- 'Remove bread'\n- 'Add bananas'")
        msg = "\n".join(lines)

    return {"messages": state["messages"] + [AIMessage(content=msg)]}


def should_continue(state: Dict[str, Any]) -> str:
    messages = state["messages"]
    # Only continue if last message is Human AND we have an AI summary before it
    if len(messages) >= 2 and isinstance(messages[-1], HumanMessage):
        # Check if previous was AI (summary)
        if isinstance(messages[-2], AIMessage):
            return "process_feedback"
    return "__end__"

def process_feedback(state: Dict[str, Any]) -> Dict[str, Any]:
    last_msg = state["messages"][-1].content.lower()
    words = last_msg.split()
    
    # Start from current state
    grocery_list = state.get("grocery_list", []).copy()
    avoid_stores = state.get("avoid_stores", []).copy()

    # 1. Handle "avoid [store]"
    store_map = {
        "walmart": "Walmart",
        "amazon": "Amazon Fresh",
        "instacart": "Instacart",
        "kroger": "Kroger"
    }
    for key, full_name in store_map.items():
        if f"avoid {key}" in last_msg and full_name not in avoid_stores:
            avoid_stores.append(full_name)

    # 2. Handle "remove X" or "delete X"
    if "remove" in words or "delete" in words:
        # Find all items in grocery list that appear as whole words in message
        for item in grocery_list[:]:  # iterate on copy
            if re.search(rf'\b{re.escape(item)}\b', last_msg):
                grocery_list.remove(item)

    # 3. Handle "add X and Y"
    if "add" in words:
        try:
            add_idx = words.index("add")
            candidates = words[add_idx + 1:]
            # Remove connectors
            for cand in candidates:
                if cand in {"and", "or", "the", "some", "a", "an"}:
                    continue
                # Only add if it's a known grocery item and not already in list
                if cand and cand not in grocery_list:
                    if any(kw in cand for kw in KNOWN_ITEMS):
                        grocery_list.append(cand)
        except ValueError:
            pass  # "add" not found

    # 4. (Optional) Handle "replace X with Y"
    # Example: "replace coffee with tea"
    for item in grocery_list[:]:
        pattern = rf'\breplace\s+{re.escape(item)}\s+with\s+(\w+)'
        match = re.search(pattern, last_msg)
        if match:
            new_item = match.group(1)
            if new_item != item and new_item not in grocery_list:
                if any(kw in new_item for kw in KNOWN_ITEMS):
                    grocery_list.remove(item)
                    grocery_list.append(new_item)
            break

    return {
        "grocery_list": grocery_list,
        "avoid_stores": avoid_stores
        # Note: budget is unchanged in feedback
    }