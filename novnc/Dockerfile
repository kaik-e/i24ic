FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:1

# Install dependencies
RUN apt-get update && apt-get install -y \
    firefox \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    python3 \
    python3-pip \
    supervisor \
    curl \
    jq \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies for cookie extraction
RUN pip3 install lz4 requests

# Create app directory
WORKDIR /app

# Copy scripts
COPY scripts/ /app/scripts/
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create directories
RUN mkdir -p /app/loot /root/.mozilla/firefox

# Expose VNC and noVNC ports
EXPOSE 5900 6080

# Start supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
