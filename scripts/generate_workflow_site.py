#!/usr/bin/env python3
"""Generate a navigable static site for a workflow."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from generate_mermaid import (
    generate_dataset_flowchart,
)
from html_rendering import (
    DEFAULT_MERMAID_URL,
    LOCAL_MERMAID_FILENAME,
    VENDORED_MERMAID_LICENSE_PATH,
    VENDORED_MERMAID_PATH,
    diagram_panel,
    escape,
    page_shell,
    record_link_href,
    record_link_status_html,
    render_sidebar,
    sanitize_documentation,
    site_css,
    site_javascript,
    slug,
    state_card,
    verified_vendored_mermaid_text,
    workflow_context,
    workflow_editor_javascript,
    write_text,
)
from validate_workflow_data import DataValidationError, validate_source
from workflow_data import (
    WorkflowDataError,
    is_catalog,
    is_manifest,
    load_catalog,
    load_json,
    load_manifest,
    site_config_from_manifest,
    theme_config_from_catalog,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def display_path(path: Path) -> str:
    """Return a portable project-relative path when possible."""
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def write_site_mermaid_assets(output: Path, mermaid_url: str) -> str:
    """Copy the pinned renderer locally when the default URL is requested."""
    if mermaid_url != DEFAULT_MERMAID_URL:
        return mermaid_url
    if (
        not VENDORED_MERMAID_PATH.is_file()
        or not VENDORED_MERMAID_LICENSE_PATH.is_file()
    ):
        raise WorkflowDataError(
            "Distribution Mermaid locale ou licence absente dans scripts/vendor."
        )
    try:
        verified_vendored_mermaid_text()
    except RuntimeError as error:
        raise WorkflowDataError(str(error)) from error
    target = output / "assets" / LOCAL_MERMAID_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(VENDORED_MERMAID_PATH, target)
    shutil.copyfile(
        VENDORED_MERMAID_LICENSE_PATH,
        target.parent / VENDORED_MERMAID_LICENSE_PATH.name,
    )
    return LOCAL_MERMAID_FILENAME


def phase_label(path: Path) -> str:
    labels = {
        "01-cadrage-budgetisation": "Cadrage et programmation budgétaire",
        "02-specifications-conception-marche": "Conception et commande publique",
        "03-realisation-qualification": "Réalisation et qualification",
        "04-mise-en-production": "Mise en service",
        "05-maintenance": "Exploitation et maintenance",
        "06-decommissionnement": "Décommissionnement",
        "01-cadrage-politique": "Cadrage et politique d'analyse",
        "02-preparation": "Préparation technique",
        "03-execution": "Exécution des analyses",
        "04-qualification": "Qualification des résultats",
        "05-remediation-suivi": "Remédiation et suivi",
        "04-generation-site": "Génération du site",
    }
    stem = path.stem
    if stem in labels:
        return labels[stem]
    stem = stem.split("-", 1)[1] if "-" in stem else stem
    return stem.replace("-", " ").capitalize()


def load_phase_map(
    source: Path, states: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    source_document = load_json(source)
    if not is_manifest(source_document):
        return [
            {
                "label": "Workflow",
                "slug": "workflow",
                "states": list(states),
                "source": source.name,
            }
        ]

    _, paths = load_manifest(source)
    known_states = {state["etat_id"]: state for state in states}
    phases: list[dict[str, Any]] = []
    assigned: set[str] = set()
    for path in paths:
        fragment = load_json(path)
        phase_states = [
            known_states[item["etat_id"]]
            for item in fragment.get("Etat", [])
            if item.get("etat_id") in known_states
        ]
        if not phase_states:
            continue
        assigned.update(state["etat_id"] for state in phase_states)
        phases.append(
            {
                "label": phase_label(path),
                "slug": slug(path.stem),
                "states": phase_states,
                "source": path.name,
            }
        )
    unassigned = [state for state in states if state["etat_id"] not in assigned]
    if unassigned:
        phases.append(
            {
                "label": "Autres états",
                "slug": "autres-etats",
                "states": unassigned,
                "source": source.name,
            }
        )
    return phases


def header(
    title: str,
    root_prefix: str = "",
    catalog_href: str | None = None,
    has_reference_page: bool = False,
    workflow_slug: str | None = None,
) -> str:
    catalog_link = (
        f'<a href="{escape(catalog_href)}">Choisir un workflow</a>'
        if catalog_href
        else ""
    )
    editor_href = catalog_href.replace("index.html", "editor.html") if catalog_href else None
    if editor_href and workflow_slug:
        editor_href = f"{editor_href}?workflow={workflow_slug}"
    editor_link = (
        f'<a href="{escape(editor_href)}">Éditer ce workflow</a>'
        if editor_href
        else ""
    )
    settings_href = f"{root_prefix}settings.html"
    reference_link = (
        f'<a href="{escape(root_prefix)}guide.html">Guide visuel</a>'
        if has_reference_page
        else ""
    )
    return f"""\
<header class="site-header">
  <h1><a href="{escape(root_prefix)}index.html">{escape(title)}</a></h1>
  <nav>
    {catalog_link}
    {editor_link}
    {reference_link}
    <a href="{escape(settings_href)}">Paramètres d’affichage</a>
    <a href="{escape(root_prefix)}index.html">Vue d'ensemble et phases</a>
    <a href="{escape(root_prefix)}etats.html">Répertoire des états</a>
    <a href="{escape(root_prefix)}transitions.html">Répertoire des transitions</a>
  </nav>
