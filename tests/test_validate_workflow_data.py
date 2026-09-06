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
STATIC_ANALYSIS_MANIFEST = (
    PROJECT_ROOT
    / "data"
    / "workflows"
    / "analyse-statique-code"
    / "manifest.json"
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
        self.assertEqual(1, len(document["Participant"]))
        self.assertEqual(13, len(document["Ligne_eau"]))
        self.assertEqual(
            {role["role_id"] for role in document["Role"]},
            {waterline["role_id"] for waterline in document["Ligne_eau"]},
        )
        self.assertGreaterEqual(len(document["Etat"]), 30)
        self.assertGreaterEqual(len(document["Transition"]), 30)
        self.assertGreaterEqual(len(document["Regle"]), 8)
        state_ids = {state["etat_id"] for state in document["Etat"]}
        state_waterlines = {
            state["etat_id"]: state.get("ligne_eau_id")
            for state in document["Etat"]
            if state["workflow_id"] == "Projet_informatique"
        }
        self.assertEqual(
            {
                waterline["ligne_eau_id"]
                for waterline in document["Ligne_eau"]
                if waterline["workflow_id"] == "Projet_informatique"
            },
            set(state_waterlines.values()),
        )
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
        self.assertEqual(
            {
                "Idee_projet": "Sponsor_metiers",
                "Cadrage": "Responsable_conduite_projet",
                "Budget_valide": "Pilotage_gouvernance",
                "Architecture_concue": "Architecture_securite",
                "Dossier_marche": "Achats_contractualisation",
                "Realisation": "Realisation_qualite",
                "Tests_integration": "Qualite_tests",
                "Recette_metier": "Metiers_validation",
                "Homologation_securite": "Securite_homologation",
                "CAB_valide": "CAB_changements",
                "Service_actif": "Exploitation_operations",
                "Maintenance": "Maintenance_service",
                "Donnees_archivees": "DPO_donnees",
            },
            {
                state_id: state_waterlines[state_id]
                for state_id in (
                    "Idee_projet",
                    "Cadrage",
                    "Budget_valide",
                    "Architecture_concue",
                    "Dossier_marche",
                    "Realisation",
                    "Tests_integration",
                    "Recette_metier",
                    "Homologation_securite",
                    "CAB_valide",
                    "Service_actif",
                    "Maintenance",
                    "Donnees_archivees",
                )
            },
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

    def test_project_contains_markdown_and_link_validation_examples(self):
        document = validate_workflow_data.validate_source(MANIFEST)
        initial_state = next(
            state for state in document["Etat"]
            if state["etat_id"] == "Idee_projet"
        )

        self.assertEqual("markdown", initial_state["type_contenu"])
        self.assertIn(
            "[documentation valide](https://example.org/guide-projet)",
            initial_state["contenu"],
        )
        self.assertIn(
            "[état destinataire supprimé](states/Etat_supprime.html)",
            initial_state["contenu"],
        )
        self.assertEqual("url", initial_state["type_lien"])
        self.assertEqual(
            "https://example.org/projet-informatique",
            initial_state["cible_lien"],
        )
        invalid_state = next(
            state for state in document["Etat"]
            if state["etat_id"] == "Budget_a_revoir"
        )
        self.assertEqual("page_etat", invalid_state["type_lien"])
        self.assertEqual(
            "states/Etat_budget_supprime.html",
            invalid_state["cible_lien"],
        )
        transitions = {
            transition["transition_id"]: transition
            for transition in document["Transition"]
            if transition["workflow_id"] == "Projet_informatique"
        }
        self.assertEqual(
            "https://example.org/projet-informatique/opportunite",
            transitions["Enregistrer_opportunite"]["cible_lien"],
        )
        self.assertEqual(
            "phases/02-specifications-conception-marche.html",
            transitions["Valider_budget"]["cible_lien"],
        )
        self.assertEqual(
            "states/Transition_budget_supprimee.html",
            transitions["Refuser_budget"]["cible_lien"],
        )

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

    def test_static_analysis_workflow_is_complete_and_reachable(self):
        document = validate_workflow_data.validate_source(STATIC_ANALYSIS_MANIFEST)
        states = [
            state
            for state in document["Etat"]
            if state["workflow_id"] == "Analyse_statique_code"
        ]
        transitions = [
            transition
            for transition in document["Transition"]
            if transition["workflow_id"] == "Analyse_statique_code"
            and transition["actif"] is True
        ]
        reachable = {"Demande_analyse"}
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

        self.assertEqual(16, len(states))
        self.assertEqual({state["etat_id"] for state in states}, reachable)
        self.assertIn("Analyse_cloturee", reachable)

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

    def test_invalid_schema_values_are_rejected(self):
        document = workflow_data.load_data_source(MANIFEST)
        schema = workflow_data.load_json(SCHEMA)
        cases = [
            (
                "required field",
                lambda invalid: invalid["Workflow"][0].pop("nom"),
                "champ obligatoire manquant nom",
            ),
            (
                "boolean type",
                lambda invalid: invalid["Workflow"][0].update(actif="oui"),
                "valeur incompatible avec le type boolean",
            ),
            (
                "choice value",
                lambda invalid: invalid["Workflow"][0].update(orientation="XX"),
                "absente des choix autorisés",
            ),
            (
                "Mermaid identifier",
                lambda invalid: invalid["Etat"][0].update(etat_id="État invalide"),
                "identifiant incompatible avec Mermaid",
            ),
        ]

        for label, mutate, expected_error in cases:
            with self.subTest(case=label):
                invalid = copy.deepcopy(document)
                mutate(invalid)
                with self.assertRaisesRegex(
                    validate_workflow_data.DataValidationError,
                    expected_error,
                ):
                    validate_workflow_data.validate_records_against_schema(
                        invalid, schema
                    )

    def test_duplicate_identifier_is_rejected(self):
        document = workflow_data.load_data_source(MANIFEST)
        invalid = copy.deepcopy(document)
        invalid["Etat"][1]["etat_id"] = invalid["Etat"][0]["etat_id"]
        schema = workflow_data.load_json(SCHEMA)

        with self.assertRaisesRegex(
            validate_workflow_data.DataValidationError,
            "identifiant dupliqué",
        ):
            validate_workflow_data.validate_references(invalid, schema)

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

    def test_transition_between_different_workflows_is_rejected(self):
        document = workflow_data.load_data_source(MANIFEST)
        invalid = copy.deepcopy(document)
        transition = invalid["Transition"][0]
        transition["workflow_id"] = next(
            workflow["workflow_id"]
            for workflow in invalid["Workflow"]
            if workflow["workflow_id"] != transition["workflow_id"]
        )
        schema = workflow_data.load_json(SCHEMA)

        validate_workflow_data.validate_references(invalid, schema)
        with self.assertRaisesRegex(
            validate_workflow_data.DataValidationError,
            "relie des états appartenant à un autre workflow",
        ):
            validate_workflow_data.validate_business_consistency(invalid)

    def test_state_waterline_must_belong_to_same_workflow(self):
        document = workflow_data.load_data_source(MANIFEST)
        invalid = copy.deepcopy(document)
        invalid["Participant"].append(
            {
                "participant_id": "Participant_autre_workflow",
                "workflow_id": "Phases_projet_informatique",
                "nom": "Autre participant",
                "processus_visible": True,
                "ordre": 99,
            }
        )
        invalid["Ligne_eau"].append(
            {
                "ligne_eau_id": "Ligne_autre_workflow",
                "workflow_id": "Phases_projet_informatique",
                "participant_id": "Participant_autre_workflow",
                "nom": "Autre workflow",
                "type_partition": "role",
                "ordre": 99,
            }
        )
        state = next(
            state
            for state in invalid["Etat"]
            if state["workflow_id"] == "Projet_informatique"
        )
        state["ligne_eau_id"] = "Ligne_autre_workflow"
        schema = workflow_data.load_json(SCHEMA)

        validate_workflow_data.validate_references(invalid, schema)
        with self.assertRaisesRegex(
            validate_workflow_data.DataValidationError,
            "ligne_eau_id appartient à un autre workflow",
        ):
            validate_workflow_data.validate_business_consistency(invalid)

    def test_message_flow_inside_same_pool_is_rejected(self):
        document = workflow_data.load_data_source(MANIFEST)
        invalid = copy.deepcopy(document)
        transition = next(
            transition
            for transition in invalid["Transition"]
            if transition["workflow_id"] == "Projet_informatique"
        )
        transition["type_flux_bpmn"] = "message"

        with self.assertRaisesRegex(
            validate_workflow_data.DataValidationError,
            "flux de message à l'intérieur d'un même pool",
        ):
            validate_workflow_data.validate_business_consistency(invalid)


if __name__ == "__main__":
    unittest.main()
