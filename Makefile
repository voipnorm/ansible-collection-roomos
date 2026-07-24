.PHONY: lint sanity unit build install-dev clean

lint:
	pre-commit run --all-files

sanity:
	ansible-test sanity --docker --python 3.10

unit:
	ansible-test units --docker --python 3.10

build:
	ansible-galaxy collection build --force

install-dev:
	ansible-galaxy collection install $$(ls -t voipnorm-roomos-*.tar.gz | head -1) --force

clean:
	rm -f voipnorm-roomos-*.tar.gz
