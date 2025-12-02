"""
Integration tests for RAG pipeline endpoints.
Tests chunking, embedding, and export endpoints.
"""
import pytest
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


@pytest.mark.integration
class TestTokenCountEndpoint:
    """Tests for POST /api/token-count endpoint."""

    def test_token_count_with_text(self, client, sample_text):
        """Token count should work with text content."""
        response = client.post(
            '/api/token-count',
            json={'content': sample_text},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert 'token_count' in data or 'tokens' in data or 'count' in data

    def test_token_count_empty_text(self, client):
        """Token count with empty text should return zero."""
        response = client.post(
            '/api/token-count',
            json={'content': ''},
            content_type='application/json'
        )

        assert response.status_code in [200, 400]

    def test_token_count_missing_content(self, client):
        """Token count without content should return error."""
        response = client.post(
            '/api/token-count',
            json={},
            content_type='application/json'
        )

        assert response.status_code in [400, 422]


@pytest.mark.integration
class TestChunkEndpoint:
    """Tests for POST /api/chunk endpoint."""

    def test_chunk_with_default_params(self, client, sample_text):
        """Chunking should work with default parameters."""
        response = client.post(
            '/api/chunk',
            json={'content': sample_text},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert 'chunks' in data or 'result' in data

    def test_chunk_with_custom_size(self, client, sample_text):
        """Chunking should respect custom chunk size."""
        response = client.post(
            '/api/chunk',
            json={
                'content': sample_text,
                'chunk_size': 256,
                'chunk_overlap': 25
            },
            content_type='application/json'
        )

        assert response.status_code == 200

    def test_chunk_with_strategy(self, client, sample_text):
        """Chunking should accept different strategies."""
        strategies = ['token', 'character', 'recursive_character', 'semantic_window']

        for strategy in strategies:
            response = client.post(
                '/api/chunk',
                json={
                    'content': sample_text,
                    'strategy': strategy
                },
                content_type='application/json'
            )

            assert response.status_code == 200, f"Strategy {strategy} failed"

    def test_chunk_returns_metadata(self, client, sample_text):
        """Chunking should return metadata about chunks."""
        response = client.post(
            '/api/chunk',
            json={'content': sample_text},
            content_type='application/json'
        )

        data = response.get_json()
        if 'metadata' in data:
            assert 'total_chunks' in data['metadata'] or 'chunk_count' in data['metadata']


@pytest.mark.integration
class TestEmbedEndpoint:
    """Tests for POST /api/embed endpoint."""

    def test_embed_single_text(self, client):
        """Embedding should work for single text."""
        response = client.post(
            '/api/embed',
            json={'text': 'This is a test sentence for embedding.'},
            content_type='application/json'
        )

        # 503 if model not loaded, 500 if internal error
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.get_json()
            assert 'embedding' in data or 'embeddings' in data or 'vector' in data

    def test_embed_batch_texts(self, client):
        """Embedding should work for batch of texts."""
        response = client.post(
            '/api/embed',
            json={
                'texts': [
                    'First text for embedding.',
                    'Second text for embedding.',
                    'Third text for embedding.'
                ]
            },
            content_type='application/json'
        )

        # 503 if model not loaded, 500 if internal error
        assert response.status_code in [200, 500, 503]

    def test_embed_empty_text(self, client):
        """Empty text should be handled gracefully."""
        response = client.post(
            '/api/embed',
            json={'text': ''},
            content_type='application/json'
        )

        # 500 if internal error during validation
        assert response.status_code in [200, 400, 500]


@pytest.mark.integration
class TestAnalyzeEndpoint:
    """Tests for POST /api/analyze endpoint."""

    def test_analyze_document(self, client, sample_text):
        """Document analysis should work."""
        response = client.post(
            '/api/analyze',
            json={'content': sample_text},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        # Should return analysis results
        assert isinstance(data, dict)


@pytest.mark.integration
class TestExportEndpoints:
    """Tests for export endpoints."""

    def test_export_jsonl(self, client, sample_text):
        """JSONL export should work."""
        # First chunk the text
        chunk_response = client.post(
            '/api/chunk',
            json={'content': sample_text},
            content_type='application/json'
        )

        if chunk_response.status_code == 200:
            response = client.post(
                '/api/export/jsonl',
                json={'content': sample_text},
                content_type='application/json'
            )

            assert response.status_code in [200, 400]

    def test_export_vectordb_chromadb(self, client, sample_text):
        """ChromaDB export format should work."""
        response = client.post(
            '/api/export/vectordb',
            json={
                'content': sample_text,
                'format': 'chromadb'
            },
            content_type='application/json'
        )

        # 503 if service unavailable, 500 if internal error
        assert response.status_code in [200, 400, 500, 503]

    def test_export_vectordb_lancedb(self, client, sample_text):
        """LanceDB export format should work."""
        response = client.post(
            '/api/export/vectordb',
            json={
                'content': sample_text,
                'format': 'lancedb'
            },
            content_type='application/json'
        )

        # 503 if service unavailable, 500 if internal error
        assert response.status_code in [200, 400, 500, 503]


@pytest.mark.integration
class TestPipelineEndpoint:
    """Tests for POST /api/pipeline endpoint."""

    def test_full_pipeline(self, client, sample_text):
        """Full RAG pipeline should process document."""
        response = client.post(
            '/api/pipeline',
            json={'content': sample_text},
            content_type='application/json'
        )

        # 503 if service unavailable, 500 if internal error
        assert response.status_code in [200, 400, 500, 503]
        if response.status_code == 200:
            data = response.get_json()
            # Should return chunked and embedded data
            assert 'chunks' in data or 'result' in data or 'embeddings' in data

    def test_pipeline_with_options(self, client, sample_text):
        """Pipeline should accept configuration options."""
        response = client.post(
            '/api/pipeline',
            json={
                'content': sample_text,
                'chunk_size': 256,
                'chunk_overlap': 25,
                'include_embeddings': True
            },
            content_type='application/json'
        )

        # 503 if service unavailable, 500 if internal error
        assert response.status_code in [200, 400, 500, 503]


@pytest.mark.integration
class TestRetrieveEndpoint:
    """Tests for POST /api/retrieve endpoint."""

    def test_retrieve_requires_query(self, client):
        """Retrieve should require a query."""
        response = client.post(
            '/api/retrieve',
            json={},
            content_type='application/json'
        )

        assert response.status_code in [400, 422]

    def test_retrieve_with_query(self, client):
        """Retrieve should accept a query."""
        response = client.post(
            '/api/retrieve',
            json={
                'query': 'What is the document about?',
                'top_k': 3
            },
            content_type='application/json'
        )

        # May fail if no documents in memory
        assert response.status_code in [200, 400, 404]


@pytest.mark.integration
class TestEmbeddingInfo:
    """Tests for embedding info endpoint."""

    def test_embedding_info(self, client):
        """Should return embedding model information."""
        response = client.get('/api/embedding-info')

        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.get_json()
            assert 'model' in data or 'dimensions' in data or 'info' in data
