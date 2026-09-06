"""Load complete or fragmented workflow datasets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


MANIFEST_FORMAT = "workflow-data-manifest-v1"
CATALOG_FORMAT = "workflow-site-catalog-v1"
DEFAULT_DIAGRAM_CONFIG: dict[str, int | bool] = {
    "node_spacing": 50,
    "rank_spacing": 80,
    "diagram_padding": 20,
    "wrapping_width": 200,
    "lane_title_wrap": 22,
    "use_max_width": False,
}
SUPPORTED_THEME_PAIRS = {"ocean", "forest", "aubergine", "graphite"}
SUPPORTED_THEME_MODES = {"system", "light", "dark"}
DEFAULT_SITE_THEME = {"pair": "ocean", "mode": "system"}


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


def site_config_from_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    if not is_manifest(manifest):
        return {}
    site = manifest.get("site", {})
    if not isinstance(site, Mapping):
        raise WorkflowDataError("La configuration 'site' du manifeste est invalide.")
    config: dict[str, Any] = {}
    for key in ("overview_workflow_id", "detail_workflow_id"):
        value = site.get(key)
        if value is not None:
            if not isinstance(value, str) or not value:
                raise WorkflowDataError(f"site.{key} doit être un identifiant.")
            config[key] = value
    reference_page = site.get("reference_page")
    if reference_page is not None:
        if (
            not isinstance(reference_page, str)
            or not reference_page
            or Path(reference_page).name != reference_page
            or not reference_page.endswith(".json")
        ):
            raise WorkflowDataError(
                "site.reference_page doit être le nom d'un fichier JSON local."
            )
        config["reference_page"] = reference_page
    diagram = site.get("diagram", {})
    if not isinstance(diagram, Mapping):
        raise WorkflowDataError("site.diagram doit être un objet.")
    normalized_diagram = dict(DEFAULT_DIAGRAM_CONFIG)
    for key in (
        "node_spacing",
        "rank_spacing",
        "diagram_padding",
        "wrapping_width",
        "lane_title_wrap",
    ):
        value = diagram.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise WorkflowDataError(f"site.diagram.{key} doit être un entier positif ou nul.")
        normalized_diagram[key] = value
    use_max_width = diagram.get("use_max_width")
    if use_max_width is not None:
        if not isinstance(use_max_width, bool):
            raise WorkflowDataError("site.diagram.use_max_width doit être un booléen.")
        normalized_diagram["use_max_width"] = use_max_width
    config["diagram"] = normalized_diagram
    theme = site.get("theme", {})
    if not isinstance(theme, Mapping):
        raise WorkflowDataError("site.theme doit être un objet.")
    pair = theme.get("pair", DEFAULT_SITE_THEME["pair"])
    mode = theme.get("mode", DEFAULT_SITE_THEME["mode"])
    if pair not in SUPPORTED_THEME_PAIRS:
        raise WorkflowDataError(
            f"site.theme.pair doit être l'une des valeurs "
            f"{sorted(SUPPORTED_THEME_PAIRS)}."
        )
    if mode not in SUPPORTED_THEME_MODES:
        raise WorkflowDataError(
            f"site.theme.mode doit être l'une des valeurs "
            f"{sorted(SUPPORTED_THEME_MODES)}."
        )
    config["theme"] = {"pair": pair, "mode": mode}
    return config


def theme_config_from_catalog(catalog: Mapping[str, Any]) -> dict[str, str]:
    """Return the default appearance of the common catalog pages."""
    theme = catalog.get("theme", {})
    if not isinstance(theme, Mapping):
        raise WorkflowDataError("theme doit être un objet dans le catalogue.")
    pair = theme.get("pair", DEFAULT_SITE_THEME["pair"])
    mode = theme.get("mode", DEFAULT_SITE_THEME["mode"])
    if pair not in SUPPORTED_THEME_PAIRS:
        raise WorkflowDataError(
            f"theme.pair doit être l'une des valeurs {sorted(SUPPORTED_THEME_PAIRS)}."
        )
    if mode not in SUPPORTED_THEME_MODES:
        raise WorkflowDataError(
            f"theme.mode doit être l'une des valeurs {sorted(SUPPORTED_THEME_MODES)}."
        )
    return {"pair": str(pair), "mode": str(mode)}
