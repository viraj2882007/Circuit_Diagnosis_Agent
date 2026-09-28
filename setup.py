from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="mcu-diagnostic-agent",
    version="1.0.0",
    author="MCU Diagnostic Agent Team",
    description="Automated MCU peripheral diagnostic tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/viraj2882007/Circuit_Diagnosis_Agent",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    package_data={
        "": ["../config/*.yaml", "../zephyr_app/**/*"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Embedded Systems",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
    install_requires=[
        "pyyaml>=6.0",
        "pyserial>=3.5",
        "pyocd>=0.32.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-asyncio>=0.21",
            "pytest-cov>=4.0",
            "black>=23.0",
            "ruff>=0.1.0",
            "mypy>=1.0",
            "pre-commit>=3.0",
            "rich>=13.0",
            "tqdm>=4.65",
        ],
        "viz": [
            "matplotlib>=3.7",
            "plotly>=5.15",
        ],
    },
    entry_points={
        "console_scripts": [
            "mcu-diag=mcu_diagnostic_agent.orchestrator.agent:main",
        ],
    },
)