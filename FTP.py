import Argparser
import os
import os.path
import re
import socket
import sys
import getpass
import time

PASSIVE_MODE = False
ARGS = None

UNITS = ['B/s', 'KB/s', 'MB/s', 'GB/s']

TIMEOUT = 600


def main():
    global ARGS
    ARGS = Argparser.parse_args()

    if ARGS.passive:
        global PASSIVE_MODE
        PASSIVE_MODE = True

    addr = None
    if ARGS.address is not None:
        addr = (ARGS.address, ARGS.port)
    else:
        address = input("Input address: ")
        port = input('Input port: ')
        if port != '':
            addr = (address, port)
        else:
            addr = (address, ARGS.port)
    print('Connecting to ' + str(addr[0]) + ':' + str(addr[1]))

    sock = socket.socket()
    sock.settimeout(TIMEOUT)
    data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock = connect(addr)
        print(receive_full_reply(sock))

        data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        data_sock.settimeout(TIMEOUT)
        data_sock.close()

        if ARGS.get or ARGS.put:
            batch_mode(sock, data_sock)

        login(sock, None, None, None)
        run(sock, data_sock)

    except ConnectionError as error:
        print(error)
        sys.exit(1)

    except Exception as error:
        print(error)
        run(sock, data_sock)


def run(control_sock, data_sock):
    while True:
        try:
            message = input('>')

            query = message.split(' ')

            str_command = query[0].lower()

            argument = None
            option = None

            if len(query) == 2:
                argument = query[1]

            if len(query) > 2:
                argument = query[1]
                i = 1
                while argument.endswith('\\'):
                    i += 1
                    if i == len(query):
                        break
                    argument = argument[:-1] + ' ' + query[i]
                i += 1
                if i < len(query):
                    option = query[i]
                    while option.endswith('\\'):
                        i += 1
                        if i == len(query):
                            break
                        option = option[:-1] + ' ' + query[i]

            command = COMMANDS.get(str_command, invalid)

            result = command(control_sock, data_sock, argument, option)
            if result is not None:
                data_sock = result

        except ConnectionError as error:
            raise error

        except Exception as error:
            print(error)


def receive_full_reply(sock):
    reply = ''
    tmp = sock.recv(65535).decode('UTF-8')
    reply += tmp

    first_reply_reg = re.compile(r'^\d\d\d .*$', re.MULTILINE)

    while not re.findall(first_reply_reg, tmp):
        try:
            tmp = sock.recv(65535).decode('UTF-8')
            reply += tmp

        except TimeoutError:
            break

    return reply


def receive_full_data(sock):
    reply = b''
    sock.settimeout(TIMEOUT)

    while True:
        try:
            tmp = sock.recv(65535)
            if not tmp:
                break

        except TimeoutError:
            break

        finally:
            reply += tmp

    return reply


def send_command(sock, command, argument=None):
    if argument is None:
        query = command + '\r\n'
    else:
        query = command + ' ' + argument + '\r\n'

    sock.sendall(bytes(query, 'utf-8'))


def batch_mode(control_sock, data_sock):
    global ARGS
    try:
        login(control_sock, data_sock, 'ftp', 'ftp')

        if ARGS.get:
            retr(control_sock, data_sock, ARGS.remote, ARGS.local)
        else:
            stor(control_sock, data_sock, ARGS.local, ARGS.remote)

    except Exception as error:
        print(error)

    finally:
        i_quit(control_sock)


def connect(host):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(TIMEOUT)

    try:
        addr = socket.getaddrinfo(host[0], host[1])
        sock.connect(addr[0][4])

    except socket.gaierror:
        raise ConnectionError('Address fetching failed: ' + str(host[0]) + ':' + str(host[1]))

    except Exception as error:
        raise ConnectionError('Connection error: ' + str(error))

    return sock


def login(control_sock, data_sock, name, passwd):
    if name is None:
        name = input('Username: ')

    send_command(control_sock, 'USER', name)
    reply = receive_full_reply(control_sock)

    print(reply)

    password(control_sock, None, passwd, None)


def password(control_sock, data_sock, passw, extra_arg):
    if passw is None:
        passw = getpass.getpass()

    send_command(control_sock, 'PASS', passw)
    reply = receive_full_reply(control_sock)

    print(reply)

    if not re.match(r'2\d\d', reply):
        raise ValueError("Incorrect login. Sign in with command 'user'")


def cwd(control_sock, data_sock, path, extra_arg):
    send_command(control_sock, 'CWD', path)
    reply = receive_full_reply(control_sock)

    print(reply)


def server_help(control_sock, data_sock, argument, extra_arg):
    send_command(control_sock, 'HELP')
    reply = receive_full_reply(control_sock)

    print(reply)


