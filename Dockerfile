# Skeleton for Hugging Face Spaces (Docker SDK listens on 7860). Finalised in phase 8.
FROM python:3.12-slim
WORKDIR /app
COPY . .
EXPOSE 7860
CMD ["echo", "Not built yet. See docs/06-IMPLEMENTATION-PLAN.md"]
