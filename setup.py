from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="pisonet",
    version="7.0.0",
    author="PISONET Development Team",
    author_email="pisonet@example.com",
    description="Centralized coin-operated internet cafe management system for Orange Pi One",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Sonjii99x-Glitch/project_centralize",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Systems Administration",
        "Topic :: Internet",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "pisonet-server=server:main",
            "pisonet-client=client:main",
            "pisonet-test=test_system:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)