import copy
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import generate_mermaid
import validate_workflow_data
import workflow_data


MANIFEST = (
    PROJECT_ROOT / "data" / "workflows" / "projet-informatique" / "manifest.json"
)
SCHEMA = PROJECT_ROOT / "schema" / "workflow-model.json"


class ValidateWorkflowDataTests(unittest.TestCase):
    def test_all_fragmented_workflow_datasets_match_model(self):
        manifests = sorted((PROJECT_ROOT / "data" / "workflows").glob("**/manifest.json"))
        self.assertTrue(manifests)

        for manifest in manifests:
            with self.subTest(manifest=manifest):
                validate_workflow_data.validate_source(manifest)

    def test_all_standalone_examples_match_model(self):
        examples = sorted((PROJECT_ROOT / "examples").glob("*.json"))
        self.assertTrue(examples)

        for example in examples:
            with self.subTest(example=example):
                validate_workflow_data.validate_source(example, SCHEMA)

    def test_project_dataset_has_expected_governance_coverage(self):
        document = validate_workflow_data.validate_source(MANIFEST)

        self.assertEqual(2, len(document["Workflow"]))
        self.assertGreaterEqual(len(document["Etat"]), 30)
        self.assertGreaterEqual(len(document["Transition"]), 30)
        self.assertGreaterEqual(len(document["Regle"]), 8)
        state_ids = {state["etat_id"] for state in document["Etat"]}
        self.assertTrue(
            {
                "Budget_valide",
                "Specifications_validees",
                "Architecture_validee",
                "Marche_attribue",
                "Homologation_securite",
                "CAB_valide",
                "Maintenance",
                "Decommissionne",
            }.issubset(state_ids)
        )

    def test_all_project_states_are_reachable_from_initial_state(self):
        document = validate_workflow_data.validate_source(MANIFEST)
        project_states = [
            state
            for state in document["Etat"]
            if state["workflow_id"] == "Projet_informatique"
        ]
        transitions = [
            transition
            for transition in document["Transition"]
            if transition["actif"] is True
            and transition["workflow_id"] == "Projet_informatique"
        ]
        reachable = {"Idee_projet"}
        changed = True
        while changed:
            changed = False
            for transition in transitions:
                if (
                    transition["etat_source_id"] in reachable
                    and transition["etat_cible_id"] not in reachable
                ):
                    reachable.add(transition["etat_cible_id"])
                    changed = True

        self.assertEqual(
            {state["etat_id"] for state in project_states},
            reachable,
        )

    def test_all_project_state_descriptions_are_html(self):
        document = validate_workflow_data.validate_source(MANIFEST)

        for state in document["Etat"]:
            with self.subTest(state=state["etat_id"]):
                self.assertTrue(state["description"].startswith("<p>"))
                self.assertTrue(state["description"].endswith("</p>"))

    def test_fragmented_dataset_can_generate_complete_diagrams(self):
        document = workflow_data.load_data_source(MANIFEST)

        diagrams = generate_mermaid.generate_diagrams(
            document,
            generate_mermaid.detect_input_kind(document),
            "Projet_informatique",
        )

        self.assertIn("[*] --> Idee_projet", diagrams["state"])
        self.assertIn("Decommissionne --> [*]", diagrams["state"])
        self.assertIn(
            "Maintenance --> Fin_maintenance_decidee : fin de vie approuvée",
            diagrams["state"],
        )

    def test_phase_overview_links_to_phase_pages(self):
        document = validate_workflow_data.validate_source(MANIFEST)

        diagrams = generate_mermaid.generate_diagrams(
            document,
            generate_mermaid.detect_input_kind(document),
            "Phases_projet_informatique",
        )

        self.assertIn(
            'click Phase_Cadrage_budgetisation '
            '"phases/01-cadrage-budgetisation.html"',
            diagrams["flowchart"],
        )

    def test_invalid_internal_link_is_rejected(self):
        document = workflow_data.load_data_source(MANIFEST)
        invalid = copy.deepcopy(document)
        phase_state = next(
            state
            for state in invalid["Etat"]
            if state["etat_id"] == "Phase_Cadrage_budgetisation"
        )
        phase_state["cible_lien"] = "../page-invalide.html"

        with self.assertRaisesRegex(
            validate_workflow_data.DataValidationError,
            r"doit pointer vers phases/\*\.html",
        ):
            validate_workflow_data.validate_business_consistency(invalid)

    def test_unknown_field_breaks_model_compatibility(self):
        document = workflow_data.load_data_source(MANIFEST)
        invalid = copy.deepcopy(document)
        invalid["Etat"][0]["champ_inconnu"] = "interdit"
        schema = workflow_data.load_json(SCHEMA)

        with self.assertRaisesRegex(
            validate_workflow_data.DataValidationError,
            "champs absents du modèle",
        ):
            validate_workflow_data.validate_records_against_schema(invalid, schema)

    def test_missing_cross_fragment_reference_is_rejected(self):
        document = workflow_data.load_data_source(MANIFEST)
        invalid = copy.deepcopy(document)
        invalid["Transition"][0]["etat_cible_id"] = "Etat_absent"
        schema = workflow_data.load_json(SCHEMA)

        validate_workflow_data.validate_records_against_schema(invalid, schema)
        with self.assertRaisesRegex(
            validate_workflow_data.DataValidationError,
            "référence introuvable",
        ):
            validate_workflow_data.validate_references(invalid, schema)


if __name__ == "__main__":
    unittest.main()
