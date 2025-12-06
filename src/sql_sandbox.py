"""
Universal SQL Sandbox - Secure BYOD (Bring Your Own Database) Module.

Provides:
1. UniversalSQLBuilder - Ingests various file formats into SQLite
2. SQLAgent - Natural language to SQL using OpenRouter
3. Secure read-only query execution

Security Constraints:
- All connections are READ-ONLY (SQLite URI mode)
- Ephemeral storage (tempfile with auto-cleanup)
- Query timeout (5 seconds max)
- Row limit (1000 max returned)
- DML/DDL blocking at multiple levels
"""

import os
import re
import sqlite3
import tempfile
import shutil
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Security constants
MAX_ROWS = 1000
QUERY_TIMEOUT_MS = 5000
MAX_FILE_SIZE_MB = 50

# Blocked SQL keywords (DML/DDL operations)
BLOCKED_KEYWORDS = [
    'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
    'TRUNCATE', 'REPLACE', 'MERGE', 'GRANT', 'REVOKE',
    'ATTACH', 'DETACH', 'VACUUM', 'REINDEX', 'ANALYZE'
]

# SQL Agent system prompt
SQL_AGENT_PROMPT = """You are an expert SQL analyst. Your task is to convert natural language questions into valid SQLite SELECT queries.

DATABASE SCHEMA:
{schema}

RULES:
1. Generate ONLY valid SQLite SELECT queries
2. Use aggregations (COUNT, SUM, AVG, MIN, MAX) for analytical questions
3. Use appropriate JOINs when querying related tables
4. Add ORDER BY for sorted results, LIMIT for top-N queries
5. NEVER use INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, or any DDL/DML
6. Return ONLY the SQL query, no explanation or markdown formatting
7. If the question cannot be answered with the schema, respond with: SELECT 'Cannot answer: [reason]' AS error

QUESTION: {question}

SQL QUERY:"""


@dataclass
class QueryResult:
    """Result of a SQL query execution."""
    success: bool
    sql: str
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    truncated: bool
    latency_ms: int
    error: Optional[str] = None


@dataclass
class DatabaseInfo:
    """Information about an ingested database."""
    path: str
    tables: List[str]
    schema: str
    row_counts: Dict[str, int]
    file_type: str
    original_filename: str


