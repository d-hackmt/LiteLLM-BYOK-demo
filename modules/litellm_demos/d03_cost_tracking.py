import time
import streamlit as st
from modules.litellm_utils import (
    show_diagram, question_selector, require_keys,
    get_gemini_key, get_groq_key, get_api_key_for_model,
    LITELLM_QUESTIONS,
)
from modules.litellm_diagrams import COST_DIAGRAM

# Models with confirmed LiteLLM pricing DB support
_PRICED_MODELS = [
    ("gemini/gemini-2.5-flash-lite", "Gemini 2.5 Flash-Lite  [~$0.10/M in]"),
    ("gemini/gemini-2.5-flash",      "Gemini 2.5 Flash       [~$0.30/M in]"),
]
# Groq shown for contrast — no public per-token pricing
_UNPRICED_MODELS = [
    ("groq/llama-3.3-70b-versatile", "Groq Llama 3.3 70B    [no public pricing]"),
    ("groq/llama-3.1-8b-instant",    "Groq Llama 3.1 8B     [no public pricing]"),
]


def _get_cost(resp) -> tuple[str, float]:
    try:
        from litellm import completion_cost
        val = completion_cost(completion_response=resp)
        if val and val > 0:
            return f"${val:.8f}", val
    except Exception:
        pass
    return "n/a", 0.0


