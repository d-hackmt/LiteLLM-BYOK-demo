import time
import streamlit as st
from modules.litellm_utils import (
    show_diagram, question_selector, require_keys, keys_ready,
    get_api_key_for_model, get_primary_model, available_models,
    get_groq_key, get_gemini_key, get_anthropic_key,
    LITELLM_QUESTIONS,
)
from modules.litellm_diagrams import UNIFIED_API_DIAGRAM

_PROVIDER_PICKS = {
    "Groq — Llama 3.3 70B":    "groq/llama-3.3-70b-versatile",
    "Groq — GPT-OSS 120B":     "groq/openai/gpt-oss-120b",
    "Groq — Llama 3.1 8B":     "groq/llama-3.1-8b-instant",
    "Gemini 2.5 Flash-Lite":   "gemini/gemini-2.5-flash-lite",
    "Gemini 2.0 Flash":        "gemini/gemini-2.5-flash",
    "Claude 3.5 Haiku":        "claude-3-5-haiku-20241022",
    "Claude 3.5 Sonnet":       "claude-3-5-sonnet-20241022",
}


def _provider_for(model: str) -> str:
    if model.startswith("groq/"):   return "Groq"
    if model.startswith("gemini/"): return "Gemini"
    if "claude" in model:           return "Anthropic"
    return "Unknown"


def render():
    st.title("Unified API")
    st.write(
        "LiteLLM's core value: **one `completion()` function for every provider**. "
        "You change the `model` string and nothing else. "
        "Run the same prompt through Groq, Gemini, and Anthropic side-by-side and compare responses, latency, and cost."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(UNIFIED_API_DIAGRAM, height=280)
        st.caption("One function call. LiteLLM translates it into the correct format for each provider automatically.")

    with st.expander("The code — this is all it takes"):
        st.code("""from litellm import completion

# Same call, same structure — just change the model string
response_groq = completion(
    model="groq/llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": "Explain RAG in one sentence."}]
)

response_gemini = completion(
    model="gemini/gemini-2.5-flash-lite",
    messages=[{"role": "user", "content": "Explain RAG in one sentence."}]
)

response_claude = completion(
    model="claude-3-5-haiku-20241022",
    messages=[{"role": "user", "content": "Explain RAG in one sentence."}]
)""", language="python")

    st.divider()
    require_keys()

    # ── Model picker ─────────────────────────────────────────────────────────
    st.subheader("Pick models to compare")
    st.write("Select up to 3 models. Only models whose provider key is configured will run.")

    avail = available_models()
    avail_labels = [lbl for lbl, m in _PROVIDER_PICKS.items() if m in avail]

    if len(avail_labels) < 1:
        st.warning("No models available — configure at least one API key in the sidebar.")
        return

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        sel_a = st.selectbox("Model 1", avail_labels, index=0, key="unif_m1")
    with col_b:
        sel_b = st.selectbox("Model 2", avail_labels,
                             index=min(1, len(avail_labels) - 1), key="unif_m2")
    with col_c:
        sel_c = st.selectbox("Model 3", avail_labels,
                             index=min(2, len(avail_labels) - 1), key="unif_m3")

    selected = [_PROVIDER_PICKS[sel_a], _PROVIDER_PICKS[sel_b], _PROVIDER_PICKS[sel_c]]
    # deduplicate while preserving order
    seen = set()
    unique = []
    for m in selected:
        if m not in seen:
            seen.add(m)
            unique.append(m)

    question = question_selector("unified", LITELLM_QUESTIONS)

    st.divider()

    if st.button("Run on all selected models", type="primary"):
        results = {}
        with st.status(f"Calling {len(unique)} model(s)...", expanded=True) as status:
            for model in unique:
                provider = _provider_for(model)
                st.write(f"Calling `{model}` ({provider})...")
                api_key = get_api_key_for_model(model)
                if not api_key:
                    st.write(f"  ⚠️  No API key for {provider} — skipping.")
                    continue
                try:
                    from litellm import completion, completion_cost
                    import litellm
                    litellm.suppress_debug_info = True
                    start = time.time()
                    resp = completion(
                        model=model,
                        messages=[{"role": "user", "content": question}],
                        max_tokens=250,
                        api_key=api_key,
                    )
                    elapsed_ms = int((time.time() - start) * 1000)
                    try:
                        cost = completion_cost(completion_response=resp)
                        cost_str = f"${cost:.6f}"
                    except Exception:
                        cost_str = "n/a"
                    results[model] = {
                        "text": resp.choices[0].message.content or "",
                        "latency": elapsed_ms,
                        "prompt_tokens": resp.usage.prompt_tokens,
                        "completion_tokens": resp.usage.completion_tokens,
                        "cost": cost_str,
                        "provider": provider,
                    }
                    st.write(f"  ✅ Done in {elapsed_ms} ms")
                except Exception as e:
                    st.write(f"  ❌ Error: {str(e)[:120]}")
            status.update(label="All calls complete", state="complete")
        st.session_state.unified_results = results

    if st.session_state.get("unified_results"):
        results = st.session_state.unified_results
        st.divider()
        st.subheader("Results")

        cols = st.columns(len(results))
        for col, (model, r) in zip(cols, results.items()):
            with col:
                st.markdown(f"**{model}**")
                st.caption(f"{r['provider']}")
                m1, m2, m3 = st.columns(3)
                m1.metric("Latency", f"{r['latency']}ms")
                m2.metric("Tokens", f"{r['prompt_tokens']}→{r['completion_tokens']}")
                m3.metric("Cost", r["cost"])
                st.write(r["text"])

        st.divider()
        st.subheader("What just happened")
        st.write(
            "Every call used the **same** `completion()` function and the **same** message structure. "
            "LiteLLM handled:\n"
            "- Translating the OpenAI-style messages to each provider's expected format\n"
            "- Routing to the correct API endpoint\n"
            "- Normalizing the response back to the OpenAI response shape\n\n"
            "Tomorrow you can swap any of these models for a different provider with **zero code changes**."
        )
