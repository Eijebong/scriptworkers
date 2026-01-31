FROM $DOCKER_IMAGE_PARENT

USER root
RUN apk add --no-cache git patch
USER worker

RUN mkdir -p /home/worker/repo-cache

# %include publishscript
COPY --chown=worker:worker /topsrcdir/publishscript /home/worker/publishscript
COPY --chown=worker:worker /topsrcdir/publishscript/run.sh /home/worker/publishscript.sh
RUN chmod +x /home/worker/publishscript.sh /home/worker/publishscript/run.sh

RUN cd /home/worker/publishscript && uv venv --python=3.13 && uv sync
