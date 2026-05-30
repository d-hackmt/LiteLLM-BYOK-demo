import time
import streamlit as st
from modules.litellm_utils import (
    show_diagram, require_keys,
    get_groq_key, get_groq2_key, get_gemini_key,
    get_api_key_for_model, available_models,
)
from modules.litellm_diagrams import SMART_CHATBOT_DIAGRAM


def _classify_task(question: str, model: str, api_key: str) -> str:
    """Use a cheap model to classify the task type."""
    try:
        import litellm
        litellm.suppress_debug_info = True
        from litellm import completion
        resp = completion(
            model=model,
            messages=[{
                "role": "user",
                "content": (
                    "Classify the following query into EXACTLY one word: 'code', 'summary', or 'general'. "
                    f"Query: {question}\n\nAnswer:"
                )
            }],
            max_tokens=5,
            api_key=api_key,
            temperature=0,
        )
        return resp.choices[0].message.content.strip().lower().replace(".", "")
    except Exception:
        return "general"


def _build_routing(avail: list) -> dict:
    """Map task types to ordered fallback chains from available models."""
    groq_key  = get_groq_key()
    groq2_key = get_groq2_key()
    gemini_key = get_gemini_key()

    def _chain(*candidates):
        return [(m, get_api_key_for_model(m)) for m in candidates if m in avail]

    code_chain = _chain(
        "groq/openai/gpt-oss-120b",
        "gemini/gemini-2.5-flash",
        "groq/llama-3.3-70b-versatile",
        "gemini/gemini-2.5-flash-lite",
        "groq/llama-3.1-8b-instant",
    )
    summary_chain = _chain(
        "gemini/gemini-2.5-flash-lite",
        "groq/llama-3.3-70b-versatile",
        "groq/llama-3.1-8b-instant",
        "gemini/gemini-2.5-flash",
    )
    general_chain = _chain(
        "groq/llama-3.3-70b-versatile",
        "groq/openai/gpt-oss-120b",
        "gemini/gemini-2.5-flash-lite",
        "groq/llama-3.1-8b-instant",
    )
    return {
        "code":    code_chain or general_chain,
        "summary": summary_chain or general_chain,
        "general": general_chain or code_chain,
    }


def _call_with_fallbacks(chain: list, messages: list) -> dict:
    """Try each model in chain until one succeeds."""
    import litellm
    litellm.suppress_debug_info = True
    from litellm import completion, completion_cost

    for model, api_key in chain:
        try:
            start = time.time()
            resp = completion(
                model=model,
                messages=messages,
                max_tokens=400,
                api_key=api_key,
            )
            elapsed_ms = int((time.time() - start) * 1000)
            try:
                cost = completion_cost(completion_response=resp)
                cost_str = f"${cost:.8f}"
            except Exception:
                cost_str = "n/a"
            return {
                "text":     resp.choices[0].message.content or "",
                "model":    resp.model,
                "latency":  elapsed_ms,
                "cost":     cost_str,
                "error":    None,
            }
        except Exception as e:
            last_error = str(e)[:120]
            continue

    return {"text": "", "model": "none", "latency": 0, "cost": "$0", "error": last_error}


