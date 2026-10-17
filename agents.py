def get_llm() -> LLM:
    api_key = get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Add it to Streamlit secrets or your .env file.")
    os.environ["ANTHROPIC_API_KEY"] = api_key
    return LLM(
        model=get_secret("ANTHROPIC_MODEL", "anthropic/claude-haiku-5-5"),
        api_key=api_key,
        temperature=0.2,
    )
