"""
Unit tests for the chunker module.
Tests RAG chunking functionality without external dependencies.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


@pytest.mark.unit
class TestChunkDocument:
    """Tests for chunk_document function."""

    def test_empty_text_returns_error(self):
        """Empty text should return error."""
        # Mock tiktoken before import
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            from chunker import chunk_document

            result = chunk_document("")
            assert "error" in result
            assert result["chunks"] == []

    def test_whitespace_only_returns_error(self):
        """Whitespace-only text should return error."""
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            from chunker import chunk_document

            result = chunk_document("   \n\t  ")
            assert "error" in result

    def test_single_chunk_for_short_text(self):
        """Short text should result in a single chunk."""
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            from chunker import chunk_document

            text = "This is a short test document."
            result = chunk_document(text, chunk_size=512, strategy="character")

            assert "error" not in result
            assert len(result["chunks"]) == 1
            assert result["chunks"][0]["text"] == text

    def test_multiple_chunks_for_long_text(self):
        """Long text should be split into multiple chunks."""
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            from chunker import chunk_document

            # Create a long text
            text = "This is a test sentence. " * 500
            result = chunk_document(text, chunk_size=100, strategy="character")

            assert "error" not in result
            assert len(result["chunks"]) > 1

    def test_chunk_size_validation(self):
        """Chunk size should be validated and constrained."""
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            from chunker import chunk_document

            text = "Test document content."

            # Too small chunk size should be adjusted to minimum
            result = chunk_document(text, chunk_size=10, strategy="character")
            assert result["metadata"]["chunk_size"] >= 64

            # Too large chunk size should be adjusted to maximum
            result = chunk_document(text, chunk_size=100000, strategy="character")
            assert result["metadata"]["chunk_size"] <= 8192

    def test_overlap_validation(self):
        """Overlap should not exceed half of chunk size."""
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            from chunker import chunk_document

            text = "This is a test. " * 100
            result = chunk_document(
                text,
                chunk_size=100,
                chunk_overlap=200,  # Larger than chunk_size
                strategy="character"
            )

            # Overlap should be constrained
            assert result["metadata"]["chunk_overlap"] <= 50

    def test_metadata_includes_statistics(self):
        """Result metadata should include all expected statistics."""
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            from chunker import chunk_document

            text = "Test document with some content."
            result = chunk_document(text, strategy="character")

            metadata = result["metadata"]
            assert "total_chunks" in metadata
            assert "total_tokens" in metadata
            assert "total_characters" in metadata
            assert "chunk_size" in metadata
            assert "chunk_overlap" in metadata
            assert "strategy" in metadata
            assert "average_chunk_tokens" in metadata
            assert "average_chunk_chars" in metadata


@pytest.mark.unit
class TestChunkStrategies:
    """Tests for different chunking strategies."""

    def test_character_strategy(self):
        """Character strategy should work without tiktoken."""
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            # Force tiktoken unavailable
            import chunker
            chunker.TIKTOKEN_AVAILABLE = False

            text = "This is a test. " * 50
            result = chunker.chunk_document(text, strategy="character")

            assert "error" not in result
            assert result["metadata"]["strategy"] == "character"

    def test_recursive_character_strategy(self):
        """Recursive character strategy should split on paragraphs."""
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            from chunker import chunk_document

            text = """Paragraph one with some content.

Paragraph two with more content.

