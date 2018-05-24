init:
	pip install -r requirements.txt

test:
	nosetests tests

update:
	pip freeze --local | grep -v '^\-e' | cut -d = -f 1  | xargs -n1 pip install -U ; pip freeze --local > requirements.txt
