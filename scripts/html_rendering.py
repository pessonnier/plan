"""Shared HTML rendering helpers for workflow documentation."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from generate_mermaid import (
    generate_dataset_flowchart,
    generate_dataset_state_diagram,
    select_workflow,
    state_sort_key,
    transition_sort_key,
)


DEFAULT_MERMAID_URL = (
    "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs"
)
SAFE_TAGS = {
    "p",
    "ul",
    "ol",
    "li",
    "strong",
    "em",
    "b",
    "i",
    "code",
    "pre",
    "br",
    "a",
}
SAFE_LINK = re.compile(r"^(?:https?://|mailto:|#)", re.IGNORECASE)


class DescriptionSanitizer(HTMLParser):
    """Allow a small documentation-oriented HTML subset."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag not in SAFE_TAGS:
            return
        if tag == "a":
            href = next((value for name, value in attrs if name == "href"), None)
            if href and SAFE_LINK.match(href):
                self.parts.append(
                    f'<a href="{html.escape(href, quote=True)}" rel="noreferrer">'
                )
                return
            self.parts.append("<a>")
            return
        self.parts.append(f"<{tag}>")

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag == "br":
            self.parts.append("<br>")

    def handle_endtag(self, tag: str) -> None:
        if tag in SAFE_TAGS and tag != "br":
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.parts.append(html.escape(data))

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&amp;{html.escape(name)};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&amp;#{html.escape(name)};")


def sanitize_documentation(value: Any, content_type: str | None = "html") -> str:
    text = "" if value is None else str(value)
    if content_type != "html":
        return f"<p>{html.escape(text)}</p>" if text else ""
    sanitizer = DescriptionSanitizer()
    sanitizer.feed(text)
    sanitizer.close()
    return "".join(sanitizer.parts)


