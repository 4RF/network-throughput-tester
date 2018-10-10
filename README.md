# Network Throughput Tester
This is a tool for testing the throughput of ethernet links using a configurable continuous packet size and transmission rate.

The source code to this tool is freely available here: https://github.com/4RF/network-throughput-tester

Instructions for building source code into an executable are here: [BUILDING.md](BUILDING.md)

# Simple throughput testing
At least two instances of the networktester need to be run. A single receiver is required, along with one or more senders.

## Sender
The sender is configured to send the specified packet size and a fixed rate. For example to send 18 bytes per packet
(64 bytes including UDP overhead) at 500kbps to 1.2.3.4:25000
```
> networktester.exe --address 1.2.3.4 --port 25000 --size 18 --rate 500000
4RF Network Tester
Version 1.3

Period = 10.0
Connecting to 127.0.0.1 port 20000
Ethernet bitrate = 500000 bps
Sending payload = 1272 bytes (plus ethernet overhead 1318.0 bytes)
Sent 474.0 packets of 1272 bytes in 10.00s = 499786 bps
Sent 475.0 packets of 1272 bytes in 10.02s = 500090 bps
Sent 475.0 packets of 1272 bytes in 10.03s = 499292 bps
Sent 475.0 packets of 1272 bytes in 10.01s = 500090 bps
Sent 475.0 packets of 1272 bytes in 10.01s = 500090 bps
```

This will generate packets continuously until stopped with ctrl-c.

## Receiver
The receiver should be configured to match the mode of the sending instance. For continuous tests you may have several
remotes sending continuously, allowing effective testing of how accurately bandwidth is shared between multiple remote
data streams.

An example of a listener receiving from two senders:

```
> networktester.exe --listen
4RF Network Tester
Version 1.3

Listening on 0.0.0.0 port 20000

Got connection from ('127.0.0.1', 57821)
Total (bps)          127.0.0.1:57821
323788               323788
500736               500736
Got connection from ('127.0.0.1', 57822)
Total (bps)          127.0.0.1:57821      127.0.0.1:57822
965009               500019               464990
999753               499968               499785
```

# Packet size sweep
To simplify testing a range of packet sizes, there is also an option to sweep through a range of specified packet sizes.

When a packet size sweep is performed, only one sender is allowed.

## Sender
To sweep through a range of packet sizes, a typical command would be:

```
> networktester.exe --address 1.2.3.4 --port 25000 --size 18 --rate 500000 --sweep --steps 18:82:210:466:978:1234:1472
4RF Network Tester
Version 1.3

Period = 10.0
Connecting to 127.0.0.1 port 20000
Sweeping payload size from 18 bytes to 1472 bytes (plus ethernet overhead of 46
bytes
Ethernet bitrate = 500000 bps
Sending payload = 18 bytes (plus ethernet overhead 64.0 bytes)
Sent 9766.0 packets of 18 bytes in 10.02s = 499270 bps
Sending payload = 82 bytes (plus ethernet overhead 128.0 bytes)
Sent 4883.0 packets of 82 bytes in 10.02s = 499220 bps
Sending payload = 210 bytes (plus ethernet overhead 256.0 bytes)
Sent 2442.0 packets of 210 bytes in 10.01s = 499373 bps
Sending payload = 466 bytes (plus ethernet overhead 512.0 bytes)
Sent 1221.0 packets of 466 bytes in 10.02s = 499323 bps
Sending payload = 978 bytes (plus ethernet overhead 1024.0 bytes)
Sent 611.0 packets of 978 bytes in 10.01s = 499782 bps
Sending payload = 1234 bytes (plus ethernet overhead 1280.0 bytes)
Sent 489.0 packets of 1234 bytes in 10.03s = 499238 bps
Sending payload = 1472 bytes (plus ethernet overhead 1518.0 bytes)
Sent 412.0 packets of 1472 bytes in 10.01s = 499583 bps
```

## Receiver:
An example of a listener receiving from a sending in sweep mode:

```
> networktester.exe --listen --sweep
4RF Network Tester
Version 1.3

Listening on 0.0.0.0 port 20000
Average period = 10.0

Got connection from ('127.0.0.1', 49799)
Address                 Payload Size  Total Size  Packets  Duration  Speed bps
127.0.0.1:49799                   18          64     9766     10.00     500019
127.0.0.1:49799                   82         128     4882     10.00     499916
127.0.0.1:49799                  210         256     2441     10.00     499916
127.0.0.1:49799                  466         512     1220     10.00     499712
127.0.0.1:49799                  978        1024      610     10.00     499712
127.0.0.1:49799                 1234        1280      486      9.98     498461
127.0.0.1:49799                 1472        1518      410      9.97     499502
```
