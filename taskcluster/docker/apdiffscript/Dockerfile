FROM $DOCKER_IMAGE_PARENT

# %include apdiffscript
COPY --chown=worker:worker /topsrcdir/apdiffscript /home/worker/apdiffscript
COPY --chown=worker:worker /topsrcdir/apdiffscript/run.sh /home/worker/apdiffscript.sh

RUN cd /home/worker/apdiffscript && ls -lah && uv venv --python=3.13 && uv sync
