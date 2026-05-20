# MinIO Setup

This directory contains the necessary files to set up a local MinIO instance using Docker Compose.

## Getting Started

### 1. Prerequisites

Ensure you have Docker and Docker Compose installed on your system.

### 2. Create `.env` file

Before starting, create a `.env` file in this directory. This file will hold your credentials and bucket configuration. You can copy the example file:

```bash
cp .env.example .env
```

Update the `.env` file with your desired values for `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, and `MINIO_BUCKET`.

### 3. Start the Services

You can start the MinIO service using the main `start-all.sh` script in the parent directory, or by running the following command in this directory:

```bash
docker-compose up -d
```

The service defined in `docker-compose.yml` will automatically:
1.  Wait for the MinIO server to be healthy.
2.  Create the bucket specified in your `.env` file.
3.  Set the bucket policy to `public`.

## Accessing MinIO

*   **S3 API Endpoint:** `http://localhost:9000`
*   **MinIO Console:** `http://localhost:9001`

Log in to the console using the `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` from your `.env` file.
