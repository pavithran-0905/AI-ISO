"""Code generation: typed model and enum stub rendering from a
generator-neutral field/member description.

**Every rendered field's type is looked up, never guessed.** An
unrecognized generator-level type name is a hard `ValueError`, not a
silently emitted `any`/`object` -- a code generator that guesses
produces code that compiles but lies about what it accepts.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.models.enums import SdkLanguage

_PYTHON_TYPES: dict[str, str] = {
    "string": "str",
    "integer": "int",
    "float": "float",
    "boolean": "bool",
    "uuid": "uuid.UUID",
    "datetime": "datetime",
}

_TYPESCRIPT_TYPES: dict[str, str] = {
    "string": "string",
    "integer": "number",
    "float": "number",
    "boolean": "boolean",
    "uuid": "string",
    "datetime": "string",
}

_GO_TYPES: dict[str, str] = {
    "string": "string",
    "integer": "int64",
    "float": "float64",
    "boolean": "bool",
    "uuid": "string",
    "datetime": "time.Time",
}

_TYPE_TABLES: dict[SdkLanguage, dict[str, str]] = {
    SdkLanguage.PYTHON: _PYTHON_TYPES,
    SdkLanguage.TYPESCRIPT: _TYPESCRIPT_TYPES,
    SdkLanguage.GO: _GO_TYPES,
}
"""Java and .NET code generation is not yet implemented -- see this
package's README "Scope boundary"."""


@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    type_name: str


def _validate_identifier(name: str, *, kind: str) -> None:
    if not name or not (name[0].isalpha() or name[0] == "_") or not name.replace("_", "").isalnum():
        raise ValueError(f"{kind} {name!r} is not a valid identifier.")


def _resolve_type(language: SdkLanguage, type_name: str) -> str:
    table = _TYPE_TABLES.get(language)
    if table is None:
        raise ValueError(f"Code generation for {language.value!r} is not supported.")
    resolved = table.get(type_name)
    if resolved is None:
        raise ValueError(f"Unrecognized generator type {type_name!r} for {language.value!r}.")
    return resolved


def render_model(language: SdkLanguage, class_name: str, fields: Sequence[FieldSpec]) -> str:
    """Render a strongly typed model stub in *language*.

    Raises:
        ValueError: On an unsupported language, an empty *fields*, an
            invalid identifier, or an unrecognized field type.
    """
    _validate_identifier(class_name, kind="class name")
    if not fields:
        raise ValueError("fields must not be empty.")
    for field in fields:
        _validate_identifier(field.name, kind="field name")

    if language == SdkLanguage.PYTHON:
        lines = [f"class {class_name}:"]
        for field in fields:
            lines.append(f"    {field.name}: {_resolve_type(language, field.type_name)}")
        return "\n".join(lines)

    if language == SdkLanguage.TYPESCRIPT:
        lines = [f"export interface {class_name} {{"]
        for field in fields:
            lines.append(f"  {field.name}: {_resolve_type(language, field.type_name)};")
        lines.append("}")
        return "\n".join(lines)

    if language == SdkLanguage.GO:
        lines = [f"type {class_name} struct {{"]
        for field in fields:
            go_field = field.name[:1].upper() + field.name[1:]
            lines.append(f"\t{go_field} {_resolve_type(language, field.type_name)}")
        lines.append("}")
        return "\n".join(lines)

    raise ValueError(f"Code generation for {language.value!r} is not supported.")


def render_enum(language: SdkLanguage, enum_name: str, members: Sequence[str]) -> str:
    """Render an enumeration stub in *language*.

    Raises:
        ValueError: On an unsupported language, an empty *members*, or
            an invalid identifier.
    """
    _validate_identifier(enum_name, kind="enum name")
    if not members:
        raise ValueError("members must not be empty.")
    for member in members:
        _validate_identifier(member, kind="enum member")

    if language == SdkLanguage.PYTHON:
        lines = [f"class {enum_name}(str, Enum):"]
        for member in members:
            lines.append(f'    {member.upper()} = "{member}"')
        return "\n".join(lines)

    if language == SdkLanguage.TYPESCRIPT:
        lines = [f"export enum {enum_name} {{"]
        for member in members:
            lines.append(f'  {member.upper()} = "{member}",')
        lines.append("}")
        return "\n".join(lines)

    if language == SdkLanguage.GO:
        lines = [f"type {enum_name} string", "", "const ("]
        for member in members:
            lines.append(f'\t{enum_name}{member.title().replace("_", "")} {enum_name} = "{member}"')
        lines.append(")")
        return "\n".join(lines)

    raise ValueError(f"Code generation for {language.value!r} is not supported.")


__all__ = ["FieldSpec", "render_enum", "render_model"]
