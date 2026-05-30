import time
import streamlit as st
from modules.litellm_utils import (
    show_diagram, require_keys, get_primary_model, get_api_key_for_model,
)
from modules.litellm_diagrams import OBSERVABILITY_DIAGRAM

# Module-level log — persists across Streamlit reruns within same Python process
_CALL_LOG: list[dict] = []


def _log_success(kwargs, completion_response, start_time, end_time):
    try:
        from litellm import completion_cost
        cost = completion_cost(completion_response=completion_response)
        cost_str = f"${cost:.8f}"
    except Exception:
        cost_str = "n/a"

    _CALL_LOG.append({
        "model":          kwargs.get("model", "unknown"),
        "user":           kwargs.get("user", "anonymous"),
        "prompt_preview": (kwargs.get("messages") or [{}])[-1].get("content", "")[:60],
        "in_tokens":      completion_response.usage.prompt_tokens,
        "out_tokens":     completion_response.usage.completion_tokens,
        "latency_ms":     round((end_time - start_time).total_seconds() * 1000),
        "cost":           cost_str,
    })


def _log_failure(kwargs, exception, start_time, end_time):
    _CALL_LOG.append({
        "model":          kwargs.get("model", "unknown"),
        "user":           kwargs.get("user", "anonymous"),
        "prompt_preview": "[FAILED]",
        "in_tokens":      0,
        "out_tokens":     0,
        "latency_ms":     round((end_time - start_time).total_seconds() * 1000),
        "cost":           "$0.00000000",
    })


def render():
    global _CALL_LOG
    primary = get_primary_model()

    st.title("Observability")
    st.write(
        "In production you **must** log every LLM call: what was asked, what was answered, "
        "how long it took, and how much it cost. "
        "LiteLLM's callback system gives you this in 5 lines of Python — "
        "no external logging service required."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(OBSERVABILITY_DIAGRAM, height=280)
        st.caption("LiteLLM calls your `success_callback` after every successful request, passing the full context.")

    with st.expander("The code"):
        st.code("""import litellm
from litellm import completion

call_log = []

def log_success(kwargs, completion_response, start_time, end_time):
    from litellm import completion_cost
    call_log.append({
        "model":    kwargs.get("model"),
        "user":     kwargs.get("user", "anonymous"),
        "prompt":   kwargs["messages"][-1]["content"][:60],
        "in_tok":   completion_response.usage.prompt_tokens,
        "out_tok":  completion_response.usage.completion_tokens,
        "latency_ms": round((end_time - start_time).total_seconds() * 1000),
        "cost_usd": completion_cost(completion_response=completion_response),
    })

# Register once — called automatically after every completion()
litellm.success_callback = [log_success]
litellm.failure_callback = [log_failure]

# Tag each call with user metadata
completion(
    model="groq/llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": "What is RAG?"}],
    user="alice"
)""", language="python")

    st.divider()
    require_keys()

    # Register callbacks globally once
    import litellm
    litellm.suppress_debug_info = True
    litellm.success_callback = [_log_success]
    litellm.failure_callback = [_log_failure]

    st.subheader("Send tagged calls and watch the audit log fill up")

    predefined = [
        ("alice",   "What is retrieval-augmented generation?"),
        ("bob",     "Explain transformers in one sentence."),
        ("alice",   "What is the difference between fine-tuning and RAG?"),
        ("charlie", "Name 3 popular open-source LLMs."),
        ("bob",     "What does RLHF stand for?"),
    ]

    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.markdown("**Predefined tagged calls**")
        if st.button("Run all 5 predefined calls", type="primary"):
            api_key = get_api_key_for_model(primary)
            if not api_key:
                st.error(f"No API key for `{primary}`.")
                return
            from litellm import completion
            with st.spinner("Sending 5 calls..."):
                for user, prompt in predefined:
                    try:
                        completion(
                            model=primary,
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=80,
                            api_key=api_key,
                            user=user,
                        )
                    except Exception as e:
                        pass
            st.success("Done — check the log")

        st.divider()
        st.markdown("**Or send a custom call**")
        custom_user  = st.text_input("User tag:", value="demo_user", key="ll_obs_user")
        custom_q     = st.text_input("Question:", value="What is a vector database?", key="ll_obs_q")
        if st.button("Send Custom Call"):
            api_key = get_api_key_for_model(primary)
            if not api_key:
                st.error(f"No API key for `{primary}`.")
            else:
                from litellm import completion
                try:
                    completion(
                        model=primary,
                        messages=[{"role": "user", "content": custom_q}],
                        max_tokens=120,
                        api_key=api_key,
                        user=custom_user,
                    )
                    st.success("Call sent — check the log")
                except Exception as e:
                    st.error(f"Error: {e}")

        if st.button("Clear Log"):
            _CALL_LOG.clear()
            st.rerun()

    with col_right:
        st.markdown("**Audit log** (auto-refreshes when you send calls)")
        if _CALL_LOG:
            import pandas as pd
            df = pd.DataFrame(_CALL_LOG)
            df.columns = ["Model", "User", "Prompt Preview", "In Tok", "Out Tok", "Latency (ms)", "Cost"]
            st.dataframe(df, width="stretch")

            total_cost = sum(
                float(r["cost"].replace("$", ""))
                for r in _CALL_LOG
                if r["cost"] not in ("n/a", "$0.00000000")
            )
            total_tokens = sum(r["in_tokens"] + r["out_tokens"] for r in _CALL_LOG)
            st.caption(
                f"Total calls: {len(_CALL_LOG)} · "
                f"Total tokens: {total_tokens:,} · "
                f"Total cost: ${total_cost:.8f}"
            )
        else:
            st.info("No calls logged yet — send some calls to fill the log.")

    st.divider()
    st.subheader("What to do with this data in production")
    st.write(
        "- Write to Postgres / BigQuery for per-user cost chargebacks\n"
        "- Push to Langfuse, Helicone, or Arize for a visual observability dashboard\n"
        "- Alert when cost per user exceeds a threshold\n"
        "- Build prompt quality metrics by logging model + tokens + response\n"
        "- Detect anomalies: unusually long prompts, unusually high costs"
    )
