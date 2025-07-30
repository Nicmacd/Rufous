"""
Setup script for Rufous MCP Server
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="rufous-mcp",
    version="0.1.0",
    author="Rufous Financial Health Team",
    author_email="team@rufous.dev",
    description="A Model Context Protocol server for PDF statement analysis and financial health tracking",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/rufous",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business :: Financial",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "rufous-mcp=rufous_mcp.minimal_server:main",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/your-org/rufous/issues",
        "Source": "https://github.com/your-org/rufous",
        "Documentation": "https://github.com/your-org/rufous/wiki",
    },
    keywords="mcp financial health pdf statements banking canada claude ai",
    include_package_data=True,
    zip_safe=False,
) 