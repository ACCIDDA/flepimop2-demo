default: yamllint air ruff

[doc('Create a virtual environment using conda')]
venv:
	conda env create --prefix "venv/" --file environment.yaml

[doc('Clean the project directory by removing generated files and folders')]
clean:
	rm -rf venv/

[group('lint')]
[group('ci')]
[doc('Lint YAML files in the project')]
yamllint:
	yamllint .

[group('lint')]
[doc('Format R files in the project with air')]
air:
	air format .

[group('lint')]
[doc('Format and lint Python files in the project with ruff')]
ruff:
	ruff format .
	ruff check --fix .

[group('ci')]
[doc('Check that R files in the project are properly formatted with air')]
ci-air:
	air format --check .

[group('ci')]
[doc('Check that Python files in the project are properly formatted with ruff')]
ci-ruff:
	ruff format --check .
	ruff check .

[group('ci')]
[doc('Run all continuous integration checks')]
ci: yamllint ci-air ci-ruff
