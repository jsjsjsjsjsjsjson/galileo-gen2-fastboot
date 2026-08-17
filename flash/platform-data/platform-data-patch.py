#!/usr/bin/env python3

# Copyright (c) 2013-2015 Intel Corporation.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in
# the documentation and/or other materials provided with the
# distribution.
# * Neither the name of Intel Corporation nor the names of its
# contributors may be used to endorse or promote products derived
# from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

'''
Tool for patching Flash.bin with Platform Data Binary
Krzysztof.M.Sywula@intel.com, john.toomey@intel.com,
marc.herbert@intel.com
'''

from __future__ import print_function

import sys
import struct
import binascii
import os
import shutil
from optparse import OptionParser

try:
    from collections import OrderedDict
    DICTIONARY = OrderedDict
except ImportError:
    DICTIONARY = dict

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

VERSION = '0.2'
ADDRESS_4G = 0x100000000
PLATFORM_DATA_MAGIC = b'PDAT'
FLASH_MISSING_PDAT_BIN = "Flash-missingPDAT.bin"

def parse_input():
    '''Function to parse all of command line params'''

    parser = OptionParser(usage="%prog", version="%prog " + VERSION)
    parser.add_option("-i", "--original-image", dest="original_image",
                      help="input flash image [default: %default]",
                      default=FLASH_MISSING_PDAT_BIN, action="store",
                      type="string")
    parser.add_option("-p", "--platform-config", dest="input_file",
                      help="configuration (INI) file [default: %default]",
                      action="store", type="string",
                      default="platform-data.ini")
    parser.add_option("-n", "--name", dest="modified_image",
                      help="output flash image [default: %default]",
                      action="store", type="string",
                      default="Flash+PlatformData.bin")
    parser.add_option("-u", "--undefined-order", dest="undefined_order",
                      help="By default, items are put in the same order as " +
                      "they come in the config file. However ordering " +
                      "requires python 2.7 or above.",
                      action="store_true", default=False)
    parser.add_option("-a", "--pdat-address", dest="pdat_address",
                      help="address of platform data in image [default: %default]",
                      action="store", type="int", default=0xFFF10000)


    opts = parser.parse_args()[0]

    mandatory = ["input_file", "original_image"]
    if DICTIONARY == dict:
        mandatory.append("undefined_order")

    for opt in mandatory:
        if not opts.__dict__[opt]:
            print("missing:", opt)
            parser.print_help()
            sys.exit(-1)

    return opts

def get_int_size(length):
    '''
    Function to return matching letter
    for struct.pack module following:
    - B is unsigned char (1 byte)
    - H is unsigned short (2 bytes)
    - L is unsigned long (4 bytes)
    - Q is unsigned long long (8 bytes)
    '''

    sizes = {1:'B', 2:'H', 4:'L', 8:'Q'}
    if length in sizes.keys():
        return sizes[length]
    else:
        raise ValueError("wrong integer size")

def get_data(data, data_type):
    '''
    Function to fetch the data from different sources:
    - file
    - text passed in ini file
    - hex value passed in ini file
    It returns in every case the data as a binary blob.
    '''

    prefix = {'hex':16, 'dec':10}

    if data_type == "file":
        with open(data, 'rb') as data_file:
            return data_file.read()
    elif data_type == "utf8.string":
        return data.encode('UTF-8')
    elif data_type == "hex.string":
        return binascii.unhexlify(data)
    #accepting [dec/hex].uint[8/16/32/64]
    elif "uint" in data_type:
        int_size = get_int_size(int(data_type[8:])/8)
        return struct.pack('<' + int_size, int(data, prefix[data_type[:3]]))
    else:
        raise ValueError("allowed values: hex.uint[8/16/32/64] / hex.string / utf8.string / file")

def create_header(data):
    '''Function to create Platform Data header'''

    return struct.pack('<4sII', PLATFORM_DATA_MAGIC, len(data),
                       binascii.crc32(data) & 0xFFFFFFFF)


def config_get_data_recursive(config, section, indices):

    curr_node = 'data' + indices

#    print('DEBUG: entering get_rec for ' +
#          '{0} with current indices: {1}'.format(config.get(section, 'desc'),
#                                                 curr_node))

    data_type = config.get(section, curr_node + ".type")

    if data_type == 'list':
        array_len = int(config.get(section, curr_node + ".list.len"))
        data = b''
        for i in range(array_len):
            data += config_get_data_recursive(config, section,
                                       indices + '[' + str(i) + ']')
    else: # leaf
        data = get_data(
            config.get(section, curr_node + ".value"),
            config.get(section, curr_node + ".type"))

    return data


def parse_ini(ini_file):
    '''Function to parse ini file and return a binary blob'''

    config = configparser.ConfigParser(dict_type=DICTIONARY)
    with open(ini_file) as config_file:
        config.read_file(config_file)

    platform_data = bytes()
    for section in config.sections():
        desc = config.get(section, "desc").encode('UTF-8')

        data = config_get_data_recursive(config, section, indices='')

        length = int(len(data))
        module_id = int(config.get(section, "id"))
        try:
            ver = int(config.get(section, "ver"))
        except configparser.NoOptionError:
            ver = 0

        if len(desc) > 10:
            raise ValueError("desc field too long, only 10 characters allowed")

        # 2byte id, 2byte length, 10byte ASCII string, 2byte version, Xbyte data
        platform_data += struct.pack('<H H 10s H' + str(len(data)) + 's',
                                     module_id, length, desc, ver, data)

    # Append the header of platform data
    return create_header(platform_data) + platform_data

def create_platform_data_binary(file_name, data):
    '''Create platform data binary in current directory'''

    with open(os.path.basename(file_name), 'wb') as data_file:
        data_file.write(data)

def patch_output_file(file_name, data, offset_from_top):
    '''Patch binary file and save it in current directory'''

    with open(file_name, 'r+b') as data_file:
        data_file.seek(0, 2)
        file_size = data_file.tell()
        if (offset_from_top > file_size):
            raise ValueError("Platform Data address must be within the input file")
        offset = file_size - offset_from_top
        data_file.seek(offset, 0)
        data_file.write(data)

def main():
    '''Main function of the module'''

    opts = parse_input()
    platform_data = parse_ini(opts.input_file)
    # "input_file" is the .ini config file
    pdat_file = os.path.splitext(opts.input_file)[0] + ".pdat"
    create_platform_data_binary(pdat_file, platform_data)

    if not os.path.exists(opts.original_image):

        print ("Full image '" + opts.original_image + "' was not found," +
               ' only standalone PDAT produced: ' + pdat_file)

        if opts.original_image != FLASH_MISSING_PDAT_BIN:
            # make this an error if the user explicitly pointed at one
            # file different from the default
            sys.exit(1)
        else:
            return

    platform_data_address = opts.pdat_address
    if (platform_data_address >= ADDRESS_4G):
        raise ValueError("Platform Data address must be below 4GB")
    platform_data_top_offset = ADDRESS_4G - platform_data_address
    # Copy the input file and patch the copy
    shutil.copy(opts.original_image, opts.modified_image)
    patch_output_file(opts.modified_image, platform_data, platform_data_top_offset)

if __name__ == "__main__":
    main()
