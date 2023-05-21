from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in tekcom_pagos/__init__.py
from tekcom_pagos import __version__ as version

setup(
	name="tekcom_pagos",
	version=version,
	description="Sistema de Gestion de Gastos de Viaje y Solicitudes de Pagos",
	author="Cuatrocubos Soluciones",
	author_email="jgiron@cuatrocubos.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
