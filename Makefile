dashboard:
	cd client && npm install && npm run generate

test:
	coverage run -m unittest discover -s tests -v
	coverage report -m

test-publish: dashboard
	-rm -r dist
	-rm -r build
	python3 -m build
	python3 -m twine upload --repository testpypi dist/*

test-upload:
	python3 -m twine upload --repository testpypi dist/*