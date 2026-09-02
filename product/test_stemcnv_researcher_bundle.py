"""Real StemCNV researcher-bundle validation and staging test; no mocks."""
import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path

import yaml
from django.core.files import File
from django.test import SimpleTestCase

from product.stemcnv_docker import _stage_uploads, validate_upload_bundle


FIXTURE_ROOT = Path(os.getenv("STEMCNV_TEST_DATA_DIR", "/var/lib/stemcnv-upstream/example_data"))


class StemCNVResearcherBundleTest(SimpleTestCase):
    def test_official_drag_drop_bundle_validates_and_stages(self):
        if not (FIXTURE_ROOT / "config.yaml").is_file():
            raise unittest.SkipTest(f"official StemCNV data not found at {FIXTURE_ROOT}")
        config = yaml.safe_load((FIXTURE_ROOT / "config.yaml").read_text())
        paths = [FIXTURE_ROOT / "config.yaml", FIXTURE_ROOT / "sample_table.tsv"]
        for definition in config["array_definition"].values():
            paths.extend(
                FIXTURE_ROOT / value
                for key, value in definition.items()
                if key.endswith("_file") and value != "__cache-default__"
            )
        paths.extend(sorted((FIXTURE_ROOT / "RAW").rglob("*.idat")))
        self.assertTrue(all(path.is_file() for path in paths))

        with ExitStack() as stack:
            uploads = [File(stack.enter_context(path.open("rb")), name=path.name) for path in paths]
            summary = validate_upload_bundle(uploads)
            self.assertEqual(summary["idat_pairs"], 6)
            self.assertEqual(summary["array_definitions"], 1)
            with tempfile.TemporaryDirectory(prefix="stemcnv-real-upload-") as directory:
                staged = Path(directory)
                _stage_uploads(uploads, staged)
                self.assertTrue((staged / "config.yaml").is_file())
                self.assertTrue((staged / "sample_table.tsv").is_file())
                self.assertEqual(len(list((staged / "RAW").rglob("*.idat"))), 12)
                for definition in config["array_definition"].values():
                    for key, value in definition.items():
                        if key.endswith("_file") and value != "__cache-default__":
                            self.assertTrue((staged / value).is_file(), value)

    def test_incomplete_real_bundle_reports_missing_idat_and_docker_path(self):
        if not (FIXTURE_ROOT / "config.yaml").is_file():
            raise unittest.SkipTest(f"official StemCNV data not found at {FIXTURE_ROOT}")
        config = yaml.safe_load((FIXTURE_ROOT / "config.yaml").read_text())
        paths = [FIXTURE_ROOT / "config.yaml", FIXTURE_ROOT / "sample_table.tsv"]
        for definition in config["array_definition"].values():
            paths.extend(
                FIXTURE_ROOT / value
                for key, value in definition.items()
                if key.endswith("_file") and value != "__cache-default__"
            )
        idats = sorted((FIXTURE_ROOT / "RAW").rglob("*.idat"))
        removed = next(path for path in idats if path.name.lower().endswith("_red.idat"))
        paths.extend(path for path in idats if path != removed)

        with ExitStack() as stack:
            uploads = [File(stack.enter_context(path.open("rb")), name=path.name) for path in paths]
            with self.assertRaisesRegex(ValueError, r"Custom-data mode:.*Red\.idat.*→ /work/RAW/"):
                validate_upload_bundle(uploads)
