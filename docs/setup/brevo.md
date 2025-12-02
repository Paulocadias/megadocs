# Brevo SMTP Setup - 5 Minute Guide

## Step-by-Step Setup

### 1. Create Free Brevo Account (2 minutes)

1. Go to: **https://app.brevo.com/account/register**
2. Enter your email
3. Create a password
4. Click "Create my account"
5. Check your email and verify

### 2. Get Your SMTP Key (1 minute)

1. After logging in, go to: **https://app.brevo.com/settings/keys/smtp**
2. Click the **"Generate a new SMTP key"** button
3. Name it: **MegaDoc Contact Form**
4. Click **"Generate"**
5. **Copy the key** - it looks like: `xsmtpsib-a1b2c3d4e5f6g7h8...`

### 3. Update Environment Variables (1 minute)

Set these environment variables (in `.env` file or system):

```bash
CONTACT_EMAIL=your-email@example.com
SMTP_SERVER=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USERNAME=your-brevo-login@example.com
SMTP_PASSWORD=xsmtpsib-your-key-here
```

**Important**:
- `SMTP_USERNAME` = The email you used to sign up for Brevo
- `SMTP_PASSWORD` = The SMTP key you just copied (NOT your Brevo password!)

### 4. Test It! (1 minute)

```bash
# Start your Flask app
python src/app.py

# Open browser
# Go to: http://localhost:8080/contact
# Fill out the form
# Submit
# Check your inbox!
```

---

## What You'll Receive

When someone submits the contact form, you'll get an email like this:

**Subject**: MegaDoc API Request - John Doe

**From**: MegaDoc Contact Form

**Reply-To**: john@example.com (user's email - click reply to respond!)

**Body**:
```
New API Access Request - MegaDoc

Timestamp: 2025-11-29 11:30:00
Request ID: abc123xyz

--- Contact Information ---
Name: John Doe
Email: john@example.com
Company: Acme Corp

--- Request Details ---
Use Case: API Integration

Additional Details:
Looking to integrate document conversion into our workflow...

---
This is an automated message from the MegaDoc contact form.
Reply directly to this email to respond to John Doe.
```

---

## Troubleshooting

### "Authentication failed"

**Problem**: Wrong SMTP key or username

**Solution**:
1. Make sure `SMTP_PASSWORD` is the SMTP key from Brevo (not your Brevo password!)
2. Make sure `SMTP_USERNAME` is your Brevo login email
3. Check for typos - the key is case-sensitive

### "Not receiving emails"

**Problem**: Email might be in spam

**Solution**:
1. Check your spam/junk folder
2. Add `noreply@brevo.com` to your contacts
3. Check Brevo dashboard for send logs: https://app.brevo.com/email/logs

### "Server not found"

**Problem**: Wrong SMTP server

**Solution**:
- Make sure `SMTP_SERVER = "smtp-relay.brevo.com"` (not `smtp.brevo.com`)

---

## Brevo Free Tier Limits

- **300 emails per day** - Perfect for a portfolio site!
- **Unlimited contacts**
- **No expiration**
- **No credit card required**
- **Professional delivery**

For a portfolio/demo site, this is more than enough!

---

## Alternative: Skip Email Setup

If you don't want to set up email right now:

**The contact form still works!**

- Submissions are logged to the console
- You'll see them when running `python src/app.py`
- You can set up Brevo anytime later

---

## Quick Reference

| Setting | Value |
|---------|-------|
| **SMTP Server** | `smtp-relay.brevo.com` |
| **SMTP Port** | `587` |
| **SMTP Username** | Your Brevo login email |
| **SMTP Password** | Your SMTP key (from Brevo dashboard) |
| **Free Limit** | 300 emails/day |

---

## Next Steps

1. Sign up for Brevo: https://app.brevo.com/account/register
2. Get SMTP key: https://app.brevo.com/settings/keys/smtp
3. Set environment variables
4. Test the contact form
5. Receive contact form submissions via email!

**Setup time: ~5 minutes total!**
