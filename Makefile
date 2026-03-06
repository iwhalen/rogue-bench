ROGUE_DIR := rogue-collection

.PHONY: help install build-rogue run-rogue clean-rogue distclean-rogue lint test

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install system dependencies (Qt5, build tools)
	sudo apt-get update
	sudo apt-get install -y \
		build-essential \
		qtbase5-dev \
		qtdeclarative5-dev \
		qtmultimedia5-dev \
		qt5-qmake \
		qml-module-qtquick2 \
		qml-module-qtquick-controls \
		qml-module-qtquick-controls2 \
		qml-module-qtquick-layouts \
		qml-module-qtquick-dialogs \
		qml-module-qtquick-window2 \
		qml-module-qtmultimedia

build-rogue: ## Build rogue-collection in 
	$(MAKE) -C $(ROGUE_DIR) headless

build-rogue-gui: ## Build rogue-collection with GUI (requires Qt5)
	$(MAKE) -C $(ROGUE_DIR)

run-rogue: ## Run rogue-collection in the GUI
	$(MAKE) -C $(ROGUE_DIR) run

clean-rogue: ## Clean rogue-collection build artifacts
	$(MAKE) -C $(ROGUE_DIR) distclean

lint: ## Run linters (ruff, ty)
	uv run ruff check .
	uv run ty check

test: ## Run tests
	uv run pytest