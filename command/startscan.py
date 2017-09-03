import spur
import time
import nmap
import shutil

''' Settings '''

default_username = 'pi'
default_password = 'raspberry'
image_path = '/tmp/'
filname_prefix = 'capture_'
jpeg_quality = '99'
images_pr_session = 2
output_path = './captures/'

''' Service functions '''


def discover_pis() -> [str]:
    raspberrys = []
    nm = nmap.PortScanner()
    scan = nm.scan(hosts='192.168.66.0/24', arguments='-sn', sudo=True)
    for unit_ip, unit_values in scan['scan'].items():
        try:
            if next(iter(unit_values['vendor'].values())) in 'Raspberry Pi Foundation':
                raspberrys.append(unit_ip)
        except StopIteration:
            pass  # ignore results without MAC
    return raspberrys


def gen_filepath(session_name: str) -> str:
    return image_path + session_name + '/'


def gen_filename(devicename: str) -> str:
    return filname_prefix + devicename + '_%d.jpg'


def gen_path_and_name(devicename, session_name) -> str:
    return gen_filepath(session_name) + gen_filename(devicename)


def gen_capture_command(devicename: str, session_name: str) -> [str]:
    # USR1 will capture, USR2 will shut down
    return ['raspistill', '-o', gen_path_and_name(devicename, session_name), '-dt', '-t', '0', '-q', jpeg_quality, '-s']


def connect_device(ip: str) -> spur.ssh.SshShell:
    print('connecting to ' + ip)
    shell = spur.SshShell(hostname=ip, username=default_username, password=default_password,
                          missing_host_key=spur.ssh.MissingHostKey.accept)
    return shell


def connect_devices(ips: [str]) -> [spur.ssh.SshShell]:
    connections = []
    index = 0
    for ip in ips:
        connection = connect_device(ip)
        connection.ident = 'device' + str(index)
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


def get_filelist(connection: spur.ssh.SshShell, filepath: str) -> [str]:
    result = connection.run(['ls'], cwd=filepath)  # get list of captured files
    files = result.output.decode("utf-8").strip('\n').split('\n')
    return files


def setup_for_capture(connections, session_name: str) -> [spur.ssh.SshProcess]:
    raspistills = []

    # cleanup all devices
    for connection in connections:
        # TODO: set system clock
        connection.run(['killall', '-w', '-s', 'USR2', 'raspistill'], allow_error=True)  # kill old sessions
        connection.run(['rm', '-rf', gen_filepath(session_name)], allow_error=True)  # remove old session with same name
        connection.run(['mkdir', gen_filepath(session_name)])  # create folder for captures

        # start raspistill
        print('Connecting to ' + connection.ident)
        raspistills.append(connection.spawn(gen_capture_command(connection.ident, session_name), store_pid=True))

    print('waiting for devices to settle')
    time.sleep(1)  # allow raspistill to shut down
    return raspistills


def copy_remote_file(connection: spur.ssh.SshShell, remote_path: str, filename: str, output_path: str) -> None:
    with connection.open(remote_path + filename, "rb") as remote_file:
        with open(output_path + filename, "wb") as local_file:
            shutil.copyfileobj(remote_file, local_file)


''' **** Here starts the application **** '''

print('Discovering Rasperry PIs')

# detect devices
devices = discover_pis()

# connect to devices
print('Initializing. Connecting to ' + str(len(devices)) + ' devices.')
connections = connect_devices(devices)

print('Enter name of session')
image_session_name = 'test'  # input()
print('capturing session : ' + image_session_name)

print('setting up capture environment')
capture_sessions = setup_for_capture(connections, image_session_name)

print('ready to start capturing!')
for capture in range(0, images_pr_session):
    print('capturing: ' + str(capture))
    capture_images(capture_sessions)
    time.sleep(1)

print('Getting files from remote devices')
for connection in connections:
    files = get_filelist(connection, gen_filepath(image_session_name))
    for filename in files:
        print(connection.ident + ':' + filename + ' ...')
        copy_remote_file(connection, gen_filepath(image_session_name), filename, output_path)

print('done capturing')
end_sessions(capture_sessions)
