"""Operations used by the workflow administration TUI.

This module deliberately depends only on the Python standard library so the
administration operations can also be exercised from tests and scripts.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from workflow_data import WorkflowDataError, load_data_source


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = PROJECT_ROOT / "data" / "workflows" / "catalog.json"
DEFAULT_BUILD = PROJECT_ROOT / "build" / "site-workflows"
SETTINGS_PATH = PROJECT_ROOT / "build" / ".workflow-tui.json"
SAFE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
THEMES = ("ocean", "forest", "aubergine", "graphite")


class TuiOperationError(RuntimeError):
    """Raised when an administration operation cannot be completed safely."""


@dataclass(frozen=True)
class WorkflowEntry:
    slug: str
    label: str
    description: str
    manifest: Path


@dataclass(frozen=True)
class CommandResult:
    command: tuple[str, ...]
    returncode: int
    output: str
    artifact: Path | None = None

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True)
class SiteThemeTarget:
    target_id: str
    label: str
    pair: str
    mode: str
    config_path: Path


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise TuiOperationError(f"Impossible de lire {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise TuiOperationError(
            f"JSON invalide dans {path}, ligne {error.lineno}: {error.msg}"
        ) from error


def _write_json(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def list_workflows(catalog_path: Path = DEFAULT_CATALOG) -> list[WorkflowEntry]:
    """Return normalized workflow entries from the site catalog."""
    catalog = _read_json(catalog_path)
    if not isinstance(catalog, Mapping) or not isinstance(
        catalog.get("workflows"), list
    ):
        raise TuiOperationError(f"Catalogue de workflows invalide: {catalog_path}")
    entries: list[WorkflowEntry] = []
    for index, item in enumerate(catalog["workflows"]):
        if not isinstance(item, Mapping):
            raise TuiOperationError(f"Entrée {index} invalide dans le catalogue.")
        try:
            slug = str(item["slug"])
            label = str(item["label"])
            manifest_value = str(item["manifest"])
        except KeyError as error:
            raise TuiOperationError(
                f"Entrée {index} incomplète dans le catalogue: {error}."
            ) from error
        entries.append(
            WorkflowEntry(
                slug=slug,
                label=label,
                description=str(item.get("description", "")),
                manifest=(catalog_path.parent / manifest_value).resolve(),
            )
        )
    return entries


def load_settings(path: Path = SETTINGS_PATH) -> dict[str, str]:
    defaults = {"theme": "ocean", "editor": ""}
    if not path.is_file():
        return defaults
    try:
        settings = _read_json(path)
    except TuiOperationError:
        return defaults
    theme = settings.get("theme") if isinstance(settings, Mapping) else None
    editor = settings.get("editor") if isinstance(settings, Mapping) else None
    return {
        "theme": theme if theme in THEMES else "ocean",
        "editor": editor if isinstance(editor, str) else "",
    }


def save_settings(theme: str, path: Path = SETTINGS_PATH) -> None:
    if theme not in THEMES:
        raise TuiOperationError(f"Thème inconnu: {theme}")
    settings = load_settings(path)
    settings["theme"] = theme
    _write_json(path, settings)


def save_editor_setting(editor: str, path: Path = SETTINGS_PATH) -> None:
    """Save an optional editor command; an empty value restores OS association."""
    settings = load_settings(path)
    settings["editor"] = editor.strip()
    _write_json(path, settings)


def list_site_theme_targets(
    catalog_path: Path = DEFAULT_CATALOG,
) -> list[SiteThemeTarget]:
    """Return the independent web theme configuration scopes."""
    catalog = _read_json(catalog_path)
    if not isinstance(catalog, Mapping):
        raise TuiOperationError(f"Catalogue invalide: {catalog_path}")
    catalog_theme = catalog.get("theme", {})
    if not isinstance(catalog_theme, Mapping):
        raise TuiOperationError("Le thème du catalogue doit être un objet.")
    targets = [
        SiteThemeTarget(
            "catalog",
            "Accueil commun et éditeur",
            str(catalog_theme.get("pair", "ocean")),
            str(catalog_theme.get("mode", "system")),
            catalog_path.resolve(),
        )
    ]
    for entry in list_workflows(catalog_path):
        manifest = _read_json(entry.manifest)
        site = manifest.get("site", {}) if isinstance(manifest, Mapping) else {}
        theme = site.get("theme", {}) if isinstance(site, Mapping) else {}
        if not isinstance(theme, Mapping):
            raise TuiOperationError(f"Thème de site invalide: {entry.manifest}")
        targets.append(
            SiteThemeTarget(
                entry.slug,
                f"Workflow · {entry.label}",
                str(theme.get("pair", "ocean")),
                str(theme.get("mode", "system")),
                entry.manifest,
            )
        )
    return targets


def save_site_theme(
    target_id: str,
    pair: str,
    mode: str,
    catalog_path: Path = DEFAULT_CATALOG,
) -> SiteThemeTarget:
    """Persist a portal or workflow website theme, separately from the TUI."""
    if pair not in THEMES:
        raise TuiOperationError(f"Paire de couleurs inconnue: {pair}")
    if mode not in {"system", "light", "dark"}:
        raise TuiOperationError(f"Mode d’affichage inconnu: {mode}")
    targets = {item.target_id: item for item in list_site_theme_targets(catalog_path)}
    target = targets.get(target_id)
    if target is None:
        raise TuiOperationError(f"Site inconnu: {target_id}")
    document = _read_json(target.config_path)
    if not isinstance(document, dict):
        raise TuiOperationError(f"Configuration invalide: {target.config_path}")
    if target_id == "catalog":
        document["theme"] = {"pair": pair, "mode": mode}
    else:
        site = document.setdefault("site", {})
        if not isinstance(site, dict):
            raise TuiOperationError(f"Configuration site invalide: {target.config_path}")
        site["theme"] = {"pair": pair, "mode": mode}
    _write_json(target.config_path, document)
    return replace(target, pair=pair, mode=mode)


def normalize_identifier(slug: str) -> str:
    identifier = "_".join(part.capitalize() for part in slug.split("-"))
    if not SAFE_IDENTIFIER.fullmatch(identifier):
        raise TuiOperationError("Impossible de produire un identifiant Mermaid sûr.")
    return identifier


def new_workflow_document(slug: str, label: str, description: str) -> dict[str, Any]:
    """Build a small but complete and schema-compatible starter workflow."""
    workflow_id = normalize_identifier(slug)
    participant_id = f"Equipe_{workflow_id}"
    lane_id = f"Pilotage_{workflow_id}"
    initial_id = f"A_demarrer_{workflow_id}"
    final_id = f"Termine_{workflow_id}"
    return {
        "Workflow": [
            {
                "workflow_id": workflow_id,
                "nom": label,
                "description": description,
                "type_diagramme": "swimlane",
                "orientation": "LR",
                "actif": True,
            }
        ],
        "Participant": [
            {
                "participant_id": participant_id,
                "workflow_id": workflow_id,
                "nom": "Équipe",
                "description": "Participant initial à personnaliser.",
                "processus_visible": True,
                "ordre": 10,
            }
        ],
        "Ligne_eau": [
            {
                "ligne_eau_id": lane_id,
                "workflow_id": workflow_id,
                "participant_id": participant_id,
                "nom": "Pilotage",
                "description": "Ligne d’eau initiale à personnaliser.",
                "type_partition": "role",
                "ordre": 10,
            }
        ],
        "Etat": [
            {
                "etat_id": initial_id,
                "workflow_id": workflow_id,
                "ligne_eau_id": lane_id,
                "nom": "À démarrer",
                "type_etat": "initial",
                "ordre": 10,
            },
            {
                "etat_id": final_id,
                "workflow_id": workflow_id,
                "ligne_eau_id": lane_id,
                "nom": "Terminé",
                "type_etat": "final",
                "ordre": 20,
            },
        ],
        "Transition": [
            {
                "transition_id": f"Demarrer_{workflow_id}",
                "workflow_id": workflow_id,
                "etat_source_id": initial_id,
                "etat_cible_id": final_id,
                "libelle": "travail réalisé",
                "actif": True,
            }
        ],
        "Role": [],
        "Regle": [],
        "Generation_Mermaid": [],
    }


def create_workflow(
    slug: str,
    label: str,
    description: str,
    catalog_path: Path = DEFAULT_CATALOG,
) -> WorkflowEntry:
    """Create a starter workflow and register it in the catalog."""
    slug = slug.strip().lower()
    label = label.strip()
    description = description.strip()
    if not SAFE_SLUG.fullmatch(slug):
        raise TuiOperationError(
            "Le slug doit contenir uniquement a-z, 0-9 et des tirets simples."
        )
    if not label:
        raise TuiOperationError("Le nom du workflow est obligatoire.")

    catalog = _read_json(catalog_path)
    if not isinstance(catalog, dict) or not isinstance(catalog.get("workflows"), list):
        raise TuiOperationError(f"Catalogue invalide: {catalog_path}")
    if any(item.get("slug") == slug for item in catalog["workflows"]):
        raise TuiOperationError(f"Le workflow {slug!r} existe déjà.")

    workflow_dir = catalog_path.parent / slug
    if workflow_dir.exists():
        raise TuiOperationError(f"Le répertoire existe déjà: {workflow_dir}")
    manifest_path = workflow_dir / "manifest.json"
    data_path = workflow_dir / "workflow.json"
    manifest = {
        "format": "workflow-data-manifest-v1",
        "schema": "../../../schema/workflow-model.json",
        "site": {
            "theme": {"pair": "ocean", "mode": "system"},
            "diagram": {
                "node_spacing": 42,
                "rank_spacing": 55,
                "diagram_padding": 20,
                "wrapping_width": 190,
                "lane_title_wrap": 18,
                "use_max_width": False,
            }
        },
        "files": ["workflow.json"],
    }
    _write_json(data_path, new_workflow_document(slug, label, description))
    _write_json(manifest_path, manifest)
    catalog["workflows"].append(
        {
            "slug": slug,
            "manifest": f"{slug}/manifest.json",
            "label": label,
            "description": description,
        }
    )
    _write_json(catalog_path, catalog)
    return WorkflowEntry(slug, label, description, manifest_path.resolve())


def configuration_files(root: Path = PROJECT_ROOT) -> list[Path]:
    """Return useful editable sources without walking generated/vendor trees."""
    candidates: list[Path] = []
    for base, patterns in (
        (root / "data" / "workflows", ("*.json", "README.md")),
        (root / "schema", ("*.json",)),
        (root / "docs", ("*.md",)),
    ):
        if not base.exists():
            continue
        for pattern in patterns:
            candidates.extend(base.rglob(pattern))
    candidates.extend(
        path
        for path in (
            root / "scripts" / "generate_mermaid.py",
            root / "scripts" / "html_rendering.py",
            root / "scripts" / "generate_workflow_site.py",
        )
        if path.is_file()
    )
    return sorted(set(candidates), key=lambda path: str(path.relative_to(root)).lower())


def read_preview(path: Path, limit: int = 24_000) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return f"Aperçu indisponible: {error}"
    if len(text) > limit:
        return text[:limit] + "\n\n… aperçu tronqué …"
    return text


def run_project_command(
    arguments: Sequence[str | Path], root: Path = PROJECT_ROOT
) -> CommandResult:
    command = (sys.executable, *map(str, arguments))
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        check=False,
    )
    output = "\n".join(part.strip() for part in (process.stdout, process.stderr) if part.strip())
    return CommandResult(command, process.returncode, output)


def validate_workflow(entry: WorkflowEntry) -> CommandResult:
    return run_project_command(("scripts/validate_workflow_data.py", entry.manifest))


def generate_mermaid(
    entry: WorkflowEntry, output: Path | None = None
) -> CommandResult:
    destination = output or PROJECT_ROOT / "build" / "mermaid" / f"{entry.slug}.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    arguments: list[str | Path] = [
        "scripts/generate_mermaid.py",
        entry.manifest,
        "--output",
        destination,
    ]
    manifest = _read_json(entry.manifest)
    site = manifest.get("site", {}) if isinstance(manifest, Mapping) else {}
    detail_workflow_id = (
        site.get("detail_workflow_id") if isinstance(site, Mapping) else None
    )
    if isinstance(detail_workflow_id, str) and detail_workflow_id:
        arguments.extend(("--workflow-id", detail_workflow_id))
    result = run_project_command(
        arguments
    )
    if result.succeeded:
        message = f"Fichier Mermaid généré: {destination.resolve()}"
        result = replace(
            result,
            output="\n".join(part for part in (result.output, message) if part),
            artifact=destination.resolve(),
        )
    return result


def generate_site(
    catalog_path: Path = DEFAULT_CATALOG, output: Path = DEFAULT_BUILD
) -> CommandResult:
    output.parent.mkdir(parents=True, exist_ok=True)
    before = {
        path.relative_to(output): path.stat().st_mtime_ns
        for path in output.rglob("*")
        if path.is_file()
    } if output.is_dir() else {}
    result = run_project_command(
        ("scripts/generate_workflow_site.py", catalog_path, "--output", output)
    )
    if result.succeeded:
        workflow_count = len(list_workflows(catalog_path))
        written = [
            path
            for path in output.rglob("*")
            if path.is_file()
            and before.get(path.relative_to(output)) != path.stat().st_mtime_ns
        ]
        html_count = sum(1 for path in written if path.suffix.lower() == ".html")
        file_count = len(written)
        summary = (
            f"Site complet généré: {workflow_count} workflows, "
            f"{html_count} pages HTML et {file_count} fichiers écrits.\n"
            f"Point d’entrée commun: {(output / 'index.html').resolve()}"
        )
        result = replace(
            result,
            output="\n".join(part for part in (result.output, summary) if part),
            artifact=(output / "index.html").resolve(),
        )
    return result


def generate_workflow_site(
    entry: WorkflowEntry, output: Path | None = None
) -> CommandResult:
    """Generate only one workflow site while keeping its catalog navigation link."""
    destination = output or DEFAULT_BUILD / entry.slug
    destination.parent.mkdir(parents=True, exist_ok=True)
    export_workflow_document(entry)
    before = {
        path.relative_to(destination): path.stat().st_mtime_ns
        for path in destination.rglob("*")
        if path.is_file()
    } if destination.is_dir() else {}
    result = run_project_command(
        (
            "scripts/generate_workflow_site.py",
            entry.manifest,
            "--output",
            destination,
            "--catalog-href",
            "../index.html",
        )
    )
    if result.succeeded:
        written = [
            path
            for path in destination.rglob("*")
            if path.is_file()
            and before.get(path.relative_to(destination)) != path.stat().st_mtime_ns
        ]
        html_count = sum(1 for path in written if path.suffix.lower() == ".html")
        page_label = "page HTML" if html_count == 1 else "pages HTML"
        file_label = "fichier écrit" if len(written) == 1 else "fichiers écrits"
        summary = (
            f"Site du workflow « {entry.label} » généré: "
            f"{html_count} {page_label} et {len(written)} {file_label}.\n"
            f"Point d’entrée du workflow: {(destination / 'index.html').resolve()}"
        )
        result = replace(
            result,
            output="\n".join(part for part in (result.output, summary) if part),
            artifact=(destination / "index.html").resolve(),
        )
    return result


def export_workflow_document(
    entry: WorkflowEntry, output: Path | None = None
) -> Path:
    """Materialize the complete document assembled from a workflow manifest."""
    destination = output or DEFAULT_BUILD / "sources" / f"{entry.slug}.json"
    try:
        document = load_data_source(entry.manifest)
    except (WorkflowDataError, OSError) as error:
        raise TuiOperationError(
            f"Impossible d’assembler le document de {entry.label}: {error}"
        ) from error
    _write_json(destination, document)
    return destination.resolve()


def open_path(path: Path) -> None:
    """Open a file or directory with the user's configured desktop application."""
    path = path.resolve()
    if not path.exists():
        raise TuiOperationError(f"Chemin introuvable: {path}")
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError as error:
        raise TuiOperationError(f"Impossible d’ouvrir {path}: {error}") from error


def open_in_editor(path: Path, editor_command: str = "") -> None:
    """Open a text file with a TUI override or the operating-system association."""
    path = path.resolve()
    if not path.is_file():
        raise TuiOperationError(f"Fichier introuvable: {path}")
    try:
        if editor_command.strip():
            command = shlex.split(editor_command, posix=sys.platform != "win32")
            if sys.platform == "win32":
                command = [
                    token[1:-1]
                    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'"
                    else token
                    for token in command
                ]
            subprocess.Popen([*command, str(path)], cwd=PROJECT_ROOT)
        elif sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except (OSError, ValueError) as error:
        raise TuiOperationError(
            f"Impossible d’ouvrir {path} dans un éditeur: {error}"
        ) from error
