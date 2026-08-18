FROM python:3.12-slim

LABEL maintainer="Dipro Paul <dipropaul032@gmail.com>"
LABEL org.opencontainers.image.title="media-data-extractor"
LABEL org.opencontainers.image.description="Network-first YouTube video scraper"
LABEL org.opencontainers.image.source="https://pypi.org/project/media-data-extractor/"
LABEL org.opencontainers.image.license="MIT"

# Install Chromium and dependencies (works on amd64 and arm64)
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Tell Selenium where Chromium is
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Install the package
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY examples/ ./examples/

RUN pip install --no-cache-dir .

# Output directory
RUN mkdir -p /output
VOLUME ["/output"]

# Default command — override with docker-compose or docker run
ENTRYPOINT ["media-data-extractor"]
CMD ["--help"]
