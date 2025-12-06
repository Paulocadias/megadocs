# Deployment Guide - MegaDoc Enterprise Platform

This guide details how to deploy the MegaDoc platform using the provided Infrastructure as Code (IaC) assets.

## Prerequisites

-   [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed and authenticated.
-   [Terraform](https://developer.hashicorp.com/terraform/install) (v1.5.0+) installed.
-   [kubectl](https://kubernetes.io/docs/tasks/tools/) installed.

## 1. Infrastructure Provisioning (Terraform)

Navigate to the `terraform/` directory to provision the GKE cluster, VPC, and Cloud SQL.

```bash
cd terraform
terraform init
terraform plan -out=tfplan -var="project_id=YOUR_PROJECT_ID"
terraform apply tfplan
```

**Outputs:**
-   `kubernetes_cluster_name`: The name of the GKE Autopilot cluster.
-   `kubernetes_cluster_host`: The endpoint of the cluster.

## 2. Cluster Authentication

Configure `kubectl` to communicate with the new GKE cluster.

```bash
gcloud container clusters get-credentials $(terraform output -raw kubernetes_cluster_name) --region europe-west1
```

## 3. Application Deployment (Kubernetes)

Navigate to the `k8s/` directory to deploy the application manifests.

```bash
cd ../k8s
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml
kubectl apply -f hpa.yaml
```

## 4. Verification

Check the status of the deployment and services.

```bash
kubectl get pods
kubectl get services
kubectl get ingress
```

Wait for the Ingress to provision a load balancer IP (this may take 5-10 minutes). Once verified, access the application via the external IP.
