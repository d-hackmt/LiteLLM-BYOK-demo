import streamlit as st

DEFAULT_MAX_TOKENS = 300

LITELLM_QUESTIONS = [
    "What is the difference between RAG and fine-tuning? When would you use each?",
    "Explain how the attention mechanism in transformers works — keep it simple.",
    "What is a vector database and why is it essential for RAG systems?",
    "How does temperature affect LLM outputs? Give a concrete example.",
    "What is hallucination in LLMs and what are 3 ways to reduce it?",
    "Explain prompt engineering — give me 3 key techniques with examples.",
    "What does 'context window' mean and why does its size matter?",
    "What is chain-of-thought prompting and when should you use it?",
    "How do you evaluate LLM output quality? Name 3 practical approaches.",
    "What is the difference between open-source and closed-source LLMs?",
    "Why do production AI apps need rate limiting and caching?",
    "What is token counting and how does it affect cost optimization?",
    "Explain the difference between zero-shot and few-shot prompting.",
    "What is RLHF and how does it shape modern LLM behavior?",
    "How do embedding models differ from generation models?",
    "What is quantization in LLMs — what does it trade off?",
    "Explain what a system prompt is and how it changes model behavior.",
    "Why would you use multiple LLM providers instead of just one?",
    "What is semantic caching and how does it save money on LLM APIs?",
    "What's the difference between streaming and non-streaming LLM responses?",
]

_PROVIDER_MODELS = {
    "groq": [
        "groq/llama-3.3-70b-versatile",
        "groq/llama-3.1-8b-instant",
        "groq/openai/gpt-oss-120b",
        "groq/openai/gpt-oss-20b",
    ],
    "gemini": [
        "gemini/gemini-2.5-flash-lite",
        "gemini/gemini-2.5-flash",
    ],
    "anthropic": [
        "claude-3-5-haiku-20241022",
        "claude-3-5-sonnet-20241022",
    ],
}

ALL_MODELS = [m for models in _PROVIDER_MODELS.values() for m in models]


def get_groq_key() -> str:
    return st.session_state.get("litellm_groq_key", "")


def get_groq2_key() -> str:
    k = st.session_state.get("litellm_groq2_key", "")
    return k if k else get_groq_key()


def get_gemini_key() -> str:
    return st.session_state.get("litellm_gemini_key", "")


def get_anthropic_key() -> str:
    return st.session_state.get("litellm_anthropic_key", "")


def get_primary_model() -> str:
    return st.session_state.get("litellm_primary_model", "groq/llama-3.3-70b-versatile")


def get_fallback_model() -> str:
    return st.session_state.get("litellm_fallback_model", "gemini/gemini-2.5-flash-lite")


def get_api_key_for_model(model: str) -> str:
    if model.startswith("groq/openai/"):
        return get_groq2_key()
    elif model.startswith("groq/"):
        return get_groq_key()
    elif model.startswith("gemini/"):
        return get_gemini_key()
    elif "claude" in model:
        return get_anthropic_key()
    return ""


def available_models() -> list:
    models = []
    if get_groq_key():
        models.extend(_PROVIDER_MODELS["groq"])
    if get_gemini_key():
        models.extend(_PROVIDER_MODELS["gemini"])
    if get_anthropic_key():
        models.extend(_PROVIDER_MODELS["anthropic"])
    return models or ["groq/llama-3.3-70b-versatile"]


def keys_ready() -> bool:
    return bool(get_groq_key() or get_gemini_key() or get_anthropic_key())


def require_keys():
    if not keys_ready():
        st.warning("Configure at least one API key in the sidebar to run this demo.")
        st.stop()


def litellm_call(model: str, messages: list, **kwargs):
    import litellm
    litellm.suppress_debug_info = True
    from litellm import completion
    api_key = get_api_key_for_model(model)
    kw = {"model": model, "messages": messages, "max_tokens": DEFAULT_MAX_TOKENS}
    if api_key:
        kw["api_key"] = api_key
    kw.update(kwargs)
    return completion(**kw)


def show_diagram(diagram_text: str, height: int = 450):
    safe = diagram_text.strip()
    html = f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:transparent;overflow:hidden;">
  <div style="position:relative;height:{height}px;">
    <div style="position:absolute;top:6px;right:6px;z-index:99;display:flex;gap:4px;">
      <button onclick="z(1.25)">+</button>
      <button onclick="z(0.8)">-</button>
      <button onclick="r()">Reset</button>
    </div>
    <div id="wrap" style="height:100%;overflow:auto;padding:8px;box-sizing:border-box;">
      <div id="content"><pre class="mermaid">{safe}</pre></div>
    </div>
  </div>
  <style>
    button {{
      background:#3a3a3a;color:#ddd;border:1px solid #555;
      border-radius:3px;padding:3px 10px;cursor:pointer;font-size:13px;
    }}
    button:hover {{ background:#555; }}
  </style>
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
    mermaid.initialize({{startOnLoad:true, theme:'dark'}});
    let s = 1;
    const c = document.getElementById('content');
    window.z = (f) => {{
      s = Math.max(0.3, Math.min(s * f, 5));
      c.style.transform = 'scale(' + s + ')';
      c.style.transformOrigin = 'top left';
    }};
    window.r = () => {{ s = 1; c.style.transform = ''; }};
  </script>
</body>
</html>"""
    st.iframe(html, height=height + 10)


def question_selector(key: str, questions: list, label: str = "Pick a question or write your own") -> str:
    st.caption(label)
    col1, col2 = st.columns([3, 2])
    with col1:
        custom = st.text_input("Write your own:", key=f"ll_cust_{key}",
                               placeholder="Type anything...")
    with col2:
        preset = st.selectbox("Or choose a preset:", questions, key=f"ll_pre_{key}")
    return custom.strip() if custom.strip() else preset
