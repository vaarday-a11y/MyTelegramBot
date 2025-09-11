# Используем Python 3.11
FROM python:3.11

# Устанавливаем ffmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Рабочая директория
WORKDIR /app

# Копируем все файлы в контейнер
COPY . .

# Устанавливаем библиотеки
RUN pip install --no-cache-dir -r requirements.txt

# Запуск бота
CMD ["python", "bot.py"]
