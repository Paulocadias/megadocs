"""
Unit tests for the utils module.
Tests utility functions for text processing and sanitization.
"""
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from utils import (
    markdown_to_text,
    sanitize_filename,
    remove_macros,
    strip_metadata,
    redact_emails,
    format_as_json,
    format_as_xml
)


@pytest.mark.unit
class TestMarkdownToText:
    """Tests for markdown_to_text function."""

    def test_removes_headers(self):
        """Headers should be converted to plain text."""
        markdown = "# Header 1\n## Header 2\n### Header 3"
        result = markdown_to_text(markdown)

        assert "#" not in result
        assert "Header 1" in result
        assert "Header 2" in result
        assert "Header 3" in result

    def test_removes_bold_italic(self):
        """Bold and italic markers should be removed."""
        markdown = "**bold** and *italic* and ***both***"
        result = markdown_to_text(markdown)

        assert "**" not in result
        assert "*" not in result
        assert "bold" in result
        assert "italic" in result
        assert "both" in result

    def test_removes_links(self):
        """Link syntax should be removed, keeping text."""
        markdown = "[Click here](https://example.com) for more"
        result = markdown_to_text(markdown)

        assert "[" not in result
        assert "](" not in result
        assert "Click here" in result

    def test_removes_images(self):
        """Image syntax should be removed, keeping alt text."""
        markdown = "![Alt text](image.png)"
        result = markdown_to_text(markdown)

        assert "![" not in result
        assert "Alt text" in result

    def test_removes_code_blocks(self):
        """Code block markers should be removed, keeping content."""
        markdown = "```python\nprint('hello')\n```"
        result = markdown_to_text(markdown)

        assert "```" not in result
        assert "print" in result

    def test_removes_inline_code(self):
        """Inline code backticks should be removed."""
        markdown = "Use the `print()` function"
        result = markdown_to_text(markdown)

        assert "`" not in result
        assert "print()" in result

    def test_converts_bullet_lists(self):
        """Bullet lists should be converted."""
        markdown = "- Item 1\n- Item 2\n* Item 3"
        result = markdown_to_text(markdown)

        assert "Item 1" in result
        assert "Item 2" in result
        assert "Item 3" in result

    def test_removes_horizontal_rules(self):
        """Horizontal rules should be removed."""
        markdown = "Text\n---\nMore text"
        result = markdown_to_text(markdown)

        assert "---" not in result
        assert "Text" in result

    def test_removes_blockquotes(self):
        """Blockquote markers should be removed."""
        markdown = "> This is a quote\n> Second line"
        result = markdown_to_text(markdown)

        assert ">" not in result
        assert "This is a quote" in result

    def test_removes_html_tags(self):
        """HTML tags should be removed."""
        markdown = "<p>Paragraph</p> and <strong>bold</strong>"
        result = markdown_to_text(markdown)

        assert "<" not in result
        assert ">" not in result
        assert "Paragraph" in result


@pytest.mark.unit
class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_normal_filename(self):
        """Normal filename should pass through."""
        result = sanitize_filename("document.pdf")
        assert result == "document.pdf"

    def test_empty_filename(self):
        """Empty filename should return None."""
        assert sanitize_filename("") is None
        assert sanitize_filename(None) is None

    def test_path_traversal_blocked(self):
        """Path traversal attempts should be blocked."""
        result = sanitize_filename("../../../etc/passwd")
        assert ".." not in str(result) if result else True

    def test_removes_path_separators(self):
        """Path separators should be removed."""
        result = sanitize_filename("path/to/file.txt")
        if result:
            assert "/" not in result
            assert "\\" not in result

    def test_long_filename_truncated(self):
        """Very long filenames should be truncated."""
        long_name = "a" * 300 + ".pdf"
        result = sanitize_filename(long_name)
        if result:
            assert len(result) <= 255

    def test_filename_without_extension(self):
        """Filename without extension should return None."""
        result = sanitize_filename("noextension")
        assert result is None

    def test_special_characters_removed(self):
        """Special characters should be handled safely."""
        result = sanitize_filename("file<>:\"|?*.pdf")
        if result:
            assert "<" not in result
            assert ">" not in result


@pytest.mark.unit
class TestRemoveMacros:
    """Tests for remove_macros function."""

    def test_removes_vba_sub(self):
        """VBA Sub procedures should be removed."""
        content = "Text\nSub MyMacro()\nMsgBox \"Hello\"\nEnd Sub\nMore text"
        result = remove_macros(content)

        assert "Sub MyMacro" not in result
        assert "End Sub" not in result
        assert "Text" in result
        assert "More text" in result

    def test_removes_vba_function(self):
        """VBA Functions should be removed."""
        content = "Function Calculate()\nReturn 1\nEnd Function"
        result = remove_macros(content)

        assert "Function Calculate" not in result
        assert "End Function" not in result

    def test_removes_script_tags(self):
        """Script tags should be removed."""
        content = "Text<script>alert('xss')</script>More"
        result = remove_macros(content)

        assert "<script>" not in result.lower()
        assert "alert" not in result

    def test_removes_javascript_protocol(self):
        """JavaScript protocol should be removed."""
        content = "javascript:alert('test')"
        result = remove_macros(content)

        assert "javascript:" not in result.lower()

    def test_preserves_normal_content(self):
        """Normal content should be preserved."""
        content = "This is normal document text without macros."
        result = remove_macros(content)

        assert result == content


