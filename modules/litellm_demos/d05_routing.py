import time
import streamlit as st
from modules.litellm_utils import (
    show_diagram, require_keys,
    get_groq_key, get_groq2_key, get_gemini_key, get_anthropic_key,
    get_api_key_for_model, available_models,
)
from modules.litellm_diagrams import ROUTING_DIAGRAM

_TASK_EXAMPLES = {
    "code":    "Write a Python function to check if a string is a palindrome.",
    "summary": "Summarize why the attention mechanism is critical for transformers in 2 sentences.",
    "general": "Tell me a fun fact about the deep ocean.",
}


def _build_routing_table() -> dict:
    """Build alias → model mapping from available keys."""
    table = {}
    groq_key   = get_groq_key()
    groq2_key  = get_groq2_key()
    gemini_key = get_gemini_key()

    if groq_key:
        table["fast-cheap"]   = ("groq/llama-3.1-8b-instant",       groq_key)
        table["balanced"]     = ("groq/llama-3.3-70b-versatile",     groq_key)
    if gemini_key and "balanced" not in table:
        table["balanced"]     = ("gemini/gemini-2.5-flash-lite",     gemini_key)
    if groq2_key:
        table["smart-coding"] = ("groq/openai/gpt-oss-120b",         groq2_key)
    elif gemini_key:
        table["smart-coding"] = ("gemini/gemini-2.5-flash",          gemini_key)
    elif groq_key:
        table["smart-coding"] = ("groq/llama-3.3-70b-versatile",     groq_key)

    return table


def render():
    st.title("Smart Routing")
    st.write(
        "Why use one model for everything? "
        "LiteLLM's **Router** lets you define human-readable aliases like `fast-cheap`, `smart-coding`, and `balanced`. "
        "Each alias maps to the right provider and model for that use case. "
        "Tomorrow you swap providers by editing one config — no code changes anywhere else."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(ROUTING_DIAGRAM, height=280)
        st.caption("Your app calls abstract names. The Router resolves them to real models and providers.")

    with st.expander("The code"):
        st.code("""from litellm import Router

model_list = [
    {
        "model_name": "fast-cheap",        # the alias your app uses
        "litellm_params": {
            "model": "groq/llama-3.1-8b-instant",   # actual model
            "api_key": groq_key
        }
    },
    {
        "model_name": "smart-coding",
        "litellm_params": {
            "model": "groq/openai/gpt-oss-120b",
            "api_key": groq2_key
        }
    },
    {
        "model_name": "balanced",
        "litellm_params": {
            "model": "gemini/gemini-2.5-flash-lite",
            "api_key": gemini_key
        }
    },
]

router = Router(model_list=model_list)

# Your app only ever sees the alias — never the real model name
response = router.completion(
    model="smart-coding",
    messages=[{"role": "user", "content": "Write a Python class for a binary tree."}]
)""", language="python")

    st.divider()
    require_keys()

    routing = _build_routing_table()
    if not routing:
        st.warning("Configure at least a Groq or Gemini key to run routing demos.")
        return

    st.subheader("Routing Table (based on your configured keys)")
    rows = [{"Alias": alias, "Actual Model": model, "Provider": "Groq" if model.startswith("groq/") else "Gemini" if model.startswith("gemini/") else "Anthropic"}
            for alias, (model, _) in routing.items()]
    import pandas as pd
    st.dataframe(pd.DataFrame(rows), width="stretch")

    st.divider()
    st.subheader("Try it — route by task type")

    tab1, tab2, tab3 = st.tabs(["code", "summary", "general"])

    for tab, task in zip([tab1, tab2, tab3], ["code", "summary", "general"]):
        with tab:
            alias = {"code": "smart-coding", "summary": "balanced", "general": "fast-cheap"}.get(task, "balanced")
            if alias not in routing:
                alias = list(routing.keys())[0]  # fallback to first available

            actual_model, api_key = routing[alias]
            st.info(f"Task **{task}** → alias `{alias}` → model `{actual_model}`")

            default_q = _TASK_EXAMPLES.get(task, "Hello!")
            custom_q  = st.text_input(f"Question ({task}):", value=default_q, key=f"ll_route_q_{task}")

            if st.button(f"Route to `{alias}`", key=f"ll_route_btn_{task}", type="primary"):
                with st.spinner(f"Routing to `{actual_model}`..."):
                    try:
                        from litellm import Router
                        import litellm
                        litellm.suppress_debug_info = True

                        model_list = [
                            {
                                "model_name": al,
                                "litellm_params": {"model": m, "api_key": k},
                            }
                            for al, (m, k) in routing.items()
                        ]
                        router = Router(model_list=model_list)
                        start = time.time()
                        resp = router.completion(
                            model=alias,
                            messages=[{"role": "user", "content": custom_q}],
                            max_tokens=300,
                        )
                        elapsed = int((time.time() - start) * 1000)
                        st.session_state[f"ll_route_res_{task}"] = {
                            "text":    resp.choices[0].message.content or "",
                            "latency": elapsed,
                            "model":   resp.model,
                            "alias":   alias,
                        }
                    except Exception as e:
                        st.error(f"Error: {e}")

            key = f"ll_route_res_{task}"
            if st.session_state.get(key):
                r = st.session_state[key]
                c1, c2 = st.columns([1, 3])
                c1.metric("Latency", f"{r['latency']}ms")
                c1.caption(f"Alias: `{r['alias']}`\nModel: `{r['model']}`")
                c2.write(r["text"])

    st.divider()
    st.subheader("The key insight")
    st.write(
        "Your codebase never contains `groq/openai/gpt-oss-120b` or `gemini/gemini-2.5-flash-lite`. "
        "It only contains `smart-coding`, `balanced`, `fast-cheap`. "
        "When you decide to swap Groq for Gemini or upgrade to a new model, "
        "you edit the Router config in one place — no grep, no refactor, no retesting across files."
    )
