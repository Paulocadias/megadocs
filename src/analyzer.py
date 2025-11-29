"""
Document Analysis Module for MegaDoc.

Provides text analysis features including:
- Word/character/sentence/paragraph counts
- Reading time estimation
- Keyword extraction (TF-IDF)
- Readability scores (Flesch-Kincaid)
- Language detection
- Document structure analysis

All processing is done offline - no external API calls.
"""

import re
import logging
from typing import Dict, Any, List
from collections import Counter

# NLP libraries (all offline processing)
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import textstat
    TEXTSTAT_AVAILABLE = True
except ImportError:
    TEXTSTAT_AVAILABLE = False

try:
    from langdetect import detect, LangDetectException
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

logger = logging.getLogger(__name__)


def analyze_document(markdown_content: str) -> Dict[str, Any]:
    """
    Perform comprehensive analysis on markdown content.

    Args:
        markdown_content: The markdown text to analyze

    Returns:
        Dictionary containing all analysis results
    """
    if not markdown_content or not markdown_content.strip():
        return {"error": "No content to analyze"}

    # Clean text (remove markdown syntax for accurate word counts)
    plain_text = _markdown_to_plain(markdown_content)

    # Basic counts
    basic_stats = _get_basic_stats(plain_text)

    # Reading time (average 200 words per minute)
    reading_time = _estimate_reading_time(basic_stats["word_count"])

    # Document structure (analyze markdown)
    structure = _analyze_structure(markdown_content)

    # Keywords (TF-IDF)
    keywords = _extract_keywords(plain_text)

    # Readability scores
    readability = _get_readability_scores(plain_text)

    # Language detection
    language = _detect_language(plain_text)

    return {
        "basic_stats": basic_stats,
        "reading_time": reading_time,
        "structure": structure,
        "keywords": keywords,
        "readability": readability,
        "language": language
    }


def _markdown_to_plain(markdown: str) -> str:
    """Remove markdown syntax to get plain text."""
    text = markdown

    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]+`', '', text)

    # Remove headers markers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Remove bold/italic
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)

    # Remove links but keep text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

    # Remove images
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', text)

    # Remove blockquotes
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)

    # Remove list markers
    text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)

    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}$', '', text, flags=re.MULTILINE)

    # Clean up whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def _get_basic_stats(text: str) -> Dict[str, int]:
    """Get basic text statistics."""
    # Word count (split on whitespace)
    words = text.split()
    word_count = len(words)

    # Character counts
    char_count = len(text)
    char_count_no_spaces = len(text.replace(' ', '').replace('\n', '').replace('\t', ''))

    # Sentence count (rough estimation)
    sentences = re.split(r'[.!?]+', text)
    sentence_count = len([s for s in sentences if s.strip()])

    # Paragraph count
    paragraphs = text.split('\n\n')
    paragraph_count = len([p for p in paragraphs if p.strip()])

    # Average word length
    avg_word_length = sum(len(w) for w in words) / max(word_count, 1)

    # Average sentence length
    avg_sentence_length = word_count / max(sentence_count, 1)

    return {
        "word_count": word_count,
        "character_count": char_count,
        "character_count_no_spaces": char_count_no_spaces,
        "sentence_count": sentence_count,
        "paragraph_count": paragraph_count,
        "average_word_length": round(avg_word_length, 1),
        "average_sentence_length": round(avg_sentence_length, 1)
    }


def _estimate_reading_time(word_count: int) -> Dict[str, Any]:
    """Estimate reading time based on word count."""
    # Average reading speed: 200-250 words per minute
    minutes = word_count / 200

    if minutes < 1:
        display = "Less than 1 minute"
    elif minutes < 2:
        display = "About 1 minute"
    else:
        display = f"About {round(minutes)} minutes"

    return {
        "minutes": round(minutes, 1),
        "display": display,
        "words_per_minute": 200
    }


def _analyze_structure(markdown: str) -> Dict[str, int]:
    """Analyze markdown document structure."""
    # Count headers by level
    h1_count = len(re.findall(r'^#\s+', markdown, re.MULTILINE))
    h2_count = len(re.findall(r'^##\s+', markdown, re.MULTILINE))
    h3_count = len(re.findall(r'^###\s+', markdown, re.MULTILINE))
    h4_plus_count = len(re.findall(r'^#{4,6}\s+', markdown, re.MULTILINE))

    # Count lists
    bullet_items = len(re.findall(r'^[\s]*[-*+]\s+', markdown, re.MULTILINE))
    numbered_items = len(re.findall(r'^[\s]*\d+\.\s+', markdown, re.MULTILINE))

    # Count code blocks
    code_blocks = len(re.findall(r'```', markdown)) // 2
    inline_code = len(re.findall(r'`[^`]+`', markdown))

    # Count links and images
    links = len(re.findall(r'\[([^\]]+)\]\([^)]+\)', markdown))
    images = len(re.findall(r'!\[([^\]]*)\]\([^)]+\)', markdown))

    # Count blockquotes
    blockquotes = len(re.findall(r'^>\s+', markdown, re.MULTILINE))

    # Count tables (markdown tables have | separators)
    table_rows = len(re.findall(r'^\|.+\|$', markdown, re.MULTILINE))

    return {
        "headers": {
            "h1": h1_count,
            "h2": h2_count,
            "h3": h3_count,
            "h4_plus": h4_plus_count,
            "total": h1_count + h2_count + h3_count + h4_plus_count
        },
        "lists": {
            "bullet_items": bullet_items,
            "numbered_items": numbered_items,
            "total_items": bullet_items + numbered_items
        },
        "code": {
            "code_blocks": code_blocks,
            "inline_code": inline_code
        },
        "links": links,
        "images": images,
        "blockquotes": blockquotes,
        "table_rows": table_rows
    }