</header>"""


def render_index(
    workflow: Mapping[str, Any],
    overview_states: Sequence[Mapping[str, Any]],
    overview_transitions: Sequence[Mapping[str, Any]],
    phases: Sequence[Mapping[str, Any]],
    mermaid_url: str,
    catalog_href: str | None = None,
    waterlines: Sequence[Mapping[str, Any]] = (),
    participants: Sequence[Mapping[str, Any]] = (),
    detail_workflow: Mapping[str, Any] | None = None,
    detail_states: Sequence[Mapping[str, Any]] = (),
    detail_transitions: Sequence[Mapping[str, Any]] = (),
    detail_waterlines: Sequence[Mapping[str, Any]] = (),
    detail_participants: Sequence[Mapping[str, Any]] = (),
    diagram_config: Mapping[str, Any] | None = None,
    has_reference_page: bool = False,
    workflow_slug: str | None = None,
    theme_config: Mapping[str, str] | None = None,
    theme_scope: str = "standalone",
) -> str:
    phase_links = [(phase["label"], f'{phase["slug"]}.html') for phase in phases]
    flowchart = generate_dataset_flowchart(
        workflow,
        overview_states,
        overview_transitions,
        link_resolver=lambda state: record_link_href(state),
        waterlines=waterlines,
        participants=participants,
        lane_title_wrap=(diagram_config or {}).get("lane_title_wrap"),
    )
    detail_diagram = ""
    if detail_workflow is not None and detail_states:
        detail_flowchart = generate_dataset_flowchart(
            detail_workflow,
            detail_states,
            detail_transitions,
            link_resolver=lambda state: record_link_href(state),
            waterlines=detail_waterlines,
            participants=detail_participants,
            lane_title_wrap=(diagram_config or {}).get("lane_title_wrap"),
        )
        detail_diagram = diagram_panel(
            "Workflow complet par acteur et ligne d’eau", detail_flowchart
        )
    cards = "".join(
        f"""\
<article class="phase-card">
  <h3>
    <a href="phases/{escape(phase["slug"])}.html">{escape(phase["label"])}</a>
    <span class="info-tooltip" tabindex="0"
      aria-label="Source : {escape(phase["source"])}"
      title="Source : {escape(phase["source"])}">i</span>
  </h3>
  <p>{escape(phase["states"][0]["nom"])} → {escape(phase["states"][-1]["nom"])}</p>
</article>"""
        for phase in phases
    )
    body = f"""\
{header(str(workflow["nom"]), catalog_href=catalog_href, has_reference_page=has_reference_page, workflow_slug=workflow_slug)}
<main class="layout">
  {render_sidebar(phase_links, root_prefix="")}
  <div class="content">
    <section class="panel">
      <h2>Vue d'ensemble</h2>
      <p>{escape(workflow.get("description", ""))}</p>
    </section>
    {diagram_panel("Vue d'ensemble des phases", flowchart)}
    {detail_diagram}
    <section class="panel">
      <h2>Phases du projet</h2>
      <div class="phase-grid">{cards}</div>
    </section>
  </div>
</main>
<footer>Site statique généré depuis les données validées.</footer>"""
    return page_shell(
        title=str(workflow["nom"]), body=body, mermaid_url=mermaid_url,
        theme_config=theme_config, theme_scope=theme_scope,
    )


def render_all_states_page(
    workflow: Mapping[str, Any],
    states: Sequence[Mapping[str, Any]],
    phases: Sequence[Mapping[str, Any]],
    mermaid_url: str,
    catalog_href: str | None = None,
    has_reference_page: bool = False,
    workflow_slug: str | None = None,
    theme_config: Mapping[str, str] | None = None,
    theme_scope: str = "standalone",
) -> str:
    phase_links = [(phase["label"], f'{phase["slug"]}.html') for phase in phases]
    phase_targets = {f'phases/{phase["slug"]}.html' for phase in phases}
    state_ids = {str(state["etat_id"]) for state in states}
    cards = "".join(
        state_card(
            state,
            link_prefix="",
            phase_targets=phase_targets,
            state_ids=state_ids,
            show_link_status=True,
        )
        for state in states
    )
    body = f"""\
{header(str(workflow["nom"]), catalog_href=catalog_href, has_reference_page=has_reference_page, workflow_slug=workflow_slug)}
<main class="layout">
  {render_sidebar(phase_links, root_prefix="")}
  <div class="content">
    <section class="panel">
      <h2>Répertoire des états</h2>
      <p>Cette page présente le texte des {len(states)} états du workflow.</p>
      <div class="state-grid">{cards}</div>
    </section>
  </div>
</main>"""
    return page_shell(
        title=f'Répertoire des états — {workflow["nom"]}',
        body=body,
        mermaid_url=mermaid_url,
        theme_config=theme_config,
        theme_scope=theme_scope,
    )


def render_all_transitions_page(
    workflow: Mapping[str, Any],
    states: Sequence[Mapping[str, Any]],
    transitions: Sequence[Mapping[str, Any]],
    phases: Sequence[Mapping[str, Any]],
    mermaid_url: str,
    catalog_href: str | None = None,
    has_reference_page: bool = False,
    workflow_slug: str | None = None,
    theme_config: Mapping[str, str] | None = None,
    theme_scope: str = "standalone",
) -> str:
    phase_links = [(phase["label"], f'{phase["slug"]}.html') for phase in phases]
    phase_targets = {f'phases/{phase["slug"]}.html' for phase in phases}
    state_by_id = {str(state["etat_id"]): state for state in states}
    state_ids = set(state_by_id)
    cards = "".join(
        f"""\
