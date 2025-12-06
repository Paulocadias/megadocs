#!/usr/bin/env python3
"""
MCP Server for DocsSite Document Conversion.

This server exposes document conversion functionality via the Model Context Protocol (MCP),
allowing AI assistants like Claude to convert documents to Markdown.

Usage:
    # Run directly
    python mcp_server.py

    # Or with MCP CLI
    mcp dev mcp_server.py

    # Install in Claude Desktop
    mcp install mcp_server.py
"""

import os
import sys
import tempfile
import base64
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Resource, ResourceTemplate

# Import our converter
from converter import DocumentConverter
from utils import markdown_to_text

# Supported formats
SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".txt",
    ".xlsx", ".xls", ".csv",
    ".pptx", ".ppt",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp",
    ".html", ".htm", ".json", ".xml",
    ".epub"
}

# Initialize server and converter
server = Server("docssite-mcp")
converter = DocumentConverter()


@server.list_tools()
async def list_tools():
    """List available tools."""
    return [
        Tool(
            name="convert_document",
            description="Convert a document file to Markdown or plain text. Supports PDF, Word, Excel, PowerPoint, images, HTML, and more.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to convert (local file path)"
                    },
                    "file_content_base64": {
                        "type": "string",
                        "description": "Base64-encoded file content (alternative to file_path)"
                    },
                    "filename": {
                        "type": "string",
                        "description": "Original filename (required if using file_content_base64)"
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["markdown", "text"],
                        "default": "markdown",
                        "description": "Output format: 'markdown' (default) or 'text' (plain text)"
                    }
                },
                "oneOf": [
                    {"required": ["file_path"]},
                    {"required": ["file_content_base64", "filename"]}
                ]
            }
        ),
        Tool(
            name="list_supported_formats",
            description="List all supported file formats for document conversion.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="convert_url",
            description="Fetch and convert a document from a URL to Markdown.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL of the document to fetch and convert"
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["markdown", "text"],
                        "default": "markdown",
                        "description": "Output format: 'markdown' (default) or 'text'"
                    }
                },
                "required": ["url"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls."""

    if name == "convert_document":
        return await handle_convert_document(arguments)

    elif name == "list_supported_formats":
        return await handle_list_formats()

    elif name == "convert_url":
        return await handle_convert_url(arguments)

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def handle_convert_document(arguments: dict):
    """Convert a document to markdown/text."""
    output_format = arguments.get("output_format", "markdown")
    temp_file = None

    try:
        # Determine input source
        if "file_path" in arguments:
            file_path = Path(arguments["file_path"])
            if not file_path.exists():
                return [TextContent(type="text", text=f"Error: File not found: {file_path}")]

            ext = file_path.suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                return [TextContent(type="text", text=f"Error: Unsupported file format: {ext}")]

        elif "file_content_base64" in arguments and "filename" in arguments:
            # Decode base64 content to temp file
            content = base64.b64decode(arguments["file_content_base64"])
            filename = arguments["filename"]
            ext = Path(filename).suffix.lower()

            if ext not in SUPPORTED_EXTENSIONS:
                return [TextContent(type="text", text=f"Error: Unsupported file format: {ext}")]

            # Write to temp file
            temp_dir = tempfile.mkdtemp()
            temp_file = Path(temp_dir) / filename
            temp_file.write_bytes(content)
            file_path = temp_file

        else:
            return [TextContent(type="text", text="Error: Provide either file_path or file_content_base64 with filename")]

        # Convert document
        markdown_content = converter.convert_to_string(file_path)

        # Convert to plain text if requested
        if output_format == "text":
            final_content = markdown_to_text(markdown_content)
        else:
            final_content = markdown_content

        return [TextContent(type="text", text=final_content)]

    except Exception as e:
        return [TextContent(type="text", text=f"Error converting document: {str(e)}")]

    finally:
        # Cleanup temp file
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
                temp_file.parent.rmdir()
            except Exception:
                pass


async def handle_list_formats():
    """List supported formats."""
    formats_by_category = {
        "Documents": [".pdf", ".docx", ".doc", ".txt"],
        "Spreadsheets": [".xlsx", ".xls", ".csv"],
        "Presentations": [".pptx", ".ppt"],
        "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp"],
        "Web": [".html", ".htm", ".json", ".xml"],
        "E-books": [".epub"]
    }

    result = "# Supported File Formats\n\n"
    for category, formats in formats_by_category.items():
        result += f"## {category}\n"
        result += ", ".join(f"`{fmt}`" for fmt in formats) + "\n\n"

    return [TextContent(type="text", text=result)]


async def handle_convert_url(arguments: dict):
    """Fetch and convert a document from URL."""
    import requests

    url = arguments.get("url")
    output_format = arguments.get("output_format", "markdown")

    if not url:
        return [TextContent(type="text", text="Error: URL is required")]

    temp_file = None
    try:
        # Fetch the document
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()

        # Determine filename from URL or Content-Disposition
        content_disposition = response.headers.get("Content-Disposition", "")
        if "filename=" in content_disposition:
            filename = content_disposition.split("filename=")[1].strip('"\'')
        else:
            filename = Path(url.split("?")[0]).name or "document"

        # Ensure it has an extension
        if "." not in filename:
            content_type = response.headers.get("Content-Type", "")
            ext_map = {
                "application/pdf": ".pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
                "application/msword": ".doc",
                "text/html": ".html",
                "text/plain": ".txt",
            }
            ext = ext_map.get(content_type.split(";")[0], ".html")
            filename += ext

        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return [TextContent(type="text", text=f"Error: Unsupported file format: {ext}")]

        # Save to temp file
        temp_dir = tempfile.mkdtemp()
        temp_file = Path(temp_dir) / filename
        temp_file.write_bytes(response.content)

        # Convert
        markdown_content = converter.convert_to_string(temp_file)

        if output_format == "text":
            final_content = markdown_to_text(markdown_content)
        else:
            final_content = markdown_content

        return [TextContent(type="text", text=final_content)]

    except requests.exceptions.RequestException as e:
        return [TextContent(type="text", text=f"Error fetching URL: {str(e)}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error converting document: {str(e)}")]
    finally:
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
                temp_file.parent.rmdir()
            except Exception:
                pass


@server.list_resources()
async def list_resources():
    """List available resources."""
    return [
        Resource(
            uri="docssite://formats",
            name="Supported Formats",
            description="List of supported file formats for conversion",
            mimeType="text/markdown"
        ),
        Resource(
            uri="docssite://api-info",
            name="API Information",
            description="Information about the DocsSite conversion API",
            mimeType="text/markdown"
        )
    ]


@server.read_resource()
async def read_resource(uri: str):
    """Read a resource."""
    if uri == "docssite://formats":
        result = await handle_list_formats()
        return result[0].text

    elif uri == "docssite://api-info":
        return """# DocsSite Document Converter

A production-grade document to Markdown conversion service.

## Features

- **Instant Conversion**: Convert PDF, Word, Excel, PowerPoint, images, and more to Markdown
- **Output Formats**: Markdown (.md) or Plain Text (.txt)
- **Privacy First**: Files are processed and immediately deleted
- **No Registration**: Open access, no API key required for basic usage

## API Endpoint

```
POST https://paulocadias.com/api/convert
```

## Usage with cURL

```bash
curl -X POST -F "file=@document.pdf" https://paulocadias.com/api/convert
```

## Rate Limits

- Default: 20 requests/minute
- With API key: Up to 10,000 requests/minute

## More Information

Visit https://paulocadias.com/api/docs for full documentation.
"""

    return f"Unknown resource: {uri}"


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
