# Contact Form - FREE Email with Brevo!

The contact form sends emails using **Brevo's free SMTP service**.

## Why Brevo?

- **300 free emails/day** - More than enough!
- **No credit card required** - Completely free
- **No passwords needed** - Just an API key
- **Reliable delivery** - Professional email service
- **Easy setup** - 5 minutes max

## Quick Setup (5 Minutes)

### Step 1: Create Free Brevo Account

1. Go to **https://app.brevo.com/account/register**
2. Sign up with your email
3. Verify your email
4. Skip the onboarding wizard

### Step 2: Get Your SMTP Key

1. Go to **https://app.brevo.com/settings/keys/smtp**
2. Click **"Generate a new SMTP key"**
3. Name it: **MegaDoc Contact Form**
4. Copy the key (looks like: `xsmtpsib-a1b2c3d4...`)

### Step 3: Set Environment Variables

Set these in your `.env` file or system environment:

```bash
CONTACT_EMAIL=your-email@example.com
SMTP_SERVER=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USERNAME=your-brevo-login@example.com
SMTP_PASSWORD=xsmtpsib-your-key-here
```

### Step 4: Test It!

1. Run: `python src/app.py`
2. Go to: `http://localhost:8080/contact`
3. Fill out the form
4. Check your inbox!

## What You'll Receive

**Subject**: MegaDoc API Request - [User's Name]
**From**: MegaDoc Contact Form
**Reply-To**: User's email (click reply to respond!)

**Body includes**:
- Timestamp
- Request ID
- User's IP
- Name, Email, Company
- Use Case
- Message

## Free Tier Limits

- **300 emails/day** - Perfect for a portfolio site!
- **Unlimited contacts**
- **No expiration**
- **No credit card ever**

## Fallback Behavior

If Brevo isn't configured yet:
- Form still works!
- Submissions logged to console
- You can set up Brevo anytime

## Security

- **CSRF Protection**
- **Honeypot** (bot detection)
- **Rate Limiting**
- **Input Validation**
- **Secure SMTP** (TLS encryption)

## Troubleshooting

**"Authentication failed"?**
- Make sure you copied the SMTP key correctly
- Use your Brevo login email for SMTP_USERNAME
- The SMTP key is NOT your Brevo password

**Not receiving emails?**
- Check your spam folder
- Verify CONTACT_EMAIL is correct
- Check Flask console for error messages

**Want to test without Brevo?**
- Just leave the config as-is
- Submissions will log to console
- Set up Brevo when ready!

## Alternative: Other Free SMTP Services

If you prefer something else:

**SendGrid** (100 emails/day free):
```bash
SMTP_SERVER=smtp.sendgrid.net
SMTP_PORT=587
```

**Mailgun** (100 emails/day free):
```bash
SMTP_SERVER=smtp.mailgun.org
SMTP_PORT=587
```

But **Brevo is the easiest** - no verification, no credit card, 300/day!
