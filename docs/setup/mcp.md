# MCP Server Setup Guide - MegaDoc

## What is MCP?

**Model Context Protocol (MCP)** allows AI assistants and IDEs to directly use your document conversion service as a tool. This means AI agents can convert documents automatically!

**Supported AI Assistants & IDEs**:
- 🤖 **Claude Desktop** - Anthropic's desktop app
- 💻 **Cursor** - AI-powered code editor
- 🧠 **Antigravity** - Google DeepMind's coding assistant
- 📝 **VS Code** - With MCP extensions
- 🔧 **Any MCP-compatible tool** - Growing ecosystem!

---

## Quick Setup by IDE/Assistant

### 🤖 Claude Desktop

**1. Locate Config File**:
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Mac**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

**2. Add MegaDoc Server**:
```json
{
  "mcpServers": {
    "megadoc": {
      "command": "python",
      "args": ["C:\\BOT\\MegadocE\\DocsSite\\mcp_server.py"],
      "env": {}
    }
  }
}
```

**3. Restart Claude Desktop**

**4. Test**: "Convert this PDF to Markdown" + attach file

---

### 💻 Cursor

**1. Open Cursor Settings**:
- Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (Mac)
- Type "MCP Settings"

**2. Add MegaDoc Server**:
```json
{
  "mcpServers": {
    "megadoc": {
      "command": "python",
      "args": ["C:\\BOT\\MegadocE\\DocsSite\\mcp_server.py"]
    }
  }
}
```

**3. Reload Cursor**: `Ctrl+Shift+P` → "Reload Window"

**4. Test**: Ask Cursor AI to convert a document in your workspace

---

### 🧠 Antigravity (Google DeepMind)

**1. Access MCP Configuration**:
- Open Antigravity settings
- Navigate to "Model Context Protocol" section

**2. Add Server**:
```json
{
  "servers": {
    "megadoc": {
      "type": "stdio",
      "command": "python",
      "args": ["C:\\BOT\\MegadocE\\DocsSite\\mcp_server.py"],
      "description": "Document conversion to Markdown"
    }
  }
}
```

**3. Restart Antigravity**

**4. Test**: Request document conversion in a coding task

---

### 📝 VS Code (with MCP Extension)

**1. Install MCP Extension**:
- Open Extensions (`Ctrl+Shift+X`)
- Search for "Model Context Protocol"
- Install the MCP extension

**2. Configure MCP Servers**:
- Open Settings (`Ctrl+,`)
- Search for "MCP Servers"
- Add configuration:

```json
{
  "mcp.servers": {
    "megadoc": {
      "command": "python",
      "args": ["C:\\BOT\\MegadocE\\DocsSite\\mcp_server.py"],
      "description": "MegaDoc - Document to Markdown converter"
    }
  }
}
```

**3. Reload VS Code**

**4. Test**: Use AI assistant features with document conversion

---

### 🔧 Generic MCP Client

For any MCP-compatible tool:

**Configuration Format**:
```json
{
  "command": "python",
  "args": ["C:\\BOT\\MegadocE\\DocsSite\\mcp_server.py"],
  "type": "stdio",
  "env": {}
}
```

**Connection Method**: STDIO (Standard Input/Output)

---

## Available MCP Tools

### 1. `convert_document`
Convert any supported document to Markdown or plain text.

**Parameters**:
- `file_path` (required): Path to the document
- `output_format` (optional): "markdown" or "text" (default: "markdown")

**Example Use Cases**:
- **Claude**: "Convert report.pdf to Markdown"
- **Cursor**: "Extract code from this Word doc"
- **Antigravity**: "Parse this Excel file for data analysis"
- **VS Code**: "Convert presentation to text for documentation"

