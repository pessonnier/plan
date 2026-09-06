import hashlib
import json
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import generate_workflow_html
import generate_workflow_site
import html_rendering


MANIFEST = (
    PROJECT_ROOT / "data" / "workflows" / "projet-informatique" / "manifest.json"
)
CATALOG = PROJECT_ROOT / "data" / "workflows" / "catalog.json"


class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = next((value for name, value in attrs if name == "href"), None)
        if href:
            self.links.append(href)


class GenerateWorkflowHtmlTests(unittest.TestCase):
    def test_default_mermaid_renderer_supports_native_swimlanes(self):
        self.assertEqual(
            html_rendering.MERMAID_DEPENDENCY["url"],
            html_rendering.DEFAULT_MERMAID_URL,
        )
        self.assertEqual(
            html_rendering.MERMAID_DEPENDENCY["sha256"],
            hashlib.sha256(
                html_rendering.VENDORED_MERMAID_PATH.read_bytes()
            ).hexdigest(),
        )

    def test_single_page_contains_flowchart_then_state_texts(self):
        page = generate_workflow_html.render_workflow_page(MANIFEST)

        flowchart_position = page.index("flowchart LR")
        descriptions_position = page.index("Textes des états")
        first_description_position = page.index(
            "La personne publique ou l&#x27;organisation qualifie le besoin"
        )

        self.assertLess(flowchart_position, descriptions_position)
        self.assertLess(descriptions_position, first_description_position)
        self.assertNotIn("stateDiagram-v2", page.split("<script>", 1)[0])
        self.assertIn('id="Phase_Cadrage_budgetisation"', page)
        self.assertNotIn("cdn.jsdelivr.net", page)
        self.assertIn("embedded:mermaid", page)

    def test_documentation_html_is_sanitized(self):
        unsafe = (
            '<p onclick="alert(1)">Texte</p>'
            '<script>alert(2)</script>'
            '<a href="javascript:alert(3)">Lien</a>'
        )

        rendered = html_rendering.sanitize_documentation(unsafe)

        self.assertNotIn("onclick", rendered)
        self.assertNotIn("<script", rendered)
        self.assertNotIn("javascript:", rendered)
        self.assertIn("<p>Texte</p>", rendered)
        self.assertIn("<a>Lien</a>", rendered)

    def test_non_html_documentation_is_escaped(self):
        rendered = html_rendering.sanitize_documentation(
            "<strong>non interprété</strong>", "texte"
        )

        self.assertEqual(
            "<p>&lt;strong&gt;non interprété&lt;/strong&gt;</p>", rendered
        )

    def test_static_site_has_state_directory_without_individual_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"

            generate_workflow_site.generate_site(MANIFEST, output)

            self.assertTrue((output / "index.html").is_file())
            self.assertTrue((output / "etats.html").is_file())
            self.assertTrue((output / "transitions.html").is_file())
            self.assertFalse((output / "workflow.html").exists())
            self.assertTrue((output / "assets" / "style.css").is_file())
            self.assertTrue((output / "assets" / "app.js").is_file())
            phase_pages = list((output / "phases").glob("*.html"))
            self.assertFalse((output / "states").exists())
            self.assertEqual(6, len(phase_pages))

            index = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn("phases/01-cadrage-budgetisation.html", index)
            all_states = (output / "etats.html").read_text(encoding="utf-8")
            all_transitions = (output / "transitions.html").read_text(
                encoding="utf-8"
            )
            phase = (
                output / "phases" / "01-cadrage-budgetisation.html"
            ).read_text(encoding="utf-8")
            self.assertIn("Vue d&#x27;ensemble des phases", index)
            self.assertIn("flowchart LR", index)
            self.assertIn("Workflow complet par acteur et ligne d’eau", index)
            self.assertIn("swimlane-beta LR", index)
            self.assertGreaterEqual(index.count("Afficher le code Mermaid"), 2)
            self.assertIn('class="diagram-source"', index)
            self.assertIn("Qualité et tests", index)
            self.assertIn("Protection&lt;br/&gt;des données", index)
            self.assertIn("Comité des&lt;br/&gt;changements", index)
            self.assertIn("Répertoire des états", all_states)
            self.assertIn("Répertoire des transitions", all_transitions)
            self.assertIn("Cette page d’exemple présente les 38 transitions", all_transitions)
            self.assertIn("financement autorisé", all_transitions)
            self.assertIn("Page de phase existante", all_transitions)
            self.assertIn("L’état « Transition_budget_supprimee » n’existe pas.", all_transitions)
            self.assertIn('href="transitions.html"', index)
            self.assertIn("Invalide", all_states)
            self.assertNotIn("states/Decommissionne.html", all_states)
            self.assertNotIn("<strong>États</strong>", index)
            self.assertNotIn("<strong>États</strong>", all_states)
            self.assertIn('data-sidebar-toggle', index)
            self.assertIn('aria-controls="workflow-sidebar"', index)
            self.assertIn('aria-label="Masquer la navigation"', index)
            self.assertIn("☰", index)
            self.assertNotIn("<dt>Workflow</dt>", index)
            self.assertNotIn("<dt>États détaillés</dt>", index)
            self.assertNotIn("<dt>Phases</dt>", index)
            self.assertNotIn("état(s)", index)
            self.assertNotIn("<p>Source :", index)
            self.assertIn('class="info-tooltip"', index)
            self.assertIn(
                'title="Source : 01-cadrage-budgetisation.json"',
                index,
            )
            self.assertNotIn("stateDiagram-v2", index)
            self.assertIn(
                'click Phase_Cadrage_budgetisation '
                '&quot;phases/01-cadrage-budgetisation.html&quot;',
                index,
            )
            self.assertIn(
                'click Budget_valide '
                '&quot;../phases/02-specifications-conception-marche.html&quot;',
                phase,
            )
            self.assertIn("swimlane-beta LR", phase)
            self.assertIn("Afficher le code Mermaid", phase)
            self.assertIn('class="code-block"', phase)
            self.assertNotIn("<h2>Transitions de la phase</h2>", phase)
            phase_title = phase.index(
                "<h2>Cadrage et programmation budgétaire</h2>"
            )
            diagram = phase.index('<pre class="mermaid">', phase_title)
            phase_panel_end = phase.index("</section>", phase_title)
            self.assertLess(phase_title, diagram)
            self.assertLess(diagram, phase_panel_end)
            self.assertIn(
                "Opportunite_qualifiee --&gt;|cadrage lancé| Cadrage",
                phase,
            )
            self.assertIn(
                "Budget_estime --&gt;|financement autorisé| Budget_valide",
                phase,
            )

            for page_path in output.glob("**/*.html"):
                collector = LinkCollector()
                collector.feed(page_path.read_text(encoding="utf-8"))
                for href in collector.links:
                    if "://" in href or href.startswith(("mailto:", "#")):
                        continue
                    link_path = href.split("#", 1)[0].split("?", 1)[0]
                    target = (page_path.parent / link_path).resolve()
                    with self.subTest(page=page_path.name, href=href):
                        self.assertTrue(target.is_file())

    def test_site_mermaid_url_is_configurable(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            custom_url = "https://example.test/mermaid.mjs"

            generate_workflow_site.generate_site(
                MANIFEST, output, mermaid_url=custom_url
            )

            script = (output / "assets" / "app.js").read_text(encoding="utf-8")
            self.assertIn(custom_url, script)
            self.assertFalse((output / "assets" / "mermaid.min.js").exists())

    def test_static_site_uses_file_compatible_mermaid_bootstrap(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"

            generate_workflow_site.generate_site(MANIFEST, output)

            index_page = (output / "index.html").read_text(encoding="utf-8")
            script = (output / "assets" / "app.js").read_text(encoding="utf-8")
            renderer = output / "assets" / "mermaid.min.js"
            renderer_license = output / "assets" / "MERMAID-LICENSE.txt"
            self.assertIn('<script defer src="assets/app.js"></script>', index_page)
            self.assertNotIn('type="module"', index_page)
            self.assertTrue(renderer.is_file())
            self.assertTrue(renderer_license.is_file())
            self.assertEqual(
                html_rendering.VENDORED_MERMAID_PATH.read_bytes(),
                renderer.read_bytes(),
            )
            self.assertIn("(async () => {", script)
            self.assertIn("await import(", script)
            self.assertIn('document.createElement("script")', script)
            self.assertIn("window.mermaid", script)
            self.assertIn("const configuredUrl = 'mermaid.min.js'", script)
            self.assertNotIn("cdn.jsdelivr.net", script)
            self.assertIn('securityLevel: "loose"', script)
            self.assertIn('htmlLabels: true', script)
            self.assertIn('rankSpacing: diagramConfig.rank_spacing', script)
            self.assertIn('swimlane: { useMaxWidth: diagramConfig.use_max_width }', script)
            self.assertIn('"rank_spacing": 20', script)
            self.assertIn('"lane_title_wrap": 18', script)
            self.assertIn('`${Math.ceil(viewBox.width)}px`', script)
            self.assertIn("workflow-navigation-collapsed", script)
            self.assertIn('localStorage.setItem(storageKey', script)
            self.assertIn('classList.toggle("sidebar-collapsed"', script)
            self.assertIn('button.textContent = "☰"', script)
            self.assertIn('button.setAttribute("title", label)', script)
            self.assertNotIn("normalizeBpmnLanes", script)
            self.assertNotIn('cluster.id.includes("-Participant_")', script)
            self.assertNotIn('cluster.id.includes("-Ligne_eau_")', script)
            self.assertIn('dataset.mermaidRendered = "true"', script)
            self.assertIn('new CustomEvent("workflow-theme-change"', script)
            self.assertIn('node.removeAttribute("data-processed")', script)
            self.assertIn("await renderMermaidDiagrams()", script)

    def test_catalog_generates_workflow_choice_and_two_sites(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "catalog"

            generate_workflow_site.generate_site(CATALOG, output)

            portal = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn("Projet informatique", portal)
            self.assertIn("Analyse statique de code", portal)
            self.assertIn("Documentation", portal)
            self.assertIn("projet-informatique/index.html", portal)
            self.assertIn("analyse-statique-code/index.html", portal)
            self.assertIn("documentation/index.html", portal)
            self.assertTrue((output / "projet-informatique" / "etats.html").is_file())
            self.assertTrue(
                (output / "projet-informatique" / "transitions.html").is_file()
            )
            self.assertTrue(
                (output / "analyse-statique-code" / "etats.html").is_file()
            )
            self.assertTrue(
                (output / "analyse-statique-code" / "transitions.html").is_file()
            )
            self.assertTrue((output / "editor.html").is_file())
            self.assertTrue((output / "settings.html").is_file())
            self.assertTrue((output / "assets" / "editor.js").is_file())
            analysis_index = (
                output / "analyse-statique-code" / "index.html"
            ).read_text(encoding="utf-8")
            self.assertIn("Choisir un workflow", analysis_index)
            self.assertIn("flowchart LR", analysis_index)
            self.assertIn("../index.html", analysis_index)
            self.assertIn(
                '../editor.html?workflow=analyse-statique-code', analysis_index
            )
            self.assertIn('href="settings.html"', analysis_index)
            self.assertTrue(
                (output / "analyse-statique-code" / "settings.html").is_file()
            )
            self.assertIn(
                'data-theme-scope="workflow-analyse-statique-code"',
                analysis_index,
            )
            analysis_theme = json.loads(
                (CATALOG.parent / "analyse-statique-code" / "manifest.json").read_text(
                    encoding="utf-8"
                )
            )["site"]["theme"]
            catalog_theme = json.loads(CATALOG.read_text(encoding="utf-8"))["theme"]
            self.assertIn(
                f'data-theme-default-pair="{analysis_theme["pair"]}"',
                analysis_index,
            )
            self.assertIn(
                f'data-theme-default-pair="{catalog_theme["pair"]}"', portal
            )
            self.assertFalse(
                (output / "analyse-statique-code" / "states").exists()
            )
            documentation_guide = (
                output / "documentation" / "guide.html"
            ).read_text(encoding="utf-8")
            self.assertIn("Guide visuel des éléments de workflow", documentation_guide)
            self.assertIn("Catalogue étendu — données", documentation_guide)
            self.assertIn("swimlane-beta LR", documentation_guide)
            self.assertIn("stateDiagram-v2", documentation_guide)
            self.assertIn("sequenceDiagram", documentation_guide)
            self.assertIn("Nœuds cliquables et aide au survol", documentation_guide)
            self.assertIn("rank_spacing", documentation_guide)
            self.assertIn("ne change pas la largeur", documentation_guide)
            self.assertIn('href="guide.html"', documentation_guide)
            self.assertNotIn("cdn.jsdelivr.net", documentation_guide)
            settings = (output / "settings.html").read_text(encoding="utf-8")
            site_script = (output / "assets" / "app.js").read_text(encoding="utf-8")
            self.assertIn('id="theme-pair"', settings)
            self.assertIn('id="theme-mode"', settings)
            self.assertIn('value="dark"', settings)
            self.assertIn('value="forest"', settings)
            self.assertIn('value="aubergine"', settings)
            self.assertIn('value="graphite"', settings)
            self.assertIn("workflow-site-theme:${scope}:pair", settings)
            self.assertIn("workflow-site-theme:${scope}:mode", settings)
            self.assertIn("workflow-site-theme:${scope}:configuration", settings)
            self.assertIn("theme-mode-toggle", site_script)
            self.assertIn("Activer le mode sombre", site_script)
            self.assertNotIn("cdn.jsdelivr.net", settings)

            for page_path in output.glob("**/*.html"):
                collector = LinkCollector()
                collector.feed(page_path.read_text(encoding="utf-8"))
                for href in collector.links:
                    if "://" in href or href.startswith(("mailto:", "#")):
                        continue
                    link_path = href.split("#", 1)[0].split("?", 1)[0]
                    target = (page_path.parent / link_path).resolve()
                    with self.subTest(page=page_path, href=href):
                        self.assertTrue(target.is_file())

    def test_catalog_editor_embeds_workflows_and_editor_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "catalog"

            generate_workflow_site.generate_site(CATALOG, output)

            editor = (output / "editor.html").read_text(encoding="utf-8")
            script = (output / "assets" / "editor.js").read_text(encoding="utf-8")
            self.assertIn("Projet informatique", editor)
            self.assertIn("Analyse statique de code", editor)
            self.assertIn('"workflow_id":"Projet_informatique"', editor)
            self.assertIn('id="state-form"', editor)
            self.assertIn('id="state-picker"', editor)
            self.assertIn('id="state-new-id-field"', editor)
            self.assertIn('id="state-delete"', editor)
            self.assertIn('id="state-inventory-link"', editor)
            self.assertIn('id="workflow-site-link"', editor)
            self.assertIn('id="workflow-document-link"', editor)
            self.assertIn('id="workflow-document-path"', editor)
            self.assertIn('id="workflow-manifest-path"', editor)
            self.assertIn('id="workflow-source-paths"', editor)
            self.assertIn("sources/documentation.json", editor)
            self.assertIn('href="settings.html"', editor)
            self.assertNotIn('id="state-rows"', editor)
            self.assertIn('id="toggle-editor-layout"', editor)
            self.assertIn('id="editor-grid"', editor)
            self.assertIn("Placer les transitions en dessous", editor)
            self.assertIn('id="state-content"', editor)
            self.assertIn('id="state-content-type"', editor)
            self.assertNotIn('id="state-description"', editor)
            self.assertIn('id="state-link-target"', editor)
            self.assertIn('id="link-rows"', editor)
            self.assertIn('id="invalid-link-alert"', editor)
            self.assertIn("Vocabulaire à employer", editor)
            self.assertIn("il ne bloque ni la copie", editor)
            self.assertIn('id="transition-form"', editor)
            self.assertIn('id="transition-picker"', editor)
            self.assertIn('id="transition-new-id-field"', editor)
            self.assertIn('id="transition-delete"', editor)
            self.assertIn('id="transition-link-type"', editor)
            self.assertIn('id="transition-link-target"', editor)
            self.assertIn('id="transition-link-label"', editor)
            self.assertNotIn('id="transition-rows"', editor)
            self.assertNotIn("<datalist", editor)
            self.assertIn('id="json-output"', editor)
            self.assertIn('id="download-json"', editor)
            self.assertIn("Enregistrer le JSON sous…", editor)
            self.assertIn("ne modifie", editor)
            self.assertTrue(script.startswith("(() => {"))
            self.assertIn("validateDocument", script)
            self.assertIn("extractTextLinks", script)
            self.assertIn("checkStructuredLink", script)
            self.assertIn("renderRecordLinks", script)
            self.assertIn('recordLinkResults(record, "Transition"', script)
            self.assertIn("loadState", script)
            self.assertIn(
                "`${state.nom} — ${state.etat_id}`",
                script,
            )
            self.assertIn('`${entry.slug}/etats.html`', script)
            self.assertIn("workflow-editor-transitions-below", script)
            self.assertIn('classList.toggle("transitions-below"', script)
            self.assertIn("localStorage.setItem(editorLayoutKey", script)
            self.assertIn("loadTransition", script)
            self.assertIn('new URLSearchParams(window.location.search)', script)
            self.assertIn('byId("workflow-site-link").href', script)
            self.assertIn('editorUrl.searchParams.set("workflow", entry.slug)', script)
            self.assertIn(
                "`${transition.libelle} — ${transition.transition_id}`",
                script,
            )
            self.assertNotIn("cible_lien est invalide", script)
            self.assertIn("JSON.stringify(documentData, null, 2)", script)
            self.assertIn("documentData.Transition", script)
            self.assertIn('typeof window.showSaveFilePicker === "function"', script)
            self.assertIn("await handle.createWritable()", script)
            self.assertIn("enregistré dans les téléchargements", script)
            self.assertIn("notamment Firefox", script)
            self.assertIn("Toujours demander où", script)
            self.assertIn('byId("workflow-document-path").textContent', script)
            self.assertTrue(
                (output / "sources" / "documentation.json").is_file()
            )


if __name__ == "__main__":
    unittest.main()
