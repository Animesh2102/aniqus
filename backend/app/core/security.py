from typing import List

ROLE_PERMISSIONS = {
    "executive": ["all", "engineering", "hr", "sales", "executive"],
    "hr": ["all", "hr"],
    "engineering": ["all", "engineering"],
    "sales": ["all", "sales"],
    "general": ["all"]
}

def get_allowed_access_levels(role: str) -> List[str]:
    """Resolves a user role into the list of document access levels they are permitted to view."""
    role_clean = role.lower().strip()
    return ROLE_PERMISSIONS.get(role_clean, ["all"])

def is_role_permitted(user_role: str, document_access_level: str) -> bool:
    """Checks whether a user role has access to a specific document classification."""
    allowed = get_allowed_access_levels(user_role)
    return document_access_level.lower().strip() in allowed
