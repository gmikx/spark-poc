FROM prom/prometheus:v3.1.0
USER root
COPY prometheus.yml /etc/prometheus/prometheus.yml
RUN chmod 0644 /etc/prometheus/prometheus.yml
USER nobody
