FROM quay.io/jupyterhub/jupyterhub:5
RUN pip install --no-cache-dir dockerspawner jupyterhub-idle-culler jupyterhub-ldapauthenticator cassandra-driver
COPY jupyterhub_config.py /etc/jupyterhub/jupyterhub_config.py
CMD ["jupyterhub", "-f", "/etc/jupyterhub/jupyterhub_config.py"]
