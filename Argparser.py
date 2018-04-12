import argparse


def parse_args():
    parser = argparse.ArgumentParser(prog='ftp.py', description='Connects to ftp server')
    group = parser.add_mutually_exclusive_group()
    parser.add_argument('address', help='address to connect', nargs='?', default=None)
    parser.add_argument('port', help='port', nargs='?', type=int, default=21)
    # parser.add_argument('user', help='user', nargs='?', type=str, default=None)
    # parser.add_argument('password', help='password', nargs='?', type=str, default=None)
    parser.add_argument('--passive', help='use passive mode instead of active', action='store_true')
    group.add_argument('--get', '-g', help='dowload file', action='store_true')
    group.add_argument('--put', '-p', help='upload file', action='store_true')
    parser.add_argument('--local', '-l', help='local file to handle')
    parser.add_argument('--remote', '-r', help='remote file to handle')
    return parser.parse_args()
