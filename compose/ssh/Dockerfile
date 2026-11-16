# Bramka SSH: ta sama tożsamość (LDAP) i ten sam /home co w notebookach, w sieci klastra.
# Użytkownik loguje się przez SSH i uruchamia własne skrypty (Python, PySpark) z dostępem do Cassandry i Neo4j.
# Obraz spark-node musi być zbudowany wcześniej (stack.sh i demo.sh robią to jako pierwszy krok)
FROM sparkpoc/spark-node:latest
USER root
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      openssh-server libnss-ldapd libpam-ldapd nslcd libpam-modules less nano vim-tiny iputils-ping \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /run/sshd /etc/sparkpoc /usr/local/lib/sparkpoc
COPY provision/sparkpoc_provision.py /usr/local/lib/sparkpoc/sparkpoc_provision.py
COPY ssh/entrypoint.sh ssh/sparkpoc-authz ssh/sparkpoc-login /usr/local/bin/
COPY ssh/sparkpoc-env.sh /etc/profile.d/sparkpoc-env.sh
COPY ssh/pam-sshd /etc/pam.d/sshd
RUN chmod 0755 /usr/local/bin/entrypoint.sh /usr/local/bin/sparkpoc-authz /usr/local/bin/sparkpoc-login \
 && chmod 0644 /etc/profile.d/sparkpoc-env.sh /etc/pam.d/sshd \
 && sed -i 's/^passwd:.*/passwd:         files ldap/; s/^group:.*/group:          files ldap/; s/^shadow:.*/shadow:         files/' /etc/nsswitch.conf
EXPOSE 22
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
