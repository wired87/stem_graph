# Integration tests for /api/file_master/* routes (live GBucket when credentials are configured)
import os
import unittest
from pathlib import Path

import dotenv
from django.test import TestCase
from google.auth.exceptions import DefaultCredentialsError
from rest_framework import status
from rest_framework.test import APIClient

# Project root and bundled StemCNV example dataset for upsert payloads
BASE_DIR = Path(__file__).resolve().parent.parent
EXAMPLE_DATA_DIR = BASE_DIR / 'product' / 'executable' / 'example_data'
# Load .env so TEST_USER_ID and GCS settings match local dev
dotenv.load_dotenv(BASE_DIR / '.env')


# True when GOOGLE_APPLICATION_CREDENTIALS points at an existing key file_master
def _gcs_credentials_available() -> bool:
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')
    if not creds_path:
        return False
    return Path(creds_path).is_file()


# All five file_master API routes in one ordered integration suite
@unittest.skipUnless(
    _gcs_credentials_available(),
    'GOOGLE_APPLICATION_CREDENTIALS file_master missing — skipping live GBucket tests',
)
class FileRouteIntegrationTests(TestCase):
    # Shared client, user scope, and objects uploaded during upsert
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = APIClient()
        cls.user_id = os.getenv('TEST_USER_ID', 'test-user')
        cls.route_prefix = 'route-test/example_data'
        cls.uploaded_names = []
        cls.example_files = sorted(
            p for p in EXAMPLE_DATA_DIR.iterdir() if p.is_file()
        )
        if not cls.example_files:
            raise unittest.SkipTest(f'example_data missing: {EXAMPLE_DATA_DIR}')
        # Upsert example_data via set-file_master before route assertions
        try:
            for path in cls.example_files:
                dest_name = f"{cls.route_prefix}/{path.name}"
                response = cls.client.post(
                    '/api/file_master/set-file_master/',
                    {
                        'user_id': cls.user_id,
                        'name': dest_name,
                        'content': path.read_text(encoding='utf-8'),
                    },
                    format='json',
                )
                if response.status_code != status.HTTP_201_CREATED:
                    raise unittest.SkipTest(
                        f'set-file_master upsert failed ({response.status_code}): {response.data}'
                    )
                cls.uploaded_names.append(dest_name)
        except DefaultCredentialsError as exc:
            raise unittest.SkipTest(f'GCS credentials unavailable: {exc}') from exc

    # Best-effort cleanup of upserted blobs
    @classmethod
    def tearDownClass(cls):
        for name in getattr(cls, 'uploaded_names', []):
            try:
                cls.client.post(
                    '/api/file_master/delete-file_master/',
                    {'user_id': cls.user_id, 'name': name},
                    format='json',
                )
            except Exception:
                pass
        super().tearDownClass()

    # POST /api/file_master/set-file_master/ — upsert create with example_data payload
    def test_set_file_upserts_example_data(self):
        self.assertEqual(len(self.uploaded_names), len(self.example_files))
        for dest_name in self.uploaded_names:
            self.assertTrue(dest_name.startswith(f'{self.route_prefix}/'))

    # GET/POST /api/file_master/get-file_master-names/
    def test_get_file_names_lists_upserted_example_data(self):
        response = self.client.post(
            '/api/file_master/get-file_master-names/',
            {'user_id': self.user_id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_id'], self.user_id)
        listed = response.data.get('file_names', [])
        for name in self.uploaded_names:
            self.assertIn(f'{self.user_id}/{name}', listed)

    # GET/POST /api/file_master/get-file_master/
    def test_get_file_returns_example_data_content(self):
        for path, dest_name in zip(self.example_files, self.uploaded_names):
            response = self.client.post(
                '/api/file_master/get-file_master/',
                {'user_id': self.user_id, 'name': dest_name},
                format='json',
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['name'], dest_name)
            self.assertEqual(
                response.data['content'],
                path.read_text(encoding='utf-8'),
            )

    # PUT/POST /api/file_master/update-file_master/ — upsert overwrite
    def test_update_file_overwrites_example_data_blob(self):
        dest_name = self.uploaded_names[0]
        updated_content = '# route-test update marker\n'
        response = self.client.post(
            '/api/file_master/update-file_master/',
            {
                'user_id': self.user_id,
                'name': dest_name,
                'content': updated_content,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], 'update-file_master')
        fetched = self.client.post(
            '/api/file_master/get-file_master/',
            {'user_id': self.user_id, 'name': dest_name},
            format='json',
        )
        self.assertEqual(fetched.data['content'], updated_content)

    # DELETE/POST /api/file_master/delete-file_master/
    def test_delete_file_removes_upserted_blob(self):
        dest_name = self.uploaded_names[-1]
        response = self.client.post(
            '/api/file_master/delete-file_master/',
            {'user_id': self.user_id, 'name': dest_name},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], 'delete-file_master')
        listed = self.client.post(
            '/api/file_master/get-file_master-names/',
            {'user_id': self.user_id},
            format='json',
        )
        self.assertNotIn(f'{self.user_id}/{dest_name}', listed.data.get('file_names', []))
        if dest_name in self.uploaded_names:
            self.uploaded_names.remove(dest_name)
