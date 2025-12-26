# app.py
import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
import re
import random
from typing import Tuple

# ===== MOCK PRICING ENGINE =====
STORES = ["Walmart", "Amazon Fresh", "Instacart", "Kroger"]
ITEM_BASE_PRICES = {
    "milk": 3.5, "eggs": 2.8, "bread": 2.2, "bananas": 0.6,
    "chicken breast": 5.99, "rice": 4.0, "pasta": 1.8,
    "tomatoes": 2.5, "cheese": 4.2, "coffee": 8.99,
    "apple": 1.2, "orange": 1.3, "yogurt": 1.5, "butter": 3.0
}

def get_mock_price(item: str, store: str) -> float:
    """Get mock price with store variation"""
    base = ITEM_BASE_PRICES.get(item.lower(), 5.0)
    variation = {"Walmart": 0.95, "Amazon Fresh": 1.1, "Instacart": 1.05, "Kroger": 1.0}.get(store, 1.0)
    return round(base * variation * (0.95 + random.random() * 0.1), 2)

def find_best_prices(items: list, avoid_stores: list = None) -> dict:
    """Find best prices for items, avoiding specified stores"""
    avoid_stores = avoid_stores or []
    basket = {}
    total = 0.0
    
    for item in items:
        best_price = float('inf')
        best_store = None
        
        for store in STORES:
            if store in avoid_stores:
                continue
            price = get_mock_price(item, store)
            if price < best_price:
                best_price = price
                best_store = store
        
        if best_store:
            basket[item] = {"price": best_price, "store": best_store}
            total += best_price
    
    return {"basket": basket, "total_cost": round(total, 2)}

# ===== COMMAND PROCESSOR =====
KNOWN_ITEMS = [
    "milk", "eggs", "bread", "coffee", "bananas", "tomatoes", "rice", "pasta",
    "cheese", "chicken", "chicken breast", "apple", "orange", "yogurt", "butter"
]

def process_user_input(user_msg: str, current_state: dict) -> dict:
    """Process user input and update state"""
    msg_lower = user_msg.lower()
    new_state = current_state.copy()
    
    # Extract budget if mentioned
    budget_match = re.search(r'\$?(\d+\.?\d*)\s*(?:budget|dollars|total)?', msg_lower)
    if budget_match:
        new_state["budget"] = float(budget_match.group(1))
    
    # Handle commands
    if "avoid" in msg_lower:
        if "walmart" in msg_lower:
            if "Walmart" not in new_state["avoid_stores"]:
                new_state["avoid_stores"].append("Walmart")
        if "amazon" in msg_lower:
            if "Amazon Fresh" not in new_state["avoid_stores"]:
                new_state["avoid_stores"].append("Amazon Fresh")
        if "kroger" in msg_lower:
            if "Kroger" not in new_state["avoid_stores"]:
                new_state["avoid_stores"].append("Kroger")
        if "instacart" in msg_lower:
            if "Instacart" not in new_state["avoid_stores"]:
                new_state["avoid_stores"].append("Instacart")
    
    if "remove" in msg_lower or "delete" in msg_lower:
        for item in new_state["grocery_list"][:]:  # iterate on copy
            if item.lower() in msg_lower:
                new_state["grocery_list"].remove(item)
    
    if "add" in msg_lower:
        # Extract items after "add"
        add_part = msg_lower.split("add", 1)[-1].strip()
        # Simple extraction - look for known items
        for item in KNOWN_ITEMS:
            if item in add_part and item not in new_state["grocery_list"]:
                new_state["grocery_list"].append(item)
    
    # If no commands and seems like a new list, extract items
    is_command = any(cmd in msg_lower for cmd in ["avoid", "remove", "delete", "add", "replace"])
    if not is_command:
        new_items = []
        for item in KNOWN_ITEMS:
            if item in msg_lower and item not in new_state["grocery_list"]:
                new_items.append(item)
        
        # Only replace list if we found items
        if new_items:
            new_state["grocery_list"] = new_items
    
    return new_state