<article class="state-card" id="{escape(transition["transition_id"])}">
  <span class="badge">Transition</span>
  <h3>{escape(transition["libelle"])}</h3>
  <dl class="metadata">
    <dt>Identifiant</dt><dd>{escape(transition["transition_id"])}</dd>
    <dt>État source</dt><dd>{escape(state_by_id[transition["etat_source_id"]]["nom"])}</dd>
    <dt>État cible</dt><dd>{escape(state_by_id[transition["etat_cible_id"]]["nom"])}</dd>
  </dl>
  {record_link_status_html(
      transition,
      phase_targets=phase_targets,
      state_ids=state_ids,
  )}
</article>"""
        for transition in transitions
    )
    body = f"""\
{header(str(workflow["nom"]), catalog_href=catalog_href, has_reference_page=has_reference_page, workflow_slug=workflow_slug)}
<main class="layout">
  {render_sidebar(phase_links, root_prefix="")}
  <div class="content">
    <section class="panel">
      <h2>Répertoire des transitions</h2>
      <p>
        Cette page d’exemple présente les {len(transitions)} transitions du
        workflow, leur lien éventuel et la validité de sa destination.
      </p>
      <div class="state-grid">{cards}</div>
    </section>
  </div>
</main>"""
    return page_shell(
        title=f'Répertoire des transitions — {workflow["nom"]}',
        body=body,
        mermaid_url=mermaid_url,
        theme_config=theme_config,
        theme_scope=theme_scope,
    )


def render_phase_page(
    workflow: Mapping[str, Any],
    phase: Mapping[str, Any],
    phases: Sequence[Mapping[str, Any]],
    transitions: Sequence[Mapping[str, Any]],
    mermaid_url: str,
    catalog_href: str | None = None,
    waterlines: Sequence[Mapping[str, Any]] = (),
    participants: Sequence[Mapping[str, Any]] = (),
    diagram_config: Mapping[str, Any] | None = None,
    has_reference_page: bool = False,
    workflow_slug: str | None = None,
    theme_config: Mapping[str, str] | None = None,
    theme_scope: str = "standalone",
) -> str:
    phase_states = phase["states"]
    phase_ids = {state["etat_id"] for state in phase_states}
    related = [
        transition
        for transition in transitions
        if transition["etat_source_id"] in phase_ids
        and transition["etat_cible_id"] in phase_ids
    ]
    flowchart = generate_dataset_flowchart(
        workflow,
        phase_states,
        related,
        link_resolver=lambda state: record_link_href(state, "../"),
        waterlines=waterlines,
        participants=participants,
        lane_title_wrap=(diagram_config or {}).get("lane_title_wrap"),
    )
    cards = "".join(
        state_card(
            state,
            link_prefix="../",
            phase_targets={f'phases/{item["slug"]}.html' for item in phases},
            state_ids={str(item["etat_id"]) for item in phase_states},
        )
        for state in phase_states
    )
    phase_links = [(item["label"], f'{item["slug"]}.html') for item in phases]
    body = f"""\
{header(str(workflow["nom"]), "../", catalog_href, has_reference_page, workflow_slug)}
<main class="layout">
  {render_sidebar(phase_links, root_prefix="../")}
  <div class="content">
    <section class="panel">
      <span class="badge">Phase</span>
      <h2>{escape(phase["label"])}</h2>
      <p>Source : {escape(phase["source"])}</p>
      <p class="notice" data-mermaid-notice hidden>
        Mermaid n'a pas pu être chargé ou rendre ce diagramme. Le code source reste affiché.
      </p>
      <pre class="mermaid">{escape(flowchart)}</pre>
      <details class="diagram-source">
        <summary>Afficher le code Mermaid</summary>
        <pre class="code-block"><code>{escape(flowchart)}</code></pre>
      </details>
    </section>
    <section class="panel">
      <h2>États de la phase</h2>
      <div class="state-grid">{cards}</div>
    </section>
  </div>
</main>"""
    return page_shell(
        title=f'{phase["label"]} — {workflow["nom"]}',
        body=body,
        root_prefix="../",
        mermaid_url=mermaid_url,
        theme_config=theme_config,
        theme_scope=theme_scope,
    )


def load_reference_page(source: Path, file_name: str) -> Mapping[str, Any]:
    reference_path = source.parent / file_name
    reference = load_json(reference_path)
    if not isinstance(reference, Mapping):
        raise WorkflowDataError(f"La racine de {reference_path} doit être un objet.")
    title = reference.get("title")
    sections = reference.get("sections")
    if not isinstance(title, str) or not title:
        raise WorkflowDataError(f"{reference_path}: title doit être renseigné.")
    if not isinstance(sections, list) or not sections:
        raise WorkflowDataError(f"{reference_path}: sections doit être une liste non vide.")
    for index, section in enumerate(sections):
        if not isinstance(section, Mapping):
            raise WorkflowDataError(f"{reference_path}: sections[{index}] doit être un objet.")
        if not isinstance(section.get("id"), str) or not section["id"]:
            raise WorkflowDataError(f"{reference_path}: sections[{index}].id est requis.")
        if not isinstance(section.get("title"), str) or not section["title"]:
            raise WorkflowDataError(f"{reference_path}: sections[{index}].title est requis.")
        diagrams = section.get("diagrams", [])
        if not isinstance(diagrams, list):
            raise WorkflowDataError(f"{reference_path}: sections[{index}].diagrams doit être une liste.")
        for diagram_index, diagram in enumerate(diagrams):
            if not isinstance(diagram, Mapping) or not isinstance(diagram.get("source"), str):
                raise WorkflowDataError(
                    f"{reference_path}: sections[{index}].diagrams[{diagram_index}].source est requis."
                )
    return reference


def render_reference_page(
    workflow: Mapping[str, Any],
    reference: Mapping[str, Any],
    phases: Sequence[Mapping[str, Any]],
    mermaid_url: str,
    catalog_href: str | None = None,
    workflow_slug: str | None = None,
    theme_config: Mapping[str, str] | None = None,
    theme_scope: str = "standalone",
) -> str:
    section_items = "".join(
        f'<li><a href="#{escape(slug(str(section["id"])))}">'
        f'{escape(section["title"])}</a></li>'
        for section in reference["sections"]
    )
    sections_html: list[str] = []
    for section in reference["sections"]:
        diagrams_html: list[str] = []
        for diagram in section.get("diagrams", []):
            source = str(diagram["source"])
            rendered = ""
            if diagram.get("render", True):
                rendered = f"""\
