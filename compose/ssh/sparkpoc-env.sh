# Środowisko sesji SSH: Spark, Cassandra i Neo4j tak jak w notebookach.
export SPARK_HOME=/opt/spark
export PYSPARK_PYTHON=python3
export JAVA_HOME=/opt/java/openjdk
export PATH="$PATH:/opt/java/openjdk/bin:/opt/spark/bin"
export SPARK_LOCAL_HOSTNAME="$(hostname -i | awk '{print $1}')"
export SPARK_LOCAL_DIRS=/tmp
export CASSANDRA_HOST=cassandra
export NEO4J_URI=bolt://neo4j:7687