def generate_response(state: dict) -> Tuple[str, dict]:
    """Generate AI response based on current state"""
    new_state = state.copy()
    if not state["grocery_list"]:
        return "🛒 No items in your basket yet. Try adding items like 'I need milk, eggs, and bread' or 'Add coffee'"
    
    # Calculate basket
    basket_result = find_best_prices(state["grocery_list"], state["avoid_stores"])
    basket = basket_result["basket"]
    total = basket_result["total_cost"]
    budget = state["budget"]
    new_state["current_basket"] = basket 
    new_state["total_cost"] = total
    # Build response
    lines = [f"🛒 **Optimized Grocery Basket** — Total: **${total:.2f}**"]
    
    if budget is not None:
        if total > budget:
            overage = total - budget
            lines.append(f"⚠️ **Over budget by ${overage:.2f}!**")
            # Find most expensive item
            if basket:
                costliest_item = max(basket.items(), key=lambda x: x[1]["price"])
                item_name = costliest_item[0].title()
                save_amount = costliest_item[1]["price"]
                lines.append(f"💡 Suggestion: Remove **{item_name}** (${save_amount:.2f}) → new total: ${total - save_amount:.2f}")
        else:
            lines.append("✅ Within budget! Great choice.")
    
    lines.append("")
    for item, info in basket.items():
        lines.append(f"• **{item.title()}**: ${info['price']:.2f} at {info['store']}")
        lines.append("\n")
    
    lines.append("\nNeed changes? Try:\n- 'Avoid Walmart'\n- 'Remove coffee'\n- 'Add bananas'")
    
    return "\n".join(lines), new_state

# ===== STREAMLIT APP =====
st.set_page_config(page_title="🛒 Grocery Agent", page_icon="🛒", layout="wide")
st.title("🛒 Smart Grocery Agent (Working Version)")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "grocery_list" not in st.session_state:
    st.session_state.grocery_list = []
if "budget" not in st.session_state:
    st.session_state.budget = None
if "avoid_stores" not in st.session_state:
    st.session_state.avoid_stores = []
if "current_basket" not in st.session_state:
    st.session_state.current_basket = {}
if "total_cost" not in st.session_state:
    st.session_state.total_cost = None

# Display chat history
for message in st.session_state.messages:
    with st.chat_message("human" if isinstance(message, HumanMessage) else "ai"):
        st.write(message.content)

# User input
if prompt := st.chat_input("What groceries do you need?"):
    # Add user message
    st.session_state.messages.append(HumanMessage(content=prompt))
    with st.chat_message("human"):
        st.write(prompt)
    
    # Process input and update state
    current_state = {
        "grocery_list": st.session_state.grocery_list.copy(),
        "budget": st.session_state.budget,
        "avoid_stores": st.session_state.avoid_stores.copy()
    }
    
    new_state = process_user_input(prompt, current_state)
    
    # Update session state
    st.session_state.grocery_list = new_state["grocery_list"]
    st.session_state.budget = new_state["budget"]
    st.session_state.avoid_stores = new_state["avoid_stores"]
    
    # Generate response
    response, new_state = generate_response(new_state)
    st.session_state.messages.append(AIMessage(content=response))
    st.session_state.current_basket = new_state["current_basket"]
    st.session_state.total_cost = new_state["total_cost"]
    
    # Display AI response
    with st.chat_message("ai"):
        st.write(response)

# Sidebar with current state
with st.sidebar:
    st.subheader("🛒 Current Basket")
    if st.session_state.grocery_list:
        #basket_result = find_best_prices(st.session_state.grocery_list, st.session_state.avoid_stores)
        #st.session_state.current_basket = basket_result["basket"]
        basket_result = st.session_state.current_basket
        total_cost = st.session_state.total_cost
        for item, info in basket_result.items():
            st.write(f"• **{item.title()}**: ${info['price']:.2f} at {info['store']}")
        st.write(f"**Total: ${total_cost:.2f}**")
        if st.session_state.budget:
            st.write(f"Budget: ${st.session_state.budget:.2f}")
    else:
        st.write("Empty basket")

    st.subheader("📋 Grocery List")
    st.write(", ".join(st.session_state.grocery_list) if st.session_state.grocery_list else "None")

    st.subheader("🚫 Avoid Stores")
    st.write(", ".join(st.session_state.avoid_stores) if st.session_state.avoid_stores else "None")

    if st.button("🔄 Reset Conversation"):
        st.session_state.messages = []
        st.session_state.grocery_list = []
        st.session_state.budget = None
        st.session_state.avoid_stores = []
        st.session_state.current_basket = {}
        st.session_state.total_cost = None
        st.rerun()