"""
Assistant State Definition for LangGraph.
Defines the schema for data flowing through the assistant's graph.
"""

import uuid
from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AssistantState(TypedDict):
    """
    Standard LangGraph state for the assistant.
    - messages: A list of standard LangChain messages (HumanMessage, AIMessage, etc.).
                The `add_messages` reducer handles appending and deduplication.
    - intent_name: Custom metadata to track the routed intent.
    - confidence: Confidence score for the routed intent.
    - user_id: The ID of the user interacting with the assistant.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    intent_name: str | None
    confidence: float | None
    user_id: uuid.UUID | None
