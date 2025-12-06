# ADR 002: Free Tier Deployment Strategy

## Status
Accepted

## Context
The project requires a hosting solution that is cost-effective (ideally free) while demonstrating "Tech Lead" capabilities like Docker containerization and infrastructure management. Options considered:
1.  **Serverless (Cloud Run/Lambda)**: Scales to zero, but cold starts and memory limits can be restrictive for AI models.
2.  **Kubernetes (GKE)**: Overkill for a single app; control plane costs money.
3.  **Virtual Machine (GCP Compute Engine)**: Full control, persistent state option, free tier available.

## Decision
We have decided to deploy on a **GCP Compute Engine `e2-micro` instance** using **Docker**.

## Justification
*   **Cost**: The `e2-micro` instance is part of GCP's "Always Free" tier.
*   **Control**: Full root access allows for custom security hardening (UFW, Fail2Ban) and swap file configuration (critical for 1GB RAM limit).
*   **Portability**: Docker ensures the application can be moved to any other host (AWS EC2, DigitalOcean) without code changes.

## Technical Constraints & Mitigations
*   **Constraint**: `e2-micro` has only 1GB RAM.
    *   *Mitigation*: We configure a 1GB Swap File in `deploy.sh`.
    *   *Mitigation*: We use a semaphore to limit concurrent heavy operations (embeddings).
*   **Constraint**: No static IP in free tier.
    *   *Mitigation*: We accept dynamic IP or use a free DNS service (Cloudflare) to manage it.

## Enterprise Context (Production Vision)
While this portfolio demonstrates a public deployment on GCP Free Tier, the **Docker-based architecture** is intentionally chosen to support:
1.  **Private VPC Deployment**: The container can run inside a private subnet with no public internet access.
2.  **On-Premise / Air-Gapped**: The system has zero external dependencies (no API calls to OpenAI/Anthropic), making it perfect for air-gapped secure environments.
3.  **Hybrid Cloud**: Can be deployed on AWS Outposts, Azure Stack, or private data centers.

## Alternatives Rejected
*   **Google Cloud Storage (GCS)**: Rejected due to ADR-001 (Zero Data Retention).
*   **Cloud Run**: Rejected due to potential cold start latency with loading AI models.
