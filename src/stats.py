"""
Statistics and monitoring module for document converter.
Uses SQLite for persistent storage.
"""

import sqlite3
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from contextlib import contextmanager

# Database file path
DB_PATH = Path(__file__).parent.parent / "data" / "stats.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Thread lock for database operations
_lock = Lock()


def _get_connection():
    """Get a database connection."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _db_connection():
    """Context manager for database connections."""
    conn = _get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _init_db():
    """Initialize the database schema."""
    with _db_connection() as conn:
        cursor = conn.cursor()

        # Conversions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                ip_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Errors table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_type TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Security events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS security_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                ip_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Service info table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS service_info (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')

        # Contact requests table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contact_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                company TEXT,
                use_case TEXT NOT NULL,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Capacity exceeded events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS capacity_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_hash TEXT NOT NULL,
                active_count INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Document analysis table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analyze_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # RAG chunking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chunk_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_hash TEXT NOT NULL,
                chunks_generated INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Document comparison table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS compare_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # SQL Sandbox requests table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sql_sandbox_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_type TEXT NOT NULL,
                file_type TEXT,
                file_size INTEGER,
                query_latency_ms INTEGER,
                success INTEGER DEFAULT 1,
                ip_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # API keys table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_hash TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                rate_limit INTEGER DEFAULT 100,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP,
                total_requests INTEGER DEFAULT 0
            )
        ''')

        # LLM requests table (v3.0) - Cost tracking for CFO Hook
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS llm_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model TEXT NOT NULL,
                model_id TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                actual_cost REAL NOT NULL,
                gpt4_cost REAL NOT NULL,
                savings REAL NOT NULL,
                savings_percent REAL NOT NULL,
                latency_ms INTEGER,
                domain TEXT,
                ip_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Agent executions table (v3.1) - Agentic workflows telemetry
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_type TEXT NOT NULL,
                mission TEXT NOT NULL,
                steps_completed INTEGER NOT NULL,
                total_latency_ms INTEGER NOT NULL,
                actual_cost REAL NOT NULL,
                gpt4_cost REAL NOT NULL,
                savings REAL NOT NULL,
                savings_percent REAL NOT NULL,
                documents_count INTEGER,
                chunks_retrieved INTEGER,
                findings_count INTEGER,
                quality_score INTEGER,
                success INTEGER DEFAULT 1,
                ip_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Response evaluations table (v3.2 - Evaluation-Driven Development)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS response_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                response_type TEXT NOT NULL,
                overall_score REAL NOT NULL,
                relevance_score REAL,
                accuracy_score REAL,
                helpfulness_score REAL,
                safety_score REAL,
                completeness_score REAL,
                feedback TEXT,
                eval_latency_ms INTEGER,
                eval_model TEXT,
                eval_tokens INTEGER,
                eval_cost REAL,
                request_id TEXT,
                passed_threshold INTEGER DEFAULT 0,
                threshold_used REAL DEFAULT 7.0,
                ip_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Index for cost queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_llm_requests_created ON llm_requests(created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_agent_executions_created ON agent_executions(created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_evaluations_created ON response_evaluations(created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_evaluations_type ON response_evaluations(response_type)')

        # Set service start time if not exists
        cursor.execute('''
            INSERT OR IGNORE INTO service_info (key, value)
            VALUES ('started_at', ?)
        ''', (datetime.now().isoformat(),))

        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversions_created ON conversions(created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversions_type ON conversions(file_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_security_created ON security_events(created_at)')

        # Migration: Add error_type and error_message columns if they don't exist
        try:
            cursor.execute('SELECT error_type FROM errors LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute('ALTER TABLE errors ADD COLUMN error_type TEXT')
            cursor.execute('ALTER TABLE errors ADD COLUMN error_message TEXT')


# Initialize database on module load
_init_db()


class Statistics:
    """Statistics manager using SQLite."""

    def __init__(self):
        pass

    def record_conversion(self, file_type: str, file_size: int, ip: str):
        """Record a successful conversion."""
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    'INSERT INTO conversions (file_type, file_size, ip_hash) VALUES (?, ?, ?)',
                    (file_type, file_size, ip_hash)
                )

    def record_error(self, error_type: str = "unknown", error_message: str = None):
        """Record a conversion error with details.

        Args:
            error_type: Category of error (e.g., 'conversion', 'analysis', 'chunking')
            error_message: Detailed error message (truncated to 500 chars)
        """
        # Truncate message to prevent DB bloat
        if error_message and len(error_message) > 500:
            error_message = error_message[:497] + "..."
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    'INSERT INTO errors (error_type, error_message) VALUES (?, ?)',
                    (error_type, error_message)
                )

    def record_rate_limit(self, ip: str):
        """Record a rate limit hit."""
        self._add_security_event("rate_limit", ip)

    def record_blocked(self, ip: str, reason: str):
        """Record a blocked request."""
        self._add_security_event(f"blocked:{reason}", ip)

    def _add_security_event(self, event_type: str, ip: str):
        """Add a security event to the log."""
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:8]
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    'INSERT INTO security_events (event_type, ip_hash) VALUES (?, ?)',
                    (event_type, ip_hash)
                )

    def record_contact_request(self, name: str, email: str, company: str, use_case: str, message: str):
        """Record a contact form submission."""
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    '''INSERT INTO contact_requests (name, email, company, use_case, message)
                       VALUES (?, ?, ?, ?, ?)''',
                    (name, email, company, use_case, message)
                )

    def record_capacity_exceeded(self, ip: str, active_count: int):
        """Record when system is over capacity."""
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    'INSERT INTO capacity_events (ip_hash, active_count) VALUES (?, ?)',
                    (ip_hash, active_count)
                )

    def record_analyze(self, ip: str):
        """Record a document analysis request."""
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    'INSERT INTO analyze_requests (ip_hash) VALUES (?)',
                    (ip_hash,)
                )

    def record_chunk(self, ip: str, chunks_generated: int):
        """Record a RAG chunking request."""
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    'INSERT INTO chunk_requests (ip_hash, chunks_generated) VALUES (?, ?)',
                    (ip_hash, chunks_generated)
                )

    def record_compare(self, ip: str):
        """Record a document comparison request."""
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    'INSERT INTO compare_requests (ip_hash) VALUES (?)',
                    (ip_hash,)
                )

    def record_sql_upload(self, ip: str, file_type: str, file_size: int, success: bool = True):
        """Record a SQL Sandbox database upload."""
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    '''INSERT INTO sql_sandbox_requests
                       (request_type, file_type, file_size, success, ip_hash)
                       VALUES (?, ?, ?, ?, ?)''',
                    ('upload', file_type, file_size, 1 if success else 0, ip_hash)
                )

    def record_sql_query(self, ip: str, latency_ms: int, success: bool = True):
        """Record a SQL Sandbox query execution."""
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    '''INSERT INTO sql_sandbox_requests
                       (request_type, query_latency_ms, success, ip_hash)
                       VALUES (?, ?, ?, ?)''',
                    ('query', latency_ms, 1 if success else 0, ip_hash)
                )

    def record_llm_request(
        self,
        model: str,
        model_id: str = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        actual_cost: float = 0.0,
        gpt4_cost: float = 0.0,
        savings: float = 0.0,
        savings_percent: float = 0.0,
        latency_ms: int = None,
        domain: str = None,
        ip: str = None,
        # Simplified signature for agent calls
        cost: float = None
    ):
        """Record an LLM request with cost tracking (v3.0).

        Args:
            model: UI model name (e.g., "Google Gemini 2.0 Flash")
            model_id: OpenRouter model ID
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            actual_cost: Actual cost in dollars
            gpt4_cost: What it would have cost with GPT-4
            savings: Amount saved vs GPT-4
            savings_percent: Percentage saved
            latency_ms: Request latency in milliseconds
            domain: Domain profile used (general, legal, medical, technical)
            ip: Client IP for hashing
            cost: Simplified cost parameter (overrides actual_cost)
        """
        # Handle simplified signature
        if cost is not None:
            actual_cost = cost

        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16] if ip else None
        model_id = model_id or model  # Use model as model_id if not provided

        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    '''INSERT INTO llm_requests
                       (model, model_id, input_tokens, output_tokens, actual_cost,
                        gpt4_cost, savings, savings_percent, latency_ms, domain, ip_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (model, model_id, input_tokens, output_tokens, actual_cost,
                     gpt4_cost, savings, savings_percent, latency_ms, domain, ip_hash)
                )

    def record_agent_execution(
        self,
        agent_type: str,
        mission: str,
        steps_completed: int,
        total_latency_ms: int,
        actual_cost: float,
        gpt4_cost: float,
        savings: float,
        savings_percent: float,
        documents_count: int = 0,
        chunks_retrieved: int = 0,
        findings_count: int = 0,
        quality_score: int = None,
        success: bool = True,
        ip: str = None
    ):
        """Record an agent execution with telemetry (v3.1).

        Args:
            agent_type: Type of agent (investigator, researcher, etc.)
            mission: User's mission/query
            steps_completed: Number of steps completed (4 = full workflow)
            total_latency_ms: Total execution time
            actual_cost: Actual cost in dollars
            gpt4_cost: What it would have cost with GPT-4
            savings: Amount saved vs GPT-4
            savings_percent: Percentage saved
            documents_count: Number of documents analyzed
            chunks_retrieved: Number of chunks retrieved for context
            findings_count: Number of findings in report
            quality_score: Quality score from validator (1-10)
            success: Whether execution succeeded
            ip: Client IP for hashing
        """
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16] if ip else None
        # Truncate mission for storage
        mission_truncated = mission[:200] if mission else ""

        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    '''INSERT INTO agent_executions
                       (agent_type, mission, steps_completed, total_latency_ms,
                        actual_cost, gpt4_cost, savings, savings_percent,
                        documents_count, chunks_retrieved, findings_count,
                        quality_score, success, ip_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (agent_type, mission_truncated, steps_completed, total_latency_ms,
                     actual_cost, gpt4_cost, savings, savings_percent,
                     documents_count, chunks_retrieved, findings_count,
                     quality_score, 1 if success else 0, ip_hash)
                )

    def record_evaluation(
        self,
        response_type: str,
        overall_score: float,
        dimensions: dict,
        feedback: str = "",
        eval_latency_ms: int = 0,
        eval_model: str = "",
        eval_tokens: int = 0,
        eval_cost: float = 0.0,
        request_id: str = None,
        threshold: float = 7.0,
        ip: str = None
    ):
        """Record a response evaluation (v3.2 - Evaluation-Driven Development).

        Args:
            response_type: Type of response (chat, investigation, sql)
            overall_score: Weighted overall score (1-10)
            dimensions: Dict with dimension scores {name: {score, reasoning}}
            feedback: Overall feedback text
            eval_latency_ms: Time to run evaluation
            eval_model: Model used for evaluation
            eval_tokens: Tokens used by evaluation
            eval_cost: Cost of evaluation
            request_id: Request ID for correlation
            threshold: Quality threshold used
            ip: Client IP for hashing
        """
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16] if ip else None
        passed = 1 if overall_score >= threshold else 0

        # Extract dimension scores
        relevance = dimensions.get('relevance', {}).get('score', 0)
        accuracy = dimensions.get('accuracy', {}).get('score', 0)
        helpfulness = dimensions.get('helpfulness', {}).get('score', 0)
        safety = dimensions.get('safety', {}).get('score', 0)
        completeness = dimensions.get('completeness', {}).get('score', 0)

        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    '''INSERT INTO response_evaluations
                       (response_type, overall_score, relevance_score, accuracy_score,
                        helpfulness_score, safety_score, completeness_score,
                        feedback, eval_latency_ms, eval_model, eval_tokens, eval_cost,
                        request_id, passed_threshold, threshold_used, ip_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (response_type, overall_score, relevance, accuracy,
                     helpfulness, safety, completeness,
                     feedback[:500] if feedback else "", eval_latency_ms,
                     eval_model, eval_tokens, eval_cost,
                     request_id, passed, threshold, ip_hash)
                )

    def get_evaluation_stats(self):
        """Get response evaluation statistics (v3.2).

        Returns:
            Dictionary with quality metrics and trends
        """
        with _db_connection() as conn:
            cursor = conn.cursor()

            try:
                cursor.execute("SELECT COUNT(*) FROM response_evaluations")
                total_evals = cursor.fetchone()[0]
            except Exception:
                return {
                    'total_evaluations': 0,
                    'avg_overall_score': 0.0,
                    'pass_rate': 0.0,
                    'by_type': {},
                    'by_dimension': {},
                    'today_evaluations': 0,
                    'today_avg_score': 0.0
                }

            if total_evals == 0:
                return {
                    'total_evaluations': 0,
                    'avg_overall_score': 0.0,
                    'pass_rate': 0.0,
                    'by_type': {},
                    'by_dimension': {},
                    'today_evaluations': 0,
                    'today_avg_score': 0.0
                }

            # Overall metrics
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    COALESCE(AVG(overall_score), 0) as avg_score,
                    COALESCE(SUM(passed_threshold), 0) as passed,
                    COALESCE(AVG(relevance_score), 0) as avg_relevance,
                    COALESCE(AVG(accuracy_score), 0) as avg_accuracy,
                    COALESCE(AVG(helpfulness_score), 0) as avg_helpfulness,
                    COALESCE(AVG(safety_score), 0) as avg_safety,
                    COALESCE(AVG(completeness_score), 0) as avg_completeness,
                    COALESCE(SUM(eval_cost), 0) as total_eval_cost
                FROM response_evaluations
            """)
            row = cursor.fetchone()
            total = row[0]
            avg_score = round(row[1], 2)
            passed = row[2]
            pass_rate = round((passed / total * 100) if total > 0 else 0, 1)

            by_dimension = {
                'relevance': round(row[3], 2),
                'accuracy': round(row[4], 2),
                'helpfulness': round(row[5], 2),
                'safety': round(row[6], 2),
                'completeness': round(row[7], 2)
            }
            total_eval_cost = round(row[8], 6)

            # By response type
            cursor.execute("""
                SELECT response_type,
                       COUNT(*) as count,
                       AVG(overall_score) as avg_score,
                       SUM(passed_threshold) as passed
                FROM response_evaluations
                GROUP BY response_type
            """)
            by_type = {}
            for type_row in cursor.fetchall():
                rtype = type_row[0]
                count = type_row[1]
                by_type[rtype] = {
                    'count': count,
                    'avg_score': round(type_row[2], 2),
                    'pass_rate': round((type_row[3] / count * 100) if count > 0 else 0, 1)
                }

            # Today's metrics
            cursor.execute("""
                SELECT COUNT(*), COALESCE(AVG(overall_score), 0)
                FROM response_evaluations
                WHERE DATE(created_at) = DATE('now')
            """)
            today_row = cursor.fetchone()
            today_evals = today_row[0]
            today_avg = round(today_row[1], 2)

            return {
                'total_evaluations': total,
                'avg_overall_score': avg_score,
                'pass_rate': pass_rate,
                'passed_count': passed,
                'by_type': by_type,
                'by_dimension': by_dimension,
                'total_eval_cost': total_eval_cost,
                'today_evaluations': today_evals,
                'today_avg_score': today_avg
            }

    def get_cost_stats(self):
        """Get LLM cost statistics (v3.0 - CFO Hook).

        Returns:
            Dictionary with total costs, savings, and model breakdown
        """
        with _db_connection() as conn:
            cursor = conn.cursor()

            # Total requests
            try:
                cursor.execute("SELECT COUNT(*) FROM llm_requests")
                total_requests = cursor.fetchone()[0]
            except Exception:
                # Table might not exist yet
                return {
                    'total_requests': 0,
                    'total_cost': 0.0,
                    'total_gpt4_cost': 0.0,
                    'total_savings': 0.0,
                    'avg_savings_percent': 0.0,
                    'cost_by_model': {},
                    'cost_by_day': {},
                    'today_savings': 0.0
                }

            # Total costs
            cursor.execute("""
                SELECT
                    COALESCE(SUM(actual_cost), 0) as total_cost,
                    COALESCE(SUM(gpt4_cost), 0) as total_gpt4_cost,
                    COALESCE(SUM(savings), 0) as total_savings,
                    COALESCE(AVG(savings_percent), 0) as avg_savings_percent
                FROM llm_requests
            """)
            row = cursor.fetchone()
            total_cost = round(row[0], 6)
            total_gpt4_cost = round(row[1], 6)
            total_savings = round(row[2], 6)
            avg_savings_percent = round(row[3], 2)

            # Cost by model
            cursor.execute("""
                SELECT model,
                       COUNT(*) as requests,
                       SUM(actual_cost) as cost,
                       SUM(savings) as saved,
                       AVG(savings_percent) as avg_pct
                FROM llm_requests
                GROUP BY model
                ORDER BY requests DESC
            """)
            model_rows = cursor.fetchall()
            cost_by_model = {
                row[0]: {
                    'requests': row[1],
                    'cost': round(row[2], 6),
                    'savings': round(row[3], 6),
                    'avg_savings_percent': round(row[4], 2)
                }
                for row in model_rows
            }

            # Cost by day (last 7 days)
            cursor.execute("""
                SELECT DATE(created_at) as day,
                       SUM(actual_cost) as cost,
                       SUM(savings) as saved
                FROM llm_requests
                WHERE DATE(created_at) >= DATE('now', '-7 days')
                GROUP BY DATE(created_at)
                ORDER BY day
            """)
            day_rows = cursor.fetchall()
            cost_by_day = {
                row[0]: {'cost': round(row[1], 6), 'savings': round(row[2], 6)}
                for row in day_rows
            }

            # Today's savings
            cursor.execute("""
                SELECT COALESCE(SUM(savings), 0)
                FROM llm_requests
                WHERE DATE(created_at) = DATE('now')
            """)
            today_savings = round(cursor.fetchone()[0], 6)

            # Total tokens
            cursor.execute("""
                SELECT
                    COALESCE(SUM(input_tokens), 0),
                    COALESCE(SUM(output_tokens), 0)
                FROM llm_requests
            """)
            token_row = cursor.fetchone()
            total_input_tokens = token_row[0]
            total_output_tokens = token_row[1]

            return {
                'total_requests': total_requests,
                'total_cost': total_cost,
                'total_gpt4_cost': total_gpt4_cost,
                'total_savings': total_savings,
                'avg_savings_percent': avg_savings_percent,
                'cost_by_model': cost_by_model,
                'cost_by_day': cost_by_day,
                'today_savings': today_savings,
                'total_input_tokens': total_input_tokens,
                'total_output_tokens': total_output_tokens
            }

    def get_agent_stats(self):
        """Get agent execution statistics (v3.1).

        Returns:
            Dictionary with agent execution metrics
        """
        with _db_connection() as conn:
            cursor = conn.cursor()

            try:
                # Total executions
                cursor.execute("SELECT COUNT(*) FROM agent_executions")
                total_executions = cursor.fetchone()[0]
            except Exception:
                # Table might not exist yet
                return {
                    'total_executions': 0,
                    'successful_executions': 0,
                    'total_cost': 0.0,
                    'total_savings': 0.0,
                    'avg_savings_percent': 0.0,
                    'avg_latency_ms': 0,
                    'avg_quality_score': 0,
                    'executions_by_type': {},
                    'today_executions': 0
                }

            # Success metrics
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as successful,
                    COALESCE(SUM(actual_cost), 0) as total_cost,
                    COALESCE(SUM(savings), 0) as total_savings,
                    COALESCE(AVG(savings_percent), 0) as avg_savings_percent,
                    COALESCE(AVG(total_latency_ms), 0) as avg_latency,
                    COALESCE(AVG(quality_score), 0) as avg_quality
                FROM agent_executions
            """)
            row = cursor.fetchone()
            total = row[0] or 0
            successful = row[1] or 0
            total_cost = round(row[2], 6)
            total_savings = round(row[3], 6)
            avg_savings_percent = round(row[4], 2)
            avg_latency_ms = int(row[5])
            avg_quality = round(row[6], 1) if row[6] else 0

            # Executions by agent type
            cursor.execute("""
                SELECT agent_type, COUNT(*) as count,
                       SUM(savings) as saved,
                       AVG(total_latency_ms) as avg_lat
                FROM agent_executions
                GROUP BY agent_type
            """)
            type_rows = cursor.fetchall()
            executions_by_type = {
                row[0]: {
                    'count': row[1],
                    'savings': round(row[2], 6),
                    'avg_latency_ms': int(row[3])
                }
                for row in type_rows
            }

            # Today's activity
            cursor.execute("""
                SELECT COUNT(*) FROM agent_executions
                WHERE DATE(created_at) = DATE('now')
            """)
            today_executions = cursor.fetchone()[0]

            # Average findings per execution
            cursor.execute("""
                SELECT COALESCE(AVG(findings_count), 0)
                FROM agent_executions
                WHERE success=1
            """)
            avg_findings = round(cursor.fetchone()[0], 1)

            return {
                'total_executions': total,
                'successful_executions': successful,
                'success_rate': round((successful / total * 100) if total > 0 else 100, 1),
                'total_cost': total_cost,
                'total_savings': total_savings,
                'avg_savings_percent': avg_savings_percent,
                'avg_latency_ms': avg_latency_ms,
                'avg_quality_score': avg_quality,
                'avg_findings': avg_findings,
                'executions_by_type': executions_by_type,
                'today_executions': today_executions
            }

    def get_sql_sandbox_stats(self):
        """Get SQL Sandbox usage statistics."""
        with _db_connection() as conn:
            cursor = conn.cursor()

            # Total uploads (files ingested)
            cursor.execute("SELECT COUNT(*) FROM sql_sandbox_requests WHERE request_type='upload'")
            files_ingested = cursor.fetchone()[0]

            # Total queries executed
            cursor.execute("SELECT COUNT(*) FROM sql_sandbox_requests WHERE request_type='query'")
            queries_executed = cursor.fetchone()[0]

            # Unique sessions (count distinct IP hashes)
            cursor.execute("SELECT COUNT(DISTINCT ip_hash) FROM sql_sandbox_requests")
            sessions = cursor.fetchone()[0]

            # Success rate
            cursor.execute("""
                SELECT
                    ROUND(AVG(success) * 100, 1) as success_rate
                FROM sql_sandbox_requests
                WHERE request_type='query'
            """)
            row = cursor.fetchone()
            success_rate = row[0] if row[0] else 100.0

            # Average query latency
            cursor.execute("""
                SELECT AVG(query_latency_ms)
                FROM sql_sandbox_requests
                WHERE request_type='query' AND query_latency_ms IS NOT NULL
            """)
            row = cursor.fetchone()
            avg_latency = round(row[0], 1) if row[0] else 0

            # File type breakdown
            cursor.execute("""
                SELECT file_type, COUNT(*) as count
                FROM sql_sandbox_requests
                WHERE request_type='upload' AND file_type IS NOT NULL
                GROUP BY file_type
            """)
            file_type_rows = cursor.fetchall()
            file_types = {row[0]: row[1] for row in file_type_rows}

            # Calculate file type counts for stats page
            sqlite_files = sum(v for k, v in file_types.items() if k in ['.sqlite', '.db', '.sqlite3'])
            dump_files = file_types.get('.sql', 0)
            spreadsheet_files = sum(v for k, v in file_types.items() if k in ['.csv', '.xlsx'])

            # DML blocked attempts (failed queries due to security)
            cursor.execute("""
                SELECT COUNT(*) FROM sql_sandbox_requests
                WHERE request_type='query' AND success=0
            """)
            dml_blocked = cursor.fetchone()[0]

            # Today's activity
            cursor.execute("""
                SELECT COUNT(*) FROM sql_sandbox_requests
                WHERE DATE(created_at) = DATE('now')
            """)
            today_requests = cursor.fetchone()[0]

            return {
                'sessions': sessions,
                'files_ingested': files_ingested,
                'queries_executed': queries_executed,
                'dml_blocked': dml_blocked,
                'sqlite_files': sqlite_files,
                'dump_files': dump_files,
                'spreadsheet_files': spreadsheet_files,
                'success_rate': success_rate,
                'avg_latency_ms': avg_latency,
                'file_types': file_types,
                'today_requests': today_requests
            }

    def get_summary(self):
        """Get statistics summary for dashboard."""
        with _db_connection() as conn:
            cursor = conn.cursor()

            # Total conversions
            total = cursor.execute('SELECT COUNT(*) FROM conversions').fetchone()[0]

            # Today's conversions
            today = datetime.now().strftime("%Y-%m-%d")
            today_count = cursor.execute(
                'SELECT COUNT(*) FROM conversions WHERE DATE(created_at) = ?', (today,)
            ).fetchone()[0]

            # This week's conversions
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            week_count = cursor.execute(
                'SELECT COUNT(*) FROM conversions WHERE DATE(created_at) >= ?', (week_ago,)
            ).fetchone()[0]

            # Total bytes processed
            total_bytes = cursor.execute(
                'SELECT COALESCE(SUM(file_size), 0) FROM conversions'
            ).fetchone()[0]

            # Format bytes
            if total_bytes >= 1024 * 1024 * 1024:
                bytes_formatted = f"{total_bytes / (1024**3):.2f} GB"
            elif total_bytes >= 1024 * 1024:
                bytes_formatted = f"{total_bytes / (1024**2):.2f} MB"
            else:
                bytes_formatted = f"{total_bytes / 1024:.2f} KB"

            # Unique users
            unique_users = cursor.execute(
                'SELECT COUNT(DISTINCT ip_hash) FROM conversions'
            ).fetchone()[0]

            # Errors
            errors = cursor.execute('SELECT COUNT(*) FROM errors').fetchone()[0]
            error_rate = f"{(errors / max(total, 1) * 100):.1f}%"

            # Rate limit hits
            rate_limits = cursor.execute(
                "SELECT COUNT(*) FROM security_events WHERE event_type = 'rate_limit'"
            ).fetchone()[0]

            # Blocked requests
            blocked = cursor.execute(
                "SELECT COUNT(*) FROM security_events WHERE event_type LIKE 'blocked:%'"
            ).fetchone()[0]

            # Conversions by type
            type_rows = cursor.execute(
                'SELECT file_type, COUNT(*) as cnt FROM conversions GROUP BY file_type ORDER BY cnt DESC'
            ).fetchall()
            conversions_by_type = {row['file_type']: row['cnt'] for row in type_rows}

            # Conversions by day (last 7 days)
            day_rows = cursor.execute('''
                SELECT DATE(created_at) as day, COUNT(*) as cnt
                FROM conversions
                WHERE DATE(created_at) >= ?
                GROUP BY DATE(created_at)
                ORDER BY day
            ''', (week_ago,)).fetchall()
            conversions_by_day = {row['day']: row['cnt'] for row in day_rows}

            # Conversions by hour
            hour_rows = cursor.execute('''
                SELECT strftime('%H', created_at) as hour, COUNT(*) as cnt
                FROM conversions
                GROUP BY strftime('%H', created_at)
            ''').fetchall()
            conversions_by_hour = {row['hour']: row['cnt'] for row in hour_rows}

            # Last conversion
            last = cursor.execute(
                'SELECT created_at FROM conversions ORDER BY id DESC LIMIT 1'
            ).fetchone()
            last_conversion = last['created_at'] if last else None

            # Service start time
            started = cursor.execute(
                "SELECT value FROM service_info WHERE key = 'started_at'"
            ).fetchone()
            uptime_since = started['value'] if started else None

            # Recent security events
            events = cursor.execute('''
                SELECT event_type as type, ip_hash, created_at as timestamp
                FROM security_events
                ORDER BY id DESC LIMIT 10
            ''').fetchall()
            recent_security_events = [
                {"type": e['type'], "ip_hash": e['ip_hash'], "timestamp": e['timestamp']}
                for e in events
            ]

            # Contact requests count
            contact_count = cursor.execute('SELECT COUNT(*) FROM contact_requests').fetchone()[0]

            # Capacity exceeded count
            try:
                capacity_exceeded = cursor.execute('SELECT COUNT(*) FROM capacity_events').fetchone()[0]
            except Exception:
                capacity_exceeded = 0

            # Analyze requests count
            try:
                analyze_count = cursor.execute('SELECT COUNT(*) FROM analyze_requests').fetchone()[0]
            except Exception:
                analyze_count = 0

            # Chunk requests count and total chunks
            try:
                chunk_count = cursor.execute('SELECT COUNT(*) FROM chunk_requests').fetchone()[0]
                total_chunks = cursor.execute(
                    'SELECT COALESCE(SUM(chunks_generated), 0) FROM chunk_requests'
                ).fetchone()[0]
            except Exception:
                chunk_count = 0
                total_chunks = 0

            # Compare requests count
            try:
                compare_count = cursor.execute('SELECT COUNT(*) FROM compare_requests').fetchone()[0]
            except Exception:
                compare_count = 0

            # Recent errors with details
            try:
                error_rows = cursor.execute('''
                    SELECT id, error_type, error_message, created_at
                    FROM errors
                    ORDER BY id DESC LIMIT 10
                ''').fetchall()
                recent_errors = [
                    {
                        "id": e['id'],
                        "type": e['error_type'] or "unknown",
                        "message": e['error_message'],
                        "timestamp": e['created_at']
                    }
                    for e in error_rows
                ]
                # Errors by type
                error_type_rows = cursor.execute('''
                    SELECT COALESCE(error_type, 'unknown') as etype, COUNT(*) as cnt
                    FROM errors
                    GROUP BY error_type
                    ORDER BY cnt DESC
                ''').fetchall()
                errors_by_type = {row['etype']: row['cnt'] for row in error_type_rows}
            except Exception:
                recent_errors = []
                errors_by_type = {}

            return {
                "total_conversions": total,
                "today_conversions": today_count,
                "week_conversions": week_count,
                "total_data_processed": bytes_formatted,
                "total_bytes": total_bytes,
                "unique_users": unique_users,
                "errors": errors,
                "error_rate": error_rate,
                "rate_limit_hits": rate_limits,
                "blocked_requests": blocked,
                "capacity_exceeded": capacity_exceeded,
                "conversions_by_type": conversions_by_type,
                "conversions_by_day": conversions_by_day,
                "conversions_by_hour": conversions_by_hour,
                "last_conversion": last_conversion,
                "uptime_since": uptime_since,
                "recent_security_events": recent_security_events,
                "contact_requests": contact_count,
                "analyze_requests": analyze_count,
                "chunk_requests": chunk_count,
                "total_chunks_generated": total_chunks,
                "compare_requests": compare_count,
                "recent_errors": recent_errors,
                "errors_by_type": errors_by_type
            }

    def get_api_stats(self):
        """Get API-friendly statistics."""
        summary = self.get_summary()
        
        # Calculate uptime in seconds
        uptime_seconds = 0
        if summary["uptime_since"]:
            try:
                start_time = datetime.fromisoformat(summary["uptime_since"])
                uptime_delta = datetime.now() - start_time
                uptime_seconds = int(uptime_delta.total_seconds())
            except (ValueError, TypeError):
                uptime_seconds = 0
        
        return {
            "success": True,
            "status": "operational",
            "statistics": {
                "conversions": {
                    "total": summary["total_conversions"],
                    "today": summary["today_conversions"],
                    "this_week": summary["week_conversions"],
                    "conversions_by_day": summary["conversions_by_day"]
                },
                "data_processed": {
                    "formatted": summary["total_data_processed"],
                    "bytes": summary["total_bytes"]
                },
                "users": {
                    "unique": summary["unique_users"]
                },
                "reliability": {
                    "errors": summary["errors"],
                    "error_rate": summary["error_rate"],
                    "errors_by_type": summary.get("errors_by_type", {}),
                    "rate_limits": summary["rate_limit_hits"],
                    "blocked": summary["blocked_requests"],
                    "capacity_exceeded": summary["capacity_exceeded"]
                },
                "popular_formats": summary["conversions_by_type"],
                "ai_features": {
                    "analyze_requests": summary.get("analyze_requests", 0),
                    "chunk_requests": summary.get("chunk_requests", 0),
                    "total_chunks_generated": summary.get("total_chunks_generated", 0),
                    "compare_requests": summary.get("compare_requests", 0)
                },
                "contact_requests": summary.get("contact_requests", 0)
            },
            "last_conversion": summary["last_conversion"],
            "service_started": summary["uptime_since"],
            "uptime_seconds": uptime_seconds,
            "recent_security_events": summary["recent_security_events"],
            "recent_errors": summary.get("recent_errors", []),
            "sql_sandbox": self.get_sql_sandbox_stats(),
            "cost_tracking": self.get_cost_stats(),  # v3.0 CFO Hook
            "agent_workflows": self.get_agent_stats(),  # v3.1 Agentic Workflows
            "response_quality": self.get_evaluation_stats()  # v3.2 Evaluation-Driven Development
        }

    def get_contact_requests(self):
        """Get all contact requests for admin view."""
        with _db_connection() as conn:
            rows = conn.execute(
                'SELECT * FROM contact_requests ORDER BY created_at DESC'
            ).fetchall()
            return [dict(row) for row in rows]


# Global statistics instance
stats = Statistics()
