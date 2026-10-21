# 開発用のイメージ（docker-compose.yml から使う）。本番用の構成は T092（本番デプロイ）で決める
FROM python:3.13-slim

# 手元のフォルダを共有するので、キャッシュ（WSL・Linux では root の持ち物になる）を作らない
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RUFF_NO_CACHE=true

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
