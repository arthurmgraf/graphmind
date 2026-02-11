"""Load testing scenarios for GraphMind API."""
from locust import HttpUser, task, between

class GraphMindUser(HttpUser):
    wait_time = between(1, 3)
    host = "http://localhost:8000"

    @task(15)
    def health_check(self):
        self.client.get("/api/v1/health")

    @task(80)
    def query_simple(self):
        self.client.post("/api/v1/query", json={
            "question": "What is machine learning?",
            "engine": "langgraph",
        })

    @task(5)
    def ingest_document(self):
        self.client.post("/api/v1/ingest", json={
            "content": "Machine learning is a subset of artificial intelligence.",
            "filename": "test_doc.md",
            "doc_type": "markdown",
        })
