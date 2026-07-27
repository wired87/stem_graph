from django.test import SimpleTestCase, override_settings
from django.urls import include, path, reverse


urlpatterns = [
    path("protein/", include("protein.urls")),
    path("drug/", include("drug_master.urls")),
]


@override_settings(ROOT_URLCONF=__name__, ALLOWED_HOSTS=["testserver"])
class WorkspaceViewTests(SimpleTestCase):
    def test_protein_workspace_is_available(self):
        response = self.client.get(reverse("protein_predictor:workspace"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Protein workspace")
        self.assertContains(response, reverse("drug_master:workspace"))

    def test_drug_workspace_is_available(self):
        response = self.client.get(reverse("drug_master:workspace"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Drug workspace")
        self.assertContains(response, reverse("protein_predictor:workspace"))
        self.assertContains(response, reverse("drug_master:run"))
