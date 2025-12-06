import os
import zipfile
import tempfile
import logging
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from converter import DocumentConverter
from utils import markdown_to_text

logger = logging.getLogger(__name__)

class BatchService:
    """
    Handles batch processing of documents via ZIP archives.
    """
    def __init__(self, max_workers=4):
        self.converter = DocumentConverter()
        self.max_workers = max_workers

    def process_zip(self, zip_path: Path, output_format: str = 'markdown') -> Path:
        """
        Process a ZIP file containing documents.
        Returns path to the resulting ZIP file.
        """
        temp_dir = Path(tempfile.mkdtemp())
        extract_dir = temp_dir / "input"
        output_dir = temp_dir / "output"
        extract_dir.mkdir()
        output_dir.mkdir()

        try:
            # Extract ZIP
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            # Find all files
            files = [f for f in extract_dir.rglob("*") if f.is_file() and not f.name.startswith('.')]
            
            results = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_file = {
                    executor.submit(self._process_single_file, f, output_dir, output_format): f 
                    for f in files
                }
                
                for future in as_completed(future_to_file):
                    file = future_to_file[future]
                    try:
                        result_path = future.result()
                        if result_path:
                            results.append(result_path)
                    except Exception as e:
                        logger.error(f"Failed to process {file.name}: {e}")
                        # Create an error file in output
                        error_file = output_dir / f"{file.stem}_error.txt"
                        error_file.write_text(f"Conversion failed: {str(e)}", encoding='utf-8')

            # Create output ZIP
            output_zip_path = zip_path.parent / f"converted_{zip_path.stem}.zip"
            self._create_zip(output_dir, output_zip_path)

            return output_zip_path

        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _process_single_file(self, input_path: Path, output_dir: Path, output_format: str) -> Path:
        """Process a single file and save to output directory."""
        try:
            # Determine output path (maintain relative structure if needed, but flat for now)
            output_ext = '.txt' if output_format == 'text' else '.md'
            output_path = output_dir / f"{input_path.stem}{output_ext}"

            # Convert
            markdown_content = self.converter.convert_to_string(input_path)

            if output_format == 'text':
                final_content = markdown_to_text(markdown_content)
            else:
                final_content = markdown_content

            output_path.write_text(final_content, encoding='utf-8')
            return output_path
        except Exception as e:
            logger.error(f"Error converting {input_path}: {e}")
            raise

    def _create_zip(self, source_dir: Path, output_zip: Path):
        """Zip the contents of source_dir to output_zip."""
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in source_dir.rglob('*'):
                if file.is_file():
                    zipf.write(file, file.relative_to(source_dir))
