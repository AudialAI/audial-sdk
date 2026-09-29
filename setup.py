from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Runtime dependencies are listed here explicitly rather than read from requirements.txt:
# that file also carries the development tools, and anything in install_requires is installed
# into every consumer's environment (including `uvx`/`pipx` installs of downstream packages).
INSTALL_REQUIRES = [
    "requests>=2.25.0",
    "tqdm>=4.62.0",
    "python-dotenv>=0.19.0",
    "click>=8.0.0",
    'importlib-metadata>=1.0.0; python_version < "3.8"',
]

DEV_REQUIRES = [
    "pytest>=6.0.0",
    "pytest-cov>=2.12.0",
    "pytest-mock>=3.6.0",
    "black>=21.5b2",
    "flake8>=3.9.0",
]

setup(
    name="audial-sdk",
    version="1.2.3",
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
    install_requires=INSTALL_REQUIRES,
    extras_require={"dev": DEV_REQUIRES},
    entry_points={
        "console_scripts": [
            "audial=audial.cli.commands:cli",
        ],
    },
)