import re
import os
import json
import xml.etree.ElementTree as ET
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


def remove_macros(content: str) -> str:
    """
    Remove macro-like patterns from content (VBA, Office macros, etc.).
    This is a basic implementation that removes common macro patterns.
    """
    # Remove VBA-style macros
    content = re.sub(r'(?i)Sub\s+\w+.*?End\s+Sub', '', content, flags=re.DOTALL)
    content = re.sub(r'(?i)Function\s+\w+.*?End\s+Function', '', content, flags=re.DOTALL)
    
    # Remove Office macro references
    content = re.sub(r'(?i)\{?MACRO\w+\}?', '', content)
    content = re.sub(r'(?i)\{?DDE\w+\}?', '', content)
    
    # Remove embedded script patterns
    content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'javascript:', '', content, flags=re.IGNORECASE)
    
    return content


def strip_metadata(content: str) -> str:
    """
    Strip metadata patterns from content (author info, creation dates, etc.).
    """
    # Remove common metadata patterns
    content = re.sub(r'(?i)Author:\s*[^\n]+', '', content)
    content = re.sub(r'(?i)Created:\s*[^\n]+', '', content)
    content = re.sub(r'(?i)Modified:\s*[^\n]+', '', content)
    content = re.sub(r'(?i)Creator:\s*[^\n]+', '', content)
    content = re.sub(r'(?i)Producer:\s*[^\n]+', '', content)
    content = re.sub(r'(?i)Keywords:\s*[^\n]+', '', content)
    content = re.sub(r'(?i)Subject:\s*[^\n]+', '', content)
    
    # Remove XML metadata tags
    content = re.sub(r'<meta[^>]*>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'<dc:creator[^>]*>.*?</dc:creator>', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'<dc:date[^>]*>.*?</dc:date>', '', content, flags=re.DOTALL | re.IGNORECASE)
    
    return content


def redact_emails(content: str) -> str:
    """
    Redact email addresses from content, replacing with [EMAIL_REDACTED].
    """
    # Email regex pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    content = re.sub(email_pattern, '[EMAIL_REDACTED]', content)
    return content


def format_as_json(content: str, filename: str) -> str:
    """
    Format content as structured JSON.
    """
    # Split content into sections (headers as keys)
    lines = content.split('\n')
    sections = []
    current_section = {'type': 'paragraph', 'content': ''}
    
    for line in lines:
        line = line.strip()
        if not line:
            if current_section['content']:
                sections.append(current_section)
                current_section = {'type': 'paragraph', 'content': ''}
            continue
        
        # Check if it's a header
        if line.startswith('#'):
            if current_section['content']:
                sections.append(current_section)
            level = len(line) - len(line.lstrip('#'))
            title = line.lstrip('#').strip()
            current_section = {
                'type': f'h{min(level, 6)}',
                'title': title,
                'content': ''
            }
        else:
            if current_section['content']:
                current_section['content'] += '\n'
            current_section['content'] += line
    
    if current_section['content']:
        sections.append(current_section)
    
    result = {
        'document': {
            'filename': filename,
            'sections': sections,
            'total_sections': len(sections)
        }
    }
    
    return json.dumps(result, indent=2, ensure_ascii=False)


def format_as_xml(content: str, filename: str) -> str:
    """
    Format content as structured XML.
    """
    root = ET.Element('document')
    root.set('filename', filename)
    body = ET.SubElement(root, 'body')
    
    lines = content.split('\n')
    current_para = None
    
    for line in lines:
        line = line.strip()
        if not line:
            current_para = None
            continue
        
        # Check if it's a header
        if line.startswith('#'):
            current_para = None
            level = len(line) - len(line.lstrip('#'))
            title = line.lstrip('#').strip()
            header_tag = f'h{min(level, 6)}'
            header_elem = ET.SubElement(body, header_tag)
            header_elem.text = title
        else:
            # Add as paragraph
            if current_para is None:
                current_para = ET.SubElement(body, 'p')
                current_para.text = line
            else:
                # Append to current paragraph
                if current_para.text:
                    current_para.text += '\n' + line
                else:
                    current_para.text = line
    
    # Convert to string with proper formatting
    try:
        ET.indent(root, space='  ')  # Python 3.9+
    except AttributeError:
        pass  # Fallback for older Python versions
    
    return ET.tostring(root, encoding='unicode', method='xml')
