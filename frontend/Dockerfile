# 開発用のイメージ（docker-compose.yml から使う）。本番の配信の構成は T092（本番デプロイ）で決める
FROM node:24-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-fund --no-audit

COPY . .

CMD ["npm", "run", "dev"]
