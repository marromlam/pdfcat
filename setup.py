#!/usr/bin/env python3

from setuptools import find_packages, setup

setup(
    name="pdfcat",
    version="0.0.1",
    description="Graphical PDF reader",
    author="Marcos Romero Lamas",
    # TODO: replace with real email
    author_email="<MAIL>",
    url="https://github.com/marromlam/pdfcat",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "PyMuPDF",
        "Pillow",
        "pyperclip",
        "pdfrw",
        "pagelabels",
        "pybtex",
        "pynvim",
        "roman",
        "rich",
    ],
    entry_points={"console_scripts": ["pdfcat=pdfcat.app:run"]},
)
