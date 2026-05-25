from typing import Any

from .add_close_group_member import add_close_group_member
from .create_family import create_family
from .find_family_member import find_family_member
from .get_birthday_reminders import get_birthday_reminders
from .get_close_group_members import get_close_group_members
from .get_family_members import get_family_members
from .get_my_families import get_my_families
from .get_my_network_summary import get_my_network_summary
from .get_my_profile import get_my_profile
from .get_network_insights import get_network_insights
from .get_pending_invitations import get_pending_invitations
from .invite_family_member import invite_family_member
from .search_accessible_docusafe import search_accessible_docusafe
from .search_docusafe import search_docusafe
from .update_my_profile import update_my_profile
from .user_details import fetch_user_details
from .web_search import web_search

_ALL_TOOLS = (
    web_search,
    fetch_user_details,
    search_docusafe,
    search_accessible_docusafe,
    get_my_profile,
    update_my_profile,
    get_my_families,
    get_family_members,
    get_pending_invitations,
    find_family_member,
    create_family,
    invite_family_member,
    get_close_group_members,
    add_close_group_member,
    get_my_network_summary,
    get_network_insights,
    get_birthday_reminders,
)


def get_all_tools() -> list[Any]:
    return list(_ALL_TOOLS)


def get_tool_map() -> dict[str, object]:
    return {tool.name: tool for tool in _ALL_TOOLS}
