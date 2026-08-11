# Quality gates for urmet-ha. Three areas that do not trip over each other, each
# with its own interpreter and its own config, so the gateway .venv (which has no
# Home Assistant) never runs the integration tests, and no area's ruff or mypy
# config is applied to another area's code:
#
#   gateway      .venv      vendored SDK + the gateway package; root pyproject.toml
#   integration  .venv-ha   Home Assistant + the test harness; qa/integration-*
#   card         card/      npm: tsc --noEmit, vitest, and the rollup bundle
#
# `make build` provisions all three. `make check` runs all three and fails if any
# area fails. The per-area targets (gateway, integration, card) run one area on
# its own; the fine-grained lint/typecheck/test targets run one step of one area.

# --- interpreters and tools -------------------------------------------------
PY      := .venv/bin/python
RUFF    := .venv/bin/ruff
MYPY    := .venv/bin/mypy
HAPY    := .venv-ha/bin/python
HARUFF  := .venv-ha/bin/ruff
HAMYPY  := .venv-ha/bin/mypy

# --- sources ----------------------------------------------------------------
GATEWAY  := addon/urmet-gateway
GW_PKG   := addon/urmet-gateway/urmet_gateway
# The shared root test infrastructure (conftest, isolation guard, skeleton) uses
# the gateway packages, so it is linted and run in the gateway area, once.
GW_SRC   := addon/urmet-gateway tests/gateway tests/test_skeleton.py tests/conftest.py tests/isolation.py
GW_TESTS := tests/gateway tests/test_skeleton.py
INT_PKG  := custom_components/urmet
INT_SRC  := custom_components/urmet tests/integration
INT_RUFF := qa/integration-ruff.toml
INT_MYPY := qa/integration-mypy.toml

.PHONY: build check clean \
	build-gateway build-integration build-card \
	gateway lint-gateway typecheck-gateway test-gateway \
	integration lint-integration typecheck-integration test-integration \
	card typecheck-card test-card build-card-bundle

# =============================== provisioning ===============================
build: build-gateway build-integration build-card

.venv:
	python3.12 -m venv .venv

build-gateway: .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e $(GATEWAY)
	$(PY) -m pip install ruff mypy pytest pytest-asyncio

.venv-ha:
	python3.12 -m venv .venv-ha

build-integration: .venv-ha
	$(HAPY) -m pip install --upgrade pip
	$(HAPY) -m pip install -r requirements-test.txt
	$(HAPY) -m pip install ruff mypy

build-card:
	cd card && npm ci

# ================================= gateway ==================================
lint-gateway:
	$(RUFF) check $(GW_SRC)
	$(RUFF) format --check $(GW_SRC)

typecheck-gateway:
	$(MYPY) $(GW_PKG)

test-gateway:
	$(PY) -m pytest $(GW_TESTS)

gateway: lint-gateway typecheck-gateway test-gateway

# =============================== integration ================================
lint-integration:
	$(HARUFF) check --config $(INT_RUFF) $(INT_SRC)
	$(HARUFF) format --check --config $(INT_RUFF) $(INT_SRC)

typecheck-integration:
	$(HAMYPY) --config-file $(INT_MYPY) $(INT_PKG)

test-integration:
	$(HAPY) -m pytest tests/integration

integration: lint-integration typecheck-integration test-integration

# ================================== card ====================================
typecheck-card:
	cd card && npm run typecheck

test-card:
	cd card && npm test

build-card-bundle:
	cd card && npm run build

card: typecheck-card test-card build-card-bundle

# =============================== unified gate ===============================
check: gateway integration card

clean:
	rm -rf .venv .venv-ha .mypy_cache .ruff_cache .pytest_cache card/node_modules
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
