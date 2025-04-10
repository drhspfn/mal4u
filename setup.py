from setuptools import setup, find_packages

setup(
    name='mal4u', 
    version='0.1.2', 
    packages=find_packages(),  
    install_requires=[  
        "aiohttp",
        "pydantic",
        "beautifulsoup4"
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/drhspfn/mal4u',
    author='drhspfn',
    author_email='jenya.gsta@gmail.com',
    license='MIT',
)
