"""
Lightweight verification script for production endpoints.
Mocks heavy AI models to test routing and logic quickly.
"""

import unittest
import sys
import os
from unittest.mock import MagicMock
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

# Mock heavy dependencies BEFORE importing app
sys.modules['sentence_transformers'] = MagicMock()
sys.modules['tiktoken'] = MagicMock()
sys.modules['chromadb'] = MagicMock()
sys.modules['lancedb'] = MagicMock()

from app import create_app

class TestLightweight(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        
        with self.client.session_transaction() as sess:
            sess['admin_authenticated'] = True

    def test_observability_endpoints(self):
        """Test stats, metrics, and health."""
        endpoints = ['/health', '/metrics', '/api/stats']
        for ep in endpoints:
            response = self.client.get(ep)
            self.assertEqual(response.status_code, 200, f"Failed {ep}")

    def test_admin_dashboards(self):
        """Test admin dashboards."""
        endpoints = ['/admin/experiments', '/admin/costs']
        for ep in endpoints:
            response = self.client.get(ep)
            self.assertEqual(response.status_code, 200, f"Failed {ep}")

    def test_rag_routing(self):
        """Test RAG endpoints exist (logic mocked)."""
        # We just want to ensure the routes are registered and don't 404
        # Since we mocked the models, they might error 500 inside, but NOT 404
        
        # Token Count
        response = self.client.post('/api/token-count', json={'text': 'test'})
        self.assertNotEqual(response.status_code, 404)
        
        # Chunk
        response = self.client.post('/api/chunk', json={'text': 'test'})
        self.assertNotEqual(response.status_code, 404)
        
        # Embed
        response = self.client.post('/api/embed', json={'text': 'test'})
        self.assertNotEqual(response.status_code, 404)

if __name__ == '__main__':
    unittest.main()
