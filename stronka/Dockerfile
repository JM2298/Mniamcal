FROM node:25-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --legacy-peer-deps

COPY . .

EXPOSE 5001

CMD ["npm", "run", "dev"]