import os
import hashlib
import tempfile
import logging
import shutil
import requests
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify, session, send_file, current_app

from config import Config
from stats import stats
from converter import DocumentConverter
from security import (
    security_check, get_client_ip, check_capacity, acquire_conversion_slot,
    release_conversion_slot, get_active_conversions
)
from utils import (
    sanitize_filename, markdown_to_text, remove_macros, 
    strip_metadata, redact_emails, format_as_json, format_as_xml
)
from batch_service import BatchService
from webhook_service import WebhookService
from analyzer import analyze_document
from chunker import chunk_document, chunk_with_headers, export_for_embedding, get_token_count
from embedder import (
    generate_embedding, generate_embeddings_batch, embed_chunks,
    export_for_chromadb, export_for_lancedb, export_jsonl, get_embedding_info
)
from openrouter_gateway import chat_completion, analyze_image, image_to_text_description
from memory_store import get_memory_store
from assistant import ask_assistant
import threading

logger = logging.getLogger(__name__)
bp = Blueprint('main', __name__)
converter = DocumentConverter()
batch_service = BatchService()
webhook_service = WebhookService()

# =============================================================================
# MIDDLEWARE
# =============================================================================

@bp.before_app_request
def before_request():
    """Pre-request security checks."""
    from security import generate_request_id
    import time
    # Generate request ID
    request.request_id = generate_request_id()
    request.start_time = time.time()


@bp.after_app_request
def after_request(response):
    """Add security headers to all responses."""
    import time
    # Security headers
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "connect-src 'self' https://cdn.jsdelivr.net; "
        "img-src 'self' data:; "
        "font-src 'self' https://fonts.gstatic.com https://r2cdn.perplexity.ai; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    )

    # Request tracking
    if hasattr(request, 'request_id'):
        response.headers["X-Request-ID"] = request.request_id

    # Response time tracking
    if hasattr(request, 'start_time'):
        elapsed = time.time() - request.start_time
        response.headers["X-Response-Time"] = f"{elapsed:.3f}s"

    # Remove server header
    response.headers.pop("Server", None)

    return response


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@bp.app_errorhandler(400)
def bad_request(error):
    return jsonify({"error": "Bad request", "request_id": getattr(request, 'request_id', 'UNKNOWN')}), 400


@bp.app_errorhandler(403)
def forbidden(error):
    return jsonify({"error": "Forbidden", "request_id": getattr(request, 'request_id', 'UNKNOWN')}), 403


@bp.app_errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found", "request_id": getattr(request, 'request_id', 'UNKNOWN')}), 404


@bp.app_errorhandler(413)
def request_entity_too_large(error):
    max_mb = Config.MAX_CONTENT_LENGTH // (1024 * 1024)
    return jsonify({
        "error": f"File too large. Maximum size is {max_mb}MB",
        "request_id": getattr(request, 'request_id', 'UNKNOWN')
    }), 413


@bp.app_errorhandler(429)
def rate_limit_exceeded(error):
    return jsonify({
        "error": "Rate limit exceeded. Please try again later.",
        "request_id": getattr(request, 'request_id', 'UNKNOWN')
    }), 429


@bp.app_errorhandler(500)
def internal_error(error):
    return jsonify({
        "error": "Internal server error",
        "request_id": getattr(request, 'request_id', 'UNKNOWN')
    }), 500


# =============================================================================
# ROUTES
# =============================================================================

