FROM python:3.12-slim
WORKDIR /app
COPY bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot/ /app/bot/
COPY dashboard/ /app/dashboard/
# HF Spaces requires port 7860
ENV PORT=7860
EXPOSE 7860
CMD ["python", "-m", "bot.main"]