<p class="notice" data-mermaid-notice hidden>
  Mermaid n'a pas pu rendre cet exemple. Son code reste disponible ci-dessous.
</p>
<pre class="mermaid">{escape(source)}</pre>"""
            support = str(diagram.get("support", "mermaid"))
            diagrams_html.append(
                f"""\
<article class="reference-example">
  <div class="reference-example-heading">
    <h3>{escape(diagram.get("title", "Exemple"))}</h3>
    <span class="support-tag support-{escape(support)}">{escape(diagram.get("support_label", support))}</span>
  </div>
  {sanitize_documentation(diagram.get("description_html", ""), "html")}
  {rendered}
  <details>
    <summary>Voir le code Mermaid</summary>
    <pre class="code-block"><code>{escape(source)}</code></pre>
  </details>
</article>"""
            )
        sections_html.append(
            f"""\
<section class="panel reference-section" id="{escape(slug(str(section['id'])))}">
  <h2>{escape(section['title'])}</h2>
  {sanitize_documentation(section.get('description_html', ''), 'html')}
  {''.join(diagrams_html)}
</section>"""
        )
    phase_items = "".join(
        f'<li><a href="phases/{escape(phase["slug"])}.html">'
        f'{escape(phase["label"])}</a></li>'
        for phase in phases
    )
    reference_navigation = f"""\
<div class="sidebar-wrapper">
  <button class="sidebar-toggle" type="button" data-sidebar-toggle
    aria-expanded="true" aria-controls="workflow-sidebar"
    aria-label="Masquer la navigation" title="Masquer la navigation">☰</button>
  <aside class="sidebar" id="workflow-sidebar">
    <strong>Sommaire du guide</strong>
    <ul>{section_items}</ul>
    <strong>Phases documentaires</strong>
    <ul>{phase_items}</ul>
  </aside>
</div>"""
    body = f"""\
{header(str(workflow['nom']), catalog_href=catalog_href, has_reference_page=True, workflow_slug=workflow_slug)}
<main class="layout reference-layout">
  {reference_navigation}
  <div class="content">
    <section class="panel">
      <span class="badge">Référence</span>
      <h2>{escape(reference['title'])}</h2>
      {sanitize_documentation(reference.get('introduction_html', ''), 'html')}
    </section>
    {''.join(sections_html)}
  </div>
</main>
<footer>Guide Mermaid local, généré avec le workflow de documentation.</footer>"""
    return page_shell(
        title=str(reference["title"]), body=body, mermaid_url=mermaid_url,
        theme_config=theme_config, theme_scope=theme_scope,
    )


def generate_single_site(
    source: Path,
    output: Path,
    schema: Path | None = None,
    workflow_id: str | None = None,
    mermaid_url: str = DEFAULT_MERMAID_URL,
    catalog_href: str | None = None,
) -> None:
    document = validate_source(source, schema)
    site_config = site_config_from_manifest(source)
    diagram_config = site_config.get("diagram", {})
    theme_config = site_config.get("theme", {"pair": "ocean", "mode": "system"})
    reference_file = site_config.get("reference_page")
    has_reference_page = bool(reference_file)
    current_workflow_slug = source.parent.name
    theme_scope = f"workflow-{current_workflow_slug}"
    overview_workflow_id = (
        workflow_id
        or site_config.get("overview_workflow_id")
    )
    detail_workflow_id = (
        site_config.get("detail_workflow_id")
        or workflow_id
    )
    overview_workflow, overview_states, overview_transitions, _, _ = workflow_context(
        document, overview_workflow_id
    )
    detail_workflow, states, transitions, _, _ = workflow_context(
        document, detail_workflow_id
    )
    overview_waterlines = [
        waterline
        for waterline in document.get("Ligne_eau", [])
        if waterline.get("workflow_id") == overview_workflow["workflow_id"]
    ]
    detail_waterlines = [
        waterline
        for waterline in document.get("Ligne_eau", [])
        if waterline.get("workflow_id") == detail_workflow["workflow_id"]
    ]
    overview_participants = [
        participant
        for participant in document.get("Participant", [])
        if participant.get("workflow_id") == overview_workflow["workflow_id"]
    ]
    detail_participants = [
        participant
        for participant in document.get("Participant", [])
        if participant.get("workflow_id") == detail_workflow["workflow_id"]
    ]
    phases = load_phase_map(source, states)

    obsolete_workflow_page = output / "workflow.html"
    if obsolete_workflow_page.exists():
        obsolete_workflow_page.unlink()
    site_mermaid_url = write_site_mermaid_assets(output, mermaid_url)
    write_text(output / "assets" / "style.css", site_css() + "\n")
    write_text(
        output / "assets" / "app.js",
        site_javascript(site_mermaid_url, diagram_config) + "\n",
    )
    write_text(
        output / "index.html",
        render_index(
            overview_workflow,
            overview_states,
            overview_transitions,
            phases,
            mermaid_url,
            catalog_href,
            overview_waterlines,
            overview_participants,
            detail_workflow,
            states,
            transitions,
            detail_waterlines,
            detail_participants,
            diagram_config,
            has_reference_page,
            current_workflow_slug,
            theme_config,
            theme_scope,
        ),
    )
    write_text(
        output / "etats.html",
        render_all_states_page(
            detail_workflow,
            states,
            phases,
            mermaid_url,
            catalog_href,
            has_reference_page,
            current_workflow_slug,
            theme_config,
            theme_scope,
        ),
    )
    write_text(
        output / "transitions.html",
        render_all_transitions_page(
            detail_workflow,
            states,
            transitions,
            phases,
            mermaid_url,
            catalog_href,
            has_reference_page,
            current_workflow_slug,
            theme_config,
            theme_scope,
        ),
    )
    for phase in phases:
        write_text(
            output / "phases" / f'{phase["slug"]}.html',
            render_phase_page(
                detail_workflow,
                phase,
                phases,
                transitions,
                mermaid_url,
                f"../{catalog_href}" if catalog_href else None,
                detail_waterlines,
                detail_participants,
                diagram_config,
                has_reference_page,
                current_workflow_slug,
                theme_config,
                theme_scope,
            ),
        )
    if reference_file:
        reference = load_reference_page(source, str(reference_file))
        write_text(
            output / "guide.html",
            render_reference_page(
                detail_workflow,
                reference,
                phases,
                mermaid_url,
                catalog_href,
                current_workflow_slug,
                theme_config,
                theme_scope,
            ),
        )
    write_text(
        output / "settings.html",
        render_settings_page(
            str(detail_workflow["nom"]), "index.html", theme_config=theme_config,
            theme_scope=theme_scope, catalog_href=catalog_href,
        ),
    )
    state_pages = output / "states"
    if state_pages.is_dir():
        for obsolete_page in state_pages.glob("*.html"):
            obsolete_page.unlink()
        try:
            state_pages.rmdir()
        except OSError:
            pass


def render_catalog_page(
    title: str,
    description: str,
    entries: Sequence[Mapping[str, Any]],
    theme_config: Mapping[str, str] | None = None,
    theme_scope: str = "catalog",
) -> str:
    cards = "".join(
        f"""\
