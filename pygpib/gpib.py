""" GPIB instrument control tentative interface

This module implements a tentatve, albeit not yet functional, interface for
communicating with instruments attached to a GPIB bus.
"""

class InterfaceManager():
	""" A helper class to manage Interface drivers """
	interface_drivers = []
	@classmethod
	def add_interface_driver(cls, new_driver):
		""" Register a new Interface driver.

		Each driver is used during for device discover. Drivers
		registered here will have their list of devices appear in
		'list_adapters()'. Each driver should only be registered once.
		"""
		assert issubclass(new_driver, Interface)
		cls.interface_drivers.append(new_driver)
		return new_driver

	@classmethod
	def list_adapters(cls):
		""" List adapters found by registered Interface drivers.

		This returns a list of all the adapters found on the system.
		How each device is detected is driver-specific.
		"""
		adapters = []
		for driver in cls.interface_drivers:
			adapters.extend(driver.list_adapters())

		return adapters

class Interface():
	""" Generic GPIB interface """
	def __init__(self):
		self.instruments = {}

	def open(self, primary_address=0):
		""" Open the interface as a GPIB controller in charge"""
		raise NotImplementedError

	def close(self):
		""" Release an open interface, and relinquish GPIB control """
		raise NotImplementedError

	def get_instrument(self, primary_address):
		""" Get a handle to the instrument at 'primary_address' """
		if primary_address > 0x1f:
			return None

		if primary_address not in self.instruments.keys():
			new_instrument = Instrument(self, primary_address)
			self.instruments[primary_address] = new_instrument

		return self.instruments[primary_address]

	def read_msg_from_instrument(self, gpib_address, **cfg):
		""" Read data from an instrument """
		raise NotImplementedError

	def write_msg_to_instrument(self, gpib_address, data, **cfg):
		""" Send data to the instrument """
		raise NotImplementedError


class Instrument():
	""" Text I/O stream to a GPIB instrument """
	def __init__(self, gpib_interface, primary_address):
		self.gpib_interface = gpib_interface
		self.primary_address = primary_address
		self.bus_config = {}

	def configure(self, send_eoi=True, end_read_on_eoi=True,
	              end_read_on_eos=False, eos_char='\n'):
		""" Configure the GPIB termination for this device """
		self.bus_config['send_eoi'] = send_eoi
		self.bus_config['end_read_on_eoi'] = end_read_on_eoi
		self.bus_config['end_read_on_eos'] = end_read_on_eos
		self.bus_config['eos_char'] = ord(eos_char)

	def read(self):
		""" Read data from the instrument

		Reads as much data from the device until some GPIB condition
		ends the transmission. This can be either an EOI signal, or
		receiving the EOS character. This is specified in 'configure()'.
		"""
		return self.gpib_interface.read_msg_from_instrument(
			self.primary_address, **self.bus_config)

	def write(self, out_buf):
		""" Send data to the instrument """
		self.gpib_interface.write_msg_to_instrument(
			self.primary_address, out_buf, **self.bus_config)

	def query(self, out_buf):
		""" Shortcut for write() and read() pairs """
		self.write(out_buf)
		return self.read()
