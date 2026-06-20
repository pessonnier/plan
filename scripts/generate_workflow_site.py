#!/usr/bin/env python3
"""Generate a navigable static site for a workflow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from generate_mermaid import (
    generate_dataset_flowchart,
)
from html_rendering import (
    DEFAULT_MERMAID_URL,
    diagram_panel,
    escape,
    page_shell,
    record_link_href,
    render_sidebar,
    site_css,
    site_javascript,
    slug,
    state_card,
    state_description,
    workflow_context,
    write_text,
)
from validate_workflow_data import DataValidationError, validate_source
from workflow_data import (
    WorkflowDataError,
    is_manifest,
    load_json,
    load_manifest,
    site_config_from_manifest,
)


def phase_label(path: Path) -> str:
    labels = {
        "01-cadrage-budgetisation": "Cadrage et programmation budgétaire",
        "02-specifications-conception-marche": "Conception et commande publique",
        "03-realisation-qualification": "Réalisation et qualification",
        "04-mise-en-production": "Mise en service",
        "05-maintenance": "Exploitation et maintenance",
        "06-decommissionnement": "Décommissionnement",
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


def header(title: str, root_prefix: str = "") -> str:
    return f"""\
<header class="site-header">
  <h1><a href="{escape(root_prefix)}index.html">{escape(title)}</a></h1>
  <nav>
    <a href="{escape(root_prefix)}index.html">Vue d'ensemble et phases</a>
    <a href="{escape(root_prefix)}etats.html">Tous les états</a>
  </nav>
</header>"""


def render_index(
    workflow: Mapping[str, Any],
    overview_states: Sequence[Mapping[str, Any]],
    overview_transitions: Sequence[Mapping[str, Any]],
    detail_states: Sequence[Mapping[str, Any]],
    phases: Sequence[Mapping[str, Any]],
    mermaid_url: str,
) -> str:
    phase_links = [(phase["label"], f'{phase["slug"]}.html') for phase in phases]
    flowchart = generate_dataset_flowchart(
        workflow,
        overview_states,
        overview_transitions,
        link_resolver=lambda state: record_link_href(state),
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
{header(str(workflow["nom"]))}
<main class="layout">
  {render_sidebar(phase_links, detail_states, root_prefix="", show_states=False)}
  <div class="content">
    <section class="panel">
      <h2>Vue d'ensemble</h2>
      <p>{escape(workflow.get("description", ""))}</p>
    </section>
    {diagram_panel("Vue d'ensemble des phases", flowchart)}
    <section class="panel">
      <h2>Phases du projet</h2>
      <div class="phase-grid">{cards}</div>
    </section>
  </div>
</main>
<footer>Site statique généré depuis les données validées.</footer>"""
    return page_shell(title=str(workflow["nom"]), body=body, mermaid_url=mermaid_url)


def render_all_states_page(
    workflow: Mapping[str, Any],
    states: Sequence[Mapping[str, Any]],
    phases: Sequence[Mapping[str, Any]],
    mermaid_url: str,
) -> str:
    phase_links = [(phase["label"], f'{phase["slug"]}.html') for phase in phases]
    cards = "".join(
        state_card(state, f"states/{state['etat_id']}.html", link_prefix="")
        for state in states
    )
    body = f"""\
{header(str(workflow["nom"]))}
<main class="layout">
  {render_sidebar(phase_links, states, root_prefix="")}
  <div class="content">
    <section class="panel">
      <h2>Tous les états</h2>
      <p>Cette page présente les {len(states)} états détaillés du workflow.</p>
      <div class="state-grid">{cards}</div>
    </section>
  </div>
</main>"""
    return page_shell(
        title=f'Tous les états — {workflow["nom"]}',
        body=body,
        mermaid_url=mermaid_url,
    )


