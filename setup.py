from setuptools import setup


setup(
    name="pypcr",
    version="0.1",
    packages=["pcr"],
    install_requires=["progressbar2"],
    entry_points={
        "console_scripts": [
            "pcrportmap = pcr.port_mapper:main"
        ]
    }
)
