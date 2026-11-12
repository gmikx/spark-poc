FROM ubuntu:24.04
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-server openssh-client iproute2 iputils-ping procps ca-certificates \
 && rm -rf /var/lib/apt/lists/* && mkdir -p /run/sshd
COPY --from=ghcr.io/erebe/wstunnel:latest /home/app/wstunnel /usr/local/bin/wstunnel
COPY gw.sh node.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/gw.sh /usr/local/bin/node.sh