<article class="phase-card">
  <h2><a href="{escape(entry["slug"])}/index.html">{escape(entry["label"])}</a></h2>
  <p>{escape(entry.get("description", ""))}</p>
  <p>
    <a href="{escape(entry["slug"])}/index.html">Ouvrir le workflow →</a>
    · <a href="editor.html?workflow={escape(entry["slug"])}">Modifier dans l’éditeur</a>
  </p>
</article>"""
        for entry in entries
    )
    body = f"""\
<header class="site-header">
  <h1>{escape(title)}</h1>
  <nav>
    <a href="editor.html">Éditeur JSON</a>
    <a href="settings.html">Paramètres d’affichage</a>
  </nav>
</header>
<main class="layout">
  <div class="content" style="grid-column: 1 / -1">
    <section class="panel">
      <h2>Choisir un workflow</h2>
      <p>{escape(description)}</p>
      <div class="phase-grid">{cards}</div>
      <p><a class="button" href="editor.html">Éditer un workflow au format JSON</a></p>
    </section>
  </div>
</main>"""
    return page_shell(
        title=title, body=body, theme_config=theme_config, theme_scope=theme_scope
    )


def render_settings_page(
    title: str,
    home_href: str = "index.html",
    editor_href: str | None = None,
    theme_config: Mapping[str, str] | None = None,
    theme_scope: str = "standalone",
    catalog_href: str | None = None,
) -> str:
    selected_theme = dict(theme_config or {"pair": "ocean", "mode": "system"})
    pair_label = {
        "ocean": "Océan",
        "forest": "Forêt",
        "aubergine": "Aubergine",
        "graphite": "Graphite",
    }.get(str(selected_theme.get("pair")), "Océan")
    mode_label = {
        "system": "automatique",
        "light": "clair",
        "dark": "sombre",
    }.get(str(selected_theme.get("mode")), "automatique")
    editor_link = (
        f'<a href="{escape(editor_href)}">Éditeur JSON</a>' if editor_href else ""
    )
    catalog_link = (
        f'<a href="{escape(catalog_href)}">Catalogue commun</a>'
        if catalog_href else ""
    )
    previews = "".join(
        f"""\
<article class="theme-preview" data-pair="{pair}">
  <div class="theme-preview-bars">
    <div class="theme-preview-light"><strong>{escape(label)}</strong><br>Mode clair</div>
    <div class="theme-preview-dark"><strong>{escape(label)}</strong><br>Mode sombre</div>
  </div>
</article>"""
        for pair, label in (
            ("ocean", "Océan"),
            ("forest", "Forêt"),
            ("aubergine", "Aubergine"),
            ("graphite", "Graphite"),
        )
    )
    body = f"""\
<header class="site-header">
  <h1><a href="{escape(home_href)}">{escape(title)}</a></h1>
  <nav>
    <a href="{escape(home_href)}">Retour aux workflows</a>
    {catalog_link}
    {editor_link}
    <a href="settings.html" aria-current="page">Paramètres d’affichage</a>
  </nav>
