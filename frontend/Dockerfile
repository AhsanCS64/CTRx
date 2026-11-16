# Dockerfile for the frontend (React + Vite)
FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* vite.config.ts tsconfig.json .
RUN npm install

COPY src ./src
COPY index.html ./

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
