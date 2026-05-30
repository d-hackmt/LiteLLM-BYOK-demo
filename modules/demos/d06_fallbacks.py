import time
import streamlit as st
from modules.utils import (
    require_keys, make_client, extract_text, build_messages,
    show_diagram, get_model_used, get_virtual_key,
    get_primary_model, get_fallback_model, get_fallback_key
)
from modules.diagrams import FALLBACK_DIAGRAM
from modules.questions import INTERESTING_QUESTIONS


def render():
    PRIMARY_MODEL = get_primary_model()
    FALLBACK_MODEL = get_fallback_model()
    vk = get_virtual_key()
    fvk = get_fallback_key()

    st.title("Fallback Routing")
    st.write(
        "What happens when your primary LLM goes down or hits its quota? "
        "With fallback routing, Portkey automatically switches to a backup model — "
        "no code changes, no downtime, no user-visible errors."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(FALLBACK_DIAGRAM, height=300)
        st.caption(
            "Portkey tries the primary target first. On any failure (4xx, 5xx) it immediately "
            "routes the same request to the next target in the list."
        )

    st.divider()
    require_keys()

    st.subheader("Setup")

    col1, col2 = st.columns(2)
    with col1:
        st.write("**Primary target**")
        st.write(f"Model: `{PRIMARY_MODEL}`")
        st.write(f"Virtual Key: `{vk}`")
    with col2:
        st.write("**Fallback target**")
        st.write(f"Model: `{FALLBACK_MODEL}`")
        st.write(f"Virtual Key: `{fvk}`" + (" *(same as primary)*" if fvk == vk else ""))

    simulate = st.toggle(
        "Simulate primary failure — watch fallback activate",
        value=True,
        help=(
            "ON: primary uses an invalid key so it fails, forcing Portkey to route to fallback. "
            "OFF: normal request where primary succeeds."
        ),
    )

    if simulate:
        st.warning(
            "Primary will use an **invalid virtual key** → auth error → "
            "Portkey immediately routes to the fallback model. "
            "Watch which model ends up answering."
        )
    else:
        st.info("Normal request — primary should succeed. Toggle ON to see the fallback activate.")

    fallback_config = {
        "strategy": {"mode": "fallback"},
        "targets": [
            {"virtual_key": "invalid-key-for-demo" if simulate else vk,
             "override_params": {"model": PRIMARY_MODEL}},
            {"virtual_key": fvk,
             "override_params": {"model": FALLBACK_MODEL}},
        ],
    }

    with st.expander("Portkey config"):
        st.json(fallback_config)
        st.caption(
            "The config is identical whether or not the primary fails. "
            "Portkey checks the response and routes automatically."
        )

    st.divider()

    question = st.selectbox("Question:", INTERESTING_QUESTIONS, key="fallback_q")
    custom_q = st.text_input("Or type your own:", key="fallback_custom", placeholder="Ask anything...")
    active_q = custom_q.strip() if custom_q.strip() else question

    label = "▶  Run — Watch Fallback Activate" if simulate else "▶  Run with Fallback Config"
    if st.button(label, type="primary", width="stretch"):
        _run_demo(PRIMARY_MODEL, FALLBACK_MODEL, vk, fvk, simulate, active_q)

    if st.session_state.get("fallback_result"):
        _show_results(PRIMARY_MODEL, FALLBACK_MODEL)


def _run_demo(primary_model, fallback_model, vk, fvk, simulate, question):
    total_start = time.time()

    with st.status("Running fallback sequence...", expanded=True) as status:

        if simulate:
            # ── Step 1: primary fails ──────────────────────────────────────
            st.write(f"**Trying primary** — calling `{primary_model}`...")
            bad_client = make_client(config={"virtual_key": "invalid-key-for-demo"})
            start = time.time()
            try:
                bad_client.chat.completions.create(
                    model=primary_model,
                    messages=build_messages(question),
                    max_tokens=10,
                )
                st.write("✅ Primary succeeded (unexpected). Fallback not needed.")
                simulate = False
            except Exception as e:
                elapsed = int((time.time() - start) * 1000)
                st.write(
                    f"❌ **Primary failed** ({elapsed}ms) — "
                    f"`{str(e)[:90]}`"
                )

            if simulate:
                time.sleep(0.4)
                st.write(f"🔀 **Activating fallback** — routing to `{fallback_model}`...")

                # ── Step 2: fallback succeeds ──────────────────────────────
                good_client = make_client(config={"virtual_key": fvk})
                start = time.time()
                try:
                    response = good_client.chat.completions.create(
                        model=fallback_model,
                        messages=build_messages(question),
                        max_tokens=250,
                    )
                    elapsed = int((time.time() - start) * 1000)
                    text = extract_text(response)
                    model = get_model_used(response)
                    st.write(f"✅ **Fallback responded** in {elapsed}ms!")
                    status.update(
                        label="Fallback delivered the response — user saw no error",
                        state="complete",
                    )
                    st.session_state.fallback_result = {
                        "text": text, "latency": elapsed, "model": model,
                        "used_fallback": True,
                        "total_ms": int((time.time() - total_start) * 1000),
                        "primary_model": primary_model,
                        "fallback_model": fallback_model,
                    }
                    return
                except Exception as e2:
                    st.error(f"Fallback also failed: {e2}")
                    status.update(label="Both targets failed", state="error")
                    return

        # ── Normal path: primary succeeds ──────────────────────────────────
        client = make_client(config={
            "strategy": {"mode": "fallback"},
            "targets": [
                {"virtual_key": vk, "override_params": {"model": primary_model}},
                {"virtual_key": fvk, "override_params": {"model": fallback_model}},
            ],
        })
        st.write(f"**Trying primary** — calling `{primary_model}`...")
        start = time.time()
        try:
            response = client.chat.completions.create(
                model=primary_model,
                messages=build_messages(question),
                max_tokens=250,
            )
            elapsed = int((time.time() - start) * 1000)
            text = extract_text(response)
            model = get_model_used(response)
            st.write(f"✅ **Primary responded** in {elapsed}ms — fallback not needed.")
            status.update(
                label="Primary succeeded — fallback config ready but not triggered",
                state="complete",
            )
            st.session_state.fallback_result = {
                "text": text, "latency": elapsed, "model": model,
                "used_fallback": False,
                "total_ms": int((time.time() - total_start) * 1000),
                "primary_model": primary_model,
                "fallback_model": fallback_model,
            }
        except Exception as e:
            st.error(f"Error: {e}")
            status.update(label="Request failed", state="error")


def _show_results(primary_model, fallback_model):
    r = st.session_state.fallback_result
    st.divider()
    st.subheader("What happened")

    if r["used_fallback"]:
        st.error(f"❌ **Primary** `{r['primary_model']}` — failed (auth error / unavailable)")
        st.success(f"✅ **Fallback** `{r['fallback_model']}` — responded in **{r['latency']}ms**")
    else:
        st.success(
            f"✅ **Primary** `{r['primary_model']}` — responded in **{r['latency']}ms** "
            f"(fallback config armed but not triggered)"
        )

    st.divider()

    col1, col2, col3 = st.columns(3)
    col1.metric("Latency", f"{r['latency']}ms")
    col2.metric("Answered by", "Fallback" if r["used_fallback"] else "Primary")
    col3.metric("Total time", f"{r['total_ms']}ms")

    st.write(r["text"])
    st.caption(f"Model: {r['model']}")

    if r["used_fallback"]:
        st.success(
            "Primary model was unavailable. "
            "Portkey automatically routed to the fallback — "
            "your application received a valid response with zero error handling code."
        )
    else:
        st.info(
            "Primary succeeded. Toggle **'Simulate primary failure'** above "
            "to watch the fallback activate."
        )

    st.divider()
    st.subheader("Real-world fallback scenarios")
    st.write(
        "- **Model outage** — provider maintenance or unexpected downtime\n"
        "- **Rate limit** — primary quota exhausted, fallback has fresh quota\n"
        "- **Cost control** — fallback to a cheaper model when budget is tight\n"
        "- **Cross-provider** — primary is Groq, fallback is OpenAI or Anthropic\n"
        "- **Latency spike** — primary is slow, fallback (smaller model) is faster"
    )
