from setuptools import setup, find_packages

from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()
long_description = long_description.replace("README: [English](README.md) | [中文](README_zh.md)", "")

setup(
    name="cryskura",
    version="1.0-alpha",
    author="HofNature",
    description="A straightforward Python package that functions as an HTTP(s) server",
    long_description=long_description,
    long_description_content_type='text/markdown',    
    packages=find_packages(),
    install_requires=["psutil"],
    license="MIT",
    keywords=["http", "https", "server", "web", "http server", "https server"],
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "cryskura=cryskura.Entry:main"
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ]
)