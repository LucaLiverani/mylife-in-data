# Data Platform Infrastructure

This directory contains the infrastructure setup for the data platform, using Docker Compose to orchestrate the following services:

- **Airflow**: For workflow orchestration and scheduling.
- **Kafka**: For real-time data streaming.
- **Storage (MinIO)**: For S3-compatible object storage.

## Getting Started

### Prerequisites

- Docker
- Docker Compose

### Setup

1.  **Create Environment Files**:
    Each service requires a `.env` file for configuration. You can create them from the provided examples:

    ```bash
    cp storage/.env.example storage/.env
    cp kafka/.env.example kafka/.env
    cp airflow/.env.example airflow/.env
    ```

2.  **Configure Environment Variables**:
    Update the `.env` files with your desired credentials and settings. For Airflow, you'll need to generate a Fernet key:

    ```bash
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ```
    Copy the output to the `AIRFLOW__CORE__FERNET_KEY` variable in `airflow/.env`.

3.  **Make Scripts Executable**:
    ```bash
    chmod +x *.sh
    ```

### Usage

- **Start all services**:
  ```bash
  ./start-all.sh
  ```

- **Stop all services**:
  ```bash
  ./stop-all.sh
  ```

- **Cleanup**:
  To stop all services and remove all data, run:
  ```bash
  ./cleanup.sh
  ```
