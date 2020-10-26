from setuptools import setup

setup(name='um2bs',
      version='2020.10.26',
      description='Ultramicroscope2Bigstitcher',
      url='https://github.com/VolkerH/Ultramicroscope2Bigstitcher',
      author='Volker Hilsenstein',
      author_email='volker.hilsenstein@gmail.com',
      license='BSD-3',
      packages=['um2bs'],
      zip_safe=False,
      install_requires = [
          'numpy',
          'scikit-image',
          'pandas',
          'pyqt5',
          'npy2bdv',
          'tifffile',
          'h5py',
          'xmltodict'
          ],
      entry_points='''
            [console_scripts]
            um2bs_gui=um2bs.um2bs_gui:run
      ''',
      )