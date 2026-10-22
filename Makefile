# Upload credentials live in ./.pypirc (gitignored, never commit it).
TWINE_UPLOAD = python3 -m twine upload --config-file .pypirc

dashboard:
	cd client && npm install && npm run generate

test:
	coverage run -m unittest discover -s tests -v
	coverage report -m

package: dashboard
	-rm -r dist
	-rm -r build
	python3 -m build

test-publish: package
	$(TWINE_UPLOAD) --repository testpypi dist/*

test-upload:
	$(TWINE_UPLOAD) --repository testpypi dist/*

publish: package
	$(TWINE_UPLOAD) --repository pypi dist/*

upload:
	$(TWINE_UPLOAD) --repository pypi dist/*
