FROM alpine:3.21
WORKDIR /app
RUN apk update && apk upgrade && apk add --no-cache nodejs npm
COPY package.json ./
RUN npm install --omit=dev && npm cache clean --force
COPY page-render.js .
EXPOSE 3030 3000
ENTRYPOINT ["node"]
CMD ["page-render.js"]
