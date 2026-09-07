FROM node:22-alpine

RUN corepack enable

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

EXPOSE 5173

# --host so the dev server binds all interfaces, not just localhost inside
# the container — otherwise the host-mapped port can't reach it.
CMD ["pnpm", "dev", "--host", "0.0.0.0"]
