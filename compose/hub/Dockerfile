FROM quay.io/jupyterhub/jupyterhub:5
RUN pip install --no-cache-dir dockerspawner jupyterhub-idle-culler jupyterhub-ldapauthenticator cassandra-driver
COPY hub/jupyterhub_config.py /etc/jupyterhub/jupyterhub_config.py
COPY provision/spark_provision.py /etc/jupyterhub/spark_provision.py
CMD ["jupyterhub", "-f", "/etc/jupyterhub/jupyterhub_config.py"]
