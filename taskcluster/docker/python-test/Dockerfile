FROM debian:bookworm-slim

VOLUME /builds/worker/checkouts
VOLUME /builds/worker/.task-cache/uv

RUN mkdir -p /builds && \
    useradd -d /builds/worker -s /bin/bash -m worker && \
    mkdir /builds/worker/artifacts && \
    chown -R worker:worker /builds/worker

# %include-run-task

RUN apt-get update \
 && apt-get install -y --reinstall ca-certificates \
 && apt-get install -y --force-yes --no-install-recommends \
    build-essential \
    mercurial \
    git


ENV SHELL=/bin/bash \
    HOME=/builds/worker \
    PATH=/builds/worker/.local/bin:$PATH

COPY --from=ghcr.io/astral-sh/uv:0.7.12 /uv /bin/uv
RUN uv python install 3.13

CMD ["/bin/bash", "--login"]