def escape(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-").lower() or "page"


def record_link_href(record: Mapping[str, Any], root_prefix: str = "") -> str | None:
    target = record.get("cible_lien")
    if not isinstance(target, str) or not target:
        return None
    if record.get("type_lien") == "url":
        return target
    return f"{root_prefix}{target}"


def page_shell(
    *,
    title: str,
    body: str,
    root_prefix: str = "",
    mermaid_url: str = DEFAULT_MERMAID_URL,
    inline_assets: bool = False,
) -> str:
    escaped_title = escape(title)
    if inline_assets:
        styles = f"<style>\n{site_css()}\n</style>"
        script = f"<script>\n{site_javascript(mermaid_url)}\n</script>"
    else:
        styles = f'<link rel="stylesheet" href="{escape(root_prefix)}assets/style.css">'
        script = (
            f'<script defer src="{escape(root_prefix)}assets/app.js"></script>'
        )
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  {styles}
</head>
<body>
{body}
{script}
</body>
</html>
"""


def site_css() -> str:
    return """\
:root {
  color-scheme: light;
  --bg: #f4f6f8;
  --surface: #ffffff;
  --text: #17212b;
  --muted: #5c6b78;
  --line: #d9e0e6;
  --accent: #075985;
  --accent-soft: #e0f2fe;
  --warning: #9a3412;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); line-height: 1.55; }
a { color: var(--accent); }
.site-header { background: #102a43; color: white; padding: 1rem 1.5rem; }
.site-header a { color: white; text-decoration: none; }
.site-header nav { display: flex; flex-wrap: wrap; gap: 1rem; margin-top: .5rem; }
.layout { display: grid; grid-template-columns: minmax(14rem, 20rem) 1fr; gap: 1.5rem;
  max-width: 96rem; margin: 0 auto; padding: 1.5rem; }
.sidebar, .panel, .state-card, .phase-card { background: var(--surface);
  border: 1px solid var(--line); border-radius: .65rem; }
.sidebar { padding: 1rem; align-self: start; position: sticky; top: 1rem; }
.sidebar ul { list-style: none; padding: 0; margin: .5rem 0; }
.sidebar li { margin: .35rem 0; }
.content { min-width: 0; }
.panel { padding: 1.25rem; margin-bottom: 1.25rem; overflow: auto; }
.mermaid { min-width: 44rem; text-align: center; }
.mermaid-fallback { white-space: pre-wrap; text-align: left; }
.state-grid, .phase-grid { display: grid;
  grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr)); gap: 1rem; }
.state-card, .phase-card { padding: 1rem; }
.state-card h3, .phase-card h3 { margin-top: 0; }
.info-tooltip { display: inline-flex; align-items: center; justify-content: center;
  width: 1.2rem; height: 1.2rem; margin-left: .35rem; border-radius: 50%;
  background: var(--accent-soft); color: var(--accent); cursor: help;
  font-size: .75rem; font-style: normal; vertical-align: middle; }
.info-tooltip:focus { outline: 2px solid var(--accent); outline-offset: 2px; }
.badge { display: inline-block; border-radius: 999px; padding: .15rem .55rem;
  background: var(--accent-soft); color: var(--accent); font-size: .8rem; }
.metadata { display: grid; grid-template-columns: max-content 1fr; gap: .35rem 1rem; }
.metadata dt { font-weight: 700; }
.metadata dd { margin: 0; }
.transition-list li { margin-bottom: .55rem; }
.pager { display: flex; justify-content: space-between; gap: 1rem; margin: 1rem 0; }
.notice { color: var(--warning); }
footer { color: var(--muted); padding: 1.5rem; text-align: center; }
@media (max-width: 760px) {
  .layout { grid-template-columns: 1fr; padding: .75rem; }
  .sidebar { position: static; }
  .mermaid { min-width: 38rem; }
}"""


def site_javascript(mermaid_url: str = DEFAULT_MERMAID_URL) -> str:
    return f"""\
(async () => {{
  const nodes = document.querySelectorAll(".mermaid");
  if (nodes.length) {{
    try {{
      const module = await import({mermaid_url!r});
      const mermaid = module.default;
      mermaid.initialize({{ startOnLoad: false, securityLevel: "loose" }});
      await mermaid.run({{ nodes }});
      document.documentElement.dataset.mermaidRendered = "true";
    }} catch (error) {{
      document.querySelectorAll(".mermaid").forEach((node) => {{
        node.classList.add("mermaid-fallback");
      }});
      document.querySelectorAll("[data-mermaid-notice]").forEach((notice) => {{
        notice.hidden = false;
      }});
      document.documentElement.dataset.mermaidRendered = "false";
      console.error("Mermaid indisponible", error);
    }}
  }}
}})();"""


def diagram_panel(title: str, diagram: str) -> str:
    return f"""\
<section class="panel">
  <h2>{escape(title)}</h2>
  <p class="notice" data-mermaid-notice hidden>
    Le moteur Mermaid n'a pas pu être chargé. Le code source reste affiché.
  </p>
  <pre class="mermaid">{escape(diagram)}</pre>
</section>"""


def state_description(state: Mapping[str, Any]) -> str:
    return sanitize_documentation(state.get("description"), "html")


def state_content(state: Mapping[str, Any]) -> str:
    return sanitize_documentation(state.get("contenu"), state.get("type_contenu"))


def state_card(
    state: Mapping[str, Any],
    state_href: str | None = None,
    link_prefix: str = "",
) -> str:
    title = escape(state["nom"])
    if state_href:
        title = f'<a href="{escape(state_href)}">{title}</a>'
    content = state_content(state)
    extra = f'<div class="state-content">{content}</div>' if content else ""
    navigation_href = record_link_href(state, link_prefix)
    navigation = (
        f'<p><a href="{escape(navigation_href)}">'
        f'{escape(state.get("libelle_lien") or "Ouvrir la page associée")} →</a></p>'
        if navigation_href
        else ""
    )
    return f"""\
<article class="state-card" id="{escape(state['etat_id'])}">
  <span class="badge">{escape(state["type_etat"])}</span>
  <h3>{title}</h3>
  <div class="state-description">{state_description(state)}</div>
  {extra}
  {navigation}
</article>"""


def workflow_context(
    document: Mapping[str, Any], workflow_id: str | None
) -> tuple[
    Mapping[str, Any],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    dict[str, Mapping[str, Any]],
]:
    workflow, states, transitions = select_workflow(document, workflow_id)
    states = sorted(states, key=state_sort_key)
    transitions = sorted(transitions, key=transition_sort_key)
    state_ids = {state["etat_id"] for state in states}
    rules = sorted(
        [
            rule
            for rule in document.get("Regle", [])
            if rule.get("workflow_id") == workflow["workflow_id"]
            and (
                rule.get("etat_id") in state_ids
                or rule.get("transition_id")
                in {item["transition_id"] for item in transitions}
            )
        ],
        key=lambda rule: str(rule.get("regle_id", "")),
    )
    roles = {
        role["role_id"]: role
        for role in document.get("Role", [])
        if isinstance(role, Mapping) and "role_id" in role
    }
    return workflow, states, transitions, rules, roles


def workflow_diagrams(
    workflow: Mapping[str, Any],
    states: Sequence[Mapping[str, Any]],
    transitions: Sequence[Mapping[str, Any]],
) -> tuple[str, str]:
    return (
        generate_dataset_flowchart(workflow, states, transitions),
        generate_dataset_state_diagram(states, transitions),
    )


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def render_sidebar(
    phases: Iterable[tuple[str, str]],
    states: Sequence[Mapping[str, Any]],
    *,
    root_prefix: str,
    show_states: bool = True,
) -> str:
    phase_items = "".join(
        f'<li><a href="{escape(root_prefix)}phases/{escape(file_name)}">'
        f"{escape(label)}</a></li>"
        for label, file_name in phases
    )
    state_items = "".join(
        f'<li><a href="{escape(root_prefix)}states/{escape(state["etat_id"])}.html">'
        f'{escape(state["nom"])}</a></li>'
        for state in states
    )
    state_section = (
        f"""\
  <strong>États</strong>
  <ul>{state_items}</ul>"""
        if show_states
        else ""
    )
    return f"""\
<aside class="sidebar">
  <strong>Phases</strong>
  <ul>{phase_items}</ul>
{state_section}
</aside>"""
