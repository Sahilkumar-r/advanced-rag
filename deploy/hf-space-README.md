---
title: ragx docs assistant
emoji: 🔎
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Ask the FastAPI and Pydantic docs. Answers show their sources.
---

# ragx docs assistant

A retrieval augmented assistant for the FastAPI and Pydantic documentation. Every answer cites the pages it came from, and the assistant
refuses when the docs do not cover the question.

- Free tier model providers answer the questions, so replies can be slow and answers can be wrong. Check the source.
- Questions are sent to those providers, which may use them for training. Ask only about public docs and do not paste secrets or personal data.
- The disk of a free Space is ephemeral: demo users are re created on every start, and saved memories do not survive a restart.
- Code, evals and the measured results: see the project repository.
