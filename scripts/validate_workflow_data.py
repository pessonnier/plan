#!/usr/bin/env python3
"""Validate workflow data files against schema/workflow-model.json."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from workflow_data import (
    WorkflowDataError,
    is_manifest,
    load_data_source,
    load_json,
    load_manifest,
    schema_path_from_manifest,
)


MERMAID_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SAFE_INTERNAL_LINK = re.compile(r"^(?:phases|states)/[A-Za-z0-9_-]+\.html$")
SAFE_EXTERNAL_LINK = re.compile(r"^https?://", re.IGNORECASE)


class DataValidationError(ValueError):
    """Raised when records are incompatible with the workflow model."""


def schema_definitions(schema: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    tables = schema.get("tables")
    if not isinstance(tables, list) or not tables:
        raise DataValidationError("Le schéma doit contenir une liste 'tables'.")

    definitions: dict[str, Mapping[str, Any]] = {}
    for table in tables:
        if not isinstance(table, Mapping) or not isinstance(table.get("name"), str):
            raise DataValidationError("Chaque table du schéma doit avoir un nom.")
        name = table["name"]
        if name in definitions:
            raise DataValidationError(f"Table dupliquée dans le schéma: {name}")
        definitions[name] = table
    return definitions


def validate_field_type(value: Any, field: Mapping[str, Any], context: str) -> None:
    field_type = field.get("type")
    valid = False
    if field_type in {"text", "long_text", "choice", "reference"}:
        valid = isinstance(value, str)
    elif field_type == "boolean":
        valid = isinstance(value, bool)
    elif field_type == "number":
        valid = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif field_type == "datetime":
        valid = isinstance(value, str)
        if valid:
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                valid = False
    else:
        raise DataValidationError(f"{context}: type de schéma inconnu {field_type!r}.")

    if not valid:
        raise DataValidationError(
            f"{context}: valeur incompatible avec le type {field_type}: {value!r}"
        )

    choices = field.get("values")
    if field_type == "choice" and isinstance(choices, list) and value not in choices:
        raise DataValidationError(
            f"{context}: valeur {value!r} absente des choix autorisés {choices!r}."
        )


def validate_records_against_schema(
    document: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    require_all_tables: bool = True,
) -> None:
    definitions = schema_definitions(schema)
    unknown_tables = set(document) - set(definitions)
    if unknown_tables:
        raise DataValidationError(
            f"Tables absentes du modèle: {', '.join(sorted(unknown_tables))}."
        )

    if require_all_tables:
        missing_tables = set(definitions) - set(document)
        if missing_tables:
            raise DataValidationError(
                f"Tables manquantes dans le jeu assemblé: "
                f"{', '.join(sorted(missing_tables))}."
            )

    for table_name, records in document.items():
        if not isinstance(records, list):
            raise DataValidationError(f"{table_name} doit être une liste.")
        table = definitions[table_name]
        fields = table.get("fields")
        if not isinstance(fields, list):
            raise DataValidationError(
                f"Le schéma de {table_name} doit contenir une liste fields."
            )
        field_map = {
            field["name"]: field
            for field in fields
            if isinstance(field, Mapping) and isinstance(field.get("name"), str)
        }

        for index, record in enumerate(records):
            context = f"{table_name}[{index}]"
            if not isinstance(record, Mapping):
                raise DataValidationError(f"{context} doit être un objet.")
            unknown_fields = set(record) - set(field_map)
            if unknown_fields:
                raise DataValidationError(
                    f"{context}: champs absents du modèle: "
                    f"{', '.join(sorted(unknown_fields))}."
                )
            for field_name, field in field_map.items():
                if field.get("required") is True and field_name not in record:
                    raise DataValidationError(
                        f"{context}: champ obligatoire manquant {field_name}."
                    )
                if field_name in record:
                    validate_field_type(
                        record[field_name], field, f"{context}.{field_name}"
                    )
                    if field_name.endswith("_id") and not MERMAID_ID.fullmatch(
                        record[field_name]
                    ):
                        raise DataValidationError(
                            f"{context}.{field_name}: identifiant incompatible "
                            f"avec Mermaid {record[field_name]!r}."
                        )


def validate_references(
    document: Mapping[str, Any], schema: Mapping[str, Any]
) -> None:
    definitions = schema_definitions(schema)
    referenced_columns: set[tuple[str, str]] = set()
    reference_fields: list[tuple[str, Mapping[str, Any]]] = []

    for table_name, table in definitions.items():
        fields = table.get("fields", [])
        if fields and isinstance(fields[0], Mapping):
            primary_field = fields[0].get("name")
            if isinstance(primary_field, str):
                referenced_columns.add((table_name, primary_field))
        for field in fields:
            if isinstance(field, Mapping) and field.get("type") == "reference":
                reference = field.get("references")
                if not isinstance(reference, str) or "." not in reference:
                    raise DataValidationError(
                        f"Référence invalide dans le schéma: "
                        f"{table_name}.{field.get('name')}."
                    )
                target_table, target_field = reference.split(".", 1)
                referenced_columns.add((target_table, target_field))
                reference_fields.append((table_name, field))

    indexes: dict[tuple[str, str], set[Any]] = {}
    for table_name, field_name in referenced_columns:
        values: set[Any] = set()
        for index, record in enumerate(document.get(table_name, [])):
            value = record.get(field_name)
            if value in values:
                raise DataValidationError(
                    f"{table_name}[{index}].{field_name}: identifiant dupliqué "
                    f"{value!r}."
                )
            values.add(value)
        indexes[(table_name, field_name)] = values

    for table_name, field in reference_fields:
        field_name = field["name"]
        target_table, target_field = field["references"].split(".", 1)
        valid_values = indexes[(target_table, target_field)]
        for index, record in enumerate(document.get(table_name, [])):
            if field_name not in record:
                continue
            value = record[field_name]
            if value not in valid_values:
                raise DataValidationError(
                    f"{table_name}[{index}].{field_name}: référence introuvable "
                    f"{value!r} dans {target_table}.{target_field}."
                )


def validate_business_consistency(document: Mapping[str, Any]) -> None:
    states = {record["etat_id"]: record for record in document.get("Etat", [])}
    transitions = {
        record["transition_id"]: record for record in document.get("Transition", [])
    }
    for index, transition in enumerate(document.get("Transition", [])):
        workflow_id = transition["workflow_id"]
        source = states[transition["etat_source_id"]]
        target = states[transition["etat_cible_id"]]
        if source["workflow_id"] != workflow_id or target["workflow_id"] != workflow_id:
            raise DataValidationError(
                f"Transition[{index}] relie des états appartenant à un autre workflow."
            )

    for index, rule in enumerate(document.get("Regle", [])):
        workflow_id = rule["workflow_id"]
        if "etat_id" in rule and states[rule["etat_id"]]["workflow_id"] != workflow_id:
            raise DataValidationError(
                f"Regle[{index}].etat_id appartient à un autre workflow."
            )
        if (
            "transition_id" in rule
            and transitions[rule["transition_id"]]["workflow_id"] != workflow_id
        ):
            raise DataValidationError(
                f"Regle[{index}].transition_id appartient à un autre workflow."
            )

    for table_name in ("Etat", "Transition"):
        for index, record in enumerate(document.get(table_name, [])):
            link_type = record.get("type_lien")
            target = record.get("cible_lien")
            label = record.get("libelle_lien")
            link_fields_present = any(
                value is not None for value in (link_type, target, label)
            )
            if not link_fields_present:
                continue
            if not all(isinstance(value, str) and value for value in (link_type, target)):
                raise DataValidationError(
                    f"{table_name}[{index}]: type_lien et cible_lien sont "
                    "obligatoires lorsqu'un lien est défini."
                )
            if link_type == "page_phase" and not (
                SAFE_INTERNAL_LINK.fullmatch(target)
                and target.startswith("phases/")
            ):
                raise DataValidationError(
                    f"{table_name}[{index}].cible_lien doit pointer vers "
                    f"phases/*.html: {target!r}."
                )
            if link_type == "page_etat" and not (
                SAFE_INTERNAL_LINK.fullmatch(target)
                and target.startswith("states/")
            ):
                raise DataValidationError(
                    f"{table_name}[{index}].cible_lien doit pointer vers "
                    f"states/*.html: {target!r}."
                )
            if link_type == "url" and not SAFE_EXTERNAL_LINK.match(target):
                raise DataValidationError(
                    f"{table_name}[{index}].cible_lien doit être une URL HTTP(S)."
                )


def validate_source(source: Path, schema_path: Path | None = None) -> dict[str, Any]:
    source_document = load_json(source)
    if is_manifest(source_document):
        inferred_schema = schema_path_from_manifest(source)
        effective_schema_path = schema_path or inferred_schema
        if effective_schema_path is None:
            raise DataValidationError("Aucun schéma n'est associé au manifeste.")
        merged, fragment_paths = load_manifest(source)
        schema = load_json(effective_schema_path)
        for fragment_path in fragment_paths:
            fragment = load_json(fragment_path)
            validate_records_against_schema(
                fragment, schema, require_all_tables=False
            )
        document = merged
    else:
        if schema_path is None:
            raise DataValidationError(
                "--schema est obligatoire pour un fichier de données unique."
            )
        effective_schema_path = schema_path
        schema = load_json(effective_schema_path)
        document = load_data_source(source)

    if not isinstance(schema, Mapping):
        raise DataValidationError("La racine du schéma doit être un objet.")
    validate_records_against_schema(document, schema)
    validate_references(document, schema)
    validate_business_consistency(document)
    return document


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Vérifie la compatibilité entre le modèle et les données."
    )
    parser.add_argument("source", type=Path, help="Fichier de données ou manifeste.")
    parser.add_argument(
        "--schema",
        type=Path,
        help="Schéma JSON. Facultatif si le manifeste déclare 'schema'.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        document = validate_source(args.source, args.schema)
        record_count = sum(len(records) for records in document.values())
        print(
            f"Compatibilité validée: {len(document)} tables, "
            f"{record_count} enregistrements."
        )
        return 0
    except (DataValidationError, WorkflowDataError) as error:
        print(f"Erreur: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
