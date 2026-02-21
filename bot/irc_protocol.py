import re

IRC_PRIVMSG_PATTERN = re.compile(
    r"^(?:@(?P<tags>[^ ]+) )?:(?P<author>[^!]+)![^ ]+ PRIVMSG #(?P<channel>[^ ]+) :(?P<message>.*)$"
)
IRC_NOTICE_PATTERN = re.compile(
    r"^(?:@(?P<tags>[^ ]+) )?:[^ ]+ NOTICE (?P<target>[^ ]+) :(?P<message>.*)$",
    re.IGNORECASE,
)
IRC_JOIN_PATTERN = re.compile(
    r"^(?:@(?P<tags>[^ ]+) )?:(?P<author>[^!]+)![^ ]+ JOIN #(?P<channel>[^ ]+)$",
    re.IGNORECASE,
)
IRC_PART_PATTERN = re.compile(
    r"^(?:@(?P<tags>[^ ]+) )?:(?P<author>[^!]+)![^ ]+ PART #(?P<channel>[^ ]+)(?: :(?P<reason>.*))?$",
    re.IGNORECASE,
)
IRC_WELCOME_PATTERN = re.compile(r"^:[^ ]+\s001\s", re.IGNORECASE)
IRC_NOTICE_DELIVERY_BLOCK_IDS = {
    "msg_bad_characters",
    "msg_banned",
    "msg_channel_blocked",
    "msg_channel_suspended",
    "msg_duplicate",
    "msg_emoteonly",
    "msg_followersonly",
    "msg_followersonly_followed",
    "msg_r9k",
    "msg_requires_verified_phone_number",
    "msg_slowmode",
    "msg_subsonly",
    "msg_suspended",
    "msg_timedout",
}
IRC_NOTICE_DELIVERY_BLOCK_HINTS = (
    "banned",
    "followers-only",
    "followers only",
    "phone number must be verified",
    "requires a verified phone number",
    "room is no longer available",
    "subscribers-only",
    "subscribers only",
    "timed out",
    "you are permanently banned",
)


class IrcAuthor:
    def __init__(self, login: str, tags: dict[str, str]) -> None:
        self.login = login
        self.name = tags.get("display-name") or login
        self.id = tags.get("user-id", "")
        is_mod = tags.get("mod") == "1" or "moderator/" in tags.get("badges", "")
        self.is_mod = is_mod
        self.is_moderator = is_mod


class IrcMessageAdapter:
    def __init__(self, text: str, author: IrcAuthor) -> None:
        self.text = text
        self.author = author
        self.echo = False


def parse_irc_tags(raw_tags: str) -> dict[str, str]:
    if not raw_tags:
        return {}
    parsed: dict[str, str] = {}
    for item in raw_tags.split(";"):
        if "=" in item:
            key, value = item.split("=", maxsplit=1)
        else:
            key, value = item, ""
        parsed[key] = value.replace(r"\s", " ").replace(r"\:", ";").replace(r"\\", "\\")
    return parsed


def flatten_chat_text(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return " | ".join(lines)


def is_irc_notice_delivery_block(msg_id: str, message: str) -> bool:
    normalized_id = (msg_id or "").strip().lower()
    if normalized_id in IRC_NOTICE_DELIVERY_BLOCK_IDS:
        return True

    lowered_message = (message or "").strip().lower()
    return any(marker in lowered_message for marker in IRC_NOTICE_DELIVERY_BLOCK_HINTS)
