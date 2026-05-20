FROM apache/airflow:3.1.3-python3.12
# Install FAB provider directly
RUN pip install --no-cache-dir apache-airflow-providers-fab
# Copy requirements file
COPY orchestration/requirements.txt /tmp/requirements.txt
# Install dependencies
RUN pip install --no-cache-dir -r /tmp/requirements.txt