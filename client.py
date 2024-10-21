import grpc
import threading
import time
from grpc import ssl_channel_credentials

import uber_pb2
import uber_pb2_grpc

def rider_mode(stub):
    rider_id = int(input("Enter your rider ID: "))
    
    # Start a thread to listen for ride updates
    update_thread = threading.Thread(target=listen_for_updates, args=(stub, rider_id))
    update_thread.start()
    
    choice = input("Enter '1' to request a ride, '2' to check ride status").strip().lower()           
    if choice == '1':
        request_ride(stub, rider_id)
    elif choice == '2':
        check_ride_status(stub)
    else:
        print("Invalid choice. Please try again.")

    update_thread.join()

def request_ride(stub, rider_id):    
    latitude = float(input("Enter your current latitude: "))
    longitude = float(input("Enter your current longitude: "))
    dest_latitude = float(input("Enter destination latitude: "))
    dest_longitude = float(input("Enter destination longitude: "))
    
    location = uber_pb2.Location(latitude=latitude, longitude=longitude)
    destination = uber_pb2.Location(latitude=dest_latitude, longitude=dest_longitude)
    
    ride_request = uber_pb2.RideRequest(
        rider_id=rider_id,
        location=location,
        destination=destination
    )
    
    response = stub.RequestRide(ride_request, timeout=10)
    print(f"Ride requested with ID: {response.ride_id}, Status: {response.status}")    
    
def check_ride_status(stub):
    ride_id = int(input("Enter the ride ID: "))
    request = uber_pb2.RiderStatusRequest(ride_id=ride_id)
    response = stub.GetRideStatus(request)
    print(f"Ride {response.ride_id} status: {response.status}")
    
def listen_for_updates(stub, rider_id):
    try:
        for update in stub.SubscribeToRideUpdates(uber_pb2.RiderSubscription(rider_id=rider_id)):
            print(f"\nRide Update: Ride {update.ride_id} - Status: {update.status}")
            print(f"Message: {update.message}")
    except grpc.RpcError as e:
        print(f"Error in ride update stream: {e}")

def driver_mode(stub):
    driver_id = int(input("Enter your driver ID: "))
    current_latitude = float(input("Enter your current latitude: "))
    current_longitude = float(input("Enter your current longitude: "))
    
    driver = uber_pb2.Driver(
        driver_id=driver_id,
        status='AVAILABLE',
        current_location=uber_pb2.Location(
            latitude=current_latitude,
            longitude=current_longitude
        )
    )
    
    def listen_for_rides():
        try:                        
            responses = stub.SubscribeRides(iter([driver]))            
            for ride_request in responses:                                                       
                print(f"\nNew Ride Request from Rider {ride_request.rider_id}:")
                print(f"Location: ({ride_request.location.latitude}, {ride_request.location.longitude})")
                print(f"Destination: ({ride_request.destination.latitude}, {ride_request.destination.longitude})")
                choice = input("Do you want to accept this ride? (yes/no): ").strip().lower()
                if choice == 'yes':
                    accept_request = uber_pb2.AcceptRideRequest(
                        ride_id=1,  
                        driver_id=driver_id
                    )
                    accept_response = stub.AcceptRide(accept_request)
                    print(f"Accept Ride Response: {accept_response.message}")
                    
                    # After accepting, wait for completion
                    if accept_response.message == "Ride accepted.":
                        input("Press Enter when you've completed the ride...")
                        complete_request = uber_pb2.RideCompletionRequest(
                            ride_id=1,
                            driver_id=driver_id
                        )
                        complete_response = stub.CompleteRide(complete_request)
                        print(f"Complete Ride Response: {complete_response.message}")
                else:
                    reject_request = uber_pb2.RejectRideRequest(
                        ride_id=1,  
                        driver_id=driver_id
                    )
                    reject_response = stub.RejectRide(reject_request)
                    print(f"Reject Ride Response: {reject_response.message}")
        except grpc.RpcError as e:
            print(f"Connection closed: {e}")

    thread = threading.Thread(target=listen_for_rides)
    thread.start()
    print("Waiting for ride requests. Press Ctrl+C to exit.")
    try:
        thread.join()
    except KeyboardInterrupt:
        print("Driver mode terminated.")

def main():
    role = input("Choose your role (rider/driver): ").strip().lower()

    if role == 'rider':
        cert_file = 'rider.crt'
        key_file = 'rider.key'
    elif role == 'driver':
        cert_file = 'driver.crt'
        key_file = 'driver.key'
    else:
        print("Invalid role selected.")
        return

    # Load the appropriate certificate, key, and CA certificate
    with open(cert_file, 'rb') as f:
        client_certificate = f.read()
    with open(key_file, 'rb') as f:
        client_private_key = f.read()
    with open('ca.crt', 'rb') as f:
        trusted_ca = f.read()

    # Create SSL credentials for the client
    credentials = grpc.ssl_channel_credentials(
        root_certificates=trusted_ca,           # Server verification
        private_key=client_private_key,         # Client's private key
        certificate_chain=client_certificate    # Client's certificate
    )

    # Establish secure channel with server using mTLS
    with grpc.secure_channel('127.0.0.1:50054', credentials) as channel:
        stub = uber_pb2_grpc.RideSharingStub(channel)
        
        if role == 'rider':
            rider_mode(stub)
        elif role == 'driver':
            driver_mode(stub)

        # Keep the main thread alive
        while True:
            time.sleep(10)

if __name__ == '__main__':
    main()