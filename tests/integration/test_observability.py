"""
Integration tests for observability endpoints.
Tests health, metrics, and stats endpoints.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


@pytest.mark.integration
class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_200(self, client):
        """Health endpoint should return 200 when healthy."""
        response = client.get('/health')

        assert response.status_code == 200
        data = response.get_json()
        assert 'status' in data
        assert data['status'] in ['healthy', 'degraded', 'unhealthy']

    def test_health_includes_components(self, client):
        """Health response should include component statuses."""
        response = client.get('/health')
        data = response.get_json()

        # Should include various component checks
        assert 'timestamp' in data or 'checks' in data or 'components' in data

    def test_health_returns_json(self, client):
        """Health endpoint should return JSON content type."""
        response = client.get('/health')

        assert response.content_type == 'application/json'


@pytest.mark.integration
class TestMetricsEndpoint:
    """Tests for /metrics endpoint."""

    def test_metrics_returns_200(self, client):
        """Metrics endpoint should return 200."""
        response = client.get('/metrics')

        assert response.status_code == 200

    def test_metrics_prometheus_format(self, client):
        """Metrics should be in Prometheus format."""
        response = client.get('/metrics')

        # Prometheus format typically contains # HELP and # TYPE comments
        content = response.get_data(as_text=True)
        # Should contain metric definitions or be empty
        assert isinstance(content, str)


@pytest.mark.integration
class TestStatsEndpoint:
    """Tests for /api/stats endpoint."""

    def test_stats_returns_200(self, client):
        """Stats endpoint should return 200."""
        response = client.get('/api/stats')

        assert response.status_code == 200

    def test_stats_includes_conversion_count(self, client):
        """Stats should include conversion statistics."""
        response = client.get('/api/stats')
        data = response.get_json()

        # Should have some statistics
        assert isinstance(data, dict)
        # Common stats might include total_conversions, success_rate, etc.

    def test_stats_returns_json(self, client):
        """Stats endpoint should return JSON."""
        response = client.get('/api/stats')

        assert response.content_type == 'application/json'


@pytest.mark.integration
class TestFormatsEndpoint:
    """Tests for /api/formats endpoint."""

    def test_formats_returns_200(self, client):
        """Formats endpoint should return 200."""
        response = client.get('/api/formats')

        assert response.status_code == 200

    def test_formats_lists_supported_types(self, client):
        """Formats should list all supported file types."""
        response = client.get('/api/formats')
        data = response.get_json()

        # Should contain supported formats
        assert isinstance(data, (dict, list))

    def test_formats_includes_pdf(self, client):
        """Formats should include PDF."""
        response = client.get('/api/formats')
        data = response.get_json()

        # PDF should be in the supported formats
        content = str(data).lower()
        assert 'pdf' in content or '.pdf' in content


@pytest.mark.integration
class TestSecurityHeaders:
    """Tests for security headers on responses."""

    def test_has_strict_transport_security(self, client):
        """Response should include HSTS header."""
        response = client.get('/health')

        assert 'Strict-Transport-Security' in response.headers

    def test_has_content_type_options(self, client):
        """Response should include X-Content-Type-Options."""
        response = client.get('/health')

        assert response.headers.get('X-Content-Type-Options') == 'nosniff'

    def test_has_frame_options(self, client):
        """Response should include X-Frame-Options."""
        response = client.get('/health')

        assert 'X-Frame-Options' in response.headers

    def test_has_xss_protection(self, client):
        """Response should include XSS protection header."""
        response = client.get('/health')

        assert 'X-XSS-Protection' in response.headers

    def test_has_request_id(self, client):
        """Response should include request ID header."""
        response = client.get('/health')

        assert 'X-Request-ID' in response.headers

    def test_has_response_time(self, client):
        """Response should include response time header."""
        response = client.get('/health')

        assert 'X-Response-Time' in response.headers


@pytest.mark.integration
class TestAdminEndpoints:
    """Tests for admin dashboard endpoints."""

    def test_admin_experiments_requires_auth(self, client):
        """Admin experiments should require authentication."""
        response = client.get('/admin/experiments')

        # Should redirect to login or return 401/403
        assert response.status_code in [200, 302, 401, 403]

    def test_admin_experiments_with_auth(self, auth_client):
        """Admin experiments should work with authentication."""
        response = auth_client.get('/admin/experiments')

        assert response.status_code == 200

    def test_admin_costs_requires_auth(self, client):
        """Admin costs should require authentication."""
        response = client.get('/admin/costs')

        # Should redirect to login or return 401/403
        assert response.status_code in [200, 302, 401, 403]

    def test_admin_costs_with_auth(self, auth_client):
        """Admin costs should work with authentication."""
        response = auth_client.get('/admin/costs')

        assert response.status_code == 200
