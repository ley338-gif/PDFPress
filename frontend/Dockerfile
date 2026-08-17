FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
# npm im Alpine-Image aktualisieren: aeltere npm-Versionen haben einen bekannten
# CLI-Bug ("Exit handler never called!"), der bei parallel laufenden nativen
# Kindprozessen (hier: der gescheiterte optionale node-gyp-Build von "canvas",
# einer optionalen pdfjs-dist-Abhaengigkeit fuer server-seitiges Rendering, das
# wir im Browser-Build nicht brauchen) ausgeloest werden kann und npm selbst
# abstuerzen laesst statt den fehlgeschlagenen optionalen Build einfach zu ueberspringen.
RUN npm install -g npm@latest && npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html
RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/run
USER nginx
ENTRYPOINT []
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
