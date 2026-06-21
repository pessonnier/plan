#!/usr/bin/env python3
"""Validate links between specifications, code and tests."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


MATRIX_FORMAT = "requirements-traceability-v1"
REFERENCE_GROUPS = ("code", "unit_tests", "functional_tests")


class TraceabilityError(ValueError):
    """Raised when the requirements traceability matrix is inconsistent."""


def load_matrix(path: Path) -> Mapping[str, Any]:
    try:
        matrix = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise TraceabilityError(f"Impossible de lire {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise TraceabilityError(
            f"JSON invalide dans {path}, ligne {error.lineno}: {error.msg}"
        ) from error
    if not isinstance(matrix, Mapping) or matrix.get("format") != MATRIX_FORMAT:
        raise TraceabilityError(
            f"Format de matrice attendu: {MATRIX_FORMAT!r}."
        )
    return matrix


def python_symbols(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except OSError as error:
        raise TraceabilityError(f"Impossible de lire {path}: {error}") from error
    except SyntaxError as error:
        raise TraceabilityError(f"Python invalide dans {path}: {error}") from error

    symbols: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.add(node.name)
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.add(f"{node.name}.{child.name}")
    return symbols


def parse_reference(reference: Any, context: str) -> tuple[str, str]:
    if not isinstance(reference, str) or "::" not in reference:
        raise TraceabilityError(
            f"{context}: référence attendue sous la forme chemin.py::symbole."
        )
    path, symbol = reference.split("::", 1)
    if not path or not symbol:
        raise TraceabilityError(f"{context}: référence incomplète {reference!r}.")
    return path, symbol


def validate_traceability(matrix_path: Path, project_root: Path) -> int:
    matrix = load_matrix(matrix_path)
    requirements = matrix.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        raise TraceabilityError("La matrice doit contenir des exigences.")

    seen_ids: set[str] = set()
    symbol_cache: dict[Path, set[str]] = {}
    for index, requirement in enumerate(requirements):
        context = f"requirements[{index}]"
        if not isinstance(requirement, Mapping):
            raise TraceabilityError(f"{context} doit être un objet.")
        requirement_id = requirement.get("id")
        if not isinstance(requirement_id, str) or not requirement_id.startswith("REQ-"):
            raise TraceabilityError(f"{context}.id est invalide.")
        if requirement_id in seen_ids:
            raise TraceabilityError(f"Exigence dupliquée: {requirement_id}.")
        seen_ids.add(requirement_id)

        specification = requirement.get("specification")
        if not isinstance(specification, str):
            raise TraceabilityError(
                f"{requirement_id}: specification doit être un chemin."
            )
        specification_path = project_root / specification
        try:
            specification_text = specification_path.read_text(encoding="utf-8")
        except OSError as error:
            raise TraceabilityError(
                f"{requirement_id}: spécification introuvable {specification}: {error}"
            ) from error
        if requirement_id not in specification_text:
            raise TraceabilityError(
                f"{requirement_id}: identifiant absent de {specification}."
            )

        for group in REFERENCE_GROUPS:
            references = requirement.get(group)
            if not isinstance(references, list) or not references:
                raise TraceabilityError(
                    f"{requirement_id}: au moins une référence {group} est requise."
                )
            for reference in references:
                relative_path, symbol = parse_reference(
                    reference, f"{requirement_id}.{group}"
                )
                normalized_path = relative_path.replace("\\", "/")
                if group == "unit_tests" and normalized_path.startswith(
                    "tests/functional/"
                ):
                    raise TraceabilityError(
                        f"{requirement_id}: un test unitaire ne doit pas être "
                        f"classé dans tests/functional: {relative_path}."
                    )
                if group == "functional_tests" and not normalized_path.startswith(
                    "tests/functional/"
                ):
                    raise TraceabilityError(
                        f"{requirement_id}: un test fonctionnel doit être placé "
                        f"dans tests/functional: {relative_path}."
                    )
                path = project_root / relative_path
                if path not in symbol_cache:
                    symbol_cache[path] = python_symbols(path)
                if symbol not in symbol_cache[path]:
                    raise TraceabilityError(
                        f"{requirement_id}: symbole introuvable "
                        f"{relative_path}::{symbol}."
                    )
    return len(requirements)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Vérifie la traçabilité spécifications-code-tests."
    )
    parser.add_argument(
        "matrix",
        nargs="?",
        type=Path,
        default=Path("traceability/requirements.json"),
        help="Matrice JSON de traçabilité.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Racine utilisée pour résoudre les chemins.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        count = validate_traceability(args.matrix, args.project_root)
        print(f"Traçabilité validée: {count} exigences.")
        return 0
    except TraceabilityError as error:
        print(f"Erreur: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
