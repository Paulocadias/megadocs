"""
OpenAPI Specification Generator for MegaDoc API.
Generates Swagger documentation from Flask routes and docstrings.
"""

from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from apispec_webframeworks.flask import FlaskPlugin
from flask import jsonify, render_template, Blueprint

# Create APISpec
spec = APISpec(
    title="MegaDoc API",
    version="2.0.0",
    openapi_version="3.0.2",
    info=dict(
        description="Enterprise Document Intelligence Platform API",
        contact=dict(
            name="API Support",
            email="support@megadoc.com"
        )
    ),
    plugins=[FlaskPlugin(), MarshmallowPlugin()],
)

# Define security schemes
api_key_scheme = {"type": "apiKey", "in": "header", "name": "X-API-Key"}
spec.components.security_scheme("ApiKeyAuth", api_key_scheme)


def generate_api_spec(app):
    """
    Generate OpenAPI specification from Flask app routes.
    
    Args:
        app: Flask application instance
        
    Returns:
        dict: OpenAPI specification
    """
    with app.test_request_context():
        # Register paths from views
        for view in app.view_functions.values():
            spec.path(view=view)
            
    return spec.to_dict()


def get_swagger_ui_config():
    """
    Get Swagger UI configuration.
    
    Returns:
        dict: Swagger UI config
    """
    return {
        'app_name': "MegaDoc API Documentation",
        'dom_id': '#swagger-ui',
        'url': '/api/spec.json',
        'layout': "BaseLayout",
        'deepLinking': True
    }
