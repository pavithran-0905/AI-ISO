"""Deep link construction and parsing.

One consistent URI shape for every link category:
``{base_url}/link/{category}/{resource_id}``. Building and parsing are
exact inverses of each other by construction, which is what every
notification and report that embeds a link, and every client that
opens one, relies on.
"""

from __future__ import annotations

from app.models.enums import DeepLinkCategory

_SEGMENT = "link"
_EXPECTED_PART_COUNT = 2


def build_deep_link(category: DeepLinkCategory, *, resource_id: str, base_url: str) -> str:
    """Build a deep link URI for *resource_id* in *category*.

    Raises:
        ValueError: If *resource_id* is empty or contains a path
            separator (which would make the link ambiguous to parse
            back).
    """
    if not resource_id or "/" in resource_id:
        raise ValueError(f"{resource_id!r} is not a valid deep-link resource id.")
    category = DeepLinkCategory(category)
    return f"{base_url.rstrip('/')}/{_SEGMENT}/{category.value}/{resource_id}"


def parse_deep_link(url: str, *, base_url: str) -> tuple[DeepLinkCategory, str]:
    """Parse a deep link URI built by :func:`build_deep_link` back into
    its category and resource id.

    Raises:
        ValueError: If *url* does not match the expected shape.
    """
    prefix = f"{base_url.rstrip('/')}/{_SEGMENT}/"
    if not url.startswith(prefix):
        raise ValueError(f"{url!r} is not a recognized deep link for {base_url!r}.")
    remainder = url[len(prefix) :]
    parts = remainder.split("/")
    if len(parts) != _EXPECTED_PART_COUNT or not parts[0] or not parts[1]:
        raise ValueError(f"{url!r} is not a well-formed deep link.")
    category_raw, resource_id = parts
    try:
        category = DeepLinkCategory(category_raw)
    except ValueError as exc:
        raise ValueError(f"{category_raw!r} is not a recognized deep link category.") from exc
    return category, resource_id


__all__ = ["build_deep_link", "parse_deep_link"]
