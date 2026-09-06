"""Shared HTML rendering helpers for workflow documentation."""

from __future__ import annotations

import html
import hashlib
import json
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


VENDOR_DIRECTORY = Path(__file__).resolve().parent / "vendor"
JAVASCRIPT_DEPENDENCIES_PATH = VENDOR_DIRECTORY / "javascript-dependencies.json"


def _load_mermaid_dependency() -> dict[str, str]:
    dependency_file = json.loads(
        JAVASCRIPT_DEPENDENCIES_PATH.read_text(encoding="utf-8")
    )
    dependency = dependency_file.get("mermaid")
    required = {"version", "file", "license_file", "url", "license_url", "sha256"}
    if not isinstance(dependency, dict) or not required.issubset(dependency):
        raise RuntimeError(
            "scripts/vendor/javascript-dependencies.json ne décrit pas Mermaid."
        )
    for key in required:
        if not isinstance(dependency[key], str) or not dependency[key]:
            raise RuntimeError(f"La propriété Mermaid {key!r} est invalide.")
    for key in ("file", "license_file"):
        if Path(dependency[key]).name != dependency[key]:
            raise RuntimeError(f"La propriété Mermaid {key!r} doit être un nom de fichier.")
    return dependency


MERMAID_DEPENDENCY = _load_mermaid_dependency()
DEFAULT_MERMAID_URL = MERMAID_DEPENDENCY["url"]
LOCAL_MERMAID_FILENAME = "mermaid.min.js"
VENDORED_MERMAID_PATH = VENDOR_DIRECTORY / MERMAID_DEPENDENCY["file"]
VENDORED_MERMAID_LICENSE_PATH = VENDOR_DIRECTORY / MERMAID_DEPENDENCY["license_file"]


def verified_vendored_mermaid_text() -> str:
    """Return the pinned renderer after checking its lock-file checksum."""
    payload = VENDORED_MERMAID_PATH.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != MERMAID_DEPENDENCY["sha256"]:
        raise RuntimeError(
            "La somme SHA-256 de la distribution Mermaid locale ne correspond "
            "pas à scripts/vendor/javascript-dependencies.json."
        )
    return payload.decode("utf-8")
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
SAFE_HTTP_LINK = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)
SAFE_PHASE_LINK = re.compile(r"^phases/[A-Za-z0-9_-]+\.html$")
SAFE_STATE_LINK = re.compile(r"^states/([A-Za-z_][A-Za-z0-9_]*)\.html$")


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
    if record.get("type_lien") == "page_etat":
        return None
    return f"{root_prefix}{target}"


def record_link_validation(
    record: Mapping[str, Any],
    *,
    phase_targets: Iterable[str] = (),
    state_ids: Iterable[str] = (),
) -> tuple[bool | None, str]:
    """Validate a structured record link without probing remote URLs."""
    link_type = record.get("type_lien")
    target = record.get("cible_lien")
    label = record.get("libelle_lien")
    if not any(value for value in (link_type, target, label)):
        return None, "Aucun lien"
    if not isinstance(link_type, str) or not isinstance(target, str) or not target:
        return False, "Le type et la destination sont obligatoires."
    if link_type == "url":
        return (
            (True, "URL HTTP(S) syntaxiquement valide")
            if SAFE_HTTP_LINK.fullmatch(target)
            else (False, "Une URL HTTP(S) est attendue.")
        )
    if link_type == "page_phase":
        if not SAFE_PHASE_LINK.fullmatch(target):
            return False, "Le chemin attendu est phases/<phase>.html."
        if target not in set(phase_targets):
            return False, "La page de phase destinataire n’existe pas."
        return True, "Page de phase existante"
    if link_type == "page_etat":
        match = SAFE_STATE_LINK.fullmatch(target)
        if not match:
            return False, "Le chemin attendu est states/<identifiant>.html."
        if match.group(1) not in set(state_ids):
            return False, f"L’état « {match.group(1)} » n’existe pas."
        return False, "Les pages individuelles d’état ne sont plus générées."
    return False, f"Type de lien inconnu : {link_type}."


def record_link_status_html(
    record: Mapping[str, Any],
    *,
    root_prefix: str = "",
    phase_targets: Iterable[str] = (),
    state_ids: Iterable[str] = (),
) -> str:
    valid, reason = record_link_validation(
        record, phase_targets=phase_targets, state_ids=state_ids
    )
    status_class = (
        "link-neutral" if valid is None else "link-valid" if valid else "link-invalid"
    )
    status_text = "Aucun lien" if valid is None else "Valide" if valid else "Invalide"
    href = record_link_href(record, root_prefix) if valid else None
    target = record.get("cible_lien")
    link = ""
    if isinstance(target, str) and target:
        label = record.get("libelle_lien") or target
        rendered_target = (
            f'<a href="{escape(href)}">{escape(label)}</a>' if href else escape(label)
        )
        link = f'<span class="record-link-target">{rendered_target}</span>'
    return (
        '<div class="record-link-status">'
        f'<span class="link-status {status_class}">{status_text}</span>'
        f"{link}<small>{escape(reason)}</small>"
        "</div>"
    )


