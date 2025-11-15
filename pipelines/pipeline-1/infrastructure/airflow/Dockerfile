FROM apache/airflow:3.1.3-python3.12
# Copy requirements file
COPY pipeline_code/requirements.txt /tmp/requirements.txt
# Install dependencies
RUN pip install --no-cache-dir -r /tmp/requirements.txt