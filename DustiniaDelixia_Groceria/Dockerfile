# DustiniaDelixia Groceria — Dockerfile (Custom Airflow Image)
# Dockerfile ini mem-build custom Airflow image dengan semua Python
# dependencies yang sudah ter-install, sehingga container tidak perlu
# menginstall ulang pip packages setiap kali startup (lebih cepat & reliable).

FROM apache/airflow:2.10.5-python3.11

# Label metadata
LABEL maintainer="DustiniaDelixia Groceria Team"
LABEL description="Custom Apache Airflow 2.10.5 image with ClickHouse drivers & data processing libraries"

# Switch ke root untuk install system dependencies jika diperlukan
USER root

# Install curl (diperlukan untuk healthcheck Airflow webserver)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Switch kembali ke airflow user untuk install pip packages
USER airflow

# Copy requirements.txt (--chown agar airflow user bisa hapus setelah install)
COPY --chown=airflow:0 requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt
