from setuptools import setup, find_packages

from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()
with open(path.join(this_directory, 'README_zh.md'), encoding='utf-8') as f:
    long_description_zh = f.read()
long_description = long_description.replace("README: [English](README.md) | [中文](README_zh.md)", "")
long_description = long_description.replace("CryskuraHTTP.png","https://github.com/HofNature/CryskuraHTTP/raw/main/CryskuraHTTP.png")
long_description_zh = long_description_zh.replace("帮助文档: [English](README.md) | [中文](README_zh.md)", "")
long_description_zh = long_description_zh.replace("CryskuraHTTP.png","https://github.com/HofNature/CryskuraHTTP/raw/main/CryskuraHTTP.png")
long_description += long_description_zh

setup(
    name="cryskura",
    version="1.0-beta.11",
    author="HofNature",
    description="A straightforward Python package that functions as an HTTP(s) server",
    long_description=long_description,
    long_description_content_type='text/markdown',    
    packages=find_packages(),
    install_requires=["psutil"],
    extras_require={
        'upnp': ["upnpclient"]
    },
    python_requires=">=3.7",
    url="https://github.com/HofNature/CryskuraHTTP",
    license="MIT",
    keywords=["http", "https", "server", "web", "http server", "https server"],
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "cryskura=cryskura.Entry:main"
        ]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Operating System :: OS Independent",
    ]
)