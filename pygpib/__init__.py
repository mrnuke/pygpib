""" pygpib - Take control of your GPIB adapter

This package imports available device drivers, and exposes list_adapters() for
easily and painlessly finding available GPIB bridges.
"""

from .gpib import InterfaceManager
from . import agilent_82357a

def list_adapters():
	""" An easy way to list existing GPIB interfaces """
	return InterfaceManager.list_adapters()
