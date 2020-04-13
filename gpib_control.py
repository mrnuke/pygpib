""" Example implementation and control of a GPIB adapter
"""
import asyncio
import os
import pygpib as gpib
import sys
import time

sys.path.insert(0, os.path.abspath("/home/mrnuke/src/pyusb"))
#import usb


async def amain():
	print('PyGPIB HP-3457A test program')

	dapts = gpib.list_adapters()
	if len(dapts) == 0:
		print('No GPIB adapter found')
		raise OSError(os.ST_NODEV)

	interface = dapts[0]

	interface.open(primary_address=10)

	instrument = interface.get_instrument(primary_address=22)
	instrument.configure(end_read_on_eos=True, eos_char='\n')

	await interface.awrite_msg_to_instrument(22, 'ID?')

	resp = await interface.aread_msg_from_instrument(22,  end_read_on_eos=True, eos='\n')
	print(resp)
	resp = resp.decode('utf-8').rstrip('\r\n')
	print(resp)


def test_repeated_reads(num_reads=20):
	print('PyGPIB Repeated reads test')

	adapters = gpib.list_adapters()
	if len(adapters) == 0:
		print('No GPIB adapter found')
		sys.exit(os.ST_NODEV)

	interface = adapters[0]
	interface.open(primary_address=10)

	num_runs = 0
	num_fails = 0
	while num_runs < num_reads:
		instrument = interface.get_instrument(primary_address=22)
		instrument.configure(end_read_on_eos=True, eos_char='\n', read_timeout=2)

		resp = instrument.write('ID?')
		resp = instrument.read()
		resp = resp.decode('utf-8').rstrip('\r\n')
		if len(resp) > 0:
			print(resp, flush=True)
		else:
			num_fails += 1

		num_runs += 1
		if num_runs % 10 == 0:
			print(f'Failed {num_fails}/{num_runs}')

	interface.close()


def main():
	print('PyGPIB HP-3457A test program')

	dapts = gpib.list_adapters()
	if len(dapts) == 0:
		raise OSError(os.ST_NODEV)

	interface = dapts[0]

	first = True
	num_runs = 0
	num_fails = 0


	interface.open(primary_address=10)

	while True:
		instrument = interface.get_instrument(primary_address=22)
		instrument.configure(end_read_on_eos=True, eos_char='\n')

		resp = instrument.write('ID?')
		resp = instrument.read()
		resp = resp.decode('utf-8').rstrip('\r\n')
		print(resp, flush=True)
		if len(resp) == 0:
			num_fails += 1
		#break
		#interface.close()
		num_runs += 1
		#time.sleep(5)
		first = False

		if num_runs >= 1:
			break

		if num_runs % 10 == 0:
			print(f'Failed {num_fails}/{num_runs}')


	print(f'Failed {num_fails}/{num_runs}')


if __name__ == '__main__':
	do_async = 0
	test_repeated_reads()
	sys.exit(0)

	if do_async:
		asyncio.run(amain())
	else:
		main()
