ROGUE_DIR := rogue-collection
DOCKER_IMAGE := rogue-bench

.PHONY: help install build clean docker-build docker-run lint test

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

build: ## Build rogue-collection in 
	$(MAKE) -C $(ROGUE_DIR) headless

clean: ## Clean rogue-collection build artifacts
	$(MAKE) -C $(ROGUE_DIR) distclean

docker-build: ## Build the Docker image
	docker build -t $(DOCKER_IMAGE) .

docker-clean: ## Stop container and remove rogue-bench image
	-docker stop $$(docker ps -q --filter ancestor=$(DOCKER_IMAGE)) 2>/dev/null
	-docker rmi $(DOCKER_IMAGE) 2>/dev/null

lint: ## Run linters (ruff, ty)
	uv run ruff check .
	uv run ty check

test: ## Run tests
	uv run pytest