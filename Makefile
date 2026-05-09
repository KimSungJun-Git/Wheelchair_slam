.PHONY: rag-rebuild analyze

rag-rebuild:
	python3 tools/extract_context.py
	python3 tools/build_vectordb.py

analyze:
	python3 tools/analyze_log.py $(LOG)
analyze-latest:
	@LATEST=$$(ls -t driving_data/*.json | head -1); \
	echo "📄 Analyzing: $$LATEST"; \
	python3 tools/analyze_log.py "$$LATEST"

analyze-all:
	@for f in driving_data/*.json; do \
		echo ""; \
		echo "===================================="; \
		echo "📄 Analyzing: $$f"; \
		echo "===================================="; \
		python3 tools/analyze_log.py "$$f"; \
	done