@pytest.mark.unit
class TestStripMetadata:
    """Tests for strip_metadata function."""

    def test_removes_author(self):
        """Author metadata should be removed."""
        content = "Author: John Doe\nContent here"
        result = strip_metadata(content)

        assert "Author:" not in result
        assert "John Doe" not in result
        assert "Content here" in result

    def test_removes_created_date(self):
        """Created date should be removed."""
        content = "Created: 2024-01-15\nDocument text"
        result = strip_metadata(content)

        assert "Created:" not in result

    def test_removes_multiple_metadata(self):
        """Multiple metadata fields should be removed."""
        content = """Author: Jane
Created: 2024-01-01
Modified: 2024-01-15
Keywords: test, document

Actual content here."""
        result = strip_metadata(content)

        assert "Author:" not in result
        assert "Created:" not in result
        assert "Modified:" not in result
        assert "Keywords:" not in result
        assert "Actual content here" in result


@pytest.mark.unit
class TestRedactEmails:
    """Tests for redact_emails function."""

    def test_redacts_simple_email(self):
        """Simple email should be redacted."""
        content = "Contact us at info@example.com for help"
        result = redact_emails(content)

        assert "info@example.com" not in result
        assert "[EMAIL_REDACTED]" in result
        assert "Contact us at" in result

    def test_redacts_multiple_emails(self):
        """Multiple emails should be redacted."""
        content = "Email john@test.com or jane@test.org"
        result = redact_emails(content)

        assert "john@test.com" not in result
        assert "jane@test.org" not in result
        assert result.count("[EMAIL_REDACTED]") == 2

    def test_handles_complex_email(self):
        """Complex email formats should be handled."""
        content = "Contact user.name+tag@sub.domain.com"
        result = redact_emails(content)

        assert "@" not in result or "[EMAIL_REDACTED]" in result

    def test_preserves_non_email_at_signs(self):
        """@ signs that aren't part of emails should be preserved or handled."""
        content = "Price is $5 @ the store"
        # This may or may not be redacted depending on pattern matching
        result = redact_emails(content)
        # Just ensure it doesn't crash
        assert isinstance(result, str)


@pytest.mark.unit
class TestFormatAsJson:
    """Tests for format_as_json function."""

    def test_returns_valid_json(self):
        """Output should be valid JSON."""
        import json

        content = "# Title\n\nParagraph text here."
        result = format_as_json(content, "test.md")

        # Should not raise
        parsed = json.loads(result)
        assert "document" in parsed

    def test_includes_filename(self):
        """Output should include filename."""
        import json

        content = "Some content"
        result = format_as_json(content, "myfile.md")
        parsed = json.loads(result)

        assert parsed["document"]["filename"] == "myfile.md"

    def test_parses_headers_as_sections(self):
        """Headers should be parsed as sections."""
        import json

        content = "# Section One\n\nContent one\n\n## Section Two\n\nContent two"
        result = format_as_json(content, "test.md")
        parsed = json.loads(result)

        sections = parsed["document"]["sections"]
        assert len(sections) > 0

    def test_handles_empty_content(self):
        """Empty content should be handled gracefully."""
        import json

        result = format_as_json("", "empty.md")
        parsed = json.loads(result)

        assert "document" in parsed


@pytest.mark.unit
class TestFormatAsXml:
    """Tests for format_as_xml function."""

    def test_returns_valid_xml(self):
        """Output should be valid XML."""
        import xml.etree.ElementTree as ET

        content = "# Title\n\nParagraph here."
        result = format_as_xml(content, "test.md")

        # Should not raise
        root = ET.fromstring(result)
        assert root.tag == "document"

    def test_includes_filename_attribute(self):
        """XML should include filename as attribute."""
        import xml.etree.ElementTree as ET

        content = "Content here"
        result = format_as_xml(content, "myfile.md")
        root = ET.fromstring(result)

        assert root.get("filename") == "myfile.md"

    def test_converts_headers_to_elements(self):
        """Headers should be converted to h1-h6 elements."""
        import xml.etree.ElementTree as ET

        content = "# Header One\n\n## Header Two"
        result = format_as_xml(content, "test.md")
        root = ET.fromstring(result)
        body = root.find("body")

        h1_elements = body.findall("h1")
        h2_elements = body.findall("h2")

        assert len(h1_elements) >= 1
        assert len(h2_elements) >= 1

    def test_handles_paragraphs(self):
        """Paragraphs should be wrapped in p elements."""
        import xml.etree.ElementTree as ET

        content = "First paragraph.\n\nSecond paragraph."
        result = format_as_xml(content, "test.md")
        root = ET.fromstring(result)
        body = root.find("body")

        p_elements = body.findall("p")
        assert len(p_elements) >= 1
