import os
import sys
import time
import shutil
import zipfile
import requests
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Configuration
BASE_URL = "http://127.0.0.1:8080"
TEST_DIR = Path("test_data")
OUTPUT_DIR = Path("test_output")
WEBHOOK_PORT = 9090

def setup_test_data():
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
    TEST_DIR.mkdir()
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Create dummy files
    (TEST_DIR / "doc1.txt").write_text("# Document 1\n\nThis is a test.", encoding='utf-8')
    (TEST_DIR / "doc2.txt").write_text("## Document 2\n\nAnother test.", encoding='utf-8')
    (TEST_DIR / "doc3.html").write_text("<html><body><h1>Document 3</h1><p>HTML test.</p></body></html>", encoding='utf-8')

    # Create ZIP
    shutil.make_archive(TEST_DIR / "test_batch", 'zip', TEST_DIR)
    return TEST_DIR / "test_batch.zip"

def test_health():
    print("Testing /health...")
    try:
        resp = requests.get(f"{BASE_URL}/health")
        assert resp.status_code == 200
        print("✅ Health check passed")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False
    return True

def test_batch_upload(zip_path):
    print("Testing Batch Upload (Sync)...")
    try:
        with open(zip_path, 'rb') as f:
            files = {'file': ('test_batch.zip', f, 'application/zip')}
            resp = requests.post(f"{BASE_URL}/api/batch/convert", files=files)
            
        if resp.status_code != 200:
            print(f"❌ Batch upload failed: {resp.status_code} - {resp.text}")
            return False
            
        output_zip = OUTPUT_DIR / "result.zip"
        output_zip.write_bytes(resp.content)
        
        # Verify ZIP content
        with zipfile.ZipFile(output_zip, 'r') as z:
            names = z.namelist()
            print(f"   Received files: {names}")
            assert "doc1.md" in names
            assert "doc2.md" in names
            assert "doc3.md" in names
            
        print("✅ Batch upload passed")
        return True
    except Exception as e:
        print(f"❌ Batch upload error: {e}")
        return False

class WebhookHandler(BaseHTTPRequestHandler):
    received_events = []
    
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        print(f"   Webhook received! Size: {len(post_data)} bytes")
        WebhookHandler.received_events.append(post_data)
        self.send_response(200)
        self.end_headers()

def test_webhook(zip_path):
    print("Testing Webhook...")
    
    # Start mock webhook server
    server = HTTPServer(('localhost', WEBHOOK_PORT), WebhookHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    
    webhook_url = f"http://localhost:{WEBHOOK_PORT}/callback"
    
    try:
        with open(zip_path, 'rb') as f:
            files = {'file': ('test_batch.zip', f, 'application/zip')}
            data = {'webhook_url': webhook_url}
            resp = requests.post(f"{BASE_URL}/api/batch/convert", files=files, data=data)
            
        if resp.status_code != 202:
            print(f"❌ Webhook request failed: {resp.status_code} - {resp.text}")
            return False
            
        print("   Request accepted. Waiting for callback...")
        
        # Wait for webhook
        for _ in range(10):
            if WebhookHandler.received_events:
                break
            time.sleep(1)
            
        if not WebhookHandler.received_events:
            print("❌ Webhook not received within timeout")
            return False
            
        print("✅ Webhook passed")
        return True
        
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return False
    finally:
        server.shutdown()

if __name__ == "__main__":
    print("=== Starting Verification ===")
    zip_path = setup_test_data()
    
    if not test_health():
        sys.exit(1)
        
    if not test_batch_upload(zip_path):
        sys.exit(1)
        
    if not test_webhook(zip_path):
        sys.exit(1)
        
    print("\n🎉 All tests passed!")
    # Cleanup
    shutil.rmtree(TEST_DIR, ignore_errors=True)
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
