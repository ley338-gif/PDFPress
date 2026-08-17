FROM node:22-alpine AS build
WORKDIR /app
# pdfjs-dist listet "canvas" als optionale Abhaengigkeit fuer server-seitiges
# Rendering (im Browser-Build hier ungenutzt). node-canvas versucht zuerst ein
# vorkompiliertes Binary von GitHub zu laden (prebuild-install) und faellt bei
# Netzwerkproblemen auf einen lokalen node-gyp-Build zurueck -- ohne diese
# Alpine-Build-Tools/Libs schlaegt dieser Fallback fehl und kann einen
# bekannten npm-CLI-Bug ("Exit handler never called!") ausloesen, der den
# gesamten Install-Schritt abbrechen laesst statt den optionalen Build zu
# ueberspringen. Mit den Tools installiert sich canvas sauber durch.
RUN apk add --no-cache python3 make g++ cairo-dev pango-dev jpeg-dev giflib-dev librsvg-dev pixman-dev
COPY package.json package-lock.json ./
RUN npm install
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
