import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import tui_core
import validate_workflow_data


class TuiCoreTests(unittest.TestCase):
    def test_starter_workflow_is_complete_and_uses_mermaid_safe_ids(self):
        document = tui_core.new_workflow_document(
            "gestion-incidents", "Gestion des incidents", "Cycle de traitement."
        )

        self.assertEqual(
            {
                "Workflow",
                "Participant",
                "Ligne_eau",
                "Etat",
                "Transition",
                "Role",
                "Regle",
                "Generation_Mermaid",
            },
            set(document),
        )
        self.assertEqual("Gestion_Incidents", document["Workflow"][0]["workflow_id"])
        self.assertEqual(2, len(document["Etat"]))
        for table in document.values():
            for record in table:
                for name, value in record.items():
                    if name.endswith("_id"):
                        self.assertRegex(value, tui_core.SAFE_IDENTIFIER)
        schema = json.loads(
            (PROJECT_ROOT / "schema" / "workflow-model.json").read_text(
                encoding="utf-8"
            )
        )
        validate_workflow_data.validate_records_against_schema(document, schema)
        validate_workflow_data.validate_references(document, schema)
        validate_workflow_data.validate_business_consistency(document)

    def test_create_workflow_registers_a_non_destructive_starter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "catalog.json"
            catalog.write_text(
                json.dumps(
                    {
                        "format": "workflow-site-catalog-v1",
                        "title": "Test",
                        "workflows": [],
                    }
                ),
                encoding="utf-8",
            )

            entry = tui_core.create_workflow(
                "gestion-incidents",
                "Gestion des incidents",
                "Cycle de traitement.",
                catalog,
            )

            self.assertTrue(entry.manifest.is_file())
            self.assertTrue((root / "gestion-incidents" / "workflow.json").is_file())
            updated = json.loads(catalog.read_text(encoding="utf-8"))
            self.assertEqual("gestion-incidents", updated["workflows"][0]["slug"])
            with self.assertRaisesRegex(tui_core.TuiOperationError, "existe déjà"):
                tui_core.create_workflow(
                    "gestion-incidents", "Doublon", "", catalog
                )

    def test_invalid_slug_is_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = Path(directory) / "catalog.json"
            catalog.write_text(
                '{"format":"workflow-site-catalog-v1","workflows":[]}',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(tui_core.TuiOperationError, "slug"):
                tui_core.create_workflow("Incident été", "Incident", "", catalog)

            self.assertEqual([catalog], list(Path(directory).iterdir()))

    def test_web_themes_are_saved_independently_from_tui_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow_dir = root / "alpha"
            workflow_dir.mkdir()
            manifest = workflow_dir / "manifest.json"
            manifest.write_text(
                json.dumps({"site": {"theme": {"pair": "ocean", "mode": "system"}}}),
                encoding="utf-8",
            )
            catalog = root / "catalog.json"
            catalog.write_text(
                json.dumps(
                    {
                        "format": "workflow-site-catalog-v1",
                        "theme": {"pair": "graphite", "mode": "light"},
                        "workflows": [
                            {
                                "slug": "alpha",
                                "label": "Alpha",
                                "manifest": "alpha/manifest.json",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            tui_settings = root / "tui.json"
            tui_core.save_settings("aubergine", tui_settings)

            tui_core.save_site_theme("alpha", "forest", "dark", catalog)
            targets = {item.target_id: item for item in tui_core.list_site_theme_targets(catalog)}

            self.assertEqual(("graphite", "light"), (targets["catalog"].pair, targets["catalog"].mode))
            self.assertEqual(("forest", "dark"), (targets["alpha"].pair, targets["alpha"].mode))
            self.assertEqual(
                {"theme": "aubergine", "editor": ""},
                json.loads(tui_settings.read_text(encoding="utf-8")),
            )

    def test_generate_one_workflow_has_its_own_scope_and_catalog_link(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            destination = root / "site" / "alpha"
            entry = tui_core.WorkflowEntry("alpha", "Alpha", "", manifest)

            def fake_run(arguments):
                destination.mkdir(parents=True)
                (destination / "index.html").write_text("<html></html>", encoding="utf-8")
                return tui_core.CommandResult(tuple(map(str, arguments)), 0, "Site statique généré")

            with mock.patch.object(tui_core, "run_project_command", side_effect=fake_run) as run:
                result = tui_core.generate_workflow_site(entry, destination)

            self.assertTrue(result.succeeded)
            self.assertEqual((destination / "index.html").resolve(), result.artifact)
            self.assertIn("Site du workflow « Alpha » généré", result.output)
            self.assertIn("1 page HTML", result.output)
            self.assertIn("--catalog-href", run.call_args.args[0])
            self.assertIn("../index.html", run.call_args.args[0])

    def test_open_in_editor_uses_configured_editor(self):
        with tempfile.TemporaryDirectory() as directory:
            document = Path(directory) / "manifest.json"
            document.write_text("{}", encoding="utf-8")
            with mock.patch.object(tui_core.subprocess, "Popen") as popen:
                tui_core.open_in_editor(document, "code --wait")

            popen.assert_called_once_with(
                ["code", "--wait", str(document.resolve())],
                cwd=tui_core.PROJECT_ROOT,
            )

    @unittest.skipUnless(sys.platform == "win32", "Association testée sous Windows")
    def test_open_in_editor_without_override_uses_file_association(self):
        with tempfile.TemporaryDirectory() as directory:
            document = Path(directory) / "manifest.json"
            document.write_text("{}", encoding="utf-8")
            with mock.patch.object(tui_core.os, "startfile") as startfile:
                tui_core.open_in_editor(document)

            startfile.assert_called_once_with(document.resolve())


if __name__ == "__main__":
    unittest.main()
