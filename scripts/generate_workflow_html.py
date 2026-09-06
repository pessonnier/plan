#!/usr/bin/env python3
"""Generate one HTML page containing workflow diagrams and state documentation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from html_rendering import (
    DEFAULT_MERMAID_URL,
    diagram_panel,
    escape,
    page_shell,
    state_card,
    workflow_context,
    write_text,
)
from generate_mermaid import (
    generate_dataset_flowchart,
    select_participants,
    select_waterlines,
)
from validate_workflow_data import DataValidationError, validate_source
from workflow_data import WorkflowDataError, site_config_from_manifest


def render_workflow_page(
    source: Path,
    schema: Path | None = None,
    workflow_id: str | None = None,
    mermaid_url: str = DEFAULT_MERMAID_URL,
) -> str:
    document = validate_source(source, schema)
    site_config = site_config_from_manifest(source)
    diagram_config = site_config.get("diagram", {})
    workflow, states, transitions, _, _ = workflow_context(document, workflow_id)
    participants = select_participants(document, str(workflow["workflow_id"]))
    waterlines = select_waterlines(
        document, str(workflow["workflow_id"]), states, participants
    )
    flowchart = generate_dataset_flowchart(
        workflow,
        states,
        transitions,
        waterlines=waterlines,
        participants=participants,
        lane_title_wrap=diagram_config.get("lane_title_wrap"),
    )
    cards = "\n".join(state_card(state) for state in states)
    body = f"""\
<header class="site-header">
  <h1>{escape(workflow["nom"])}</h1>
  <p>{escape(workflow.get("description", ""))}</p>
</header>
<main class="layout">
  <div class="content" style="grid-column: 1 / -1">
    {diagram_panel("Vue processus", flowchart)}
    <section class="panel">
      <h2>Textes des états</h2>
      <div class="state-grid">
        {cards}
      </div>
    </section>
  </div>
</main>
<footer>Documentation statique générée depuis le modèle de workflow.</footer>"""
    return page_shell(
        title=str(workflow["nom"]),
        body=body,
        mermaid_url=mermaid_url,
        inline_assets=True,
        diagram_config=diagram_config,
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Génère une page HTML documentant un workflow."
    )
    parser.add_argument("source", type=Path, help="Données JSON ou manifeste.")
    parser.add_argument("--schema", type=Path, help="Schéma pour un fichier unique.")
    parser.add_argument("--workflow-id", help="Workflow à sélectionner.")
    parser.add_argument("--output", type=Path, required=True, help="Page HTML produite.")
    parser.add_argument(
        "--mermaid-url",
        default=DEFAULT_MERMAID_URL,
        help="URL du module JavaScript Mermaid.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        page = render_workflow_page(
            args.source, args.schema, args.workflow_id, args.mermaid_url
        )
        write_text(args.output, page)
        print(f"Page HTML générée: {args.output}")
        return 0
    except (DataValidationError, WorkflowDataError, OSError) as error:
        print(f"Erreur: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
