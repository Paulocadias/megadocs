# ADR 001: Zero Data Retention (ZDR) Architecture

## Status
Accepted

## Context
The DocsSite platform processes sensitive documents for conversion and analysis. Users, particularly enterprise clients, are concerned about data privacy and the risk of data leaks. Traditional architectures often store uploaded files in cloud storage (e.g., AWS S3, Google Cloud Storage) for processing, which introduces:
1.  **Security Risk**: Persistent storage is a target for attackers.
2.  **Compliance Burden**: GDPR/CCPA requirements for data deletion and management.
3.  **Cost**: Storage costs accumulate over time.

## Decision
We have decided to implement a **Zero Data Retention (ZDR)** architecture.
*   **No Persistent Storage**: Files are never saved to disk or cloud storage (GCS/S3).
*   **In-Memory Processing**: Files are processed entirely in RAM using Python's `BytesIO`.
*   **Ephemeral Lifecycle**: Data exists only for the duration of the HTTP request.

## Consequences

### Positive
*   **Maximum Privacy**: "We can't leak what we don't have."
*   **Simplified Compliance**: No data retention policies or cleanup scripts needed.
*   **Reduced Cost**: Zero spend on cloud storage.

### Negative
*   **Memory Constraints**: Processing large files requires significant RAM (mitigated by strict file size limits and swap).
*   **No Retry Capability**: If a process fails, the user must re-upload the file.
*   **No History**: Users cannot access previously converted files.

## Compliance
This decision aligns with our "Privacy-First" value proposition for the AI Tech Lead portfolio.
