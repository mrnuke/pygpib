import setuptools
from distutils.core import setup

with open("README.rst", "r") as readme:
	long_description = readme.read()

setup (
	name = 'pygpib',
	packages = ['pygpib'],
	version = '0.0.0',
	license = 'GPLv3',
	description = 'Take control of your GPIB adapters!',
	long_description=long_description,
	long_description_content_type="text/x-rst",
	author = 'Alexandru Gagniuc',
	url = 'https://github.com/mrnuke/pygpib',
	keywords = ['GPIB', 'USB'],
	install_requires = [ 'pyusb' ],
	classifiers = [
		'Development Status :: 1 - Planning',
		'Intended Audience :: Developers',
		'Intended Audience :: Science/Research',
		'Topic :: Scientific/Engineering',
		'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
		'Programming Language :: Python :: 3.7',
	],
	python_requires = '>=3.7',
)