class UniversalSQLBuilder:
    """
    Normalizes various file formats into SQLite databases.

    Supported formats:
    - Native SQLite: .sqlite, .db, .sqlite3
    - SQL Dumps: .sql
    - Spreadsheets: .csv, .xlsx
    """

    SUPPORTED_EXTENSIONS = {'.sqlite', '.db', '.sqlite3', '.sql', '.csv', '.xlsx'}

    def __init__(self, temp_dir: Optional[str] = None):
        """
        Initialize the SQL builder.

        Args:
            temp_dir: Optional custom temp directory
        """
        self.temp_dir = temp_dir or tempfile.mkdtemp(prefix='sql_sandbox_')
        self._databases: Dict[str, DatabaseInfo] = {}

    def cleanup(self):
        """Clean up all temporary files."""
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up SQL sandbox temp dir: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temp dir: {e}")

    def ingest(self, file_path: str, original_filename: str) -> DatabaseInfo:
        """
        Ingest a file and convert to SQLite database.

        Args:
            file_path: Path to the uploaded file
            original_filename: Original filename for extension detection

        Returns:
            DatabaseInfo with path and schema information

        Raises:
            ValueError: If file type is not supported or file is invalid
        """
        ext = Path(original_filename).suffix.lower()

        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {ext}. Supported: {self.SUPPORTED_EXTENSIONS}")

        # Route to appropriate strategy
        if ext in {'.sqlite', '.db', '.sqlite3'}:
            db_path = self._ingest_sqlite(file_path, original_filename)
        elif ext == '.sql':
            db_path = self._ingest_sql_dump(file_path, original_filename)
        elif ext == '.csv':
            db_path = self._ingest_csv(file_path, original_filename)
        elif ext == '.xlsx':
            db_path = self._ingest_xlsx(file_path, original_filename)
        else:
            raise ValueError(f"Unhandled extension: {ext}")

        # Extract schema information
        db_info = self._extract_schema(db_path, ext, original_filename)
        self._databases[db_path] = db_info

        return db_info

    def _ingest_sqlite(self, file_path: str, original_filename: str) -> str:
        """
        Strategy A: Native SQLite files.
        Copy to temp location and validate.
        """
        # Copy to temp directory
        dest_path = os.path.join(self.temp_dir, f"db_{int(time.time())}.sqlite")
        shutil.copy2(file_path, dest_path)

        # Validate it's a real SQLite file
        try:
            conn = sqlite3.connect(f"file:{dest_path}?mode=ro&uri=true", uri=True)
            conn.execute("SELECT 1")
            conn.close()
            logger.info(f"Ingested native SQLite: {original_filename}")
            return dest_path
        except sqlite3.Error as e:
            os.remove(dest_path)
            raise ValueError(f"Invalid SQLite file: {e}")

    def _ingest_sql_dump(self, file_path: str, original_filename: str) -> str:
        """
        Strategy B: SQL dump rehydration.
        Execute SQL script into a new database.
        Supports MySQL and PostgreSQL dump conversion to SQLite.
        """
        dest_path = os.path.join(self.temp_dir, f"db_{int(time.time())}.sqlite")
        conn = None

        try:
            # Read SQL file
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                sql_script = f.read()

            # Convert MySQL/PostgreSQL syntax to SQLite
            sql_script = self._convert_to_sqlite(sql_script)

            # Debug: Log first CREATE TABLE for troubleshooting
            for line in sql_script.split('\n'):
                if 'CREATE TABLE' in line.upper():
                    logger.debug(f"Converted SQL sample: {line[:200]}")
                    break

            # Create new database and execute script
            conn = sqlite3.connect(dest_path)
            conn.executescript(sql_script)
            conn.commit()

            # Validate that at least one table was created
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            conn = None

            if not tables:
                raise ValueError(
                    "No tables were created from the SQL dump. "
                    "The file may contain only comments, or uses unsupported SQL syntax. "
                    "Ensure the dump contains CREATE TABLE statements."
                )

            logger.info(f"Ingested SQL dump: {original_filename} (tables: {tables})")
            return dest_path

        except sqlite3.OperationalError as e:
            error_msg = str(e)
            # Provide user-friendly error messages
            if 'syntax error' in error_msg.lower():
                raise ValueError(
                    f"SQL syntax error: {error_msg}. "
                    "The SQL dump may use database-specific syntax not compatible with SQLite. "
                    "Try exporting as SQLite format or use CSV instead."
                )
            raise ValueError(f"SQL execution error: {error_msg}")
        except Exception as e:
            if 'no tables' not in str(e).lower():
                logger.error(f"SQL dump ingestion failed: {e}")
            raise ValueError(f"Failed to process SQL dump: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            # Clean up on failure
            if 'tables' not in dir() or not tables:
                if os.path.exists(dest_path):
                    try:
                        os.remove(dest_path)
                    except Exception:
                        pass

    def _convert_to_sqlite(self, sql: str) -> str:
        """
        Convert MySQL/PostgreSQL SQL syntax to SQLite-compatible syntax.

        Uses sqlglot for robust SQL transpilation, with regex fallback for
        unsupported constructs like MySQL conditional comments.
        """
        # Phase 1: Pre-processing - Remove MySQL-specific constructs that sqlglot can't handle
        sql = self._preprocess_mysql_dump(sql)

        # Phase 2: Use sqlglot for SQL transpilation (statement by statement)
        try:
            sql = self._convert_with_sqlglot(sql)
        except Exception as e:
            logger.warning(f"sqlglot conversion failed, using regex fallback: {e}")
            sql = self._convert_to_sqlite_regex(sql)

        return sql

    def _preprocess_mysql_dump(self, sql: str) -> str:
        """
        Pre-process MySQL dump to remove constructs that sqlglot can't handle.
        These are MySQL-specific administrative statements and comments.
        """
        # Remove MySQL conditional comments like /*!40101 SET ... */;
        sql = re.sub(r'/\*!\d+.*?\*/;?', '', sql, flags=re.DOTALL)

        # Remove MySQL-specific statements
        sql = re.sub(r'LOCK\s+TABLES\s+[^;]+;', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'UNLOCK\s+TABLES\s*;', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'SET\s+NAMES\s+[^;]+;', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'SET\s+sql_mode\s*=\s*[^;]+;', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'SET\s+character_set_client\s*=\s*[^;]+;', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'SET\s+@[^;]+;', '', sql, flags=re.IGNORECASE)

        # Remove MySQL administrative ALTER statements (after backtick removal)
        sql = sql.replace('`', '')
        sql = re.sub(r'ALTER\s+TABLE\s+\w+\s+DISABLE\s+KEYS\s*;', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'ALTER\s+TABLE\s+\w+\s+ENABLE\s+KEYS\s*;', '', sql, flags=re.IGNORECASE)

        return sql

    def _convert_with_sqlglot(self, sql: str) -> str:
        """
        Convert SQL using sqlglot transpiler.
        Handles statement-by-statement conversion for better error handling.
        """
        try:
            import sqlglot
            from sqlglot import exp
        except ImportError:
            logger.warning("sqlglot not installed, using regex fallback")
            return self._convert_to_sqlite_regex(sql)

        converted_statements = []

        # Split into statements and convert each
        # Use sqlglot's parser to handle complex statements
        try:
            # Parse with error handling for unsupported syntax
            statements = sqlglot.parse(sql, read='mysql', error_level='WARN')

            for stmt in statements:
                if stmt is None:
                    continue

                try:
                    # Transpile to SQLite
                    converted = stmt.sql(dialect='sqlite')

                    # Post-process: Fix AUTOINCREMENT placement
                    # sqlglot outputs: INTEGER(11) NOT NULL AUTOINCREMENT PRIMARY KEY
                    # SQLite requires: INTEGER PRIMARY KEY AUTOINCREMENT
                    converted = self._fix_sqlite_autoincrement(converted)

                    converted_statements.append(converted)
                except Exception as stmt_error:
                    logger.debug(f"Statement conversion failed: {stmt_error}")
                    # Try to include original statement with regex cleanup
                    try:
                        original = stmt.sql(dialect='mysql')
                        cleaned = self._convert_to_sqlite_regex(original)
                        converted_statements.append(cleaned)
                    except Exception:
                        pass

        except Exception as e:
            logger.debug(f"sqlglot parsing failed: {e}")
            # Fall back to regex-based conversion
            return self._convert_to_sqlite_regex(sql)

        return ';\n'.join(converted_statements) + ';'

    def _fix_sqlite_autoincrement(self, sql: str) -> str:
        """
        Post-process sqlglot output for SQLite compatibility.
        Handles AUTOINCREMENT placement and other SQLite-specific fixes.
        """
        # Remove type size specifiers (INTEGER(11), UINT(11), etc.)
        sql = re.sub(r'\bINTEGER\s*\(\d+\)', 'INTEGER', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bUINT\s*\(\d+\)', 'INTEGER', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bUINT\b', 'INTEGER', sql, flags=re.IGNORECASE)

        # Remove TEXT size specifiers (TEXT(255) -> TEXT)
        sql = re.sub(r'\bTEXT\s*\(\d+\)', 'TEXT', sql, flags=re.IGNORECASE)

        # Remove REAL precision (REAL(10, 2) -> REAL)
        sql = re.sub(r'\bREAL\s*\(\d+\s*,\s*\d+\)', 'REAL', sql, flags=re.IGNORECASE)

        # Convert TIMESTAMPTZ to TEXT (SQLite doesn't have timestamp types)
        sql = re.sub(r'\bTIMESTAMPTZ\b', 'TEXT', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bTIMESTAMP\b', 'TEXT', sql, flags=re.IGNORECASE)

        # Convert ENUM to TEXT
        sql = re.sub(r"\bENUM\s*\([^)]+\)", 'TEXT', sql, flags=re.IGNORECASE)

        # Remove ZEROFILL
        sql = re.sub(r'\bZEROFILL\b', '', sql, flags=re.IGNORECASE)

        # Remove INDEX definitions inside CREATE TABLE (SQLite doesn't support this)
        sql = re.sub(r',?\s*UNIQUE\s+\w+\s*\([^)]+\)', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r',?\s*INDEX\s+\w+\s*\([^)]+\)', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r',?\s*KEY\s+\w+\s*\([^)]+\)', '', sql, flags=re.IGNORECASE)

        # Fix pattern: INTEGER NOT NULL AUTOINCREMENT PRIMARY KEY -> INTEGER PRIMARY KEY AUTOINCREMENT
        sql = re.sub(
            r'\bINTEGER\s+(?:NOT\s+NULL\s+)?AUTOINCREMENT\s+PRIMARY\s+KEY\b',
            'INTEGER PRIMARY KEY AUTOINCREMENT',
            sql,
            flags=re.IGNORECASE
        )

        # Fix pattern: INTEGER AUTOINCREMENT -> INTEGER PRIMARY KEY AUTOINCREMENT
        sql = re.sub(
            r'\bINTEGER\s+AUTOINCREMENT\b(?!\s+PRIMARY)',
            'INTEGER PRIMARY KEY AUTOINCREMENT',
            sql,
            flags=re.IGNORECASE
        )

        # Remove redundant PRIMARY KEY constraints after AUTOINCREMENT conversion
        sql = re.sub(r',?\s*PRIMARY\s+KEY\s*\([^)]+\)', '', sql, flags=re.IGNORECASE)

        # Clean up multiple spaces and empty commas before closing paren
        sql = re.sub(r',\s*\)', ')', sql)
        sql = re.sub(r'  +', ' ', sql)

        return sql

    def _convert_to_sqlite_regex(self, sql: str) -> str:
        """
        Fallback regex-based conversion for MySQL/PostgreSQL to SQLite.
        Used when sqlglot fails or is unavailable.
        """
        # Remove MySQL-specific table options
        sql = re.sub(r'\s*ENGINE\s*=\s*\w+', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\s*DEFAULT\s+CHARSET\s*=\s*\w+', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\s*COLLATE\s*=?\s*\w+', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\s*CHARACTER\s+SET\s+\w+', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\s*AUTO_INCREMENT\s*=\s*\d+', '', sql, flags=re.IGNORECASE)

        # Convert INT types to INTEGER
        sql = re.sub(r'\bINT\s*\(\s*\d+\s*\)', 'INTEGER', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bTINYINT\s*\(\s*\d+\s*\)', 'INTEGER', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bSMALLINT\s*\(\s*\d+\s*\)', 'INTEGER', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bMEDIUMINT\s*\(\s*\d+\s*\)', 'INTEGER', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bBIGINT\s*\(\s*\d+\s*\)', 'INTEGER', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bBIGINT\b', 'INTEGER', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bMEDIUMINT\b', 'INTEGER', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bSMALLINT\b', 'INTEGER', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bTINYINT\b', 'INTEGER', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bINT\b(?!EGER)', 'INTEGER', sql, flags=re.IGNORECASE)

        # Handle AUTO_INCREMENT patterns - convert to SQLite AUTOINCREMENT
        sql = re.sub(
            r'\bINTEGER\s+(?:UNSIGNED\s+)?(?:NOT\s+NULL\s+)?AUTO_INCREMENT\s+PRIMARY\s+KEY\b',
            'INTEGER PRIMARY KEY AUTOINCREMENT',
            sql,
            flags=re.IGNORECASE
        )
        sql = re.sub(
            r'\bINTEGER\s+PRIMARY\s+KEY\s+AUTO_INCREMENT\b',
            'INTEGER PRIMARY KEY AUTOINCREMENT',
            sql,
            flags=re.IGNORECASE
        )
        sql = re.sub(
            r'\bINTEGER\s+(?:UNSIGNED\s+)?(?:NOT\s+NULL\s+)?AUTO_INCREMENT\b',
            'INTEGER PRIMARY KEY AUTOINCREMENT',
            sql,
            flags=re.IGNORECASE
        )
        sql = re.sub(r'\bAUTO_INCREMENT\b', 'AUTOINCREMENT', sql, flags=re.IGNORECASE)

        # Fix any remaining AUTOINCREMENT patterns
        sql = re.sub(r'PRIMARY\s+KEY\s+AUTOINCREMENT', 'PRIMARY KEY __VALID_AUTOINC__', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bAUTOINCREMENT\b', '', sql, flags=re.IGNORECASE)
        sql = sql.replace('__VALID_AUTOINC__', 'AUTOINCREMENT')

        # Convert DECIMAL/NUMERIC to REAL
        sql = re.sub(r'\bDECIMAL\s*\(\s*\d+\s*,\s*\d+\s*\)', 'REAL', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bNUMERIC\s*\(\s*\d+\s*,\s*\d+\s*\)', 'REAL', sql, flags=re.IGNORECASE)

        # Convert VARCHAR/CHAR to TEXT
        sql = re.sub(r'\bVARCHAR\s*\(\s*\d+\s*\)', 'TEXT', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bCHAR\s*\(\s*\d+\s*\)', 'TEXT', sql, flags=re.IGNORECASE)

        # PostgreSQL SERIAL type
        sql = re.sub(r'\bSERIAL\b', 'INTEGER PRIMARY KEY AUTOINCREMENT', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bBIGSERIAL\b', 'INTEGER PRIMARY KEY AUTOINCREMENT', sql, flags=re.IGNORECASE)

        # Remove UNSIGNED and ZEROFILL
        sql = re.sub(r'\bUNSIGNED\b', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bZEROFILL\b', '', sql, flags=re.IGNORECASE)

        # Remove MySQL-specific key/index definitions
        sql = re.sub(r',?\s*UNIQUE\s+KEY\s+\w+\s*\([^)]+\)', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r',?\s*KEY\s+\w+\s*\([^)]+\)', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r',?\s*INDEX\s+\w+\s*\([^)]+\)', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r',?\s*FULLTEXT\s+KEY\s+\w+\s*\([^)]+\)', '', sql, flags=re.IGNORECASE)

        # Convert ENUM to TEXT
        sql = re.sub(r"\bENUM\s*\([^)]+\)", 'TEXT', sql, flags=re.IGNORECASE)

        # Remove COMMENT and ON UPDATE CURRENT_TIMESTAMP
        sql = re.sub(r"\bCOMMENT\s+'[^']*'", '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bON\s+UPDATE\s+CURRENT_TIMESTAMP\b', '', sql, flags=re.IGNORECASE)

        # Remove redundant PRIMARY KEY constraints
        sql = re.sub(r',?\s*PRIMARY\s+KEY\s*\([^)]+\)', '', sql, flags=re.IGNORECASE)

        # Clean up multiple spaces
        sql = re.sub(r'  +', ' ', sql)

        return sql

    def _ingest_csv(self, file_path: str, original_filename: str) -> str:
        """
        Strategy C: CSV to SQLite translation.
        Uses pandas for robust CSV parsing.
        """
        try:
            import pandas as pd
        except ImportError:
            raise ValueError("pandas is required for CSV ingestion. Install with: pip install pandas")

        dest_path = os.path.join(self.temp_dir, f"db_{int(time.time())}.sqlite")

        try:
            # Read CSV with pandas (handles various formats)
            df = pd.read_csv(file_path, encoding='utf-8', encoding_errors='replace')

            # Sanitize column names
            df.columns = [self._sanitize_column_name(col) for col in df.columns]

            # Derive table name from filename
            table_name = self._sanitize_table_name(Path(original_filename).stem)

            # Write to SQLite
            conn = sqlite3.connect(dest_path)
            df.to_sql(table_name, conn, index=False, if_exists='replace')
            conn.close()

            logger.info(f"Ingested CSV as table '{table_name}': {original_filename}")
            return dest_path

        except Exception as e:
            if os.path.exists(dest_path):
                os.remove(dest_path)
            raise ValueError(f"Failed to import CSV: {e}")

    def _ingest_xlsx(self, file_path: str, original_filename: str) -> str:
        """
        Strategy C: Excel to SQLite translation.
        Each sheet becomes a table.
        """
        try:
            import pandas as pd
        except ImportError:
            raise ValueError("pandas and openpyxl required for Excel ingestion")

        dest_path = os.path.join(self.temp_dir, f"db_{int(time.time())}.sqlite")

        try:
            # Read all sheets
            xlsx = pd.ExcelFile(file_path, engine='openpyxl')

            conn = sqlite3.connect(dest_path)

            for sheet_name in xlsx.sheet_names:
                df = pd.read_excel(xlsx, sheet_name=sheet_name)

                # Sanitize column names
                df.columns = [self._sanitize_column_name(col) for col in df.columns]

                # Sanitize table name
                table_name = self._sanitize_table_name(sheet_name)

                df.to_sql(table_name, conn, index=False, if_exists='replace')
                logger.info(f"Imported sheet '{sheet_name}' as table '{table_name}'")

            conn.close()
            logger.info(f"Ingested Excel with {len(xlsx.sheet_names)} sheets: {original_filename}")
            return dest_path

        except Exception as e:
            if os.path.exists(dest_path):
                os.remove(dest_path)
            raise ValueError(f"Failed to import Excel: {e}")

    def _sanitize_column_name(self, name: str) -> str:
        """Sanitize column name for SQL compatibility."""
        # Convert to string, replace spaces/special chars with underscore
        name = str(name)
        name = re.sub(r'[^\w]', '_', name)
        name = re.sub(r'_+', '_', name)  # Collapse multiple underscores
        name = name.strip('_')
        # Ensure doesn't start with number
        if name and name[0].isdigit():
            name = 'col_' + name
        return name or 'unnamed'

    def _sanitize_table_name(self, name: str) -> str:
        """Sanitize table name for SQL compatibility."""
        name = self._sanitize_column_name(name)
        return name[:64]  # Limit length

    def _extract_schema(self, db_path: str, file_type: str, original_filename: str) -> DatabaseInfo:
        """Extract schema information from database."""
        conn = sqlite3.connect(f"file:{db_path}?mode=ro&uri=true", uri=True)
        cursor = conn.cursor()

        # Get table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]

        # Build schema string and count rows
        schema_parts = []
        row_counts = {}

        for table in tables:
            # Get column info
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()

            col_defs = []
            for col in columns:
                col_name = col[1]
                col_type = col[2] or 'TEXT'
                pk = ' PRIMARY KEY' if col[5] else ''
                col_defs.append(f"  {col_name} {col_type}{pk}")

            schema_parts.append(f"TABLE {table}:\n" + "\n".join(col_defs))

            # Count rows
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            row_counts[table] = cursor.fetchone()[0]

        conn.close()

        schema = "\n\n".join(schema_parts)

        return DatabaseInfo(
            path=db_path,
            tables=tables,
            schema=schema,
            row_counts=row_counts,
            file_type=file_type,
            original_filename=original_filename
        )

    def get_read_only_uri(self, db_path: str) -> str:
        """Get read-only SQLite URI for a database path."""
        return f"file:{db_path}?mode=ro&uri=true"


class SQLAgent:
    """
    Natural language to SQL agent using OpenRouter.

    Converts user questions to SQL queries and executes them safely.
    """

    def __init__(self, model: str = None):
        """
        Initialize the SQL agent.

        Args:
            model: OpenRouter model to use for SQL generation.
                   If None, uses the simple model from router config.
        """
        if model is None:
            # Get default model from router configuration
            try:
                from router import get_router
                router = get_router()
                # Use simple model for SQL queries (fast, efficient)
                model = router.config.get("models", {}).get("simple", {}).get("primary", "Google Gemini 2.0 Flash")
            except Exception:
                model = "Google Gemini 2.0 Flash"  # Fallback
        self.model = model

    def query(
        self,
        question: str,
        db_info: DatabaseInfo,
        auto_execute: bool = True
    ) -> Dict[str, Any]:
        """
        Process a natural language question.

        Args:
            question: Natural language question
            db_info: Database information from UniversalSQLBuilder
            auto_execute: If True, execute the generated SQL

        Returns:
            Dictionary with sql, results, and metadata
        """
        start_time = time.time()

        # Generate SQL using OpenRouter (with fallback)
        try:
            gen_result = self._generate_sql(question, db_info.schema)
            sql = gen_result['sql']
            model_used = gen_result.get('model_used', self.model)
            fallback_used = gen_result.get('fallback_used', False)
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'sql': None,
                'latency_ms': int((time.time() - start_time) * 1000)
            }

        # Validate SQL (security check)
        validation_error = self._validate_sql(sql)
        if validation_error:
            return {
                'success': False,
                'error': validation_error,
                'sql': sql,
                'model': model_used,
                'latency_ms': int((time.time() - start_time) * 1000)
            }

        if not auto_execute:
            return {
                'success': True,
                'sql': sql,
                'model': model_used,
                'fallback_used': fallback_used,
                'executed': False,
                'latency_ms': int((time.time() - start_time) * 1000)
            }

        # Execute SQL
        result = self._execute_sql(sql, db_info.path)
        result['latency_ms'] = int((time.time() - start_time) * 1000)
        result['model'] = model_used
        result['fallback_used'] = fallback_used

        return result

    def _generate_sql(self, question: str, schema: str) -> Dict[str, Any]:
        """
        Generate SQL query using OpenRouter with fallback support.

        Returns:
            Dictionary with 'sql', 'model_used', and optionally 'fallback_used'
        """
        from openrouter_gateway import chat_completion_with_fallback

        prompt = SQL_AGENT_PROMPT.format(schema=schema, question=question)

        result = chat_completion_with_fallback(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            domain="technical"
        )

        if 'error' in result:
            # Include models_tried info for better error reporting
            models_tried = result.get('models_tried', [self.model])
            raise ValueError(f"SQL generation failed: {result.get('error')} (tried: {', '.join(models_tried)})")

        sql = result.get('response', '').strip()

        # Clean up SQL (remove markdown formatting if present)
        sql = self._clean_sql(sql)

        return {
            'sql': sql,
            'model_used': result.get('fallback_model', result.get('model', self.model)),
            'fallback_used': result.get('fallback_used', False),
            'original_model': result.get('original_model'),
            'models_tried': result.get('models_tried')
        }

    def _clean_sql(self, sql: str) -> str:
        """Clean up SQL response from LLM."""
        # Remove markdown code blocks
        sql = re.sub(r'```sql\s*', '', sql)
        sql = re.sub(r'```\s*', '', sql)

        # Remove leading/trailing whitespace
        sql = sql.strip()

        # If the response contains text before SELECT, extract just the SELECT query
        # Some LLMs return "Here's the query:\n\nSELECT..." despite instructions
        select_match = re.search(r'\bSELECT\b', sql, re.IGNORECASE)
        if select_match and select_match.start() > 0:
            sql = sql[select_match.start():]

        # Remove any trailing semicolons for safety
        sql = sql.rstrip(';')

        return sql

    def _validate_sql(self, sql: str) -> Optional[str]:
        """
        Validate SQL for security.

        Returns:
            Error message if validation fails, None if OK
        """
        if not sql:
            return "Empty SQL query"

        sql_upper = sql.upper()

        # Check for blocked keywords
        for keyword in BLOCKED_KEYWORDS:
            # Use word boundary check to avoid false positives
            if re.search(rf'\b{keyword}\b', sql_upper):
                return f"Blocked operation: {keyword} is not allowed"

        # Must start with SELECT (after potential whitespace)
        if not re.match(r'^\s*SELECT\b', sql_upper):
            return "Only SELECT queries are allowed"

        # Check for suspicious patterns
        suspicious_patterns = [
            (r'--', "SQL comments not allowed"),
            (r'/\*', "Block comments not allowed"),
            (r';\s*\w', "Multiple statements not allowed"),
            (r'LOAD_EXTENSION', "Extension loading not allowed"),
        ]

        for pattern, msg in suspicious_patterns:
            if re.search(pattern, sql_upper):
                return msg

        return None

    def _execute_sql(self, sql: str, db_path: str) -> Dict[str, Any]:
        """
        Execute SQL query with safety constraints.

        Args:
            sql: Validated SQL query
            db_path: Path to SQLite database

        Returns:
            Dictionary with columns, rows, and metadata
        """
        try:
            # Connect in read-only mode
            conn = sqlite3.connect(
                f"file:{db_path}?mode=ro&uri=true",
                uri=True,
                timeout=QUERY_TIMEOUT_MS / 1000
            )

            # Set busy timeout
            conn.execute(f"PRAGMA busy_timeout = {QUERY_TIMEOUT_MS}")

            cursor = conn.cursor()

            # Execute with row limit
            limited_sql = f"{sql} LIMIT {MAX_ROWS + 1}"
            cursor.execute(limited_sql)

            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            # Fetch results
            rows = cursor.fetchall()

            # Check if truncated
            truncated = len(rows) > MAX_ROWS
            if truncated:
                rows = rows[:MAX_ROWS]

            conn.close()

            return {
                'success': True,
                'sql': sql,
                'columns': columns,
                'rows': [list(row) for row in rows],
                'row_count': len(rows),
                'truncated': truncated,
                'error': None
            }

        except sqlite3.OperationalError as e:
            error_msg = str(e)
            if 'timeout' in error_msg.lower():
                return {
                    'success': False,
                    'sql': sql,
                    'error': f"Query timeout ({QUERY_TIMEOUT_MS}ms exceeded)",
                    'columns': [],
                    'rows': [],
                    'row_count': 0,
                    'truncated': False
                }
            return {
                'success': False,
                'sql': sql,
                'error': f"SQL Error: {error_msg}",
                'columns': [],
                'rows': [],
                'row_count': 0,
                'truncated': False
            }
        except Exception as e:
            return {
                'success': False,
                'sql': sql,
                'error': f"Execution error: {str(e)}",
                'columns': [],
                'rows': [],
                'row_count': 0,
                'truncated': False
            }


class SQLSandboxSession:
    """
    Manages a complete SQL sandbox session.

    Provides a high-level interface combining builder and agent.
    """

    def __init__(self, session_id: str):
        """
        Initialize a sandbox session.

        Args:
            session_id: Unique session identifier
        """
        self.session_id = session_id
        self.builder = UniversalSQLBuilder()
        self.agent = SQLAgent()
        self.current_db: Optional[DatabaseInfo] = None
        self.query_history: List[Dict[str, Any]] = []
        self._consent_given = False

    @property
    def has_consent(self) -> bool:
        """Check if user has given consent."""
        return self._consent_given

    def give_consent(self):
        """Record user consent for ephemeral data processing."""
        self._consent_given = True
        logger.info(f"Consent given for session {self.session_id}")

    def upload_database(self, file_path: str, filename: str) -> Dict[str, Any]:
        """
        Upload and ingest a database file.

        Args:
            file_path: Path to uploaded file
            filename: Original filename

        Returns:
            Dictionary with success status and database info
        """
        if not self._consent_given:
            return {
                'success': False,
                'error': 'Consent required before uploading data'
            }

        try:
            self.current_db = self.builder.ingest(file_path, filename)

            return {
                'success': True,
                'tables': self.current_db.tables,
                'schema': self.current_db.schema,
                'row_counts': self.current_db.row_counts,
                'file_type': self.current_db.file_type
            }

        except ValueError as e:
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Database upload failed: {e}")
            return {
                'success': False,
                'error': 'Failed to process database file'
            }

    def ask(self, question: str) -> Dict[str, Any]:
        """
        Ask a natural language question about the database.

        Args:
            question: Natural language question

        Returns:
            Dictionary with SQL, results, and metadata
        """
        if not self._consent_given:
            return {
                'success': False,
                'error': 'Consent required'
            }

        if not self.current_db:
            return {
                'success': False,
                'error': 'No database loaded. Please upload a file first.'
            }

        result = self.agent.query(question, self.current_db)

        # Add to history
        self.query_history.append({
            'question': question,
            'sql': result.get('sql'),
            'success': result.get('success'),
            'timestamp': time.time()
        })

        return result

    def get_schema(self) -> Dict[str, Any]:
        """Get current database schema as dictionary."""
        if not self.current_db:
            return {"tables": [], "schema": None}

        tables_info = []
        for table in self.current_db.tables:
            tables_info.append({
                "name": table,
                "row_count": self.current_db.row_counts.get(table, 0)
            })

        return {
            "tables": tables_info,
            "schema": self.current_db.schema,
            "file_type": self.current_db.file_type,
            "original_filename": self.current_db.original_filename
        }

    def get_tables(self) -> List[str]:
        """Get list of tables in current database."""
        return self.current_db.tables if self.current_db else []

    def has_database(self) -> bool:
        """Check if a database is currently loaded."""
        return self.current_db is not None

    def ingest(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Ingest database file from bytes content.

        Args:
            file_content: File content as bytes
            filename: Original filename

        Returns:
            Dictionary with tables, row_counts, and success status
        """
        if not self._consent_given:
            return {'error': 'Consent required before uploading data'}

        # Write content to temp file
        temp_path = os.path.join(self.builder.temp_dir, f"upload_{int(time.time())}_{filename}")
        try:
            with open(temp_path, 'wb') as f:
                f.write(file_content)

            # Use upload_database internally
            result = self.upload_database(temp_path, filename)

            # Clean up temp upload file (builder keeps its own copy)
            if os.path.exists(temp_path):
                os.remove(temp_path)

            return result

        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            logger.error(f"Ingest failed: {e}")
            return {'error': str(e)}

    def query(self, question: str) -> Dict[str, Any]:
        """
        Execute natural language query (alias for ask()).

        Args:
            question: Natural language question

        Returns:
            Dictionary with sql, results, columns, row_count, etc.
        """
        result = self.ask(question)

        # Transform result for routes.py compatibility
        if result.get('success'):
            return {
                'sql': result.get('sql', ''),
                'results': result.get('rows', []),
                'columns': result.get('columns', []),
                'row_count': result.get('row_count', 0),
                'execution_time_ms': result.get('latency_ms', 0),
                'model': self.agent.model
            }
        else:
            return {'error': result.get('error', 'Query failed')}

    def cleanup(self):
        """Clean up session resources."""
        self.builder.cleanup()
        self.current_db = None
        self.query_history = []
        logger.info(f"Session {self.session_id} cleaned up")


# Session storage (in-memory, ephemeral)
_sessions: Dict[str, SQLSandboxSession] = {}


def get_session(session_id: str) -> SQLSandboxSession:
    """Get or create a sandbox session."""
    if session_id not in _sessions:
        _sessions[session_id] = SQLSandboxSession(session_id)
    return _sessions[session_id]


def cleanup_session(session_id: str):
    """Clean up and remove a session."""
    if session_id in _sessions:
        _sessions[session_id].cleanup()
        del _sessions[session_id]
