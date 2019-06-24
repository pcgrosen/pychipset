from setuptools import setup


setup(
    name="pychipset",
    version="0.1",
    packages=["chipset"],
    install_requires=["progressbar2"],
    entry_points={
        "console_scripts": [
            "pcrportmap = chipset.pcr.port_mapper:main",
            "memory = chipset.memory.memory:main"
        ]
    }
)
