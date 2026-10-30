import io
import re
import tempfile
from pathlib import Path

import fitz
from PIL import Image
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from notes.models import Note, NotePage, ViewLog
from notes.processing import InvalidNoteFile, process_upload


class NotelyPortalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(
            PRIVATE_STORAGE_DIR=Path(self.temp_dir.name),
            DEBUG=True,
            SECURE_SSL_REDIRECT=False,
            SESSION_COOKIE_SECURE=False,
            CSRF_COOKIE_SECURE=False,
        )
        self.settings_override.enable()
        self.reader = User.objects.create_user("reader", password="reader-code1")
        self.note = Note.objects.create(
            title="Sample notes",
            slug="sample-notes",
            is_published=True,
            processing_status="ready",
            source_type="image",
        )
        image_path = Path(self.temp_dir.name) / "source.webp"
        Image.new("RGB", (480, 360), "white").save(image_path, "WEBP")
        self.page = NotePage.objects.create(
            note=self.note,
            page_number=1,
            image_path=str(image_path),
            width=480,
            height=360,
        )

    def tearDown(self):
        self.settings_override.disable()
        self.temp_dir.cleanup()

    def login_viewer(self, client=None, username="reader", code="reader-code1"):
        client = client or Client()
        return client, client.post(
            "/login/",
            {"username": username, "access_code": code},
        )

    def test_notes_and_image_routes_require_login(self):
        for path in ("/", "/n/sample-notes/", "/n/sample-notes/p/1/"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login/", response.url)

    def test_access_code_login_and_deactivation(self):
        client, response = self.login_viewer()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")
        self.reader.is_active = False
        self.reader.save(update_fields=["is_active"])
        next_response = client.get("/")
        self.assertEqual(next_response.status_code, 302)
        self.assertTrue(next_response.url.startswith("/login/"))

    def test_replace_policy_invalidates_first_session(self):
        first_client, first_login = self.login_viewer()
        self.assertEqual(first_login.status_code, 302)
        second_client, second_login = self.login_viewer()
        self.assertEqual(second_login.status_code, 302)
        kicked_out = first_client.get("/")
        self.assertEqual(kicked_out.status_code, 302)
        self.assertEqual(kicked_out.url, "/login/")
        self.assertIn(
            "another device",
            " ".join(str(message) for message in kicked_out.wsgi_request._messages),
        )
        self.assertEqual(second_client.get("/").status_code, 200)

    @override_settings(SINGLE_SESSION_POLICY="block")
    def test_block_policy_rejects_second_login(self):
        first_client, first_login = self.login_viewer()
        self.assertEqual(first_login.status_code, 302)
        _, second_login = self.login_viewer()
        self.assertEqual(second_login.status_code, 200)
        self.assertEqual(first_client.get("/").status_code, 200)

    def test_rate_limit_after_five_failed_logins(self):
        for _ in range(5):
            response = self.client.post(
                "/login/",
                {"username": "reader", "access_code": "wrong"},
            )
            self.assertEqual(response.status_code, 200)
        limited = self.client.post(
            "/login/",
            {"username": "reader", "access_code": "wrong"},
        )
        self.assertEqual(limited.status_code, 429)
        self.assertContains(limited, "Invalid credentials", status_code=429)

    def test_admin_login_works_with_same_origin_csrf(self):
        admin = User.objects.create_superuser(
            username="rootadmin",
            email="root@example.test",
            password="admin-password-123",
        )
        client = Client(enforce_csrf_checks=True)
        page = client.get("/admin/login/")
        self.assertEqual(page.status_code, 200)
        token_match = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"',
            page.content.decode(),
        )
        self.assertIsNotNone(token_match)
        result = client.post(
            "/admin/login/",
            {
                "username": admin.username,
                "password": "admin-password-123",
                "csrfmiddlewaretoken": token_match.group(1),
                "next": "/admin/",
            },
            HTTP_ORIGIN="http://testserver",
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(client.get("/admin/").status_code, 200)

    @override_settings(RUNNING_DEV_SERVER=True)
    def test_admin_login_accepts_null_origin_only_with_valid_csrf_token_in_dev(self):
        admin_user = User.objects.create_superuser(
            username="rootadmin",
            email="root@example.test",
            password="admin-password-123",
        )
        client = Client(enforce_csrf_checks=True)
        page = client.get("/admin/login/")
        token = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"',
            page.content.decode(),
        ).group(1)
        response = client.post(
            "/admin/login/",
            {
                "username": admin_user.username,
                "password": "admin-password-123",
                "csrfmiddlewaretoken": token,
            },
            HTTP_ORIGIN="null",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.get("/admin/").status_code, 200)

    def test_null_origin_is_rejected_outside_development_server(self):
        client = Client(enforce_csrf_checks=True)
        page = client.get("/admin/login/")
        token = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"',
            page.content.decode(),
        ).group(1)
        response = client.post(
            "/admin/login/",
            {
                "username": "unknown",
                "password": "unknown",
                "csrfmiddlewaretoken": token,
            },
            HTTP_ORIGIN="null",
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_viewer_and_sees_generated_code_once(self):
        admin_user = User.objects.create_superuser(
            username="rootadmin",
            email="root@example.test",
            password="admin-password-123",
        )
        client = Client()
        client.force_login(admin_user)
        response = client.get("/admin/auth/user/add/")
        self.assertEqual(response.status_code, 200)
        response = client.post(
            "/admin/auth/user/add/",
            {"username": "newreader", "is_active": "on", "_save": "Save"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        created = User.objects.get(username="newreader")
        self.assertTrue(created.has_usable_password())
        page_text = response.content.decode()
        self.assertIn("Access code for newreader", page_text)

    @override_settings(RUNNING_DEV_SERVER=True)
    def test_admin_can_upload_processed_note_with_opaque_origin_and_valid_csrf(self):
        admin_user = User.objects.create_superuser(
            username="rootadmin",
            email="root@example.test",
            password="admin-password-123",
        )
        buffer = io.BytesIO()
        Image.new("RGB", (80, 50), "navy").save(buffer, format="PNG")
        upload = SimpleUploadedFile("cover.png", buffer.getvalue(), content_type="image/png")
        client = Client(enforce_csrf_checks=True)
        client.force_login(admin_user)
        form_page = client.get("/admin/notes/note/add/")
        token = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"',
            form_page.content.decode(),
        ).group(1)
        response = client.post(
            "/admin/notes/note/add/",
            {
                "csrfmiddlewaretoken": token,
                "title": "Uploaded in admin",
                "slug": "uploaded-in-admin",
                "description": "",
                "source_type": "image",
                "is_published": "on",
                "position": "0",
                "upload": upload,
                "_save": "Save",
            },
            follow=True,
            HTTP_ORIGIN="null",
        )
        self.assertEqual(response.status_code, 200)
        created = Note.objects.get(slug="uploaded-in-admin")
        self.assertEqual(created.processing_status, "ready")
        self.assertEqual(created.pages.count(), 1)
        self.assertTrue(Path(created.pages.first().image_path).is_file())

    def test_non_staff_viewer_cannot_enter_admin(self):
        self.client.force_login(self.reader)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_image_and_pdf_upload_validation(self):
        invalid = SimpleUploadedFile("fake.jpg", b"not image bytes")
        with self.assertRaises(InvalidNoteFile):
            process_upload(self.note, invalid)

        document = fitz.open()
        document.new_page()
        document.new_page()
        pdf_upload = SimpleUploadedFile("two-pages.pdf", document.tobytes())
        process_upload(self.note, pdf_upload)
        pages = NotePage.objects.filter(note=self.note).order_by("page_number")
        self.assertEqual(pages.count(), 2)
        self.assertTrue(all(Path(page.image_path).is_file() for page in pages))
        self.assertNotEqual(self.note.source_path, "")

    def test_reupload_replaces_page_records_without_renaming_directories(self):
        def image_upload(color, filename):
            buffer = io.BytesIO()
            Image.new("RGB", (120, 80), color).save(buffer, format="PNG")
            return SimpleUploadedFile(filename, buffer.getvalue(), content_type="image/png")

        process_upload(self.note, image_upload("red", "first.png"))
        first_page = self.note.pages.get(page_number=1)
        first_path = Path(first_page.image_path)
        self.assertTrue(first_path.is_file())

        process_upload(self.note, image_upload("blue", "second.png"))
        self.note.refresh_from_db()
        second_page = self.note.pages.get(page_number=1)
        self.assertTrue(Path(second_page.image_path).is_file())
        self.assertNotEqual(first_page.image_path, second_page.image_path)
        self.assertEqual(self.note.processing_status, "ready")
        self.assertEqual(self.note.pages.count(), 1)

    def test_viewer_delivers_notely_watermark_and_private_headers(self):
        first_client, _ = self.login_viewer()
        first_page = first_client.get("/n/sample-notes/p/1/")
        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page["Content-Disposition"], "inline")
        self.assertIn("no-store", first_page["Cache-Control"])
        self.assertEqual(first_page["X-Content-Type-Options"], "nosniff")
        self.assertEqual(first_page["X-Robots-Tag"], "noindex, nofollow, noarchive")

        second = User.objects.create_user("second", password="secondcode2")
        second_client = Client()
        second_client.force_login(second)
        second_page = second_client.get("/n/sample-notes/p/1/")
        first_pixels = Image.open(io.BytesIO(first_page.content)).convert("RGB")
        second_pixels = Image.open(io.BytesIO(second_page.content)).convert("RGB")
        self.assertEqual(first_pixels.tobytes(), second_pixels.tobytes())

    @override_settings(RUNNING_DEV_SERVER=True)
    def test_page_fetch_from_opaque_origin_works_only_in_development(self):
        client = Client()
        client.force_login(self.reader)
        local_response = client.get(
            "/n/sample-notes/p/1/",
            HTTP_ORIGIN="null",
            HTTP_SEC_FETCH_DEST="empty",
        )
        self.assertEqual(local_response.status_code, 200)
        self.assertEqual(local_response["Content-Type"], "image/jpeg")

        with override_settings(RUNNING_DEV_SERVER=False):
            production_response = client.get(
                "/n/sample-notes/p/1/",
                HTTP_ORIGIN="null",
                HTTP_SEC_FETCH_DEST="empty",
            )
        self.assertEqual(production_response.status_code, 404)

    def test_admin_notes_list_shows_superuser_only_preview(self):
        admin_user = User.objects.create_superuser(
            username="previewadmin",
            email="preview@example.test",
            password="admin-password-123",
        )
        client = Client()
        client.force_login(admin_user)
        listing = client.get("/admin/notes/note/")
        self.assertEqual(listing.status_code, 200)
        self.assertContains(
            listing,
            f"/admin-preview/notes/{self.note.pk}/p/1/",
        )
        preview = client.get(f"/admin-preview/notes/{self.note.pk}/p/1/")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview["Content-Type"], "image/jpeg")

        viewer_client = Client()
        viewer_client.force_login(self.reader)
        denied = viewer_client.get(f"/admin-preview/notes/{self.note.pk}/p/1/")
        self.assertEqual(denied.status_code, 404)

    def test_open_note_writes_view_log_once(self):
        client, _ = self.login_viewer()
        response = client.get("/n/sample-notes/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ViewLog.objects.filter(user=self.reader, note=self.note).count(), 1)

    def test_private_source_is_not_routed(self):
        client, _ = self.login_viewer()
        response = client.get("/private/sources/1/original.pdf")
        self.assertEqual(response.status_code, 404)
