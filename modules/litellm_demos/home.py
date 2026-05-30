import streamlit as st


def render():
    st.title("LiteLLM Gateway Explorer")
    st.subheader("Hands-on experiments with LiteLLM — run real multi-provider LLM calls, see everything live.")

    st.info(
        "This app teaches you how LiteLLM works as an LLM gateway by letting you run each concept yourself. "
        "Every button fires real API calls. Every result shows exactly which model answered, what it cost, and how fast it was."
    )

    st.divider()

    st.header("What is LiteLLM?")
    st.write(
        "LiteLLM is an open-source Python library that gives you **one unified API** for 100+ LLM providers. "
        "You call `completion()` once and switch between OpenAI, Anthropic, Groq, Gemini, and dozens more "
        "by changing a single string. It also handles fallbacks, caching, cost tracking, routing, and observability — "
        "all without a managed service or SaaS dependency."
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Providers Supported", "100+", delta="one unified API")
    with col2:
        st.metric("Extra Infrastructure", "Zero", delta="pure Python library")
    with col3:
        st.metric("License", "MIT", delta="fully open-source")

    st.divider()

    st.header("Setup — 3 steps to get started")

    with st.expander("Step 1 — Install LiteLLM", expanded=True):
        st.code("pip install litellm", language="bash")
        st.write("That's it. No daemon, no proxy, no Docker required for the basic usage shown in this app.")

    with st.expander("Step 2 — Get your API keys"):
        st.write(
            "- **Groq** (free): [console.groq.com](https://console.groq.com) — ultra-fast inference for Llama and OpenAI-compat models\n"
            "- **Gemini** (free tier): [aistudio.google.com](https://aistudio.google.com) — Google's latest flash models\n"
            "- **Anthropic** (optional): [console.anthropic.com](https://console.anthropic.com) — Claude models\n\n"
            "You only need one provider to start. Having two or more unlocks the multi-provider demos."
        )

    with st.expander("Step 3 — Enter your keys in the sidebar"):
        st.write(
            "Open the **API Keys** section in the sidebar. "
            "Enter at least one key. The green checkmark appears and all demos are ready. "
            "More keys = more demos you can run."
        )

    st.divider()

    st.header("Experiments in this app")

    experiments = [
        ("Unified API",           "The killer feature: one `completion()` call works with Groq, Gemini, and Anthropic. Change the model string, everything else stays the same."),
        ("Automatic Fallbacks",   "If your primary model fails or gets rate-limited, LiteLLM silently falls back to the next model in your list. Your app never sees the error."),
        ("Cost Tracking",         "LiteLLM calculates the exact USD cost of every call using its built-in pricing database. See tokens in, tokens out, and dollars spent per request."),
        ("Response Caching",      "Enable in-memory caching with one line. First call hits the API; second identical call returns instantly at zero cost."),
        ("Smart Routing",         "Define named aliases like `fast-cheap` or `smart-coding` with the Router. Each alias maps to the right provider for that task type."),
        ("Load Balancing",        "Pool multiple deployments under one alias. The Router distributes traffic with strategies: simple-shuffle, least-busy, or latency-based."),
        ("Observability",         "Register a `success_callback` and LiteLLM calls it after every request — with model, tokens, latency, cost, and your custom metadata."),
        ("LangChain Integration", "Drop `ChatLiteLLM` into any LangChain chain as a replacement for `ChatOpenAI`. All gateway features work transparently inside your agents."),
        ("Guardrails",            "Add input guardrails via callbacks: PII redaction, prompt injection detection, forbidden topic blocking — pure Python, no extra service."),
        ("Smart Chatbot",         "An end-to-end chatbot that classifies user intent, routes to the best model, falls back on failure, and logs cost and latency per message."),
    ]

    for i, (name, desc) in enumerate(experiments, 1):
        with st.expander(f"{i}. {name}"):
            st.write(desc)

    st.divider()
    st.caption("Providers used: Groq (Llama + OpenAI-compat), Gemini (Flash), Anthropic (Claude). Configure any combination in the sidebar.")
    st.caption("LiteLLM is MIT-licensed and free. Costs come from your provider API usage only.")
