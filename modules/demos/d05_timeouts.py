import time
import streamlit as st
from modules.utils import (
    require_keys, make_client, extract_text, build_messages,
    show_diagram, get_model_used, get_virtual_key, get_primary_model
)
from modules.diagrams import TIMEOUT_DIAGRAM
from modules.questions import INTERESTING_QUESTIONS


def render():
    PRIMARY_MODEL = get_primary_model()
    vk = get_virtual_key()

    st.title("Request Timeouts")
    st.write(
        "Sometimes an LLM takes too long — a stuck request can hang your entire app indefinitely. "
        "Portkey's timeout config sets a hard time limit in milliseconds. "
        "If the model doesn't respond in time, Portkey returns a 408 and you handle it gracefully."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(TIMEOUT_DIAGRAM, height=440)
        st.caption(
            "The timer starts when Portkey receives your request. "
            "If the LLM hasn't responded by the deadline, Portkey cuts the connection and returns 408."
        )

    st.divider()
    require_keys()

    st.subheader("Configure")

    col1, col2 = st.columns(2)
    with col1:
        tight_ms = st.slider(
            "Tight timeout (ms) — will force a timeout",
            min_value=500, max_value=4000, value=1500, step=250,
            help="The large 70B model usually needs 3–8s. Anything under ~2.5s will reliably time out.",
        )
    with col2:
        generous_ms = st.slider(
            "Generous timeout (ms) — will let it succeed",
            min_value=5000, max_value=60000, value=30000, step=5000,
            help="Plenty of time for the model to respond. Used for the comparison run.",
        )

    col1, col2 = st.columns(2)
    col1.metric("Tight timeout", f"{tight_ms}ms = {tight_ms/1000:.1f}s")
    col2.metric("Generous timeout", f"{generous_ms}ms = {generous_ms/1000:.0f}s")

    with st.expander("Portkey config being used"):
        st.json({"virtual_key": vk, "request_timeout": tight_ms})
        st.caption("Swap the value to switch between a tight and generous timeout.")

    st.divider()

    question = st.selectbox("Question:", INTERESTING_QUESTIONS, key="timeout_q")
    custom_q = st.text_input("Or type your own:", key="timeout_custom", placeholder="Ask anything...")
    active_q = custom_q.strip() if custom_q.strip() else question

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Force a Timeout")
        st.caption(f"Uses {tight_ms}ms limit — primary 70B will almost certainly exceed this.")
        if st.button("▶  Watch It Time Out", type="primary", width="stretch", key="btn_tight"):
            _run_tight(PRIMARY_MODEL, vk, tight_ms, active_q)

        if st.session_state.get("timeout_tight"):
            r = st.session_state.timeout_tight
            if not r["success"]:
                st.error(f"⏱ **Timed out** after {r['latency']}ms (limit: {tight_ms}ms)")
                st.caption("408 error — request exceeded the time limit and was cut off by Portkey.")
            else:
                st.success(f"✅ Responded in {r['latency']}ms — try a shorter timeout to see the cutoff.")
                st.write(r["text"])

    with col2:
        st.subheader("Run with Generous Timeout")
        st.caption(f"Uses {generous_ms}ms — gives the model enough time to respond.")
        if st.button("▶  Run Normally", width="stretch", key="btn_generous"):
            _run_generous(PRIMARY_MODEL, vk, generous_ms, active_q)

        if st.session_state.get("timeout_generous"):
            r = st.session_state.timeout_generous
            if r["success"]:
                st.success(f"✅ Responded in **{r['latency']}ms** with a {generous_ms}ms limit")
                st.write(r["text"])
                st.caption(f"Model: {r['model']}")
            else:
                st.error(f"Timed out even at {generous_ms}ms — very unusual.")

    if st.session_state.get("timeout_tight") and st.session_state.get("timeout_generous"):
        tight = st.session_state.timeout_tight
        gen = st.session_state.timeout_generous
        if not tight["success"] and gen["success"]:
            st.divider()
            st.subheader("Side by side")
            c1, c2, c3 = st.columns(3)
            c1.metric("Tight timeout", f"{tight_ms}ms", delta="timed out ✕", delta_color="inverse")
            c2.metric("Generous timeout", f"{generous_ms}ms", delta="succeeded ✓")
            c3.metric("Model response time", f"~{gen['latency']}ms",
                      delta=f">{tight_ms}ms so tight cut it off", delta_color="inverse")
            st.success(
                f"The model actually took ~{gen['latency']}ms to respond. "
                f"The {tight_ms}ms timeout cut the request off early — "
                "Portkey returned a 408 before the model had a chance to finish."
            )

    st.divider()
    st.subheader("When to use timeouts")
    st.write(
        "- **User-facing features** → 8–15s max. Users abandon after 15 seconds.\n"
        "- **Background jobs** → 60–120s. More tolerance for slow responses.\n"
        "- **Combine with retry** → timeout + retry means: try fast, if too slow try again.\n"
        "- **Combine with fallback** → timeout + fallback means: if primary is slow, switch to faster model."
    )


def _run_tight(primary_model, vk, timeout_ms, question):
    with st.status(f"Running with {timeout_ms}ms timeout...", expanded=True) as status:
        st.write(f"Sending request to `{primary_model}`...")
        st.write(f"⏱ Portkey timer starts — {timeout_ms}ms limit active...")
        client = make_client(config={"virtual_key": vk, "request_timeout": timeout_ms})
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
            st.write(f"✅ Responded in {elapsed}ms — timeout was not hit.")
            status.update(label="Responded before timeout", state="complete")
            st.session_state.timeout_tight = {
                "success": True, "latency": elapsed,
                "text": text, "model": model,
            }
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            st.write(f"⏱ **Timer expired at {elapsed}ms** — Portkey cut the request.")
            st.write("Portkey returned: `408 Request Timeout`")
            status.update(label=f"Timed out at {elapsed}ms — 408 returned", state="error")
            st.session_state.timeout_tight = {
                "success": False, "latency": elapsed,
                "text": str(e), "model": "—",
            }


def _run_generous(primary_model, vk, timeout_ms, question):
    with st.status(f"Running with {timeout_ms}ms timeout...", expanded=True) as status:
        st.write(f"Sending request to `{primary_model}`...")
        st.write(f"⏱ Timer starts — {timeout_ms}ms limit ({timeout_ms//1000}s) — plenty of time...")
        client = make_client(config={"virtual_key": vk, "request_timeout": timeout_ms})
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
            st.write(f"✅ Responded in **{elapsed}ms** — well within the {timeout_ms}ms limit.")
            status.update(label=f"Responded in {elapsed}ms", state="complete")
            st.session_state.timeout_generous = {
                "success": True, "latency": elapsed,
                "text": text, "model": model,
            }
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            st.write(f"Timed out even at {timeout_ms}ms: {e}")
            status.update(label="Unexpected timeout", state="error")
            st.session_state.timeout_generous = {
                "success": False, "latency": elapsed,
                "text": str(e), "model": "—",
            }
