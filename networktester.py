#!/usr/bin/python3

# Network Tester 
#
# Copyright (c) 2016-2018 4RF
#
# This file is subject to the terms and conditions of the GNU General Public
# License Version 3.  See the file "LICENSE" in the main directory of this
# archive for more details.

import socket
import errno
import sys
import getopt
import random
import signal
import time
import select

sw_version_number = "1.3"

listen_port_number = 20000
send_port_number = 0
address = "0.0.0.0"
packet_size = 1272
use_tcp = False
listen = False
delay_time = 100
bitrate = 500000 # Use default of 500kBit/s, which is higher than capacity of a 100kHz link @ 64QAM Raw
period = 10.0
verbose = False
sweep_start_size = None
sweep_step_sizes = None
sweep_step_size = None
sweep_max_size = None
sweep_end = None
sweep = False
sweep_delay = 10.0
listen_once = False

def usage():
    print('Usage: networktester.py')
    print('  --help')
    print('  --listen')
    print('  --once')
    print('  --tcp')
    print('  --size <size>')
    print('  --address <addr>')
    print('  --port <port>')
    print('  --sendport <port>')
    print('  --rate <time>')
    print('  --period <seconds>')
    print('  --verbose')
    print('  --sweep')
    print('  --steps <sweep list separated by :, eg 18:82:210:466:978:1234:1472>')
    print('  --start <sweep start size>')
    print('  --stop <sweep end size>')
    print('  --step <sweep step size>')
    print('  --sweep-end <listen ends after this step size>')

try:
    opts, args = getopt.getopt(sys.argv[1:],"",["help", "listen", "size=", "address=", "port=", "sendport=", "rate=", "tcp", "period=", "sweep", "start=", "stop=", "step=", "verbose", "steps=", "sweep-end=", "once"])
except getopt.GetoptError:
    usage()
    sys.exit(1)

for opt, arg in opts:
    if opt == "--port":
        listen_port_number = int(arg)
    if opt == "--sendport":
        send_port_number = int(arg)
    elif opt == "--size":
        packet_size = int(arg)
    elif opt == "--address":
        address = arg
    elif opt == "--tcp":
        use_tcp = True
    elif opt == "--listen":
        listen = True
    elif opt == "--rate":
        bitrate = float(arg)
    elif opt == "--period":
        period = float(arg)
    elif opt == "--sweep":
        sweep = True
    elif opt == "--start":
        sweep_start_size = int(arg)
    elif opt == "--stop":
        sweep_max_size = int(arg)
    elif opt == "--step":
        sweep_step_size = int(arg)
    elif opt == "--steps":
        sweep_step_sizes = list(map(int, arg.split(":")))
    elif opt == "--sweep-end":
        sweep_end = int(arg)
    elif opt == "--once":
        listen_once = True
    elif opt == "--verbose":
        verbose = True
    elif opt == "--help":
        print(opt, arg)
        usage()
        sys.exit(1)

# At least 12 bytes is required to hold the magic, length and sequence number fields
if (packet_size < 12) or ((sweep == True) and sweep_start_size and (sweep_start_size < 12)):
    print('packet size must be 12 bytes or more')
    usage()
    sys.exit(1)

if (packet_size > 1472) or ((sweep == True) and sweep_max_size and (sweep_max_size > 1472)):
    print('packet size must be 1272 bytes or less')
    usage()
    sys.exit(1)

if (sweep == True) and not(sweep_step_sizes) and not(listen) and (not(sweep_step_size) or not(sweep_start_size) or not(sweep_max_size)):
    print('invalid sweep params')
    usage()
    sys.exit(1)

if (listen == False) and (address == "0.0.0.0"):
    print('Invalid address')
    usage()
    sys.exit(1)

print('4RF Network Tester')
print('Version {}'.format(sw_version_number))
print('')

if sweep and not(listen) and not(sweep_step_sizes):
    sweep_step_sizes = list(range(sweep_start_size, sweep_max_size, sweep_step_size))

# Calculate the size of each packet at the ethernet layer
udp_overhead = 8
ip4_overhead = 20
eth_overhead = 18 # 14 byte header + 4 byte crc. 8 byte preamble not included

sock = None
exiting = False

def signal_handler(signal, frame):
    global sock
    global exiting
    
    print('exiting...')
    exiting = True
    if sock:
        sock.close()

def dodelay(t):
    global exiting
    
    start = time.monotonic()
    now = start
    while (not exiting) and (now - start < t):
        duration = t - (now - start)
        if duration > 1:
            duration = 1
        time.sleep(duration)
        now = time.monotonic()

