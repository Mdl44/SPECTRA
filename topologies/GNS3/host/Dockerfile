FROM alpine:latest

RUN apk update && apk add --no-cache \
    dhcpcd \
    openssh \
    net-snmp \
    net-snmp-tools \
    bash \
    iputils \
    bind-tools

RUN ssh-keygen -A && \
    echo "root:cisco123" | chpasswd && \
    sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config

COPY snmpd.conf /etc/snmp/snmpd.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
