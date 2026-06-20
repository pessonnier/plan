#!/usr/bin/env python3
"""Generate Mermaid diagrams from the workflow schema or workflow records."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from workflow_data import WorkflowDataError, load_data_source


MERMAID_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SUPPORTED_ORIENTATIONS = {"TD", "LR", "BT", "RL"}


class MermaidGenerationError(ValueError):
    """Raised when input data cannot be converted safely to Mermaid."""


def detect_input_kind(document: Any) -> str:
    if not isinstance(document, Mapping):
        raise MermaidGenerationError("La racine du document JSON doit être un objet.")

    if isinstance(document.get("tables"), list):
        return "schema"

    required_tables = {"Workflow", "Etat", "Transition"}
    if required_tables.issubset(document):
        return "dataset"

    raise MermaidGenerationError(
        "Format JSON non reconnu. Fournir un schéma avec une liste 'tables' ou "
        "un jeu de données contenant Workflow, Etat et Transition."
    )


def require_mermaid_id(value: Any, context: str) -> str:
    if not isinstance(value, str) or not MERMAID_ID.fullmatch(value):
        raise MermaidGenerationError(
            f"{context} doit être un identifiant Mermaid stable "
            "(lettres ASCII, chiffres et '_', sans espace ni accent): {value!r}"
        )
    return value


def escape_flowchart_label(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("|", "&#124;")
        .replace("\r\n", "<br/>")
        .replace("\n", "<br/>")
        .replace("\r", "<br/>")
    )


def escape_state_label(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("\r\n", " ")
        .replace("\n", " ")
        .replace("\r", " ")
        .replace(":", "&#58;")
    )


def as_record_list(document: Mapping[str, Any], table_name: str) -> list[Mapping[str, Any]]:
    records = document.get(table_name)
    if not isinstance(records, list):
        raise MermaidGenerationError(f"{table_name} doit être une liste.")
    if not all(isinstance(record, Mapping) for record in records):
        raise MermaidGenerationError(
            f"Chaque entrée de {table_name} doit être un objet JSON."
        )
    return list(records)


def select_workflow(
    document: Mapping[str, Any], workflow_id: str | None
) -> tuple[Mapping[str, Any], list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    workflows = as_record_list(document, "Workflow")
    states = as_record_list(document, "Etat")
    transitions = as_record_list(document, "Transition")

    if workflow_id is not None:
        matches = [
            workflow
            for workflow in workflows
            if workflow.get("workflow_id") == workflow_id
        ]
        if not matches:
            raise MermaidGenerationError(
                f"Workflow introuvable dans le jeu de données: {workflow_id}"
            )
    else:
        matches = [workflow for workflow in workflows if workflow.get("actif", True)]
        if len(matches) != 1:
            raise MermaidGenerationError(
                "Le jeu de données doit contenir exactement un workflow actif, "
                "ou l'option --workflow-id doit être fournie."
            )

    workflow = matches[0]
    selected_id = require_mermaid_id(
        workflow.get("workflow_id"), "Workflow.workflow_id"
    )

    selected_states = [
        state for state in states if state.get("workflow_id") == selected_id
    ]
    selected_transitions = [
        transition
        for transition in transitions
        if transition.get("workflow_id") == selected_id
        and transition.get("actif", True) is True
    ]

    if not selected_states:
        raise MermaidGenerationError(
            f"Le workflow {selected_id} ne contient aucun état."
        )

    validate_workflow_records(selected_id, selected_states, selected_transitions)
    return workflow, selected_states, selected_transitions


def validate_workflow_records(
    workflow_id: str,
    states: Sequence[Mapping[str, Any]],
    transitions: Sequence[Mapping[str, Any]],
) -> None:
    state_ids: set[str] = set()

    for state in states:
        state_id = require_mermaid_id(state.get("etat_id"), "Etat.etat_id")
        if state_id in state_ids:
            raise MermaidGenerationError(
                f"Etat.etat_id est dupliqué dans le workflow {workflow_id}: {state_id}"
            )
        state_ids.add(state_id)

        if not isinstance(state.get("nom"), str) or not state["nom"].strip():
            raise MermaidGenerationError(f"Etat.nom est requis pour {state_id}.")
        if state.get("type_etat") not in {
            "initial",
            "normal",
            "validation",
            "blocage",
            "final",
        }:
            raise MermaidGenerationError(
                f"Etat.type_etat est invalide pour {state_id}: "
                f"{state.get('type_etat')!r}"
            )

    transition_ids: set[str] = set()
    for transition in transitions:
        transition_id = require_mermaid_id(
            transition.get("transition_id"), "Transition.transition_id"
        )
        if transition_id in transition_ids:
            raise MermaidGenerationError(
                f"Transition.transition_id est dupliqué: {transition_id}"
            )
        transition_ids.add(transition_id)

        source = transition.get("etat_source_id")
        target = transition.get("etat_cible_id")
        if source not in state_ids or target not in state_ids:
            raise MermaidGenerationError(
                f"La transition {transition_id} référence un état absent du workflow "
                f"{workflow_id}: {source!r} -> {target!r}"
            )
        if not isinstance(transition.get("libelle"), str):
            raise MermaidGenerationError(
                f"Transition.libelle est requis pour {transition_id}."
            )


def state_sort_key(state: Mapping[str, Any]) -> tuple[float, str]:
    order = state.get("ordre")
    numeric_order = float(order) if isinstance(order, (int, float)) else float("inf")
    return numeric_order, str(state.get("etat_id", ""))


def transition_sort_key(transition: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(transition.get("etat_source_id", "")),
        str(transition.get("etat_cible_id", "")),
        str(transition.get("transition_id", "")),
    )


def escape_mermaid_link(value: Any) -> str:
    return str(value).replace("\\", "/").replace('"', "%22")


def generate_dataset_flowchart(
    workflow: Mapping[str, Any],
    states: Sequence[Mapping[str, Any]],
    transitions: Sequence[Mapping[str, Any]],
    link_resolver: Callable[[Mapping[str, Any]], str | None] | None = None,
) -> str:
    orientation = workflow.get("orientation") or "TD"
    if orientation not in SUPPORTED_ORIENTATIONS:
        raise MermaidGenerationError(
            f"Workflow.orientation invalide: {orientation!r}. "
            f"Valeurs permises: {', '.join(sorted(SUPPORTED_ORIENTATIONS))}."
        )

    lines = [f"flowchart {orientation}"]
    for state in sorted(states, key=state_sort_key):
        state_id = str(state["etat_id"])
        label = escape_flowchart_label(state["nom"])
        lines.append(f'    {state_id}["{label}"]')

    if transitions:
        lines.append("")
    for transition in sorted(transitions, key=transition_sort_key):
        source = transition["etat_source_id"]
        target = transition["etat_cible_id"]
        label = escape_flowchart_label(transition["libelle"])
        lines.append(f"    {source} -->|{label}| {target}")

    linked_states = [
        state
        for state in sorted(states, key=state_sort_key)
        if state.get("cible_lien")
    ]
    if linked_states:
        lines.append("")
    for state in linked_states:
        target = (
            link_resolver(state)
            if link_resolver is not None
            else str(state["cible_lien"])
        )
        if not target:
            continue
        tooltip = state.get("libelle_lien") or state["nom"]
        lines.append(
            f'    click {state["etat_id"]} "{escape_mermaid_link(target)}" '
            f'"{escape_flowchart_label(tooltip)}"'
        )

    return "\n".join(lines)


def generate_dataset_state_diagram(
    states: Sequence[Mapping[str, Any]],
    transitions: Sequence[Mapping[str, Any]],
) -> str:
    ordered_states = sorted(states, key=state_sort_key)
    lines = ["stateDiagram-v2"]

    for state in ordered_states:
        state_id = str(state["etat_id"])
        label = escape_state_label(state["nom"])
        if label != state_id:
            lines.append(f'    state "{label}" as {state_id}')

    initial_states = [
        state for state in ordered_states if state.get("type_etat") == "initial"
    ]
    final_states = [
        state for state in ordered_states if state.get("type_etat") == "final"
    ]

    if initial_states or transitions or final_states:
        lines.append("")
    for state in initial_states:
        lines.append(f"    [*] --> {state['etat_id']}")
    for transition in sorted(transitions, key=transition_sort_key):
        label = escape_state_label(transition["libelle"])
        suffix = f" : {label}" if label else ""
        lines.append(
            f"    {transition['etat_source_id']} --> "
            f"{transition['etat_cible_id']}{suffix}"
        )
    for state in final_states:
        lines.append(f"    {state['etat_id']} --> [*]")

    return "\n".join(lines)


def schema_tables(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    tables = document.get("tables")
    if not isinstance(tables, list) or not tables:
        raise MermaidGenerationError("Le schéma doit contenir une liste 'tables'.")
    if not all(isinstance(table, Mapping) for table in tables):
        raise MermaidGenerationError("Chaque table du schéma doit être un objet.")
    return list(tables)


def schema_relations(
    tables: Sequence[Mapping[str, Any]],
) -> list[tuple[str, str, str]]:
    relations: list[tuple[str, str, str]] = []
    table_names = {
        require_mermaid_id(table.get("name"), "tables[].name") for table in tables
    }

    for table in tables:
        source = str(table["name"])
        fields = table.get("fields")
        if not isinstance(fields, list):
            raise MermaidGenerationError(f"fields doit être une liste pour {source}.")
        for field in fields:
            if not isinstance(field, Mapping):
                raise MermaidGenerationError(
                    f"Chaque champ de la table {source} doit être un objet."
                )
            if field.get("type") != "reference":
                continue
            field_name = require_mermaid_id(
                field.get("name"), f"{source}.fields[].name"
            )
            reference = field.get("references")
            if not isinstance(reference, str) or "." not in reference:
                raise MermaidGenerationError(
                    f"Référence invalide pour {source}.{field_name}: {reference!r}"
                )
            target = reference.split(".", 1)[0]
            if target not in table_names:
                raise MermaidGenerationError(
                    f"Table référencée absente pour {source}.{field_name}: {target}"
                )
            relations.append((source, target, field_name))

    return sorted(relations)


def generate_schema_flowchart(document: Mapping[str, Any]) -> str:
    tables = sorted(schema_tables(document), key=lambda table: str(table.get("name")))
    relations = schema_relations(tables)
    lines = ["flowchart LR"]

    for table in tables:
        table_name = str(table["name"])
        description = escape_flowchart_label(table.get("description", table_name))
        lines.append(f'    {table_name}["{table_name}<br/><small>{description}</small>"]')

    if relations:
        lines.append("")
    for source, target, field_name in relations:
        lines.append(f"    {source} -->|{field_name}| {target}")

    return "\n".join(lines)


def generate_schema_state_diagram(document: Mapping[str, Any]) -> str:
    tables = sorted(schema_tables(document), key=lambda table: str(table.get("name")))
    relations = schema_relations(tables)
    lines = ["stateDiagram-v2"]

    for table in tables:
        table_name = str(table["name"])
        lines.append(f'    state "{escape_state_label(table_name)}" as {table_name}')

    if relations:
        lines.append("")
    for source, target, field_name in relations:
        lines.append(f"    {source} --> {target} : {escape_state_label(field_name)}")

    return "\n".join(lines)


def generate_diagrams(
    document: Mapping[str, Any],
    input_kind: str,
    workflow_id: str | None,
) -> dict[str, str]:
    if input_kind == "schema":
        if workflow_id is not None:
            raise MermaidGenerationError(
                "--workflow-id n'est applicable qu'à un jeu de données."
            )
        return {
            "flowchart": generate_schema_flowchart(document),
            "state": generate_schema_state_diagram(document),
        }

    workflow, states, transitions = select_workflow(document, workflow_id)
    return {
        "flowchart": generate_dataset_flowchart(workflow, states, transitions),
        "state": generate_dataset_state_diagram(states, transitions),
    }


def format_output(diagrams: Iterable[str], output_format: str) -> str:
    selected = list(diagrams)
    if output_format == "code":
        return "\n\n".join(selected) + "\n"
    return "\n\n".join(f"```mermaid\n{diagram}\n```" for diagram in selected) + "\n"


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Génère des diagrammes Mermaid depuis le schéma Grist ou un jeu "
            "de données de workflow."
        )
    )
    parser.add_argument("input", type=Path, help="Fichier JSON source.")
    parser.add_argument(
        "--diagram",
        choices=("flowchart", "state", "both"),
        default="both",
        help="Diagramme à produire (défaut: both).",
    )
    parser.add_argument(
        "--workflow-id",
        help="Workflow à sélectionner si le jeu de données en contient plusieurs.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "code"),
        default="markdown",
        dest="output_format",
        help="Format de sortie (défaut: markdown).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Fichier de sortie. Par défaut, écrit sur la sortie standard.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    try:
        document = load_data_source(args.input)
        input_kind = detect_input_kind(document)
        diagrams = generate_diagrams(document, input_kind, args.workflow_id)
        selected_names = (
            ("flowchart", "state")
            if args.diagram == "both"
            else (args.diagram,)
        )
        result = format_output(
            (diagrams[name] for name in selected_names), args.output_format
        )

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(result, encoding="utf-8")
        else:
            sys.stdout.write(result)
        return 0
    except (MermaidGenerationError, WorkflowDataError, OSError) as error:
        parser.exit(2, f"Erreur: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
