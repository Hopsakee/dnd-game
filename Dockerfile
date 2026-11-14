# solo-dm web app. One image for OrbStack on the Mac mini, NixOS later, or a
# server: Linux everywhere. Built and run with compose.yaml (see README, M6).

FROM ghcr.io/astral-sh/uv:0.13.8 AS uv

FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /app
COPY . .

# uv.lock is written in the development box and names its local wheel store as
# the source, which exists nowhere else. So install the exact versions it pins
# from PyPI instead: same versions as tested, other download location.
RUN uv export --frozen --no-dev --no-hashes --no-emit-project -o /tmp/requirements.txt \
 && uv venv /venv \
 && uv pip install --python /venv -r /tmp/requirements.txt \
 && uv pip install --python /venv --no-deps -e . \
 && rm /tmp/requirements.txt

# Runs as a user that cannot write its own code. It writes only to the two
# volumes compose.yaml mounts: campaigns/ and logs/.
RUN useradd --system --uid 10001 solodm \
 && mkdir -p /app/campaigns /app/logs \
 && chown solodm /app/campaigns /app/logs
USER solodm

ENV PATH="/venv/bin:$PATH" PYTHONUNBUFFERED=1
EXPOSE 5001
# 127.0.0.1: the app shares the Tailscale container's network (compose.yaml),
# whose serve config forwards the tailnet to it. Nothing else can reach it.
CMD ["solo-dm", "web", "--host", "127.0.0.1", "--port", "5001"]
