FROM quay.io/jupyterhub/jupyterhub:5
RUN pip install --no-cache-dir dockerspawner jupyterhub-idle-culler jupyterhub-ldapauthenticator cassandra-driver
COPY hub/jupyterhub_config.py /etc/jupyterhub/jupyterhub_config.py
COPY provision/sparkpoc_provision.py /etc/jupyterhub/sparkpoc_provision.py
CMD ["jupyterhub", "-f", "/etc/jupyterhub/jupyterhub_config.py"]
