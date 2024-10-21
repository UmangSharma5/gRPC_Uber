import grpc
from concurrent import futures
import time
import threading
from queue import Queue
from grpc import ssl_server_credentials

import uber_pb2
import uber_pb2_grpc

class RideSharingServicer(uber_pb2_grpc.RideSharingServicer):
    def __init__(self):
        # List of driver streams
        self.drivers = {}
        self.lock = threading.Lock()
        self.ride_id_counter = 1
        self.active_rides = {}  # ride_id: rider info
        self.ride_timers = {}
        self.rider_streams = {}

    def RequestRide(self, request, context):        
        with self.lock:            
            ride_id = self.ride_id_counter
            self.ride_id_counter += 1
            self.active_rides[ride_id] = {
                'rider_id': request.rider_id,
                'location': request.location,
                'destination': request.destination,
                'status': 'Pending'
            }
        print(f"Received ride request {ride_id} from rider {request.rider_id}")
        
        timer = threading.Timer(10.0, self.auto_reject_ride, args=[ride_id])
        self.ride_timers[ride_id] = timer
        timer.start()
        
        # Notify all drivers
        threading.Thread(target=self.notify_drivers, args=(ride_id,)).start()
        # For simplicity, respond immediately with ride_id and status
        return uber_pb2.RideResponse(
            ride_id=ride_id,
            driver_id=0,  # To be assigned
            status='Ride Requested'
        )
        
    def auto_reject_ride(self, ride_id):
        with self.lock:
            ride = self.active_rides.get(ride_id)
            if ride and ride['status'] == 'Pending':
                ride['status'] = 'Auto-Rejected'
                print(f"Ride {ride_id} automatically rejected after 10 seconds")
                self.notify_rider(ride['rider_id'], ride_id, 'Auto-Rejected', "No drivers accepted the ride within 10 seconds.")
                # Remove the ride from active_rides or mark it as expired                
        
    def GetRideStatus(self, request, context):
        with self.lock:
            ride = self.active_rides.get(request.ride_id)
            if not ride:
                return uber_pb2.RiderStatusResponse(
                    ride_id=request.ride_id,
                    status="Ride not found"
                )
            return uber_pb2.RiderStatusResponse(
                ride_id=request.ride_id,
                status=ride['status']
            )

    def SubscribeRides(self, request_iterator, context):        
        driver_info = next(request_iterator, None)        
        if driver_info is None:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details('Driver information is required.')
            return
        
        driver_id = driver_info.driver_id
        print(f"Driver {driver_id} subscribed for rides.")
        # Create a queue for this driver        
        with self.lock:
            self.drivers[driver_id] = {'status': 'AVAILABLE', 'queue': []}            
        try:
            while True:
                with self.lock:
                    if self.drivers[driver_id]['queue']:
                        if self.drivers[driver_id]['status'] == 'AVAILABLE':
                            ride_id, ride_request = self.drivers[driver_id]['queue'].pop(0)                            
                            yield uber_pb2.RideRequestWithRideId(
                                rider_id=ride_request.rider_id,
                                location=ride_request.location,
                                destination=ride_request.destination,
                                ride_id=ride_id  
                            )
                time.sleep(1)
        except grpc.RpcError as e:
            print(f"Driver {driver_id} disconnected.")
            with self.lock:
                if driver_id in self.drivers:
                    del self.drivers[driver_id]

    def notify_drivers(self, ride_id):
        with self.lock:
            ride = self.active_rides.get(ride_id)
            if not ride:
                return
            ride_request = uber_pb2.RideRequest(
                rider_id=ride['rider_id'],
                location=ride['location'],
                destination=ride['destination']
            )
            for driver_id, driver_info in self.drivers.items():                
                driver_info['queue'].append((ride_id, ride_request))
        print(f"Notified drivers about ride {ride_id}")
        
    def notify_rider(self, rider_id, ride_id, status, message):
        if rider_id in self.rider_streams:
            try:
                self.rider_streams[rider_id].put(uber_pb2.RideStatusUpdate(
                    ride_id=ride_id,
                    status=status,
                    message=message
                ))
            except Exception as e:
                print(f"Error notifying rider {rider_id}: {e}")
                
    def SubscribeToRideUpdates(self, request, context):
        rider_id = request.rider_id
        queue = Queue()
        self.rider_streams[rider_id] = queue
        try:
            while True:
                update = queue.get()
                yield update
        except Exception as e:
            print(f"Rider {rider_id} disconnected: {e}")
        finally:
            self.rider_streams.pop(rider_id, None)

    def AcceptRide(self, request, context):
        with self.lock:
            ride = self.active_rides.get(request.ride_id)
            if not ride or ride['status'] != 'Pending':
                return uber_pb2.AcceptRideResponse(
                    success=False,
                    message='Ride not available.'
                )
                
            timer = self.ride_timers.pop(request.ride_id, None)
            if timer:
                timer.cancel()
               
            # Cancel the auto-rejection timer 
            ride['status'] = 'Accepted'
            ride['driver_id'] = request.driver_id
            self.drivers[request.driver_id]['status'] = 'ON_RIDE'
                        
            # Notify the rider
            self.notify_rider(ride['rider_id'], request.ride_id, 'Accepted', f"Your ride has been accepted by driver {request.driver_id}")
        print(f"Ride {request.ride_id} accepted by driver {request.driver_id}")
        return uber_pb2.AcceptRideResponse(
            success=True,
            message='Ride accepted.'
        )

    def RejectRide(self, request, context):
        with self.lock:
            ride = self.active_rides.get(request.ride_id)
            if not ride or ride['status'] != 'Pending':
                return uber_pb2.RejectRideResponse(
                    success=False,
                    message='Ride not available.'
                )                        
        print(f"Ride {request.ride_id} rejected by driver {request.driver_id}")
        return uber_pb2.RejectRideResponse(
            success=True,
            message='Ride rejected.'
        )
        
    def CompleteRide(self, request, context):
        with self.lock:
            ride = self.active_rides.get(request.ride_id)
            if not ride or ride['status'] != 'Accepted' or ride['driver_id'] != request.driver_id:
                return uber_pb2.RideCompletionResponse(
                    success=False,
                    message='Ride not available or not assigned to this driver.'
                )
            
            ride['status'] = 'Completed'
            self.drivers[request.driver_id]['status'] = 'AVAILABLE'
            
            # Notify the rider
            self.notify_rider(ride['rider_id'], request.ride_id, 'Completed', f"Your ride has been completed by driver {request.driver_id}")
        
        print(f"Ride {request.ride_id} completed by driver {request.driver_id}")
        return uber_pb2.RideCompletionResponse(
            success=True,
            message='Ride completed successfully.'
        )

def serve():
    # Load server's certificate and key
    with open('server.crt', 'rb') as f:
        server_certificate = f.read()
    with open('server.key', 'rb') as f:
        server_private_key = f.read()

    # Load the trusted CA's certificate to verify client certificates
    with open('ca.crt', 'rb') as f:
        trusted_ca = f.read()

    # Setup server credentials for mTLS
    server_credentials = grpc.ssl_server_credentials(
        [(server_private_key, server_certificate)],
        root_certificates=trusted_ca,  # Verify client certificates
        require_client_auth=True        # Enforce client-side authentication
    )

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    uber_pb2_grpc.add_RideSharingServicer_to_server(RideSharingServicer(), server)

    # Use secure port with mTLS
    server.add_secure_port('127.0.0.1:50054', server_credentials)
    
    server.start()
    print("Server started with mTLS on port 50054.")
    try:
        while True:
            time.sleep(86400)  
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()
