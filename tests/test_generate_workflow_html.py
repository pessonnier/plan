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
    def test_single_page_contains_flowchart_then_phase_descriptions(self):
        page = generate_workflow_html.render_workflow_page(MANIFEST)

        flowchart_position = page.index("flowchart TD")
        descriptions_position = page.index("Description des états")
        first_description_position = page.index(
            "La personne publique ou l&#x27;organisation qualifie le besoin"
        )

        self.assertLess(flowchart_position, descriptions_position)
        self.assertLess(descriptions_position, first_description_position)
        self.assertNotIn("stateDiagram-v2", page)
        self.assertIn('id="Phase_Cadrage_budgetisation"', page)

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

    def test_static_site_contains_navigation_and_all_state_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"

            generate_workflow_site.generate_site(MANIFEST, output)

            self.assertTrue((output / "index.html").is_file())
            self.assertTrue((output / "etats.html").is_file())
            self.assertFalse((output / "workflow.html").exists())
            self.assertTrue((output / "assets" / "style.css").is_file())
            self.assertTrue((output / "assets" / "app.js").is_file())
            state_pages = list((output / "states").glob("*.html"))
            phase_pages = list((output / "phases").glob("*.html"))
            self.assertEqual(34, len(state_pages))
            self.assertEqual(6, len(phase_pages))

            maintenance = (output / "states" / "Maintenance.html").read_text(
                encoding="utf-8"
            )
            self.assertIn("../index.html", maintenance)
            self.assertIn("Fin_maintenance_decidee.html", maintenance)
            self.assertIn("Contrôles associés", maintenance)

            index = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn("phases/01-cadrage-budgetisation.html", index)
            all_states = (output / "etats.html").read_text(encoding="utf-8")
            phase = (
                output / "phases" / "01-cadrage-budgetisation.html"
            ).read_text(encoding="utf-8")
            self.assertIn("Vue d&#x27;ensemble des phases", index)
            self.assertIn("Tous les états", all_states)
            self.assertIn("states/Decommissionne.html", all_states)
            self.assertNotIn("<strong>États</strong>", index)
            self.assertIn("<strong>États</strong>", all_states)
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

            for page_path in output.glob("**/*.html"):
                collector = LinkCollector()
                collector.feed(page_path.read_text(encoding="utf-8"))
                for href in collector.links:
                    if "://" in href or href.startswith(("mailto:", "#")):
                        continue
                    target = (page_path.parent / href.split("#", 1)[0]).resolve()
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

    def test_static_site_uses_file_compatible_mermaid_bootstrap(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"

            generate_workflow_site.generate_site(MANIFEST, output)

            index_page = (output / "index.html").read_text(encoding="utf-8")
            script = (output / "assets" / "app.js").read_text(encoding="utf-8")
            self.assertIn('<script defer src="assets/app.js"></script>', index_page)
            self.assertNotIn('type="module"', index_page)
            self.assertIn("(async () => {", script)
            self.assertIn("await import(", script)
            self.assertIn('securityLevel: "loose"', script)
            self.assertIn('dataset.mermaidRendered = "true"', script)


if __name__ == "__main__":
    unittest.main()
