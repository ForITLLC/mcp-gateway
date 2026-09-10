FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE NOTICE THIRD_PARTY_NOTICES.md ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --uid 10001 --create-home gateway
USER 10001
EXPOSE 8000
ENTRYPOINT ["forit-mcp-gateway"]
CMD ["--config", "/config/gateway.json", "--host", "0.0.0.0", "--port", "8000"]
