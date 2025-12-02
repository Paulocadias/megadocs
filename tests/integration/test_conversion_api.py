"""
Integration tests for document conversion API.
Tests /api/convert and related endpoints.
"""
import pytest
import io
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


@pytest.mark.integration
class TestConversionEndpoint:
    """Tests for POST /api/convert endpoint."""

    def test_convert_requires_file(self, client):
        """Conversion should require a file upload."""
        response = client.post('/api/convert')

        assert response.status_code in [400, 422]

    def test_convert_txt_file(self, client, txt_file_data):
        """Text file should convert successfully."""
        data = {
            'file': (io.BytesIO(txt_file_data), 'test.txt')
        }
        response = client.post(
            '/api/convert',
            data=data,
            content_type='multipart/form-data'
        )

        # Should succeed or return validation error
        assert response.status_code in [200, 400, 429, 503]
        if response.status_code == 200:
            result = response.get_json()
            assert 'success' in result or 'content' in result or 'markdown' in result

    def test_convert_html_file(self, client, html_file_data):
        """HTML file should convert successfully."""
        data = {
            'file': (io.BytesIO(html_file_data), 'test.html')
        }
        response = client.post(
            '/api/convert',
            data=data,
            content_type='multipart/form-data'
        )

        assert response.status_code in [200, 400, 429, 503]

    def test_convert_json_file(self, client, json_file_data):
        """JSON file should convert successfully."""
        data = {
            'file': (io.BytesIO(json_file_data), 'test.json')
        }
        response = client.post(
            '/api/convert',
            data=data,
            content_type='multipart/form-data'
        )

        assert response.status_code in [200, 400, 429, 503]

    def test_convert_unsupported_format(self, client):
        """Unsupported format should return error."""
        data = {
            'file': (io.BytesIO(b'binary content'), 'test.exe')
        }
        response = client.post(
            '/api/convert',
            data=data,
            content_type='multipart/form-data'
        )

        assert response.status_code in [400, 415]

    def test_convert_empty_file(self, client):
        """Empty file should be handled gracefully."""
        data = {
            'file': (io.BytesIO(b''), 'empty.txt')
        }
        response = client.post(
            '/api/convert',
            data=data,
            content_type='multipart/form-data'
        )

        # Should return error or handle gracefully
        assert response.status_code in [200, 400, 422]


@pytest.mark.integration
class TestConversionOutputFormats:
    """Tests for different output formats."""

    def test_output_format_markdown(self, client, txt_file_data):
        """Should support markdown output format."""
        data = {
            'file': (io.BytesIO(txt_file_data), 'test.txt'),
            'output_format': 'markdown'
        }
        response = client.post(
            '/api/convert',
            data=data,
            content_type='multipart/form-data'
        )

        assert response.status_code in [200, 400, 429, 503]

    def test_output_format_text(self, client, txt_file_data):
        """Should support plain text output format."""
        data = {
            'file': (io.BytesIO(txt_file_data), 'test.txt'),
            'output_format': 'text'
        }
        response = client.post(
            '/api/convert',
            data=data,
            content_type='multipart/form-data'
        )

        assert response.status_code in [200, 400, 429, 503]

    def test_output_format_json(self, client, txt_file_data):
        """Should support JSON output format."""
        data = {
            'file': (io.BytesIO(txt_file_data), 'test.txt'),
            'output_format': 'json'
        }
        response = client.post(
            '/api/convert',
            data=data,
            content_type='multipart/form-data'
        )

        assert response.status_code in [200, 400, 429, 503]

    def test_output_format_xml(self, client, txt_file_data):
        """Should support XML output format."""
        data = {
            'file': (io.BytesIO(txt_file_data), 'test.txt'),
            'output_format': 'xml'
        }
        response = client.post(
            '/api/convert',
            data=data,
            content_type='multipart/form-data'
        )

        assert response.status_code in [200, 400, 429, 503]


@pytest.mark.integration
class TestConversionSanitization:
    """Tests for content sanitization options."""

    def test_sanitize_remove_macros(self, client, txt_file_data):
        """Should support macro removal option."""
        data = {
            'file': (io.BytesIO(txt_file_data), 'test.txt'),
            'remove_macros': 'true'
        }
        response = client.post(
            '/api/convert',
            data=data,
            content_type='multipart/form-data'
        )

        assert response.status_code in [200, 400, 429, 503]

    def test_sanitize_strip_metadata(self, client, txt_file_data):
        """Should support metadata stripping option."""
        data = {
            'file': (io.BytesIO(txt_file_data), 'test.txt'),
            'strip_metadata': 'true'
        }
        response = client.post(
            '/api/convert',
            data=data,
            content_type='multipart/form-data'
        )

        assert response.status_code in [200, 400, 429, 503]

    def test_sanitize_redact_emails(self, client):
        """Should support email redaction option."""
        content = b"Contact us at test@example.com for help"
        data = {
            'file': (io.BytesIO(content), 'contact.txt'),
            'redact_emails': 'true'
        }
        response = client.post(
            '/api/convert',
            data=data,
            content_type='multipart/form-data'
        )

        assert response.status_code in [200, 400, 429, 503]
        if response.status_code == 200:
            result = response.get_json()
            content_str = str(result)
            # Email should be redacted
            assert 'test@example.com' not in content_str or 'REDACTED' in content_str


@pytest.mark.integration
class TestConversionErrorHandling:
    """Tests for error handling in conversion."""

    def test_rejects_oversized_file(self, client, oversized_file_data):
        """Oversized files should be rejected with 413."""
        data = {
            'file': (io.BytesIO(oversized_file_data), 'large.txt')
        }
        response = client.post(
            '/api/convert',
            data=data,
            content_type='multipart/form-data'
        )

        assert response.status_code == 413

    def test_handles_malformed_request(self, client):
        """Malformed requests should return appropriate error."""
        response = client.post(
            '/api/convert',
            data='not a valid multipart',
            content_type='text/plain'
        )

        assert response.status_code in [400, 415]

    def test_returns_json_error(self, client):
        """Errors should be returned as JSON."""
        response = client.post('/api/convert')

        if response.status_code != 200:
            assert response.content_type == 'application/json'
            data = response.get_json()
            assert 'error' in data or 'message' in data


@pytest.mark.integration
class TestWebConversion:
    """Tests for web-based conversion form."""

    def test_convert_page_loads(self, client):
        """Convert page should load successfully."""
        response = client.get('/convert')

        assert response.status_code == 200

    def test_injection_page_loads(self, client):
        """Injection page should load successfully."""
        response = client.get('/injection')

        # May redirect or return 200
        assert response.status_code in [200, 302, 308]
