FROM grafana/grafana-oss:11.4.0
USER root
COPY grafana/provisioning /etc/grafana/provisioning
COPY grafana/dashboards /etc/grafana/dashboards
RUN chmod -R a+rX /etc/grafana/provisioning /etc/grafana/dashboards
USER 472
