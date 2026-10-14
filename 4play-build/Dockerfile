FROM alpine:3.21
WORKDIR /app
RUN apk update && apk upgrade && apk add --no-cache nodejs npm
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY page-render.js .
RUN adduser -D -u 10001 app
USER app
EXPOSE 3030 3000
ENTRYPOINT ["node"]
CMD ["page-render.js"]
