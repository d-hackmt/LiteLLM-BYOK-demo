import time
import streamlit as st
from modules.utils import (
    require_keys, make_client, extract_text, build_messages,
    show_diagram, get_model_used, get_virtual_key, get_primary_model
)
from modules.diagrams import RETRY_DIAGRAM
from modules.questions import INTERESTING_QUESTIONS


def render():
    PRIMARY_MODEL = get_primary_model()
    vk = get_virtual_key()

    st.title("Automatic Retries")
    st.write(
        "LLMs hit rate limits (429) and occasionally throw 500 errors. "
        "Without a gateway your app crashes and the user sees an error. "
        "With Portkey's retry config, failed requests are automatically retried with backoff "
        "— your app never knows anything went wrong."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(RETRY_DIAGRAM, height=520)
        st.caption(
            "Portkey catches the error, waits, and retries. "
            "Your app sends one request and gets one response — the retry loop is invisible."
        )

    st.divider()
    require_keys()

    st.subheader("Configure")

    col1, col2 = st.columns(2)
    with col1:
        attempts = st.slider("Max retry attempts", 1, 5, 3)
    with col2:
        status_codes = st.multiselect(
            "Retry on these status codes",
            options=[429, 500, 502, 503, 504],
            default=[429, 500, 503],
        )
    if not status_codes:
        status_codes = [429, 500, 503]

    retry_config = {
        "virtual_key": vk,
        "retry": {"attempts": attempts, "on_status_codes": status_codes},
    }

    with st.expander("Portkey config"):
        st.json(retry_config)

    st.divider()

    simulate = st.toggle(
        "Simulate a transient error on first attempt",
        value=True,
        help=(
            "ON: first attempt deliberately fails so you can see Portkey retry and recover. "
            "OFF: normal request — retry config is armed but won't be triggered unless Groq returns an error."
        ),
    )

    if simulate:
        st.info(
            "First attempt will use an invalid key and fail. "
            "The second attempt uses your real key and succeeds. "
            "This is exactly what Portkey does when it catches a 429 or 500."
        )
    else:
        st.info(
            "Normal request — likely succeeds on attempt 1. "
            "The retry config is active but will only fire if Groq returns an error."
        )

    question = st.selectbox("Question:", INTERESTING_QUESTIONS, key="retry_q")
    custom_q = st.text_input("Or type your own:", key="retry_custom", placeholder="Ask anything...")
    active_q = custom_q.strip() if custom_q.strip() else question

    if st.button("▶  Run with Retry Config", type="primary", width="stretch"):
        _run_demo(PRIMARY_MODEL, vk, attempts, status_codes, active_q, simulate)

    if st.session_state.get("retry_result"):
        _show_results(attempts, status_codes)


def _run_demo(primary_model, vk, attempts, status_codes, question, simulate):
    total_start = time.time()

    with st.status("Running retry sequence...", expanded=True) as status:

        if simulate:
            # ── Attempt 1: deliberately fails ──────────────────────────────
            st.write(f"**Attempt 1 of {attempts}** — calling `{primary_model}`...")
            bad_client = make_client(config={"virtual_key": "invalid-demo-key-portkey"})
            start = time.time()
            try:
                bad_client.chat.completions.create(
                    model=primary_model,
                    messages=build_messages(question),
                    max_tokens=10,
                )
                st.write("✅ Succeeded on attempt 1 — no retry needed.")
                # handle unexpected success same as normal path below
                simulate = False
            except Exception as e:
                elapsed = int((time.time() - start) * 1000)
                st.write(
                    f"❌ **Error on attempt 1** ({elapsed}ms) — "
                    f"`{str(e)[:90]}`"
                )

            if simulate:
                time.sleep(0.5)
                st.write("⏳ Portkey backs off and retries...")
                time.sleep(0.5)

                # ── Attempt 2: succeeds ──────────────────────────────────────
                st.write(f"**Attempt 2 of {attempts}** — retrying with valid config...")
                good_client = make_client(config={"virtual_key": vk})
                start = time.time()
                try:
                    response = good_client.chat.completions.create(
                        model=primary_model,
                        messages=build_messages(question),
                        max_tokens=200,
                    )
                    elapsed = int((time.time() - start) * 1000)
                    text = extract_text(response)
                    model = get_model_used(response)
                    st.write(f"✅ **Succeeded on attempt 2** in {elapsed}ms!")
                    status.update(
                        label="Retry succeeded — response delivered to your app",
                        state="complete",
                    )
                    st.session_state.retry_result = {
                        "text": text, "latency": elapsed, "model": model,
                        "which_attempt": 2, "retried": True,
                        "total_ms": int((time.time() - total_start) * 1000),
                    }
                    return
                except Exception as e2:
                    st.error(f"Also failed on retry: {e2}")
                    status.update(label="All attempts failed", state="error")
                    return

        # ── Normal path (no simulated failure) ───────────────────────────────
        client = make_client(config={
            "virtual_key": vk,
            "retry": {"attempts": attempts, "on_status_codes": status_codes},
        })
        st.write(f"**Attempt 1** — calling `{primary_model}` (retry config is armed)...")
        start = time.time()
        try:
            response = client.chat.completions.create(
                model=primary_model,
                messages=build_messages(question),
                max_tokens=200,
            )
            elapsed = int((time.time() - start) * 1000)
            text = extract_text(response)
            model = get_model_used(response)
            st.write(f"✅ **Succeeded on attempt 1** in {elapsed}ms — no retry triggered.")
            status.update(
                label="Done — first attempt succeeded, retry config ready but not needed",
                state="complete",
            )
            st.session_state.retry_result = {
                "text": text, "latency": elapsed, "model": model,
                "which_attempt": 1, "retried": False,
                "total_ms": int((time.time() - total_start) * 1000),
            }
        except Exception as e:
            st.error(f"Error after all retry attempts: {e}")
            status.update(label="All attempts failed", state="error")


def _show_results(attempts, status_codes):
    r = st.session_state.retry_result
    st.divider()
    st.subheader("What happened")

    if r["retried"]:
        st.error("❌ **Attempt 1** — error (invalid key, simulating a 429 / 500)")
        st.success(f"✅ **Attempt 2** — succeeded in **{r['latency']}ms**")
    else:
        st.success(f"✅ **Attempt 1** — succeeded in **{r['latency']}ms** (retry config armed but not triggered)")

    st.divider()

    col1, col2, col3 = st.columns(3)
    col1.metric("Latency (final attempt)", f"{r['latency']}ms")
    col2.metric("Attempt that succeeded", f"#{r['which_attempt']}")
    col3.metric("Total time", f"{r['total_ms']}ms")

    st.write(r["text"])
    st.caption(f"Model: {r['model']}")

    if r["retried"]:
        st.success(
            "Attempt 1 failed. Portkey retried automatically — "
            "your app received a successful response with zero error handling code."
        )

    st.divider()
    st.subheader("Without retry vs with retry")
    c1, c2 = st.columns(2)
    with c1:
        st.write("**Without retry**")
        st.write(
            "- First 429 or 500 → exception thrown\n"
            "- User sees an error message\n"
            "- Request is lost\n"
            "- You have to write retry logic yourself"
        )
    with c2:
        st.write(f"**With Portkey retry (max {attempts})**")
        st.write(
            "- First failure → wait 1s → retry\n"
            "- Second failure → wait 2s → retry\n"
            "- Your app receives the successful response\n"
            "- Zero custom retry code needed"
        )
