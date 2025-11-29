# Free Python Hosting Alternatives Research

Research conducted: November 2025

## Overview

This document evaluates free Python/Flask hosting alternatives for DocsSite. The app requires:
- File uploads up to 50MB
- Processing time for document conversion (can take seconds to minutes for large files)
- SQLite database support
- Custom domain support (paulocadias.com)

---

## Platform Comparison

| Platform | Free Tier | File Upload Limit | Timeout | Custom Domain | Best For |
|----------|-----------|-------------------|---------|---------------|----------|
| **PythonAnywhere** | Yes (permanent) | 100MB | ~5 min | Paid only | Learning/Portfolio |
| **Render** | Yes (limited) | No hard limit | 30 sec | Yes | Simple APIs |
| **Railway** | $5 credit | Not specified | Flexible | Yes | Quick prototypes |
| **Fly.io** | ~$5/month free | Flexible | Flexible | Yes | Production apps |

---

## Detailed Analysis

### 1. PythonAnywhere

**Pricing:** Free tier available (permanent)

**Free Tier Includes:**
- 1 web app at `your-username.pythonanywhere.com`
- 512MB storage
- Low CPU/bandwidth allocation
- No outbound internet access (whitelist only)

**Limitations for DocsSite:**
- **Upload limit: 100MB hard cap** (our 50MB limit fits)
- **Response timeout: ~5 minutes** (sufficient for conversions)
- **No custom domain on free tier** (would need paid plan for paulocadias.com)
- **Low CPU** - may cause slow conversions during peak times
- **No SSH access** on free tier

**Paid Plans:** Start at $5/month with custom domains, SSH, more CPU

**Verdict:** Good for testing/portfolio. Would need paid plan for paulocadias.com domain.

---

### 2. Render

**Pricing:** Free tier with usage limits

**Free Tier Includes:**
- 750 hours/month of web service runtime
- Auto-deploy from Git
- Free SSL/TLS
- Custom domain support

**Limitations for DocsSite:**
- **30-second request timeout** - CRITICAL ISSUE for file processing
- **Worker timeout errors** common on free tier
- **Database destroyed after 90 days** on free tier
- **Suspended if usage limits exceeded**
- **No console access** on free tier

**Workarounds:**
- Would need Celery + Redis for background processing
- Adds significant complexity

**Paid Plans:** Start at $7/month for individual service

**Verdict:** NOT RECOMMENDED - 30-second timeout makes file conversion unreliable.

---

### 3. Railway

**Pricing:** $5 one-time trial credit, then $5/month Hobby plan

**Free Trial Includes:**
- $5 credit (one-time, runs out fast for 24/7 apps)
- Auto-detection of Python apps
- Custom domain support
- PostgreSQL available

**Limitations for DocsSite:**
- **Trial credit exhausts quickly** (days to weeks)
- **No permanent free tier** - subscription required after trial
- Usage-based pricing can be unpredictable

**Paid Plans:** $5/month Hobby (includes $5 usage credit)

**Verdict:** Good developer experience but no sustainable free option.

---

### 4. Fly.io

**Pricing:** Pay-per-use, first ~$5/month effectively free

**Free Allowance Includes:**
- ~$5/month of free usage
- Multiple regions available
- Custom domain support
- Flexible resource allocation

**Limitations for DocsSite:**
- **Credit card required** to sign up
- **Usage-based billing** - could exceed free allowance
- More complex setup than other platforms
- Container-based (needs Dockerfile)

**Paid Plans:** Usage-based ($0.02/GB bandwidth, compute per-second)

**Verdict:** Most flexible but requires credit card and more DevOps knowledge.

---

### 5. Major Cloud Providers (AWS / GCP / Azure)

For a standard Flask app with SQLite persistence, a Virtual Machine (VM) is the best option.

| Provider | Free Tier Offering | Duration | Specs | Verdict |
|----------|-------------------|----------|-------|---------|
| **GCP** | **Compute Engine e2-micro** | **Always Free** | 2 vCPU, 1GB RAM, 30GB Disk | **BEST OPTION** - Permanent free VM |
| **AWS** | EC2 t2.micro / t3.micro | 12 Months | 1 vCPU, 1GB RAM, 30GB Disk | Good, but expires after 1 year |
| **Azure** | Virtual Machine B1s | 12 Months | 1 vCPU, 1GB RAM, 64GB Disk | Good, but expires after 1 year |

**Why GCP e2-micro is the winner:**
- It is part of the "Always Free" tier (does not expire after 12 months).
- Provides a full Linux VM (Debian/Ubuntu) where you can install Python, Nginx, etc.
- Persistent disk allows SQLite to work perfectly.
- **Region Restriction:** Must use `us-west1`, `us-central1`, or `us-east1`.

---

## Recommendations

### For "Forever Free" Production (Recommended)

**Winner: Google Cloud Platform (e2-micro VM)**

Reasons:
- **True Free Tier:** Runs 24/7 for free if configured correctly (standard persistent disk, specific regions).
- **Full Control:** You get a full Linux server.
- **Persistence:** SQLite works natively on the disk.
- **Scalable:** Easy to upgrade if needed later.

See the [GCP Free Tier Guide](gcp-free-tier-guide.md) for setup instructions.

### For Portfolio/Demo (Easiest Setup)

**Winner: PythonAnywhere (Paid Basic - $5/month)**

Reasons:
- Simple deployment (no Docker needed)
- 5-minute timeout works for file processing
- 100MB upload limit exceeds our 50MB requirement
- Custom domain support
- Python-focused platform (good for resume)

### For Production Scale (Paid)

**Winner: Fly.io or Railway**

Reasons:
- Better performance
- More flexible resource allocation
- Global CDN options

---

## Migration Considerations

If moving from DreamHost to PythonAnywhere:

1. **Environment Variables:** Set via web interface
2. **SQLite:** Works out of the box
3. **File Paths:** May need adjustment for PythonAnywhere directory structure
4. **WSGI:** Uses own WSGI config (not Passenger)
5. **Domain:** Configure in PythonAnywhere dashboard + DNS

### Code Changes Needed

Minimal changes expected:
- Update file paths for PythonAnywhere structure
- Review WSGI configuration
- Test rate limiting with shared IP proxy

---

## Sources

- [PythonAnywhere Pricing](https://www.pythonanywhere.com/pricing/)
- [PythonAnywhere Upload Limits](https://www.pythonanywhere.com/forums/topic/13442/)
- [Render Flask Deployment](https://testdriven.io/blog/flask-render-deployment/)
- [Render Timeout Issues](https://community.render.com/t/increase-flask-service-timeout-limit/1664)
- [Railway Pricing](https://railway.com/pricing)
- [Railway Flask Guide](https://docs.railway.com/guides/flask)
- [Fly.io Pricing](https://fly.io/pricing/)
- [Python Hosting Comparison 2025](https://www.nandann.com/blog/python-hosting-options-comparison)
- [Best Flask Hosting 2025](https://codeless.co/best-flask-hosting/)
