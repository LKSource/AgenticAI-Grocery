# main.py
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from state import GroceryState
from agents import (
    parse_grocery_list,
    optimize_basket,
    generate_summary,
    process_feedback,
    should_continue
)
from langchain_core.messages import HumanMessage

load_dotenv()

# Build the stateful, looping workflow
workflow = StateGraph(GroceryState)

# Add all nodes
workflow.add_node("parse_grocery_list", parse_grocery_list)
workflow.add_node("optimize_basket", optimize_basket)
workflow.add_node("generate_summary", generate_summary)
workflow.add_node("process_feedback", process_feedback)

# Define the primary flow
workflow.add_edge(START, "parse_grocery_list")
workflow.add_edge("parse_grocery_list", "optimize_basket")
workflow.add_edge("optimize_basket", "generate_summary")

# Conditional edge: after summary, check if user responded
workflow.add_conditional_edges(
    "generate_summary",
    should_continue,
    {
        "process_feedback": "process_feedback",
        "__end__": END
    }
)

# Feedback loops back to optimization (not parsing!)
workflow.add_edge("process_feedback", "optimize_basket")

# Compile the graph
app = workflow.compile()

if __name__ == "__main__":
    # Initialize clean state
    state = {
        "messages": [],
        "grocery_list": [],
        "budget": None,
        "avoid_stores": [],
        "current_basket": {},
        "total_cost": 0.0
    }

    # Simulate a multi-turn conversation
    conversation = [
        "I need milk, eggs, bread, and coffee. Budget is $12.",
        "Avoid Walmart",
        "Remove coffee",
        "Add bananas and tomatoes"
    ]

    for i, user_msg in enumerate(conversation):
        print(f"\n{'='*60}")
        print(f"👉 TURN {i+1}: User says: \"{user_msg}\"")
        # Append user message
        state["messages"].append(HumanMessage(content=user_msg))
        # Run the graph (it will loop internally if needed)
        state = app.invoke(state)
        
        # Print results
        print(f"\n🤖 Agent Response:")
        print(state["messages"][-1].content)
        print(f"\n📋 Current Grocery List: {state['grocery_list']}")
        print(f"🚫 Avoid Stores: {state['avoid_stores']}")
        print(f"💰 Total Cost: ${state['total_cost']:.2f}")