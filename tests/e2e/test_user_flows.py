"""
End-to-end tests for complete user workflows.
Tests multi-step user journeys through the application.
"""
import pytest
import io
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


@pytest.mark.e2e
class TestDocumentInjectionToChat:
    """Tests for the Document Injection -> RAG Chat workflow."""

    def test_upload_and_convert_document(self, client, txt_file_data):
        """Step 1: Upload and convert a document."""
        data = {
            'file': (io.BytesIO(txt_file_data), 'test_doc.txt')
        }
        response = client.post(
            '/api/convert',
            data=data,
            content_type='multipart/form-data'
        )

        # Should succeed or be rate limited
        assert response.status_code in [200, 429, 503]
        if response.status_code == 200:
            result = response.get_json()
            assert result is not None

    def test_analyze_converted_document(self, client, sample_text):
        """Step 2: Analyze the converted document."""
        response = client.post(
            '/api/analyze',
            json={'content': sample_text},
            content_type='application/json'
        )

        assert response.status_code == 200

    def test_chunk_for_rag(self, client, sample_text):
        """Step 3: Chunk document for RAG."""
        response = client.post(
            '/api/chunk',
            json={
                'content': sample_text,
                'chunk_size': 256,
                'strategy': 'semantic_window'
            },
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert 'chunks' in data

    def test_generate_embeddings(self, client, sample_text):
        """Step 4: Generate embeddings for chunks."""
        response = client.post(
            '/api/embed',
            json={'text': sample_text[:500]},
            content_type='application/json'
        )

        # May fail if embedding model not loaded
        assert response.status_code in [200, 503]

    def test_full_injection_to_rag_flow(self, client, txt_file_data, sample_text):
        """Complete flow: Upload -> Convert -> Chunk -> Embed."""
        # Step 1: Convert document
        convert_response = client.post(
            '/api/convert',
            data={'file': (io.BytesIO(txt_file_data), 'flow_test.txt')},
            content_type='multipart/form-data'
        )

        if convert_response.status_code != 200:
            pytest.skip("Conversion not available")

        converted_content = convert_response.get_json().get('content', sample_text)

        # Step 2: Chunk the content
        chunk_response = client.post(
            '/api/chunk',
            json={'content': converted_content, 'chunk_size': 256},
            content_type='application/json'
        )

        assert chunk_response.status_code == 200
        chunks = chunk_response.get_json().get('chunks', [])

        # Step 3: Embed first chunk (if available)
        if chunks:
            first_chunk_text = chunks[0].get('text', '')
            if first_chunk_text:
                embed_response = client.post(
                    '/api/embed',
                    json={'text': first_chunk_text},
                    content_type='application/json'
                )
                # Embedding may or may not be available
                assert embed_response.status_code in [200, 503]


@pytest.mark.e2e
class TestBatchProcessingWorkflow:
    """Tests for batch processing workflow."""

    def test_batch_upload_endpoint_exists(self, client):
        """Batch upload endpoint should exist."""
        response = client.post('/api/batch/convert')

        # Should return error for missing file, not 404
        assert response.status_code != 404

    def test_batch_status_endpoint(self, client):
        """Batch status endpoint should work."""
        # Try to get status of non-existent job
        response = client.get('/api/batch/status/nonexistent-job-id')

        # Should return 404 or error, not 500
        assert response.status_code in [200, 400, 404]


@pytest.mark.e2e
class TestRagChatWorkflow:
    """Tests for RAG chat workflow."""

    def test_rag_page_loads(self, client):
        """RAG chat page should load."""
        response = client.get('/rag')

        assert response.status_code == 200

    def test_memory_status_endpoint(self, client):
        """Memory status endpoint should work."""
        response = client.get('/api/memory/status')

        assert response.status_code in [200, 404]

    def test_memory_reset_endpoint(self, client):
        """Memory reset endpoint should work."""
        response = client.post('/api/memory/reset')

        assert response.status_code in [200, 404]


@pytest.mark.e2e
class TestPageNavigation:
    """Tests for page navigation and loading."""

    def test_landing_page_loads(self, client):
        """Landing page should load."""
        response = client.get('/')

        assert response.status_code == 200

    def test_convert_page_loads(self, client):
        """Convert page should load."""
        response = client.get('/convert')

        assert response.status_code == 200

    def test_architecture_page_loads(self, client):
        """Architecture page should load."""
        response = client.get('/architecture')

        assert response.status_code == 200

    def test_methodology_page_loads(self, client):
        """Methodology page should load."""
        response = client.get('/methodology')

        assert response.status_code == 200

    def test_use_cases_page_loads(self, client):
        """Use cases page should load."""
        response = client.get('/use-cases')

        assert response.status_code == 200

    def test_stats_page_loads(self, client):
        """Stats page should load."""
        response = client.get('/stats')

        assert response.status_code == 200

    def test_api_docs_page_loads(self, client):
        """API docs page should load."""
        response = client.get('/api/docs')

        assert response.status_code in [200, 302]

    def test_contact_page_loads(self, client):
        """Contact page should load."""
        response = client.get('/contact')

        assert response.status_code == 200


@pytest.mark.e2e
class TestErrorHandling:
    """Tests for error handling across the application."""

    def test_404_returns_json(self, client):
        """404 errors should return JSON for API routes."""
        response = client.get('/api/nonexistent-endpoint')

        assert response.status_code == 404
        assert response.content_type == 'application/json'

    def test_400_returns_json(self, client):
        """400 errors should return JSON."""
        response = client.post(
            '/api/convert',
            data='invalid data',
            content_type='text/plain'
        )

        if response.status_code == 400:
            assert response.content_type == 'application/json'

    def test_error_includes_request_id(self, client):
        """Errors should include request ID."""
        response = client.get('/api/nonexistent')

        if response.status_code >= 400:
            data = response.get_json()
            if data:
                assert 'request_id' in data or 'X-Request-ID' in response.headers


@pytest.mark.e2e
@pytest.mark.slow
class TestPerformance:
    """Performance-related E2E tests."""

    def test_health_check_is_fast(self, client):
        """Health check should respond quickly."""
        import time

        start = time.time()
        response = client.get('/health')
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 2.0  # Should respond in under 2 seconds

    def test_stats_endpoint_is_fast(self, client):
        """Stats endpoint should respond quickly."""
        import time

        start = time.time()
        response = client.get('/api/stats')
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 2.0
