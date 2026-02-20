import re

IRC_PRIVMSG_PATTERN = re.compile(
    r"^(?:@(?P<tags>[^ ]+) )?:(?P<author>[^!]+)![^ ]+ PRIVMSG #(?P<channel>[^ ]+) :(?P<message>.*)$"
)
IRC_WELCOME_PATTERN = re.compile(r"^:[^ ]+\s001\s", re.IGNORECASE)


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
