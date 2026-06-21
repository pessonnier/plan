"""Load complete or fragmented workflow datasets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


MANIFEST_FORMAT = "workflow-data-manifest-v1"
CATALOG_FORMAT = "workflow-site-catalog-v1"


class WorkflowDataError(ValueError):
    """Raised when workflow data files cannot be loaded or assembled."""


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except OSError as error:
        raise WorkflowDataError(f"Impossible de lire le fichier {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise WorkflowDataError(
            f"JSON invalide dans {path}, ligne {error.lineno}, colonne "
            f"{error.colno}: {error.msg}"
        ) from error


def is_manifest(document: Any) -> bool:
    return (
        isinstance(document, Mapping)
        and document.get("format") == MANIFEST_FORMAT
        and isinstance(document.get("files"), list)
    )


def is_catalog(document: Any) -> bool:
    return (
        isinstance(document, Mapping)
        and document.get("format") == CATALOG_FORMAT
        and isinstance(document.get("workflows"), list)
    )


def load_catalog(catalog_path: Path) -> tuple[Mapping[str, Any], list[dict[str, Any]]]:
    catalog = load_json(catalog_path)
    if not is_catalog(catalog):
        raise WorkflowDataError(
            f"Catalogue invalide dans {catalog_path}: format attendu "
            f"{CATALOG_FORMAT!r}."
        )
    entries = catalog["workflows"]
    if not entries:
        raise WorkflowDataError("Le catalogue doit contenir au moins un workflow.")
    loaded: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise WorkflowDataError(f"workflows[{index}] doit être un objet.")
        slug = entry.get("slug")
        manifest = entry.get("manifest")
        label = entry.get("label")
        if not all(isinstance(value, str) and value for value in (slug, manifest, label)):
            raise WorkflowDataError(
                f"workflows[{index}] doit définir slug, manifest et label."
            )
        if slug in seen_slugs:
            raise WorkflowDataError(f"Slug de workflow dupliqué: {slug}.")
        seen_slugs.add(slug)
        loaded.append(
            {
                "slug": slug,
                "manifest": (catalog_path.parent / manifest).resolve(),
                "label": label,
                "description": str(entry.get("description", "")),
            }
        )
    return catalog, loaded


def load_manifest(manifest_path: Path) -> tuple[dict[str, list[Any]], list[Path]]:
    manifest = load_json(manifest_path)
    if not is_manifest(manifest):
        raise WorkflowDataError(
            f"Manifeste invalide dans {manifest_path}: format attendu "
            f"{MANIFEST_FORMAT!r}."
        )

    file_names = manifest["files"]
    if not file_names or not all(isinstance(name, str) and name for name in file_names):
        raise WorkflowDataError("Le manifeste doit référencer au moins un fichier JSON.")

    merged: dict[str, list[Any]] = {}
    loaded_paths: list[Path] = []
    for file_name in file_names:
        fragment_path = (manifest_path.parent / file_name).resolve()
        fragment = load_json(fragment_path)
        if not isinstance(fragment, Mapping):
            raise WorkflowDataError(
                f"La racine du fragment {fragment_path} doit être un objet JSON."
            )
        for table_name, records in fragment.items():
            if not isinstance(records, list):
                raise WorkflowDataError(
                    f"{fragment_path}: la table {table_name} doit être une liste."
                )
            merged.setdefault(str(table_name), []).extend(records)
        loaded_paths.append(fragment_path)

    return merged, loaded_paths


def load_data_source(path: Path) -> dict[str, Any]:
    document = load_json(path)
    if is_manifest(document):
        merged, _ = load_manifest(path)
        return merged
    if not isinstance(document, dict):
        raise WorkflowDataError("La racine du document JSON doit être un objet.")
    return document


def schema_path_from_manifest(manifest_path: Path) -> Path | None:
    manifest = load_json(manifest_path)
    if not is_manifest(manifest):
        return None
    schema = manifest.get("schema")
    if not isinstance(schema, str) or not schema:
        raise WorkflowDataError("Le manifeste doit déclarer un chemin 'schema'.")
    return (manifest_path.parent / schema).resolve()


def site_config_from_manifest(manifest_path: Path) -> dict[str, str]:
    manifest = load_json(manifest_path)
    if not is_manifest(manifest):
        return {}
    site = manifest.get("site", {})
    if not isinstance(site, Mapping):
        raise WorkflowDataError("La configuration 'site' du manifeste est invalide.")
    config: dict[str, str] = {}
    for key in ("overview_workflow_id", "detail_workflow_id"):
        value = site.get(key)
        if value is not None:
            if not isinstance(value, str) or not value:
                raise WorkflowDataError(f"site.{key} doit être un identifiant.")
            config[key] = value
    return config
