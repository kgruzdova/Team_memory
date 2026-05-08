PYTHON ?= python
PYTEST ?= pytest

.PHONY: test test-unit test-e2e dev-backend dev-frontend

test:
	$(PYTEST) backend/tests -q

test-unit:
	$(PYTEST) backend/tests/test_kb.py backend/tests/test_ai.py backend/tests/test_review.py backend/tests/test_pipeline.py -q

test-e2e:
	$(PYTHON) -m backend.tests.run_kb_eval

dev-backend:
	uvicorn app:app --reload

dev-frontend:
	cd frontend && npm run dev