</header>
<main class="editor-shell">
  <section class="panel">
    <span class="badge">Apparence</span>
    <h2>Paramètres d’affichage</h2>
    <p>
      Choisissez une paire de couleurs puis le mode clair, sombre ou automatique.
      Le choix est enregistré localement dans ce navigateur et ne nécessite aucun accès Internet.
    </p>
    <form class="settings-form" id="theme-settings">
      <label for="theme-pair">
        Paire de thèmes
        <select id="theme-pair" name="theme-pair">
          <option value="ocean">Océan</option>
          <option value="forest">Forêt</option>
          <option value="aubergine">Aubergine</option>
          <option value="graphite">Graphite</option>
        </select>
      </label>
      <label for="theme-mode">
        Mode
        <select id="theme-mode" name="theme-mode">
          <option value="system">Automatique — réglage du système</option>
          <option value="light">Clair</option>
          <option value="dark">Sombre</option>
        </select>
      </label>
      <div class="editor-actions">
        <button class="button button-secondary" id="reset-theme" type="button">
          Rétablir {escape(pair_label)} / {escape(mode_label)}
        </button>
      </div>
      <p class="editor-status" id="theme-status" role="status" aria-live="polite"></p>
    </form>
  </section>
  <section class="panel">
    <h2>Paires disponibles</h2>
    <div class="settings-grid">{previews}</div>
  </section>
</main>"""
    return page_shell(
        title=f"Paramètres d’affichage — {title}", body=body,
        theme_config=theme_config, theme_scope=theme_scope,
    )


def render_editor_page(
    title: str,
    entries: Sequence[Mapping[str, Any]],
    theme_config: Mapping[str, str] | None = None,
    theme_scope: str = "catalog",
) -> str:
    payload = {
        "workflows": [
            {
                "slug": entry["slug"],
                "label": entry["label"],
                "workflow_id": entry["workflow_id"],
                "document": entry["document"],
                "document_path": entry["document_path"],
                "document_display_path": entry["document_display_path"],
                "manifest_path": entry["manifest_path"],
                "source_paths": entry["source_paths"],
            }
            for entry in entries
        ]
    }
    encoded_payload = (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    state_types = "".join(
        f'<option value="{value}">{label}</option>'
        for value, label in (
            ("initial", "Initial"),
            ("normal", "Normal"),
            ("validation", "Validation"),
            ("blocage", "Blocage"),
            ("final", "Final"),
        )
    )
    body = f"""\
<header class="site-header">
  <h1><a href="index.html">{escape(title)}</a></h1>
  <nav>
    <a href="index.html">Choisir un workflow</a>
    <a href="editor.html" aria-current="page">Éditeur JSON</a>
    <a href="settings.html">Paramètres d’affichage</a>
  </nav>
