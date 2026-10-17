def get_llm() -> LLM:
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to Streamlit secrets or your .env file.")
    os.environ["OPENAI_API_KEY"] = api_key
    return LLM(
        model=get_secret("OPENAI_MODEL", "openai/gpt-4o-mini"),
        api_key=api_key,
        temperature=0.2,
    )
