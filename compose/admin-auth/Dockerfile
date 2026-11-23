# Ten sam obraz bazowy co hub: ma bibliotekę ldap3 i konfigurację TLS zgodną z serwerem LDAP wydziału
FROM quay.io/jupyterhub/jupyterhub:5
RUN pip install --no-cache-dir ldap3
COPY app.py /app/app.py
RUN chmod 0644 /app/app.py
USER nobody
CMD ["python3", "/app/app.py"]
