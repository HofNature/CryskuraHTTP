from setuptools import setup, find_packages

setup(
    name="cryskura",
    version="1.0",
    author="HofNature",
    description="A straightforward Python package that functions as an HTTP(s) server",
    long_description="CryskuraHTTP is a lightweight, customizable HTTP(s) server implemented in Python. It supports basic HTTP(s) functionalities, including serving files and handling errors, with optional SSL support.",    
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