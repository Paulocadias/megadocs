# Deploying to Google Cloud Platform (Free Tier)

This guide explains how to deploy the DocsSite to a **Google Cloud Platform (GCP) Compute Engine e2-micro instance**, which is eligible for the "Always Free" tier.

## Prerequisites

- A Google Cloud Platform account (requires credit card for identity verification, but you won't be charged if you stay within limits).
- A domain name (e.g., `paulocadias.com`) - optional but recommended.

## Step 1: Create a Project and VM

1.  **Go to Console:** Visit [console.cloud.google.com](https://console.cloud.google.com/).
2.  **New Project:** Create a new project (e.g., "megadocs-production").
3.  **Navigate to Compute Engine:** Go to **Compute Engine** -> **VM instances**.
4.  **Create Instance:** Click **Create Instance**.
5.  **Configure for Free Tier (CRITICAL):**
    *   **Name:** `megadocs-server`
    *   **Region:** Must be one of: `us-west1` (Oregon), `us-central1` (Iowa), or `us-east1` (South Carolina).
    *   **Zone:** Any zone in the chosen region.
    *   **Machine configuration:**
        *   Series: **E2**
        *   Machine type: **e2-micro** (2 vCPU, 1 GB memory)
    *   **Boot disk:**
        *   Click "Change".
        *   OS: **Ubuntu** (select "Ubuntu 22.04 LTS" or 24.04 LTS).
        *   Boot disk type: **Standard persistent disk** (Balanced or SSD are NOT free).
        *   Size: **30 GB** (Max allowed for free tier).
    *   **Firewall:** Check both **Allow HTTP traffic** and **Allow HTTPS traffic**.
6.  **Create:** Click **Create** and wait for the VM to start.

## Step 2: Connect and Setup Environment

1.  **SSH:** Click the **SSH** button next to your instance in the console.
2.  **Update System:**
    ```bash
    sudo apt update && sudo apt upgrade -y
    ```
3.  **Install Docker & Git:**
    ```bash
    sudo apt install -y docker.io git
    sudo usermod -aG docker $USER
    # Log out and log back in for group changes to take effect
    exit
    ```
    (Click SSH again to reconnect)

## Step 3: Deploy the Application

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/YOUR_USERNAME/DocsSite.git
    cd DocsSite
    ```
    *(Note: You may need to generate a Personal Access Token on GitHub and use it as the password if your repo is private)*

2.  **Run Deployment Script:**
    We have included a script to automate the installation of Docker, building the image, and running the container.

    ```bash
    # Make the script executable
    chmod +x deploy.sh

    # Run it
    ./deploy.sh
    ```

    **Note:** The first time you run this, it might ask you to log out and log back in to apply Docker permissions. If so:
    1.  Type `exit` to disconnect.
    2.  Reconnect via SSH.
    3.  Run `cd DocsSite && ./deploy.sh` again.

    The script will:
    - Install Docker and Git.
    - Create a `.env` file with a secure secret key.
    - Build the Docker image.
    - Start the application on port 80.

## Step 4: Configure Domain (Optional)

1.  **Get External IP:** In the GCP Console, find the **External IP** of your VM.
2.  **Make IP Static:** Go to **VPC network** -> **IP addresses**. Find your VM's IP and click "Reserve" to make it static (so it doesn't change on reboot).
3.  **Update DNS:** Go to your domain registrar (e.g., Namecheap, GoDaddy).
    *   Create an **A Record** for `@` pointing to your VM's External IP.
    *   Create a **CNAME Record** for `www` pointing to `@`.

## Step 5: Enable HTTPS (SSL)

For a production app, you should use HTTPS. The easiest way is to use Caddy or Nginx as a reverse proxy with Let's Encrypt.

### Option A: Quick Caddy Setup (Easiest)

1.  Stop the current container:
    ```bash
    docker stop docssite && docker rm docssite
    ```
2.  Run Caddy as a reverse proxy:
    ```bash
    # Run DocsSite on localhost only
    docker run -d --name docssite -p 127.0.0.1:5000:5000 --restart always -v $(pwd)/data:/app/data docssite

    # Run Caddy
    docker run -d --name caddy --restart always \
      -p 80:80 -p 443:443 \
      -v caddy_data:/data \
      caddy caddy reverse-proxy --from yourdomain.com --to host.docker.internal:5000
    ```

## Step 6: Setup Cloudflare (Highly Recommended)

For free SSL, DDoS protection, and faster speeds, use Cloudflare.

1.  **Create Account:** Go to [cloudflare.com](https://www.cloudflare.com/) and sign up.
2.  **Add Site:** Enter your domain (e.g., `paulocadias.com`).
3.  **Select Plan:** Choose the **Free** plan.
4.  **Update DNS:** Cloudflare will give you two nameservers (e.g., `bob.ns.cloudflare.com`). Go to your domain registrar and replace your current nameservers with these.
5.  **Configure SSL:**
    *   Go to **SSL/TLS** -> **Overview**.
    *   Set encryption mode to **Full**.
6.  **Configure DNS Records:**
    *   Add an **A record** for `@` pointing to your GCP VM's External IP.
    *   Add a **CNAME record** for `www` pointing to `@`.
    *   Make sure the "Proxy status" cloud icon is **Orange** (Proxied).

## Maintenance

- **View Logs:** `docker logs docssite`
- **Update App:**
    ```bash
    cd DocsSite
    git pull
    ./deploy.sh
    ```

