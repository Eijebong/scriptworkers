FROM $DOCKER_IMAGE_PARENT

RUN mkdir -p /home/worker/argocd-webhook
# %include argocd-webhook
COPY --chown=worker:worker /topsrcdir/argocd-webhook/run.sh /home/worker/argocd-webhook/run.sh