def render():
    st.title("Smart Chatbot — End-to-End Demo")
    st.write(
        "Everything we've learned, combined into one interactive chatbot. "
        "Every message is **classified by task type**, **routed to the best model**, "
        "falls back silently on failure, and **logs cost and latency per turn**."
    )

    with st.expander("Architecture", expanded=False):
        show_diagram(SMART_CHATBOT_DIAGRAM, height=280)
        st.caption("Classifier → Router → Best model → Fallback chain → Response + audit trail.")

    with st.expander("What happens for each message"):
        st.write(
            "1. **Classify** — a fast, cheap model reads your message and outputs one word: `code`, `summary`, or `general`\n"
            "2. **Route** — the task type maps to an ordered list of models (best fit first)\n"
            "3. **Call with fallbacks** — tries models in order, returns the first success\n"
            "4. **Log** — records which model answered, how long it took, and what it cost"
        )

    st.divider()
    require_keys()

    avail = available_models()
    routing = _build_routing(avail)

    # Classifier model — use whatever's fastest
    classifier_model = (
        "groq/llama-3.1-8b-instant" if "groq/llama-3.1-8b-instant" in avail
        else avail[0]
    )
    classifier_key = get_api_key_for_model(classifier_model)

    # ── Sidebar-style config display ──────────────────────────────────────────
    with st.expander("Routing configuration (from your keys)"):
        for task, chain in routing.items():
            models_str = " → ".join(f"`{m}`" for m, _ in chain) if chain else "none"
            st.write(f"**{task}**: {models_str}")
        st.caption(f"Classifier: `{classifier_model}`")

    # ── Chat UI ───────────────────────────────────────────────────────────────
    if "ll_chat_history" not in st.session_state:
        st.session_state.ll_chat_history = []
    if "ll_chat_log" not in st.session_state:
        st.session_state.ll_chat_log = []

    # Render history
    for turn in st.session_state.ll_chat_history:
        with st.chat_message("user"):
            st.write(turn["question"])
        with st.chat_message("assistant"):
            st.write(turn["answer"])
            with st.expander(f"Routing decision · {turn['task']} · {turn['model']} · {turn['latency']}ms · {turn['cost']}"):
                st.write(f"**Detected task:** `{turn['task']}`")
                st.write(f"**Model answered:** `{turn['model']}`")
                st.write(f"**Latency:** {turn['latency']}ms")
                st.write(f"**Cost:** {turn['cost']}")

    # Input
    user_input = st.chat_input("Ask anything — code, summaries, or general questions...")

    if user_input:
        if not avail:
            st.error("No models available — configure at least one API key in the sidebar.")
            return

        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Classifying → routing → calling..."):
                # Step 1: classify
                task = _classify_task(user_input, classifier_model, classifier_key)
                task = task if task in ("code", "summary", "general") else "general"

                # Step 2: get chain
                chain = routing.get(task, routing["general"])
                if not chain:
                    st.error("No models available for this task type.")
                    return

                # Step 3: call with fallbacks
                messages = [{"role": "user", "content": user_input}]
                result = _call_with_fallbacks(chain, messages)

            if result["error"] and not result["text"]:
                st.error(f"All models failed: {result['error']}")
            else:
                st.write(result["text"])
                with st.expander(f"Routing decision · {task} · {result['model']} · {result['latency']}ms · {result['cost']}"):
                    st.write(f"**Detected task:** `{task}`")
                    st.write(f"**Model answered:** `{result['model']}`")
                    st.write(f"**Latency:** {result['latency']}ms")
                    st.write(f"**Cost:** {result['cost']}")
                    st.write(f"**Chain tried:** {' → '.join(m for m, _ in chain)}")

                # Save to history and log
                turn = {
                    "question": user_input,
                    "answer":   result["text"],
                    "task":     task,
                    "model":    result["model"],
                    "latency":  result["latency"],
                    "cost":     result["cost"],
                }
                st.session_state.ll_chat_history.append(turn)
                st.session_state.ll_chat_log.append(turn)

    # ── Stats panel ───────────────────────────────────────────────────────────
    if st.session_state.ll_chat_log:
        st.divider()
        log = st.session_state.ll_chat_log
        total_turns = len(log)
        avg_latency = sum(t["latency"] for t in log) // total_turns

        task_dist = {}
        for t in log:
            task_dist[t["task"]] = task_dist.get(t["task"], 0) + 1

        c1, c2, c3 = st.columns(3)
        c1.metric("Total turns", total_turns)
        c2.metric("Avg latency", f"{avg_latency}ms")
        c3.metric("Task distribution", " / ".join(f"{k}:{v}" for k, v in task_dist.items()))

        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            if st.button("Clear Chat"):
                st.session_state.ll_chat_history = []
                st.session_state.ll_chat_log = []
                st.rerun()
