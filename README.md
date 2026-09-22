# Socket Video Streaming

A Python-based client-server video streaming application built for a Computer Networks project at **VNU-HCMUS**. The system uses **RTSP-like control messages over TCP** and streams **MJPEG video frames over RTP/UDP** across a local network.

The project demonstrates core networking concepts such as socket programming, RTP packet construction, RTSP session control, frame fragmentation and reassembly, buffering, packet ordering, and multithreaded client/server communication.

## Features

- Client-server video streaming over a LAN
- RTSP-style session control using TCP
- RTP video transport using UDP
- `SETUP`, `PLAY`, `PAUSE`, and `TEARDOWN` operations
- Custom RTP packet encoding and decoding
- MJPEG frame streaming
- Frame fragmentation into smaller RTP payloads
- Client-side frame reassembly
- Jitter buffer for handling out-of-order packets
- Packet-loss detection using RTP sequence numbers
- Startup buffering for smoother playback
- Adaptive playback timing based on buffer occupancy
- Multithreaded networking and video display
- Simple desktop GUI built with Tkinter
- Support for multiple client connections at the server level

## Architecture

```mermaid
flowchart LR
    A[Client GUI] -->|RTSP Commands / TCP| B[RTSP Server]
    B --> C[ServerWorker]
    C --> D[VideoStream]
    D --> E[MJPEG Frames]
    E --> F[Frame Fragmentation]
    F --> G[RTP Packet Encoder]
    G -->|RTP / UDP| H[Client RTP Receiver]
    H --> I[Jitter Buffer]
    I --> J[Frame Reassembly]
    J --> K[Frame Buffer]
    K --> L[Video Display]
```

The application separates **session control** from **media delivery**:

1. The client establishes a TCP connection with the server.
2. The client sends RTSP-style requests such as `SETUP`, `PLAY`, `PAUSE`, and `TEARDOWN`.
3. After `PLAY`, the server reads MJPEG frames from the requested video file.
4. Large frames are divided into chunks with a maximum payload size of approximately **1400 bytes**.
5. Each chunk is wrapped inside a custom RTP packet containing sequence number, timestamp, marker bit, payload type, and SSRC fields.
6. RTP packets are transmitted to the client over UDP.
7. The client places packets into a jitter buffer, restores packet order, detects missing packets, and reconstructs complete JPEG frames.
8. Reconstructed frames are placed into a playback buffer and displayed through the Tkinter interface.

## Networking Design

### Control Channel — TCP

TCP is used for RTSP-style control communication.

The server listens for incoming client connections and processes commands such as:

```text
SETUP
PLAY
PAUSE
TEARDOWN
```

TCP is appropriate for the control channel because commands must arrive reliably and in the correct order.

### Media Channel — RTP over UDP

The video stream itself is transmitted using RTP packets over UDP.

UDP avoids retransmission delays that can negatively affect real-time playback. To compensate for packet reordering and packet loss, the client implements:

- RTP sequence-number tracking
- jitter buffering
- missing-packet detection
- corrupted-frame rejection
- frame reconstruction using the RTP marker bit

## RTP Packet Structure

The project implements a standard 12-byte RTP-style header.

```text
  0                   1                   2                   3
  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |V=2|P|X|  CC   |M|     PT      |       Sequence Number         |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |                           Timestamp                           |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |                              SSRC                             |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |                         Video Payload ...                     |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

Important fields used by the application:

| Field | Purpose |
|---|---|
| Version | RTP version, set to 2 |
| Marker | Marks the final packet belonging to a video frame |
| Payload Type | Set to 26 for MJPEG |
| Sequence Number | Detects ordering and packet loss |
| Timestamp | Provides playback timing information |
| SSRC | Identifies the RTP source |
| Payload | Fragment of an MJPEG frame |

## Video Processing

`VideoStream.py` reads frames from an MJPEG video source.

It supports two frame-reading strategies:

- reading frames prefixed by a 5-byte frame-length field
- scanning for the JPEG End-of-Image marker (`FF D9`) as a fallback

On the server, each frame is fragmented before transmission:

```text
MJPEG Frame
    |
    +-- Chunk 1 --> RTP Packet
    +-- Chunk 2 --> RTP Packet
    +-- Chunk 3 --> RTP Packet
    ...
    +-- Final Chunk --> RTP Packet with Marker = 1
