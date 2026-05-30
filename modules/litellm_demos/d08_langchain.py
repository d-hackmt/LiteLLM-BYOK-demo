import time
import streamlit as st
from modules.litellm_utils import (
    show_diagram, require_keys, get_primary_model, get_fallback_model,
    get_api_key_for_model, available_models,
)
from modules.litellm_diagrams import LANGCHAIN_DIAGRAM


def render():
    primary  = get_primary_model()
    fallback = get_fallback_model()

    st.title("LangChain Integration")
    st.write(
        "LiteLLM integrates directly into LangChain via `ChatLiteLLM`. "
        "Swap `ChatOpenAI` for `ChatLiteLLM` and your entire chain — prompts, parsers, agents — "
        "immediately gains access to every provider LiteLLM supports, plus fallbacks and cost tracking."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(LANGCHAIN_DIAGRAM, height=280)
        st.caption("ChatLiteLLM is a drop-in replacement for any LangChain chat model. All gateway features work transparently.")

    with st.expander("Installation"):
        st.code("pip install langchain-litellm", language="bash")

    with st.expander("The code — basic chain"):
        st.code(f"""from langchain_litellm import ChatLiteLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

llm = ChatLiteLLM(
    model="{primary}",
    api_key="your-api-key",
    temperature=0.3,
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful AI tutor. Be concise."),
    ("user", "{{question}}")
])

chain = prompt | llm | StrOutputParser()
answer = chain.invoke({{"question": "What is an LLM Gateway?"}})""", language="python")

    with st.expander("The code — chain with fallbacks"):
        st.code(f"""from langchain_litellm import ChatLiteLLM

primary  = ChatLiteLLM(model="{primary}",  api_key=primary_key)
fallback = ChatLiteLLM(model="{fallback}", api_key=fallback_key)

# LangChain's .with_fallbacks() — if primary raises any exception, use fallback
robust_llm = primary.with_fallbacks([fallback])

chain = prompt | robust_llm | StrOutputParser()
# Works even if primary model is down or rate-limited""", language="python")

    st.divider()

    # Check if langchain-litellm is installed
    try:
        from langchain_litellm import ChatLiteLLM
        _lc_available = True
    except ImportError:
        _lc_available = False

    if not _lc_available:
        st.error(
            "`langchain-litellm` is not installed. Run:\n\n"
            "```\npip install langchain-litellm\n```\n\n"
            "then restart the app."
        )
        return

    require_keys()

    api_key = get_api_key_for_model(primary)
    if not api_key:
        st.warning(f"No API key configured for `{primary}`. Change the primary model in the sidebar.")
        return

    tab1, tab2, tab3 = st.tabs(["Basic Chain", "Chain with Fallbacks", "JSON Output"])

    # ── Tab 1: Basic chain ────────────────────────────────────────────────────
    with tab1:
        st.subheader("Basic LangChain + LiteLLM chain")
        system_msg = st.text_input("System message:", value="You are a helpful AI tutor. Be concise.", key="ll_lc_sys1")
        user_q     = st.text_input("Question:", value="What is an LLM Gateway in 3 bullet points?", key="ll_lc_q1")

        if st.button("Run Chain", key="ll_lc_btn1", type="primary"):
            try:
                from langchain_litellm import ChatLiteLLM
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_core.output_parsers import StrOutputParser
                import litellm
                litellm.suppress_debug_info = True

                llm = ChatLiteLLM(model=primary, api_key=api_key, temperature=0.3, max_tokens=300)
                prompt_tmpl = ChatPromptTemplate.from_messages([
                    ("system", system_msg),
                    ("user", "{question}")
                ])
                chain = prompt_tmpl | llm | StrOutputParser()

                with st.spinner("Running chain..."):
                    start = time.time()
                    answer = chain.invoke({"question": user_q})
                    elapsed = int((time.time() - start) * 1000)

                st.success(f"Done in {elapsed}ms")
                st.write(answer)
                st.caption(f"Model: `{primary}`")
            except Exception as e:
                st.error(f"Error: {e}")

    # ── Tab 2: Chain with fallbacks ───────────────────────────────────────────
    with tab2:
        st.subheader("Chain with automatic fallbacks")
        avail = available_models()
        others = [m for m in avail if m != primary]

        if not others:
            st.warning("Configure a second provider key to see cross-provider fallbacks.")
        else:
            fb_model = others[0]
            fb_key   = get_api_key_for_model(fb_model)
            st.info(f"Primary: `{primary}` → Fallback: `{fb_model}`")

            simulate_fail = st.toggle("Simulate primary failure", value=True, key="ll_lc_sim")
            if simulate_fail:
                st.warning("Primary will use an invalid model name — LangChain will activate `.with_fallbacks()`.")

            user_q2 = st.text_input("Question:", value="What are the top 3 benefits of an LLM Gateway?", key="ll_lc_q2")

            if st.button("Run with Fallbacks", key="ll_lc_btn2", type="primary"):
                try:
                    from langchain_litellm import ChatLiteLLM
                    from langchain_core.prompts import ChatPromptTemplate
                    from langchain_core.output_parsers import StrOutputParser
                    import litellm
                    litellm.suppress_debug_info = True

                    bad_model = "groq/nonexistent-llm-xyz"
                    primary_llm  = ChatLiteLLM(
                        model=bad_model if simulate_fail else primary,
                        api_key=api_key, max_tokens=300
                    )
                    fallback_llm = ChatLiteLLM(model=fb_model, api_key=fb_key, max_tokens=300)
                    robust_llm   = primary_llm.with_fallbacks([fallback_llm])

                    prompt_tmpl = ChatPromptTemplate.from_messages([
                        ("system", "You are a concise AI assistant."),
                        ("user", "{question}")
                    ])
                    chain = prompt_tmpl | robust_llm | StrOutputParser()

                    with st.spinner("Running chain with fallback config..."):
                        start = time.time()
                        answer = chain.invoke({"question": user_q2})
                        elapsed = int((time.time() - start) * 1000)

                    if simulate_fail:
                        st.success(f"Primary failed → Fallback `{fb_model}` answered in {elapsed}ms")
                    else:
                        st.success(f"Primary `{primary}` answered in {elapsed}ms")
                    st.write(answer)
                except Exception as e:
                    st.error(f"Error: {e}")

    # ── Tab 3: JSON output ────────────────────────────────────────────────────
    with tab3:
        st.subheader("Structured JSON output via LangChain")
        st.write("Combine LiteLLM's routing with LangChain's output parsers to get structured JSON back.")

        user_q3 = st.text_input("Topic:", value="LLM Gateway benefits", key="ll_lc_q3")

        if st.button("Run JSON Chain", key="ll_lc_btn3", type="primary"):
            try:
                from langchain_litellm import ChatLiteLLM
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_core.output_parsers import JsonOutputParser
                import litellm, json
                litellm.suppress_debug_info = True

                llm = ChatLiteLLM(model=primary, api_key=api_key, temperature=0.2, max_tokens=300)
                prompt_tmpl = ChatPromptTemplate.from_messages([
                    ("system", 'Respond ONLY with valid JSON. Format: {{"items": ["point1", "point2", "point3"]}}'),
                    ("user", "List 3 key points about: {topic}")
                ])
                chain = prompt_tmpl | llm | JsonOutputParser()

                with st.spinner("Running JSON chain..."):
                    start = time.time()
                    result = chain.invoke({"topic": user_q3})
                    elapsed = int((time.time() - start) * 1000)

                st.success(f"Done in {elapsed}ms — parsed JSON:")
                st.json(result)
                st.caption(f"Model: `{primary}`")
            except Exception as e:
                st.error(f"Error: {e}")