def page_shell(
    *,
    title: str,
    body: str,
    root_prefix: str = "",
    mermaid_url: str = DEFAULT_MERMAID_URL,
    inline_assets: bool = False,
    diagram_config: Mapping[str, Any] | None = None,
    theme_config: Mapping[str, str] | None = None,
    theme_scope: str = "standalone",
) -> str:
    escaped_title = escape(title)
    selected_theme = dict(theme_config or {"pair": "ocean", "mode": "system"})
    default_pair = str(selected_theme.get("pair", "ocean"))
    default_mode = str(selected_theme.get("mode", "system"))
    theme_bootstrap = """<script>
(() => {
  const root = document.documentElement;
  const scope = root.dataset.themeScope || "standalone";
  const pairKey = `workflow-site-theme:${scope}:pair`;
  const modeKey = `workflow-site-theme:${scope}:mode`;
  const configurationKey = `workflow-site-theme:${scope}:configuration`;
  const defaultPair = root.dataset.themeDefaultPair || "ocean";
  const defaultMode = root.dataset.themeDefaultMode || "system";
  const configuration = `${defaultPair}/${defaultMode}`;
  try {
    const configurationChanged = localStorage.getItem(configurationKey) !== configuration;
    const pair = configurationChanged
      ? defaultPair : (localStorage.getItem(pairKey) || defaultPair);
    const preference = configurationChanged
      ? defaultMode : (localStorage.getItem(modeKey) || defaultMode);
    if (configurationChanged) {
      localStorage.setItem(pairKey, pair);
      localStorage.setItem(modeKey, preference);
      localStorage.setItem(configurationKey, configuration);
    }
    const mode = preference === "system"
      ? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
      : preference;
    root.dataset.themePair = pair;
    root.dataset.themeMode = mode;
    root.dataset.themeModePreference = preference;
  } catch (error) {
    root.dataset.themePair = defaultPair;
    root.dataset.themeMode = defaultMode === "dark" ? "dark" : "light";
    root.dataset.themeModePreference = defaultMode;
  }
})();
</script>"""
    if inline_assets:
        styles = f"<style>\n{site_css()}\n</style>"
        embedded_renderer = ""
        configured_url = mermaid_url
        if mermaid_url == DEFAULT_MERMAID_URL:
            embedded_renderer = (
                f"<script>\n{verified_vendored_mermaid_text()}\n</script>\n"
            )
            configured_url = "embedded:mermaid"
        script = (
            embedded_renderer
            + f"<script>\n{site_javascript(configured_url, diagram_config)}\n</script>"
        )
    else:
        styles = f'<link rel="stylesheet" href="{escape(root_prefix)}assets/style.css">'
        script = (
            f'<script defer src="{escape(root_prefix)}assets/app.js"></script>'
        )
    return f"""<!doctype html>
<html lang="fr" data-theme-scope="{escape(theme_scope)}"
  data-theme-default-pair="{escape(default_pair)}"
  data-theme-default-mode="{escape(default_mode)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  {theme_bootstrap}
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
  --header-bg: #102a43;
  --header-text: #ffffff;
  --button-text: #ffffff;
  --input-border: #aebbc6;
  --code-bg: #111827;
  --code-text: #f9fafb;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
}
:root[data-theme-mode="dark"] {
  color-scheme: dark;
  --bg: #08131f;
  --surface: #102233;
  --text: #e5eef7;
  --muted: #a8bacb;
  --line: #32485c;
  --accent: #7dd3fc;
  --accent-soft: #123b52;
  --warning: #fdba74;
  --header-bg: #06101a;
  --header-text: #f8fafc;
  --button-text: #06101a;
  --input-border: #52697d;
  --code-bg: #020617;
  --code-text: #e2e8f0;
}
:root[data-theme-pair="forest"] {
  --bg: #f1f7f2; --surface: #ffffff; --text: #183126; --muted: #587064;
  --line: #cbdccf; --accent: #166534; --accent-soft: #dcfce7;
  --warning: #9a3412; --header-bg: #153d2a; --header-text: #ffffff;
  --input-border: #9fb6a6;
}
:root[data-theme-pair="forest"][data-theme-mode="dark"] {
  --bg: #09150f; --surface: #12251a; --text: #e1f3e7; --muted: #a7c3b0;
  --line: #365844; --accent: #86efac; --accent-soft: #17452a;
  --warning: #fdba74; --header-bg: #06100a; --header-text: #f0fdf4;
  --input-border: #517460;
  --button-text: #07150d;
}
:root[data-theme-pair="aubergine"] {
  --bg: #f8f4fa; --surface: #ffffff; --text: #30203a; --muted: #74617d;
  --line: #e1d5e7; --accent: #7e22ce; --accent-soft: #f3e8ff;
  --warning: #9a3412; --header-bg: #3b174d; --header-text: #ffffff;
  --input-border: #bea9c8;
}
:root[data-theme-pair="aubergine"][data-theme-mode="dark"] {
  --bg: #160b1b; --surface: #281532; --text: #f3e8ff; --muted: #cbb4d7;
  --line: #563666; --accent: #d8b4fe; --accent-soft: #4a1d61;
  --warning: #fdba74; --header-bg: #0e0712; --header-text: #faf5ff;
  --input-border: #745484;
  --button-text: #17091d;
}
:root[data-theme-pair="graphite"] {
  --bg: #f5f5f5; --surface: #ffffff; --text: #202124; --muted: #5f6368;
  --line: #d7d7d7; --accent: #374151; --accent-soft: #e5e7eb;
  --warning: #9a3412; --header-bg: #27272a; --header-text: #ffffff;
  --input-border: #a3a3a3;
}
:root[data-theme-pair="graphite"][data-theme-mode="dark"] {
  --bg: #111214; --surface: #202124; --text: #f1f3f4; --muted: #bdc1c6;
  --line: #45474a; --accent: #d1d5db; --accent-soft: #34363a;
  --warning: #fdba74; --header-bg: #090a0b; --header-text: #ffffff;
  --input-border: #66696d;
  --button-text: #111214;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); line-height: 1.55; }
a { color: var(--accent); }
.site-header { background: var(--header-bg); color: var(--header-text); padding: 1rem 1.5rem; }
.site-header a { color: var(--header-text); text-decoration: none; }
.site-header nav { display: flex; flex-wrap: wrap; gap: 1rem; margin-top: .5rem; }
.theme-mode-toggle { margin-left: auto; border: 1px solid currentColor;
  border-radius: 999px; padding: .25rem .7rem; background: transparent;
  color: var(--header-text); cursor: pointer; font: inherit; }
.theme-mode-toggle:hover, .theme-mode-toggle:focus-visible {
  background: color-mix(in srgb, var(--header-text) 16%, transparent); }
.layout { display: grid; grid-template-columns: minmax(14rem, 20rem) 1fr; gap: 1.5rem;
  max-width: 96rem; margin: 0 auto; padding: 1.5rem; }
.layout.sidebar-collapsed { grid-template-columns: 3rem 1fr; }
.sidebar-wrapper { min-width: 0; }
.sidebar, .panel, .state-card, .phase-card { background: var(--surface);
  border: 1px solid var(--line); border-radius: .65rem; }
.sidebar { padding: 1rem; align-self: start; position: sticky; top: 1rem; }
.sidebar-toggle { width: 100%; margin-bottom: .5rem; padding: .45rem .6rem;
  border: 1px solid var(--line); border-radius: .45rem; background: var(--surface);
  color: var(--accent); cursor: pointer; font: inherit; font-size: 1.1rem;
  font-weight: 700; }
.sidebar-toggle:hover, .sidebar-toggle:focus-visible { background: var(--accent-soft); }
.layout.sidebar-collapsed .sidebar { display: none; }
.sidebar ul { list-style: none; padding: 0; margin: .5rem 0; }
.sidebar li { margin: .35rem 0; }
.content { min-width: 0; }
.panel { padding: 1.25rem; margin-bottom: 1.25rem; overflow: auto; }
.mermaid { width: max-content; min-width: 100%; text-align: center; }
.mermaid svg { display: block; height: auto; margin-inline: auto;
  max-width: none !important; }
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
.editor-shell { max-width: 96rem; margin: 0 auto; padding: 1.5rem; }
.editor-toolbar { display: flex; flex-wrap: wrap; align-items: end; gap: .75rem; }
.editor-toolbar label { flex: 1 1 20rem; }
.editor-toolbar select { width: 100%; }
.editor-summary { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: 1rem; }
.editor-layout-controls { display: flex; justify-content: flex-end;
  margin: 0 0 .75rem; }
.editor-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.25rem; }
.editor-grid.transitions-below { grid-template-columns: 1fr; }
.editor-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: .75rem; }
.editor-form .field-wide { grid-column: 1 / -1; }
.editor-form label, .editor-toolbar label { display: grid; gap: .25rem;
  color: var(--muted); font-size: .9rem; font-weight: 650; }
[hidden] { display: none !important; }
.editor-form input, .editor-form select, .editor-form textarea,
.editor-toolbar select, .json-editor { border: 1px solid var(--input-border);
  border-radius: .4rem; background: var(--surface); color: var(--text); font: inherit;
  padding: .55rem .65rem; }
.editor-form textarea { min-height: 6rem; resize: vertical; }
.editor-actions { display: flex; flex-wrap: wrap; gap: .55rem; align-items: center;
  margin-top: .75rem; }
.button { border: 1px solid var(--accent); border-radius: .4rem;
  background: var(--accent); color: var(--button-text); cursor: pointer; font: inherit;
  font-weight: 650; padding: .5rem .8rem; text-decoration: none; }
.button:hover, .button:focus-visible { filter: brightness(.92); }
.button-secondary { background: var(--surface); color: var(--accent); }
.button-danger { border-color: #b91c1c; background: var(--surface); color: #ef4444; }
.button-small { padding: .25rem .5rem; font-size: .85rem; }
.editor-table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
.editor-table th, .editor-table td { border-top: 1px solid var(--line);
  padding: .55rem .4rem; text-align: left; vertical-align: top; }
.editor-table th { color: var(--muted); font-size: .85rem; }
.editor-table td:last-child { white-space: nowrap; }
.json-editor { width: 100%; min-height: 30rem; resize: vertical;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .86rem;
  line-height: 1.45; tab-size: 2; }
.validation-summary { border-radius: .4rem; padding: .65rem .8rem; }
.validation-summary.valid { background: #dcfce7; color: #166534; }
.validation-summary.invalid { background: #fee2e2; color: #991b1b; }
.validation-summary ul { margin: .4rem 0 0; padding-left: 1.25rem; }
.editor-status { min-height: 1.5rem; color: var(--muted); }
.editor-empty { color: var(--muted); font-style: italic; }
.link-status { display: inline-block; border-radius: 999px; padding: .12rem .5rem;
  font-size: .8rem; font-weight: 700; }
.link-valid { background: #dcfce7; color: #166534; }
.link-invalid { background: #fee2e2; color: #991b1b; }
.link-neutral { background: #e5e7eb; color: #374151; }
.record-link-status { display: grid; gap: .35rem; margin-top: .75rem; }
.record-link-status .link-status { justify-self: start; }
.record-link-status small { color: var(--muted); }
.record-link-target { overflow-wrap: anywhere; }
.link-target { max-width: 32rem; overflow-wrap: anywhere;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .85rem; }
.link-alert { border: 1px solid #fca5a5; border-radius: .45rem;
  background: #fff1f2; color: #991b1b; margin: .75rem 0; padding: .75rem; }
.link-alert ul { margin: .4rem 0 0; padding-left: 1.25rem; }
.editor-table tr.link-row-invalid { background: #fff1f2; }
.vocabulary-list { margin-bottom: 0; }
.reference-layout { max-width: 110rem; }
.reference-section { scroll-margin-top: 1rem; }
.reference-example { border-top: 1px solid var(--line); margin-top: 1rem;
  padding-top: 1rem; }
.reference-example-heading { display: flex; flex-wrap: wrap; align-items: center;
  justify-content: space-between; gap: .75rem; }
.reference-example-heading h3 { margin: 0; }
.support-tag { display: inline-block; border-radius: 999px; padding: .15rem .55rem;
  font-size: .78rem; font-weight: 700; }
.support-json { background: #dcfce7; color: #166534; }
.support-mermaid { background: #e0f2fe; color: #075985; }
.support-limite { background: #ffedd5; color: #9a3412; }
.code-block { overflow: auto; border-radius: .45rem; background: var(--code-bg);
  color: var(--code-text); padding: 1rem; white-space: pre; }
details { margin-top: .75rem; }
details summary { color: var(--accent); cursor: pointer; font-weight: 650; }
.settings-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
  gap: 1rem; }
.theme-preview { border: 2px solid var(--line); border-radius: .65rem; overflow: hidden; }
.theme-preview-bars { display: grid; grid-template-columns: 1fr 1fr; min-height: 5rem; }
.theme-preview-light { background: #f4f6f8; color: #17212b; padding: .75rem; }
.theme-preview-dark { background: #102233; color: #e5eef7; padding: .75rem; }
.theme-preview[data-pair="forest"] .theme-preview-light { background:#f1f7f2; color:#183126; }
.theme-preview[data-pair="forest"] .theme-preview-dark { background:#12251a; color:#e1f3e7; }
.theme-preview[data-pair="aubergine"] .theme-preview-light { background:#f8f4fa; color:#30203a; }
.theme-preview[data-pair="aubergine"] .theme-preview-dark { background:#281532; color:#f3e8ff; }
.theme-preview[data-pair="graphite"] .theme-preview-light { background:#f5f5f5; color:#202124; }
.theme-preview[data-pair="graphite"] .theme-preview-dark { background:#202124; color:#f1f3f4; }
.settings-form { display: grid; gap: 1rem; max-width: 38rem; }
.settings-form label { display: grid; gap: .35rem; font-weight: 650; }
.settings-form select { border: 1px solid var(--input-border); border-radius: .4rem;
  background: var(--surface); color: var(--text); font: inherit; padding: .55rem .65rem; }
@media (max-width: 760px) {
  .layout { grid-template-columns: 1fr; padding: .75rem; }
  .layout.sidebar-collapsed { grid-template-columns: 1fr; }
  .layout.sidebar-collapsed .sidebar-wrapper { width: 3rem; }
  .sidebar { position: static; }
  .editor-shell { padding: .75rem; }
  .editor-grid, .editor-form { grid-template-columns: 1fr; }
  .editor-form .field-wide { grid-column: auto; }
  .editor-table { display: block; overflow-x: auto; }
}"""


