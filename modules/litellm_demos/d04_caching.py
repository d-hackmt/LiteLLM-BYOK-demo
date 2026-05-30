import time
import streamlit as st
from modules.litellm_utils import (
    show_diagram, require_keys, get_primary_model, get_api_key_for_model,
    LITELLM_QUESTIONS,
)
from modules.litellm_diagrams import CACHE_DIAGRAM


def _init_cache():
    if not st.session_state.get("ll_cache_ready"):
        import litellm
        litellm.suppress_debug_info = True
        from litellm.caching import Cache
        litellm.cache = Cache(type="local")
        st.session_state.ll_cache_ready = True


def _clear_cache():
    import litellm
    litellm.cache = None
    st.session_state.ll_cache_ready = False
    st.session_state.pop("ll_cache_miss", None)
    st.session_state.pop("ll_cache_hit", None)


def render():
    primary = get_primary_model()

    st.title("Response Caching")
    st.write(
        "If 100 users ask the same question, why call the LLM 100 times? "
        "Enable LiteLLM's in-memory cache with one line. "
        "The first call hits the API; every identical call after returns from cache — "
        "**instantly**, at **zero cost**."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(CACHE_DIAGRAM, height=320)
        st.caption(
            "LiteLLM hashes the request (model + full messages list). "
            "Cache hit → return stored response. Cache miss → call LLM, store result."
        )

    with st.expander("The code — one line to enable"):
        st.code("""import litellm
from litellm import completion
from litellm.caching import Cache

# Enable in-memory cache (swap type="redis" for production)
litellm.cache = Cache(type="local")

# Pass caching=True on the calls you want cached
response = completion(
    model="groq/llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": "What is RAG?"}],
    caching=True
)
# Second call with same model + same messages → instant cache hit, $0 cost""", language="python")

    st.divider()
    require_keys()

    st.subheader("Pick a question")
    st.write("Choose or type a question, then run it **twice** — first call hits the API, second returns from cache.")

    question = st.selectbox("Choose a question:", LITELLM_QUESTIONS, key="ll_cache_q_sel")
    custom_q = st.text_input("Or type your own:", key="ll_cache_q_custom",
                              placeholder="Be exact — caching matches character-for-character")
    active_q = custom_q.strip() if custom_q.strip() else question
    st.info(f"Active question: **{active_q}**")

    st.divider()

    col_btn1, col_btn2 = st.columns([2, 1])
    with col_btn2:
        if st.button("Clear Cache & Reset"):
            _clear_cache()
            st.rerun()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Run 1 — Cache Miss")
        st.write("Calls the LLM. Response is stored in cache for the next identical request.")

        if st.button("Run First Request (Cold)", key="ll_cache_run1"):
            _init_cache()
            api_key = get_api_key_for_model(primary)
            if not api_key:
                st.error(f"No API key for `{primary}`.")
                return
            try:
                import litellm
                from litellm import completion
                with st.spinner("Calling LLM..."):
                    start = time.time()
                    resp = completion(
                        model=primary,
                        messages=[{"role": "user", "content": active_q}],
                        max_tokens=250,
                        api_key=api_key,
                        caching=True,
                        cache={"no-cache": True},  # force a fresh API call
                    )
                    elapsed = int((time.time() - start) * 1000)
                    st.session_state.ll_cache_miss = {
                        "text":    resp.choices[0].message.content or "",
                        "latency": elapsed,
                        "model":   resp.model,
                        "question": active_q,
                    }
            except Exception as e:
                st.error(f"Error: {e}")

        if st.session_state.get("ll_cache_miss"):
            r = st.session_state.ll_cache_miss
            st.metric("Latency (API call)", f"{r['latency']} ms")
            st.write(r["text"])
            st.caption(f"Model: {r['model']}")

    with col2:
        st.subheader("Run 2 — Cache Hit")
        st.write("Same question, same model. LiteLLM returns the cached response without calling the LLM.")

        if not st.session_state.get("ll_cache_miss"):
            st.info("Run the first request first.")
        else:
            cached_q = st.session_state.ll_cache_miss["question"]
            if st.button("Run Second Request (Cached)", type="primary", key="ll_cache_run2"):
                api_key = get_api_key_for_model(primary)
                try:
                    import litellm
                    from litellm import completion
                    with st.spinner("Checking cache..."):
                        start = time.time()
                        resp = completion(
                            model=primary,
                            messages=[{"role": "user", "content": cached_q}],
                            max_tokens=250,
                            api_key=api_key,
                            caching=True,
                        )
                        elapsed = int((time.time() - start) * 1000)
                        st.session_state.ll_cache_hit = {
                            "text":    resp.choices[0].message.content or "",
                            "latency": elapsed,
                            "model":   resp.model,
                        }
                except Exception as e:
                    st.error(f"Error: {e}")

            if st.session_state.get("ll_cache_hit"):
                r = st.session_state.ll_cache_hit
                miss_ms = st.session_state.ll_cache_miss["latency"]
                st.metric("Latency (Cache hit)", f"{r['latency']} ms",
                          delta=f"-{miss_ms - r['latency']}ms vs cold")
                st.write(r["text"])
                st.caption(f"Model: {r['model']}")

    if st.session_state.get("ll_cache_miss") and st.session_state.get("ll_cache_hit"):
        st.divider()
        st.subheader("Comparison")

        miss_ms = st.session_state.ll_cache_miss["latency"]
        hit_ms  = st.session_state.ll_cache_hit["latency"]
        speedup = miss_ms / hit_ms if hit_ms > 0 else float("inf")

        c1, c2, c3 = st.columns(3)
        c1.metric("Cold (API call)",   f"{miss_ms} ms")
        c2.metric("Cached (instant)",  f"{hit_ms} ms")
        c3.metric("Speedup",           f"{speedup:.0f}x faster")

        st.success(
            f"The LLM was **not called** for the second request. "
            f"LiteLLM returned the cached response in {hit_ms}ms at **zero cost**."
        )

        st.divider()
        st.subheader("When caching pays off most")
        st.write(
            "- **FAQ bots**: Users ask the same questions over and over\n"
            "- **Search assistants**: Common queries always cache, rare ones miss\n"
            "- **Dev/test pipelines**: Run tests without burning API quota every time\n"
            "- **Report templates**: Same prompt + different data → use semantic cache (Redis)\n\n"
            "**Production tip**: Swap `Cache(type='local')` for `Cache(type='redis', ...)` "
            "to share the cache across multiple app replicas and survive restarts."
        )
