# Python image
FROM python:3.10-slim

# Ishchi katalog
WORKDIR /app

# Kerakli fayllarni ko‘chirish
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Bot fayllarini ko‘chirish
COPY . .

# Botni ishga tushirish
CMD ["python", "bot.py"]
