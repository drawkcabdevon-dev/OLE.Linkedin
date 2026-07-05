FROM python:3.13-slim

LABEL description="Online Everywhere LinkedIn Agent"
LABEL maintainer="Online Everywhere"

WORKDIR /app

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

ENV GOOGLE_CLOUD_PROJECT=linkedin-agent-501504

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp_servers/ mcp_servers/
COPY templates/ templates/
COPY telegram_bot.py .
COPY gemini_client.py .
COPY schedule_config.json .
COPY authorized_chats.json .
COPY entrypoint.sh .

RUN mkdir -p assets data

EXPOSE 8080

CMD ["python3", "-u", "telegram_bot.py"]