import time
import streamlit as st
from modules.litellm_utils import (
    show_diagram, question_selector, require_keys,
    get_primary_model, get_fallback_model,
    get_api_key_for_model, available_models,
    LITELLM_QUESTIONS,
)
from modules.litellm_diagrams import FALLBACK_DIAGRAM


def render():
    primary   = get_primary_model()
    fallback  = get_fallback_model()

    st.title("Automatic Fallbacks")
    st.write(
        "What happens when your primary LLM goes down or hits its rate limit? "
        "LiteLLM's `fallbacks` parameter lets you define a chain of backup models. "
        "If the primary fails for any reason, LiteLLM silently retries with the next model — "
        "your application never sees the error."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(FALLBACK_DIAGRAM, height=300)
        st.caption("LiteLLM intercepts the error, moves to the next model in the fallbacks list, and returns the first success.")

    with st.expander("The code"):
        st.code(f"""from litellm import completion

response = completion(
    model="{primary}",           # primary — try this first
    messages=[{{"role": "user", "content": "..."}}],
    fallbacks=[
        "{fallback}",             # 1st backup
        "groq/llama-3.1-8b-instant",  # 2nd backup
    ]
)

# response.model tells you which model actually answered
print("Answered by:", response.model)""", language="python")

    st.divider()
    require_keys()

    avail = available_models()
    if len(avail) < 2:
        st.warning(
            "Fallback demos are most useful with 2+ providers configured. "
            "Add a second provider key in the sidebar to see a real cross-provider fallback."
        )

    st.subheader("Configuration")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Primary model**")
        st.code(primary)
    with col2:
        st.markdown("**Fallback chain**")
        st.code(fallback + "\n(+ any other configured models as further backups)")

    simulate = st.toggle(
        "Simulate primary failure — force fallback to activate",
        value=True,
        help="ON: uses a fake model name so the primary always fails. OFF: normal call where primary succeeds.",
    )

    if simulate:
        st.warning(
            "Primary will use **`nonexistent-model-xyz`** → `BadRequestError` → "
            "LiteLLM routes to the fallback chain. Watch which model ends up answering."
        )
    else:
        st.info("Normal call — primary should succeed. Toggle ON to see the fallback activate.")

    question = question_selector("fallback", LITELLM_QUESTIONS)

    st.divider()

    if st.button(
        "Run — Watch Fallback Activate" if simulate else "Run with Fallback Config",
        type="primary",
    ):
        _run(primary, fallback, avail, simulate, question)

    if st.session_state.get("ll_fallback_result"):
        _show(primary, fallback)


def _run(primary, fallback, avail, simulate, question):
    import litellm
    litellm.suppress_debug_info = True
    from litellm import completion

    primary_key  = get_api_key_for_model(primary)
    fallback_key = get_api_key_for_model(fallback)

    # Build a fallbacks list from all available models except primary
    other_models = [m for m in avail if m != primary]
    if fallback not in other_models and fallback_key:
        other_models.insert(0, fallback)

    effective_primary = "groq/nonexistent-model-xyz" if simulate else primary
    effective_key     = primary_key  # key stays valid; bad model name causes the error

    total_start = time.time()

    with st.status("Running fallback sequence...", expanded=True) as status:
        if simulate:
            st.write(f"Trying primary: `{effective_primary}` ...")
            try:
                start = time.time()
                completion(
                    model=effective_primary,
                    messages=[{"role": "user", "content": question}],
                    max_tokens=10,
                    api_key=effective_key,
                )
                st.write("✅ Primary succeeded (unexpected). Fallback not needed.")
            except Exception as e:
                elapsed = int((time.time() - start) * 1000)
                st.write(f"❌ Primary failed in {elapsed}ms — `{str(e)[:100]}`")

            # Activate fallback
            if other_models:
                fb_model = other_models[0]
                fb_key   = get_api_key_for_model(fb_model)
                time.sleep(0.3)
                st.write(f"🔀 Activating fallback: `{fb_model}` ...")
                try:
                    start = time.time()
                    resp = completion(
                        model=fb_model,
                        messages=[{"role": "user", "content": question}],
                        max_tokens=250,
                        api_key=fb_key,
                    )
                    elapsed = int((time.time() - start) * 1000)
                    st.write(f"✅ Fallback responded in {elapsed}ms!")
                    status.update(label="Fallback delivered — user saw no error", state="complete")
                    st.session_state.ll_fallback_result = {
                        "text": resp.choices[0].message.content or "",
                        "latency": elapsed,
                        "model": resp.model,
                        "used_fallback": True,
                        "total_ms": int((time.time() - total_start) * 1000),
                        "primary": primary,
                        "fallback": fb_model,
                    }
                except Exception as e2:
                    st.error(f"Fallback also failed: {e2}")
                    status.update(label="Both targets failed", state="error")
            else:
                st.error("No fallback model available — add a second provider key in the sidebar.")
                status.update(label="No fallback configured", state="error")
            return

        # Normal path — primary is valid
        st.write(f"Trying primary: `{primary}` ...")
        try:
            start = time.time()
            resp = completion(
                model=primary,
                messages=[{"role": "user", "content": question}],
                max_tokens=250,
                api_key=primary_key,
                fallbacks=other_models[:2] if other_models else [],
            )
            elapsed = int((time.time() - start) * 1000)
            st.write(f"✅ Primary responded in {elapsed}ms — fallback not triggered.")
            status.update(label="Primary succeeded — fallback config armed but unused", state="complete")
            st.session_state.ll_fallback_result = {
                "text": resp.choices[0].message.content or "",
                "latency": elapsed,
                "model": resp.model,
                "used_fallback": False,
                "total_ms": int((time.time() - total_start) * 1000),
                "primary": primary,
                "fallback": other_models[0] if other_models else fallback,
            }
        except Exception as e:
            st.error(f"Error: {e}")
            status.update(label="Request failed", state="error")


def _show(primary, fallback):
    r = st.session_state.ll_fallback_result
    st.divider()
    st.subheader("What happened")

    if r["used_fallback"]:
        st.error(f"❌ **Primary** `{r['primary']}` — failed (bad model / rate-limit / error)")
        st.success(f"✅ **Fallback** `{r['fallback']}` — responded in **{r['latency']}ms**")
    else:
        st.success(f"✅ **Primary** `{r['primary']}` — responded in **{r['latency']}ms** (fallback config armed)")

    col1, col2, col3 = st.columns(3)
    col1.metric("Latency", f"{r['latency']}ms")
    col2.metric("Answered by", "Fallback" if r["used_fallback"] else "Primary")
    col3.metric("Total time", f"{r['total_ms']}ms")

    st.write(r["text"])
    st.caption(f"Model: {r['model']}")

    if r["used_fallback"]:
        st.success(
            "The primary model was unavailable. LiteLLM automatically routed to the fallback "
            "— your application received a valid response with zero error-handling code on your side."
        )
    else:
        st.info("Toggle **'Simulate primary failure'** above to watch the fallback chain activate.")

    st.divider()
    st.subheader("When fallbacks save the day")
    st.write(
        "- **Provider outage** — Groq, OpenAI, or Anthropic goes down\n"
        "- **Rate limit** — primary quota exhausted, fallback has fresh quota\n"
        "- **Cost cutover** — primary is expensive, fallback is cheaper on budget spike\n"
        "- **Cross-provider resilience** — if all Groq models fail, fall back to Gemini\n"
        "- **Model deprecation** — old model removed by provider, fallback keeps app alive"
    )