def _extract_keywords(text: str, top_n: int = 10) -> List[Dict[str, Any]]:
    """Extract keywords using TF-IDF."""
    if not SKLEARN_AVAILABLE:
        # Fallback: simple word frequency
        return _simple_keyword_extraction(text, top_n)

    if len(text.split()) < 5:
        return []

    try:
        # Use TF-IDF with single document (treat sentences as documents)
        sentences = re.split(r'[.!?\n]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        if len(sentences) < 2:
            return _simple_keyword_extraction(text, top_n)

        # TF-IDF vectorizer
        vectorizer = TfidfVectorizer(
            max_features=100,
            stop_words='english',
            ngram_range=(1, 2),  # Include bigrams
            min_df=1,
            max_df=0.9
        )

        tfidf_matrix = vectorizer.fit_transform(sentences)
        feature_names = vectorizer.get_feature_names_out()

        # Get average TF-IDF scores across all sentences
        avg_scores = tfidf_matrix.mean(axis=0).A1

        # Sort by score
        keyword_scores = list(zip(feature_names, avg_scores))
        keyword_scores.sort(key=lambda x: x[1], reverse=True)

        # Return top keywords
        return [
            {"keyword": kw, "score": round(score, 4)}
            for kw, score in keyword_scores[:top_n]
            if score > 0
        ]

    except Exception as e:
        logger.warning(f"TF-IDF extraction failed: {e}")
        return _simple_keyword_extraction(text, top_n)


def _simple_keyword_extraction(text: str, top_n: int = 10) -> List[Dict[str, Any]]:
    """Simple keyword extraction based on word frequency."""
    # Common stop words
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
        'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
        'it', 'its', 'this', 'that', 'these', 'those', 'i', 'you', 'he',
        'she', 'we', 'they', 'what', 'which', 'who', 'when', 'where', 'why',
        'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other',
        'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so',
        'than', 'too', 'very', 'just', 'also', 'now', 'here', 'there'
    }

    # Tokenize and filter
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    words = [w for w in words if w not in stop_words]

    # Count frequencies
    word_counts = Counter(words)
    total_words = len(words)

    # Calculate scores (normalized frequency)
    keywords = [
        {"keyword": word, "score": round(count / total_words, 4)}
        for word, count in word_counts.most_common(top_n)
    ]

    return keywords


def _get_readability_scores(text: str) -> Dict[str, Any]:
    """Calculate readability scores."""
    if not TEXTSTAT_AVAILABLE:
        return {"available": False, "message": "textstat library not installed"}

    if len(text.split()) < 10:
        return {"available": False, "message": "Not enough text for readability analysis"}

    try:
        # Flesch Reading Ease (0-100, higher = easier)
        flesch_reading_ease = textstat.flesch_reading_ease(text)

        # Flesch-Kincaid Grade Level
        flesch_kincaid_grade = textstat.flesch_kincaid_grade(text)

        # Gunning Fog Index
        gunning_fog = textstat.gunning_fog(text)

        # SMOG Index
        smog_index = textstat.smog_index(text)

        # Automated Readability Index
        ari = textstat.automated_readability_index(text)

        # Coleman-Liau Index
        coleman_liau = textstat.coleman_liau_index(text)

        # Reading level interpretation
        if flesch_reading_ease >= 90:
            level = "Very Easy (5th grade)"
        elif flesch_reading_ease >= 80:
            level = "Easy (6th grade)"
        elif flesch_reading_ease >= 70:
            level = "Fairly Easy (7th grade)"
        elif flesch_reading_ease >= 60:
            level = "Standard (8th-9th grade)"
        elif flesch_reading_ease >= 50:
            level = "Fairly Difficult (10th-12th grade)"
        elif flesch_reading_ease >= 30:
            level = "Difficult (College)"
        else:
            level = "Very Difficult (Graduate)"

        return {
            "available": True,
            "flesch_reading_ease": round(flesch_reading_ease, 1),
            "flesch_kincaid_grade": round(flesch_kincaid_grade, 1),
            "gunning_fog": round(gunning_fog, 1),
            "smog_index": round(smog_index, 1),
            "automated_readability_index": round(ari, 1),
            "coleman_liau_index": round(coleman_liau, 1),
            "reading_level": level
        }

    except Exception as e:
        logger.warning(f"Readability calculation failed: {e}")
        return {"available": False, "message": str(e)}


def _detect_language(text: str) -> Dict[str, Any]:
    """Detect the language of the text."""
    if not LANGDETECT_AVAILABLE:
        return {"available": False, "message": "langdetect library not installed"}

    if len(text.split()) < 5:
        return {"available": False, "message": "Not enough text for language detection"}

    try:
        language_code = detect(text)

        # Map common language codes to names
        language_names = {
            'en': 'English',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese',
            'nl': 'Dutch',
            'pl': 'Polish',
            'ru': 'Russian',
            'ja': 'Japanese',
            'ko': 'Korean',
            'zh-cn': 'Chinese (Simplified)',
            'zh-tw': 'Chinese (Traditional)',
            'ar': 'Arabic',
            'hi': 'Hindi',
            'tr': 'Turkish',
            'sv': 'Swedish',
            'da': 'Danish',
            'no': 'Norwegian',
            'fi': 'Finnish'
        }

        language_name = language_names.get(language_code, language_code.upper())

        return {
            "available": True,
            "code": language_code,
            "name": language_name
        }

    except LangDetectException as e:
        return {"available": False, "message": "Could not detect language"}
    except Exception as e:
        logger.warning(f"Language detection failed: {e}")
        return {"available": False, "message": str(e)}
