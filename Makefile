.PHONY: types-python validate clean install

install:
	cd python && pip install -e ..

types-python:
	@echo "Python types are hand-maintained Pydantic models in python/zeos_types/"
	@echo "JSON schemas are source of truth in schemas/"

validate:
	python3 -c "import json, glob; [json.load(open(f)) for f in glob.glob('schemas/*.schema.json')]; print('All schemas valid JSON')"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf *.egg-info python/*.egg-info
