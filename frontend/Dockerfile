FROM node:20-alpine

WORKDIR /app

COPY package.json .
RUN npm install --omit=dev --no-audit --no-fund

COPY server.js ./
COPY views ./views
COPY public ./public

RUN chown -R node:node /app
USER node

EXPOSE 3000

CMD ["npm", "start"]
