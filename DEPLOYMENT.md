# Deployment Guide for DreamHost

## Step-by-Step Deployment to paulocadias.com

### 1. Prepare DreamHost Panel

1. Log into your DreamHost panel
2. Go to **Manage Domains** → **paulocadias.com** → **Edit**
3. Enable **Passenger (Python)** checkbox
4. Save changes

### 2. SSH into Server

```bash
ssh YOUR_USERNAME@paulocadias.com
```

### 3. Set Up Python Virtual Environment

```bash
# Navigate to your domain folder
cd ~/paulocadias.com

# Create virtual environment with Python 3
python3 -m venv venv

# Activate it
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### 4. Upload Project Files

Upload via SFTP or Git:

**Option A: SFTP**
Upload these files/folders to `~/paulocadias.com/`:
- `src/` folder
- `static/` folder
- `passenger_wsgi.py`
- `requirements.txt`
- `.htaccess`
- `.env` (create from .env.example)

**Option B: Git (Recommended)**
```bash
cd ~/paulocadias.com
git clone YOUR_PRIVATE_REPO_URL .
```

### 5. Install Dependencies

```bash
cd ~/paulocadias.com
source venv/bin/activate
pip install -r requirements.txt
```

### 6. Configure Environment

```bash
# Create .env file
cp .env.example .env

# Generate a secret key
python -c "import secrets; print(secrets.token_hex(32))"

# Edit .env with your secret key
nano .env
```

### 7. Update Configuration Files

Edit `passenger_wsgi.py` - replace `YOUR_USERNAME` with your actual DreamHost username.

Edit `.htaccess` - replace `YOUR_USERNAME` with your actual DreamHost username.

### 8. Create Required Directories

```bash
mkdir -p ~/paulocadias.com/tmp
```

### 9. Restart Passenger

```bash
touch ~/paulocadias.com/tmp/restart.txt
```

### 10. Test

Visit https://paulocadias.com in your browser.

## Troubleshooting

### Check Logs
```bash
# Passenger error log
cat ~/logs/paulocadias.com/http/error.log

# Application log
cat ~/paulocadias.com/passenger.log
```

### Common Issues

**500 Internal Server Error**
- Check Python path in passenger_wsgi.py
- Verify all dependencies installed: `pip list`
- Check error.log for details

**Import Errors**
- Ensure src/ is in Python path
- Verify markitdown is installed: `pip show markitdown`

**Permission Denied**
- Files should be 644: `chmod 644 *.py`
- Directories should be 755: `chmod 755 src/ static/`

### Restart After Changes
```bash
touch ~/paulocadias.com/tmp/restart.txt
```

## Updating the Site

```bash
cd ~/paulocadias.com
source venv/bin/activate
git pull  # if using git
pip install -r requirements.txt  # if dependencies changed
touch tmp/restart.txt
```
