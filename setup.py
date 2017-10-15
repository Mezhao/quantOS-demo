from setuptools import setup, find_packages
import codecs
import os


def read(fname):
    return codecs.open(os.path.join(os.path.dirname(__file__), fname)).read()

try:
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst')
except (IOError, ImportError):
    long_description = ''



setup(
    name='quantos',
    version='0.2',
    description='A opensource pathform for Quant inverstement with Python.',
    long_description = long_description,
    install_requires=[
						'pytest',
						'Jinja2',
						'matplotlib',
						'msgpack_python',
						'nose_parameterized',
						'pypandoc',
						'seaborn',
						'setuptools',
						'six',
						'xarray',
						'pyzmq',
						'msgpack_python',
						'python-snappy',
    ],
    license='Apache 2',
    classifiers=[
    'Programming Language :: Python :: 2.7',
    ],
    packages=find_packages(),
    package_data={'': ['*.json', '*.css', '*.html']},
    )