def i_list(control_sock, data_sock, argument, extra_arg):
    sock = None
    if PASSIVE_MODE:
        data_sock = pasv(control_sock)
    else:
        sock = port(control_sock)

    send_command(control_sock, 'LIST', argument)
    reply = receive_full_reply(control_sock)

    print(reply)

    if not PASSIVE_MODE:
        data_sock, address = sock.accept()

    if data_sock is None:
        raise ConnectionError('Data connection is required')

    data = receive_full_data(data_sock).decode('UTF-8')

    print(data)

    data_sock.close()

    reply = receive_full_reply(control_sock)

    print(reply)


def name_list(control_sock, data_sock=None, argument=None, extra_arg=None, do_print=False):
    sock = None
    if PASSIVE_MODE:
        data_sock = pasv(control_sock)
    else:
        sock = port(control_sock)

    send_command(control_sock, 'NLST', argument)
    reply = receive_full_reply(control_sock)

    if do_print:
        print(reply)

    if not PASSIVE_MODE:
        data_sock, address = sock.accept()

    if data_sock is None:
        raise ConnectionError('Data connection is required')

    data = receive_full_data(data_sock).decode('UTF-8')

    if do_print:
        print(data)

    data_sock.close()

    reply = receive_full_reply(control_sock)

    if do_print:
        print(reply)
    return data.rstrip('\r\n').split('\r\n')


def pasv(control_sock, data_sock=None, argument=None, extra_arg=None):
    send_command(control_sock, 'PASV')
    reply = receive_full_reply(control_sock)

    print(reply)

    res = re.findall(r'(\d+),(\d+),(\d+),(\d+),(\d+),(\d+)', reply)[0]

    ip_address = '.'.join(res[:4])
    port_number = int(res[4]) * 256 + int(res[5])
    parameters = (ip_address, port_number)

    data = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    data.connect(parameters)

    PASSIVE_MODE = True

    return data


def port(control_sock, data_sock=None, argument=None, extra_argument=None):
    ip_address = control_sock.getsockname()[0]

    sock = socket.socket()
    sock.bind(('', 0))
    sock.listen()

    local_port = sock.getsockname()[1]
    port_whole, port_factor = local_port // 256, local_port % 256
    query = 'PORT ' + ip_address.replace('.', ',') + ',' + str(port_whole) + ',' + str(port_factor)

    send_command(control_sock, query)
    reply = receive_full_reply(control_sock)

    print(reply)

    return sock


def pwd(control_sock, data_sock, argument, extra_arg):
    send_command(control_sock, 'PWD')
    reply = receive_full_reply(control_sock)

    print(reply)


def i_quit(control_sock, data_sock=None, argument=None, extra_arg=None):
    send_command(control_sock, 'QUIT')
    reply = receive_full_reply(control_sock)

    print(reply)

    sys.exit(0)


def get_size(control_sock, data_sock, filename, path_value, do_print=True):
    send_command(control_sock, 'SIZE', filename)
    reply = receive_full_reply(control_sock)

    if do_print:
        print(reply)

    result = re.findall(r' (\d+)', reply)

    return int(result[0])


def stat(control_sock, data_sock, argument, extra_arg):
    send_command(control_sock, 'STAT')
    reply = receive_full_reply(control_sock)

    print(reply)


def syst(control_sock, data_sock, argument, extra_arg):
    send_command(control_sock, 'SYST')
    reply = receive_full_reply(control_sock)

    print(reply)


def i_type(control_sock, data_sock, name, extra_arg):
    send_command(control_sock, 'TYPE', name)
    reply = receive_full_reply(control_sock)

    print(reply)


def is_directory(control_sock, name):
    send_command(control_sock, 'PWD')
    start_dir = re.findall(r'"(.+)"', receive_full_reply(control_sock))[0]

    send_command(control_sock, 'CWD', name)
    reply_code = receive_full_reply(control_sock)[:3]
    if reply_code == '550':
        return False
    else:
        send_command(control_sock, 'CWD', start_dir)
        receive_full_reply(control_sock)
        return True


def retr_dir(control_sock, name, destination_dir):
    destination_dir = os.path.normpath(destination_dir + '/' + os.path.basename(name))
    if not os.path.exists(destination_dir):
        os.mkdir(destination_dir)
    for item in name_list(control_sock, argument=name, do_print=False):
        item_path = name + '/' + item
        retr(control_sock, None, item_path, destination_dir)


def count_speed(passed, start_time, current):
    if current - start_time == 0:
        average = 0
    else:
        average = passed / (current - start_time)
    unit_index = 0
    while average > 1024:
        average /= 1024
        unit_index += 1
    return '{:>6.1f}{}'.format(average, UNITS[unit_index])


