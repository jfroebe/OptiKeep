FROM python:3.12.15-slim-bookworm
LABEL org.opencontainers.image.title="OptiKeep" \
      org.opencontainers.image.licenses="GPL-3.0-only" \
      org.opencontainers.image.source="https://github.com/jfroebe/OptiKeep"
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
ARG CZKAWKA_VERSION=12.0.2
RUN curl --fail --location --retry 3 "https://github.com/qarmin/czkawka/releases/download/${CZKAWKA_VERSION}/linux_czkawka_cli_musl" -o /usr/local/bin/czkawka_cli \
    && echo 'e90381d8c38479a97f9e98335523208ac285b6e4bcac10f41db791d04a51b14a  /usr/local/bin/czkawka_cli' | sha256sum -c - \
    && chmod 755 /usr/local/bin/czkawka_cli
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY optikeep ./optikeep
RUN pip install --no-cache-dir '.[test]' \
    && useradd --uid 1000 --create-home optikeep \
    && mkdir -p /config /cache /logs \
    && chown 1000:1000 /config /cache /logs
COPY tests ./tests
USER 1000:1000
EXPOSE 18766
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:18766/health')"
ENTRYPOINT ["optikeep"]
CMD ["serve"]
