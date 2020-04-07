===========================================
pygpib - Take control of your GPIB adapters
===========================================

The pygpib module provides Python access to GPIB adapters. It provides access
to GPIB instruments through an interface that hides the ugly details of GPIB.


Introduction
============

In general, USB-GPIB adapters require special drivers provided by the
manucaturer, or linux-gpib. Vendor drivers are usually limited to one operating
system. linux-gpib requires out-of-tree kernel modules, making it cumbersome
to set up and update with new kernels.

pygpib is designed to allow the use of USB-GPIB adapters without the need for
special drivers or kernel modules. The interface is centered around read() and
write() calls with minimal GPIB-centric configuration and housekeeping.