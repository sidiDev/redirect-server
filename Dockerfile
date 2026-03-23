FROM python:3.12-slim

WORKDIR /app

COPY custom-redirect-script.py .

ENV PORT=8000
EXPOSE 8000

CMD ["python", "custom-redirect-script.py"]
