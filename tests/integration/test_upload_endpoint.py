"""
Integration tests for POST /documents/upload.
These tests exercise the full stack: HTTP → route → router → loader → response.
The TestClient runs the app in-process — no server needs to be running.
"""


class TestHealthCheck:
    def test_returns_200(self, client):
        assert client.get("/health").status_code == 200

    def test_response_shape(self, client):
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert "app" in body
        assert "allowed_types" in body


class TestUploadPng:
    def test_status_200(self, client, tmp_png):
        with open(tmp_png, "rb") as f:
            resp = client.post("/documents/upload", files={"file": ("test.png", f, "image/png")})
        assert resp.status_code == 200

    def test_response_contains_required_fields(self, client, tmp_png):
        with open(tmp_png, "rb") as f:
            body = client.post("/documents/upload", files={"file": ("test.png", f, "image/png")}).json()
        for field in ("filename", "file_type", "page_count", "char_count", "text", "preview_url", "metadata"):
            assert field in body, f"Missing field: {field}"

    def test_page_count_is_one(self, client, tmp_png):
        with open(tmp_png, "rb") as f:
            body = client.post("/documents/upload", files={"file": ("test.png", f, "image/png")}).json()
        assert body["page_count"] == 1

    def test_preview_url_format(self, client, tmp_png):
        with open(tmp_png, "rb") as f:
            body = client.post("/documents/upload", files={"file": ("test.png", f, "image/png")}).json()
        assert body["preview_url"].startswith("/outputs/")
        assert body["preview_url"].endswith("_preview.jpg")

    def test_original_filename_preserved(self, client, tmp_png):
        with open(tmp_png, "rb") as f:
            body = client.post("/documents/upload", files={"file": ("my_scan.png", f, "image/png")}).json()
        assert body["filename"] == "my_scan.png"


class TestUploadPdf:
    def test_status_200(self, client, tmp_pdf):
        with open(tmp_pdf, "rb") as f:
            resp = client.post("/documents/upload", files={"file": ("test.pdf", f, "application/pdf")})
        assert resp.status_code == 200

    def test_text_extracted(self, client, tmp_pdf):
        with open(tmp_pdf, "rb") as f:
            body = client.post("/documents/upload", files={"file": ("test.pdf", f, "application/pdf")}).json()
        assert "Hello from pytest PDF" in body["text"]

    def test_file_type_is_pdf(self, client, tmp_pdf):
        with open(tmp_pdf, "rb") as f:
            body = client.post("/documents/upload", files={"file": ("test.pdf", f, "application/pdf")}).json()
        assert body["file_type"] == "pdf"

    def test_char_count_matches_text_length(self, client, tmp_pdf):
        with open(tmp_pdf, "rb") as f:
            body = client.post("/documents/upload", files={"file": ("test.pdf", f, "application/pdf")}).json()
        assert body["char_count"] == len(body["text"])


class TestUploadDocx:
    def test_status_200(self, client, tmp_docx):
        with open(tmp_docx, "rb") as f:
            resp = client.post("/documents/upload", files={"file": ("test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
        assert resp.status_code == 200

    def test_paragraph_in_text(self, client, tmp_docx):
        with open(tmp_docx, "rb") as f:
            body = client.post("/documents/upload", files={"file": ("test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}).json()
        assert "Hello from pytest paragraph" in body["text"]

    def test_table_content_in_text(self, client, tmp_docx):
        with open(tmp_docx, "rb") as f:
            body = client.post("/documents/upload", files={"file": ("test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}).json()
        assert "pytest" in body["text"]


class TestUploadPasswordPdf:
    def test_missing_password_returns_401(self, client, tmp_pdf_encrypted):
        path, _ = tmp_pdf_encrypted
        with open(path, "rb") as f:
            resp = client.post("/documents/upload", files={"file": ("locked.pdf", f, "application/pdf")})
        assert resp.status_code == 401

    def test_wrong_password_returns_401(self, client, tmp_pdf_encrypted):
        path, _ = tmp_pdf_encrypted
        with open(path, "rb") as f:
            resp = client.post(
                "/documents/upload",
                files={"file": ("locked.pdf", f, "application/pdf")},
                data={"password": "wrongpassword"},
            )
        assert resp.status_code == 401

    def test_correct_password_returns_200(self, client, tmp_pdf_encrypted):
        path, password = tmp_pdf_encrypted
        with open(path, "rb") as f:
            resp = client.post(
                "/documents/upload",
                files={"file": ("locked.pdf", f, "application/pdf")},
                data={"password": password},
            )
        assert resp.status_code == 200


class TestUploadRejections:
    def test_unsupported_file_type_returns_415(self, client, tmp_unsupported_file):
        with open(tmp_unsupported_file, "rb") as f:
            resp = client.post(
                "/documents/upload",
                files={"file": ("malicious.exe", f, "application/octet-stream")},
            )
        assert resp.status_code == 415

    def test_error_response_has_detail_field(self, client, tmp_unsupported_file):
        with open(tmp_unsupported_file, "rb") as f:
            body = client.post(
                "/documents/upload",
                files={"file": ("malicious.exe", f, "application/octet-stream")},
            ).json()
        assert "detail" in body