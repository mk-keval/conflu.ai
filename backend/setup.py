from setuptools import find_packages, setup

setup(
    name="conflu-ai",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.0,<3",
        "pydantic-settings[yaml]>=2.0,<3",
        "duckdb>=0.10.0",
        "vectorbt>=0.40.0",
        "pandas-ta>=0.3.14",
        "pandas>=2.0,<3",
        "structlog>=24.1,<25",
        "numpy>=1.26",
        "pyyaml>=6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0",
            "pytest-asyncio>=0.23",
            "hypothesis>=6.0",
            "mypy>=1.8",
            "ruff>=0.3",
            "pre-commit>=3.6",
        ],
        "test": [
            "pytest>=8.0",
            "pytest-asyncio>=0.23",
            "hypothesis>=6.0",
        ],
    },
)