</header>
<main class="editor-shell">
  <section class="panel">
    <h2>Éditeur de workflow</h2>
    <p>
      Sélectionnez un workflow, modifiez ses états et transitions, puis
      enregistrez le document JSON fusionné. Cette page statique ne modifie
      jamais silencieusement les fichiers sources du projet : le navigateur
      vous demandera où enregistrer le JSON. Les autres tables (rôles, règles,
      lignes d'eau…) restent modifiables dans l'éditeur JSON complet.
    </p>
    <div class="editor-toolbar">
      <label for="workflow-source">
        Workflow source
        <select id="workflow-source"></select>
      </label>
      <button class="button button-secondary" id="reset-workflow" type="button">
        Annuler les modifications
      </button>
      <a class="button button-secondary" id="workflow-site-link" href="#">
        Ouvrir le workflow
      </a>
    </div>
    <div class="source-location" aria-live="polite">
      <h3>Origine du document utilisé pour générer le site</h3>
      <dl class="metadata">
        <dt>Document JSON complet</dt>
        <dd><a id="workflow-document-link" href="#"><code
          id="workflow-document-path"></code></a></dd>
        <dt>Manifeste lu</dt>
        <dd><code id="workflow-manifest-path"></code></dd>
        <dt>Fragments JSON assemblés</dt>
        <dd><ul id="workflow-source-paths"></ul></dd>
      </dl>
      <p class="editor-status">
        Le document complet est la copie fusionnée exacte de cette génération.
        Pour modifier durablement la prochaine génération, éditez le manifeste
        ou les fragments sources listés ci-dessus, puis régénérez le site.
      </p>
    </div>
    <h3 id="editor-title"></h3>
    <div class="editor-summary" id="editor-summary"></div>
    <p class="editor-status" id="editor-status" role="status" aria-live="polite"></p>
  </section>

  <div class="editor-layout-controls">
    <button class="button button-secondary" id="toggle-editor-layout"
      type="button" aria-pressed="false">
      Placer les transitions en dessous
    </button>
  </div>
  <div class="editor-grid" id="editor-grid">
    <section class="panel">
      <h2>États</h2>
      <p>
        <a class="button button-secondary" id="state-inventory-link"
          href="#" target="_blank" rel="noopener">
          Ouvrir le répertoire des états
        </a>
      </p>
      <form class="editor-form" id="state-form">
        <label class="field-wide">
          Identifiant
          <select id="state-picker">
            <option value="">Nouvel état…</option>
          </select>
        </label>
        <label class="field-wide" id="state-new-id-field">
          Nouvel identifiant
          <input id="state-id" pattern="[A-Za-z_][A-Za-z0-9_]*"
            placeholder="Etat_a_valider">
        </label>
        <label>
          Nom
          <input id="state-name" required placeholder="État à valider">
        </label>
        <label>
          Type
          <select id="state-type">{state_types}</select>
        </label>
        <label>
          Ordre
          <input id="state-order" type="number" step="1">
        </label>
        <label class="field-wide">
          Ligne d'eau
          <select id="state-waterline"></select>
        </label>
        <label>
          Format du texte de l'état
          <select id="state-content-type">
            <option value="markdown">Markdown</option>
            <option value="html">HTML</option>
            <option value="texte">Texte brut</option>
          </select>
        </label>
        <label class="field-wide">
          Texte de l'état
          <textarea id="state-content"
            placeholder="## Informations&#10;&#10;Consultez la [documentation](https://example.org)."></textarea>
        </label>
        <label>
          Type de lien de l'état
          <select id="state-link-type">
            <option value="">Aucun lien</option>
            <option value="page_phase">Page de phase</option>
            <option value="page_etat" disabled>
              Page individuelle d'état (obsolète)
            </option>
            <option value="url">URL HTTP(S)</option>
          </select>
        </label>
        <label>
          Destination du lien
          <input id="state-link-target" placeholder="https://example.org">
        </label>
        <label class="field-wide">
          Libellé du lien
          <input id="state-link-label" placeholder="Ouvrir la ressource">
        </label>
        <div class="editor-actions field-wide">
          <button class="button" id="state-submit" type="submit">Ajouter l’état</button>
          <button class="button button-secondary" id="state-cancel"
            type="button" hidden>Annuler</button>
          <button class="button button-danger" id="state-delete"
            type="button" hidden>Supprimer l’état</button>
        </div>
      </form>
      <p class="editor-status">
        Choisissez un état existant dans la liste de l'identifiant pour le
        modifier, ou sélectionnez « Nouvel état… » pour en créer un.
      </p>
    </section>

    <section class="panel">
      <h2>Transitions</h2>
      <form class="editor-form" id="transition-form">
        <label class="field-wide">
          Identifiant
          <select id="transition-picker">
            <option value="">Nouvelle transition…</option>
          </select>
        </label>
        <label class="field-wide" id="transition-new-id-field">
          Nouvel identifiant
          <input id="transition-id" pattern="[A-Za-z_][A-Za-z0-9_]*"
            autocomplete="off" placeholder="Valider_etat">
        </label>
        <label>
          État source
          <select id="transition-source" required></select>
        </label>
        <label>
          État cible
          <select id="transition-target" required></select>
        </label>
        <label class="field-wide">
          Libellé
          <input id="transition-label" required placeholder="validation accordée">
        </label>
        <label>
          Rôle autorisé
          <select id="transition-role"></select>
        </label>
        <label>
          <span>Activation</span>
          <span><input id="transition-active" type="checkbox" checked> Active</span>
        </label>
        <label class="field-wide">
          Condition
          <textarea id="transition-condition"></textarea>
        </label>
        <label>
          Type de lien de la transition
          <select id="transition-link-type">
            <option value="">Aucun lien</option>
            <option value="page_phase">Page de phase</option>
            <option value="page_etat" disabled>
              Page individuelle d'état (obsolète)
            </option>
            <option value="url">URL HTTP(S)</option>
          </select>
        </label>
        <label>
          Destination du lien
          <input id="transition-link-target" placeholder="https://example.org">
        </label>
        <label class="field-wide">
          Libellé du lien
          <input id="transition-link-label" placeholder="Ouvrir la ressource">
        </label>
        <div class="editor-actions field-wide">
          <button class="button" id="transition-submit" type="submit">
            Ajouter la transition
          </button>
          <button class="button button-secondary" id="transition-cancel"
            type="button" hidden>Annuler</button>
          <button class="button button-danger" id="transition-delete"
            type="button" hidden>Supprimer la transition</button>
        </div>
      </form>
      <p class="editor-status">
        Choisissez une transition existante dans la liste de l'identifiant
        pour la modifier, ou saisissez un nouvel identifiant pour en créer une.
      </p>
    </section>
  </div>

  <section class="panel">
    <h2>Validité des liens des états et des transitions</h2>
    <p>
      Le contrôle porte sur les liens structurés des états et des transitions,
      ainsi que sur les liens HTML ou Markdown trouvés dans leur texte.
      Il vérifie le format, le protocole et les références internes ; la
      disponibilité distante d'une URL HTTP(S) n'est pas testée. Un lien
      invalide est un avertissement : il ne bloque ni la copie ni le
      téléchargement du JSON.
    </p>
    <div class="link-alert" id="invalid-link-alert" role="alert" hidden></div>
    <div class="editor-summary" id="link-summary"></div>
    <p class="editor-empty" id="link-empty" hidden>Aucun lien détecté.</p>
    <table class="editor-table">
      <thead><tr>
        <th>Élément</th><th>Type</th><th>Origine</th><th>Cible</th><th>Validité</th>
      </tr></thead>
      <tbody id="link-rows"></tbody>
    </table>
  </section>

  <section class="panel">
    <h2>Vocabulaire à employer</h2>
    <dl class="metadata vocabulary-list">
      <dt>Workflow</dt><dd>Processus complet décrit par le document JSON.</dd>
      <dt>État</dt><dd>Situation stable du workflow.</dd>
      <dt>Texte de l'état</dt>
      <dd>Contenu unique de l'état, saisi en Markdown, HTML ou texte brut.</dd>
      <dt>Format du texte</dt><dd>Markdown, HTML ou texte brut.</dd>
      <dt>Lien de l'état</dt><dd>Lien structuré facultatif porté par l'état.</dd>
      <dt>Lien de la transition</dt>
      <dd>Lien structuré facultatif porté par la transition.</dd>
      <dt>Destination du lien</dt><dd>URL ou page visée par le lien.</dd>
      <dt>Transition</dt><dd>Passage autorisé d'un état source à un état cible.</dd>
      <dt>Répertoire des états</dt>
      <dd>Page regroupant les états ; il n'existe plus de page individuelle.</dd>
      <dt>Répertoire des transitions</dt>
      <dd>Page regroupant les transitions et la validité de leurs liens.</dd>
    </dl>
  </section>

  <section class="panel">
    <h2>Document JSON complet</h2>
    <p>
      Cette zone permet aussi de modifier directement les workflows, rôles,
      règles, lignes d'eau et métadonnées. Appliquez le JSON pour
      resynchroniser les formulaires. Les modifications restent dans cette
      page jusqu'à l'utilisation du bouton « Enregistrer le JSON sous… ».
    </p>
    <textarea class="json-editor" id="json-output" spellcheck="false"
      aria-label="Document JSON du workflow"></textarea>
    <div class="editor-actions">
      <button class="button button-secondary" id="apply-json" type="button">
        Appliquer le JSON
      </button>
      <button class="button button-secondary" id="copy-json" type="button">
        Copier le JSON
      </button>
      <button class="button" id="download-json" type="button">
        Enregistrer le JSON sous…
      </button>
    </div>
    <p class="editor-status" id="save-method-note"></p>
    <div class="validation-summary" id="json-validation" role="status"
      aria-live="polite"></div>
  </section>
</main>
<script id="workflow-editor-data" type="application/json">{encoded_payload}</script>
<script defer src="assets/editor.js"></script>"""
    return page_shell(
        title=f"Éditeur JSON — {title}", body=body,
        theme_config=theme_config, theme_scope=theme_scope,
    )


def generate_catalog_site(
    source: Path,
    output: Path,
    mermaid_url: str = DEFAULT_MERMAID_URL,
) -> None:
    catalog, entries = load_catalog(source)
    catalog_theme = theme_config_from_catalog(catalog)
    editor_entries = []
    for entry in entries:
        document = validate_source(entry["manifest"])
        _, source_paths = load_manifest(entry["manifest"])
        config = site_config_from_manifest(entry["manifest"])
        workflow_id = config.get("detail_workflow_id")
        if not workflow_id:
            workflows = document.get("Workflow", [])
            if not workflows:
                raise WorkflowDataError(
                    f"Le workflow {entry['label']} ne contient aucune définition."
                )
            workflow_id = str(workflows[0]["workflow_id"])
        document_path = Path("sources") / f'{entry["slug"]}.json'
        write_text(
            output / document_path,
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        )
        editor_entries.append(
            {
                **entry,
                "workflow_id": workflow_id,
                "document": document,
                "document_path": document_path.as_posix(),
                "document_display_path": display_path(output / document_path),
                "manifest_path": display_path(entry["manifest"]),
                "source_paths": [display_path(path) for path in source_paths],
            }
        )
    site_mermaid_url = write_site_mermaid_assets(output, mermaid_url)
    write_text(output / "assets" / "style.css", site_css() + "\n")
    write_text(
        output / "assets" / "app.js", site_javascript(site_mermaid_url) + "\n"
    )
    write_text(
        output / "assets" / "editor.js",
        workflow_editor_javascript() + "\n",
    )
    write_text(
        output / "index.html",
        render_catalog_page(
            str(catalog.get("title", "Workflows")),
            str(catalog.get("description", "")),
            entries,
            catalog_theme,
            "catalog",
        ),
    )
    write_text(
        output / "editor.html",
        render_editor_page(
            str(catalog.get("title", "Workflows")),
            editor_entries,
            catalog_theme,
            "catalog",
        ),
    )
    write_text(
        output / "settings.html",
        render_settings_page(
            str(catalog.get("title", "Workflows")),
            "index.html",
            "editor.html",
            theme_config=catalog_theme,
            theme_scope="catalog",
        ),
    )
    for entry in entries:
        generate_single_site(
            entry["manifest"],
            output / entry["slug"],
            mermaid_url=mermaid_url,
            catalog_href="../index.html",
        )


def generate_site(
    source: Path,
    output: Path,
    schema: Path | None = None,
    workflow_id: str | None = None,
    mermaid_url: str = DEFAULT_MERMAID_URL,
    catalog_href: str | None = None,
) -> None:
    source_document = load_json(source)
    if is_catalog(source_document):
        if schema is not None or workflow_id is not None or catalog_href is not None:
            raise WorkflowDataError(
                "--schema, --workflow-id et --catalog-href ne s'appliquent pas à un catalogue."
            )
        generate_catalog_site(source, output, mermaid_url)
        return
    generate_single_site(
        source,
        output,
        schema,
        workflow_id,
        mermaid_url,
        catalog_href=catalog_href,
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Génère un site statique navigable pour un workflow."
    )
    parser.add_argument("source", type=Path, help="Données JSON ou manifeste.")
    parser.add_argument("--schema", type=Path, help="Schéma pour un fichier unique.")
    parser.add_argument("--workflow-id", help="Workflow à sélectionner.")
    parser.add_argument("--output", type=Path, required=True, help="Répertoire produit.")
    parser.add_argument(
        "--mermaid-url",
        default=DEFAULT_MERMAID_URL,
        help="URL du module JavaScript Mermaid.",
    )
    parser.add_argument(
        "--catalog-href",
        help="Lien relatif vers l'accueil commun, pour la génération d'un seul workflow.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        generate_site(
            args.source,
            args.output,
            args.schema,
            args.workflow_id,
            args.mermaid_url,
            args.catalog_href,
        )
        print(f"Site statique généré: {args.output / 'index.html'}")
        return 0
    except (DataValidationError, WorkflowDataError, OSError) as error:
        print(f"Erreur: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
