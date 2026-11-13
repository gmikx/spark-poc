FROM apache/spark:4.0.0

USER root

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3-pip python3-venv curl git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir \
      "jupyterhub==5.*" jupyterlab notebook ipykernel \
      pyspark==4.0.0 pandas matplotlib \
      cassandra-driver neo4j

ENV COURSIER_CACHE=/opt/coursier-cache
ARG ALMOND_VERSION=0.14.1
ARG SCALA_VERSION=2.13.16
RUN curl -fsSL -o /usr/local/bin/coursier https://github.com/coursier/launchers/raw/master/coursier \
 && chmod +x /usr/local/bin/coursier \
 && coursier launch --fork almond:${ALMOND_VERSION} --scala ${SCALA_VERSION} -- \
      --install --global --id scala213 --display-name "Scala 2.13 (Almond)" \
 && chmod -R a+rX /usr/local/share/jupyter/kernels/scala213 \
 && chmod -R a+rX /opt/coursier-cache

RUN useradd -m -u 1000 -s /bin/bash jovyan \
 && mkdir -p /home/jovyan/work /tmp/spark \
 && chown -R jovyan:jovyan /home/jovyan /tmp/spark

# install tworzy nowy plik z prawami 0644 (COPY przenosi też ACL z katalogu budowania, co blokuje odczyt przez użytkownika kontenera)
COPY spark-defaults.conf /tmp/spark-defaults.conf
RUN install -m 0644 /tmp/spark-defaults.conf /opt/spark/conf/spark-defaults.conf && rm /tmp/spark-defaults.conf

# Almond uruchamia Sparka w swojej JVM bez spark-submit, więc nie czyta spark-defaults.conf.
# Spark czyta jednak właściwości systemowe "spark.*", więc przepisujemy plik na argumenty -D kernela.
RUN python3 - <<'PY'
import json
kernel = "/usr/local/share/jupyter/kernels/scala213/kernel.json"
props = []
for line in open("/opt/spark/conf/spark-defaults.conf"):
    line = line.strip()
    if line and not line.startswith("#"):
        key, value = line.split(None, 1)
        if key != "spark.driver.memory":
            props.append(f"-D{key}={value.strip()}")
data = json.load(open(kernel))
data["argv"] = data["argv"][:1] + props + data["argv"][1:]
json.dump(data, open(kernel, "w"), indent=2)
PY

ENV SPARK_HOME=/opt/spark \
    PYSPARK_PYTHON=python3 \
    HOME=/home/jovyan \
    SHELL=/bin/bash

RUN apt-get update && apt-get install -y --no-install-recommends libnss-wrapper \
 && rm -rf /var/lib/apt/lists/*

USER jovyan
WORKDIR /home/jovyan/work
