FROM nginx:1.27-alpine

RUN apk add --no-cache openssl

COPY nginx/scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
