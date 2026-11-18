
# LAN Chat & File Sharing

A peer-to-peer communication and file-sharing application developed using Python Socket Programming. The application allows multiple devices connected to the same Local Area Network (LAN) to discover each other, exchange messages in real time, and transfer files directly between peers.

## 1. Project Overview

LAN Chat & File Sharing is a client-server and peer-to-peer networking application that demonstrates fundamental networking concepts using Python sockets.

The application provides a decentralized peer discovery mechanism using UDP broadcasting and supports TCP-based communication for messaging and file transfers.

### Main Features

| Feature | Description |
|---|---|
| Peer Discovery | Automatically discovers other devices on the same LAN using UDP broadcasting. |
| Peer Management | Maintains a list of discovered peers and their connection statuses. |
| Status Management | Allows users to change their status, such as Online and Away. |
| Real-time Chat | Enables users to exchange messages directly with other peers using TCP sockets. |
| Chat History | Stores and displays conversation history. |
| Unread Notifications | Tracks unread messages and notifies users of incoming messages. |
| File Sharing | Allows users to send files to one or multiple peers on the LAN. |
| File Transfer Requests | Allows recipients to accept or reject incoming file requests. |
| Transfer Monitoring | Displays file transfer progress and transfer statuses. |
| Transfer Cancellation | Supports cancelling ongoing file transfers. |
| Available Files | Manages and displays files available for sharing. |

## 2. Technologies Used

- **Programming Language:** Python
- **Networking:** Python Socket Programming
- **UDP:** Peer discovery and presence broadcasting.
- **TCP:** Message exchange and file transfer.
- **Multithreading:** Handles concurrent network operations without blocking the user interface.
- **Unit Testing:** Python `unittest` framework.

## 3. Project Structure

The project is organized into several modules to separate networking, peer management, chat functionality, file transfer, and user interface responsibilities.

```text
project/
│
├── src/
│   ├── peer-discover/
│   │   ├── presence_message.py
│   │   ├── broadcast.py
│   │   ├── listen.py
│   │   └── peer_manager.py
│   │
│   ├── common/
│   │   ├── logger.py
│   │   └── message.py
│   ├── chat/
│   │   ├── chat_server.py
│   │   ├── chat_client.py
│   │   ├── chat_message.py
│   │   ├── chat_ui.py
│   │   └── chat_manager.py
│   │
│   ├── file_transfer/
│   │   ├── file_ui.py
│   │   ├── file_utils.py
│   │   ├── file_manager.py
│   │   ├── file_server.py
│   │   ├── file_sender.py
│   │   └── file_receiver.py
│   ├── config.py
│   ├── ui.py
│   └── main.py
│
├── tests/
│   ├── test_chat.py
│   ├── test_peer_discovery.py
│   ├── test_chat_server.py
│   ├── test_chat_manager.py
│   └── ... 
│
├── requirements.txt
└── README.md
```

**Note:** The structure above describes the main project modules. Some filenames may differ depending on the current implementation.

## 4. Requirements

Before installing the project, ensure that the following requirements are met:

- Python 3.10 or later.
- Git (optional, for cloning the repository).
- Two or more devices connected to the same Local Area Network (LAN) for multi-peer testing.
- Network access that allows UDP broadcast and TCP connections between devices.

## 5. Installation

### Step 1: Extract the project

Download the submitted ZIP file and extract it to a directory on your computer.

### Step 2: Create a virtual environment

It is recommended to use a virtual environment to isolate project dependencies.

**Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

**Linux / macOS:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install dependencies

If the project contains a `requirements.txt` file, install the required packages:

```bash
pip install -r requirements.txt
```

If no external dependencies are required, the project can run using Python's standard library.

### Step 4: Configure network settings

Open the network configuration file:

```text
src/peer-discover/config.py
```

Check the configuration parameters, including:

- Peer discovery broadcast settings.
- UDP listening port.
- TCP chat server settings.
- File transfer server settings.
- Peer timeout and inactive peer cleanup intervals.
- File storage directory.

Make sure that the selected ports are available and consistent across the application.

**Important:** All devices participating in the application should be connected to the same LAN. Ensure that the firewall allows the application's UDP and TCP traffic.

## 6. Running the Application
### Step 1: Start the first peer

Open a terminal at the project root directory and run:

```bash
python src/main.py --peer-id A001 --username Alice --port 5001
```

### Step 2: Start additional peers

Open another terminal window for each peer and execute the application with different peer IDs, usernames, and ports.

**Peer A:**
```bash
python src/main.py --peer-id A001 --username Alice --port 5001
```

**Peer B:**
```bash
python src/main.py --peer-id B001 --username Bob --port 5002
```

**Peer C:**
```bash
python src/main.py --peer-id C001 --username Charlie --port 5003
```

Each peer must have a unique peer ID and an available port.

### Step 3: Discover other peers

