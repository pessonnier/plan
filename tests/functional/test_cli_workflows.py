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
CATALOG = PROJECT_ROOT / "data" / "workflows" / "catalog.json"
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
        self.assertIn("Compatibilité validée: 8 tables, 122 enregistrements.", result.stdout)

    def test_validate_data_cli_rejects_dangling_reference(self):
        data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        data["Transition"][0]["etat_cible_id"] = "Etat_absent"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "invalid-reference.json"
            source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            result = self.run_cli(
                "validate_workflow_data.py",
                source,
                "--schema",
                SCHEMA,
            )

        self.assertEqual(2, result.returncode)
        self.assertIn("référence introuvable", result.stderr)

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
            self.assertIn("swimlane-beta LR", content)
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
            self.assertLess(
                content.index("flowchart LR"), content.index("Textes des états")
            )
            self.assertNotIn("stateDiagram-v2", content.split("<script>", 1)[0])
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
            self.assertTrue((output / "transitions.html").is_file())
            self.assertFalse((output / "workflow.html").exists())
            self.assertFalse((output / "states").exists())
            index = (output / "index.html").read_text(encoding="utf-8")
            all_states = (output / "etats.html").read_text(encoding="utf-8")
            all_transitions = (output / "transitions.html").read_text(
                encoding="utf-8"
            )
            script = (output / "assets" / "app.js").read_text(encoding="utf-8")
            self.assertIn('<script defer src="assets/app.js"></script>', index)
            self.assertNotIn('type="module"', index)
            self.assertIn("await import(", script)
            self.assertIn('securityLevel: "loose"', script)
            self.assertNotIn("stateDiagram-v2", index)
            self.assertIn("flowchart LR", index)
            self.assertNotIn("<dt>Workflow</dt>", index)
            self.assertNotIn("<dt>États détaillés</dt>", index)
            self.assertNotIn("<dt>Phases</dt>", index)
            self.assertNotIn("état(s)", index)
            self.assertNotIn("<strong>États</strong>", index)
            self.assertIn('aria-label="Masquer la navigation"', index)
            self.assertIn("☰", index)
            self.assertIn("workflow-navigation-collapsed", script)
            self.assertIn('classList.toggle("sidebar-collapsed"', script)
            self.assertIn('button.textContent = "☰"', script)
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
            self.assertIn("Répertoire des états", all_states)
            self.assertIn("Répertoire des transitions", all_transitions)
            self.assertIn("Invalide", all_transitions)
            self.assertNotIn("states/Decommissionne.html", all_states)
            self.assertNotIn("<strong>États</strong>", all_states)
            first_phase = (
                output / "phases" / "01-cadrage-budgetisation.html"
            ).read_text(encoding="utf-8")
            self.assertIn(
                'subgraph Ligne_eau_Pilotage_gouvernance '
                '[&quot;Direction&lt;br/&gt;financière&quot;]',
                first_phase,
            )
            self.assertIn("swimlane-beta LR", first_phase)
            self.assertNotIn("subgraph Participant_Organisation_porteuse", first_phase)
            self.assertIn(
                'subgraph Ligne_eau_Responsable_conduite_projet '
                '[&quot;Responsable de&lt;br/&gt;conduite de projet&quot;]',
                first_phase,
            )
            self.assertIn(
                'subgraph Ligne_eau_Sponsor_metiers '
                '[&quot;Sponsor métier&quot;]',
                first_phase,
            )
            self.assertNotIn("Organisation porteuse du projet —", first_phase)
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
            body = content.split("<body>", 1)[1].split("</body>", 1)[0]
            document_body = body.split("<script", 1)[0]
            self.assertNotIn("onclick", document_body)
            self.assertNotIn("<script>alert(2)</script>", document_body)
            self.assertNotIn("javascript:alert(3)", document_body)
            self.assertIn("<p>Documenté</p>", document_body)

    def test_traceability_cli(self):
        result = self.run_cli("validate_traceability.py")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Traçabilité validée: 10 exigences.", result.stdout)

    def test_tui_headless_list_does_not_require_textual(self):
        result = self.run_cli("workflow_tui.py", "--list", "--catalog", CATALOG)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("documentation\tDocumentation", result.stdout)
        self.assertIn("projet-informatique\tProjet informatique", result.stdout)

    def test_catalog_site_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "catalog"
            result = self.run_cli(
                "generate_workflow_site.py", CATALOG, "--output", output
            )

            self.assertEqual(0, result.returncode, result.stderr)
            portal = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn("Projet informatique", portal)
            self.assertIn("Analyse statique de code", portal)
            self.assertTrue(
                (output / "projet-informatique" / "index.html").is_file()
            )
            self.assertTrue(
                (output / "analyse-statique-code" / "index.html").is_file()
            )
            self.assertTrue(
                (output / "projet-informatique" / "transitions.html").is_file()
            )
            analysis_index = (
                output / "analyse-statique-code" / "index.html"
            ).read_text(encoding="utf-8")
            self.assertIn("flowchart LR", analysis_index)

    def test_catalog_editor_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "catalog"
            result = self.run_cli(
                "generate_workflow_site.py", CATALOG, "--output", output
            )

            self.assertEqual(0, result.returncode, result.stderr)
            editor = (output / "editor.html").read_text(encoding="utf-8")
            editor_script = (output / "assets" / "editor.js").read_text(
                encoding="utf-8"
            )
            self.assertIn('id="workflow-source"', editor)
            self.assertIn('"workflow_id":"Analyse_statique_code"', editor)
            self.assertIn("Ajouter l’état", editor)
            self.assertIn('id="state-picker"', editor)
            self.assertIn("Nouvel état…", editor)
            self.assertIn("Supprimer l’état", editor)
            self.assertIn("Ouvrir le répertoire des états", editor)
            self.assertNotIn('id="state-rows"', editor)
            self.assertIn('id="toggle-editor-layout"', editor)
            self.assertIn("Placer les transitions en dessous", editor)
            self.assertIn("Format du texte de l'état", editor)
            self.assertIn("Texte de l'état", editor)
            self.assertNotIn('id="state-description"', editor)
            self.assertIn("Validité des liens des états et des transitions", editor)
            self.assertIn(
                "[état destinataire supprimé](states/Etat_supprime.html)",
                editor,
            )
            self.assertIn("Vocabulaire à employer", editor)
            self.assertIn("il ne bloque ni la copie", editor)
            self.assertIn("Ajouter la transition", editor)
            self.assertIn('id="transition-picker"', editor)
            self.assertIn("Nouvelle transition…", editor)
            self.assertIn("Supprimer la transition", editor)
            self.assertIn('id="transition-link-target"', editor)
            self.assertNotIn('id="transition-rows"', editor)
            self.assertIn("Enregistrer le JSON sous…", editor)
            self.assertIn("validateDocument", editor_script)
            self.assertIn("stateLinkResults", editor_script)
            self.assertIn("renderRecordLinks", editor_script)
            self.assertIn("loadState", editor_script)
            self.assertIn("workflow-editor-transitions-below", editor_script)
            self.assertIn('classList.toggle("transitions-below"', editor_script)
            self.assertIn("loadTransition", editor_script)
            self.assertIn("application/json;charset=utf-8", editor_script)


if __name__ == "__main__":
    unittest.main()