def render():
    st.title("Cost Tracking")
    st.write(
        "LiteLLM ships with a built-in pricing database covering 100+ models. "
        "Call `completion_cost(response)` after any request and get the exact USD cost — "
        "no external service, no manual math. "
        "This demo uses **Gemini** models because they have publicly published per-token prices "
        "that LiteLLM can look up. Groq's free tier doesn't publish per-token pricing, so it shows `n/a`."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(COST_DIAGRAM, height=250)
        st.caption("LiteLLM reads token counts from the response and multiplies by the model's per-token price from its internal database.")

    with st.expander("The code — three lines to track cost"):
        st.code("""from litellm import completion, completion_cost

response = completion(
    model="gemini/gemini-2.5-flash-lite",
    messages=[{"role": "user", "content": "Explain RAG in one sentence."}],
    api_key=gemini_key,
)

cost = completion_cost(completion_response=response)

print(f"Input tokens:  {response.usage.prompt_tokens}")
print(f"Output tokens: {response.usage.completion_tokens}")
print(f"Cost:          ${cost:.8f}")   # e.g. $0.00001350""", language="python")

    st.divider()
    require_keys()

    gemini_key = get_gemini_key()
    groq_key   = get_groq_key()

    if not gemini_key:
        st.warning(
            "This demo works best with a **Gemini API key** — Gemini models have full pricing data in LiteLLM. "
            "Add your Gemini key in the sidebar (aistudio.google.com)."
        )
        if not groq_key:
            return

    # ── Single call tab + comparison tab ──────────────────────────────────────
    tab1, tab2 = st.tabs(["Single Call", "Compare Models Side-by-Side"])

    # ── Tab 1: Single call ────────────────────────────────────────────────────
    with tab1:
        st.subheader("Run a call and see its cost")

        available_for_tab1 = []
        if gemini_key:
            available_for_tab1 += _PRICED_MODELS
        if groq_key:
            available_for_tab1 += _UNPRICED_MODELS

        model_labels = [lbl for _, lbl in available_for_tab1]
        model_values = [m   for m,  _   in available_for_tab1]

        sel_label = st.selectbox("Model:", model_labels, key="ll_cost_model_sel")
        sel_model = model_values[model_labels.index(sel_label)]
        sel_key   = get_api_key_for_model(sel_model)

        question = question_selector("cost", LITELLM_QUESTIONS)

        if "ll_cost_runs" not in st.session_state:
            st.session_state.ll_cost_runs = []

        c1, c2 = st.columns([3, 1])
        with c1:
            run_btn = st.button("Run Call and Track Cost", type="primary", key="ll_cost_run1")
        with c2:
            if st.button("Clear History", key="ll_cost_clear"):
                st.session_state.ll_cost_runs = []
                st.rerun()

        if run_btn:
            if not sel_key:
                st.error(f"No API key configured for `{sel_model}`.")
            else:
                try:
                    import litellm
                    litellm.suppress_debug_info = True
                    from litellm import completion
                    with st.spinner(f"Calling `{sel_model}`..."):
                        start = time.time()
                        resp = completion(
                            model=sel_model,
                            messages=[{"role": "user", "content": question}],
                            max_tokens=200,
                            api_key=sel_key,
                        )
                        elapsed_ms = int((time.time() - start) * 1000)
                    cost_str, cost_val = _get_cost(resp)
                    st.session_state.ll_cost_runs.append({
                        "question":          question[:60] + ("..." if len(question) > 60 else ""),
                        "text":              resp.choices[0].message.content or "",
                        "model":             resp.model,
                        "latency":           elapsed_ms,
                        "prompt_tokens":     resp.usage.prompt_tokens,
                        "completion_tokens": resp.usage.completion_tokens,
                        "total_tokens":      resp.usage.total_tokens,
                        "cost_str":          cost_str,
                        "cost_val":          cost_val,
                    })
                except Exception as e:
                    st.error(f"Error: {e}")

        if st.session_state.get("ll_cost_runs"):
            st.divider()
            last = st.session_state.ll_cost_runs[-1]
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Latency",       f"{last['latency']} ms")
            m2.metric("Input Tokens",  last["prompt_tokens"])
            m3.metric("Output Tokens", last["completion_tokens"])
            m4.metric("Cost",          last["cost_str"])
            with st.expander("Response"):
                st.write(last["text"])
                st.caption(f"Model: {last['model']}")

            if len(st.session_state.ll_cost_runs) > 1:
                st.divider()
                st.subheader(f"Running Totals — {len(st.session_state.ll_cost_runs)} calls")
                total_cost   = sum(r["cost_val"] for r in st.session_state.ll_cost_runs)
                total_tokens = sum(r["total_tokens"] for r in st.session_state.ll_cost_runs)
                avg_latency  = sum(r["latency"] for r in st.session_state.ll_cost_runs) // len(st.session_state.ll_cost_runs)
                tc1, tc2, tc3 = st.columns(3)
                tc1.metric("Total Cost",   f"${total_cost:.8f}")
                tc2.metric("Total Tokens", f"{total_tokens:,}")
                tc3.metric("Avg Latency",  f"{avg_latency} ms")

                import pandas as pd
                df = pd.DataFrame([{
                    "Question":     r["question"],
                    "Model":        r["model"],
                    "Latency (ms)": r["latency"],
                    "In Tokens":    r["prompt_tokens"],
                    "Out Tokens":   r["completion_tokens"],
                    "Cost":         r["cost_str"],
                } for r in st.session_state.ll_cost_runs])
                st.dataframe(df, width="stretch")

    # ── Tab 2: Side-by-side comparison ────────────────────────────────────────
    with tab2:
        st.subheader("Run the same prompt across multiple models — compare cost, speed, and quality")

        if not gemini_key:
            st.warning("Add a Gemini API key in the sidebar to run the comparison.")
        else:
            compare_options = []
            if gemini_key:
                compare_options += _PRICED_MODELS
            if groq_key:
                compare_options += _UNPRICED_MODELS

            selected_labels = st.multiselect(
                "Select models to compare:",
                options=[lbl for _, lbl in compare_options],
                default=[lbl for _, lbl in compare_options[:2]],
                key="ll_cost_compare_sel",
            )
            label_to_model = {lbl: m for m, lbl in compare_options}
            selected_models = [(label_to_model[lbl], lbl) for lbl in selected_labels if lbl in label_to_model]

            cmp_question = st.selectbox("Question:", LITELLM_QUESTIONS, key="ll_cost_cmp_q")

            if st.button("Compare All Selected Models", type="primary", key="ll_cost_cmp_btn"):
                if not selected_models:
                    st.warning("Select at least one model.")
                else:
                    results = []
                    with st.status(f"Running {len(selected_models)} calls...", expanded=True) as status:
                        import litellm
                        litellm.suppress_debug_info = True
                        from litellm import completion
                        for model, label in selected_models:
                            api_key = get_api_key_for_model(model)
                            if not api_key:
                                st.write(f"⚠️  `{model}` — no API key, skipping")
                                continue
                            try:
                                start = time.time()
                                resp = completion(
                                    model=model,
                                    messages=[{"role": "user", "content": cmp_question}],
                                    max_tokens=200,
                                    api_key=api_key,
                                )
                                elapsed = int((time.time() - start) * 1000)
                                cost_str, cost_val = _get_cost(resp)
                                results.append({
                                    "Model":        resp.model,
                                    "In Tokens":    resp.usage.prompt_tokens,
                                    "Out Tokens":   resp.usage.completion_tokens,
                                    "Latency (ms)": elapsed,
                                    "Cost":         cost_str,
                                    "_cost_val":    cost_val,
                                    "_text":        resp.choices[0].message.content or "",
                                })
                                st.write(f"✅ `{model}` — {elapsed}ms — {cost_str}")
                            except Exception as e:
                                st.write(f"❌ `{model}` — {str(e)[:100]}")
                        status.update(label="Done", state="complete")
                    st.session_state.ll_cost_cmp_results = results

            if st.session_state.get("ll_cost_cmp_results"):
                results = st.session_state.ll_cost_cmp_results
                st.divider()
                import pandas as pd
                display_df = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in results])
                st.dataframe(display_df, width="stretch")

                st.subheader("Responses")
                cols = st.columns(len(results))
                for col, r in zip(cols, results):
                    with col:
                        st.markdown(f"**{r['Model']}**")
                        st.caption(f"Cost: {r['Cost']}  ·  {r['Latency (ms)']}ms")
                        st.write(r["_text"])

                st.info(
                    "**Why does Groq show `n/a`?** "
                    "Groq's free inference tier doesn't publish per-token prices, "
                    "so LiteLLM's pricing database has no entry to look up. "
                    "Gemini, OpenAI, and Anthropic all publish their prices publicly."
                )

    st.divider()
    st.subheader("Why cost tracking matters")
    st.write(
        "- **Budget control**: Know exactly what each feature or user costs per call\n"
        "- **Model comparison**: Is Gemini 2.5 Flash worth 3x the cost of Flash-Lite for this task?\n"
        "- **Chargeback**: Tag calls with `user=` metadata → build per-user cost reports\n"
        "- **Cache ROI**: If a query costs $0.0001 and fires 500 times/day, caching saves $50/day\n\n"
        "In production, pipe `completion_cost()` into your `success_callback` "
        "(see the Observability demo) to write cost data to your database automatically."
    )
