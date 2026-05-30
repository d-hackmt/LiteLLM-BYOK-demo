UNIFIED_API_DIAGRAM = """
graph LR
    A[Your Application] -->|completion model messages| B[LiteLLM]
    B -->|groq/llama-3.3-70b| C[Groq]
    B -->|gemini/gemini-2.5-flash| D[Gemini]
    B -->|claude-3-5-haiku| E[Anthropic]
    C -->|Response| B
    D -->|Response| B
    E -->|Response| B
    B -->|Unified Response| A
"""

FALLBACK_DIAGRAM = """
graph LR
    A[Your Application] -->|completion with fallbacks list| B[LiteLLM]
    B -->|Try Primary| C[Primary Model]
    C -->|Fails rate limit or error| B
    B -->|Auto Fallback 1| D[Fallback Model 1]
    D -->|Fails| B
    B -->|Auto Fallback 2| E[Fallback Model 2]
    E -->|Success| B
    B -->|Response| A
"""

COST_DIAGRAM = """
graph LR
    A[Your Application] -->|completion call| B[LiteLLM]
    B -->|API Request| C[LLM Provider]
    C -->|Response with usage| B
    B -->|completion_cost response| D[Cost Engine]
    D -->|USD cost per call| E[Cost Tracker]
    B -->|Response| A
"""

CACHE_DIAGRAM = """
graph LR
    A[Your Application] -->|completion caching=True| B[LiteLLM Cache]
    B -->|Check hash model + messages| C{Cache Hit?}
    C -->|YES instant| D[Return Cached Response]
    C -->|NO call LLM| E[LLM Provider]
    E -->|Store in Cache| F[In-Memory Cache]
    F -->|Return Response| A
    D -->|Return Response| A
"""

ROUTING_DIAGRAM = """
graph LR
    A[Your Application] -->|model=fast-cheap| B[LiteLLM Router]
    B -->|resolves alias| C[groq/llama-3.3-70b-versatile]
    A -->|model=smart-coding| B
    B -->|resolves alias| D[groq/openai/gpt-oss-120b]
    A -->|model=balanced| B
    B -->|resolves alias| E[gemini/gemini-2.5-flash-lite]
    C & D & E --> F[Provider API]
    F -->|Response| A
"""

LOAD_BALANCE_DIAGRAM = """
graph LR
    A[Your Application] -->|N requests model=chat| B[LiteLLM Router]
    B -->|simple-shuffle or least-busy or latency-based| C{Strategy}
    C -->|Request| D[Groq Llama 70B]
    C -->|Request| E[Groq GPT-OSS-120B]
    C -->|Request| F[Gemini Flash-Lite]
    D & E & F -->|Responses| A
"""

OBSERVABILITY_DIAGRAM = """
graph LR
    A[Your Application] -->|completion with metadata| B[LiteLLM]
    B -->|API Call| C[LLM Provider]
    C -->|Response| B
    B -->|success_callback| D[Your Logger]
    D -->|model prompt tokens latency cost| E[Audit Log]
    B -->|failure_callback| F[Error Handler]
    B -->|Response| A
"""

LANGCHAIN_DIAGRAM = """
graph LR
    A[LangChain Chain] -->|prompt| B[ChatLiteLLM]
    B -->|completion call| C[LiteLLM]
    C -->|Primary| D[LLM Provider 1]
    D -->|Fails| C
    C -->|with_fallbacks| E[LLM Provider 2]
    E -->|Response| C
    C -->|Response| B
    B -->|Response| A
"""

GUARDRAILS_DIAGRAM = """
graph LR
    A[User Input] -->|raw message| B[Input Guardrail]
    B -->|PII redaction injection check topic filter| C{Safe?}
    C -->|BLOCKED| D[GuardrailViolation raised]
    C -->|REDACTED or ALLOWED| E[LiteLLM]
    E -->|API Call| F[LLM Provider]
    F -->|Response| G[Output Guardrail]
    G -->|Check response| A
"""

SMART_CHATBOT_DIAGRAM = """
graph LR
    A[User Message] -->|text| B[Task Classifier]
    B -->|code or summary or general| C[LiteLLM Router]
    C -->|code route| D[Smart Model]
    C -->|summary route| E[Fast Model]
    C -->|general route| F[Balanced Model]
    D & E & F -->|Fallback chain| G[Backup Models]
    D & E & F & G -->|Response| H[User]
    C -.->|log cost and latency| I[Audit Trail]
"""
