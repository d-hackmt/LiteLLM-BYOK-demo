import streamlit as st

st.set_page_config(
    page_title="LiteLLM Gateway Explorer",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state defaults ────────────────────────────────────────────────────
_DEFAULTS = {
    "litellm_groq_key": "",
    "litellm_groq2_key": "",
    "litellm_gemini_key": "",
    "litellm_anthropic_key": "",
    "litellm_primary_model": "groq/llama-3.3-70b-versatile",
    "litellm_fallback_model": "gemini/gemini-2.5-flash-lite",
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

_ALL_MODELS = [
    "groq/llama-3.3-70b-versatile",
    "groq/llama-3.1-8b-instant",
    "groq/openai/gpt-oss-120b",
    "groq/openai/gpt-oss-20b",
    "gemini/gemini-2.5-flash-lite",
    "gemini/gemini-2.5-flash",
    "claude-3-5-haiku-20241022",
    "claude-3-5-sonnet-20241022",
]


def _model_idx(name: str) -> int:
    try:
        return _ALL_MODELS.index(name)
    except ValueError:
        return 0


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("LiteLLM Gateway Explorer")
    st.caption("Hands-on experiments with LiteLLM")
    st.divider()

    _any_key = bool(
        st.session_state.litellm_groq_key
        or st.session_state.litellm_gemini_key
        or st.session_state.litellm_anthropic_key
    )
    with st.expander("API Keys", expanded=not _any_key):
        st.session_state.litellm_groq_key = st.text_input(
            "Groq API Key",
            value=st.session_state.litellm_groq_key,
            type="password",
            placeholder="gsk_...",
            key="_ll_groq",
            help="console.groq.com — for llama-3.3-70b, llama-3.1-8b, gpt-oss models",
        )
        st.session_state.litellm_groq2_key = st.text_input(
            "Groq API Key 2  (load-balance demos)",
            value=st.session_state.litellm_groq2_key,
            type="password",
            placeholder="gsk_... (leave blank to reuse the key above)",
            key="_ll_groq2",
            help="A second Groq key to show load-balancing across two key pools. Optional.",
        )
        if not st.session_state.litellm_groq2_key:
            st.caption("Key 2 not set — primary Groq key used for all Groq calls.")
        st.session_state.litellm_gemini_key = st.text_input(
            "Gemini API Key",
            value=st.session_state.litellm_gemini_key,
            type="password",
            placeholder="AIza...",
            key="_ll_gemini",
            help="aistudio.google.com — for gemini-2.5-flash-lite, gemini-2.5-flash",
        )
        st.session_state.litellm_anthropic_key = st.text_input(
            "Anthropic API Key  (optional)",
            value=st.session_state.litellm_anthropic_key,
            type="password",
            placeholder="sk-ant-...",
            key="_ll_anthropic",
            help="console.anthropic.com — for claude-3-5-haiku and claude-3-5-sonnet",
        )

    with st.expander("Model Selection", expanded=False):
        st.caption("Primary and fallback models used across all demos.")

        def _lbl(m: str) -> str:
            if m.startswith("groq/"):   return f"{m}  [Groq]"
            if m.startswith("gemini/"): return f"{m}  [Gemini]"
            if "claude" in m:           return f"{m}  [Anthropic]"
            return m

        st.session_state.litellm_primary_model = st.selectbox(
            "Primary Model",
            options=_ALL_MODELS,
            index=_model_idx(st.session_state.litellm_primary_model),
            format_func=_lbl,
            key="_ll_pm",
        )
        st.session_state.litellm_fallback_model = st.selectbox(
            "Fallback Model",
            options=_ALL_MODELS,
            index=_model_idx(st.session_state.litellm_fallback_model),
            format_func=_lbl,
            key="_ll_fm",
        )
        if st.session_state.litellm_primary_model == st.session_state.litellm_fallback_model:
            st.caption("Primary and fallback are the same model — fallback still activates on errors.")

    # ── Status ────────────────────────────────────────────────────────────────
    st.divider()
    _has_key = bool(
        st.session_state.litellm_groq_key
        or st.session_state.litellm_gemini_key
        or st.session_state.litellm_anthropic_key
    )
    if _has_key:
        st.success("Ready to run demos", icon="✅")
    else:
        st.warning("Configure at least one API key above to start", icon="⚠️")

    # ── Navigation ────────────────────────────────────────────────────────────
    st.divider()
    _PAGES = [
        ("Home",                  "home"),
        ("Unified API",           "unified_api"),
        ("Automatic Fallbacks",   "fallbacks"),
        ("Cost Tracking",         "cost_tracking"),
        ("Response Caching",      "caching"),
        ("Smart Routing",         "routing"),
        ("Load Balancing",        "load_balancing"),
        ("LangChain Integration", "langchain"),
        ("Guardrails",            "guardrails"),
        ("Smart Chatbot",         "smart_chatbot"),
    ]
    _LABELS = [p[0] for p in _PAGES]
    _KEYS   = [p[1] for p in _PAGES]

    selected_idx = st.radio(
        "Experiments",
        range(len(_LABELS)),
        format_func=lambda i: _LABELS[i],
        label_visibility="visible",
    )
    current_page = _KEYS[selected_idx]


# ── Route to demo ─────────────────────────────────────────────────────────────
from modules.litellm_demos import (
    home,
    d01_unified_api,
    d02_fallbacks,
    d03_cost_tracking,
    d04_caching,
    d05_routing,
    d06_load_balancing,
    d08_langchain,
    d09_guardrails,
    d10_smart_chatbot,
)

_PAGE_MAP = {
    "home":           home.render,
    "unified_api":    d01_unified_api.render,
    "fallbacks":      d02_fallbacks.render,
    "cost_tracking":  d03_cost_tracking.render,
    "caching":        d04_caching.render,
    "routing":        d05_routing.render,
    "load_balancing": d06_load_balancing.render,
    "langchain":      d08_langchain.render,
    "guardrails":     d09_guardrails.render,
    "smart_chatbot":  d10_smart_chatbot.render,
}

_PAGE_MAP[current_page]()