signal.signal(signal.SIGINT, signal_handler)

# Create a TCP/IP socket
if use_tcp:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
else:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def add_connection(connection, client_address):
    global connection_list

    print('Got connection from', client_address)

    c = [connection, time.monotonic(), 0, 0, 0, 0, None, 0, 0, 0, 0, None]
    connection_list[client_address] = c

    if sweep:
        print("{:<22}{:>14}{:>12}{:>9}{:>10}{:>11}".format('Address', 'Payload Size', 'Total Size', 'Packets', 'Duration', 'Speed bps'))
    else:
        s = "{:<21}".format("Total (bps)")
        for c in connection_list:
            s += "{:<21}".format(str(c[0])+":"+str(c[1]))
        print(s)

if listen == False:
    print('Period =', period)

    # Create a TCP/IP socket
    if use_tcp:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    else:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Connect the socket to the port where the server is listening
    server_address = (address, listen_port_number)
    print('Connecting to %s port %s' % server_address)
    if use_tcp:
        sock.connect(server_address)
    else:
        sock.bind(("0.0.0.0", send_port_number))
    sock.setblocking(0)
    
    if sweep:
        packet_size = sweep_step_sizes[0]
        print('Sweeping payload size from {} bytes to {} bytes (plus ethernet overhead of {} bytes'.format(sweep_step_sizes[0], sweep_step_sizes[-1], udp_overhead + ip4_overhead + eth_overhead) )
    
    print('Ethernet bitrate = {:.0f} bps'.format(bitrate))

    this_delay_time = delay_time
    
    try:
        total_time = 0
        packets_sent = 0
        total_data_sent = 0
        sequence_number = 0
        measure_start_time = time.monotonic()
        measure_bytes = 0
        last_packet_size = 0
        sweep_period_start_time = time.monotonic()
        while True:
            try:
                current_time = time.monotonic()
                
                if (not(sweep) and (current_time - measure_start_time >= 10.0)):
                    print('Sent {} packets of {} bytes in {:.2f}s = {:.0f} bps'.format(measure_bytes / packet_size, packet_size, current_time - measure_start_time, measure_bytes * packet_size_eth_bits / packet_size / (current_time - measure_start_time)))
                    measure_bytes = 0
                    measure_start_time = current_time

                if sweep and (time.monotonic() - sweep_period_start_time > period):
                    print('Sent {} packets of {} bytes in {:.2f}s = {:.0f} bps'.format(measure_bytes / packet_size, packet_size, current_time - measure_start_time, measure_bytes * packet_size_eth_bits / packet_size / (current_time - measure_start_time)))
                    
                    cindex = sweep_step_sizes.index(packet_size)
                    if cindex < len(sweep_step_sizes)-1:
                        packet_size = sweep_step_sizes[cindex+1]
                    else:
                        break
                    
                    dodelay(sweep_delay)
                    measure_bytes = 0
                    measure_start_time = time.monotonic()
                
                # Send data
                if last_packet_size != packet_size:
                    packets_sent = 0
                    start_time = time.monotonic()
                    last_packet_size = packet_size
                    packet_size_eth_bits = (packet_size + udp_overhead + ip4_overhead + eth_overhead) * 8
                    delay_time = float(packet_size_eth_bits) / float(bitrate)
                    print('Sending payload = {} bytes (plus ethernet overhead {} bytes)'.format(packet_size, packet_size_eth_bits / 8))
                    #print('Delay between packets = {:.02f} ms'.format(delay_time * 1000.0))
                    
                    # Each packet contains a magic number (4 bytes), a length (4 bytes), and remaining bytes are random
                    packet = bytearray(packet_size)
                    for x in range(0, packet_size):
                        packet[x] = random.randint(0,255)
                    packet[0] = 0xBA
                    packet[1] = 0xAD
                    packet[2] = 0xF0
                    packet[3] = 0x0D
                    packet[4] = (packet_size >> 24) & 0xFF
                    packet[5] = (packet_size >> 16) & 0xFF
                    packet[6] = (packet_size >> 8) & 0xFF
                    packet[7] = (packet_size >> 0) & 0xFF
                    
                    sweep_period_start_time = time.monotonic()
                
                sequence_number += 1
                packet[8] = (sequence_number >> 24) & 0xFF
                packet[9] = (sequence_number >> 16) & 0xFF
                packet[10] = (sequence_number >> 8) & 0xFF
                packet[11] = (sequence_number >> 0) & 0xFF
                
                total_data_sent += packet_size
                if use_tcp:
                    sent_data = 0
                    while (sent_data < packet_size):
                        try:
                            ret = sock.send(packet[sent_data:])
                            sent_data += ret
                        except socket.error as e:
                            if e.args[0] != errno.EWOULDBLOCK:
                                raise e
                            dodelay(0.01)
                else:
                    sock.sendto(packet, server_address)
                measure_bytes += packet_size
                packets_sent += 1

                # Delay enough to make average message rate what is requested, correcting for loop overhead and imprecise delay function
                if bitrate > 0:
                    elapsed_time = time.monotonic() - start_time
                    expected_elapsed_time = packets_sent * delay_time
                    if expected_elapsed_time > elapsed_time:
                        this_delay_time = expected_elapsed_time - elapsed_time
                    else:
                        this_delay_time = 0
                else:
                    this_delay_time = 0
                if this_delay_time > 0:
                    dodelay(this_delay_time)
                current_time = time.monotonic()
            except:
                break

    finally:
        print('Closing socket')
        sock.close()
    
