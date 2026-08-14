"""App version comparison and upgrade policy.

Dotted version labels are parsed to a tuple of integers and compared
numerically, never lexically -- ``"9.0" < "10.0"`` as strings is
``False``; as versions it must be ``True``. Mobile app versions are not
guaranteed to be 3-part semver (Android ``versionName`` is often just
``"3.4"``), so parsing accepts any positive number of dotted parts
rather than requiring exactly three.
"""

from __future__ import annotations


def parse_version(label: str) -> tuple[int, ...]:
    """Parse a dotted version label into a tuple of its integer parts.

    Raises:
        ValueError: If *label* has no parts, or any part is not a
            non-negative integer.
    """
    parts = label.split(".")
    if not parts or any(not part for part in parts):
        raise ValueError(f"{label!r} is not a valid dotted version label.")
    try:
        numbers = tuple(int(part) for part in parts)
    except ValueError as exc:
        raise ValueError(f"{label!r} is not a valid dotted version label.") from exc
    if any(number < 0 for number in numbers):
        raise ValueError(f"{label!r} has a negative version part, which is not allowed.")
    return numbers


def compare_versions(a: str, b: str) -> int:
    """Return -1 if *a* < *b*, 0 if equal, 1 if *a* > *b*, comparing
    part-by-part and treating a missing trailing part as ``0``
    (``"1.2" == "1.2.0"``)."""
    left = parse_version(a)
    right = parse_version(b)
    length = max(len(left), len(right))
    left = left + (0,) * (length - len(left))
    right = right + (0,) * (length - len(right))
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


def is_below_minimum(current: str, minimum: str) -> bool:
    """Whether *current* is strictly below the platform's own
    *minimum* -- the forced-upgrade threshold."""
    return compare_versions(current, minimum) < 0


def is_update_recommended(current: str, recommended: str) -> bool:
    """Whether *current* is strictly below the platform's own
    *recommended* version -- an update-available nudge, not a block."""
    return compare_versions(current, recommended) < 0


__all__ = [
    "compare_versions",
    "is_below_minimum",
    "is_update_recommended",
    "parse_version",
]