After starting the application:

1. Each peer broadcasts its presence information over UDP.
2. Other peers listen for broadcast messages.
3. Discovered peers are automatically added to the peer list.
4. Verify that the peers appear in the online peer list.

### Step 4: Exchange messages

1. Select an online peer.
2. Open a chat session.
3. Enter and send a message.
4. Verify that the recipient receives the message.

### Step 5: Transfer files

1. Open the file-sharing interface.
2. Select one or more online peers.
3. Choose a file to send.
4. Send the file transfer request.
5. The receiving peer accepts or rejects the request.
6. If accepted, monitor the transfer progress.
7. Verify that the received file is saved in the configured destination directory.

## 7. Testing

The project uses Python's built-in `unittest` framework to test individual modules and verify application behavior.

### 7.1 Run All Tests

From the project root directory, execute:

```bash
python -m unittest discover -s tests -v
```

This command automatically discovers and executes test cases in the `tests/` directory.

### 7.2 Run Individual Test Files

To test a specific module, execute:

```bash
python -m unittest discover -s tests -p "test_chat.py" -v
```

Other examples:

```bash
python -m unittest discover -s tests -p "test_peer_discovery.py" -v

python -m unittest discover -s tests -p "test_chat_server.py" -v

python -m unittest discover -s tests -p "test_chat_manager.py" -v
```

Replace the filename with the corresponding test file when necessary.

### 7.3 Test Coverage

The test suite focuses on the following components:

| Test Module | Testing Scope |
|---|---|
| `test_chat.py` | Chat functionality, message creation, validation, and communication. |
| `test_peer_discovery.py` | UDP broadcasting, peer discovery, peer updates, and inactive peer cleanup. |
| `test_chat_server.py` | TCP server initialization and incoming client connections. |
| `test_chat_manager.py` | Incoming message processing, unread message tracking, and chat history management. |
| File transfer tests | File requests, sending, receiving, transfer progress, and cancellation. |
| UI tests | Menu navigation, peer display, user input, notifications, and error handling. |

### 7.4 Expected Test Results

A successful test execution should display results similar to:

```text
test_create_chat_message ... ok
test_validate_chat_message ... ok
test_update_peer ... ok
test_get_online_peers ... ok
test_handle_incoming_message ... ok

----------------------------------------------------------------------
Ran XX tests in X.XXXs

OK
```

The actual number of tests and execution time depend on the current test suite.

## 8. Network Configuration and Troubleshooting

### Devices cannot discover each other

Possible causes:

- Devices are connected to different networks.
- UDP broadcast traffic is blocked by the firewall.
- The configured UDP port is incorrect.
- Network isolation is enabled on the router or access point.

**Solution:**
- Verify that all devices are connected to the same LAN.
- Check UDP configuration.
- Allow UDP broadcast traffic through the firewall.

### Chat messages cannot be delivered

Possible causes:

- The destination peer is offline.
- The TCP server is not running.
- The configured IP address or TCP port is incorrect.
- The firewall blocks TCP connections.

**Solution:**
- Verify the peer's connection status.
- Ensure that the TCP chat server is running.
- Check the peer's IP address and TCP port.
- Check firewall permissions.

### File transfer fails

Possible causes:

- The receiver has rejected the transfer request.
- The receiver is unavailable.
- The file path is invalid.
- The TCP connection cannot be established.
- The destination directory is inaccessible.

**Solution:**
- Verify that the receiver is online.
- Ensure that the incoming transfer request is accepted.
- Check file paths and destination directory permissions.
- Verify the file transfer TCP configuration.

## 9. Key Networking Concepts

This project demonstrates several fundamental networking concepts:

| Concept | Application |
|---|---|
| UDP Socket | Broadcasts presence messages to discover peers on the LAN. |
| TCP Socket | Establishes reliable connections for chat and file transfer. |
| Peer-to-Peer Communication | Allows devices to communicate directly with each other. |
| Multithreading | Handles multiple network operations concurrently. |
| Message Serialization | Encodes and decodes messages for network transmission. |
| Connection Management | Tracks online peers and removes inactive devices. |
| Data Validation | Validates incoming messages and transfer requests. |

## 10. Limitations

- The application is designed primarily for devices within the same Local Area Network.
- Peer discovery depends on UDP broadcast support in the network environment.
- Communication may be affected by firewall rules and network configurations.
- Application availability depends on the destination peer being online.
- The application does not currently provide end-to-end encryption unless implemented separately.

## 11. Future Improvements

Potential improvements include:

- Implementing encrypted communication.
- Supporting file transfer resumption.
- Improving network error handling and reconnection mechanisms.
- Supporting communication across different networks.
- Improving the user interface and transfer management experience.

## 12. Authors

Developed as a Socket Programming course project.

**Project:** LAN Chat & File Sharing

**Course:** Socket Programming
