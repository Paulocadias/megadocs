# Security Architecture

DocsSite is built with a "Defense in Depth" approach, prioritizing user privacy through a Zero Data Retention (ZDR) architecture. This document outlines the security measures implemented across the stack.

## 1. Zero Data Retention (ZDR)

The core privacy promise of DocsSite is that **we do not store your data**.

-   **Ephemeral Processing**: Files are uploaded to a temporary directory, processed immediately, and deleted instantly after the response is sent.
-   **Automatic Cleanup**: A failsafe cleanup routine ensures no temporary files remain even if a process crashes.
-   **No Database Storage**: Document content is never saved to a database. Only anonymous metadata (file size, extension, processing time) is logged for statistics.

## 2. Infrastructure Security (GCP & OS Hardening)

We utilize Google Cloud Platform's secure infrastructure with additional hardening layers:

-   **Firewall (UFW)**: Strict whitelist policy. Only ports 22 (SSH), 80 (HTTP), and 443 (HTTPS) are open. All other incoming traffic is blocked.
-   **Brute-Force Protection (Fail2Ban)**: Monitors logs for repeated failed login attempts (SSH) and automatically bans offending IP addresses.
-   **Container Isolation**: The application runs inside a Docker container, isolating it from the host operating system.
-   **Least Privilege**: The application runs as a non-root user inside the container (where applicable) and the Docker daemon is accessed via a specific user group on the host.

## 3. Network Security (Cloudflare)

We recommend and support Cloudflare as the edge security layer:

-   **DDoS Protection**: Absorbs volumetric attacks at the edge before they reach the server.
-   **Web Application Firewall (WAF)**: Blocks common web exploits (SQLi, XSS) and malicious bots.
-   **SSL/TLS Encryption**: Full end-to-end encryption. Cloudflare provides the public certificate, and the server communicates securely.
-   **Bot Management**: Challenges suspicious visitors with CAPTCHAs.

## 4. Application Security

The Flask application implements rigorous security controls:

### Input Validation
-   **Magic Byte Verification**: Files are validated by their binary signature (magic bytes), not just file extensions, preventing malicious file spoofing (e.g., an EXE renamed to PDF).
-   **Strict File Size Limits**: Enforced at multiple levels (Nginx/Cloudflare edge, Flask request header, and actual stream reading) to prevent DoS via disk exhaustion.
-   **Filename Sanitization**: All filenames are stripped of dangerous characters to prevent directory traversal attacks.

### Access Control
-   **Rate Limiting**: IP-based rate limiting (default 20 req/min) prevents abuse.
-   **Concurrency Control**: Semaphore-based locking limits active conversions to prevent CPU/RAM exhaustion on the micro instance.
-   **Honeypot Fields**: Invisible form fields trap automated bots that blindly fill out forms.

### Secure Headers
We enforce modern security headers to protect users in the browser:
-   `Strict-Transport-Security` (HSTS): Forces HTTPS.
-   `Content-Security-Policy` (CSP): Restricts sources of scripts, styles, and images to prevent XSS.
-   `X-Frame-Options: DENY`: Prevents clickjacking.
-   `X-Content-Type-Options: nosniff`: Prevents MIME-type sniffing.
-   `Referrer-Policy: strict-origin-when-cross-origin`: Protects privacy.
-   `Permissions-Policy`: Disables sensitive features (camera, mic, geolocation).

### Session Security
-   `Secure`: Cookies are only sent over HTTPS.
-   `HttpOnly`: Cookies cannot be accessed by JavaScript (XSS mitigation).
-   `SameSite=Lax`: Prevents Cross-Site Request Forgery (CSRF).

## 5. Monitoring & Audit

-   **Request ID Tracking**: Every request is assigned a unique ID (`X-Request-ID`) that is propagated through logs and headers, enabling precise tracing of issues.
-   **Access Logs**: Detailed logs track IP addresses, endpoints, and response codes (without logging sensitive data).
-   **Abuse Detection**: Automatic blocking of IPs that exceed rate limits or trigger security alarms (like honeypots).

---

*This architecture ensures that DocsSite is secure by design, protecting both the platform availability and user data privacy.*
