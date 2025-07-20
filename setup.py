from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="audial-sdk",
    version="1.0.4",
    author="Audial Team",
    author_email="support@audial.io",
    description="Python SDK for the Audial audio processing API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/audial/audial-sdk",  # Update this to your actual GitHub URL
    project_urls={
        "Bug Tracker": "https://github.com/audial/audial-sdk/issues",
        "Documentation": "https://github.com/audial/audial-sdk/blob/main/API_DOCUMENTATION.md",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",  # Add this
        "Intended Audience :: Developers",  # Add this
        "Topic :: Multimedia :: Sound/Audio",  # Add this if relevant
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "audial=audial.cli.commands:cli",
        ],
    },
)