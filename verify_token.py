import os
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("GITHUB_TOKEN")
if not token:
    print("Error: GITHUB_TOKEN not found in .env")
    exit(1)

print(f"Testing token: {token[:10]}...")

headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
response = requests.get("https://api.github.com/user", headers=headers)

if response.status_code == 200:
    user = response.json()
    print(f"Success! Authenticated as: {user['login']}")
    
    # Check repo permissions
    repo_url = "https://api.github.com/repos/Paulocadias/DOCSsite"
    repo_resp = requests.get(repo_url, headers=headers)
    if repo_resp.status_code == 200:
        permissions = repo_resp.json().get("permissions", {})
        print(f"Repo access: OK. Permissions: {permissions}")
        if not permissions.get("push"):
            print("WARNING: You do not have PUSH permission to this repo!")
    elif repo_resp.status_code == 404:
        print("Repo not found (or private and token lacks access).")
    else:
        print(f"Repo check failed: {repo_resp.status_code}")
else:
    print(f"Authentication Failed: {response.status_code}")
    print(response.text)