def site_javascript(
    mermaid_url: str = DEFAULT_MERMAID_URL,
    diagram_config: Mapping[str, Any] | None = None,
) -> str:
    from workflow_data import DEFAULT_DIAGRAM_CONFIG

    normalized_config = dict(DEFAULT_DIAGRAM_CONFIG)
    if diagram_config:
        normalized_config.update(diagram_config)
    serialized_config = json.dumps(normalized_config, ensure_ascii=False)
    return f"""\
(async () => {{
  const diagramConfig = {serialized_config};
  const themeRoot = document.documentElement;
  const themeScope = themeRoot.dataset.themeScope || "standalone";
  const themePairKey = `workflow-site-theme:${{themeScope}}:pair`;
  const themeModeKey = `workflow-site-theme:${{themeScope}}:mode`;
  const themeConfigurationKey = `workflow-site-theme:${{themeScope}}:configuration`;
  const defaultThemePair = themeRoot.dataset.themeDefaultPair || "ocean";
  const defaultThemeMode = themeRoot.dataset.themeDefaultMode || "system";
  const themePairs = new Set(["ocean", "forest", "aubergine", "graphite"]);
  const themeModes = new Set(["system", "light", "dark"]);
  const readTheme = (key, allowed, fallback) => {{
    try {{
      const value = localStorage.getItem(key);
      return allowed.has(value) ? value : fallback;
    }} catch (error) {{
      return fallback;
    }}
  }};
  const resolveThemeMode = (preference) => preference === "system"
    ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    : preference;
  let themeToggle = null;
  const updateThemeToggle = () => {{
    if (!themeToggle) return;
    const isDark = document.documentElement.dataset.themeMode === "dark";
    themeToggle.textContent = isDark ? "☀ Mode clair" : "☾ Mode sombre";
    themeToggle.setAttribute("aria-label", isDark
      ? "Activer le mode clair" : "Activer le mode sombre");
  }};
  const applyTheme = (pair, preference, persist = false) => {{
    const selectedPair = themePairs.has(pair) ? pair : defaultThemePair;
    const selectedPreference = themeModes.has(preference) ? preference : defaultThemeMode;
    document.documentElement.dataset.themePair = selectedPair;
    document.documentElement.dataset.themeModePreference = selectedPreference;
    document.documentElement.dataset.themeMode = resolveThemeMode(selectedPreference);
    if (persist) {{
      try {{
        localStorage.setItem(themePairKey, selectedPair);
        localStorage.setItem(themeModeKey, selectedPreference);
      }} catch (error) {{
        console.debug("Préférence de thème non persistée", error);
      }}
    }}
    updateThemeToggle();
    window.dispatchEvent(new CustomEvent("workflow-theme-change", {{
      detail: {{ pair: selectedPair, mode: document.documentElement.dataset.themeMode }}
    }}));
  }};
  const themeConfiguration = `${{defaultThemePair}}/${{defaultThemeMode}}`;
  try {{
    if (localStorage.getItem(themeConfigurationKey) !== themeConfiguration) {{
      localStorage.setItem(themePairKey, defaultThemePair);
      localStorage.setItem(themeModeKey, defaultThemeMode);
      localStorage.setItem(themeConfigurationKey, themeConfiguration);
    }}
  }} catch (error) {{
    console.debug("Configuration de thème non persistée", error);
  }}
  let themePair = readTheme(themePairKey, themePairs, defaultThemePair);
  let themePreference = readTheme(themeModeKey, themeModes, defaultThemeMode);
  applyTheme(themePair, themePreference);
  const themeNavigation = document.querySelector(".site-header nav");
  if (themeNavigation) {{
    themeToggle = document.createElement("button");
    themeToggle.type = "button";
    themeToggle.className = "theme-mode-toggle";
    themeToggle.addEventListener("click", () => {{
      themePreference = document.documentElement.dataset.themeMode === "dark"
        ? "light" : "dark";
      if (themeModeSelect) themeModeSelect.value = themePreference;
      applyTheme(themePair, themePreference, true);
    }});
    themeNavigation.append(themeToggle);
    updateThemeToggle();
  }}
  const colorScheme = window.matchMedia("(prefers-color-scheme: dark)");
  colorScheme.addEventListener("change", () => {{
    if (themePreference === "system") applyTheme(themePair, themePreference);
  }});
  const themePairSelect = document.getElementById("theme-pair");
  const themeModeSelect = document.getElementById("theme-mode");
  const themeStatus = document.getElementById("theme-status");
  const updateThemeSettings = () => {{
    if (!themePairSelect || !themeModeSelect) return;
    themePair = themePairSelect.value;
    themePreference = themeModeSelect.value;
    applyTheme(themePair, themePreference, true);
    if (themeStatus) themeStatus.textContent = "Préférences enregistrées localement.";
  }};
  if (themePairSelect && themeModeSelect) {{
    themePairSelect.value = themePair;
    themeModeSelect.value = themePreference;
    themePairSelect.addEventListener("change", updateThemeSettings);
    themeModeSelect.addEventListener("change", updateThemeSettings);
    document.getElementById("reset-theme")?.addEventListener("click", () => {{
      themePairSelect.value = defaultThemePair;
      themeModeSelect.value = defaultThemeMode;
      updateThemeSettings();
    }});
  }}
  const loadMermaid = async () => {{
    const configuredUrl = {mermaid_url!r};
    if (configuredUrl === "embedded:mermaid" && window.mermaid) {{
      return window.mermaid;
    }}
    const currentScript = document.currentScript || Array.from(document.scripts).find(
      (script) => /(?:^|\\/)app\\.js(?:[?#]|$)/.test(script.src)
    );
    const baseUrl = currentScript && currentScript.src
      ? currentScript.src
      : document.baseURI;
    const url = /^[A-Za-z][A-Za-z0-9+.-]*:/.test(configuredUrl)
      ? configuredUrl
      : new URL(configuredUrl, baseUrl).href;
    if (/\\.mjs(?:[?#]|$)/i.test(url)) {{
      const module = await import(url);
      return module.default || module;
    }}
    if (window.mermaid) {{
      return window.mermaid;
    }}
    await new Promise((resolve, reject) => {{
      const script = document.createElement("script");
      script.src = url;
      script.onload = resolve;
      script.onerror = () => reject(new Error(`Impossible de charger ${{url}}`));
      document.head.append(script);
    }});
    if (!window.mermaid) {{
      throw new Error("Le script chargé n'expose pas Mermaid.");
    }}
    return window.mermaid;
  }};

  const storageKey = "workflow-navigation-collapsed";
  document.querySelectorAll("[data-sidebar-toggle]").forEach((button) => {{
    const layout = button.closest(".layout");
    if (!layout) {{
      return;
    }}
    const applyState = (collapsed) => {{
      layout.classList.toggle("sidebar-collapsed", collapsed);
      button.setAttribute("aria-expanded", String(!collapsed));
      const label = collapsed ? "Afficher la navigation" : "Masquer la navigation";
      button.textContent = "☰";
      button.setAttribute("aria-label", label);
      button.setAttribute("title", label);
    }};
    let collapsed = false;
    try {{
      collapsed = localStorage.getItem(storageKey) === "true";
    }} catch (error) {{
      console.debug("Préférence de navigation non persistée", error);
    }}
    applyState(collapsed);
    button.addEventListener("click", () => {{
      const nextState = !layout.classList.contains("sidebar-collapsed");
      applyState(nextState);
      try {{
        localStorage.setItem(storageKey, String(nextState));
      }} catch (error) {{
        console.debug("Préférence de navigation non persistée", error);
      }}
    }});
  }});

  const nodes = Array.from(document.querySelectorAll(".mermaid"));
  const mermaidSources = new Map(nodes.map((node) => [node, node.textContent || ""]));
  let mermaidRenderer = null;
  let mermaidRendering = false;
  let mermaidRenderQueued = false;
  const renderMermaidDiagrams = async () => {{
    if (!nodes.length) return;
    if (mermaidRendering) {{
      mermaidRenderQueued = true;
      return;
    }}
    mermaidRendering = true;
    try {{
      mermaidRenderer = mermaidRenderer || await loadMermaid();
      nodes.forEach((node) => {{
        node.removeAttribute("data-processed");
        node.classList.remove("mermaid-fallback");
        node.textContent = mermaidSources.get(node) || "";
      }});
      mermaidRenderer.initialize({{
        startOnLoad: false,
        securityLevel: "loose",
        htmlLabels: true,
        theme: document.documentElement.dataset.themeMode === "dark" ? "dark" : "default",
        flowchart: {{
          nodeSpacing: diagramConfig.node_spacing,
          rankSpacing: diagramConfig.rank_spacing,
          diagramPadding: diagramConfig.diagram_padding,
          wrappingWidth: diagramConfig.wrapping_width
        }},
        swimlane: {{ useMaxWidth: diagramConfig.use_max_width }}
      }});
      await mermaidRenderer.run({{ nodes }});
      nodes.forEach((node) => {{
        const svg = node.querySelector("svg");
        const viewBox = svg && svg.viewBox && svg.viewBox.baseVal;
        if (svg && viewBox && viewBox.width) {{
          svg.style.width = diagramConfig.use_max_width
            ? "100%"
            : `${{Math.ceil(viewBox.width)}}px`;
        }}
      }});
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
    }} finally {{
      mermaidRendering = false;
      if (mermaidRenderQueued) {{
        mermaidRenderQueued = false;
        void renderMermaidDiagrams();
      }}
    }}
  }};
  if (nodes.length) {{
    window.addEventListener("workflow-theme-change", () => {{
      void renderMermaidDiagrams();
    }});
    await renderMermaidDiagrams();
  }}
}})();"""