else:
    # Bind the socket to the port
    server_address = (address, listen_port_number)
    print('Listening on %s port %s' % server_address)
    if sweep:
        print('Average period = {:.1f}'.format(period))
    print('')
    
    sock.bind(server_address)
    sock.setblocking(0)
    
    if use_tcp:
        # Listen for incoming connections
        sock.listen(1)

    connection_list = {}
    
    total_start_time = None
    start_time = time.monotonic()
    sweep_rx_length = 0
    last_rx_length = 0
    first_rx_time = 0
    last_rx_time = 0
    this_rx_time = 0

    while True:
        try:
            current_time = time.monotonic()
            if (sweep == False) and ((current_time - start_time) >= period):
                start_time += period
                
                total_bytes = 0
                total_packets = 0
                period_bytes = 0
                period_packets = 0
                period_dropped_bytes = 0
                total_dropped_bytes = 0
                
                s = ""
                for c in connection_list:
                    total_packets += connection_list[c][2]
                    total_bytes += connection_list[c][3]
                    period_packets += connection_list[c][4]
                    period_bytes += connection_list[c][5]
                    period_dropped_bytes += connection_list[c][8]
                    total_dropped_bytes += connection_list[c][10]
                    
                    bps_period = (connection_list[c][5] + connection_list[c][4] * (udp_overhead + ip4_overhead + eth_overhead)) * 8.0 / period
                    bps_total = (connection_list[c][3] + connection_list[c][2] * (udp_overhead + ip4_overhead + eth_overhead)) * 8.0 / (current_time - connection_list[c][1])
                    s += '{:<21}'.format(int(bps_period))
                    
                    connection_list[c][4] = 0
                    connection_list[c][5] = 0
                    connection_list[c][7] = 0
                    connection_list[c][8] = 0
                
                if total_start_time != None:
                    bps_period = (period_bytes + period_packets * (udp_overhead + ip4_overhead + eth_overhead)) * 8.0 / period
                    bps_total = (total_bytes + total_packets * (udp_overhead + ip4_overhead + eth_overhead)) * 8.0 / (current_time - total_start_time)

                    s = '{:<21}'.format(int(bps_period)) + s
                else:
                    s = '{:<21}'.format(0)
                print(s)
                
                if listen_once:
                    sys.exit(0)
            
            elif (sweep == True) and ((last_rx_length != sweep_rx_length) or (time.monotonic() - last_rx_time > sweep_delay)):
                if sweep_rx_length != 0:
                    for c in connection_list:
                        # Latest packet is different size. So subtract from total, and use time up till previous packet as averaging period
                        period_num_packets = connection_list[c][4] - 1
                        period_total_data = connection_list[c][5] - last_rx_length
                        if last_rx_length == sweep_rx_length:
                            period_num_packets -= 1
                            period_total_data -= last_rx_length
                            last_rx_length = 0
                        calc_period = last_rx_time - start_time
                        #print period_num_packets, period_total_data, calc_period
                        if period_num_packets > 0:
                            bps_period = (period_total_data + period_num_packets * (udp_overhead + ip4_overhead + eth_overhead)) * 8.0 / calc_period
                            print('{:<22}{:>14}{:>12}{:>9}{:>10.2f}{:>11}'.format(str(c[0])+":"+str(c[1]), sweep_rx_length, sweep_rx_length + udp_overhead + ip4_overhead + eth_overhead, period_num_packets, calc_period, int(bps_period)))
                        
                        connection_list[c][4] = 0
                        connection_list[c][5] = 0
                        connection_list[c][7] = 0
                        connection_list[c][8] = 0
                        
                if sweep_end and (sweep_end == sweep_rx_length):
                    break
                sweep_rx_length = last_rx_length
                start_time = time.monotonic()
    
            # Wait for data, timing out after 100ms
            check_list = []
            if use_tcp:
                for c in connection_list:
                    check_list.append(connection_list[c][0])
            check_list.append(sock)
            ready_to_read, ready_to_write, in_error = select.select(check_list, [], [], 0.1)
            
            if use_tcp and (sock in ready_to_read):
                ready_to_read.remove(sock)
                connection, client_address = sock.accept()
                add_connection(connection, client_address)

                if total_start_time == None:
                    start_time = time.monotonic()
                    total_start_time = time.monotonic()

            for connection in ready_to_read:
                # Read a single datagram from one remote host
                if use_tcp:
                    address = connection.getpeername()
                    readdata = bytearray(connection.recv(packet_size))
                else:
                    readdata, address = connection.recvfrom(4096)
                    readdata = bytearray(readdata)
                
                # Check if we have received from this remote host already. If not, add to list of connections
                found = False
                for c in connection_list:
                    if c == address:
                        found = True
                        break
                if found == False:
                    add_connection(None, address)
                    if total_start_time == None:
                        total_start_time = time.monotonic()

                if connection_list[address][11]:
                    data = connection_list[address][11]
                    connection_list[address][11] = None
                    data.extend(readdata)
                else:
                    data = readdata
                
                if len(data) > 0:
                    connection_list[address][3] += len(data)
                    connection_list[address][5] += len(data)
                    
                    while len(data) >= 12:
                        magic = (data[0] << 24) | (data[1] << 16) | (data[2] << 8) | data[3]
                        pktlen = (data[4] << 24) | (data[5] << 16) | (data[6] << 8) | data[7]
                        
                        connection_list[address][2] += 1
                        connection_list[address][4] += 1
                        
                        if magic != 0xBAADF00D:
                            print('{}: magic number mismatch {} != {}'.format(str(address[0])+":"+str(address[1]), magic, 0xBAADF00D))
                            data = None
                        elif (pktlen != len(data)) and (use_tcp == False):
                            print('{}: length mismatch {} != {}'.format(str(address[0])+":"+str(address[1]), pktlen, len(data)))
                            data = None
                        else:
                            if len(data) >= pktlen:
                                seq = (data[8] << 24) | (data[9] << 16) | (data[10] << 8) | data[11]
                                last_seq = connection_list[address][6]
                                if last_seq == None:
                                    last_seq = seq - 1
                                elif (seq == 0) or (seq <= last_seq - 100):
                                    print('{}: Reconnected'.format(str(address[0])+":"+str(address[1])))
                                    connection_list[address] = [None, time.monotonic(), 0, 0, 0, 0, None, 0, 0, 0, 0, None]
                                    last_seq = 0
                                    
                                if seq != last_seq + 1:
                                    #print('{}: Lost {} packets (seq = {})'.format(str(address[0])+":"+str(address[1]), seq - last_seq - 1, seq))
                                    connection_list[address][7] += seq - last_seq - 1
                                    connection_list[address][8] += (seq - last_seq - 1) * len(data)
                                    connection_list[address][9] += seq - last_seq - 1
                                    connection_list[address][10] += (seq - last_seq - 1) * len(data)

                                
                                connection_list[address][6] = seq
                                
                                last_rx_length = pktlen
                                last_rx_time = this_rx_time
                                this_rx_time = time.monotonic()
                                
                                # Any data that is part of next packet, keep in a buffer
                                if len(data) > pktlen:
                                    data = data[pktlen:]
                                else:
                                    data = None
                                    break
                            else:
                                break
                    
                    # Save any remaining data
                    connection_list[address][11] = data
                        
                else:
                    print('{}: Client disconnected'.format(str(address[0])+":"+str(address[1])))
                    connection.close()
                    del connection_list[address]
                    if not connection_list:
                        total_start_time = None
                    
            for connection in in_error:
                ca = None
                for c in connection_list:
                    if connection_list[c][0] == connection:
                        ca = c
                        break
                if ca and use_tcp:
                    # Clean up the connection
                    print('Client disconnected', ca)
                    del connection_list[ca]
                    connection.close()
                    if not connection_list:
                        total_start_time = None

        except:
            break

