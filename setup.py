from setuptools import setup, find_packages

setup(
    name="Findpapers",
    version="0.6.7",
    description="Findpapers is an application that helps researchers who are looking for references for their work.",
    author="Jonatas Grosman",
    author_email="jonatasgrosman@gmail.com",
    url="https://github.com/jonatasgrosman/findpapers",
    packages=find_packages(),
    install_requires=[
        "lxml==4.9.2",
        "requests==2.24.0",
        "colorama==0.4.3",
        "inquirer==2.7.0",
        "edlib==1.3.8",
        "xmltodict==0.12.0",
        "typer==0.9.0",
        'importlib-metadata==1.0; python_version < "3.8"',
    ],
    extras_require={
        "dev": [
            "pytest==5.2",
            "pytest-cov==2.10.1",
            "pytest-randomly==3.4.1",
            "Sphinx==3.2.1",
            "coverage[toml]==5.2.1",
        ]
    },
    entry_points={
        "console_scripts": [
            "findpapers=findpapers.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
)
