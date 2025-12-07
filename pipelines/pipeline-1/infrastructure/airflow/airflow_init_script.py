import subprocess
import sys
import os
import time

def run_command(command, check=True, capture_output=False, shell=False):
    """Helper function to run shell commands."""
    try:
        print(f"Running command: {' '.join(command) if isinstance(command, list) else command}")
        result = subprocess.run(command, check=check, capture_output=capture_output, text=True, shell=shell)
        if capture_output:
            print(f"Stdout:\n{result.stdout}")
            print(f"Stderr:\n{result.stderr}")
        return result
    except subprocess.CalledProcessError as e:
        print(f"Command failed with error: {e}")
        if e.stdout:
            print(f"Stdout:\n{e.stdout}")
        if e.stderr:
            print(f"Stderr:\n{e.stderr}")
        sys.exit(1)

def main():
    print("Starting Airflow 3.x initialization with Python script...")

    # Wait for postgres
    print("⏳ Waiting for database...")
    for i in range(30):
        try:
            run_command(["pg_isready", "-h", "postgres", "-p", "5432", "-U", os.environ.get("POSTGRES_USER")], capture_output=True)
            print("PostgreSQL is ready!")
            break
        except SystemExit: # pg_isready failing will cause SystemExit from run_command
            time.sleep(2)
    else:
        print("❌ PostgreSQL did not become ready in time!")
        sys.exit(1)

    # Test connection
    print("🔌 Testing database connection...")
    run_command(["psql", f"postgresql://{os.environ.get('POSTGRES_USER')}:{os.environ.get('POSTGRES_PASSWORD')}@postgres:5432/{os.environ.get('POSTGRES_DB')}", "-c", "SELECT 1"], capture_output=True)

    print("⚠️  Migrating to Airflow 3.x - database will be upgraded automatically")
    print("⚠️  Make sure you have a database backup before proceeding!")

    # Initialize database (handles 2.x -> 3.x migration)
    print("📊 Initializing Airflow database (migrating if needed)...")
    run_command(["/home/airflow/.local/bin/airflow", "db", "migrate"])

    # Create admin user directly via DB shell
    print("👤 Creating admin user...")
    admin_username = os.environ.get("AIRFLOW_ADMIN_USERNAME")
    admin_email = os.environ.get("AIRFLOW_ADMIN_EMAIL")
    admin_password = os.environ.get("AIRFLOW_ADMIN_PASSWORD")

    # Insert user if not exists
    # Note: This is a simplified approach. In a production environment, you would use a more robust way to hash passwords
    # and manage users, potentially through an external authentication system (e.g., LDAP, OAuth).
    # This direct SQL insert is for initialization purposes.
    sql_command = f"""
INSERT INTO ab_user (first_name, last_name, username, email, active, password, login_count, fail_login_count, created_on, changed_on) VALUES
    ('Admin', 'User', '{admin_username}', '{admin_email}', true, '{admin_password}', 0, 0, NOW(), NOW())
ON CONFLICT (username) DO NOTHING;
"""
    run_command(["/home/airflow/.local/bin/airflow", "db", "shell", "-c", sql_command], check=False, capture_output=True)
    print("Admin user creation command sent to DB. Check logs for details or potential 'already exists' messages.")

    # MinIO connection
    print("🔗 Setting up MinIO connection...")
    run_command(["/home/airflow/.local/bin/airflow", "connections", "delete", "minio_s3"], check=False, capture_output=True) # Don't check as it might not exist
    run_command([
        "/home/airflow/.local/bin/airflow", "connections", "add", "minio_s3",
        "--conn-type", "aws", "--conn-login", os.environ.get("MINIO_ROOT_USER"),
        "--conn-password", os.environ.get("MINIO_ROOT_PASSWORD"),
        "--conn-extra", '{"endpoint_url": "http://minio:9000", "region_name": "us-east-1"}'
    ])

    # Kafka connection
    print("🔗 Setting up Kafka connection...\n")
    run_command(["/home/airflow/.local/bin/airflow", "connections", "delete", "kafka_default"], check=False, capture_output=True) # Don't check as it might not exist
    run_command([
        "/home/airflow/.local/bin/airflow", "connections", "add", "kafka_default",
        "--conn-type", "generic", "--conn-host", "kafka", "--conn-port", "9092",
        "--conn-extra", '{"bootstrap.servers": "kafka:9092", "group.id": "airflow"}'
    ])

    # ClickHouse connection
    print("🔗 Setting up ClickHouse connection...\n")
    run_command(["/home/airflow/.local/bin/airflow", "connections", "delete", "clickhouse_default"], check=False, capture_output=True) # Don't check as it might not exist
    run_command([
        "/home/airflow/.local/bin/airflow", "connections", "add", "clickhouse_default",
        "--conn-type", "generic", "--conn-host", "clickhouse", "--conn-port", "9000",
        "--conn-login", "admin", "--conn-password", "clickhouse08062013",
        "--conn-extra", '{"database": "bronze"}'
    ])

    print("Airflow initialization complete!")

if __name__ == "__main__":
    main()
