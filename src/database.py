"""SQLite database layer for TruthLens AI verification history."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Optional

from src.config import get_settings


SCHEMA_VERSION = 1

SCHEMA_SQL = f"""
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS verifications (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    input_type TEXT NOT NULL,
    original_input TEXT NOT NULL,
    extracted_text TEXT,
    source_url TEXT,
    title TEXT,
    extraction_status TEXT NOT NULL,
    extraction_warnings TEXT,  -- JSON array
    extraction_error TEXT,
    language_code TEXT,
    language_name TEXT,
    detection_confidence REAL,
    detection_status TEXT,
    translation_status TEXT,
    translated_text TEXT,
    translation_warnings TEXT,  -- JSON array
    translation_error TEXT,
    classifier_label TEXT,
    classifier_decision_score REAL,
    classifier_model_version TEXT,
    overall_verdict TEXT,
    overall_confidence REAL,
    overall_explanation TEXT,
    warnings TEXT,  -- JSON array
    status TEXT NOT NULL DEFAULT 'completed'
);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    verification_id TEXT NOT NULL,
    claim_index INTEGER NOT NULL,
    claim_text TEXT NOT NULL,
    claim_type TEXT DEFAULT 'factual',
    verification_status TEXT DEFAULT 'pending',
    assessment_verdict TEXT,
    assessment_confidence REAL,
    assessment_explanation TEXT,
    assessment_confidence_type TEXT,
    assessment_limitations TEXT,  -- JSON array
    FOREIGN KEY (verification_id) REFERENCES verifications(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    evidence_index INTEGER NOT NULL,
    source_type TEXT,
    title TEXT,
    publisher TEXT,
    domain TEXT,
    url TEXT,
    published_at TEXT,
    retrieved_at TEXT NOT NULL,
    snippet TEXT,
    content_status TEXT,
    query TEXT,
    connector TEXT,
    connector_status TEXT,
    relevance_score REAL,
    stance TEXT,  -- SUPPORTS, CONTRADICTS, MIXED, NEUTRAL, INSUFFICIENT
    FOREIGN KEY (claim_id) REFERENCES claims(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_verifications_created_at ON verifications(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_claims_verification_id ON claims(verification_id);
CREATE INDEX IF NOT EXISTS idx_evidence_claim_id ON evidence(claim_id);
"""

INSERT_SCHEMA_VERSION = """
INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, datetime('now'));
"""


class Database:
    """SQLite database manager for verification history."""

    def __init__(self, database_url: str | None = None):
        settings = get_settings()
        self.database_url = database_url or settings.database_url
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            # Extract path from sqlite:///./truthlens.db
            if self.database_url.startswith("sqlite:///"):
                db_path = self.database_url[10:]  # Remove "sqlite:///"
            else:
                db_path = "./truthlens.db"

            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        conn.executescript(SCHEMA_SQL)
        conn.execute(INSERT_SCHEMA_VERSION, (SCHEMA_VERSION,))
        conn.commit()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database transactions."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # Verification operations

    def create_verification(self, data: dict[str, Any]) -> str:
        """Create a new verification record."""
        verification_id = data.get("id") or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO verifications (
                    id, created_at, updated_at, input_type, original_input,
                    extracted_text, source_url, title, extraction_status,
                    extraction_warnings, extraction_error,
                    language_code, language_name, detection_confidence, detection_status,
                    translation_status, translated_text, translation_warnings, translation_error,
                    classifier_label, classifier_decision_score, classifier_model_version,
                    overall_verdict, overall_confidence, overall_explanation,
                    warnings, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    verification_id,
                    now,
                    now,
                    data.get("input_type"),
                    data.get("original_input"),
                    data.get("extracted_text"),
                    data.get("source_url"),
                    data.get("title"),
                    data.get("extraction_status"),
                    json.dumps(data.get("extraction_warnings") or []),
                    data.get("extraction_error"),
                    data.get("language_code"),
                    data.get("language_name"),
                    data.get("detection_confidence"),
                    data.get("detection_status"),
                    data.get("translation_status"),
                    data.get("translated_text"),
                    json.dumps(data.get("translation_warnings") or []),
                    data.get("translation_error"),
                    data.get("classifier_label"),
                    data.get("classifier_decision_score"),
                    data.get("classifier_model_version"),
                    data.get("overall_verdict"),
                    data.get("overall_confidence"),
                    data.get("overall_explanation"),
                    json.dumps(data.get("warnings") or []),
                    data.get("status", "completed"),
                ),
            )

            # Insert claims
            for idx, claim in enumerate(data.get("claims") or []):
                claim_id = claim.get("id") or str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO claims (
                        id, verification_id, claim_index, claim_text, claim_type,
                        verification_status, assessment_verdict, assessment_confidence,
                        assessment_explanation, assessment_confidence_type, assessment_limitations
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        claim_id,
                        verification_id,
                        idx,
                        claim.get("text"),
                        claim.get("claim_type", "factual"),
                        claim.get("verification_status", "pending"),
                        claim.get("assessment_verdict"),
                        claim.get("assessment_confidence"),
                        claim.get("assessment_explanation"),
                        claim.get("assessment_confidence_type"),
                        json.dumps(claim.get("assessment_limitations") or []),
                    ),
                )

                # Insert evidence for this claim
                for ev_idx, ev in enumerate(claim.get("evidence") or []):
                    evidence_id = ev.get("id") or str(uuid.uuid4())
                    conn.execute(
                        """
                        INSERT INTO evidence (
                            id, claim_id, evidence_index, source_type, title, publisher,
                            domain, url, published_at, retrieved_at, snippet,
                            content_status, query, connector, connector_status,
                            relevance_score, stance
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            evidence_id,
                            claim_id,
                            ev_idx,
                            ev.get("source_type"),
                            ev.get("title"),
                            ev.get("publisher"),
                            ev.get("domain"),
                            ev.get("url"),
                            ev.get("published_at"),
                            ev.get("retrieved_at") or now,
                            ev.get("snippet"),
                            ev.get("content_status"),
                            ev.get("query"),
                            ev.get("connector"),
                            ev.get("connector_status"),
                            ev.get("relevance_score"),
                            ev.get("stance"),
                        ),
                    )

        return verification_id

    def get_verification(self, verification_id: str) -> dict[str, Any] | None:
        """Get a verification by ID with all related data."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM verifications WHERE id = ?", (verification_id,)
        ).fetchone()

        if not row:
            return None

        result = dict(row)
        result["extraction_warnings"] = json.loads(result["extraction_warnings"] or "[]")
        result["translation_warnings"] = json.loads(result["translation_warnings"] or "[]")
        result["warnings"] = json.loads(result["warnings"] or "[]")

        # Get claims
        claims = []
        for claim_row in conn.execute(
            "SELECT * FROM claims WHERE verification_id = ? ORDER BY claim_index",
            (verification_id,),
        ):
            claim = dict(claim_row)
            claim["assessment_limitations"] = json.loads(
                claim["assessment_limitations"] or "[]"
            )

            # Get evidence for this claim
            evidence = []
            for ev_row in conn.execute(
                "SELECT * FROM evidence WHERE claim_id = ? ORDER BY evidence_index",
                (claim["id"],),
            ):
                evidence.append(dict(ev_row))

            claim["evidence"] = evidence
            claims.append(claim)

        result["claims"] = claims
        return result

    def list_verifications(
        self, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """List verifications with pagination."""
        conn = self._get_connection()
        rows = conn.execute(
            """
            SELECT * FROM verifications
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

        return [dict(row) for row in rows]

    def delete_verification(self, verification_id: str) -> bool:
        """Delete a verification and all related data."""
        with self.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM verifications WHERE id = ?", (verification_id,)
            )
            return cursor.rowcount > 0


# Global database instance
_db: Database | None = None


def get_database() -> Database:
    """Get global database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db