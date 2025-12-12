FROM $DOCKER_IMAGE_PARENT

# %include githubscript
COPY --chown=worker:worker /topsrcdir/githubscript /home/worker/githubscript
COPY --chown=worker:worker /topsrcdir/githubscript/run.sh /home/worker/githubscript.sh
RUN chmod +x /home/worker/githubscript.sh /home/worker/githubscript/run.sh

RUN cd /home/worker/githubscript && ls -lah && uv venv --python=3.13 && uv sync