Paragraph three with final content."""

            result = chunk_document(text, chunk_size=100, strategy="recursive_character")

            assert "error" not in result
            assert result["metadata"]["strategy"] == "recursive_character"

    def test_semantic_window_strategy(self):
        """Semantic window strategy should preserve sentences."""
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            from chunker import chunk_document

            text = "First sentence here. Second sentence follows. Third sentence ends."
            result = chunk_document(text, chunk_size=50, strategy="semantic_window")

            assert "error" not in result
            assert result["metadata"]["strategy"] == "semantic_window"

    def test_fixed_size_strategy(self):
        """Fixed size strategy should create consistent chunks."""
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            from chunker import chunk_document

            text = "A" * 1000
            result = chunk_document(text, chunk_size=50, strategy="fixed_size")

            assert "error" not in result
            assert result["metadata"]["strategy"] == "fixed_size"


@pytest.mark.unit
class TestChunkStructure:
    """Tests for chunk structure and content."""

    def test_chunk_has_required_fields(self):
        """Each chunk should have all required fields."""
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            from chunker import chunk_document

            text = "Test document for field validation."
            result = chunk_document(text, strategy="character")

            chunk = result["chunks"][0]
            assert "index" in chunk
            assert "text" in chunk
            assert "token_count" in chunk
            assert "char_count" in chunk
            assert "start_char" in chunk
            assert "end_char" in chunk
            assert "metadata" in chunk

    def test_chunk_indices_are_sequential(self):
        """Chunk indices should be sequential starting from 0."""
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            from chunker import chunk_document

            text = "Test sentence. " * 100
            result = chunk_document(text, chunk_size=50, strategy="character")

            indices = [chunk["index"] for chunk in result["chunks"]]
            assert indices == list(range(len(indices)))

    def test_chunk_positions_are_valid(self):
        """Chunk start/end positions should be valid."""
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            from chunker import chunk_document

            text = "Test document content here."
            result = chunk_document(text, strategy="character")

            for chunk in result["chunks"]:
                assert chunk["start_char"] >= 0
                assert chunk["end_char"] >= chunk["start_char"]
                assert chunk["char_count"] >= 0


@pytest.mark.unit
class TestTokenCounting:
    """Tests for token counting functionality."""

    def test_get_token_count_empty_text(self):
        """Empty text should return zero tokens."""
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            from chunker import get_token_count

            result = get_token_count("")
            assert result["token_count"] == 0

    def test_get_token_count_with_text(self):
        """Non-empty text should return positive token count."""
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            from chunker import get_token_count

            result = get_token_count("Hello world, this is a test.")

            assert result["token_count"] > 0
            assert "method" in result
            assert "character_count" in result

    def test_token_estimation_fallback(self):
        """Token estimation should work when tiktoken unavailable."""
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            import chunker
            chunker.TIKTOKEN_AVAILABLE = False

            result = chunker.get_token_count("Test text for estimation")

            assert result["token_count"] > 0
            assert result["method"] == "estimation"


@pytest.mark.unit
class TestChunkWithHeaders:
    """Tests for header-aware chunking."""

    def test_header_context_included(self):
        """Chunks should include header context in metadata."""
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            from chunker import chunk_with_headers

            text = """# Main Title

Introduction paragraph here.

## Section One

Content of section one.

## Section Two

Content of section two.
"""
            result = chunk_with_headers(text, chunk_size=1000)

            assert "error" not in result
            # Check that chunks have header context
            for chunk in result["chunks"]:
                assert "header_context" in chunk["metadata"]
                assert "section" in chunk["metadata"]


@pytest.mark.unit
class TestExportForEmbedding:
    """Tests for embedding export functionality."""

    def test_export_with_metadata(self):
        """Export should include metadata when requested."""
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            from chunker import chunk_document, export_for_embedding

            text = "Test document for export."
            chunks_result = chunk_document(text, strategy="character")
            export = export_for_embedding(chunks_result, include_metadata=True)

            assert len(export) == len(chunks_result["chunks"])
            assert "id" in export[0]
            assert "text" in export[0]
            assert "metadata" in export[0]

    def test_export_without_metadata(self):
        """Export should exclude metadata when not requested."""
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            from chunker import chunk_document, export_for_embedding

            text = "Test document for export."
            chunks_result = chunk_document(text, strategy="character")
            export = export_for_embedding(chunks_result, include_metadata=False)

            assert "metadata" not in export[0]

    def test_export_handles_error_result(self):
        """Export should handle error results gracefully."""
        with patch.dict(sys.modules, {'tiktoken': MagicMock()}):
            from chunker import export_for_embedding

            error_result = {"error": "Test error"}
            export = export_for_embedding(error_result)

            assert export == []