def render_phase_page(
    workflow: Mapping[str, Any],
    phase: Mapping[str, Any],
    phases: Sequence[Mapping[str, Any]],
    all_states: Sequence[Mapping[str, Any]],
    transitions: Sequence[Mapping[str, Any]],
    mermaid_url: str,
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
    )
    cards = "".join(
        state_card(
            state,
            f"../states/{state['etat_id']}.html",
            link_prefix="../",
        )
        for state in phase_states
    )
    phase_links = [(item["label"], f'{item["slug"]}.html') for item in phases]
    body = f"""\
{header(str(workflow["nom"]), "../")}
<main class="layout">
  {render_sidebar(phase_links, all_states, root_prefix="../")}
  <div class="content">
    <section class="panel">
      <span class="badge">Phase</span>
      <h2>{escape(phase["label"])}</h2>
      <p>Source : {escape(phase["source"])}</p>
    </section>
    {diagram_panel("Transitions de la phase", flowchart)}
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
    )


def render_state_page(
    workflow: Mapping[str, Any],
    state: Mapping[str, Any],
    states: Sequence[Mapping[str, Any]],
    transitions: Sequence[Mapping[str, Any]],
    rules: Sequence[Mapping[str, Any]],
    roles: Mapping[str, Mapping[str, Any]],
    phases: Sequence[Mapping[str, Any]],
    mermaid_url: str,
) -> str:
    position = next(index for index, item in enumerate(states) if item == state)
    previous_state = states[position - 1] if position else None
    next_state = states[position + 1] if position + 1 < len(states) else None
    incoming = [item for item in transitions if item["etat_cible_id"] == state["etat_id"]]
    outgoing = [item for item in transitions if item["etat_source_id"] == state["etat_id"]]
    related_rules = [
        rule
        for rule in rules
        if rule.get("etat_id") == state["etat_id"]
        or rule.get("transition_id")
        in {item["transition_id"] for item in incoming + outgoing}
    ]
    state_index = {item["etat_id"]: item for item in states}

    def transition_items(items: Sequence[Mapping[str, Any]], incoming_side: bool) -> str:
        rendered = []
        for transition in items:
            other_id = (
                transition["etat_source_id"]
                if incoming_side
                else transition["etat_cible_id"]
            )
            role = roles.get(transition.get("role_autorise"))
            role_text = f" — {escape(role['nom'])}" if role else ""
            transition_href = record_link_href(transition, "../")
            transition_link = (
                f' — <a href="{escape(transition_href)}">'
                f'{escape(transition.get("libelle_lien") or "Ouvrir")}</a>'
                if transition_href
                else ""
            )
            rendered.append(
                f'<li><a href="{escape(other_id)}.html">'
                f'{escape(state_index[other_id]["nom"])}</a> : '
                f'{escape(transition["libelle"])}{role_text}{transition_link}</li>'
            )
        return "".join(rendered) or "<li>Aucune</li>"

    rule_items = "".join(
        f"<li><strong>{escape(rule['nom'])}</strong> — "
        f"{escape(rule.get('expression', ''))}<br>"
        f"{escape(rule.get('message_erreur', ''))}</li>"
        for rule in related_rules
    ) or "<li>Aucune règle associée.</li>"
    previous_link = (
        f'<a href="{escape(previous_state["etat_id"])}.html">← '
        f'{escape(previous_state["nom"])}</a>'
        if previous_state
        else "<span></span>"
    )
    next_link = (
        f'<a href="{escape(next_state["etat_id"])}.html">'
        f'{escape(next_state["nom"])} →</a>'
        if next_state
        else "<span></span>"
    )
    phase_links = [(phase["label"], f'{phase["slug"]}.html') for phase in phases]
    state_navigation_href = record_link_href(state, "../")
    state_navigation = (
        f'<p><a href="{escape(state_navigation_href)}">'
        f'{escape(state.get("libelle_lien") or "Ouvrir la page associée")} →</a></p>'
        if state_navigation_href
        else ""
    )
    body = f"""\
{header(str(workflow["nom"]), "../")}
<main class="layout">
  {render_sidebar(phase_links, states, root_prefix="../")}
  <div class="content">
    <nav class="pager">{previous_link}{next_link}</nav>
    <article class="panel">
      <span class="badge">{escape(state["type_etat"])}</span>
      <h2>{escape(state["nom"])}</h2>
      <div>{state_description(state)}</div>
      <dl class="metadata">
        <dt>Identifiant</dt><dd>{escape(state["etat_id"])}</dd>
        <dt>Ordre</dt><dd>{escape(state.get("ordre", ""))}</dd>
      </dl>
      {state_navigation}
    </article>
    <section class="panel">
      <h2>Transitions entrantes</h2>
      <ul class="transition-list">{transition_items(incoming, True)}</ul>
      <h2>Transitions sortantes</h2>
      <ul class="transition-list">{transition_items(outgoing, False)}</ul>
    </section>
    <section class="panel">
      <h2>Contrôles associés</h2>
      <ul class="transition-list">{rule_items}</ul>
    </section>
    <nav class="pager">{previous_link}{next_link}</nav>
  </div>
</main>"""
    return page_shell(
        title=f'{state["nom"]} — {workflow["nom"]}',
        body=body,
        root_prefix="../",
        mermaid_url=mermaid_url,
    )


def generate_site(
    source: Path,
    output: Path,
    schema: Path | None = None,
    workflow_id: str | None = None,
    mermaid_url: str = DEFAULT_MERMAID_URL,
) -> None:
    document = validate_source(source, schema)
    site_config = site_config_from_manifest(source)
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
    detail_workflow, states, transitions, rules, roles = workflow_context(
        document, detail_workflow_id
    )
    phases = load_phase_map(source, states)

    obsolete_workflow_page = output / "workflow.html"
    if obsolete_workflow_page.exists():
        obsolete_workflow_page.unlink()
    write_text(output / "assets" / "style.css", site_css() + "\n")
    write_text(output / "assets" / "app.js", site_javascript(mermaid_url) + "\n")
    write_text(
        output / "index.html",
        render_index(
            overview_workflow,
            overview_states,
            overview_transitions,
            states,
            phases,
            mermaid_url,
        ),
    )
    write_text(
        output / "etats.html",
        render_all_states_page(
            detail_workflow,
            states,
            phases,
            mermaid_url,
        ),
    )
    for phase in phases:
        write_text(
            output / "phases" / f'{phase["slug"]}.html',
            render_phase_page(
                detail_workflow, phase, phases, states, transitions, mermaid_url
            ),
        )
    for state in states:
        write_text(
            output / "states" / f'{state["etat_id"]}.html',
            render_state_page(
                detail_workflow,
                state,
                states,
                transitions,
                rules,
                roles,
                phases,
                mermaid_url,
            ),
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
        )
        print(f"Site statique généré: {args.output / 'index.html'}")
        return 0
    except (DataValidationError, WorkflowDataError, OSError) as error:
        print(f"Erreur: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
