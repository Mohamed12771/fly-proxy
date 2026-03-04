FROM alpine:latest

RUN apk add --no-cache curl unzip
RUN curl -L https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip -o xray.zip \
    && unzip xray.zip \
    && chmod +x xray

COPY config.json /config.json

CMD ["./xray", "-config", "/config.json"]