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
from utils import sanitize_filename, markdown_to_text
from batch_service import BatchService
from webhook_service import WebhookService
from analyzer import analyze_document
from chunker import chunk_document, chunk_with_headers, export_for_embedding, get_token_count
from embedder import (
    generate_embedding, generate_embeddings_batch, embed_chunks,
    export_for_chromadb, export_for_lancedb, export_jsonl, get_embedding_info
)
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
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
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

@bp.route("/")
def landing():
    """Render the landing page - portfolio showcase."""
    return render_template("landing.html")


@bp.route("/convert")
def converter():
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
        csrf_token=session['csrf_token']
    )


@bp.route("/use-cases")
def use_cases():
    """Render the business use cases page."""
    return render_template("use_cases.html")


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
        stats.record_error()
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
    if output_format not in ('markdown', 'text'):
        output_format = 'markdown'

    # Acquire conversion slot
    if not acquire_conversion_slot():
        stats.record_capacity_exceeded(ip, get_active_conversions())
        return jsonify({
            "error": "System is currently at maximum capacity. Please try again in a few moments.",
            "request_id": request_id
        }), 503

    # Set output file extension based on format
    output_ext = '.txt' if output_format == 'text' else '.md'

    temp_dir = tempfile.mkdtemp()
    temp_input = Path(temp_dir) / filename

    try:
        temp_input.write_bytes(file_content)
        logger.info(f"API conversion: {filename} -> {output_format} from {ip} [Active: {get_active_conversions()}/{Config.MAX_CONCURRENT_CONVERSIONS}]", extra={'request_id': request_id})

        # Step 1: Convert to Markdown first
        markdown_content = converter.convert_to_string(temp_input)

        # Step 2: If text format requested, convert markdown to plain text
        if output_format == 'text':
            final_content = markdown_to_text(markdown_content)
        else:
            final_content = markdown_content

        release_conversion_slot()
        stats.record_conversion(ext, len(file_content), ip)

        return jsonify({
            "success": True,
            "filename": f"{Path(filename).stem}{output_ext}",
            "content": final_content,
            "format": output_format,
            "request_id": request_id
        })

    except Exception as e:
        logger.error(f"API conversion error: {e}", extra={'request_id': request_id})
        release_conversion_slot()
        stats.record_error()
        return jsonify({"error": str(e), "request_id": request_id}), 500

    finally:
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
        stats.record_error()
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


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Admin login page."""
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == Config.ADMIN_PASSWORD:
            session['admin_authenticated'] = True
            logger.info(f"Admin login successful from {get_client_ip()}")
            return '<script>window.location.href="/admin";</script>'
        else:
            logger.warning(f"Failed admin login attempt from {get_client_ip()}")
            return render_template("login.html", error="Invalid password")

    # Already logged in - redirect to admin
    if session.get('admin_authenticated'):
        return '<script>window.location.href="/admin";</script>'

    return render_template("login.html")


@bp.route("/logout")
def logout():
    """Admin logout."""
    session.pop('admin_authenticated', None)
    return '<script>window.location.href="/";</script>'


@bp.route("/admin")
def admin_dashboard():
    """Admin dashboard with statistics (requires login)."""
    if not session.get('admin_authenticated'):
        return '<script>window.location.href="/login";</script>'
    return render_template("admin.html", stats=stats.get_summary())


@bp.route("/api/docs")
def api_docs():
    """API documentation page."""
    base_url = request.url_root.rstrip('/')
    return render_template("api-docs.html", base_url=base_url)


@bp.route("/api/stats")
def api_stats():
    """Public API statistics endpoint."""
    return jsonify(stats.get_api_stats())


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
        stats.record_error()
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
        strategy = params.get('strategy', 'token')
        preserve_headers = params.get('preserve_headers', 'false').lower() == 'true'
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
        stats.record_error()
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


@bp.route("/compare")
def compare_page():
    """Render document comparison page."""
    if 'csrf_token' not in session:
        session['csrf_token'] = hashlib.sha256(os.urandom(32)).hexdigest()
    return render_template("compare.html", csrf_token=session['csrf_token'])


@bp.route("/rag")
def rag_page():
    """Render RAG pipeline page."""
    if 'csrf_token' not in session:
        session['csrf_token'] = hashlib.sha256(os.urandom(32)).hexdigest()
    return render_template("rag.html", csrf_token=session['csrf_token'], active_page='rag')


@bp.route("/api/compare", methods=["POST"])
@security_check
def api_compare():
    """
    Compare two markdown documents and return diff.

    Expects JSON body with:
    - original: Original markdown content
    - modified: Modified markdown content

    Returns:
    - diff: Array of line objects with type (added/removed/unchanged) and text
    - stats: Counts of additions, deletions, unchanged lines
    """
    request_id = getattr(request, 'request_id', 'UNKNOWN')
    ip = get_client_ip()

    try:
        if not request.is_json:
            return jsonify({"error": "JSON body required", "request_id": request_id}), 400

        original = request.json.get('original', '')
        modified = request.json.get('modified', '')

        if not original or not modified:
            return jsonify({"error": "Both original and modified content required", "request_id": request_id}), 400

        # Use difflib to compare
        import difflib

        original_lines = original.splitlines()
        modified_lines = modified.splitlines()

        differ = difflib.Differ()
        diff_result = list(differ.compare(original_lines, modified_lines))

        # Process diff into structured format
        diff = []
        additions = 0
        deletions = 0
        unchanged = 0

        for line in diff_result:
            if line.startswith('  '):  # Unchanged
                diff.append({"type": "unchanged", "text": line[2:]})
                unchanged += 1
            elif line.startswith('- '):  # Removed
                diff.append({"type": "removed", "text": line[2:]})
                deletions += 1
            elif line.startswith('+ '):  # Added
                diff.append({"type": "added", "text": line[2:]})
                additions += 1
            # Skip '? ' lines (diff markers)

        # Record stats
        stats.record_compare(ip)
        logger.info(f"Document comparison from {ip}", extra={'request_id': request_id})

        return jsonify({
            "success": True,
            "diff": diff,
            "stats": {
                "additions": additions,
                "deletions": deletions,
                "unchanged": unchanged
            },
            "request_id": request_id
        })

    except Exception as e:
        logger.error(f"Comparison error: {e}", extra={'request_id': request_id})
        stats.record_error()
        return jsonify({"error": "Comparison failed", "request_id": request_id}), 500


@bp.route("/architecture")
def architecture_page():
    """Render architecture/technology showcase page."""
    return render_template("architecture.html")


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
        stats.record_error()
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
            result = generate_embedding(data['text'])
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

            results = generate_embeddings_batch(texts)
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

            results = embed_chunks(chunks, include_text=True)
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
        stats.record_error()
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
        stats.record_error()
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

        output_format = params.get('output_format', 'jsonl').lower()
        include_analysis = str(params.get('include_analysis', 'false')).lower() == 'true'
        chunk_size = int(params.get('chunk_size', 512))
        chunk_overlap = int(params.get('chunk_overlap', 50))
        collection_name = params.get('collection_name', 'documents')

        # Step 1: Chunk
        chunk_result = chunk_document(markdown_content, chunk_size, chunk_overlap)
        if "error" in chunk_result:
            return jsonify({"error": chunk_result["error"], "request_id": request_id}), 400

        chunks = chunk_result.get("chunks", [])

        # Step 2: Analysis (optional)
        analysis = None
        if include_analysis:
            analysis = analyze_document(markdown_content)

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
        stats.record_error()
        return jsonify({"error": "Pipeline processing failed", "request_id": request_id}), 500


@bp.route("/contact")
def contact_page():
    """Render contact form for API access requests."""
    if 'csrf_token' not in session:
        session['csrf_token'] = hashlib.sha256(os.urandom(32)).hexdigest()
    return render_template("contact.html", csrf_token=session['csrf_token'])


@bp.route("/contact", methods=["POST"])
@security_check
def contact_submit():
    """Handle contact form submission."""
    request_id = getattr(request, 'request_id', 'UNKNOWN')
    ip = get_client_ip()

    # CSRF validation
    csrf_token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
    if not csrf_token or csrf_token != session.get('csrf_token'):
        return jsonify({"error": "Invalid request token. Please refresh the page."}), 403

    # Honeypot check
    if request.form.get('website'):
        logger.warning(f"Contact honeypot triggered from {ip}", extra={'request_id': request_id})
        return jsonify({"error": "Invalid request"}), 400

    # Get form data
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    company = request.form.get('company', '').strip()
    use_case = request.form.get('use_case', '').strip()
    message = request.form.get('message', '').strip()

    # Validation
    if not name or len(name) < 2:
        return jsonify({"error": "Please provide your name"}), 400
    if not email or '@' not in email:
        return jsonify({"error": "Please provide a valid email"}), 400
    if not use_case:
        return jsonify({"error": "Please select a use case"}), 400

    # Sanitize inputs (basic)
    name = name[:100]
    email = email[:100]
    company = company[:100] if company else ""
    use_case = use_case[:50]
    message = message[:1000] if message else ""

    # Record in database
    try:
        stats.record_contact_request(name, email, company, use_case, message)
        logger.info(f"Contact request from {email} ({use_case})", extra={'request_id': request_id})
        return jsonify({
            "success": True,
            "message": "Thank you! Your request has been submitted. We'll contact you soon."
        })
    except Exception as e:
        logger.error(f"Failed to save contact request: {e}", extra={'request_id': request_id})
        return jsonify({"error": "Failed to submit request. Please try again."}), 500


# =============================================================================
# API KEY MANAGEMENT (Admin)
# =============================================================================

def admin_required(f):
    """Require admin authentication for protected routes."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_authenticated'):
            return jsonify({"error": "Admin authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function


@bp.route("/admin/api-keys")
@admin_required
def admin_api_keys():
    """List all API keys."""
    from api_keys import api_keys
    keys = api_keys.list_keys()
    return jsonify({"keys": keys})


@bp.route("/admin/api-keys/generate", methods=["POST"])
@admin_required
def admin_generate_api_key():
    """Generate a new API key."""
    from api_keys import api_keys
    request_id = getattr(request, 'request_id', 'UNKNOWN')

    data = request.get_json() or request.form
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    rate_limit = int(data.get('rate_limit', 100))

    if not name or not email:
        return jsonify({"error": "Name and email are required"}), 400

    if rate_limit < 1 or rate_limit > 10000:
        return jsonify({"error": "Rate limit must be between 1 and 10000"}), 400

    try:
        raw_key = api_keys.generate_key(name, email, rate_limit)
        logger.info(f"API key generated for {email}", extra={'request_id': request_id})
        return jsonify({
            "success": True,
            "api_key": raw_key,
            "name": name,
            "email": email,
            "rate_limit": rate_limit,
            "message": "Save this key securely - it won't be shown again!"
        })
    except Exception as e:
        logger.error(f"Failed to generate API key: {e}", extra={'request_id': request_id})
        return jsonify({"error": "Failed to generate API key"}), 500


@bp.route("/admin/api-keys/<int:key_id>/deactivate", methods=["POST"])
@admin_required
def admin_deactivate_key(key_id):
    """Deactivate an API key."""
    from api_keys import api_keys
    try:
        api_keys.deactivate_key(key_id)
        return jsonify({"success": True, "message": "API key deactivated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/admin/api-keys/<int:key_id>/activate", methods=["POST"])
@admin_required
def admin_activate_key(key_id):
    """Reactivate an API key."""
    from api_keys import api_keys
    try:
        api_keys.activate_key(key_id)
        return jsonify({"success": True, "message": "API key activated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/admin/api-keys/<int:key_id>/rate-limit", methods=["POST"])
@admin_required
def admin_update_rate_limit(key_id):
    """Update rate limit for an API key."""
    from api_keys import api_keys
    data = request.get_json() or request.form
    new_limit = int(data.get('rate_limit', 100))

    if new_limit < 1 or new_limit > 10000:
        return jsonify({"error": "Rate limit must be between 1 and 10000"}), 400

    try:
        api_keys.update_rate_limit(key_id, new_limit)
        return jsonify({"success": True, "message": f"Rate limit updated to {new_limit}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