def print_progress(iteration, total, speed='', prefix='Progress:', suffix='Complete', decimals=1, bar_length=30):
    format_string = "{0:." + str(decimals) + "f}"
    if float(total) == 0:
        percent = format_string.format(100)
        filled_length = int(round(bar_length))
    else:
        percent = format_string.format(100 * (iteration / float(total)))
        filled_length = int(round(bar_length * iteration / float(total)))
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    sys.stdout.write('\r{} [{}] {}{} {}; {}'.format(prefix, bar, percent, '%', suffix, speed))
    if iteration == total:
        sys.stdout.write('\n\n')
    sys.stdout.flush()


def retr(control_sock, data_sock, remote_file, destination_dir):
    if remote_file is None:
        raise ValueError("Please input remote file name")

    if destination_dir is None:
        if not os.path.exists(os.path.normpath(str(os.getcwd()) + '/downloads')):
            os.mkdir(os.path.normpath(str(os.getcwd()) + '/downloads'))
        destination_dir = os.path.normpath(str(os.getcwd()) + '/downloads/')

    if is_directory(control_sock, remote_file):
        retr_dir(control_sock, remote_file, destination_dir)
        return

    # dir_name = os.path.dirname(destination_dir)
    # while not os.path.exists(dir_name):
    #     os.makedirs(dir_name)

    i_type(control_sock, None, 'I', None)
    file_size = get_size(control_sock, None, remote_file, None, False)

    sock = None
    if PASSIVE_MODE:
        data_sock = pasv(control_sock)
    else:
        sock = port(control_sock)

    send_command(control_sock, 'RETR', remote_file)
    reply = receive_full_reply(control_sock)

    print(reply)

    if not reply.startswith('150'):
        raise FileNotFoundError("Couldn't download file " + str(remote_file))

    if not PASSIVE_MODE:
        data_sock, address = sock.accept()

    local_file = os.path.normpath(destination_dir + '/' + os.path.basename(remote_file))
    # local_file_name = os.path.basename(os.path.normpath(destination_dir + '/' + remote_file))
    result_file = open(local_file, 'wb')

    received = 0

    print_progress(received, file_size)
    start_time = time.time()

    while file_size > received:
        data = data_sock.recv(65535)
        if not data:
            break
        result_file.write(data)

        received += len(data)

        speed = count_speed(received, start_time, time.time())
        print_progress(received, file_size, speed)

    result_file.close()

    data_sock.close()
    reply = receive_full_reply(control_sock)

    print(reply)


def stor(control_sock, data_sock, local_file, remote_name):
    if local_file is None:
        local_file = input("Please input local file name: ")

    if remote_name is None:
        remote_name = os.path.basename(local_file)

    file_size = os.path.getsize(local_file)

    i_type(control_sock, None, 'I', None)

    sock = None
    if PASSIVE_MODE:
        data_sock = pasv(control_sock)
    else:
        sock = port(control_sock)

    send_command(control_sock, 'STOR', remote_name)
    reply = receive_full_reply(control_sock)

    print(reply)

    if reply[0] == '5':
        return

    if not PASSIVE_MODE:
        data_sock, address = sock.accept()

    file = open(local_file, 'rb')
    sent = 0

    print_progress(sent, file_size)
    start_time = time.time()

    while file_size > sent:
        data = file.read(65535)
        data_sock.sendall(data)

        sent += len(data)

        speed = count_speed(sent, start_time, time.time())
        print_progress(sent, file_size, speed)

    file.close()
    data_sock.close()
    reply = receive_full_reply(control_sock)

    print(reply)


def help(arg1, arg2, arg3, arg4):
    print("""Supported commands:
    \tcwd \tcd \tdir 
    \thelp\tlist\tls  
    \tpass\tpasv\tport
    \tpwd \tquit\tretr
    \tsize\tstat\tstor
    \tsyst\ttype\tuser
    \tget \tput \t?
    """)


def invalid(arg1, arg2, arg3, arg4):
    print("Invalid command. Use 'help' command or '/?' for internal help")


COMMANDS = {
    'cwd': cwd,
    'cd': cwd,
    'help': server_help,
    'dir': i_list,
    'list': i_list,
    'ls': i_list,
    'nlst': name_list,
    'pass': password,
    'pasv': pasv,
    'port': port,
    'pwd': pwd,
    'quit': i_quit,
    'exit': i_quit,
    'retr': retr,
    'get': retr,
    'size': get_size,
    'stat': stat,
    'stor': stor,
    'put': stor,
    'syst': syst,
    'type': i_type,
    'user': login,
    '?': help
}

if __name__ == '__main__':
    main()
