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
						'pytest==3.0.7',
						'Jinja2==2.9.6',
						'matplotlib==2.0.2',
						'msgpack_python==0.4.8',
						'nose_parameterized==0.6.0',
						'pypandoc==1.4',
						'seaborn==0.8.1',
						'setuptools==36.6.0',
						'six==1.11.0',
						'xarray==0.9.6',
						'pyzmq==17.0.0b1',
						'msgpack_python==0.4.8',
						'python-snappy==0.5.1',
    ],
    license='Apache 2',
    classifiers=[
    'Programming Language :: Python :: 2.7',
    ],
    packages=find_packages(),
    package_data={'': ['*.json', '*.css', '*.html']},
    )