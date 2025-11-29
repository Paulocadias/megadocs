import requests
import time
import sys
import os

BASE_URL = "http://localhost:5000"

def print_pass(message):
    print(f"✅ PASS: {message}")

def print_fail(message, error=None):
    print(f"❌ FAIL: {message}")
    if error:
        print(f"   Error: {error}")

def test_health():
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print_pass("Health check")
            return True
        else:
            print_fail(f"Health check returned {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_fail("Could not connect to server. Is it running?")
        return False
    except requests.exceptions.Timeout:
        print_fail("Health check timed out.")
        return False

def test_stats():
    try:
        response = requests.get(f"{BASE_URL}/api/stats", timeout=5)
        if response.status_code == 200 and "statistics" in response.json():
            print_pass("Stats API")
        else:
            print_fail(f"Stats API returned {response.status_code}")
    except Exception as e:
        print_fail("Stats API", e)

def test_formats():
    try:
        response = requests.get(f"{BASE_URL}/api/formats", timeout=5)
        if response.status_code == 200 and "formats" in response.json():
            print_pass("Formats API")
        else:
            print_fail(f"Formats API returned {response.status_code}")
    except Exception as e:
        print_fail("Formats API", e)

def test_convert():
    # Create a dummy file
    with open("test_doc.txt", "w") as f:
        f.write("# Test Document\nThis is a test.")
    
    try:
        files = {'file': open('test_doc.txt', 'rb')}
        response = requests.post(f"{BASE_URL}/api/convert", files=files, timeout=5)
        if response.status_code == 200 and response.json().get("success"):
            print_pass("Convert API")
        else:
            print_fail(f"Convert API returned {response.status_code}: {response.text}")
    except Exception as e:
        print_fail("Convert API", e)
    finally:
        if os.path.exists("test_doc.txt"):
            os.remove("test_doc.txt")

def test_analyze():
    try:
        data = {"content": "# Title\n\nSome content."}
        response = requests.post(f"{BASE_URL}/api/analyze", json=data, timeout=5)
        if response.status_code == 200 and response.json().get("success"):
            print_pass("Analyze API")
        else:
            print_fail(f"Analyze API returned {response.status_code}: {response.text}")
    except Exception as e:
        print_fail("Analyze API", e)

def test_token_count():
    try:
        data = {"content": "Hello world"}
        response = requests.post(f"{BASE_URL}/api/token-count", json=data, timeout=5)
        if response.status_code == 200 and "token_count" in response.json():
            print_pass("Token Count API")
        else:
            print_fail(f"Token Count API returned {response.status_code}: {response.text}")
    except Exception as e:
        print_fail("Token Count API", e)

if __name__ == "__main__":
    print("Starting System Verification...")
    if test_health():
        test_stats()
        test_formats()
        test_convert()
        test_analyze()
        test_token_count()
    else:
        sys.exit(1)