def workflow_editor_javascript() -> str:
    """Return the dependency-free workflow editor used by catalog sites."""

    return r"""(() => {
  const payloadNode = document.getElementById("workflow-editor-data");
  const sourceSelect = document.getElementById("workflow-source");
  if (!payloadNode || !sourceSelect) {
    return;
}

  const payload = JSON.parse(payloadNode.textContent);
  const byId = (id) => document.getElementById(id);
  const clone = (value) => JSON.parse(JSON.stringify(value));
  const identifierPattern = /^[A-Za-z_][A-Za-z0-9_]*$/;
  let selectedEntry = null;
  let documentData = null;
  let dirty = false;
  let jsonTimer = null;
  const editorLayoutKey = "workflow-editor-transitions-below";
  const editorGrid = byId("editor-grid");
  const layoutButton = byId("toggle-editor-layout");
  const saveButton = byId("download-json");
  const supportsFilePicker = typeof window.showSaveFilePicker === "function";
  if (supportsFilePicker) {
    byId("save-method-note").textContent = (
      "Le navigateur demandera le nom et l’emplacement du fichier JSON."
    );
  } else {
    saveButton.textContent = "Télécharger le JSON";
    byId("save-method-note").textContent = (
      "Ce navigateur — notamment Firefox — ne permet pas à un site statique " +
      "de choisir directement un dossier. Le fichier ira dans le dossier de " +
      "téléchargement configuré. Dans Firefox, activez « Toujours demander où " +
      "enregistrer les fichiers » dans Paramètres > Général > Fichiers et applications."
    );
  }

  function applyEditorLayout(transitionsBelow) {
    editorGrid.classList.toggle("transitions-below", transitionsBelow);
    layoutButton.setAttribute("aria-pressed", String(transitionsBelow));
    const label = transitionsBelow
      ? "Placer les transitions à droite"
      : "Placer les transitions en dessous";
    layoutButton.textContent = label;
    layoutButton.setAttribute("title", label);
  }

  let transitionsBelow = false;
  try {
    transitionsBelow = localStorage.getItem(editorLayoutKey) === "true";
  } catch (error) {
    console.debug("Disposition de l’éditeur non persistée", error);
  }
  applyEditorLayout(transitionsBelow);
  layoutButton.addEventListener("click", () => {
    transitionsBelow = !editorGrid.classList.contains("transitions-below");
    applyEditorLayout(transitionsBelow);
    try {
      localStorage.setItem(editorLayoutKey, String(transitionsBelow));
    } catch (error) {
      console.debug("Disposition de l’éditeur non persistée", error);
    }
  });

  function records(table) {
    if (!Array.isArray(documentData[table])) {
      documentData[table] = [];
    }
    return documentData[table];
  }

  function workflowRecords(table) {
    return records(table).filter(
      (item) => item.workflow_id === selectedEntry.workflow_id
    );
  }

  function setStatus(message) {
    byId("editor-status").textContent = message;
  }

  function option(value, label, selected = false) {
    const node = document.createElement("option");
    node.value = value;
    node.textContent = label;
    node.selected = selected;
    return node;
  }

  function replaceOptions(select, items, emptyLabel = null) {
    const previous = select.value;
    select.replaceChildren();
    if (emptyLabel !== null) {
      select.append(option("", emptyLabel));
    }
    items.forEach((item) => {
      select.append(option(item.value, item.label, item.value === previous));
    });
  }

  function checkInternalStateTarget(target, stateIds) {
    const match = /^states\/([A-Za-z_][A-Za-z0-9_]*)\.html$/.exec(target);
    if (!match) {
      return { valid: false, reason: "Le chemin attendu est states/<identifiant>.html." };
    }
    if (!stateIds.has(match[1])) {
      return { valid: false, reason: `L’état « ${match[1]} » n’existe pas.` };
    }
    return { valid: true, reason: "" };
  }

  function checkStructuredLink(state, stateIds) {
    const type = state.type_lien || "";
    const target = state.cible_lien || "";
    const hasLink = Boolean(type || target || state.libelle_lien);
    if (!hasLink) {
      return null;
    }
    if (!type || !target) {
      return {
        target: target || "(cible absente)",
        valid: false,
        reason: "Le type et la cible sont obligatoires."
      };
    }
    if (type === "url") {
      return {
        target,
        valid: /^https?:\/\/[^\s]+$/i.test(target),
        reason: "Une URL HTTP(S) est attendue."
      };
    }
    if (type === "page_phase") {
      return {
        target,
        valid: /^phases\/[A-Za-z0-9_-]+\.html$/.test(target),
        reason: "Le chemin attendu est phases/<phase>.html."
      };
    }
    if (type === "page_etat") {
      const reference = checkInternalStateTarget(target, stateIds);
      if (!reference.valid) {
        return { target, ...reference };
      }
      return {
        target,
        valid: false,
        reason: "Les pages individuelles d’état ne sont plus générées."
      };
    }
    return { target, valid: false, reason: `Type de lien inconnu : ${type}.` };
  }

  function checkTextTarget(rawTarget, stateIds) {
    const target = rawTarget.trim().replaceAll("&amp;", "&");
    if (/^https?:\/\/[^\s]+$/i.test(target)) {
      return { target, valid: true, reason: "" };
    }
    if (/^mailto:[^@\s]+@[^@\s]+$/i.test(target)) {
      return { target, valid: true, reason: "" };
    }
    if (/^#[A-Za-z_][A-Za-z0-9_-]*$/.test(target)) {
      return { target, valid: true, reason: "" };
    }
    if (/^phases\/[A-Za-z0-9_-]+\.html$/.test(target)) {
      return { target, valid: true, reason: "" };
    }
    if (target.startsWith("states/")) {
      return { target, ...checkInternalStateTarget(target, stateIds) };
    }
    return {
      target,
      valid: false,
      reason: "Protocole ou cible non autorisé(e)."
    };
  }

  function extractTextLinks(text) {
    const links = [];
    const source = typeof text === "string" ? text : "";
    const htmlPattern = /<a\b[^>]*\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/gi;
    let match;
    while ((match = htmlPattern.exec(source)) !== null) {
      links.push(match[1] || match[2] || match[3] || "");
    }
    const markdownPattern = /!?\[[^\]]*]\(\s*<?([^)\s>]+)>?(?:\s+["'][^"']*["'])?\s*\)/g;
    while ((match = markdownPattern.exec(source)) !== null) {
      links.push(match[1] || "");
    }
    return [...new Set(links)];
  }

  function recordLinkResults(record, recordType, stateIds) {
    const results = [];
    const structured = checkStructuredLink(record, stateIds);
    const typeLabel = recordType === "État" ? "l’état" : "la transition";
    if (structured) {
      results.push({ origin: `Lien de ${typeLabel}`, ...structured });
    }
    const text = record.contenu || record.description || "";
    extractTextLinks(text).forEach((target) => {
      results.push({
        origin: `Texte de ${typeLabel}`,
        ...checkTextTarget(target, stateIds)
      });
    });
    return results;
  }

  function stateLinkResults(state, stateIds) {
    return recordLinkResults(state, "État", stateIds);
  }

  function validateDocument(value) {
    const errors = [];
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return ["La racine du JSON doit être un objet."];
    }
    const requiredTables = [
      "Workflow", "Ligne_eau", "Etat", "Transition", "Role", "Regle",
      "Generation_Mermaid"
    ];
    requiredTables.forEach((table) => {
      if (!Array.isArray(value[table])) {
        errors.push(`${table} doit être une liste.`);
      }
    });
    if (errors.length) {
      return errors;
    }

    const identifiers = [
      ["Workflow", "workflow_id"], ["Ligne_eau", "ligne_eau_id"],
      ["Etat", "etat_id"], ["Transition", "transition_id"],
      ["Role", "role_id"], ["Regle", "regle_id"],
      ["Generation_Mermaid", "generation_id"]
    ];
    identifiers.forEach(([table, field]) => {
      const seen = new Set();
      value[table].forEach((item, index) => {
        const id = item && item[field];
        if (typeof id !== "string" || !identifierPattern.test(id)) {
          errors.push(`${table}[${index}].${field} doit être un identifiant compatible Mermaid.`);
        } else if (seen.has(id)) {
          errors.push(`${table}.${field} contient le doublon « ${id} ».`);
        }
        seen.add(id);
      });
    });

    const workflows = new Set(value.Workflow.map((item) => item.workflow_id));
    const states = new Map(value.Etat.map((item) => [item.etat_id, item]));
    const transitions = new Map(
      value.Transition.map((item) => [item.transition_id, item])
    );
    const roles = new Set(value.Role.map((item) => item.role_id));
    const waterlines = new Map(
      value.Ligne_eau.map((item) => [item.ligne_eau_id, item])
    );

    ["Ligne_eau", "Etat", "Transition", "Regle", "Generation_Mermaid"].forEach(
      (table) => value[table].forEach((item, index) => {
        if (!workflows.has(item.workflow_id)) {
          errors.push(`${table}[${index}].workflow_id référence un workflow absent.`);
        }
      })
    );
    value.Etat.forEach((state, index) => {
      if (!state.nom || !["initial", "normal", "validation", "blocage", "final"].includes(state.type_etat)) {
        errors.push(`Etat[${index}] doit définir nom et un type_etat valide.`);
      }
      if (state.ligne_eau_id) {
        const waterline = waterlines.get(state.ligne_eau_id);
        if (!waterline || waterline.workflow_id !== state.workflow_id) {
          errors.push(`Etat[${index}].ligne_eau_id est absent ou appartient à un autre workflow.`);
        }
      }
    });
    value.Transition.forEach((transition, index) => {
      const source = states.get(transition.etat_source_id);
      const target = states.get(transition.etat_cible_id);
      if (!transition.libelle || typeof transition.actif !== "boolean") {
        errors.push(`Transition[${index}] doit définir libelle et actif.`);
      }
      if (!source || !target) {
        errors.push(`Transition[${index}] référence un état absent.`);
      } else if (
        source.workflow_id !== transition.workflow_id ||
        target.workflow_id !== transition.workflow_id
      ) {
        errors.push(`Transition[${index}] relie des états d'un autre workflow.`);
      }
      if (transition.role_autorise && !roles.has(transition.role_autorise)) {
        errors.push(`Transition[${index}].role_autorise référence un rôle absent.`);
      }
    });
    value.Regle.forEach((rule, index) => {
      if (rule.etat_id && !states.has(rule.etat_id)) {
        errors.push(`Regle[${index}].etat_id référence un état absent.`);
      }
      if (rule.transition_id && !transitions.has(rule.transition_id)) {
        errors.push(`Regle[${index}].transition_id référence une transition absente.`);
      }
      if (!rule.nom || typeof rule.bloquante !== "boolean") {
        errors.push(`Regle[${index}] doit définir nom et bloquante.`);
      }
    });
    return errors;
  }

  function renderValidation(errors) {
    const box = byId("json-validation");
    box.className = `validation-summary ${errors.length ? "invalid" : "valid"}`;
    if (!errors.length) {
      box.textContent = (
        "Structure JSON valide : l’export reste disponible indépendamment " +
        "des avertissements de liens."
      );
      byId("copy-json").disabled = false;
      byId("download-json").disabled = false;
      return;
    }
    box.replaceChildren();
    const title = document.createElement("strong");
    title.textContent = `${errors.length} erreur(s) à corriger`;
    box.append(title);
    const list = document.createElement("ul");
    errors.slice(0, 12).forEach((error) => {
      const item = document.createElement("li");
      item.textContent = error;
      list.append(item);
    });
    if (errors.length > 12) {
      const item = document.createElement("li");
      item.textContent = `… et ${errors.length - 12} autre(s).`;
      list.append(item);
    }
    box.append(list);
    byId("copy-json").disabled = true;
    byId("download-json").disabled = true;
  }

  function validateJsonText() {
    try {
      renderValidation(validateDocument(JSON.parse(byId("json-output").value)));
    } catch (error) {
      renderValidation([`JSON invalide : ${error.message}`]);
    }
  }

  function renderSummary() {
    const workflow = records("Workflow").find(
      (item) => item.workflow_id === selectedEntry.workflow_id
    );
    byId("editor-title").textContent = workflow ? workflow.nom : selectedEntry.label;
    byId("editor-summary").replaceChildren(
      ...[
        `${workflowRecords("Etat").length} états`,
        `${workflowRecords("Transition").length} transitions`,
        `${workflowRecords("Regle").length} règles`
      ].map((text) => {
        const badge = document.createElement("span");
        badge.className = "badge";
        badge.textContent = text;
        return badge;
      })
    );
  }

  function renderRecordLinks() {
    const body = byId("link-rows");
    body.replaceChildren();
    const stateIds = new Set(records("Etat").map((state) => state.etat_id));
    const links = [
      ...workflowRecords("Etat").flatMap((record) =>
        recordLinkResults(record, "État", stateIds).map((link) => ({
          record,
          recordType: "État",
          recordId: record.etat_id,
          recordName: record.nom,
          ...link
        }))
      ),
      ...workflowRecords("Transition").flatMap((record) =>
        recordLinkResults(record, "Transition", stateIds).map((link) => ({
          record,
          recordType: "Transition",
          recordId: record.transition_id,
          recordName: record.libelle,
          ...link
        }))
      )
    ];
    links.forEach((link) => {
      const row = document.createElement("tr");
      [link.recordName, link.recordType, link.origin].forEach((text) => {
        const cell = document.createElement("td");
        cell.textContent = text;
        row.append(cell);
      });
      const target = document.createElement("td");
      target.className = "link-target";
      target.textContent = link.target;
      row.append(target);
      const statusCell = document.createElement("td");
      const status = document.createElement("span");
      status.className = `link-status ${link.valid ? "link-valid" : "link-invalid"}`;
      status.textContent = link.valid ? "Valide" : `Invalide — ${link.reason}`;
      statusCell.append(status);
      row.append(statusCell);
      body.append(row);
    });
    const validCount = links.filter((link) => link.valid).length;
    const invalidCount = links.length - validCount;
    byId("link-summary").replaceChildren(
      ...[
        `${links.length} liens détectés`,
        `${validCount} valides`,
        `${invalidCount} invalides`
      ].map((text) => {
        const badge = document.createElement("span");
        badge.className = "badge";
        badge.textContent = text;
        return badge;
      })
    );
    const invalidByRecord = new Map();
    links.filter((link) => !link.valid).forEach((link) => {
      const key = `${link.recordType}:${link.recordId}`;
      if (!invalidByRecord.has(key)) {
        invalidByRecord.set(key, {
          type: link.recordType,
          name: link.recordName,
          targets: []
        });
      }
      invalidByRecord.get(key).targets.push(link.target);
    });
    const alert = byId("invalid-link-alert");
    alert.replaceChildren();
    if (invalidByRecord.size) {
      const title = document.createElement("strong");
      title.textContent = `${invalidByRecord.size} élément(s) contiennent une destination invalide`;
      const list = document.createElement("ul");
      invalidByRecord.forEach((item) => {
        const row = document.createElement("li");
        row.textContent = `${item.type} « ${item.name} » : ${item.targets.join(", ")}`;
        list.append(row);
      });
      alert.append(title, list);
      alert.hidden = false;
    } else {
      alert.hidden = true;
    }
    byId("link-empty").hidden = links.length !== 0;
  }

  function refreshFormOptions() {
    const states = workflowRecords("Etat").sort(
      (a, b) => (Number(a.ordre) || 0) - (Number(b.ordre) || 0)
    );
    const stateItems = states.map((state) => ({
      value: state.etat_id,
      label: `${state.nom} (${state.etat_id})`
    }));
    replaceOptions(byId("transition-source"), stateItems);
    replaceOptions(byId("transition-target"), stateItems);
    const statePicker = byId("state-picker");
    const selectedState = statePicker.value;
    statePicker.replaceChildren(option("", "Nouvel état…"));
    states.forEach((state) => {
      statePicker.append(
        option(
          state.etat_id,
          `${state.nom} — ${state.etat_id}`,
          state.etat_id === selectedState
        )
      );
    });
    const transitionPicker = byId("transition-picker");
    const selectedTransition = transitionPicker.value;
    transitionPicker.replaceChildren(
      option("", "Nouvelle transition…")
    );
    workflowRecords("Transition").forEach((transition) => {
      transitionPicker.append(
        option(
          transition.transition_id,
          `${transition.libelle} — ${transition.transition_id}`,
          transition.transition_id === selectedTransition
        )
      );
    });
    replaceOptions(
      byId("transition-role"),
      records("Role").map((role) => ({ value: role.role_id, label: role.nom })),
      "Aucun rôle"
    );
    replaceOptions(
      byId("state-waterline"),
      workflowRecords("Ligne_eau").map((line) => ({
        value: line.ligne_eau_id, label: line.nom
      })),
      "Aucune ligne d'eau"
    );
  }

  function renderJson() {
    byId("json-output").value = JSON.stringify(documentData, null, 2);
    renderValidation(validateDocument(documentData));
  }

  function renderAll() {
    renderSummary();
    refreshFormOptions();
    renderRecordLinks();
    renderJson();
  }

  function resetStateForm() {
    const form = byId("state-form");
    form.reset();
    form.dataset.editingId = "";
    byId("state-picker").value = "";
    byId("state-new-id-field").hidden = false;
    byId("state-id").required = true;
    byId("state-type").value = "normal";
    byId("state-content-type").value = "markdown";
    byId("state-submit").textContent = "Ajouter l’état";
    byId("state-cancel").hidden = true;
    byId("state-delete").hidden = true;
  }

  function loadState(stateId) {
    const state = workflowRecords("Etat").find(
      (item) => item.etat_id === stateId
    );
    if (!state) return false;
    const form = byId("state-form");
    form.dataset.editingId = state.etat_id;
    byId("state-picker").value = state.etat_id;
    byId("state-id").value = state.etat_id;
    byId("state-new-id-field").hidden = true;
    byId("state-id").required = false;
    byId("state-name").value = state.nom;
    byId("state-content").value = state.contenu || state.description || "";
    byId("state-content-type").value = state.type_contenu || (
      state.description ? "html" : "markdown"
    );
    byId("state-type").value = state.type_etat;
    byId("state-order").value = state.ordre ?? "";
    byId("state-waterline").value = state.ligne_eau_id || "";
    byId("state-link-type").value = state.type_lien || "";
    byId("state-link-target").value = state.cible_lien || "";
    byId("state-link-label").value = state.libelle_lien || "";
    byId("state-submit").textContent = "Enregistrer l’état";
    byId("state-cancel").hidden = false;
    byId("state-delete").hidden = false;
    return true;
  }

  function resetTransitionForm() {
    const form = byId("transition-form");
    form.reset();
    form.dataset.editingId = "";
    byId("transition-active").checked = true;
    byId("transition-picker").value = "";
    byId("transition-new-id-field").hidden = false;
    byId("transition-id").required = true;
    byId("transition-submit").textContent = "Ajouter la transition";
    byId("transition-cancel").hidden = true;
    byId("transition-delete").hidden = true;
  }

  function loadTransition(transitionId) {
    const transition = workflowRecords("Transition").find(
      (item) => item.transition_id === transitionId
    );
    if (!transition) return false;
    const form = byId("transition-form");
    form.dataset.editingId = transition.transition_id;
    byId("transition-picker").value = transition.transition_id;
    byId("transition-id").value = transition.transition_id;
    byId("transition-new-id-field").hidden = true;
    byId("transition-id").required = false;
    byId("transition-source").value = transition.etat_source_id;
    byId("transition-target").value = transition.etat_cible_id;
    byId("transition-label").value = transition.libelle;
    byId("transition-role").value = transition.role_autorise || "";
    byId("transition-condition").value = transition.condition || "";
    byId("transition-link-type").value = transition.type_lien || "";
    byId("transition-link-target").value = transition.cible_lien || "";
    byId("transition-link-label").value = transition.libelle_lien || "";
    byId("transition-active").checked = transition.actif;
    byId("transition-submit").textContent = "Enregistrer la transition";
    byId("transition-cancel").hidden = false;
    byId("transition-delete").hidden = false;
    return true;
  }

  function selectDataset(slug, force = false) {
    const entry = payload.workflows.find((item) => item.slug === slug);
    if (!entry) {
      return;
    }
    if (
      dirty && !force &&
      !window.confirm("Les modifications non enregistrées seront perdues. Continuer ?")
    ) {
      sourceSelect.value = selectedEntry.slug;
      return;
    }
    selectedEntry = entry;
    sourceSelect.value = entry.slug;
    documentData = clone(entry.document);
    byId("state-inventory-link").href = `${entry.slug}/etats.html`;
    byId("workflow-site-link").href = `${entry.slug}/index.html`;
    byId("workflow-document-link").href = entry.document_path;
    byId("workflow-document-path").textContent = entry.document_display_path;
    byId("workflow-manifest-path").textContent = entry.manifest_path;
    byId("workflow-source-paths").replaceChildren(
      ...entry.source_paths.map((path) => {
        const item = document.createElement("li");
        const code = document.createElement("code");
        code.textContent = path;
        item.append(code);
        return item;
      })
    );
    try {
      const editorUrl = new URL(window.location.href);
      editorUrl.searchParams.set("workflow", entry.slug);
      window.history.replaceState(null, "", editorUrl);
    } catch (error) {
      console.debug("Adresse de l’éditeur non mise à jour", error);
    }
    dirty = false;
    resetStateForm();
    resetTransitionForm();
    renderAll();
    setStatus(`Workflow « ${entry.label} » chargé.`);
  }

  function markChanged(message) {
    dirty = true;
    renderAll();
    setStatus(message);
  }

  sourceSelect.addEventListener("change", () => selectDataset(sourceSelect.value));
  byId("reset-workflow").addEventListener("click", () => {
    if (!dirty || window.confirm("Annuler toutes les modifications de ce workflow ?")) {
      selectDataset(selectedEntry.slug, true);
    }
  });

  byId("state-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const editingId = form.dataset.editingId;
    const id = editingId || byId("state-id").value.trim();
    const duplicate = records("Etat").find(
      (item) => item.etat_id === id && item.etat_id !== editingId
    );
    if (!identifierPattern.test(id) || duplicate) {
      setStatus(
        duplicate
          ? `L’identifiant d’état « ${id} » existe déjà.`
          : "L’identifiant doit commencer par une lettre ou _ et ne contenir que lettres, chiffres et _."
      );
      byId("state-id").focus();
      return;
    }
    const existing = records("Etat").find((item) => item.etat_id === editingId);
    const state = {
      ...(existing || {}),
      etat_id: id,
      workflow_id: selectedEntry.workflow_id,
      nom: byId("state-name").value.trim(),
      type_etat: byId("state-type").value
    };
    delete state.description;
    const order = byId("state-order").value;
    const waterline = byId("state-waterline").value;
    const content = byId("state-content").value.trim();
    const linkType = byId("state-link-type").value;
    const linkTarget = byId("state-link-target").value.trim();
    const linkLabel = byId("state-link-label").value.trim();
    if (order === "") delete state.ordre; else state.ordre = Number(order);
    if (waterline) state.ligne_eau_id = waterline; else delete state.ligne_eau_id;
    if (content) {
      state.contenu = content;
      state.type_contenu = byId("state-content-type").value;
    } else {
      delete state.contenu;
      delete state.type_contenu;
    }
    if (linkType || linkTarget || linkLabel) {
      state.type_lien = linkType;
      state.cible_lien = linkTarget;
      if (linkLabel) state.libelle_lien = linkLabel; else delete state.libelle_lien;
    } else {
      delete state.type_lien;
      delete state.cible_lien;
      delete state.libelle_lien;
    }
    if (editingId) {
      Object.assign(existing, state);
      if (editingId !== id) {
        records("Transition").forEach((item) => {
          if (item.etat_source_id === editingId) item.etat_source_id = id;
          if (item.etat_cible_id === editingId) item.etat_cible_id = id;
        });
        records("Regle").forEach((item) => {
          if (item.etat_id === editingId) item.etat_id = id;
        });
      }
    } else {
      records("Etat").push(state);
    }
    resetStateForm();
    markChanged(editingId ? "État mis à jour." : "État ajouté.");
  });

  byId("state-picker").addEventListener("change", (event) => {
    const stateId = event.currentTarget.value;
    if (stateId) {
      loadState(stateId);
    } else {
      resetStateForm();
    }
  });
  byId("state-delete").addEventListener("click", () => {
    const editingId = byId("state-form").dataset.editingId;
    const state = records("Etat").find((item) => item.etat_id === editingId);
    if (!state) return;
    const relatedTransitions = records("Transition").filter(
      (item) => item.etat_source_id === state.etat_id || item.etat_cible_id === state.etat_id
    );
    if (!window.confirm(
      `Supprimer « ${state.nom} » et ${relatedTransitions.length} transition(s) associée(s) ?`
    )) return;
    const removedTransitionIds = new Set(
      relatedTransitions.map((item) => item.transition_id)
    );
    documentData.Etat = records("Etat").filter((item) => item.etat_id !== state.etat_id);
    documentData.Transition = records("Transition").filter(
      (item) => !removedTransitionIds.has(item.transition_id)
    );
    documentData.Regle = records("Regle").filter(
      (item) => item.etat_id !== state.etat_id &&
        !removedTransitionIds.has(item.transition_id)
    );
    resetStateForm();
    resetTransitionForm();
    markChanged("État et références associées supprimés.");
  });
  byId("state-cancel").addEventListener("click", resetStateForm);

  byId("transition-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const editingId = form.dataset.editingId;
    const id = editingId || byId("transition-id").value.trim();
    const duplicate = records("Transition").find(
      (item) => item.transition_id === id && item.transition_id !== editingId
    );
    if (!identifierPattern.test(id) || duplicate) {
      setStatus(
        duplicate
          ? `L’identifiant de transition « ${id} » existe déjà.`
          : "L’identifiant doit commencer par une lettre ou _ et ne contenir que lettres, chiffres et _."
      );
      byId("transition-id").focus();
      return;
    }
    const existing = records("Transition").find(
      (item) => item.transition_id === editingId
    );
    const transition = {
      ...(existing || {}),
      transition_id: id,
      workflow_id: selectedEntry.workflow_id,
      etat_source_id: byId("transition-source").value,
      etat_cible_id: byId("transition-target").value,
      libelle: byId("transition-label").value.trim(),
      actif: byId("transition-active").checked
    };
    const role = byId("transition-role").value;
    const condition = byId("transition-condition").value.trim();
    const linkType = byId("transition-link-type").value;
    const linkTarget = byId("transition-link-target").value.trim();
    const linkLabel = byId("transition-link-label").value.trim();
    if (role) transition.role_autorise = role; else delete transition.role_autorise;
    if (condition) transition.condition = condition; else delete transition.condition;
    if (linkType || linkTarget || linkLabel) {
      transition.type_lien = linkType;
      transition.cible_lien = linkTarget;
      if (linkLabel) transition.libelle_lien = linkLabel;
      else delete transition.libelle_lien;
    } else {
      delete transition.type_lien;
      delete transition.cible_lien;
      delete transition.libelle_lien;
    }
    if (editingId) {
      Object.assign(existing, transition);
      if (editingId !== id) {
        records("Regle").forEach((item) => {
          if (item.transition_id === editingId) item.transition_id = id;
        });
      }
    } else {
      records("Transition").push(transition);
    }
    resetTransitionForm();
    markChanged(editingId ? "Transition mise à jour." : "Transition ajoutée.");
  });

  byId("transition-picker").addEventListener("change", (event) => {
    const transitionId = event.currentTarget.value;
    if (transitionId) {
      loadTransition(transitionId);
    } else {
      resetTransitionForm();
    }
  });
  byId("transition-delete").addEventListener("click", () => {
    const editingId = byId("transition-form").dataset.editingId;
    const transition = records("Transition").find(
      (item) => item.transition_id === editingId
    );
    if (!transition) return;
    if (!window.confirm(`Supprimer la transition « ${transition.libelle} » ?`)) return;
    documentData.Transition = records("Transition").filter(
      (item) => item.transition_id !== transition.transition_id
    );
    documentData.Regle = records("Regle").filter(
      (item) => item.transition_id !== transition.transition_id
    );
    resetTransitionForm();
    markChanged("Transition et règles associées supprimées.");
  });
  byId("transition-cancel").addEventListener("click", resetTransitionForm);

  byId("json-output").addEventListener("input", () => {
    window.clearTimeout(jsonTimer);
    byId("copy-json").disabled = true;
    byId("download-json").disabled = true;
    const validation = byId("json-validation");
    validation.className = "validation-summary";
    validation.textContent = "Validation en cours…";
    jsonTimer = window.setTimeout(validateJsonText, 180);
  });
  byId("apply-json").addEventListener("click", () => {
    try {
      const candidate = JSON.parse(byId("json-output").value);
      const errors = validateDocument(candidate);
      renderValidation(errors);
      if (errors.length) {
        setStatus("Le JSON n’a pas été appliqué : corrigez les erreurs signalées.");
        return;
      }
      documentData = candidate;
      dirty = true;
      resetStateForm();
      resetTransitionForm();
      renderAll();
      setStatus("Les modifications JSON ont été appliquées aux formulaires.");
    } catch (error) {
      renderValidation([`JSON invalide : ${error.message}`]);
      setStatus("Le JSON n’a pas été appliqué.");
    }
  });

  byId("copy-json").addEventListener("click", async () => {
    const text = byId("json-output").value;
    try {
      await navigator.clipboard.writeText(text);
    } catch (error) {
      const editor = byId("json-output");
      editor.focus();
      editor.select();
      document.execCommand("copy");
    }
    setStatus("JSON copié dans le presse-papiers.");
  });
  byId("download-json").addEventListener("click", async () => {
    const contents = byId("json-output").value + "\n";
    const suggestedName = `${selectedEntry.slug}-modifie.json`;
    if (supportsFilePicker) {
      try {
        const handle = await window.showSaveFilePicker({
          suggestedName,
          types: [{
            description: "Document JSON de workflow",
            accept: { "application/json": [".json"] }
          }]
        });
        const writable = await handle.createWritable();
        await writable.write(contents);
        await writable.close();
        dirty = false;
        setStatus(`Fichier ${handle.name || suggestedName} enregistré sur le disque.`);
        return;
      } catch (error) {
        if (error && error.name === "AbortError") {
          setStatus("Enregistrement annulé.");
          return;
        }
        console.debug("Sélecteur d’enregistrement indisponible", error);
      }
    }
    const blob = new Blob([contents], {
      type: "application/json;charset=utf-8"
    });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = suggestedName;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
    dirty = false;
    setStatus(
      `Fichier ${link.download} enregistré dans les téléchargements du navigateur.`
    );
  });

  payload.workflows.forEach((entry) => {
    sourceSelect.append(option(entry.slug, entry.label));
  });
  const requestedSlug = new URLSearchParams(window.location.search).get("workflow");
  const initialSlug = payload.workflows.some((entry) => entry.slug === requestedSlug)
    ? requestedSlug
    : payload.workflows[0].slug;
  selectDataset(initialSlug, true);
})();"""


