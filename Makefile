.PHONY: retro-check install-hooks ci-retro

retro-check:
	./scripts/check_retro_css.sh

install-hooks:
	./scripts/install_git_hook.sh

ci-retro:
	bash -n scripts/check_retro_css.sh
	bash -n scripts/install_git_hook.sh
	shellcheck scripts/check_retro_css.sh scripts/install_git_hook.sh
	./scripts/check_retro_css.sh
