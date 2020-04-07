""" GPIB instrument control tentative interface

This module implements a tentatve, albeit not yet functional, interface for
communicating with instruments attached to a GPIB bus.
"""
def list_adapters():
	""" An easy way to list existing GPIB interfaces """
	return []

class Interface():
	""" Generic GPIB interface """

	def open(self, primary_address=0):
		""" Open the interface as a GPIB controller in charge"""
		raise NotImplementedError

	def close(self):
		""" Release an open interface, and relinquish GPIB control """
		raise NotImplementedError

	def get_instrument(self, primary_address):
		""" Get a handle to the instrument at 'primary_address' """
		raise NotImplementedError


class Instrument():
	""" Text I/O stream to a GPIB instrument """
	def __init__(self, gpib_interface):
		self.gpib_interface = gpib_interface

	def configure(self, send_eoi=True, end_read_on_eoi=True,
	              end_read_on_eos=False, eos_char='\n'):
		""" Configure the GPIB termination for this device """
		raise NotImplementedError

	def read(self, num=None):
		""" Read data from the instrument

		Reads as much data from the device until some GPIB condition
		ends the transmission. This can be either an EOI signal, or
		receiving the EOS character. This is specified in 'configure()'.
		"""
		raise NotImplementedError

	def write(self, out_buf):
		""" Send data to the instrument """
		raise NotImplementedError

	def query(self, out_buf):
		""" Shortcut for write() and read() pairs """
		self.write(out_buf)
		return self.read()
