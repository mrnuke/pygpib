""" Userspace driver for Agilent 82357A USB GPIB adapter

Not tested on 82357B (endpoint numbers are not the same).

TODO: Normally, a WRITE command is followed by a notification through an
INTERRUPT_IN transfer. This transfer should be submitted before the BULK OUT.
Because we're currently using synchronous pyusb transfers, we're limited to
running the BULK OUT before the INTERRUPT IN.
This leaves a window of opportunity where the program can be interrupted before
the notification arrives. This would leave the 82357A in a stale state.
"""
import asyncio
import concurrent.futures
import logging
import struct
import time
import usb

import pygpib.gpib as gpib


# Command codes (control transfers)
_WVALUE_ABORT_TRANSFER = 0x00a0
_WVALUE_TRANSFER_STATUS = 0x00b0

# Command codes (bulk transfers)
_CMD_WRITE = 1
_CMD_READ = 3
_CMD_WRITE_REGS = 4
_CMD_READ_REGS = 5

# TMS9914 direct-access registers
_TMS9914_IMR0 = 0
_TMS9914_IMR1 = 1
_TMS9914_ADDR_STATUS = 2
_TMS9914_AUXCR = 3
_TMS9914_BUS_STATUS = 3
_TMS9914_ADDRESS = 4
_TMS9914_SERIAL_POLL = 5
_TMS9914_PARALLEL_POLL = 6

# Other device registers
_HARDWARE_CONTROL = 0x0a
_LED_CONTROL = 0x0b
_RESET_TO_POWERUP = 0x0c
_PROTOCOL_CONTROL = 0x0d
_FAST_TALKER_T1 = 0xe

# Firmware register bits (and pieces)
_PROTOCOL_WRITE_COMPLETE_INTERRUPT_EN = 0x01
_LEDS_CONTROLLED_BY_FIRMWARE = 0x01

# Transfer flags for write transfers
_WRITE_XFER_FLAG_SEND_EOI = 0x01

# Transfer flags for read transfers
_READ_XFER_FLAG_END_ON_EOI = 0x01
_READ_XFER_FLAG_END_NO_ADDR = 0x01
_READ_XFER_FLAG_END_ON_EOS = 0x04
_READ_XFER_FLAG_SERIAL_POLL = 0x08

# TMS9914 AUXCR commands
_AUX_SOFT_RESET = 0x0
_AUX_DACR = 0x1
_AUX_RHDF = 0x2
_AUX_HLDA = 0x3
_AUX_HDFE = 0x4
_AUX_NBAF = 0x5
_AUX_FGET = 0x6
_AUX_RTL = 0x7
_AUX_SEOI = 0x8
_AUX_LON = 0x9
_AUX_TON = 0xa
_AUX_GTS = 0xb
_AUX_TCA = 0xc
_AUX_TCS = 0xd
_AUX_RPP = 0xe
_AUX_SIC = 0xf
_AUX_SRE = 0x10
_AUX_RQC = 0x11
_AUX_RLC = 0x12
_AUX_DAI = 0x13
_AUX_PTS = 0x14
_AUX_STDL = 0x15
_AUX_SHDW = 0x16
_AUX_VSTDL = 0x17
_AUX_RSV2 = 0x18

# Bits for the interrupt maskregisters
_IMR0_BOIE = 0x10
_IMR1_SRQIE = 0x02