@bp.route("/health")
def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    Returns comprehensive system health status.
    """
    from health import get_health_status
    
    health_data = get_health_status()
    status_code = 200 if health_data["status"] == "healthy" else 503
    
    return jsonify(health_data), status_code

    
    health_data = get_health_status()
    status_code = 200 if health_data["status"] == "healthy" else 503
    
    return jsonify(health_data), status_code


@bp.before_app_request
def ab_testing_middleware():
    """Ensure user has an ID for A/B testing."""
    if 'user_id' not in session:
        session['user_id'] = hashlib.sha256(os.urandom(32)).hexdigest()[:16]





@bp.route("/api/stats")
def public_stats():
    """
    Public statistics endpoint - no authentication required.
    Shows system transparency and usage metrics.
    """
    from stats import stats
    
    return jsonify(stats.get_api_stats())


@bp.route("/metrics")
def metrics():
    """
    Prometheus metrics endpoint for monitoring systems.
    Returns metrics in Prometheus text format.
    """
    from metrics import get_metrics
    
    metrics_data, content_type = get_metrics()
    return metrics_data, 200, {'Content-Type': content_type}


@bp.route("/stats")
def stats_page():
    """Render the public statistics page."""
    return render_template("stats.html", active_page='stats')


@bp.route("/api/spec.json")
def api_spec():
    """Serve OpenAPI specification."""
    from api_spec import generate_api_spec
    from flask import current_app
    return jsonify(generate_api_spec(current_app))


@bp.route("/api/swagger")
def swagger_ui():
    """Render Swagger UI."""
    return render_template("swagger.html")


@bp.route("/")
def landing():
    """Render the landing page - portfolio showcase."""
    from ab_testing import experiments
    
    # Example Experiment: New Hero Text
    # Ensure experiment exists (idempotent)
    if "hero_text_v2" not in experiments._experiments:
        experiments.create_experiment(
            id="hero_text_v2",
            name="Hero Text Optimization",
            description="Testing new hero text for better conversion",
            variants=["control", "variant_a"]
        )
    
    user_id = session.get('user_id', 'unknown')
    variant = experiments.get_assignment("hero_text_v2", user_id)
    
    return render_template("landing.html", experiment_variant=variant)


@bp.route("/convert")
def converter_page():
    """Render the converter upload page with CSRF token."""
    max_size_mb = Config.MAX_CONTENT_LENGTH // (1024 * 1024)

    # Generate CSRF token
    if 'csrf_token' not in session:
        session['csrf_token'] = hashlib.sha256(os.urandom(32)).hexdigest()

    return render_template(
        "index.html",
        extensions=sorted(Config.ALLOWED_EXTENSIONS),
        max_size_mb=max_size_mb,
        rate_limit=Config.RATE_LIMIT_REQUESTS,
        csrf_token=session['csrf_token'],
        active_page='convert'
    )


@bp.route("/use-cases")
def use_cases():
    """Render the business use cases page."""
    return render_template("use_cases.html", active_page='use-cases')


@bp.route("/mcp")
def mcp_docs():
    """Render the MCP integration documentation page."""
    return render_template("mcp.html")


@bp.route("/contact", methods=["GET"])
def contact_page():
    """Render the contact form page."""
    # Generate CSRF token
    if 'csrf_token' not in session:
        session['csrf_token'] = hashlib.sha256(os.urandom(32)).hexdigest()
    
    return render_template("contact.html", csrf_token=session['csrf_token'], active_page='contact')


@bp.route("/contact", methods=["POST"])
@security_check
def submit_contact():
    """Handle contact form submission and send email via Brevo SMTP."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from datetime import datetime
    
    request_id = getattr(request, 'request_id', 'UNKNOWN')
    ip = get_client_ip()
    
    # CSRF validation
    csrf_token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
    if not csrf_token or csrf_token != session.get('csrf_token'):
        logger.warning(f"CSRF validation failed on contact form from {ip}", extra={'request_id': request_id})
        return jsonify({"error": "Invalid request token. Please refresh the page.", "request_id": request_id}), 403
    
    # Honeypot check (bot detection)
    if request.form.get('website'):
        logger.warning(f"Bot detected on contact form from {ip}", extra={'request_id': request_id})
        return jsonify({"error": "Invalid request.", "request_id": request_id}), 400
    
    # Get form data
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    company = request.form.get('company', '').strip()
    use_case = request.form.get('use_case', '').strip()
    message = request.form.get('message', '').strip()
    
    # Validation
    if not name or not email or not use_case:
        return jsonify({"error": "Please fill in all required fields.", "request_id": request_id}), 400
    
    # Basic email validation
    if '@' not in email or '.' not in email:
        return jsonify({"error": "Please provide a valid email address.", "request_id": request_id}), 400
    
    try:
        # Try to import email config
        try:
            from email_config import CONTACT_EMAIL, SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_SENDER
            email_configured = (SMTP_PASSWORD and SMTP_PASSWORD != "your-brevo-smtp-key-here")
        except ImportError:
            email_configured = False
            logger.warning("Email configuration not found. Please set up email_config.py")
        
        # Prepare email content
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        email_body = f"""
New API Access Request - MegaDoc

Timestamp: {timestamp}
Request ID: {request_id}
IP Address: {ip}

--- Contact Information ---
Name: {name}
Email: {email}
Company: {company or 'Not provided'}

--- Request Details ---
Use Case: {use_case}

Additional Details:
{message or 'No additional details provided'}

---
This is an automated message from the MegaDoc contact form.
Reply directly to this email to respond to {name}.
"""
        
        if email_configured:
            try:
                # Send email via Brevo SMTP
                msg = MIMEMultipart()
                msg['From'] = f"MegaDoc Contact Form <{SMTP_SENDER}>"
                msg['To'] = CONTACT_EMAIL
                msg['Subject'] = f"MegaDoc API Request - {name}"
                msg['Reply-To'] = email
                
                msg.attach(MIMEText(email_body, 'plain'))
                
                # Connect and send
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                    server.starttls()
                    server.login(SMTP_USERNAME, SMTP_PASSWORD)
                    server.send_message(msg)
                
                logger.info(f"Contact form email sent to {CONTACT_EMAIL} from {email}", extra={'request_id': request_id})
            except Exception as e:
                logger.error(f"Failed to send email: {str(e)}", extra={'request_id': request_id})
                # Fall back to console logging
                logger.info(f"Contact form submission (email failed):\n{email_body}", extra={'request_id': request_id})
        else:
            # Log to console if email not configured
            logger.info(f"""
╔══════════════════════════════════════════════════════════════╗
║              NEW CONTACT FORM SUBMISSION                      ║
╠══════════════════════════════════════════════════════════════╣
║ Timestamp: {timestamp}
║ Request ID: {request_id}
║ IP Address: {ip}
║ 
║ Name: {name}
║ Email: {email}
║ Company: {company or 'Not provided'}
║ Use Case: {use_case}
║ 
║ Message:
║ {message or 'No additional details provided'}
╚══════════════════════════════════════════════════════════════╝
            """, extra={'request_id': request_id})
        
        return jsonify({
            "success": True,
            "message": "Thank you! Your request has been submitted successfully. We'll get back to you soon.",
            "request_id": request_id
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing contact form: {str(e)}", extra={'request_id': request_id})
        return jsonify({
            "error": "Failed to submit request. Please try again later.",
            "request_id": request_id
        }), 500


@bp.route("/convert", methods=["POST"])
@security_check
def convert_file():
    """Convert uploaded file to Markdown with full security validation."""
    request_id = getattr(request, 'request_id', 'UNKNOWN')
    ip = get_client_ip()

    # CSRF validation
    csrf_token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
    if not csrf_token or csrf_token != session.get('csrf_token'):
        logger.warning(f"CSRF validation failed from {ip}", extra={'request_id': request_id})
        return jsonify({"error": "Invalid request token. Please refresh the page.", "request_id": request_id}), 403

    # Capacity check - prevent system overload
    allowed, active_count = check_capacity()
    if not allowed:
        stats.record_capacity_exceeded(ip, active_count)
        logger.warning(f"System over capacity ({active_count}/{Config.MAX_CONCURRENT_CONVERSIONS}) for {ip}", extra={'request_id': request_id})
        return jsonify({
            "error": "System is currently at maximum capacity. Please try again in a few moments.",
            "active_conversions": active_count,
            "max_capacity": Config.MAX_CONCURRENT_CONVERSIONS,
            "request_id": request_id
        }), 503

    # File presence check
    if "file" not in request.files:
        return jsonify({"error": "No file provided", "request_id": request_id}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected", "request_id": request_id}), 400

    # Sanitize and validate filename
    filename = sanitize_filename(file.filename)
    if not filename:
        logger.warning(f"Invalid filename attempted from {ip}: {file.filename}", extra={'request_id': request_id})
        return jsonify({"error": "Invalid filename", "request_id": request_id}), 400

    # Extension validation
    ext = Path(filename).suffix.lower()
    if ext not in Config.ALLOWED_EXTENSIONS:
        logger.warning(f"Blocked extension {ext} from {ip}", extra={'request_id': request_id})
        return jsonify({
            "error": f"File type '{ext}' not supported.",
            "allowed": sorted(Config.ALLOWED_EXTENSIONS),
            "request_id": request_id
        }), 400

    # STRICT FILE SIZE CHECK - Check Content-Length header first
    max_size = Config.MAX_CONTENT_LENGTH
    max_mb = max_size // (1024 * 1024)
    content_length = request.content_length
    if content_length and content_length > max_size:
        logger.warning(f"File size rejected (Content-Length: {content_length} bytes) from {ip}", extra={'request_id': request_id})
        return jsonify({
            "error": f"File too large. Maximum size is {max_mb}MB. Your file is {content_length / (1024*1024):.1f}MB.",
            "request_id": request_id
        }), 413

    # Read file content for magic byte validation
    file_content = file.read()
    file.seek(0)  # Reset for saving

    # STRICT FILE SIZE CHECK - Verify actual file size after reading
    actual_size = len(file_content)
    if actual_size > max_size:
        logger.warning(f"File size rejected (actual: {actual_size} bytes, max: {max_size}) from {ip}", extra={'request_id': request_id})
        return jsonify({
            "error": f"File too large. Maximum size is {max_mb}MB. Your file is {actual_size / (1024*1024):.1f}MB.",
            "request_id": request_id
        }), 413

    # Magic byte validation (moved to security.py but called here via validate_file_magic if needed, 
    # but we extracted it to security.py so we should import it if we want to use it explicitly, 
    # or rely on the fact that we already validated extension. 
    # Wait, I moved validate_file_magic to security.py. I need to import it.)
    from security import validate_file_magic
    if not validate_file_magic(file_content, ext):
        logger.warning(
            f"Magic byte mismatch from {ip}: claimed {ext}, content doesn't match",
            extra={'request_id': request_id}
        )
        return jsonify({
            "error": "File content doesn't match file extension. Possible file tampering detected.",
            "request_id": request_id
        }), 400

    # Get output format (default to markdown)
    output_format = request.form.get('output_format', 'markdown')
    if output_format not in ('markdown', 'text'):
        output_format = 'markdown'

    # Process file - acquire conversion slot
    if not acquire_conversion_slot():
        # Double-check capacity (race condition protection)
        stats.record_capacity_exceeded(ip, get_active_conversions())
        return jsonify({
            "error": "System is currently at maximum capacity. Please try again in a few moments.",
            "request_id": request_id
        }), 503

    # Set output file extension and mimetype based on format
    if output_format == 'text':
        output_ext = '.txt'
        output_mimetype = 'text/plain'
    else:
        output_ext = '.md'
        output_mimetype = 'text/markdown'

    temp_dir = tempfile.mkdtemp()
    temp_input = Path(temp_dir) / filename
    temp_output = Path(temp_dir) / f"{Path(filename).stem}{output_ext}"

    try:
        # Save with restricted permissions
        temp_input.write_bytes(file_content)

        logger.info(
            f"Converting: {filename} ({len(file_content)} bytes) -> {output_format} from {ip} [Active: {get_active_conversions()}/{Config.MAX_CONCURRENT_CONVERSIONS}]",
            extra={'request_id': request_id}
        )

        # Step 1: Convert to Markdown first
        markdown_content = converter.convert_to_string(temp_input)

        # Step 2: If text format requested, convert markdown to plain text
        if output_format == 'text':
            final_content = markdown_to_text(markdown_content)
        else:
            final_content = markdown_content

        temp_output.write_text(final_content, encoding="utf-8")

        # Release slot after conversion is done
        release_conversion_slot()

        # Prepare response
        response = send_file(
            str(temp_output),
            mimetype=output_mimetype,
            as_attachment=True,
            download_name=f"{Path(filename).stem}{output_ext}",
        )

        # Cleanup callback
        @response.call_on_close
        def cleanup():
            try:
                temp_input.unlink(missing_ok=True)
                temp_output.unlink(missing_ok=True)
                Path(temp_dir).rmdir()
                logger.info(f"Cleanup completed for {filename}", extra={'request_id': request_id})
            except Exception as e:
                logger.warning(f"Cleanup error: {e}", extra={'request_id': request_id})

        logger.info(f"Conversion successful: {filename}", extra={'request_id': request_id})
        stats.record_conversion(ext, len(file_content), ip)
        return response

    except Exception as e:
        logger.error(f"Conversion error: {e}", extra={'request_id': request_id})
        stats.record_error("conversion", str(e))
        release_conversion_slot()  # Release slot on error
        # Cleanup on error
        try:
            temp_input.unlink(missing_ok=True)
            temp_output.unlink(missing_ok=True)
            Path(temp_dir).rmdir()
        except Exception:
            pass
        return jsonify({"error": "Conversion failed. Please try a different file.", "request_id": request_id}), 500


@bp.route("/api/convert", methods=["POST"])
@security_check
def api_convert():
    """API endpoint with security validation and concurrency control."""
    request_id = getattr(request, 'request_id', 'UNKNOWN')
    ip = get_client_ip()

    # API key validation (optional - for future use)
    api_key = request.headers.get('X-API-Key')

    # Capacity check - prevent system overload
    allowed, active_count = check_capacity()
    if not allowed:
        stats.record_capacity_exceeded(ip, active_count)
        logger.warning(f"API: System over capacity ({active_count}/{Config.MAX_CONCURRENT_CONVERSIONS}) for {ip}", extra={'request_id': request_id})
        return jsonify({
            "error": "System is currently at maximum capacity. Please try again in a few moments.",
            "active_conversions": active_count,
            "max_capacity": Config.MAX_CONCURRENT_CONVERSIONS,
            "request_id": request_id
        }), 503

    if "file" not in request.files:
        return jsonify({"error": "No file provided", "request_id": request_id}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected", "request_id": request_id}), 400

    filename = sanitize_filename(file.filename)
    if not filename:
        return jsonify({"error": "Invalid filename", "request_id": request_id}), 400

    ext = Path(filename).suffix.lower()
    if ext not in Config.ALLOWED_EXTENSIONS:
        return jsonify({"error": "File type not supported", "request_id": request_id}), 400

    # STRICT FILE SIZE CHECK - Check Content-Length header first
    max_size = Config.MAX_CONTENT_LENGTH
    max_mb = max_size // (1024 * 1024)
    content_length = request.content_length
    if content_length and content_length > max_size:
        logger.warning(f"API: File size rejected (Content-Length: {content_length} bytes) from {ip}", extra={'request_id': request_id})
        return jsonify({
            "error": f"File too large. Maximum size is {max_mb}MB.",
            "request_id": request_id
        }), 413

    file_content = file.read()

    # STRICT FILE SIZE CHECK - Verify actual file size after reading
    actual_size = len(file_content)
    if actual_size > max_size:
        logger.warning(f"API: File size rejected (actual: {actual_size} bytes, max: {max_size}) from {ip}", extra={'request_id': request_id})
        return jsonify({
            "error": f"File too large. Maximum size is {max_mb}MB. Your file is {actual_size / (1024*1024):.1f}MB.",
            "request_id": request_id
        }), 413

    from security import validate_file_magic
    if not validate_file_magic(file_content, ext):
        return jsonify({"error": "File content validation failed", "request_id": request_id}), 400

    # Get output format (default to markdown)
    output_format = request.form.get('output_format', 'markdown')
    if output_format not in ('markdown', 'text', 'json', 'xml'):
        output_format = 'markdown'
    
    # Get sanitization options
    remove_macros_flag = request.form.get('remove_macros', 'false').lower() == 'true'
    strip_metadata_flag = request.form.get('strip_metadata', 'false').lower() == 'true'
    redact_emails_flag = request.form.get('redact_emails', 'false').lower() == 'true'

    # Acquire conversion slot
    if not acquire_conversion_slot():
        stats.record_capacity_exceeded(ip, get_active_conversions())
        return jsonify({
            "error": "System is currently at maximum capacity. Please try again in a few moments.",
            "request_id": request_id
        }), 503

    # Set output file extension based on format
    if output_format == 'text':
        output_ext = '.txt'
    elif output_format == 'json':
        output_ext = '.json'
    elif output_format == 'xml':
        output_ext = '.xml'
    else:
        output_ext = '.md'

    temp_dir = tempfile.mkdtemp()
    temp_input = Path(temp_dir) / filename

    import time
    start_time = time.time()
    success = False
    error_msg = None

    try:
        temp_input.write_bytes(file_content)
        logger.info(f"API conversion: {filename} -> {output_format} from {ip} [Active: {get_active_conversions()}/{Config.MAX_CONCURRENT_CONVERSIONS}]", extra={'request_id': request_id})

        # Check if file is an image - use unified multi-modal pipeline
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}
        is_image = ext in image_extensions
        source_type = 'image' if is_image else 'document'
        
        if is_image:
            # Step 1: Convert image to text description using Vision AI
            import base64
            import mimetypes
            
            # Determine MIME type
            mime_type = mimetypes.guess_type(filename)[0] or 'image/jpeg'
            if ext == '.png':
                mime_type = 'image/png'
            elif ext == '.gif':
                mime_type = 'image/gif'
            elif ext == '.bmp':
                mime_type = 'image/bmp'
            
            # Convert to base64 data URI
            image_base64 = base64.b64encode(file_content).decode('utf-8')
            image_data_uri = f"data:{mime_type};base64,{image_base64}"
            
            # Generate AI description for RAG indexing
            logger.info(f"Converting image to text description for RAG indexing: {filename}", extra={'request_id': request_id})
            try:
                # image_to_text_description returns a string (the description text)
                markdown_content = image_to_text_description(image_data_uri)
                if not markdown_content or not markdown_content.strip():
                    raise ValueError("AI failed to generate image description")
                # Keep image_data_uri for memory store (don't store in session - too large!)
                logger.info(f"Image description generated: {len(markdown_content)} chars", extra={'request_id': request_id})
            except requests.exceptions.HTTPError as e:
                # Handle rate limit (429) specially
                if "Rate limit" in str(e) or (hasattr(e, 'response') and e.response and e.response.status_code == 429):
                    logger.warning(f"Rate limit hit for image description: {e}", extra={'request_id': request_id})
                    release_conversion_slot()
                    return jsonify({
                        "error": "Queue Full",
                        "message": "Rate limit exceeded. Please wait a few seconds and try again.",
                        "retry_after": 3,
                        "request_id": request_id
                    }), 429
                logger.error(f"Image description generation failed: {e}", extra={'request_id': request_id})
                raise ValueError(f"Failed to generate image description: {str(e)}")
            except Exception as e:
                logger.error(f"Image description generation failed: {e}", extra={'request_id': request_id})
                raise ValueError(f"Failed to generate image description: {str(e)}")
        else:
            # Step 1: Convert document to Markdown (traditional path)
            markdown_content = converter.convert_to_string(temp_input)

        # Step 2: Apply sanitization options (only for documents, images already processed)
        if not is_image:
            if remove_macros_flag:
                markdown_content = remove_macros(markdown_content)
            if strip_metadata_flag:
                markdown_content = strip_metadata(markdown_content)
            if redact_emails_flag:
                markdown_content = redact_emails(markdown_content)

        # Step 3: Format output based on requested format
        if output_format == 'text':
            final_content = markdown_to_text(markdown_content)
        elif output_format == 'json':
            final_content = format_as_json(markdown_content, Path(filename).stem)
        elif output_format == 'xml':
            final_content = format_as_xml(markdown_content, Path(filename).stem)
        else:
            final_content = markdown_content

        release_conversion_slot()
        stats.record_conversion(ext, len(file_content), ip)
        success = True

        # Use server-side memory store (not session cookies - avoids 4KB limit)
        memory_store = get_memory_store()
        session_id = session.get('user_id')
        if not session_id:
            session_id = hashlib.sha256(os.urandom(32)).hexdigest()[:16]
            session['user_id'] = session_id

        # image_data_uri is already set above for images (local variable, not session)
        # For non-images, set to None
        if not is_image:
            image_data_uri = None

        # Add to server-side memory store
        memory_store.add_item(
            session_id=session_id,
            filename=filename,
            content=final_content,
            doc_type=source_type,
            doc_format=output_format,
            image_data_uri=image_data_uri
        )

        # Get current memory count
        memory_count = memory_store.get_item_count(session_id)
        logger.info(f"Added to memory: {filename} (Total items: {memory_count})", extra={'request_id': request_id})

        return jsonify({
            "success": True,
            "filename": f"{Path(filename).stem}{output_ext}",
            "content": final_content,
            "format": output_format,
            "source_type": source_type,
            "memory_count": memory_count,
            "request_id": request_id
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"API conversion error: {e}", extra={'request_id': request_id})
        release_conversion_slot()
        stats.record_error("api_conversion", error_msg)
        return jsonify({"error": str(e), "request_id": request_id}), 500

    finally:
        # Track analytics
        try:
            duration = time.time() - start_time
            from analytics import analytics
            from ab_testing import experiments
            
            analytics.track_conversion(
                file_type=ext,
                size=len(file_content),
                duration=duration,
                success=success,
                error=error_msg
            )
            
            # Track A/B Test Metric (if successful)
            if success:
                user_id = session.get('user_id', 'unknown')
                variant = experiments.get_assignment("hero_text_v2", user_id)
                experiments.track_metric("hero_text_v2", variant, "conversions")
                
        except Exception as e:
            logger.error(f"Analytics/AB error: {e}")

        try:
            temp_input.unlink(missing_ok=True)
            Path(temp_dir).rmdir()
        except Exception:
            pass





@bp.route("/api/batch/convert", methods=["POST"])
@security_check
def api_batch_convert():
    """Batch convert ZIP file containing documents."""
    request_id = getattr(request, 'request_id', 'UNKNOWN')
    ip = get_client_ip()

    if "file" not in request.files:
        return jsonify({"error": "No file provided", "request_id": request_id}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected", "request_id": request_id}), 400

    filename = sanitize_filename(file.filename)
    if not filename.lower().endswith('.zip'):
        return jsonify({"error": "Only ZIP files are allowed for batch processing", "request_id": request_id}), 400

    # Check capacity (batch jobs count as 1 active conversion for now, or maybe more?)
    # For simplicity, we treat it as 1 slot but it consumes more resources.
    if not acquire_conversion_slot():
        return jsonify({"error": "System busy", "request_id": request_id}), 503



    temp_dir = tempfile.mkdtemp()
    temp_input = Path(temp_dir) / filename

    try:
        file.save(temp_input)
        logger.info(f"Batch conversion started: {filename} from {ip}", extra={'request_id': request_id})

        output_format = request.form.get('output_format', 'markdown')
        webhook_url = request.form.get('webhook_url')

        if webhook_url:
            # Async processing
            def process_async():
                try:
                    output_zip = batch_service.process_zip(temp_input, output_format)
                    stats.record_conversion('.zip', file.content_length or 0, ip)
                    
                    # Send webhook
                    with open(output_zip, 'rb') as f:
                        files = {'file': (f"converted_{Path(filename).stem}.zip", f, 'application/zip')}
                        try:
                            requests.post(webhook_url, files=files, timeout=30)
                            logger.info(f"Webhook sent to {webhook_url}", extra={'request_id': request_id})
                        except Exception as e:
                            logger.error(f"Webhook failed: {e}", extra={'request_id': request_id})
                    
                    # Cleanup
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    logger.error(f"Async batch error: {e}", extra={'request_id': request_id})
                    shutil.rmtree(temp_dir, ignore_errors=True)

            threading.Thread(target=process_async).start()
            
            return jsonify({
                "message": "Batch processing started. Result will be sent to webhook.",
                "request_id": request_id,
                "status": "accepted"
            }), 202

        # Sync processing
        output_zip = batch_service.process_zip(temp_input, output_format)

        release_conversion_slot()
        stats.record_conversion('.zip', file.content_length or 0, ip)

        # Return result
        response = send_file(
            str(output_zip),
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"converted_{Path(filename).stem}.zip"
        )

        @response.call_on_close
        def cleanup():
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.info(f"Batch cleanup completed for {filename}", extra={'request_id': request_id})
            except Exception as e:
                logger.warning(f"Batch cleanup error: {e}", extra={'request_id': request_id})

        return response

    except Exception as e:
        logger.error(f"Batch conversion error: {e}", extra={'request_id': request_id})
        release_conversion_slot()
        stats.record_error("batch_conversion", str(e))
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"error": str(e), "request_id": request_id}), 500


@bp.route("/health")
def health():
    """Health check endpoint."""
    from datetime import datetime
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })


@bp.route("/security-info")
def security_info():
    """Display security features (for demonstration)."""
    return jsonify({
        "security_features": [
            "Rate limiting (IP-based)",
            "File size limits",
            "File type validation (extension + magic bytes)",
            "CSRF protection",
            "Security headers (CSP, X-Frame-Options, etc.)",
            "Request ID tracking",
            "Honeypot bot detection",
            "Input sanitization",
            "Automatic IP blocking for abuse",
            "Secure file handling",
            "Automatic file cleanup"
        ],
        "limits": {
            "max_file_size_mb": Config.MAX_CONTENT_LENGTH // (1024 * 1024),
            "rate_limit_requests": Config.RATE_LIMIT_REQUESTS,
            "rate_limit_window_seconds": Config.RATE_LIMIT_WINDOW
        },
        "headers": [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Content-Security-Policy",
            "Referrer-Policy",
            "Permissions-Policy",
            "X-Request-ID",
            "X-Response-Time"
        ]
    })





@bp.route("/api/docs")
def api_docs():
    """API documentation page."""
    base_url = request.url_root.rstrip('/')
    return render_template("api-docs.html", base_url=base_url, active_page='api')


# Note: /api/stats route is defined earlier at public_stats()

@bp.route("/api/formats")
def api_formats():
    """List supported file formats."""
    return jsonify({
        "formats": sorted(Config.ALLOWED_EXTENSIONS),
        "max_file_size_mb": Config.MAX_CONTENT_LENGTH // (1024 * 1024),
        "rate_limit": {
            "requests": Config.RATE_LIMIT_REQUESTS,
            "window_seconds": Config.RATE_LIMIT_WINDOW
        }
    })


# =============================================================================
# DOCUMENT ANALYSIS & CHUNKING API
# =============================================================================

@bp.route("/api/analyze", methods=["POST"])
@security_check
def api_analyze():
    """
    Analyze document content (markdown).

    Accepts either:
    - File upload (converts to markdown first, then analyzes)
    - Raw markdown content in 'content' field

    Returns comprehensive analysis including:
    - Word/character/sentence counts
    - Reading time estimation
    - TF-IDF keywords
    - Readability scores (Flesch-Kincaid, etc.)
    - Language detection
    - Document structure analysis
    """
    request_id = getattr(request, 'request_id', 'UNKNOWN')
    ip = get_client_ip()

    try:
        markdown_content = None

        # Check if file was uploaded
        if "file" in request.files and request.files["file"].filename:
            file = request.files["file"]
            filename = sanitize_filename(file.filename)

            if not filename:
                return jsonify({"error": "Invalid filename", "request_id": request_id}), 400

            ext = Path(filename).suffix.lower()
            if ext not in Config.ALLOWED_EXTENSIONS:
                return jsonify({"error": "File type not supported", "request_id": request_id}), 400

            # Read and validate file
            file_content = file.read()
            max_size = Config.MAX_CONTENT_LENGTH
            if len(file_content) > max_size:
                return jsonify({"error": "File too large", "request_id": request_id}), 413

            from security import validate_file_magic
            if not validate_file_magic(file_content, ext):
                return jsonify({"error": "File content validation failed", "request_id": request_id}), 400

            # Convert to markdown first
            temp_dir = tempfile.mkdtemp()
            temp_input = Path(temp_dir) / filename

            try:
                temp_input.write_bytes(file_content)
                markdown_content = converter.convert_to_string(temp_input)
            finally:
                temp_input.unlink(missing_ok=True)
                Path(temp_dir).rmdir()

        # Or check for raw content
        elif request.is_json and request.json.get('content'):
            markdown_content = request.json['content']
        elif request.form.get('content'):
            markdown_content = request.form['content']
        else:
            return jsonify({
                "error": "No content provided. Upload a file or send 'content' field.",
                "request_id": request_id
            }), 400

        # Perform analysis
        analysis = analyze_document(markdown_content)

        if "error" in analysis:
            return jsonify({"error": analysis["error"], "request_id": request_id}), 400

        # Record stats
        stats.record_analyze(ip)
        logger.info(f"Document analyzed from {ip}", extra={'request_id': request_id})

        return jsonify({
            "success": True,
            "analysis": analysis,
            "request_id": request_id
        })

    except Exception as e:
        logger.error(f"Analysis error: {e}", extra={'request_id': request_id})
        stats.record_error("analysis", str(e))
        return jsonify({"error": "Analysis failed", "request_id": request_id}), 500


@bp.route("/api/chunk", methods=["POST"])
@security_check
def api_chunk():
    """
    Chunk document for RAG pipeline integration.

    Accepts either:
    - File upload (converts to markdown first, then chunks)
    - Raw markdown content in 'content' field

    Parameters (optional):
    - chunk_size: Target chunk size in tokens (default: 512, range: 64-8192)
    - chunk_overlap: Overlap between chunks (default: 50, range: 0 to chunk_size/2)
    - strategy: "token" (tiktoken-based) or "character" (fallback)
    - preserve_headers: true/false - Include header context in chunks
    - export_format: "full" (default) or "embedding" (simplified for vector DBs)

    Returns:
    - Array of chunks with text, token counts, and metadata
    - Chunking statistics
    """
    request_id = getattr(request, 'request_id', 'UNKNOWN')
    ip = get_client_ip()

    try:
        markdown_content = None

        # Check if file was uploaded
        if "file" in request.files and request.files["file"].filename:
            file = request.files["file"]
            filename = sanitize_filename(file.filename)

            if not filename:
                return jsonify({"error": "Invalid filename", "request_id": request_id}), 400

            ext = Path(filename).suffix.lower()
            if ext not in Config.ALLOWED_EXTENSIONS:
                return jsonify({"error": "File type not supported", "request_id": request_id}), 400

            # Read and validate file
            file_content = file.read()
            max_size = Config.MAX_CONTENT_LENGTH
            if len(file_content) > max_size:
                return jsonify({"error": "File too large", "request_id": request_id}), 413

            from security import validate_file_magic
            if not validate_file_magic(file_content, ext):
                return jsonify({"error": "File content validation failed", "request_id": request_id}), 400

            # Convert to markdown first
            temp_dir = tempfile.mkdtemp()
            temp_input = Path(temp_dir) / filename

            try:
                temp_input.write_bytes(file_content)
                markdown_content = converter.convert_to_string(temp_input)
            finally:
                temp_input.unlink(missing_ok=True)
                Path(temp_dir).rmdir()

        # Or check for raw content
        elif request.is_json and request.json.get('content'):
            markdown_content = request.json['content']
            params = request.json
        elif request.form.get('content'):
            markdown_content = request.form['content']
            params = request.form
        else:
            return jsonify({
                "error": "No content provided. Upload a file or send 'content' field.",
                "request_id": request_id
            }), 400

        # Get chunking parameters
        if request.is_json:
            params = request.json
        else:
            params = request.form

        chunk_size = int(params.get('chunk_size', 512))
        chunk_overlap = int(params.get('chunk_overlap', 50))
        strategy = params.get('strategy', 'character')  # Default to character to avoid tiktoken hang
        # Handle both boolean and string values for preserve_headers
        preserve_headers_val = params.get('preserve_headers', False)
        if isinstance(preserve_headers_val, bool):
            preserve_headers = preserve_headers_val
        else:
            preserve_headers = str(preserve_headers_val).lower() == 'true'
        export_format = params.get('export_format', 'full')

        # Validate parameters
        chunk_size = max(64, min(chunk_size, 8192))
        chunk_overlap = max(0, min(chunk_overlap, chunk_size // 2))

        # Perform chunking
        if preserve_headers:
            result = chunk_with_headers(markdown_content, chunk_size, chunk_overlap)
        else:
            result = chunk_document(markdown_content, chunk_size, chunk_overlap, strategy)

        if "error" in result:
            return jsonify({"error": result["error"], "request_id": request_id}), 400

        # Export format
        if export_format == "embedding":
            chunks = export_for_embedding(result, include_metadata=True)
            response_data = {
                "success": True,
                "chunks": chunks,
                "metadata": result.get("metadata", {}),
                "request_id": request_id
            }
        else:
            response_data = {
                "success": True,
                "chunks": result["chunks"],
                "metadata": result.get("metadata", {}),
                "request_id": request_id
            }

        # Record stats
        num_chunks = len(result.get("chunks", []))
        stats.record_chunk(ip, num_chunks)
        logger.info(f"Document chunked ({num_chunks} chunks) from {ip}", extra={'request_id': request_id})

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Chunking error: {e}", extra={'request_id': request_id})
        stats.record_error("chunking", str(e))
        return jsonify({"error": "Chunking failed", "request_id": request_id}), 500


@bp.route("/api/token-count", methods=["POST"])
@security_check
def api_token_count():
    """
    Get accurate token count for text using tiktoken.

    Accepts:
    - Raw text in 'content' field

    Returns:
    - Token count
    - Character count
    - Encoding method used
    """
    request_id = getattr(request, 'request_id', 'UNKNOWN')

    try:
        # Get content
        if request.is_json and request.json.get('content'):
            content = request.json['content']
        elif request.form.get('content'):
            content = request.form['content']
        else:
            return jsonify({
                "error": "No content provided",
                "request_id": request_id
            }), 400

        # Get token count
        result = get_token_count(content)

        return jsonify({
            "success": True,
            **result,
            "request_id": request_id
        })

    except Exception as e:
        logger.error(f"Token count error: {e}", extra={'request_id': request_id})
        return jsonify({"error": "Token counting failed", "request_id": request_id}), 500


@bp.route("/rag")
def rag_page():
    """Render RAG pipeline page."""
    if 'csrf_token' not in session:
        session['csrf_token'] = hashlib.sha256(os.urandom(32)).hexdigest()

    # Get memory count from server-side store
    memory_store = get_memory_store()
    session_id = session.get('user_id', '')
    memory_count = memory_store.get_item_count(session_id) if session_id else 0

    return render_template("rag.html", csrf_token=session['csrf_token'], active_page='rag', memory_count=memory_count)


@bp.route("/api/memory/reset", methods=["POST"])
@security_check
def reset_memory():
    """Reset session memory (clear all injected data)."""
    request_id = getattr(request, 'request_id', 'UNKNOWN')

    # Clear server-side memory store
    memory_store = get_memory_store()
    session_id = session.get('user_id', '')
    if session_id:
        memory_store.clear_session(session_id)

    logger.info(f"Memory reset by user", extra={'request_id': request_id})
    return jsonify({
        "success": True,
        "message": "Memory cleared",
        "request_id": request_id
    })


@bp.route("/api/memory/status", methods=["GET"])
def memory_status():
    """Get current memory status."""
    memory_store = get_memory_store()
    session_id = session.get('user_id', '')

    if not session_id:
        return jsonify({"count": 0, "items": []})

    items = memory_store.get_items(session_id)
    return jsonify({
        "count": len(items),
        "items": [
            {
                "filename": item.get('filename', 'Unknown'),
                "type": item.get('type', 'unknown'),
                "format": item.get('format', 'markdown')
            }
            for item in items
        ]
    })


@bp.route("/methodology")
def methodology_page():
    """Render methodology/engineering leadership page."""
    return render_template("methodology.html", active_page='methodology')


@bp.route("/architecture")
def architecture_page():
    """Render architecture/technology showcase page."""
    return render_template("architecture.html", active_page='architecture')


# =============================================================================
# RAG EXPORT & EMBEDDING API
# =============================================================================

@bp.route("/api/export/jsonl", methods=["POST"])
@security_check
def api_export_jsonl():
    """
    Export document chunks as JSONL format.

    Accepts:
    - Raw markdown content in 'content' field
    - Optional: include_embeddings (true/false)
    - Optional: chunk_size, chunk_overlap

    Returns:
    - JSONL formatted string (one JSON object per line)
    """
    request_id = getattr(request, 'request_id', 'UNKNOWN')
    ip = get_client_ip()

    try:
        # Get content
        if request.is_json:
            params = request.json
            content = params.get('content', '')
        else:
            params = request.form
            content = params.get('content', '')

        if not content:
            return jsonify({"error": "No content provided", "request_id": request_id}), 400

        # Chunking parameters
        chunk_size = int(params.get('chunk_size', 512))
        chunk_overlap = int(params.get('chunk_overlap', 50))
        include_embeddings = str(params.get('include_embeddings', 'false')).lower() == 'true'

        # Chunk the content
        result = chunk_document(content, chunk_size, chunk_overlap)
        if "error" in result:
            return jsonify({"error": result["error"], "request_id": request_id}), 400

        chunks = result.get("chunks", [])

        # Export as JSONL
        jsonl_output = export_jsonl(chunks, include_embeddings=include_embeddings)

        # Record stats
        stats.record_chunk(ip, len(chunks))
        logger.info(f"JSONL export ({len(chunks)} chunks) from {ip}", extra={'request_id': request_id})

        return jsonify({
            "success": True,
            "format": "jsonl",
            "chunks_count": len(chunks),
            "includes_embeddings": include_embeddings,
            "data": jsonl_output,
            "request_id": request_id
        })

    except Exception as e:
        logger.error(f"JSONL export error: {e}", extra={'request_id': request_id})
        stats.record_error("jsonl_export", str(e))
        return jsonify({"error": "Export failed", "request_id": request_id}), 500


@bp.route("/api/embed", methods=["POST"])
@security_check
def api_embed():
    """
    Generate embeddings for text or chunks.

    Accepts:
    - text: Single text string to embed
    - texts: Array of text strings to embed
    - chunks: Array of chunk objects with 'text' field

    Returns:
    - Embeddings with model info and dimensions
    """
    request_id = getattr(request, 'request_id', 'UNKNOWN')
    ip = get_client_ip()

    try:
        if not request.is_json:
            return jsonify({"error": "JSON body required", "request_id": request_id}), 400

        data = request.json

        # Single text
        if 'text' in data:
            import time
            from model_metrics import model_metrics
            
            start_time = time.time()
            result = generate_embedding(data['text'])
            duration = time.time() - start_time
            
            model_metrics.track_operation(
                operation='embedding',
                model='all-MiniLM-L6-v2',
                input_size=len(data['text']),
                output_size=1,
                duration=duration
            )
            
            stats.record_analyze(ip)
            return jsonify({
                "success": True,
                "embedding": result,
                "embedding_info": get_embedding_info(),
                "request_id": request_id
            })

        # Multiple texts
        if 'texts' in data:
            texts = data['texts']
            if not isinstance(texts, list) or len(texts) == 0:
                return jsonify({"error": "texts must be a non-empty array", "request_id": request_id}), 400
            if len(texts) > 100:
                return jsonify({"error": "Maximum 100 texts per request", "request_id": request_id}), 400

            import time
            from model_metrics import model_metrics
            
            start_time = time.time()
            results = generate_embeddings_batch(texts)
            duration = time.time() - start_time
            
            total_chars = sum(len(t) for t in texts)
            model_metrics.track_operation(
                operation='embedding_batch',
                model='all-MiniLM-L6-v2',
                input_size=total_chars,
                output_size=len(results),
                duration=duration
            )

            stats.record_analyze(ip)
            return jsonify({
                "success": True,
                "embeddings": results,
                "count": len(results),
                "embedding_info": get_embedding_info(),
                "request_id": request_id
            })

        # Chunks with text
        if 'chunks' in data:
            chunks = data['chunks']
            if not isinstance(chunks, list) or len(chunks) == 0:
                return jsonify({"error": "chunks must be a non-empty array", "request_id": request_id}), 400
            if len(chunks) > 100:
                return jsonify({"error": "Maximum 100 chunks per request", "request_id": request_id}), 400

            import time
            from model_metrics import model_metrics
            
            start_time = time.time()
            results = embed_chunks(chunks, include_text=True)
            duration = time.time() - start_time
            
            total_chars = sum(len(c.get('text', '')) for c in chunks)
            model_metrics.track_operation(
                operation='embedding_chunks',
                model='all-MiniLM-L6-v2',
                input_size=total_chars,
                output_size=len(results),
                duration=duration
            )

            stats.record_analyze(ip)
            return jsonify({
                "success": True,
                "embedded_chunks": results,
                "count": len(results),
                "embedding_info": get_embedding_info(),
                "request_id": request_id
            })

        return jsonify({
            "error": "Provide 'text', 'texts', or 'chunks' in request body",
            "request_id": request_id
        }), 400

    except Exception as e:
        logger.error(f"Embedding error: {e}", extra={'request_id': request_id})
        stats.record_error("embedding", str(e))
        return jsonify({"error": "Embedding generation failed", "request_id": request_id}), 500


@bp.route("/api/embedding-info", methods=["GET"])
def api_embedding_info():
    """Get information about the embedding system."""
    return jsonify({
        "success": True,
        **get_embedding_info()
    })


@bp.route("/api/export/vectordb", methods=["POST"])
@security_check
def api_export_vectordb():
    """
    Export chunks in vector database ready format.

    Accepts:
    - content: Markdown content to chunk and embed
    - format: "chromadb" or "lancedb" (default: chromadb)
    - collection_name / table_name: Name for the collection/table
    - chunk_size, chunk_overlap: Chunking parameters

    Returns:
    - Data structure ready for direct import into the specified vector DB
    """
    request_id = getattr(request, 'request_id', 'UNKNOWN')
    ip = get_client_ip()

    try:
        if not request.is_json:
            return jsonify({"error": "JSON body required", "request_id": request_id}), 400

        data = request.json
        content = data.get('content', '')

        if not content:
            return jsonify({"error": "No content provided", "request_id": request_id}), 400

        # Parameters
        export_format = data.get('format', 'chromadb').lower()
        collection_name = data.get('collection_name', data.get('table_name', 'documents'))
        chunk_size = int(data.get('chunk_size', 512))
        chunk_overlap = int(data.get('chunk_overlap', 50))

        # Validate format
        if export_format not in ['chromadb', 'lancedb']:
            return jsonify({
                "error": "format must be 'chromadb' or 'lancedb'",
                "request_id": request_id
            }), 400

        # Chunk the content
        result = chunk_document(content, chunk_size, chunk_overlap)
        if "error" in result:
            return jsonify({"error": result["error"], "request_id": request_id}), 400

        chunks = result.get("chunks", [])

        # Export in requested format
        if export_format == 'chromadb':
            export_data = export_for_chromadb(chunks, collection_name)
        else:
            export_data = export_for_lancedb(chunks, collection_name)

        # Record stats
        stats.record_chunk(ip, len(chunks))
        logger.info(f"VectorDB export ({export_format}, {len(chunks)} chunks) from {ip}",
                    extra={'request_id': request_id})

        return jsonify({
            "success": True,
            "format": export_format,
            "chunks_count": len(chunks),
            **export_data,
            "request_id": request_id
        })

    except Exception as e:
        logger.error(f"VectorDB export error: {e}", extra={'request_id': request_id})
        stats.record_error("vectordb_export", str(e))
        return jsonify({"error": "Export failed", "request_id": request_id}), 500


@bp.route("/api/pipeline", methods=["POST"])
@security_check
def api_full_pipeline():
    """
    Complete RAG preparation pipeline in one call.

    Accepts:
    - File upload OR content field
    - output_format: "jsonl", "chromadb", "lancedb" (default: jsonl)
    - include_analysis: true/false
    - chunk_size, chunk_overlap

    Returns:
    - Markdown content
    - Analysis (if requested)
    - Chunks with embeddings in requested format
    """
    request_id = getattr(request, 'request_id', 'UNKNOWN')
    ip = get_client_ip()

    try:
        markdown_content = None
        original_filename = None

        # Check if file was uploaded
        if "file" in request.files and request.files["file"].filename:
            file = request.files["file"]
            original_filename = sanitize_filename(file.filename)

            if not original_filename:
                return jsonify({"error": "Invalid filename", "request_id": request_id}), 400

            ext = Path(original_filename).suffix.lower()
            if ext not in Config.ALLOWED_EXTENSIONS:
                return jsonify({"error": "File type not supported", "request_id": request_id}), 400

            file_content = file.read()
            if len(file_content) > Config.MAX_CONTENT_LENGTH:
                return jsonify({"error": "File too large", "request_id": request_id}), 413

            from security import validate_file_magic
            if not validate_file_magic(file_content, ext):
                return jsonify({"error": "File validation failed", "request_id": request_id}), 400

            temp_dir = tempfile.mkdtemp()
            temp_input = Path(temp_dir) / original_filename

            try:
                temp_input.write_bytes(file_content)
                markdown_content = converter.convert_to_string(temp_input)
            finally:
                temp_input.unlink(missing_ok=True)
                Path(temp_dir).rmdir()

        elif request.form.get('content'):
            markdown_content = request.form['content']
        elif request.is_json and request.json.get('content'):
            markdown_content = request.json['content']
        else:
            return jsonify({
                "error": "Upload a file or provide 'content' field",
                "request_id": request_id
            }), 400

        # Get parameters
        if request.is_json:
            params = request.json
        else:
            params = request.form

        output_format = params.get('export_format', params.get('output_format', 'jsonl')).lower()
        include_analysis = str(params.get('include_analysis', 'false')).lower() == 'true'
        chunk_size = int(params.get('chunk_size', 512))
        chunk_overlap = int(params.get('overlap', params.get('chunk_overlap', 50)))
        chunking_strategy = params.get('chunking_strategy', 'recursive_character')
        embedding_model = params.get('embedding_model', 'all-MiniLM-L6-v2')
        collection_name = params.get('collection_name', 'documents')

        # Step 1: Chunk
        chunk_result = chunk_document(markdown_content, chunk_size, chunk_overlap, chunking_strategy)
        if "error" in chunk_result:
            return jsonify({"error": chunk_result["error"], "request_id": request_id}), 400

        chunks = chunk_result.get("chunks", [])

        # Step 2: Analysis (optional)
        analysis = None
        if include_analysis:
            analysis = analyze_document(markdown_content)

        # Step 2: Generate embeddings for chunks
        chunk_texts = [c.get('text', '') for c in chunks]
        embeddings_result = generate_embeddings_batch(chunk_texts, embedding_model)
        
        # Add embeddings to chunks
        for i, chunk in enumerate(chunks):
            if i < len(embeddings_result):
                chunk['embedding'] = embeddings_result[i]['embedding']
                chunk['embedding_info'] = {
                    'model': embeddings_result[i]['model'],
                    'dimensions': embeddings_result[i]['dimensions']
                }

        # Step 3: Export with embeddings
        if output_format == 'chromadb':
            export_data = export_for_chromadb(chunks, collection_name)
        elif output_format == 'lancedb':
            export_data = export_for_lancedb(chunks, collection_name)
        else:  # jsonl
            export_data = {
                "format": "jsonl",
                "data": export_jsonl(chunks, include_embeddings=True)
            }

        # Record stats
        stats.record_conversion('.pipeline', len(markdown_content), ip)
        stats.record_chunk(ip, len(chunks))
        if include_analysis:
            stats.record_analyze(ip)

        logger.info(f"Full pipeline ({output_format}, {len(chunks)} chunks) from {ip}",
                    extra={'request_id': request_id})

        response = {
            "success": True,
            "pipeline": {
                "source_file": original_filename,
                "markdown_length": len(markdown_content),
                "chunks_count": len(chunks),
                "output_format": output_format
            },
            "markdown": markdown_content[:5000] + ("..." if len(markdown_content) > 5000 else ""),
            "export": export_data,
            "request_id": request_id
        }

        if analysis:
            response["analysis"] = analysis

        return jsonify(response)

    except Exception as e:
        logger.error(f"Pipeline error: {e}", extra={'request_id': request_id})
        stats.record_error("pipeline", str(e))
        return jsonify({"error": "Pipeline processing failed", "request_id": request_id}), 500


@bp.route("/api/retrieve", methods=["POST"])
@security_check
def api_retrieve():
    """
    Retrieve similar chunks based on query using cosine similarity.
    
    Accepts:
    - query: Search query text
    - chunks: List of chunk objects with text and optional embeddings
    - embeddings: Optional list of embeddings (if not in chunks)
    - model: Embedding model name (for query embedding)
    - top_k: Number of results to return (default: 3)
    
    Returns:
    - results: List of top_k chunks with similarity scores
    """
    request_id = getattr(request, 'request_id', 'UNKNOWN')
    ip = get_client_ip()
    
    try:
        if not request.is_json:
            return jsonify({"error": "JSON body required", "request_id": request_id}), 400
        
        data = request.json
        query = data.get('query', '').strip()
        if not query:
            return jsonify({"error": "Query is required", "request_id": request_id}), 400
        
        chunks = data.get('chunks', [])
        embeddings = data.get('embeddings', [])
        model_name = data.get('model', 'all-MiniLM-L6-v2')
        top_k = int(data.get('top_k', 3))
        
        # Generate query embedding
        query_embedding_result = generate_embedding(query, model_name)
        query_embedding = query_embedding_result['embedding']
        
        # Get chunk embeddings
        chunk_embeddings = []
        chunk_texts = []
        
        for i, chunk in enumerate(chunks):
            if isinstance(chunk, dict):
                # Try to get embedding from chunk
                chunk_emb = chunk.get('embedding') or (embeddings[i] if i < len(embeddings) else None)
                chunk_text = chunk.get('text', '')
            else:
                chunk_emb = embeddings[i] if i < len(embeddings) else None
                chunk_text = str(chunk)
            
            if chunk_emb:
                chunk_embeddings.append(chunk_emb)
                chunk_texts.append(chunk_text)
        
        if not chunk_embeddings:
            return jsonify({"error": "No embeddings found in chunks", "request_id": request_id}), 400
        
        # Calculate cosine similarity
        import math
        similarities = []
        for i, chunk_emb in enumerate(chunk_embeddings):
            # Cosine similarity
            dot_product = sum(a * b for a, b in zip(query_embedding, chunk_emb))
            magnitude_a = math.sqrt(sum(a * a for a in query_embedding))
            magnitude_b = math.sqrt(sum(b * b for b in chunk_emb))
            
            if magnitude_a > 0 and magnitude_b > 0:
                similarity = dot_product / (magnitude_a * magnitude_b)
            else:
                similarity = 0.0
            
            similarities.append({
                'index': i,
                'text': chunk_texts[i],
                'score': similarity
            })
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x['score'], reverse=True)
        
        # Return top_k results
        results = similarities[:top_k]
        
        logger.info(f"Retrieval query from {ip} ({len(results)} results)", extra={'request_id': request_id})
        
        return jsonify({
            "success": True,
            "query": query,
            "results": results,
            "total_chunks": len(chunk_embeddings),
            "request_id": request_id
        })
        
    except Exception as e:
        logger.error(f"Retrieval error: {e}", extra={'request_id': request_id})
        return jsonify({"error": "Retrieval failed", "request_id": request_id}), 500


@bp.route("/api/chat", methods=["POST"])
@security_check
def api_chat():
    """
    Chat completion endpoint using OpenRouter Gateway.
    
    Accepts:
    - model: UI model name (e.g., "Google Gemini 2.0 Flash")
    - messages: List of message objects with "role" and "content"
    - context: Optional context text for RAG
    
    Returns:
    - response: AI response text
    - latency_ms: Request latency in milliseconds
    - cost: Estimated cost (always 0.00 for free tier)
    - model: Model name used
    """
    request_id = getattr(request, 'request_id', 'UNKNOWN')
    ip = get_client_ip()
    
    try:
        if not request.is_json:
            return jsonify({"error": "JSON body required", "request_id": request_id}), 400
        
        data = request.json
        model = data.get('model', 'Google Gemini 2.0 Flash')
        messages = data.get('messages', [])
        context = data.get('context', '')

        # Get memory from server-side store
        memory_store = get_memory_store()
        session_id = session.get('user_id', '')

        # Check if memory exists and is not empty
        if not session_id or memory_store.get_item_count(session_id) == 0:
            logger.warning(f"Chat request with empty memory from {ip}", extra={'request_id': request_id})
            return jsonify({
                "error": "Memory Empty",
                "message": "No data has been injected. Please upload files first.",
                "request_id": request_id
            }), 400

        # Get combined context from memory store
        if not context:  # Only use memory if no explicit context provided
            context = memory_store.get_combined_content(session_id)
        
        if not messages:
            return jsonify({"error": "Messages array required", "request_id": request_id}), 400
        
        # Validate messages format
        for msg in messages:
            if not isinstance(msg, dict) or 'role' not in msg or 'content' not in msg:
                return jsonify({"error": "Invalid message format. Each message must have 'role' and 'content'", "request_id": request_id}), 400
        
        # Call OpenRouter gateway
        try:
            # Get domain from request (default to general)
            domain = request.json.get('domain', 'general')
            result = chat_completion(model=model, messages=messages, context=context, domain=domain)
            
            # Check for rate limit error
            if "error" in result and result.get("error") == "Queue Full":
                retry_after = result.get("retry_after", 3)
                logger.warning(f"Rate limit hit for {ip}", extra={'request_id': request_id})
                return jsonify({
                    "error": "Queue Full",
                    "retry_after": retry_after,
                    "request_id": request_id
                }), 429
            
            # Success response
            logger.info(f"Chat completion from {ip} using {model}", extra={'request_id': request_id})
            return jsonify({
                "success": True,
                "response": result.get("response", ""),
                "latency_ms": result.get("latency_ms", 0),
                "cost": result.get("cost", 0.0),
                "model": result.get("model", model),
                "request_id": request_id
            })
            
        except ValueError as e:
            # API key missing
            logger.error(f"OpenRouter configuration error: {e}", extra={'request_id': request_id})
            return jsonify({
                "error": "OpenRouter API not configured",
                "request_id": request_id
            }), 503
        except requests.exceptions.RequestException as e:
            # HTTP errors from OpenRouter
            logger.error(f"OpenRouter HTTP error: {e}", extra={'request_id': request_id})
            return jsonify({
                "error": "Inference service unavailable",
                "request_id": request_id
            }), 502
        except Exception as e:
            logger.error(f"OpenRouter error: {e}", extra={'request_id': request_id})
            return jsonify({
                "error": "Chat completion failed",
                "request_id": request_id
            }), 500
            
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", extra={'request_id': request_id})
        return jsonify({"error": "Internal server error", "request_id": request_id}), 500


@bp.route("/api/key/validate")
def validate_api_key_endpoint():
    """Validate an API key and return its info."""
    from security import validate_api_key
    api_key = request.headers.get('X-API-Key')

    if not api_key:
        return jsonify({
            "valid": False,
            "error": "No API key provided. Use X-API-Key header."
        }), 400

    is_valid, key_info = validate_api_key(api_key)

    if is_valid and key_info:
        return jsonify({
            "valid": True,
            "name": key_info.get('name'),
            "rate_limit": key_info.get('rate_limit'),
            "total_requests": key_info.get('total_requests')
        })

    return jsonify({
        "valid": False,
        "error": "Invalid or inactive API key"
    }), 401


@bp.route("/vision")
def vision_page():
    """Vision defect analysis page for industrial maintenance."""
    return render_template("vision.html", active_page="vision")


@bp.route("/api/analyze-image", methods=["POST"])
@security_check
def api_analyze_image():
    """
    Analyze image for industrial defects using vision AI.
    
    Accepts:
    - image: Base64-encoded image (data URI format)
    - context: Optional equipment context (e.g., "Packaging Line A")
    
    Returns:
    - analysis: Structured JSON with defect information
    - latency_ms: Request latency
    """
    request_id = getattr(request, 'request_id', 'UNKNOWN')
    ip = get_client_ip()
    
    try:
        if not request.is_json:
            return jsonify({"error": "JSON body required", "request_id": request_id}), 400
        
        data = request.json
        image_base64 = data.get('image')
        context = data.get('context', '')
        
        if not image_base64:
            return jsonify({"error": "Image data required", "request_id": request_id}), 400
        
        # Validate base64 image format
        if not image_base64.startswith('data:image/'):
            return jsonify({"error": "Invalid image format. Expected data URI.", "request_id": request_id}), 400
        
        # Call vision analysis
        try:
            result = analyze_image(image_base64=image_base64, context=context)
            
            # Check for rate limit error
            if "error" in result and result.get("error") == "Queue Full":
                retry_after = result.get("retry_after", 3)
                logger.warning(f"Vision rate limit hit for {ip}", extra={'request_id': request_id})
                return jsonify({
                    "error": "System Busy",
                    "message": "Retrying...",
                    "retry_after": retry_after,
                    "request_id": request_id
                }), 429
            
            # Success response
            logger.info(f"Vision analysis from {ip} for context: {context}", extra={'request_id': request_id})
            return jsonify({
                "success": True,
                "analysis": result.get("analysis", {}),
                "latency_ms": result.get("latency_ms", 0),
                "model": result.get("model", "google/gemini-2.0-flash-exp:free"),
                "request_id": request_id
            })
            
        except ValueError as e:
            # API key missing
            logger.error(f"Vision configuration error: {e}", extra={'request_id': request_id})
            return jsonify({
                "error": "Vision service not configured",
                "request_id": request_id
            }), 503
        except requests.exceptions.RequestException as e:
            # HTTP errors from OpenRouter
            logger.error(f"Vision service error: {e}", extra={'request_id': request_id})
            return jsonify({
                "error": "Vision service unavailable",
                "message": "Please try again in a moment",
                "request_id": request_id
            }), 502
        except Exception as e:
            logger.error(f"Vision analysis error: {e}", extra={'request_id': request_id})
            return jsonify({
                "error": "Image analysis failed",
                "request_id": request_id
            }), 500
            
    except Exception as e:
        logger.error(f"Vision endpoint error: {e}", extra={'request_id': request_id})
        return jsonify({"error": "Internal server error", "request_id": request_id}), 500


# =============================================================================
# MEGADOC ASSISTANT ENDPOINT
# =============================================================================

@bp.route("/api/assistant", methods=["POST"])
@security_check
def api_assistant():
    """
    MegaDoc Assistant - RAG chatbot with live stats access

    POST /api/assistant
    Content-Type: application/json

    Request body:
    {
        "question": "How many documents have been processed?",
        "model": "meta-llama/llama-3.2-3b-instruct:free"  // optional
    }

    Response:
    {
        "answer": "Based on the live statistics...",
        "model": "meta-llama/llama-3.2-3b-instruct:free",
        "stats_included": true,
        "request_id": "abc123"
    }
    """
    request_id = getattr(request, 'request_id', 'UNKNOWN')
    logger.info(f"Assistant request from {request.remote_addr}", extra={'request_id': request_id})

    try:
        data = request.get_json() or {}
        question = data.get("question", "").strip()

        if not question:
            return jsonify({
                "error": "Question is required",
                "request_id": request_id
            }), 400

        if len(question) > 500:
            return jsonify({
                "error": "Question too long (max 500 characters)",
                "request_id": request_id
            }), 400

        model = data.get("model")  # Optional model override

        result = ask_assistant(question, model=model)

        if "error" in result:
            logger.warning(f"Assistant error: {result['error']}", extra={'request_id': request_id})
            return jsonify({
                "error": result["error"],
                "request_id": request_id
            }), 503

        logger.info(f"Assistant response generated", extra={'request_id': request_id})
        return jsonify({
            "answer": result.get("answer", ""),
            "model": result.get("model", "unknown"),
            "stats_included": result.get("stats_included", False),
            "tokens_used": result.get("tokens_used", {}),
            "request_id": request_id
        })

    except Exception as e:
        logger.error(f"Assistant endpoint error: {e}", extra={'request_id': request_id})
        return jsonify({
            "error": "Internal server error",
            "request_id": request_id
        }), 500
