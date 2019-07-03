from setuptools import setup


setup(
    name="pychipset",
    version="0.1",
    packages=["chipset"],
    install_requires=["progressbar2",
                      "cffi>=1.0.0"],
    setup_requires=["cffi>=1.0.0"],
    cffi_modules=["chipset/pci/libpci_build.py:builder"],
    entry_points={
        "console_scripts": [
            "pcrportmap = chipset.pcr.port_mapper:main",
            "memory = chipset.memory.memory:main"
        ]
    }
)
