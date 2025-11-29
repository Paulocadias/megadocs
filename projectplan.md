# MegaDoc - Enterprise Document Intelligence Platform

## Project Overview
A production-grade Flask web application showcasing AI Tech Lead portfolio capabilities. Features document-to-Markdown conversion, RAG pipeline with vector embeddings, zero data retention architecture, and comprehensive security. Designed for technical interviews and enterprise demonstration.

**Live at**: https://megadocs.paulocadias.com

## Current Tasks

(No pending tasks - all current tasks completed)

## Recently Completed

- [x] Create professional landing page for AI Tech Lead portfolio positioning
  - Hero section with "Enterprise Document Intelligence Platform"
  - Architecture overview, security section, API preview
  - Updated routes: `/` = landing page, `/convert` = converter tool
- [x] Update architecture.html with Zero Data Retention (ZDR) concepts
  - "Why Markdown for LLMs & Chatbots?" section
  - Enhanced security section with ZDR terminology
  - Privacy-first architecture positioning
- [x] Update use_cases.html with AI chatbot buzzwords
  - "Data Preparation for AI & Chatbots" hero
  - Enterprise Chatbot Data Preparation (RAG)
  - Semantic Search & Knowledge Bases
  - AI-Ready Document Migration
  - Privacy-First AI for Regulated Industries
  - Document Processing for AI Agents
- [x] Add dedicated security section to landing page
  - Brute force protection, CSRF, magic byte validation
  - Bot detection, security headers, Cloudflare integration
- [x] Update navigation across all templates
  - Changed `/` links to `/convert` for converter tool
  - Added landing page as new home route
- [x] Update domain to megadocs.paulocadias.com
- [x] Complete RAG pipeline API (embeddings, chunking, vector DB exports)
  - embedder.py: Embeddings with all-MiniLM-L6-v2 (384 dims) + TF-IDF fallback
  - /api/analyze: Document structure analysis
  - /api/chunk: Semantic chunking with token counting
  - /api/token-count: Token counting (tiktoken cl100k_base)
  - /api/embed: Generate embeddings
  - /api/export/jsonl: JSONL export for streaming
  - /api/export/vectordb: ChromaDB/LanceDB export format
  - /api/pipeline: Full RAG pipeline in one call
- [x] Update Architecture page with RAG pipeline flow diagram
- [x] Update Use Cases page with enhanced RAG preparation section
- [x] Update API documentation with all new endpoints
- [x] Create MCP (Model Context Protocol) server integration (mcp_server.py with convert_document, convert_url, list_supported_formats tools)
- [x] Implement API key system for higher rate limits (X-API-Key header, admin management)
- [x] Support batch file uploads (zip) - /api/batch/convert endpoint with ZIP processing
- [x] Add webhook support for conversion completion - async batch processing with webhook notifications
- [x] Refactor to modular architecture (blueprints, config.py, security.py, utils.py)
- [x] Add Use Cases page (/use-cases) with enterprise scenarios
- [x] Research free Python hosting alternatives (see [docs/hosting-alternatives.md](docs/hosting-alternatives.md))
- [x] Add authentication for admin dashboard (password-based, session auth)

## Completed Tasks

- [x] Set up Flask project structure for DreamHost/Passenger
- [x] Create file upload endpoint with validation
- [x] Implement MarkItDown conversion service
- [x] Build simple HTML upload page (drag & drop)
- [x] Add file download response (converted markdown)
- [x] Implement automatic file cleanup (delete after conversion)
- [x] Add file size limits and security validation
- [x] Create passenger_wsgi.py for DreamHost deployment
- [x] Write deployment guide for DreamHost
- [x] Add rate limiting (20 req/min IP-based)
- [x] Add comprehensive REST API with documentation (/api/convert, /api/stats, /api/formats)
- [x] Create admin dashboard with statistics (/admin)
- [x] Add API documentation page (/api/docs)
- [x] Implement CSRF protection
- [x] Implement magic byte file validation
- [x] Add security headers (CSP, X-Frame-Options, XSS protection)
- [x] Add honeypot bot detection
- [x] Implement IP blocking for abuse
- [x] Add request ID tracking for audit logs
- [x] Replace JSON stats with SQLite database
- [x] Add contact form for API/MCP access requests (/contact)
- [x] Add concurrent request limiter (max 10 simultaneous conversions)
- [x] Track users left out due to capacity exceeded in statistics
- [x] Add SEO meta tags (Open Graph, Twitter Cards, JSON-LD structured data)
- [x] Add strict file size validation (Content-Length + actual size verification)
- [x] Add output format selector (Markdown vs Plain Text extraction)
- [x] Fix CSP to allow inline scripts (for JSON-LD structured data and CSRF token)
- [x] Add inline SVG favicon to all templates (no external file needed)
- [x] Add client-side file size validation with user feedback
- [x] Add Markdown to Plain Text converter (strips MD syntax, keeps structure)
- [x] Handle HTTP error codes properly (413 file too large, 429 rate limit, 503 capacity)
- [x] Add keyboard accessibility to upload area (Enter/Space to select file)
- [x] Add ARIA labels for screen reader support

## Backlog

- [ ] Add progress indicator for large files
- [ ] Add Google Cloud Platform deployment option
- [ ] Email notifications for contact form submissions
- [ ] CLI automation tool for batch processing
