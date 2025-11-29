import re
import os
from werkzeug.utils import secure_filename

def markdown_to_text(markdown_content):
    """
    Convert Markdown to clean formatted plain text.
    Removes all markdown syntax while preserving text structure.
    """
    text = markdown_content

    # Remove code blocks but keep content (fenced)
    text = re.sub(r'```[\w]*\n?(.*?)```', r'\1', text, flags=re.DOTALL)

    # Remove inline code backticks
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # Convert headers to plain text (keep the text, remove #)
    text = re.sub(r'^#{1,6}\s*(.+)$', r'\1', text, flags=re.MULTILINE)

    # Remove bold/italic (handle combined **_text_** patterns)
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', text)  # ***bold italic***
    text = re.sub(r'___(.+?)___', r'\1', text)        # ___bold italic___
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)      # **bold**
    text = re.sub(r'__(.+?)__', r'\1', text)          # __bold__
    text = re.sub(r'\*(.+?)\*', r'\1', text)          # *italic*
    text = re.sub(r'_(.+?)_', r'\1', text)            # _italic_
    text = re.sub(r'~~(.+?)~~', r'\1', text)          # ~~strikethrough~~

    # Convert links [text](url) to just text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    # Remove images ![alt](url) -> alt text
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)

    # Remove reference links [text][ref]
    text = re.sub(r'\[([^\]]+)\]\[[^\]]*\]', r'\1', text)

    # Remove reference definitions [ref]: url
    text = re.sub(r'^\[[^\]]+\]:\s*\S+.*$', '', text, flags=re.MULTILINE)

    # Convert blockquotes (remove >)
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)

    # Convert bullet lists to simple bullets
    text = re.sub(r'^[\s]*[-*+]\s+', '• ', text, flags=re.MULTILINE)

    # Keep numbered lists but clean them up
    text = re.sub(r'^[\s]*(\d+)\.\s+', r'\1. ', text, flags=re.MULTILINE)

    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)

    # Remove HTML tags if any
    text = re.sub(r'<[^>]+>', '', text)

    # Clean up excessive blank lines (more than 2 consecutive)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove leading/trailing whitespace from lines
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)

    # Final cleanup - remove leading/trailing whitespace
    text = text.strip()

    return text


def sanitize_filename(filename):
    """Sanitize filename to prevent path traversal and other attacks."""
    if not filename:
        return None

    # Use werkzeug's secure_filename first
    filename = secure_filename(filename)

    if not filename:
        return None

    # Additional sanitization
    # Remove any remaining path separators
    filename = filename.replace('/', '').replace('\\', '')

    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255-len(ext)] + ext

    # Ensure it has an extension
    if '.' not in filename:
        return None

    return filename
