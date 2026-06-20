import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    PROJECT_ROOT / "data" / "workflows" / "projet-informatique" / "manifest.json"
)
SCHEMA = PROJECT_ROOT / "schema" / "workflow-model.json"
EXAMPLE = PROJECT_ROOT / "examples" / "workflow-data.json"


class WorkflowCliFunctionalTests(unittest.TestCase):
    maxDiff = None

    def run_cli(self, script, *arguments):
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / script), *map(str, arguments)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
            check=False,
        )

    def test_validate_data_cli(self):
        result = self.run_cli("validate_workflow_data.py", MANIFEST)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Compatibilité validée: 6 tables, 108 enregistrements.", result.stdout)

    def test_mermaid_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "workflow.md"
            result = self.run_cli(
                "generate_mermaid.py",
                MANIFEST,
                "--diagram",
                "both",
                "--workflow-id",
                "Projet_informatique",
                "--output",
                output,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            content = output.read_text(encoding="utf-8")
            self.assertIn("flowchart TD", content)
            self.assertIn("stateDiagram-v2", content)
            self.assertIn("Decommissionne --> [*]", content)

    def test_html_page_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "workflow.html"
            result = self.run_cli(
                "generate_workflow_html.py", MANIFEST, "--output", output
            )

            self.assertEqual(0, result.returncode, result.stderr)
            content = output.read_text(encoding="utf-8")
            self.assertLess(content.index("flowchart TD"), content.index("Description des états"))
            self.assertNotIn("stateDiagram-v2", content)
            self.assertIn("La personne publique ou l&#x27;organisation", content)

    def test_static_site_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            result = self.run_cli(
                "generate_workflow_site.py", MANIFEST, "--output", output
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((output / "index.html").is_file())
            self.assertTrue((output / "etats.html").is_file())
            self.assertFalse((output / "workflow.html").exists())
            self.assertEqual(34, len(list((output / "states").glob("*.html"))))
            maintenance = (output / "states" / "Maintenance.html").read_text(
                encoding="utf-8"
            )
            self.assertIn("Fin_maintenance_decidee.html", maintenance)
            index = (output / "index.html").read_text(encoding="utf-8")
            all_states = (output / "etats.html").read_text(encoding="utf-8")
            script = (output / "assets" / "app.js").read_text(encoding="utf-8")
            self.assertIn('<script defer src="assets/app.js"></script>', index)
            self.assertNotIn('type="module"', index)
            self.assertIn("await import(", script)
            self.assertIn('securityLevel: "loose"', script)
            self.assertNotIn("stateDiagram-v2", index)
            self.assertNotIn("<dt>Workflow</dt>", index)
            self.assertNotIn("<dt>États détaillés</dt>", index)
            self.assertNotIn("<dt>Phases</dt>", index)
            self.assertNotIn("état(s)", index)
            self.assertNotIn("<strong>États</strong>", index)
            self.assertNotIn("<p>Source :", index)
            self.assertIn('class="info-tooltip"', index)
            self.assertIn(
                'title="Source : 01-cadrage-budgetisation.json"',
                index,
            )
            self.assertIn(
                'click Phase_Cadrage_budgetisation '
                '&quot;phases/01-cadrage-budgetisation.html&quot;',
                index,
            )
            self.assertIn("Tous les états", all_states)
            self.assertIn("states/Decommissionne.html", all_states)
            self.assertIn("<strong>États</strong>", all_states)
            first_phase = (
                output / "phases" / "01-cadrage-budgetisation.html"
            ).read_text(encoding="utf-8")
            self.assertIn(
                'click Budget_valide '
                '&quot;../phases/02-specifications-conception-marche.html&quot;',
                first_phase,
            )

    def test_unsafe_html_is_filtered_end_to_end(self):
        data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        data["Etat"][0]["description"] = (
            '<p onclick="alert(1)">Documenté</p>'
            '<script>alert(2)</script>'
            '<a href="javascript:alert(3)">Lien</a>'
        )
        data["Etat"][0]["type_contenu"] = "html"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "unsafe.json"
            output = Path(directory) / "unsafe.html"
            source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            result = self.run_cli(
                "generate_workflow_html.py",
                source,
                "--schema",
                SCHEMA,
                "--output",
                output,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            content = output.read_text(encoding="utf-8")
            self.assertNotIn("onclick", content)
            self.assertNotIn("<script>alert(2)</script>", content)
            self.assertNotIn("javascript:alert(3)", content)
            self.assertIn("<p>Documenté</p>", content)

    def test_traceability_cli(self):
        result = self.run_cli("validate_traceability.py")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Traçabilité validée: 7 exigences.", result.stdout)


if __name__ == "__main__":
    unittest.main()
