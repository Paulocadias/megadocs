"""
RAG Chunking Module for MegaDoc.

Provides document chunking capabilities for RAG (Retrieval-Augmented Generation) pipelines:
- Token-accurate chunking using tiktoken (OpenAI-compatible)
- Configurable chunk sizes and overlap
- Multiple chunking strategies
- Export to JSON for vector database integration

All processing is done offline - no external API calls.
"""

import re
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

# Token counting library
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

logger = logging.getLogger(__name__)

# Default encoding for tiktoken (cl100k_base is used by GPT-4, GPT-3.5-turbo)
DEFAULT_ENCODING = "cl100k_base"


@dataclass
class Chunk:
    """Represents a text chunk."""
    index: int
    text: str
    token_count: int
    char_count: int
    start_char: int
    end_char: int
    metadata: Dict[str, Any]


def chunk_document(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    strategy: str = "token"
) -> Dict[str, Any]:
    """
    Chunk a document for RAG pipeline integration.

    Args:
        text: The text to chunk
        chunk_size: Target chunk size (in tokens or characters depending on strategy)
        chunk_overlap: Overlap between chunks
        strategy: "token" (tiktoken-based) or "character" (simple character split)

    Returns:
        Dictionary containing chunks and metadata
    """
    if not text or not text.strip():
        return {"error": "No content to chunk", "chunks": []}

    # Validate parameters
    chunk_size = max(64, min(chunk_size, 8192))
    chunk_overlap = max(0, min(chunk_overlap, chunk_size // 2))

    if strategy == "token" and TIKTOKEN_AVAILABLE:
        chunks = _chunk_by_tokens(text, chunk_size, chunk_overlap)
    else:
        chunks = _chunk_by_characters(text, chunk_size, chunk_overlap)
        if strategy == "token" and not TIKTOKEN_AVAILABLE:
            logger.warning("tiktoken not available, falling back to character chunking")

    # Calculate statistics
    total_tokens = sum(c.token_count for c in chunks)
    total_chars = len(text)

    return {
        "chunks": [asdict(c) for c in chunks],
        "metadata": {
            "total_chunks": len(chunks),
            "total_tokens": total_tokens,
            "total_characters": total_chars,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "strategy": strategy if (strategy == "character" or not TIKTOKEN_AVAILABLE) else "token",
            "encoding": DEFAULT_ENCODING if TIKTOKEN_AVAILABLE else None,
            "average_chunk_tokens": round(total_tokens / max(len(chunks), 1), 1),
            "average_chunk_chars": round(total_chars / max(len(chunks), 1), 1)
        }
    }


def _chunk_by_tokens(
    text: str,
    chunk_size: int,
    chunk_overlap: int
) -> List[Chunk]:
    """Chunk text by token count using tiktoken."""
    try:
        encoding = tiktoken.get_encoding(DEFAULT_ENCODING)
    except Exception as e:
        logger.error(f"Failed to load tiktoken encoding: {e}")
        return _chunk_by_characters(text, chunk_size, chunk_overlap)

    # Encode the entire text
    tokens = encoding.encode(text)
    total_tokens = len(tokens)

    if total_tokens <= chunk_size:
        # Text fits in a single chunk
        return [Chunk(
            index=0,
            text=text,
            token_count=total_tokens,
            char_count=len(text),
            start_char=0,
            end_char=len(text),
            metadata={"is_single_chunk": True}
        )]

    chunks = []
    chunk_index = 0
    token_start = 0

    while token_start < total_tokens:
        # Calculate token end position
        token_end = min(token_start + chunk_size, total_tokens)

        # Get the chunk tokens
        chunk_tokens = tokens[token_start:token_end]

        # Decode back to text
        chunk_text = encoding.decode(chunk_tokens)

        # Calculate character positions (approximate)
        # We need to find where this chunk starts and ends in the original text
        if chunk_index == 0:
            char_start = 0
        else:
            # Decode up to token_start to get character position
            char_start = len(encoding.decode(tokens[:token_start]))

        char_end = len(encoding.decode(tokens[:token_end]))

        chunks.append(Chunk(
            index=chunk_index,
            text=chunk_text,
            token_count=len(chunk_tokens),
            char_count=len(chunk_text),
            start_char=char_start,
            end_char=char_end,
            metadata={
                "token_start": token_start,
                "token_end": token_end
            }
        ))

        chunk_index += 1

        # Move to next chunk with overlap
        token_start = token_end - chunk_overlap

        # Avoid infinite loop if overlap is too large
        if token_start >= token_end:
            token_start = token_end

    return chunks


def _chunk_by_characters(
    text: str,
    chunk_size: int,
    chunk_overlap: int
) -> List[Chunk]:
    """Chunk text by character count (fallback method)."""
    # For character mode, multiply chunk_size by ~4 to approximate tokens
    char_chunk_size = chunk_size * 4
    char_overlap = chunk_overlap * 4

    total_chars = len(text)

    if total_chars <= char_chunk_size:
        # Estimate token count
        token_count = _estimate_tokens(text)
        return [Chunk(
            index=0,
            text=text,
            token_count=token_count,
            char_count=total_chars,
            start_char=0,
            end_char=total_chars,
            metadata={"is_single_chunk": True, "token_estimation": "approximate"}
        )]

    chunks = []
    chunk_index = 0
    char_start = 0

    while char_start < total_chars:
        # Calculate end position
        char_end = min(char_start + char_chunk_size, total_chars)

        # Try to break at sentence or word boundary
        if char_end < total_chars:
            # Look for sentence boundary
            search_start = max(char_end - 100, char_start)
            last_sentence = text.rfind('. ', search_start, char_end)
            if last_sentence > char_start + char_chunk_size // 2:
                char_end = last_sentence + 1
            else:
                # Look for word boundary
                last_space = text.rfind(' ', search_start, char_end)
                if last_space > char_start + char_chunk_size // 2:
                    char_end = last_space

        chunk_text = text[char_start:char_end].strip()
        token_count = _estimate_tokens(chunk_text)

        chunks.append(Chunk(
            index=chunk_index,
            text=chunk_text,
            token_count=token_count,
            char_count=len(chunk_text),
            start_char=char_start,
            end_char=char_end,
            metadata={"token_estimation": "approximate"}
        ))

        chunk_index += 1

        # Move to next chunk with overlap
        char_start = char_end - char_overlap

        # Avoid infinite loop
        if char_start >= char_end:
            char_start = char_end

    return chunks


def _estimate_tokens(text: str) -> int:
    """Estimate token count without tiktoken (rough approximation)."""
    # Rough estimate: ~4 characters per token for English
    # This is a common approximation used when tiktoken isn't available
    return max(1, len(text) // 4)


def get_token_count(text: str) -> Dict[str, Any]:
    """
    Get accurate token count for text.

    Returns:
        Dictionary with token count and encoding information
    """
    if not text:
        return {"token_count": 0, "encoding": None}

    if TIKTOKEN_AVAILABLE:
        try:
            encoding = tiktoken.get_encoding(DEFAULT_ENCODING)
            tokens = encoding.encode(text)
            return {
                "token_count": len(tokens),
                "encoding": DEFAULT_ENCODING,
                "method": "tiktoken",
                "character_count": len(text)
            }
        except Exception as e:
            logger.warning(f"tiktoken encoding failed: {e}")

    # Fallback to estimation
    return {
        "token_count": _estimate_tokens(text),
        "encoding": None,
        "method": "estimation",
        "character_count": len(text)
    }


def chunk_with_headers(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 50
) -> Dict[str, Any]:
    """
    Chunk document while preserving header context.

    This strategy keeps track of the current section hierarchy and
    includes header context in each chunk's metadata.

    Args:
        text: Markdown text to chunk
        chunk_size: Target chunk size in tokens
        chunk_overlap: Overlap between chunks

    Returns:
        Dictionary with chunks that include header context
    """
    # Parse headers and their positions
    headers = []
    header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

    for match in header_pattern.finditer(text):
        level = len(match.group(1))
        title = match.group(2).strip()
        position = match.start()
        headers.append({
            "level": level,
            "title": title,
            "position": position
        })

    # Get base chunks
    result = chunk_document(text, chunk_size, chunk_overlap, "token")

    if "error" in result:
        return result

    # Enrich chunks with header context
    for chunk in result["chunks"]:
        chunk_start = chunk["start_char"]

        # Find applicable headers
        current_headers = {}
        for header in headers:
            if header["position"] <= chunk_start:
                level = header["level"]
                # Clear lower-level headers when a higher-level header is found
                for l in range(level, 7):
                    current_headers.pop(l, None)
                current_headers[level] = header["title"]

        # Build header path
        header_path = []
        for level in sorted(current_headers.keys()):
            header_path.append(current_headers[level])

        chunk["metadata"]["header_context"] = header_path
        chunk["metadata"]["section"] = " > ".join(header_path) if header_path else "Document Root"

    result["metadata"]["chunking_strategy"] = "header_aware"

    return result


def export_for_embedding(
    chunks_result: Dict[str, Any],
    include_metadata: bool = True
) -> List[Dict[str, Any]]:
    """
    Export chunks in a format ready for embedding/vector database.

    Args:
        chunks_result: Result from chunk_document()
        include_metadata: Whether to include metadata in export

    Returns:
        List of dictionaries suitable for embedding APIs
    """
    if "error" in chunks_result:
        return []

    export = []
    for chunk in chunks_result["chunks"]:
        item = {
            "id": f"chunk_{chunk['index']}",
            "text": chunk["text"],
            "token_count": chunk["token_count"]
        }

        if include_metadata:
            item["metadata"] = {
                "index": chunk["index"],
                "char_start": chunk["start_char"],
                "char_end": chunk["end_char"],
                **chunk.get("metadata", {})
            }

        export.append(item)

    return export
