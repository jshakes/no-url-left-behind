#!/usr/bin/env python3
"""Setup script for no-url-left-behind package."""

from setuptools import setup, find_packages
import os

# Read the requirements from requirements.txt
with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

# Read the README file for long description
readme_path = os.path.join(os.path.dirname(__file__), "README.md")
if os.path.exists(readme_path):
    with open(readme_path, "r", encoding="utf-8") as f:
        long_description = f.read()
else:
    long_description = "A tool for detecting 404 errors during website migrations by checking URLs from sitemap.xml files."

setup(
    name="nulb",
    version="1.0.1",
    author="James Shakespeare",
    author_email="j@jshakespeare.com",
    description="A tool for detecting 404 errors during website migrations by checking URLs from sitemap.xml files",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jshakes/no-url-left-behind",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Testing",
        "Topic :: System :: Systems Administration",
    ],
    python_requires=">=3.7",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "nulb=nulb.main:main",
        ],
    },
    keywords="url migration sitemap 404 website migration checker",
    project_urls={
        "Bug Reports": "https://github.com/jshakes/no-url-left-behind/issues",
        "Source": "https://github.com/jshakes/no-url-left-behind",
    },
)