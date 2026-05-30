import time
from collections import Counter
import streamlit as st
from modules.litellm_utils import (
    show_diagram, require_keys,
    get_groq_key, get_groq2_key, get_gemini_key,
    get_api_key_for_model, available_models,
)
from modules.litellm_diagrams import LOAD_BALANCE_DIAGRAM


def _build_pool() -> list:
    """Build a pool of model configs from available keys."""
    pool = []
    groq_key = get_groq_key()
    groq2_key = get_groq2_key()
    gemini_key = get_gemini_key()

    if groq_key:
        pool.append({
            "model_name": "chat",
            "litellm_params": {"model": "groq/llama-3.3-70b-versatile", "api_key": groq_key},
            "model_info": {"id": "Groq-Llama-70B"},
        })
    if groq2_key and groq2_key != groq_key:
        pool.append({
            "model_name": "chat",
            "litellm_params": {"model": "groq/openai/gpt-oss-120b", "api_key": groq2_key},
            "model_info": {"id": "Groq-GPT-OSS-120B"},
        })
    elif groq2_key:  # same key as key1 — add a different model
        pool.append({
            "model_name": "chat",
            "litellm_params": {"model": "groq/llama-3.1-8b-instant", "api_key": groq2_key},
            "model_info": {"id": "Groq-Llama-8B"},
        })
    if gemini_key:
        pool.append({
            "model_name": "chat",
            "litellm_params": {"model": "gemini/gemini-2.5-flash-lite", "api_key": gemini_key},
            "model_info": {"id": "Gemini-Flash-Lite"},
        })
    return pool


def render():
    st.title("Load Balancing")
    st.write(
        "Hit rate limits on one key? Have multiple providers? "
        "LiteLLM's Router can pool multiple deployments under a single alias "
        "and distribute traffic across them using different strategies. "
        "Your app still calls `model='chat'` — the Router handles the rest."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(LOAD_BALANCE_DIAGRAM, height=260)
        st.caption("One alias, many deployments. The routing strategy decides which deployment handles each request.")

    with st.expander("The code"):
        st.code("""from litellm import Router

# Multiple deployments under the SAME model_name alias
model_list = [
    {
        "model_name": "chat",
        "litellm_params": {"model": "groq/llama-3.3-70b-versatile", "api_key": key1},
        "model_info": {"id": "groq-llama"}
    },
    {
        "model_name": "chat",
        "litellm_params": {"model": "groq/openai/gpt-oss-120b", "api_key": key2},
        "model_info": {"id": "groq-gpt-oss"}
    },
    {
        "model_name": "chat",
        "litellm_params": {"model": "gemini/gemini-2.5-flash-lite", "api_key": gemini_key},
        "model_info": {"id": "gemini-flash"}
    },
]

router = Router(
    model_list=model_list,
    routing_strategy="simple-shuffle"  # or "least-busy" or "latency-based-routing"
)

# Run 8 requests — the router distributes them across deployments
for i in range(8):
    r = router.completion(
        model="chat",
        messages=[{"role": "user", "content": f"Say hello #{i}"}],
        max_tokens=10
    )
    print(r._hidden_params.get("model_id"), r.choices[0].message.content)""", language="python")

    st.divider()
    require_keys()

    pool = _build_pool()
    if len(pool) < 2:
        st.warning(
            "Load balancing demos need at least 2 deployments. "
            "Configure a second API key (Groq Key 2 or Gemini) in the sidebar."
        )
        if len(pool) == 1:
            st.info(f"Currently only one deployment available: `{pool[0]['model_info']['id']}`")
        return

    st.subheader(f"Pool: {len(pool)} deployments")
    for entry in pool:
        m = entry["litellm_params"]["model"]
        mid = entry["model_info"]["id"]
        st.caption(f"• `{mid}` → `{m}`")

    st.divider()

    strategy_tab, tab2, tab3 = st.tabs([
        "simple-shuffle  (random)",
        "least-busy  (concurrency-aware)",
        "latency-based  (fastest first)",
    ])

    for tab, strategy in zip(
        [strategy_tab, tab2, tab3],
        ["simple-shuffle", "least-busy", "latency-based-routing"],
    ):
        with tab:
            _strategy_demo(pool, strategy)


def _strategy_demo(pool, strategy):
    n = st.slider("Number of requests to send", 4, 12, 6, key=f"ll_lb_n_{strategy}")

    desc = {
        "simple-shuffle":        "Random distribution — spreads load evenly over time without tracking state.",
        "least-busy":            "Tracks in-flight requests per deployment. New requests go to the least-loaded one.",
        "latency-based-routing": "Measures response time per deployment. New requests go to whichever has been fastest recently.",
    }
    st.info(desc[strategy])

    if st.button(f"Run {n} requests with `{strategy}`", key=f"ll_lb_btn_{strategy}", type="primary"):
        from litellm import Router
        import litellm
        litellm.suppress_debug_info = True

        router = Router(model_list=pool, routing_strategy=strategy)
        results = []

        with st.status(f"Running {n} requests...", expanded=True) as status:
            for i in range(n):
                try:
                    start = time.time()
                    r = router.completion(
                        model="chat",
                        messages=[{"role": "user", "content": f"Say exactly: OK #{i+1}"}],
                        max_tokens=10,
                    )
                    elapsed = int((time.time() - start) * 1000)
                    dep = r._hidden_params.get("model_id", "unknown")
                    results.append({"req": i + 1, "deployment": dep, "latency": elapsed,
                                    "text": r.choices[0].message.content or ""})
                    st.write(f"#{i+1} → `{dep}` — {elapsed}ms")
                except Exception as e:
                    results.append({"req": i + 1, "deployment": "ERROR", "latency": 0,
                                    "text": str(e)[:80]})
                    st.write(f"#{i+1} → ERROR: {str(e)[:80]}")
            status.update(label="Done", state="complete")

        st.session_state[f"ll_lb_res_{strategy}"] = results

    key = f"ll_lb_res_{strategy}"
    if st.session_state.get(key):
        results = st.session_state[key]
        st.divider()

        distribution = Counter(r["deployment"] for r in results)
        c1, c2 = st.columns([1, 2])
        with c1:
            st.subheader("Distribution")
            for dep, count in distribution.most_common():
                bar = "█" * count
                st.write(f"`{dep}`: {bar} ({count})")
        with c2:
            st.subheader("Per-request latency")
            import pandas as pd
            df = pd.DataFrame([
                {"Request": f"#{r['req']}", "Deployment": r["deployment"], "Latency (ms)": r["latency"]}
                for r in results if r["deployment"] != "ERROR"
            ])
            if not df.empty:
                st.bar_chart(df.set_index("Request")["Latency (ms)"])
