"""Real, opt-in StemCNV route test. No mocks and no synthetic workflow."""
import os
import time
import unittest
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings
from django.urls import include, path
from rest_framework.test import APITestCase

FIXTURE_ROOT = Path(os.getenv("STEMCNV_TEST_DATA_DIR", "product/executable/example_data"))
REAL_TEST = os.getenv("STEMCNV_REAL_INTEGRATION") == "1"
urlpatterns = [path("api/product/", include("product.urls"))]


class StemCNVResultPackagingTest(SimpleTestCase):
    def test_only_researcher_facing_results_are_selected(self):
        from product.stemcnv_docker import _is_final_artifact

        self.assertTrue(_is_final_artifact("data/HG001/HG001.StemCNV-check-report.html"))
        self.assertTrue(_is_final_artifact("data/HG001/HG001.CNV_calls.combined-annotated.vcf.gz"))
        self.assertTrue(_is_final_artifact("data/summary-overview.xlsx"))
        self.assertFalse(_is_final_artifact("data/HG001/HG001.annotated-SNP-data.standard-filter.vcf.gz"))
        self.assertFalse(_is_final_artifact("data/HG001/HG001.gencall.hg19.gtc"))
        self.assertFalse(_is_final_artifact("data/HG001/StemCNV-check-report-html_images/plot.png"))

    def test_html_report_images_are_embedded(self):
        from product.stemcnv_docker import _embed_report_images

        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "plot-1.png"
            image.write_bytes(b"real-png-bytes")
            report = b"window.open('./StemCNV-check-report-html_images//plot-1.png')"
            embedded = _embed_report_images(report, lambda name: Path(directory) / name)
        self.assertIn(b"data:image/png;base64,", embedded)
        self.assertNotIn(b"StemCNV-check-report-html_images", embedded)


@override_settings(ALLOWED_HOSTS=["testserver"], ROOT_URLCONF=__name__)
class StemCNVDockerRouteIntegrationTest(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not REAL_TEST:
            raise unittest.SkipTest("set STEMCNV_REAL_INTEGRATION=1 to run the real container workflow")
        if not (FIXTURE_ROOT / "config.yaml").is_file():
            raise unittest.SkipTest(f"real StemCNV fixtures not found at {FIXTURE_ROOT}")

    def test_real_fixture_bundle_completes_and_downloads_results(self):
        response = self.client.post(
            "/api/product/run-local/", {"cores": 3, "output_name": "route-test-results.zip"}, format="multipart"
        )
        self.assertEqual(response.status_code, 202, response.content)
        self.assertEqual(response.json()["input_source"], "canonical-example")
        run_id = response.json()["run_id"]
        deadline = time.monotonic() + int(os.getenv("STEMCNV_TEST_TIMEOUT", "14400"))
        while time.monotonic() < deadline:
            response = self.client.get(f"/api/product/status-run/{run_id}/")
            if response.status_code != 202:
                break
            time.sleep(10)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], "complete", response.json().get("logs"))
        download = self.client.get(f"/api/product/status-run/{run_id}/?download=1")
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download["Content-Type"], "application/zip")
        self.assertIn('filename="route-test-results.zip"', download["Content-Disposition"])
