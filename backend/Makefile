.PHONY: lint test coverage check restore-db help

lint:  ## 代码检查：ruff + black + mypy
	bash run_checks.sh

test:  ## 运行测试
	bash run_tests.sh

coverage:  ## 运行测试并输出覆盖率
	bash run_tests.sh --cov=app --cov-report=term-missing --cov-report=html --cov-report=xml

check: lint test  ## 完整门禁：lint → test

restore-db:  ## 从备份文件恢复数据库，用法：make restore-db BACKUP=./backups/xxx
	@if [ -z "$(BACKUP)" ]; then \
		echo "用法：make restore-db BACKUP=./backups/xxx"; \
		exit 1; \
	fi
	venv/bin/python scripts/restore_database.py "$(BACKUP)"

help:  ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-10s\033[0m %s\n", $$1, $$2}'
