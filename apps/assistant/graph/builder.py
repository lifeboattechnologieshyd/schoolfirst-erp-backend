"""
Graph Builder for the Assistant application.
Defines the nodes and edges for the LangGraph orchestration.
"""

from typing import Any, cast

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from apps.assistant.graph.nodes import generate_title_node, intent_handler_node, intent_router_node
from apps.assistant.graph.state import AssistantState
from apps.assistant.tools import get_all_tools


def build_graph() -> Any:
    """
    Builds and compiles the Assistant LangGraph.

    The graph follows this flow:
    1. START -> Router (Parallel: START -> Generate Title)
    2. Router -> Handler
    3. Handler -> Tools (Conditional: if tool calls are requested)
    4. Tools -> Handler
    5. Handler -> END
    """
    builder = StateGraph(cast(Any, AssistantState))

    # Add Nodes
    builder.add_node("router", intent_router_node)
    builder.add_node("handler", intent_handler_node)
    builder.add_node("generate_title", generate_title_node)

    # Tool node executes the bound tools
    builder.add_node("tools", ToolNode(get_all_tools()))

    # Add Edges
    builder.add_edge(START, "router")
    builder.add_edge("router", "generate_title")
    builder.add_edge("generate_title", END)

    # After router, we always go to the handler (which uses the intent in state)
    builder.add_edge("router", "handler")

    # The handler can either finish (END) or call tools ("tools")
    builder.add_conditional_edges("handler", tools_condition)

    # After tools execute, return to the handler to incorporate the result.
    builder.add_edge("tools", "handler")

    # Compile the graph
    graph = builder.compile()

    return graph
