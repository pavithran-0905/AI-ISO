"""Tests for app.generator.engine: typed model and enum stub
rendering."""

from __future__ import annotations

import pytest

from app.generator.engine import FieldSpec, render_enum, render_model
from app.models.enums import SdkLanguage


class TestRenderModel:
    def test_python_model(self) -> None:
        source = render_model(
            SdkLanguage.PYTHON, "User", [FieldSpec("id", "uuid"), FieldSpec("name", "string")]
        )
        assert "class User:" in source
        assert "id: uuid.UUID" in source
        assert "name: str" in source

    def test_typescript_model(self) -> None:
        source = render_model(SdkLanguage.TYPESCRIPT, "User", [FieldSpec("id", "uuid")])
        assert "export interface User {" in source
        assert "id: string;" in source

    def test_go_model(self) -> None:
        source = render_model(SdkLanguage.GO, "User", [FieldSpec("id", "uuid")])
        assert "type User struct {" in source
        assert "Id string" in source

    def test_unsupported_language_raises(self) -> None:
        with pytest.raises(ValueError, match="not supported"):
            render_model(SdkLanguage.DOTNET, "User", [FieldSpec("id", "uuid")])

    def test_empty_fields_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            render_model(SdkLanguage.PYTHON, "User", [])

    def test_invalid_class_name_raises(self) -> None:
        with pytest.raises(ValueError, match="not a valid identifier"):
            render_model(SdkLanguage.PYTHON, "123User", [FieldSpec("id", "uuid")])

    def test_invalid_field_name_raises(self) -> None:
        with pytest.raises(ValueError, match="not a valid identifier"):
            render_model(SdkLanguage.PYTHON, "User", [FieldSpec("1id", "uuid")])

    def test_unrecognized_field_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unrecognized generator type"):
            render_model(SdkLanguage.PYTHON, "User", [FieldSpec("id", "not_a_type")])


class TestRenderEnum:
    def test_python_enum(self) -> None:
        source = render_enum(SdkLanguage.PYTHON, "Status", ["active", "inactive"])
        assert 'ACTIVE = "active"' in source

    def test_typescript_enum(self) -> None:
        source = render_enum(SdkLanguage.TYPESCRIPT, "Status", ["active"])
        assert "export enum Status {" in source

    def test_go_enum(self) -> None:
        source = render_enum(SdkLanguage.GO, "Status", ["active"])
        assert "type Status string" in source

    def test_unsupported_language_raises(self) -> None:
        with pytest.raises(ValueError, match="not supported"):
            render_enum(SdkLanguage.JAVA, "Status", ["active"])

    def test_empty_members_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            render_enum(SdkLanguage.PYTHON, "Status", [])

    def test_invalid_member_name_raises(self) -> None:
        with pytest.raises(ValueError, match="not a valid identifier"):
            render_enum(SdkLanguage.PYTHON, "Status", ["1active"])
