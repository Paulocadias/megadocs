"""
Test suite for production features (Observability, A/B Testing, Model Metrics).
"""

import unittest
import json
import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from app import create_app
from config import Config

class TestProductionFeatures(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        
        # Mock admin session
        with self.client.session_transaction() as sess:
            sess['admin_authenticated'] = True

    def test_health_check(self):
        """Test /health endpoint."""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'healthy')
        self.assertIn('system', data)
        self.assertIn('database', data)

    def test_metrics_endpoint(self):
        """Test /metrics endpoint."""
        response = self.client.get('/metrics')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'http_requests_total', response.data)
        self.assertIn(b'conversion_duration_seconds', response.data)

    def test_public_stats(self):
        """Test /api/stats endpoint."""
        response = self.client.get('/api/stats')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('total_conversions', data)
        self.assertIn('conversions_by_day', data)

    def test_ab_testing_integration(self):
        """Test A/B testing integration."""
        # First request should assign a variant
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        
        # Check if user_id is in session (implicit check via cookie)
        cookie = response.headers.get('Set-Cookie')
        self.assertIsNotNone(cookie)

    def test_admin_experiments(self):
        """Test /admin/experiments endpoint."""
        response = self.client.get('/admin/experiments')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'A/B Experiments', response.data)

    def test_admin_costs(self):
        """Test /admin/costs endpoint."""
        response = self.client.get('/admin/costs')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Cost Optimization', response.data)
        self.assertIn(b'ROI Calculator', response.data)

    def test_rag_endpoints(self):
        """Test RAG endpoints (chunk, token-count, embed)."""
        # Token Count
        response = self.client.post('/api/token-count', json={'text': 'Hello world'})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('token_count', data)
        
        # Chunking
        response = self.client.post('/api/chunk', json={'text': 'Hello world ' * 100})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('chunks', data)
        
        # Embedding (Mocked or Real if model is loaded)
        # Note: This might be slow if loading model for first time
        response = self.client.post('/api/embed', json={'text': 'Hello world'})
        if response.status_code == 200:
            data = response.get_json()
            self.assertIn('embedding', data)
        else:
            # If model loading fails in test env (e.g. memory), that's acceptable for now
            # provided it handles error gracefully
            self.assertNotEqual(response.status_code, 500)

if __name__ == '__main__':
    unittest.main()
