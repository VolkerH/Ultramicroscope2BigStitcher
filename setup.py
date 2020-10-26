import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="um2bs",
    version="2020.10.26",
    description="Ultramicroscope2Bigstitcher",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/VolkerH/Ultramicroscope2Bigstitcher",
    author="Volker Hilsenstein",
    author_email="volker.hilsenstein@gmail.com",
    license="BSD-3",
    packages=["um2bs"],
    zip_safe=False,
    install_requires=[
        "numpy",
        "scikit-image",
        "pandas",
        "pyqt5",
        "npy2bdv",
        "tifffile",
        "h5py",
        "xmltodict",
    ],
    entry_points="""
            [console_scripts]
            um2bs_gui=um2bs.um2bs_gui:run
      """,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD-3 License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
