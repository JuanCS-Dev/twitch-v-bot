from typing import Any


def is_owner(user_id: str, owner_id: str) -> bool:
    return str(user_id) == str(owner_id)


def is_moderator(author: Any) -> bool:
    return bool(getattr(author, "is_mod", False)) or bool(getattr(author, "is_moderator", False))


def is_trusted_curator(author: Any, owner_id: str) -> bool:
    return is_owner(getattr(author, "id", ""), owner_id) or is_moderator(author)
