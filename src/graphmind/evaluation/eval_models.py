from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class GroqEvalModel:
    def __init__(self, model_name: str = "llama-3.3-70b-versatile"):
        self.model_name = model_name
        self._client = None

    def _get_client(self):
        if self._client is None:
            from groq import Groq

            self._client = Groq()
        return self._client

    def generate(self, prompt: str, schema: type[BaseModel] | None = None) -> Any:
        import instructor

        client = self._get_client()
        instructor_client = instructor.from_groq(client)

        if schema is not None:
            return instructor_client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                response_model=schema,
            )

        response = client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        return response.choices[0].message.content

    def get_model_name(self) -> str:
        return self.model_name


class GeminiEvalModel:
    def __init__(self, model_name: str = "gemini-2.0-flash"):
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            import google.generativeai as genai

            self._model = genai.GenerativeModel(self.model_name)
        return self._model

    def generate(self, prompt: str, schema: type[BaseModel] | None = None) -> Any:
        model = self._get_model()

        if schema is not None:
            import instructor

            instructor_client = instructor.from_gemini(
                client=model,
                mode=instructor.Mode.GEMINI_JSON,
            )
            return instructor_client.messages.create(
                messages=[{"role": "user", "content": prompt}],
                response_model=schema,
            )

        response = model.generate_content(prompt)
        return response.text

    def get_model_name(self) -> str:
        return self.model_name
