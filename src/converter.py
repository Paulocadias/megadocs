"""Document to Markdown converter using MarkItDown."""

import logging
from pathlib import Path
from typing import Optional

from markitdown import MarkItDown

logger = logging.getLogger(__name__)


class DocumentConverter:
    """Wrapper around MarkItDown for document conversion."""

    def __init__(self) -> None:
        """Initialize the converter."""
        self._markitdown = MarkItDown()

    def convert_file(self, input_path: Path, output_path: Optional[Path] = None) -> Path:
        """Convert a file to Markdown.

        Args:
            input_path: Path to the input file
            output_path: Optional custom output path

        Returns:
            Path to the created Markdown file

        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If conversion fails
        """
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        logger.info(f"Converting: {input_path}")

        try:
            result = self._markitdown.convert(str(input_path))
            markdown_content = result.text_content

            if output_path is None:
                output_path = input_path.with_suffix(".md")

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown_content, encoding="utf-8")

            logger.info(f"Created: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to convert {input_path}: {e}")
            raise ValueError(f"Conversion failed: {e}") from e

    def convert_to_string(self, input_path: Path) -> str:
        """Convert a file and return the Markdown content as string.

        Args:
            input_path: Path to the input file

        Returns:
            Markdown content as string

        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If conversion fails
        """
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        try:
            result = self._markitdown.convert(str(input_path))
            return result.text_content
        except Exception as e:
            logger.error(f"Failed to convert {input_path}: {e}")
            raise ValueError(f"Conversion failed: {e}") from e
