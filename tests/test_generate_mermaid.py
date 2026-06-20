import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
MODULE_PATH = PROJECT_ROOT / "scripts" / "generate_mermaid.py"
SPEC = importlib.util.spec_from_file_location("generate_mermaid", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
generate_mermaid = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate_mermaid)


class GenerateMermaidTests(unittest.TestCase):
    def load_example(self):
        return json.loads(
            (PROJECT_ROOT / "examples" / "workflow-data.json").read_text(
                encoding="utf-8"
            )
        )

    def test_dataset_generates_both_diagram_types(self):
        document = self.load_example()

        diagrams = generate_mermaid.generate_diagrams(
            document, generate_mermaid.detect_input_kind(document), None
        )

        self.assertTrue(diagrams["flowchart"].startswith("flowchart TD\n"))
        self.assertIn('A_qualifier["À qualifier"]', diagrams["flowchart"])
        self.assertIn(
            "A_qualifier -->|dossier complet| En_instruction",
            diagrams["flowchart"],
        )
        self.assertNotIn("ancienne transition", diagrams["flowchart"])

        self.assertTrue(diagrams["state"].startswith("stateDiagram-v2\n"))
        self.assertIn("[*] --> A_qualifier", diagrams["state"])
        self.assertIn("Clos --> [*]", diagrams["state"])
        self.assertNotIn("ancienne transition", diagrams["state"])

    def test_schema_generates_structural_diagrams(self):
        document = json.loads(
            (PROJECT_ROOT / "schema" / "workflow-model.json").read_text(
                encoding="utf-8"
            )
        )

        diagrams = generate_mermaid.generate_diagrams(
            document, generate_mermaid.detect_input_kind(document), None
        )

        self.assertTrue(diagrams["flowchart"].startswith("flowchart LR\n"))
        self.assertIn("Etat -->|workflow_id| Workflow", diagrams["flowchart"])
        self.assertTrue(diagrams["state"].startswith("stateDiagram-v2\n"))
        self.assertIn("Etat --> Workflow : workflow_id", diagrams["state"])

    def test_invalid_mermaid_identifier_is_rejected(self):
        document = self.load_example()
        document["Etat"][0]["etat_id"] = "À qualifier"

        with self.assertRaisesRegex(
            generate_mermaid.MermaidGenerationError,
            "identifiant Mermaid stable",
        ):
            generate_mermaid.generate_diagrams(document, "dataset", None)

    def test_multiple_active_workflows_require_selection(self):
        document = self.load_example()
        document["Workflow"].append(
            {
                "workflow_id": "Second_workflow",
                "nom": "Second workflow",
                "actif": True,
            }
        )

        with self.assertRaisesRegex(
            generate_mermaid.MermaidGenerationError,
            "--workflow-id",
        ):
            generate_mermaid.generate_diagrams(document, "dataset", None)

    def test_cli_writes_markdown_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "workflow.md"
            status = generate_mermaid.main(
                [
                    str(PROJECT_ROOT / "examples" / "workflow-data.json"),
                    "--diagram",
                    "state",
                    "--output",
                    str(output),
                ]
            )

            self.assertEqual(0, status)
            content = output.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("```mermaid\nstateDiagram-v2\n"))
            self.assertTrue(content.endswith("\n```\n"))


if __name__ == "__main__":
    unittest.main()