```

The client collects those chunks and rebuilds the original JPEG frame before displaying it.

## Buffering and Playback

The client uses two buffering mechanisms.

### Jitter Buffer

Incoming RTP packets are temporarily stored by sequence number.

This allows the client to:

- reorder packets
- wait for expected packets
- detect missing packets
- discard corrupted frames when necessary

### Frame Buffer

Completed JPEG frames are stored in a queue before playback.

The implementation includes startup buffering and slightly adjusts playback timing depending on the current buffer occupancy. This helps reduce visible stuttering when packet arrival timing varies.

The current implementation is paced around **30 FPS**.

## Multithreading

Networking and rendering tasks run in separate threads so the GUI remains responsive.

### Server

Each connected client is handled by a separate worker flow. RTP transmission also runs in its own thread.

### Client

The client separates:

- RTP packet reception
- video display
- GUI/event handling

This prevents network operations from blocking the user interface.

## Project Structure

```text
Socket/
├── Client.py
├── ClientLauncher.py
├── RtpPacket.py
├── Server.py
├── ServerWorker.py
├── VideoStream.py
└── __pycache__/
```

### File Responsibilities

| File | Description |
|---|---|
| `Server.py` | Starts the TCP server, accepts client connections, and creates a worker for each client |
| `ServerWorker.py` | Processes RTSP requests, manages session state, fragments video frames, builds RTP packets, and sends them through UDP |
| `VideoStream.py` | Reads individual MJPEG/JPEG frames from the video file |
| `RtpPacket.py` | Encodes and decodes RTP headers and payloads |
| `ClientLauncher.py` | Parses command-line arguments and starts the Tkinter client |
| `Client.py` | Handles the GUI, RTSP communication, RTP reception, jitter buffering, frame reconstruction, buffering, and playback |

## Requirements

- Python 3.x
- Pillow
- Tkinter
- A network connection between the server and client machines

Tkinter is normally included with standard Python installations on Windows.

Install Pillow with:

```bash
pip install Pillow
```

On some Linux distributions, Tkinter may need to be installed separately.

For Ubuntu/Debian:

```bash
sudo apt install python3-tk
```

## Installation

Clone the repository:

```bash
git clone https://github.com/XuanDuong1905/Socket.git
cd Socket
```

Install the required Python package:

```bash
pip install Pillow
```

## Running the Application

The server and client can run on the same machine or on separate machines connected to the same LAN.

### 1. Start the server

```bash
python Server.py <server_port>
```

Example:

```bash
python Server.py 8554
```

The server will listen for incoming RTSP/TCP connections on the specified port.

### 2. Start the client

```bash
python ClientLauncher.py <server_ip> <server_port> <rtp_port> <video_file>
```

Example:

```bash
python ClientLauncher.py 192.168.1.10 8554 5004 movie.Mjpeg
```

Arguments:

| Argument | Description |
|---|---|
| `server_ip` | IP address of the machine running the server |
| `server_port` | TCP port used by the RTSP control channel |
| `rtp_port` | UDP port where the client receives RTP packets |
| `video_file` | Video filename requested from the server |

> The requested video file must be accessible to the server process.

## Session Flow

```text
Client                                      Server
  |                                           |
  | -------- TCP Connection ----------------> |
  |                                           |
  | -------- SETUP --------------------------> |
  | <------- 200 OK ------------------------- |
  |                                           |
  | -------- PLAY ---------------------------> |
  | <------- 200 OK ------------------------- |
  |                                           |
  | <======= RTP / UDP Video Stream ========= |
  |                                           |
  | -------- PAUSE --------------------------> |
  | <------- 200 OK ------------------------- |
  |                                           |
  | -------- TEARDOWN -----------------------> |
  | <------- 200 OK ------------------------- |
  |                                           |
```

## Technical Highlights

### Frame Fragmentation

High-resolution JPEG frames can be much larger than a safe UDP payload. Instead of transmitting an entire frame in one datagram, the server splits each frame into chunks of roughly 1400 bytes.

This reduces the risk of IP fragmentation and allows large video frames to be transported more reliably across the network.

### Frame Reassembly

Every RTP packet carries a sequence number. The final fragment of a frame has its RTP marker bit set to `1`.

The client appends payloads in sequence until the final fragment arrives, then reconstructs the JPEG frame.

### Packet Loss Handling

If the jitter buffer grows while an expected sequence number is still missing, the client assumes packet loss has occurred.

The affected frame is marked as corrupted and discarded rather than displaying incomplete image data.

### RTP Timestamping

The server uses a 90 kHz RTP clock and calculates timestamps based on the frame number and target playback rate.

This gives the client timing information that can be used for video playback and elapsed-time display.

## What I Learned

This project provided hands-on experience with several important computer-networking concepts:

- TCP and UDP socket programming
- client-server architecture
- RTSP-style session management
- RTP packet structures
- media fragmentation and reconstruction
- sequence numbers and timestamps
- packet loss and packet reordering
- jitter buffering
- multithreading
- synchronization between networking and media playback
- GUI programming with Tkinter

One of the most important engineering challenges was handling video frames that were too large to safely transmit as a single UDP packet. The solution was to fragment each frame into smaller RTP payloads and reconstruct it on the client using sequence numbers and the RTP marker bit.

## Limitations

The project is primarily an educational implementation and is not intended to replace a production streaming server.

Current limitations include:

- MJPEG-focused video transport
- fixed playback pacing around 30 FPS
- no audio streaming
- no congestion-control algorithm
- no RTP retransmission mechanism
- no encryption or authentication
- simplified RTSP implementation
- LAN-oriented usage

## Possible Improvements

Future versions could include:

- H.264/H.265 video encoding
- audio streaming
- dynamic frame-rate detection
- adaptive bitrate streaming
- congestion control
- packet-loss recovery or Forward Error Correction
- RTCP statistics
- encryption
- authentication
- improved multi-client scalability
- automatic video metadata detection
- cross-platform UI improvements

## Author

**Xuan Duong**

Computer Science student project — VNU-HCMUS

GitHub: [XuanDuong1905](https://github.com/XuanDuong1905)

## Repository

https://github.com/XuanDuong1905/Socket

---

If you find this project useful for learning computer networks, socket programming, RTSP, or RTP, feel free to explore the source code and experiment with it.
