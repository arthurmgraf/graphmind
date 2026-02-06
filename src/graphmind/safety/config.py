from langchain_groq import ChatGroq
from nemoguardrails.llm.providers import register_llm_provider

register_llm_provider("groq", ChatGroq)
