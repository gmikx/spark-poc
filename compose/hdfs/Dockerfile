FROM apache/hadoop:3.3.6
USER root
ARG JMX_EXPORTER=1.0.1
RUN mkdir -p /opt/jmx \
 && curl -fsSL -o /opt/jmx/agent.jar https://repo1.maven.org/maven2/io/prometheus/jmx/jmx_prometheus_javaagent/${JMX_EXPORTER}/jmx_prometheus_javaagent-${JMX_EXPORTER}.jar
COPY jmx.yml /opt/jmx/jmx.yml
