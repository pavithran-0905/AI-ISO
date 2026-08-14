"""Tests for app.cli.profiles.engine: default-profile selection."""

from __future__ import annotations

from uuid import uuid4

from app.cli.profiles.engine import profiles_to_unset


class TestProfilesToUnset:
    def test_unsets_every_other_default(self) -> None:
        a, b, c = uuid4(), uuid4(), uuid4()
        assert set(profiles_to_unset([a, b], new_default_id=c)) == {a, b}

    def test_excludes_the_new_default_even_if_present(self) -> None:
        a = uuid4()
        assert profiles_to_unset([a], new_default_id=a) == []

    def test_empty_existing_defaults_unsets_nothing(self) -> None:
        assert profiles_to_unset([], new_default_id=uuid4()) == []
