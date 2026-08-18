FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    postgresql \
    postgresql-contrib \
    openssh-server \
    openssh-client \
    rsyslog \
    dnsmasq \
    isc-dhcp-server \
    tftpd-hpa \
    chrony \
    net-tools \
    iproute2 \
    iputils-ping \
    traceroute \
    tcpdump \
    curl \
    wget \
    nano \
    sudo \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libcairo2 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /run/sshd

RUN useradd -m -s /bin/bash spectra && \
    echo "spectra:spectra" | chpasswd && \
    usermod -aG sudo spectra

RUN sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config

RUN echo "domain=corp.net" > /etc/dnsmasq.d/spectra.conf && \
    echo "local=/corp.net/" >> /etc/dnsmasq.d/spectra.conf && \
    echo "no-resolv" >> /etc/dnsmasq.d/spectra.conf && \
    echo "server=8.8.8.8" >> /etc/dnsmasq.d/spectra.conf

RUN sed -i 's/#module(load="imudp")/module(load="imudp")/' /etc/rsyslog.conf && \
    sed -i 's/#input(type="imudp" port="514")/input(type="imudp" port="514")/' /etc/rsyslog.conf

RUN echo "local stratum 10" >> /etc/chrony/chrony.conf && \
    echo "allow 10.0.0.0/8" >> /etc/chrony/chrony.conf && \
    echo "allow fd44:f1:f1::/48" >> /etc/chrony/chrony.conf

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY dhcpd.conf /etc/dhcp/dhcpd.conf
RUN sed -i 's/INTERFACESv4=""/INTERFACESv4="eth0"/' /etc/default/isc-dhcp-server

COPY dhcpd6.conf /etc/dhcp/dhcpd6.conf

RUN mkdir -p /srv/tftp/configs && \
    sed -i 's|TFTP_DIRECTORY="/srv/tftp"|TFTP_DIRECTORY="/srv/tftp"|' /etc/default/tftpd-hpa && \
    sed -i 's/TFTP_ADDRESS=".*"/TFTP_ADDRESS="0.0.0.0:69"/' /etc/default/tftpd-hpa

COPY ztp-hosts.conf /etc/dhcp/ztp-hosts.conf
COPY templates/ /app/templates/
COPY generate_config.py /app/generate_config.py

COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
