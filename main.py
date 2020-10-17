#!/usr/bin/env python3

from requests import Session, RequestException
from contextlib import closing
from lxml import html
from re import sub, search
import json
from time import sleep
from cmd import Cmd
from getpass import getpass
import signal

LOGIN_URL = 'https://mc.shockbyte.com/index.php?r=site/login'
CONSOLE_URL = 'https://mc.shockbyte.com/index.php?r=server/log'
VIEW_URL = 'https://mc.shockbyte.com/index.php?r=server/view'
VIEW_PLAYER_URL = 'https://mc.shockbyte.com/index.php?r=player/view'

class Console(Cmd):
    prompt = "Multicraft > "

    def __init__(self, session, server_id, server_name='Multicraft'):
        self.session = session
        self.server_id = server_id
        self.server_name = server_name
        self.prompt = f"{server_name} > "
        super().__init__()

    def do_exit(self, inp):
        return True

    def default(self, inp):
        send_console(self.session, self.server_id, inp)


def session_post(url, session, payload):
    try:
        with closing(session.post(url, data=payload)) as resp:
                return resp
    except RequestException as e:
        print('Error during requests to {0} : {1}'.format(url, str(e)))

def session_get(url, session):
    try:
        resp = session.get(url, stream=True)
        session.close()
        return resp

    except RequestException as e:
        print('Error during requests to {0} : {1}'.format(url, str(e)))
        session.close()
        return None

def dump(obj):
   for attr in dir(obj):
       if hasattr( obj, attr ):
           print( "obj.%s = %s" % (attr, getattr(obj, attr)))

def extract_server_id_from_url(url):
    res = search('&id=[0-9]+', url)
    return res[0][4:]

def login(session, username, password):
    print("Logging in...")
    session.get(LOGIN_URL)

    payload = {
        "LoginForm[name]": username,
        "LoginForm[password]": password,
        "LoginForm[rememberMe]": 0,
        "LoginForm[ignoreIp]": 0,
        "yt": "Login"
    }
    res = session.post(LOGIN_URL, data=payload)
    tree = html.fromstring(res.content)
    error_message = tree.xpath("//div[@class='errorMessage']/text()")

    if len(error_message) > 0 and error_message[0] != '':
        print(error_message[0])
        exit(1)
    else:
        print("Successfully logged in!")
        return extract_server_id_from_url(res.url)

def get_console(session, server_id, log_seq=0):
    token = session.cookies.get('YII_CSRF_TOKEN')
    payload = {
        'ajax': 'refresh',
        'type': 'all',
        'log_seq': log_seq,
        'YII_CSRF_TOKEN': token
    }

    url = f"{CONSOLE_URL}&id={server_id}"
    res = session.post(url, data=payload)
    status_detail = json.loads(res.content.decode('utf-8'))

    return status_detail

def send_console(session, server_id, command):
    token = session.cookies.get('YII_CSRF_TOKEN')
    payload = {
        'ajax': 'command',
        'YII_CSRF_TOKEN': token,
        'command': command
    }

    url = f"{CONSOLE_URL}&id={server_id}"
    session.post(url, data=payload)

def stream_console(session, server_id, log_seq=0):
    global should_stream_console
    should_stream_console = True
    while should_stream_console:
        status = get_console(session, server_id, log_seq)
        if (log_seq != status['log_seq']):
            log_seq = status['log_seq']
            print(status['log'], end='')

        sleep(1)

def get_status(session, server_id):
    token = session.cookies.get('YII_CSRF_TOKEN')
    payload = {
        'ajax': 'refresh',
        'type': 'all',
        'log_seq': 0,
        'YII_CSRF_TOKEN': token
    }

    url = f"{VIEW_URL}&id={server_id}"
    res = session.post(url, data=payload)
    details = json.loads(res.content.decode('utf-8'))

    players_tree = html.fromstring(details['players'])
    player_elements = players_tree.xpath('//div/a/span')

    players = []
    for player_element in player_elements:
        player_name = player_element.xpath('text()')[0]
        player_link = player_element.getparent().xpath('@href')[0]
        player_id = search('[0-9]+$', player_link)[0]
        players.append({
            'name': player_name,
            'id': player_id
        })

    return {
            'players': players,
            'status': details['status']
    }

def main_menu(session, server_id):
    def exit_console(sig, frame):
        global should_stream_console
        if should_stream_console:
            should_stream_console = False
        else:
            exit(2)

    while True:
        print("=======Main Menu=======")
        print("1. View Console")
        print("2. Send Console Command")
        print("3. View Status")
        print("4. Exit")

        num = input("Option: ")

        if num.isnumeric():
            num = int(num)
        else:
            print(f"Invalid option: '{num}'")
            continue

        if num == 1:
            signal.signal(signal.SIGINT, exit_console)
            stream_console(session, server_id)
        elif num == 2:
            console = Console(session, server_id)
            console.cmdloop()
        elif num == 3:
            info = get_status(session, server_id)
            while True:
                print('=========Status=========')
                print(info['status'])

                print('-------Player List-------')
                i = 1
                for player in info['players']:
                    print(f"{i}. {player['name']} ({player['id']})")
                    i += 1
                print(f'{i}. Go Back')

                ans = input("Option: ")
                if ans.isdigit():
                    ans = int(ans)
                    if ans == i:
                        break
                    elif ans > 0 and ans <= len(info['players']):
                        player_id = info['players'][ans - 1]['id']
                        print(f"{VIEW_PLAYER_URL}&id={player_id}")
                        break
        elif num == 4:
            exit(0)
        else:
            print(f"Invalid option: '{num}'")
            continue


def main():
    session = Session()

    username = input("Enter username: ")
    password = getpass("Enter password: ")
    server_id = login(session, username, password)
    main_menu(session, server_id)


if __name__ == '__main__':
    main()
