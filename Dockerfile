FROM python:3.10-slim

RUN apt-get update && apt-get install -y ffmpeg git curl build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
