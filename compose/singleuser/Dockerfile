FROM apache/spark:3.5.9-java17-python3

USER root

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3-pip python3-venv curl git ca-certificates libopenblas0 \
 && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir \
      "jupyterhub==5.*" jupyterlab notebook ipykernel \
      pyspark==3.5.9 pandas pyarrow matplotlib \
      cassandra-driver neo4j findspark hdfs

ENV COURSIER_CACHE=/opt/coursier-cache
ARG ALMOND_VERSION=0.14.1
ARG SCALA_VERSION=2.12.18
RUN curl -fsSL -o /usr/local/bin/coursier https://github.com/coursier/launchers/raw/master/coursier \
 && chmod +x /usr/local/bin/coursier \
 && coursier launch --fork almond:${ALMOND_VERSION} --scala ${SCALA_VERSION} -- \
      --install --global --id scala212 --display-name "Scala 2.12 (Almond)" \
 && chmod -R a+rX /usr/local/share/jupyter/kernels/scala212 \
 && chmod -R a+rwX /opt/coursier-cache

# Konektory dla Sparka 3.5 (Scala 2.12) w classpath sterownika i executorów: Cassandra, Neo4j, Iceberg
ARG CASSANDRA_CONNECTOR=3.5.1
ARG NEO4J_CONNECTOR=5.6.0_for_spark_3
ARG ICEBERG_VERSION=1.12.0
RUN M=https://repo1.maven.org/maven2 \
 && curl -fsSL -o /opt/spark/jars/spark-cassandra-connector-assembly_2.12-${CASSANDRA_CONNECTOR}.jar $M/com/datastax/spark/spark-cassandra-connector-assembly_2.12/${CASSANDRA_CONNECTOR}/spark-cassandra-connector-assembly_2.12-${CASSANDRA_CONNECTOR}.jar \
 && curl -fsSL -o /opt/spark/jars/neo4j-connector-apache-spark_2.12-${NEO4J_CONNECTOR}.jar $M/org/neo4j/neo4j-connector-apache-spark_2.12/${NEO4J_CONNECTOR}/neo4j-connector-apache-spark_2.12-${NEO4J_CONNECTOR}.jar \
 && curl -fsSL -o /opt/spark/jars/iceberg-spark-runtime-3.5_2.12-${ICEBERG_VERSION}.jar $M/org/apache/iceberg/iceberg-spark-runtime-3.5_2.12/${ICEBERG_VERSION}/iceberg-spark-runtime-3.5_2.12-${ICEBERG_VERSION}.jar \
 && chmod 0644 /opt/spark/jars/*connector* /opt/spark/jars/iceberg*

RUN useradd -m -u 1000 -s /bin/bash jovyan \
 && mkdir -p /home/jovyan/work /tmp/spark \
 && chown -R jovyan:jovyan /home/jovyan /tmp/spark

# install tworzy nowy plik z prawami 0644 (COPY przenosi też ACL z katalogu budowania, co blokuje odczyt przez użytkownika kontenera)
COPY spark-defaults.conf predef.sc log4j2.properties core-site.xml hdfs-site.xml metrics.properties hdfs sparkhdfs.py /tmp/
RUN install -D -m 0644 /tmp/spark-defaults.conf /opt/spark/conf/spark-defaults.conf \
 && install -D -m 0644 /tmp/log4j2.properties /opt/spark/conf/log4j2.properties \
 && install -D -m 0644 /tmp/core-site.xml /opt/spark/conf/core-site.xml \
 && install -D -m 0644 /tmp/hdfs-site.xml /opt/spark/conf/hdfs-site.xml \
 && install -D -m 0644 /tmp/metrics.properties /opt/spark/conf/metrics.properties \
 && install -D -m 0755 /tmp/hdfs /usr/local/bin/hdfs \
 && install -D -m 0644 /tmp/sparkhdfs.py /usr/local/lib/python3.10/dist-packages/sparkhdfs.py \
 && install -D -m 0644 /tmp/predef.sc /opt/almond/predef.sc \
 && rm /tmp/spark-defaults.conf /tmp/log4j2.properties /tmp/predef.sc /tmp/core-site.xml /tmp/hdfs-site.xml /tmp/metrics.properties /tmp/hdfs /tmp/sparkhdfs.py

# Almond uruchamia Sparka w swojej JVM bez spark-submit, więc nie czyta spark-defaults.conf.
# Spark czyta jednak właściwości systemowe "spark.*", więc przepisujemy plik na argumenty -D kernela.
RUN python3 - <<'PY'
import json
kernel = "/usr/local/share/jupyter/kernels/scala212/kernel.json"
props = []
for line in open("/opt/spark/conf/spark-defaults.conf"):
    line = line.strip()
    if line and not line.startswith("#"):
        key, value = line.split(None, 1)
        if key != "spark.driver.memory":
            props.append(f"-D{key}={value.strip()}")
props.append("-Dlog4j2.configurationFile=/opt/spark/conf/log4j2.properties")
# Kernel to zwykła JVM (bez spark-submit), więc dodajemy to, co spark-submit dodaje sam: dostęp do modułów Javy 17.
# Katalog klas REPL (spark.repl.class.outputDir) Spark udostępnia executorom, dzięki czemu lambdy z komórek działają na klastrze.
opens = ["java.lang", "java.lang.invoke", "java.lang.reflect", "java.io", "java.net", "java.nio", "java.util",
         "java.util.concurrent", "java.util.concurrent.atomic", "jdk.internal.ref", "sun.nio.ch", "sun.nio.cs",
         "sun.security.action", "sun.util.calendar"]
props += ["-XX:+IgnoreUnrecognizedVMOptions"] + [f"--add-opens=java.base/{m}=ALL-UNNAMED" for m in opens]
props += ["--add-opens=java.security.jgss/sun.security.krb5=ALL-UNNAMED", "-Djdk.reflect.useDirectMethodHandle=false",
          "-Dspark.repl.class.outputDir=/tmp/almond-out"]
data = json.load(open(kernel))
# predef.sc ładuje jary Sparka i definiuje spark oraz sc (tworzone dopiero przy pierwszym użyciu)
data["argv"] = data["argv"][:1] + props + data["argv"][1:] + ["--predef", "/opt/almond/predef.sc", "--output-directory", "/tmp/almond-out",
                                                              "--auto-update-lazy-vals=false", "--auto-update-vars=false"]
json.dump(data, open(kernel, "w"), indent=2)
PY

ENV SPARK_HOME=/opt/spark \
    HADOOP_CONF_DIR=/opt/spark/conf \
    HDFS_WEBHDFS=http://namenode:9870 \
    PYSPARK_PYTHON=python3 \
    HOME=/home/jovyan \
    SHELL=/bin/bash

RUN apt-get update && apt-get install -y --no-install-recommends libnss-wrapper \
 && rm -rf /var/lib/apt/lists/*

USER jovyan
WORKDIR /home/jovyan/work
