"""
Build Knowledge Base for MegaDoc Assistant
Embeds all documentation into vectors for RAG retrieval
"""

import os
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from chunker import chunk_document
from embedder import generate_embeddings_batch

def find_docs(base_path: str) -> list[str]:
    """Find all markdown files for embedding"""
    docs = []
    exclude_dirs = {'.pytest_cache', 'venv', 'node_modules', '__pycache__', '.git'}

    for root, dirs, files in os.walk(base_path):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            if file.endswith('.md'):
                docs.append(os.path.join(root, file))

    return docs

def build_knowledge_base(output_path: str = "data/knowledge_base.jsonl"):
    """Build knowledge base from all documentation"""
    base_path = Path(__file__).parent.parent
    docs = find_docs(str(base_path))

    print(f"Found {len(docs)} documentation files")

    all_chunks = []

    for doc_path in docs:
        rel_path = os.path.relpath(doc_path, base_path)
        print(f"Processing: {rel_path}")

        try:
            with open(doc_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if not content.strip():
                print(f"  Skipping empty file")
                continue

            # Chunk the document
            result = chunk_document(content, chunk_size=500, chunk_overlap=50)

            if result.get("error"):
                print(f"  Error chunking: {result['error']}")
                continue

            chunks = result.get("chunks", [])
            print(f"  Created {len(chunks)} chunks")

            for i, chunk in enumerate(chunks):
                all_chunks.append({
                    "source": rel_path,
                    "chunk_id": i,
                    "content": chunk["content"],
                    "char_count": chunk.get("char_count", len(chunk["content"]))
                })

        except Exception as e:
            print(f"  Error: {e}")
            continue

    print(f"\nTotal chunks: {len(all_chunks)}")
    print("Generating embeddings (this may take a moment)...")

    # Generate embeddings for all chunks
    texts = [c["content"] for c in all_chunks]
    embeddings_results = generate_embeddings_batch(texts)

    print(f"Generated {len(embeddings_results)} embeddings")

    # Combine chunks with embeddings
    output_data = []
    for i, chunk in enumerate(all_chunks):
        if i < len(embeddings_results):
            chunk["embedding"] = embeddings_results[i].get("embedding", [])
            chunk["embedding_model"] = embeddings_results[i].get("model", "unknown")
        else:
            chunk["embedding"] = []
        output_data.append(chunk)

    # Ensure data directory exists
    output_file = base_path / output_path
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Save as JSONL
    with open(output_file, 'w', encoding='utf-8') as f:
        for item in output_data:
            f.write(json.dumps(item) + '\n')

    print(f"\nKnowledge base saved to: {output_path}")
    print(f"Total entries: {len(output_data)}")

    # Also save a summary
    embedding_dim = len(embeddings_results[0].get("embedding", [])) if embeddings_results else 0
    summary = {
        "total_docs": len(docs),
        "total_chunks": len(output_data),
        "embedding_dim": embedding_dim,
        "embedding_model": embeddings_results[0].get("model", "unknown") if embeddings_results else "none",
        "sources": list(set(c["source"] for c in output_data))
    }

    summary_file = output_file.parent / "knowledge_base_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    print(f"Summary saved to: {summary_file.name}")

    return output_data

if __name__ == "__main__":
    build_knowledge_base()
