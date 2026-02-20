FROM python:3.12-slim
WORKDIR /app
COPY bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot/ /app/bot/
EXPOSE 8080
CMD ["python", "-m", "bot.main"]
