from setuptools import setup, find_packages

setup(
    name='self_evolution_experiment',
    version='0.6',
    packages=find_packages(),
    install_requires=[
        'duckdb>=0.10.0; python_version < "3.13"',
        'duckdb>=1.0.0; python_version >= "3.13"',
        'openai', 
        'python-dotenv'
    ],
    python_requires='>=3.8',
    extras_require={
        'test': [
            'pytest',
            'pytest-cov',
            'pytest-mock',
        ],
    },
)