def diagram_panel(title: str, diagram: str) -> str:
    return f"""\
<section class="panel">
  <h2>{escape(title)}</h2>
  <p class="notice" data-mermaid-notice hidden>
    Mermaid n'a pas pu être chargé ou rendre ce diagramme. Le code source reste affiché.
  </p>
  <pre class="mermaid">{escape(diagram)}</pre>
  <details class="diagram-source">
    <summary>Afficher le code Mermaid</summary>
    <pre class="code-block"><code>{escape(diagram)}</code></pre>
  </details>
</section>"""


def state_description(state: Mapping[str, Any]) -> str:
    return sanitize_documentation(state.get("description"), "html")


def state_content(state: Mapping[str, Any]) -> str:
    if state.get("contenu"):
        return sanitize_documentation(
            state.get("contenu"), state.get("type_contenu")
        )
    return state_description(state)


def state_card(
    state: Mapping[str, Any],
    state_href: str | None = None,
    link_prefix: str = "",
    *,
    phase_targets: Iterable[str] = (),
    state_ids: Iterable[str] = (),
    show_link_status: bool = False,
) -> str:
    title = escape(state["nom"])
    if state_href:
        title = f'<a href="{escape(state_href)}">{title}</a>'
    content = state_content(state)
    text = f'<div class="state-text">{content}</div>' if content else ""
    navigation_href = record_link_href(state, link_prefix)
    if phase_targets or state_ids:
        link_valid, _ = record_link_validation(
            state, phase_targets=phase_targets, state_ids=state_ids
        )
        if link_valid is not True:
            navigation_href = None
    navigation = (
        f'<p><a href="{escape(navigation_href)}">'
        f'{escape(state.get("libelle_lien") or "Ouvrir la page associée")} →</a></p>'
        if navigation_href and not show_link_status
        else ""
    )
    link_status = (
        record_link_status_html(
            state,
            root_prefix=link_prefix,
            phase_targets=phase_targets,
            state_ids=state_ids,
        )
        if show_link_status
        else ""
    )
    return f"""\
<article class="state-card" id="{escape(state['etat_id'])}">
  <span class="badge">{escape(state["type_etat"])}</span>
  <h3>{title}</h3>
  {text}
  {navigation}
  {link_status}
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
    *,
    root_prefix: str,
) -> str:
    phase_items = "".join(
        f'<li><a href="{escape(root_prefix)}phases/{escape(file_name)}">'
        f"{escape(label)}</a></li>"
        for label, file_name in phases
    )
    return f"""\
<div class="sidebar-wrapper">
  <button class="sidebar-toggle" type="button" data-sidebar-toggle
    aria-expanded="true" aria-controls="workflow-sidebar"
    aria-label="Masquer la navigation" title="Masquer la navigation">
    ☰
  </button>
  <aside class="sidebar" id="workflow-sidebar">
    <strong>Phases</strong>
    <ul>{phase_items}</ul>
  </aside>
</div>"""
