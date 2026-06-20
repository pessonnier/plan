import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import validate_traceability


MATRIX = PROJECT_ROOT / "traceability" / "requirements.json"


class TraceabilityTests(unittest.TestCase):
    def test_project_traceability_matrix_is_valid(self):
        count = validate_traceability.validate_traceability(MATRIX, PROJECT_ROOT)

        self.assertEqual(7, count)

    def test_missing_symbol_is_rejected(self):
        matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
        invalid = copy.deepcopy(matrix)
        invalid["requirements"][0]["code"][0] = (
            "scripts/validate_workflow_data.py::fonction_absente"
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "requirements.json"
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(
                validate_traceability.TraceabilityError,
                "symbole introuvable",
            ):
                validate_traceability.validate_traceability(path, PROJECT_ROOT)

    def test_functional_test_must_be_in_functional_directory(self):
        matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
        invalid = copy.deepcopy(matrix)
        invalid["requirements"][0]["functional_tests"][0] = (
            "tests/test_validate_workflow_data.py::"
            "ValidateWorkflowDataTests.test_all_fragmented_workflow_datasets_match_model"
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "requirements.json"
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(
                validate_traceability.TraceabilityError,
                "doit être placé dans tests/functional",
            ):
                validate_traceability.validate_traceability(path, PROJECT_ROOT)


if __name__ == "__main__":
    unittest.main()
