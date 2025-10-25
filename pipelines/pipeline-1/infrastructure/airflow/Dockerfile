FROM apache/airflow:2.7.3-python3.8
# Copy requirements file
COPY pipeline_code/requirements.txt /tmp/requirements.txt
# Install dependencies
RUN pip install --no-cache-dir -r /tmp/requirements.txt