@gpib.InterfaceManager.add_interface_driver
class Agilent82357A(gpib.Interface):
	""" pygib implementation for Agilent 82357A """
	agilent_devs = []
	def __init__(self, usb_dev):
		super().__init__()
		self.ep_in = 2 | usb.ENDPOINT_IN
		self.ep_out = 4
		self.ep_interrupt = 6 | usb.ENDPOINT_IN

		self.usb = usb_dev
		self.log = logging.getLogger(self.usb.product)

	@classmethod
	def list_adapters(cls):
		""" List the 82357A adapters found on the system

		TODO: Make sure adapters are not duplicated.
		i.e. if an existing adapter exists for a given USB device,
		don't create another one.
		"""
		devs = usb.core.find(idVendor=0x0957, idProduct=0x0107, find_all=True)
		for dev in devs:
			cls.agilent_devs.append(Agilent82357A(dev))

		return cls.agilent_devs


	def open(self, primary_address=0):
		try:
			self.usb.set_configuration()
		except usb.USBError as usb_error:
			# Can happen if 8051 is in reset
			# WARNING: Cypress reset casuses device to drop out
			# self.__cypress_fx_8051_reset()
			raise OSError from usb_error

		self.__initialize_interface(primary_address)


	def close(self):
		usb.util.dispose_resources(self.usb)


	def read_msg_from_instrument(self, gpib_address, **cfg):
		""" Read a message that the instrument is dying to send """
		num_bytes = 1024

		flags = 0
		if cfg.get('end_on_eoi', True):
			flags |= _READ_XFER_FLAG_END_ON_EOI
		if cfg.get('end_read_on_eos'):
			flags |= _READ_XFER_FLAG_END_ON_EOS
		eos = cfg.get('eos_char', 0)
		timeout_ms = int(cfg['read_timeout'] * 1000)

		hdr = struct.pack('<BBBBLB', _CMD_READ, gpib_address, 0xff,
				  flags, num_bytes, eos)
		self.usb.write(self.ep_out, hdr)

		res = self.__read(num_bytes + 1, flush_buf_on_failure=True,
				  timeout_ms=timeout_ms)
		if len(res) == 0:
			self.log.warning("ABORT: No reply to query")
			return bytes()

		reply = bytes(res[:-1])
		return reply

	async def aread_msg_from_instrument(self, gpib_address, **cfg):
		""" Read a message that the instrument is dying to send """
		num_bytes = 1024

		flags = 0
		if cfg.get('send_eoi', True):
			flags |= _READ_XFER_FLAG_END_ON_EOI
		if cfg.get('end_read_on_eos'):
			flags |= _READ_XFER_FLAG_END_ON_EOS
		eos = cfg.get('eos_char', 0)

		hdr = struct.pack('<BBBBLB', 3, gpib_address, 0xff, flags,
				  num_bytes, eos)
		x_in = self.usb.submit_read(self.ep_in, num_bytes + 1)
		x_out = self.usb.submit_write(self.ep_out, hdr)

		await x_out.result()
		try:
			res = await x_in.result()
		except usb.USBError:
			resp = self.__abort_transfer(False)
			self.log.error(f'Transfer ABORTED! Status={bytes(resp).hex()}')
			line_status = self.__gpib_line_status()
			self.log.error(f'Line status is {line_status.hex()}')
			return bytes()

		if len(res) == 0:
			self.log.warning("ABORT: No reply to query")
			return bytes()

		reply = bytes(res[:-1])
		return reply


	def write_msg_to_instrument(self, gpib_address, data, **cfg):
		flags = 0
		if cfg.get('send_eoi', True):
			flags |= _WRITE_XFER_FLAG_SEND_EOI

		if isinstance(data, str):
			data = bytes(data, 'utf-8')

		hdr = struct.pack('<BBBBL', _CMD_WRITE, gpib_address, 0xff,
				  flags, len(data))
		self.usb.write(self.ep_out, hdr + data)
		self.__wait_for_write_complete()


	async def awrite_msg_to_instrument(self, gpib_address, out, **cfg):

		hdr = struct.pack('<BBBBL', 1, gpib_address, 0xff, 0x03, len(out))
		self.usb.write(self.ep_out, hdr + bytes(out, 'utf-8'))
		#self.__wait_for_write_complete()
		await asyncio.wait_for(self.__wait_interrupt(), 1)
		#await asyncio.wait_for(self.__wait_interrupt(), 1)


	def __abort_transfer(self, flush_buffers=False):
		flush_flag = 0x01 if flush_buffers else 0x00
		resp = self.usb.ctrl_transfer(
			bmRequestType=0xc0, bRequest=4,
			wValue=_WVALUE_ABORT_TRANSFER, wIndex=flush_flag,
			data_or_wLength=2)

		if not flush_buffers:
			return resp

		try:
			leftover = self.usb.read(self.ep_in, 2)
			self.log.warning(f'Leftover buffer data: {bytes(leftover).hex()}')
		except usb.USBError:
			pass

		return resp


	def __cypress_fx_8051_reset(self):
		""" Reset the 8051 core on the Cypress FX chip. This will
		cause the devce to re-enumerate """
		self.usb.ctrl_transfer(
			bmRequestType=usb.TYPE_VENDOR, bRequest=0xa0,
			wValue=0x7f92, wIndex=0, data_or_wLength=[1])

		self.usb.ctrl_transfer(
			bmRequestType=usb.TYPE_VENDOR, bRequest=0xa0,
			wValue=0x7f92, wIndex=0, data_or_wLength=[0])


	def __initialize_interface(self, interface_primary_address):
		init_sequence = [
			# Power on adapter hardware
			(_HARDWARE_CONTROL, 0x7),
			(_LED_CONTROL, _LEDS_CONTROLLED_BY_FIRMWARE),
			# Initialize TMS9914 GPIB chip
			(_TMS9914_AUXCR, _AUX_SOFT_RESET | 0x80),
			(_TMS9914_IMR0, _IMR0_BOIE),
			(_TMS9914_IMR1, _IMR1_SRQIE),
			(_TMS9914_AUXCR, _AUX_NBAF),
			(_TMS9914_AUXCR, _AUX_HDFE),
			(_TMS9914_AUXCR, _AUX_TON),
			(_TMS9914_AUXCR, _AUX_LON),
			(_TMS9914_AUXCR, _AUX_RSV2),
			(_TMS9914_AUXCR, _AUX_DACR),
			(_TMS9914_AUXCR, _AUX_RPP),
			(_TMS9914_AUXCR, _AUX_STDL | 0x80),
			(_TMS9914_AUXCR, _AUX_VSTDL),
			(_TMS9914_ADDRESS, interface_primary_address & 0x1f),
			(_TMS9914_SERIAL_POLL, 0),
			(_TMS9914_PARALLEL_POLL, 0),
			(_TMS9914_AUXCR, _AUX_SOFT_RESET),
			(_TMS9914_AUXCR, _AUX_SRE | 0x80),
			(_TMS9914_AUXCR, _AUX_TCA),
			# Setup firmware and protocol parameters
			(_FAST_TALKER_T1, 0x27),
			(_PROTOCOL_CONTROL, _PROTOCOL_WRITE_COMPLETE_INTERRUPT_EN),
		]

		self.__abort_transfer()
		self.__write_regs([(_RESET_TO_POWERUP, 1)])
		self.__write_regs(init_sequence)
		self.__gpib_clear_interface()


	def __read_reply(self, cmd, num_extra_bytes):
		expected_reply_len = 2 + num_extra_bytes
		reply = self.__read(expected_reply_len)
		if len(reply) < expected_reply_len:
			self.log.warning('Insufficient information in reply')
			return bytes()
		if reply[0] != ~cmd & 0xff:
			self.log.warning('Reply to wrong command')
			return bytes()
		if reply[1] > 0:
			self.log.warning(f'Error {reply[1]}')
			return bytes()

		return bytes(reply[2:])


	def __read_regs(self, regs):
		out = bytes([0x05, len(regs), *regs])
		self.usb.write(self.ep_out, out)

		return self.__read_reply(0x05, len(regs))


	def __write_regs(self, kv_pairs):
		out = struct.pack('<BB', 0x04, len(kv_pairs))
		for reg, value in kv_pairs:
			out += struct.pack('<BB', reg, value)

		self.usb.write(self.ep_out, out)
		self.__read_reply(0x04, 0)


	def __read(self, data_len, flush_buf_on_failure=False, timeout_ms=100):
		try:
			res = self.usb.read(self.ep_in, data_len, timeout_ms)
		except usb.USBError:
			resp = self.__abort_transfer(flush_buf_on_failure)
			self.log.error(f'Transfer ABORTED! Status={bytes(resp).hex()}')
			line_status = self.__gpib_line_status()
			self.log.error(f'Line status is {line_status.hex()}')
			return []

		return res


	async def __wait_interrupt(self):
		while True:
			try:
				res = self.usb.read(self.ep_interrupt, 8)
				break
			except usb.USBError:
				await asyncio.sleep(0.003)

		return res


	def __wait_for_write_complete(self, timeout=0.100):
		while True:
			try:
				packet = asyncio.run(asyncio.wait_for(self.__wait_interrupt(), timeout))
			except concurrent.futures.TimeoutError:
				return

			if packet[0] & 0x02:
				return

			self.log.warning(f'Unkown packet {packet}')


	def __gpib_clear_interface(self):
		self.__write_regs([(_TMS9914_AUXCR, _AUX_SIC | 0x80)])
		time.sleep(0.001)
		self.__write_regs([(_TMS9914_AUXCR, _AUX_SIC)])

	def __gpib_line_status(self):
		return self.__read_regs([_TMS9914_ADDR_STATUS, _TMS9914_BUS_STATUS])
