import spur
import time
import nmap

default_username = 'pi'
default_password = 'raspberry'
image_path='/tmp/'
jpeg_quality = '99'

def discover_pis() -> [str]:
    raspberrys=[]
    nm = nmap.PortScanner()
    scan=nm.scan(hosts='192.168.66.0/24', arguments='-sn', sudo=True)
    for unit_ip, unit_values in scan['scan'].items():
        try:
            if next(iter(unit_values['vendor'].values())) in 'Raspberry Pi Foundation':
                raspberrys.append(unit_ip)
        except StopIteration:
            pass # ignore results without MAC
    return raspberrys


def gen_filepath(session_name: str) -> str:
    return image_path + session_name + '/'

def gen_filename(devicename: str) -> str:
    return 'capture_'+devicename+'_%d.jpg'

def gen_path_and_name(devicename, session_name) -> str:
    return gen_filepath(session_name) + gen_filename(devicename)

def gen_capture_command(devicename: str, session_name: str) -> [str]:
    # USR1 will capture, USR2 will shut down
    return ['raspistill', '-o', gen_path_and_name(devicename, session_name), '-dt', '-t', '0', '-q', jpeg_quality, '-s']

def connect_device(ip: str) -> spur.ssh.SshShell:
    print('connecting to ' + ip) 
    shell = spur.SshShell(hostname=ip, username=default_username, password=default_password, missing_host_key=spur.ssh.MissingHostKey.accept)
    return shell

def connect_devices(ips: [str]) -> [spur.ssh.SshShell]:
    connections = []
    index=0
    for ip in ips:
        connection = connect_device(ip)
        connection.ident='device' + str(index)
        connections.append(connection)
        index = index + 1
    return connections

def capture_images(sessions: [spur.ssh.SshProcess]) -> None:
    for session in sessions:
        session.send_signal('SIGUSR1')

def end_sessions(sessions: [spur.ssh.SshProcess]) -> None:
    for session in sessions:
        session.send_signal('SIGUSR2')

    # Await terminations
    for session in sessions:
        session.wait_for_result()

#def multispawn(connections, command):
#    processes = []
#    for connection in connections:
#        process = connection.spawn(command(connection.ident), store_pid=True)
#        processes.append(process)
#    return processes

#def multirun(connections, command):
#    for connection in connections:
#        process = connection.run(command(connection.ident))
#        processes.append(process)
#    return processes

def setup_for_capture(connections, session_name: str) -> [spur.ssh.SshProcess]:
    raspistills=[]

    #cleanup all devices
    for connection in connections:
        connection.run(['killall', '-w' ,'-s', 'USR2', 'raspistill'], allow_error=True) # kill old sessions
        connection.run(['rm', '-rf', gen_filepath(session_name)], allow_error=True) # remove old session with same name
        connection.run(['mkdir', gen_filepath(session_name)]) # create folder for captures

        #start raspistill
        print('Connecting to ' + connection.ident)
        raspistills.append(connection.spawn(gen_capture_command(connection.ident, session_name), store_pid=True))

    print('waiting for devices to settle')
    time.sleep(1) # allow raspistill to shut down
    return raspistills

#detect devices
devices = discover_pis()

# connect to devices
print('Initializing. Connecting to ' + str(len(devices)) + ' devices.')
connections = connect_devices(devices)

#print ('now waiting for a bit...')
#time.sleep(5) # await connections to establish

print('Enter name of session')
image_session_name = 'test' #input()
print('capturing session : ' + image_session_name)

print('setting up capture environment')
capture_sessions = setup_for_capture(connections, image_session_name)

print('ready to start capturing!')
for capture in range(1, 10):
    print('capturing: ' + str(capture))
    capture_images(capture_sessions)
    time.sleep(1)

print('done capturing')
end_sessions(capture_sessions)

#for ip in devices:
#    current_device = connect_device(ip)
#    current_device.run(['raspistill', '-o', '/tmp/out.png'])
#    in_file = current_device.open('/tmp/out.png', 'rb')
#    out_file = open('/tmp/test.png', mode='wb')
#    data=in_file.read()
#    out_file.write(data)