### 2. `convert_document_base64`
Convert a base64-encoded document (for when file isn't on disk).

**Parameters**:
- `content` (required): Base64-encoded file content
- `filename` (required): Original filename (for format detection)
- `output_format` (optional): "markdown" or "text"

**Example Use Cases**:
- User uploads file in chat
- AI encodes to base64
- Converts without saving to disk
- Returns converted content

---

## Supported File Formats

- **Documents**: PDF, Word (.docx, .doc), Text
- **Spreadsheets**: Excel (.xlsx, .xls), CSV
- **Presentations**: PowerPoint (.pptx, .ppt)
- **Images**: JPG, PNG, GIF, BMP (OCR)
- **Web**: HTML, JSON, XML
- **E-books**: EPUB

---

## Platform-Specific Paths

### Windows
```json
{
  "command": "python",
  "args": ["C:\\BOT\\MegadocE\\DocsSite\\mcp_server.py"]
}
```

### Mac/Linux
```json
{
  "command": "python3",
  "args": ["/Users/username/DocsSite/mcp_server.py"]
}
```

### With Virtual Environment

**Windows**:
```json
{
  "command": "C:\\BOT\\MegadocE\\DocsSite\\venv\\Scripts\\python.exe",
  "args": ["C:\\BOT\\MegadocE\\DocsSite\\mcp_server.py"]
}
```

**Mac/Linux**:
```json
{
  "command": "/Users/username/DocsSite/venv/bin/python",
  "args": ["/Users/username/DocsSite/mcp_server.py"]
}
```

---

## Testing the MCP Server

### Test Locally (Without IDE)

```bash
# Run the server
python mcp_server.py

# It will start and wait for MCP commands
# Press Ctrl+C to stop
```

### Test with MCP Inspector

```bash
# Install MCP inspector
npm install -g @modelcontextprotocol/inspector

# Run inspector
mcp-inspector python mcp_server.py
```

This opens a web UI to test your MCP server!

---

## Troubleshooting

### "Server not found" in IDE

**Solution**:
1. Check the path in config is correct (use absolute paths)
2. Make sure Python is in your PATH
3. Restart the IDE completely
4. Check IDE logs for MCP errors

### "Import error" when starting

**Solution**:
```bash
# Install dependencies
cd C:\BOT\MegadocE\DocsSite
pip install -r requirements.txt
```

### "Permission denied"

**Solution**:
- Windows: No special permissions needed
- Mac/Linux: `chmod +x mcp_server.py`

### Server crashes

**Solution**:
- Check IDE logs (location varies by IDE)
- Run server manually to see errors: `python mcp_server.py`
- Verify Python version: `python --version` (3.8+ required)

---

## IDE-Specific Troubleshooting

### Claude Desktop
- **Logs**: `%APPDATA%\Claude\logs\mcp-server-megadoc.log`
- **Config**: `%APPDATA%\Claude\claude_desktop_config.json`

### Cursor
- **Logs**: Check Developer Tools (`Ctrl+Shift+I`)
- **Config**: Cursor Settings → MCP

### VS Code
- **Logs**: Output panel → Select "MCP"
- **Config**: Settings → Search "MCP"

### Antigravity
- **Logs**: Check Antigravity console
- **Config**: Antigravity settings panel

---

## Example Use Cases Across IDEs

### 1. Document Analysis (Claude)
```
User: "Analyze this contract PDF and summarize key points"
Claude: Uses MCP to convert PDF → Analyzes Markdown → Provides summary
```

### 2. Code Extraction (Cursor)
```
Developer: "Extract code snippets from this documentation PDF"
Cursor: Uses MCP to convert → Parses code blocks → Inserts into editor
```

### 3. Data Processing (Antigravity)
```
Task: "Process Excel data for analysis"
Antigravity: Uses MCP to convert → Extracts tables → Generates code
```

### 4. Documentation (VS Code)
```
Writer: "Convert these Word docs to Markdown for our wiki"
VS Code: Uses MCP → Batch converts → Formats for documentation
```

---

## Production Deployment

### Local Development (Recommended)
- MCP server runs on your machine
- Direct file access
- No network latency
- Maximum security

### Remote Server (Advanced)
If you want to connect to your GCP deployment:

```json
{
  "command": "ssh",
  "args": [
    "your-gcp-server",
    "cd /path/to/DocsSite && python mcp_server.py"
  ]
}
```

**Note**: Most IDEs work best with local MCP servers.

---

## Security Notes

### Local MCP Server
- ✅ Runs on your machine
- ✅ No network exposure
- ✅ Direct file access
- ✅ No authentication needed
- ✅ Perfect for development

### Remote MCP Server
- ⚠️ Requires SSH/network access
- ⚠️ Network latency
- ⚠️ Consider authentication
- ⚠️ Use VPN if possible

---

## MCP Resources

- **MCP Specification**: https://modelcontextprotocol.io/
- **MCP Python SDK**: https://github.com/modelcontextprotocol/python-sdk
- **MCP Inspector**: https://github.com/modelcontextprotocol/inspector
- **Claude Desktop**: https://claude.ai/download
- **Cursor**: https://cursor.sh/
- **VS Code MCP Extension**: Search in VS Code marketplace

---

## Next Steps

### For Claude Desktop Users:
1. ✅ Add MegaDoc to `claude_desktop_config.json`
2. ✅ Restart Claude
3. ✅ Test with a document

### For Cursor Users:
1. ✅ Add MegaDoc to Cursor MCP settings
2. ✅ Reload window
3. ✅ Test in your workspace

### For Antigravity Users:
1. ✅ Configure MCP server in settings
2. ✅ Restart Antigravity
3. ✅ Test in a coding task

### For VS Code Users:
1. ✅ Install MCP extension
2. ✅ Configure server
3. ✅ Test with AI assistant

### For Other IDEs:
1. ✅ Check if MCP is supported
2. ✅ Use generic STDIO configuration
3. ✅ Test and report compatibility!

---

## Support

If you encounter issues:
1. Check your IDE's MCP logs
2. Run `python mcp_server.py` manually to see errors
3. Verify all dependencies: `pip install -r requirements.txt`
4. Check Python version: `python --version` (3.8+ required)
5. Try the MCP Inspector for debugging

**Your MCP server works with any MCP-compatible IDE or AI assistant! 🚀**


---

## Available MCP Tools

### 1. `convert_document`
Convert any supported document to Markdown or plain text.

**Parameters**:
- `file_path` (required): Path to the document
- `output_format` (optional): "markdown" or "text" (default: "markdown")

**Example**:
```
Claude: "Convert report.pdf to Markdown"
→ Uses convert_document tool
→ Returns Markdown content
```

### 2. `convert_document_base64`
Convert a base64-encoded document (for when file isn't on disk).

**Parameters**:
- `content` (required): Base64-encoded file content
- `filename` (required): Original filename (for format detection)
- `output_format` (optional): "markdown" or "text"

**Example**:
```
Claude: User uploads file in chat
→ Claude encodes to base64
→ Uses convert_document_base64
→ Returns converted content
```

---

## Supported File Formats

- **Documents**: PDF, Word (.docx, .doc), Text
- **Spreadsheets**: Excel (.xlsx, .xls), CSV
- **Presentations**: PowerPoint (.pptx, .ppt)
- **Images**: JPG, PNG, GIF, BMP (OCR)
- **Web**: HTML, JSON, XML
- **E-books**: EPUB

---

## Advanced Configuration

### Custom Python Environment

If using a virtual environment:

```json
{
  "mcpServers": {
    "megadoc": {
      "command": "C:\\BOT\\MegadocE\\DocsSite\\venv\\Scripts\\python.exe",
      "args": ["C:\\BOT\\MegadocE\\DocsSite\\mcp_server.py"],
      "env": {}
    }
  }
}
```

### Environment Variables

Add custom settings:

```json
{
  "mcpServers": {
    "megadoc": {
      "command": "python",
      "args": ["C:\\BOT\\MegadocE\\DocsSite\\mcp_server.py"],
      "env": {
        "MAX_FILE_SIZE": "52428800",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

---

## Testing the MCP Server

### Test Locally (Without Claude)

```bash
# Run the server
python mcp_server.py

# It will start and wait for MCP commands
# Press Ctrl+C to stop
```

### Test with MCP Inspector

```bash
# Install MCP inspector
npm install -g @modelcontextprotocol/inspector

# Run inspector
mcp-inspector python mcp_server.py
```

This opens a web UI to test your MCP server!

---

## Troubleshooting

### "Server not found" in Claude

**Solution**:
1. Check the path in `claude_desktop_config.json` is correct
2. Make sure Python is in your PATH
3. Restart Claude Desktop completely
4. Check Claude's logs: `%APPDATA%\Claude\logs`

### "Import error" when starting

**Solution**:
```bash
# Install dependencies
cd C:\BOT\MegadocE\DocsSite
pip install -r requirements.txt
```

### "Permission denied"

**Solution**:
- Make sure `mcp_server.py` is executable
- On Windows, no special permissions needed
- On Mac/Linux: `chmod +x mcp_server.py`

### Server crashes

**Solution**:
- Check Claude's logs: `%APPDATA%\Claude\logs\mcp-server-megadoc.log`
- Run server manually to see errors: `python mcp_server.py`

---

## Production Deployment

### Running MCP Server on GCP

The MCP server is designed for **local use** with Claude Desktop. For production:

1. **Local Development**: Use MCP with Claude Desktop
2. **Production API**: Users call your REST API directly
3. **Hybrid**: Run MCP server locally, pointing to production API

### Remote MCP Server (Advanced)

If you want Claude to connect to your GCP server:

```json
{
  "mcpServers": {
    "megadoc-remote": {
      "command": "ssh",
      "args": [
        "your-gcp-server",
        "cd /path/to/DocsSite && python mcp_server.py"
      ]
    }
  }
}
```

---

## Security Notes

### Local MCP Server
- ✅ Runs on your machine
- ✅ No network exposure
- ✅ Direct file access
- ✅ No authentication needed

### Remote MCP Server
- ⚠️ Requires SSH access
- ⚠️ Network latency
- ⚠️ Consider authentication
- ⚠️ Use VPN if possible

---

## Example Use Cases

### 1. Document Analysis
```
User: "Analyze this contract PDF and summarize key points"
Claude: Uses MCP to convert PDF → Analyzes Markdown → Provides summary
```

### 2. Batch Processing
```
User: "Convert all PDFs in this folder to Markdown"
Claude: Uses MCP repeatedly → Converts each file → Returns results
```

### 3. Data Extraction
```
User: "Extract tables from this Excel file"
Claude: Uses MCP to convert → Parses Markdown tables → Returns data
```

### 4. Content Migration
```
User: "Convert these Word docs to clean text for my blog"
Claude: Uses MCP → Converts to text → Formats for blog
```

---

## MCP Resources

- **MCP Specification**: https://modelcontextprotocol.io/
- **MCP Python SDK**: https://github.com/modelcontextprotocol/python-sdk
- **Claude Desktop**: https://claude.ai/download
- **MCP Inspector**: https://github.com/modelcontextprotocol/inspector

---

## Next Steps

1. ✅ Install Claude Desktop
2. ✅ Add MegaDoc to `claude_desktop_config.json`
3. ✅ Restart Claude
4. ✅ Test with a document
5. 🎉 Enjoy AI-powered document conversion!

---

## Support

If you encounter issues:
1. Check Claude's logs: `%APPDATA%\Claude\logs`
2. Run `python mcp_server.py` manually to see errors
3. Verify all dependencies: `pip install -r requirements.txt`
4. Check Python version: `python --version` (3.8+ required)

**Your MCP server is ready to empower Claude with document conversion! 🚀**
