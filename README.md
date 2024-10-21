# Ride-Sharing System

This is a basic ride-sharing system implemented using gRPC. The system consists of a server that manages ride requests and a client application that can be used by both riders and drivers.

## Prerequisites

- Python3 3.7+
- gRPC

## Setup

1. Clone the repository or download the source code.

2. Install the required Python packages:

```bash
pip install grpcio grpcio-tools
```

3. Generate the gRPC code from the proto file:

```bash
python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. uber.proto
```

This command will generate `uber_pb2.py` and `uber_pb2_grpc.py` files.

## Project Structure

The project consists of the following main files:

- `uber.proto`: The protocol buffer definition file.
- `server.py`: The server implementation.
- `client.py`: The client implementation for both riders and drivers.
- `uber_pb2.py` and `uber_pb2_grpc.py`: Generated gRPC code (you'll generate these).

## Running the Server

1. Open a terminal and navigate to the project directory.

2. Run the server:

```bash
python3 server.py
```

The server will start and listen on `127.0.0.1:50054`.

## Running the Client

1. Open a new terminal (keep the server running) and navigate to the project directory.

2. Run the client:

```bash
python3 client.py
```

3. Choose your role when prompted:
   - Enter 'rider' to act as a rider
   - Enter 'driver' to act as a driver

4. Follow the on-screen instructions:
   - As a rider, you can request rides and check ride status.
   - As a driver, you can accept or reject ride requests.

## Features

- Riders can request rides and check the status of their rides.
- Drivers can subscribe to ride requests and accept or reject them.
- Real-time updates for ride statuses.
- Automatic ride rejection if no driver accepts within 10 seconds.

## Example Usage

### As a Rider:

1. Run the client and choose 'rider' role.
2. Enter your rider ID when prompted.
3. Choose option '1' to request a ride.
4. Enter the required information (current location and destination).
5. Wait for updates on your ride status.
6. You can check the ride status anytime by choosing option '2'.

### As a Driver:

1. Run the client and choose 'driver' role.
2. Enter your driver ID and current location when prompted.
3. The system will notify you of any available ride requests.
4. Choose to accept or reject each ride request.

## Troubleshooting

If you encounter any issues:

1. Ensure all prerequisites are installed correctly.
2. Make sure the server is running before starting the client.
3. Check that you've generated the gRPC code correctly.
4. Verify that you're using the correct localhost address and port.
5. Make sure there are no processes running on the port before running client and server.


