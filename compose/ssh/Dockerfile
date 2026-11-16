# Bramka SSH: ta sama tożsamość (LDAP) i ten sam /home co w notebookach, w sieci klastra.
# Użytkownik loguje się przez SSH i uruchamia własne skrypty (Python, PySpark) z dostępem do Cassandry i Neo4j.
# Obraz spark-node musi być zbudowany wcześniej (stack.sh i demo.sh robią to jako pierwszy krok)
FROM spark/spark-node:latest
USER root
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      openssh-server libnss-ldapd libpam-ldapd nslcd libpam-modules less nano vim-tiny iputils-ping \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /run/sshd /etc/spark /usr/local/lib/spark
COPY provision/spark_provision.py /usr/local/lib/spark/spark_provision.py
COPY ssh/entrypoint.sh ssh/spark-authz ssh/spark-login /usr/local/bin/
COPY ssh/spark-env.sh /etc/profile.d/spark-env.sh
COPY ssh/pam-sshd /etc/pam.d/sshd
RUN chmod 0755 /usr/local/bin/entrypoint.sh /usr/local/bin/spark-authz /usr/local/bin/spark-login \
 && chmod 0644 /etc/profile.d/spark-env.sh /etc/pam.d/sshd \
 && sed -i 's/^passwd:.*/passwd:         files ldap/; s/^group:.*/group:          files ldap/; s/^shadow:.*/shadow:         files/' /etc/nsswitch.conf
EXPOSE 22
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
