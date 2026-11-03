# 03. App Flow

Diagrams are the intended design. Nothing is implemented yet.

## 1. Screens
Login or guest entry, then Chat (text, mic, attach), Source drawer, History, Memory manager, Settings (voice, theme), and for admins: Users, Eval dashboard, System metrics.

## 2. Login and roles
```mermaid
flowchart TD
  A[Open app] --> B{Has valid token?}
  B -- yes --> C[Chat]
  B -- no --> D[Login or continue as guest]
  D -- credentials --> E[POST /api/auth/login]
  E -- ok --> F[JWT access and refresh] --> C
  E -- fail --> D
  D -- guest --> G[Guest token, tight rate limit] --> C
  C --> H{Role}
  H -- admin --> I[Admin menu]
  H -- developer --> J[Image upload and API token]
  H -- viewer --> K[History and memory]
  H -- guest --> L[Ask only]
```

## 3. Text question (main path)
```mermaid
sequenceDiagram
  participant U as User
  participant API as FastAPI
  participant G as Guardrails
  participant C as Cache
  participant M as Memory
  participant S as SelfRAG
  participant R as Retriever
  participant L as RouterLLM
  U->>API: POST /api/ask
  API->>G: input checks
  G-->>API: ok or refuse
  API->>C: exact then semantic lookup
  alt hit
    C-->>API: cached answer and citations
  else miss
    API->>M: read relevant memories
    API->>S: question and memory
    S->>R: retrieve (BM25, ANN, RRF, rerank)
    R-->>S: chunks
    S->>L: grade relevance (fast model)
    S->>L: generate answer (answer model)
    S->>L: check support
    alt unsupported and attempts under 2
      S->>R: rewrite query, retry
    else unsupported
      S-->>API: refusal
    end
    S-->>API: answer, citations, confidence
    API->>C: store
  end
  API->>G: output checks
  API->>M: write memory candidates
  API-->>U: answer, sources, trace id
```

## 4. Voice question
```mermaid
flowchart LR
  A[Hold mic] --> B[Audio blob] --> C[POST /api/ask-voice]
  C --> D[Whisper STT via router] --> E{Transcript confident?}
  E -- no --> F[Show transcript, user confirms or retypes]
  E -- yes --> G[Text question flow]
  F --> G
  G --> H[Answer text] --> I{Speak reply on?}
  I -- yes --> J[Browser speech synthesis]
  I -- no --> K[Show only]
```

## 5. Image question
```mermaid
flowchart LR
  A[Attach screenshot] --> B[Client resize and strip EXIF] --> C[POST /api/ask-image]
  C --> D{Role developer or admin?}
  D -- no --> X[403 with reason]
  D -- yes --> E[Vision model: read error text, describe diagram]
  E --> F[Compose text query from description and user note]
  F --> G[Text question flow]
```

## 6. Provider fallback
```mermaid
flowchart TD
  A[Call tier model 1] -->|ok| Z[Return]
  A -->|429, 5xx, timeout| B[Open circuit, record]
  B --> C[Call model 2]
  C -->|ok| Z
  C -->|fail| D[Call model 3]
  D -->|ok| Z
  D -->|fail| E{OpenAI budget left?}
  E -- yes --> F[Call OpenAI last resort, record cost] --> Z
  E -- no --> G[Friendly message with retry time, show cached similar answers if any]
```

## 7. Memory read and write
```mermaid
flowchart TD
  A[Turn finished] --> B[Propose memory candidates]
  B --> C{Passes rules: no secrets, no PII, useful}
  C -- no --> D[Drop]
  C -- yes --> E{Kind}
  E -- preference or fact --> F[Long term, ask consent once]
  E -- named thing --> G[Entity]
  E -- Q and A with feedback --> H[Episodic]
  E -- style rule --> I[Procedural]
  F --> J[(memories table and vector)]
  G --> J
  H --> J
  I --> J
  K[Next question] --> L[Search memories by user, top k] --> M[Inject below system prompt, labelled untrusted]
```

## 8. Admin eval dashboard and schedule
```mermaid
flowchart TD
  CRON[GitHub Actions cron: nightly sample, weekly full] --> API[POST /api/admin/evals/run with service token]
  ADM[Admin clicks Run now] --> API
  API --> R[Eval runner]
  R --> S1[Retrieval eval]
  R --> S2[Generation eval]
  R --> S3[Pipeline eval]
  R --> S4[System metrics from traces]
  R --> S5[Safety eval]
  S1 --> DB[(eval_runs and eval_results)]
  S2 --> DB
  S3 --> DB
  S4 --> DB
  S5 --> DB
  DB --> D[Dashboard: trend, per type, regressions, cost]
  DB --> G{Drop beyond tolerance?}
  G -- yes --> N[Flag run failed, show diff vs last good run]
```

## 9. Error and edge states
- Provider quota exhausted: banner with retry time; cached answers still work.
- Space cold start: loading screen explaining the wake up.
- Off topic or unsupported: refusal with what was searched and a nearby doc link.
- Mic or camera denied: fall back to text and file picker with an explanation.
- Expired token: silent refresh, otherwise login with the draft question preserved.
