## uv + pyenv 改造计划

1. 新增 `pyproject.toml` 与 `.python-version`，将 Python 依赖入口切换到 `uv sync`。
2. 改造启动脚本与运行时提示，移除项目主链路对 `conda` 的依赖。
3. 对齐 `Dockerfile`、`docker-compose.yml`、`electron/build-backend.sh` 的安装与构建方式。
4. 更新 `README.md`，补充新的 `uv + pyenv` 使用说明与排障文档。
