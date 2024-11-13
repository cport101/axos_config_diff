#!/usr/bin/env python3
"""
TEST
============================
__title__  = "TEST DIFF TEMPLATE BY HEIR."
__author__ = "Charles F. Port"
__copyright__ = "Copyright 25SEPT24"
__credits__ = ["Charles F. Port"]
__license__ = "MIT"
__version__ = "0.0.0"
__modified__ = 03OCT24
__maintainer__ = "TBD"
__email__ = "cport@rawbw.com"
__status__ = "Test"

TERMS AND CONDITIONS FOR USE
============================
1. This software is provided by the author "as is" and any express or implied
warranties, including, but not limited to, the implied warranties of
marketability and fitness for a particular purpose are disclaimed. In no
event shall the author be liable for any direct, indirect, incidental,
special, exemplary, or consequential damages (including, but not limited to,
procurement of substitute goods or services; loss of use, data, or profits; or
business interruption) however caused and on any theory of liability, whether
in contract, strict liability, or tort (including negligence or otherwise)
arising in any way out of the use of this software, even if advised of the
possibility of such damage.

2. No Support. Neither Author (nor Calix, Inc.) will provide support.

3. USE AT YOUR OWN RISK
===========================
END OF TERMS AND CONDITIONS

Changes:
========
24SEPT24:
--------
0. Conception
--------
03OCT24
1. Added menu
========
"""
# =============================================================
# IMPORT LIBS
# =============================================================
from difflib import SequenceMatcher
from difflib import unified_diff
import logging
import csv
import time
import tempfile
import os
import re
import sys
from diffplus import IndentedConfig, IncrementalDiff
from getpass import getpass
from io import StringIO
from logging.config import dictConfig
from netmiko import ConnectHandler
from paramiko import SSHClient, AutoAddPolicy, SSHException
from paramiko_expect import SSHClientInteraction
from pyats.log.utils import banner
from tabulate import tabulate
import conf_diff
import jinja2
import textfsm
import yaml

# ------------------------------------------------------------
# FIXED VARIABLES/TEXTFSM TEMPLATES [TEXT GENERATION FROM CLI]
# ------------------------------------------------------------
SHOWCARDTMP = r"""Value SLOT (\d\/\d)
Value CARD (\w+\d+)
Value CSTATE (.*\s\bService\b)
Value CTYPE (\S+)
Value MISC (.*?)
Value STATE (\s|\(.*\))
Value MODEL (\w+\d+|\w\d\-\d\_......)
Value SERIAL (\d+)
Value SOFTWARE (\S+\-.*)

Start
  ^${SLOT}\s+${CARD}\s+${CSTATE}\s+${CTYPE}${MISC}${STATE}\s+${MODEL}\s+${SERIAL}\s+${SOFTWARE} -> Record
"""

# ------------------------------------------------------------
# INPUT VARS
# ------------------------------------------------------------
ip_addr = input("Enter Hostanme or IP Address: ")
user_name = input("Enter ssh username: ")

# ------------------------------------------------------------
#  CREDENTIALS
# ------------------------------------------------------------
device_netmiko = {
    "device_type": "vyos",
    "host": ip_addr,
    "username": user_name,
    "password": getpass(),
    "fast_cli": False,
}
passwd = device_netmiko["password"]
# ------------------------------------------------------------
device_paramiko = {
    "hostname": ip_addr,
    "username": user_name,
    "password": passwd,
    "port": 22,
}

# --------------------------------------------------
# DISABLE PARAMIKO LOGGER
# --------------------------------------------------
paramiko_logger = logging.getLogger("paramiko.transport")
paramiko_logger.disabled = True


# --------------------------------------------------
# [FUNCTION 00] Function to setup && start logging
# --------------------------------------------------
def check_terminal_size(min_columns=200, min_lines=50):
    """Checks if the terminal size meets the minimum requirements."""
    try:
        columns, lines = os.get_terminal_size()
    except OSError:
        return False  # Unable to get terminal size
    return columns >= min_columns and lines >= min_lines


# --------------------------------------------------
# [FUNCTION 0] Function to setup && start logging
# --------------------------------------------------
def init_logger():
    """DEFINE LOGGER FUNCTIONS"""
    logging_config = dict(
        version=1,
        formatters={
            'f': {
                'format': '%(asctime)s %(name)-12s %(levelname)-8s %(message)s'
            }
        },
        handlers={
            'h': {
                'class': 'logging.StreamHandler',
                'formatter': 'f',
                'level': logging.INFO
            }
        },
        root={
            'handlers': ['h'],
            'level': logging.DEBUG,
        },
    )
    dictConfig(logging_config)
    logger = logging.getLogger()
    if logger:
        return True


# ------------------------------------------------------------
#  FUNCTION [1] PARSE CLI OUTPUT WITH TEXTFSM
# ------------------------------------------------------------
def parse_fsm(template, output):
    """
    USE Text FSM to reformat CLI Output
    """
    tmp = tempfile.NamedTemporaryFile(delete=False)
    with open(tmp.name, "w") as f_tmp0:
        f_tmp0.write(template)
    with open(tmp.name, "r") as f_tmp0:
        fsm = textfsm.TextFSM(f_tmp0)
        fsm_results = fsm.ParseText(output)
        parsed = tabulate(fsm_results, headers=fsm.header)
        parsed_dict = [dict(zip(fsm.header, pr)) for pr in fsm_results]
    return parsed, parsed_dict


# ------------------------------------------------------------
#  FUNCTION [2] GEN JINGA2
# ------------------------------------------------------------
def gen_template_config(yml_data, jinja_data):
    """ RENDER JINJA2 """
    templateLoader = jinja2.FileSystemLoader('/', followlinks=True)
    templateEnv = jinja2.Environment(loader=templateLoader)
    TEMPLATE_FILE = jinja_data
    template = templateEnv.get_template(TEMPLATE_FILE)
    with open(yml_data, 'r') as stream0:
        cfg_data = yaml.safe_load(stream0)
        out_put = template.render(cfg_data)
    return out_put


# ------------------------------------------------------------
#  FUNCTION [3] NETMIKO SSH
# ------------------------------------------------------------
def ssh_execute_cmd(command, login):
    """ SSH GET """
    with ConnectHandler(**login) as ssh_connect:
        output = ssh_connect.send_command(command, delay_factor=2)
    return output


# ------------------------------------------------------------
#  FUNCTION [4] USE PARAMIKO EXPECT
# ------------------------------------------------------------
def ssh_expect(login):
    """ SSH EXPECT """
    # ------------------------------------------------
    # FUNCTION VARS
    # ------------------------------------------------
    root_prompt = '.*# '
    ques_mark = '\x3F'
    cmd_n0 = ('terminal screen-length 250')
    cmd_n1 = (f'show running-config {ques_mark}')
    special_prompt = (f'{root_prompt}show running-config ')
    try:
        ssh = SSHClient()
        ssh.set_missing_host_key_policy(AutoAddPolicy())
        #ssh.connect( hostname = host_name, username = user_name,
        #             password = pass_word, port = port, allow_agent=False)
        ssh.connect(**login, allow_agent=False)
        with SSHClientInteraction(ssh, timeout=10, display=False) as interact:
            interact.send('\n')
            interact.expect(root_prompt)
            ############################
            interact.send(cmd_n0)
            interact.expect(root_prompt)
            ############################
            interact.send(cmd_n1)
            interact.expect(special_prompt)
            ############################
            results = interact.current_output_clean
            ############################
        ssh.close()
    except SSHException as err:
        print(str(err).encode())
    return results


# ------------------------------------------------------------
#  FUNCTION [5] CREATE A CONFIG HIERARCHY
# ------------------------------------------------------------
def create_hierarchy(raw_results):
    """ CREATE A CONFIG HIERARCHY"""
    new_data = list(csv.DictReader(StringIO(raw_results), delimiter='\t'))
    new_list = [
        d['show running-config ?'] for d in new_data
        if 'show running-config ?' in d
    ]
    hier_0 = (re.findall(r"\'\s\s(\w+)\s+", str(new_list)))
    hier_1 = (re.findall(r'\'\s\s(\w+\-\w+)\s+', str(new_list)))
    hier_2 = (re.findall(r"\'\s\s(\w+\-\w+\-\w+)\s+", str(new_list)))
    hier_3 = (re.findall(r"\'\s\s(\w+\-\w+\-\w+\-\w+)\s+",
                         str(new_list)))
    hier_4 = (re.findall(r"\'\s\s(\w+[\-]\w+\-\w+\-\w+\-\w+)\s+",
                         str(new_list)))
    hier_new = []
    for line_0 in hier_0:
        hier_new.append(line_0)
    for line_1 in hier_1:
        hier_new.append(line_1)
    for line_2 in hier_2:
        hier_new.append(line_2)
    for line_3 in hier_3:
        hier_new.append(line_3)
    for line_4 in hier_4:
        hier_new.append(line_4)
    hier_axos = sorted(hier_new)
    return hier_axos


# ------------------------------------------------------------
#  FUNCTION [6] CONFIRM CHOICE
# ------------------------------------------------------------
def confirm_choice(value):
    """ CONFIRM  """
    while True:
        choice = input(
            f"Is this your choice: Validate the {value} hierarchy? (yes/no): "
        ).lower()
        if choice in ('yes', 'y'):
            return True
        elif choice in ('no', 'n'):
            return False
        else:
            print("Invalid choice. Please enter 'yes' or 'no'.")


# ------------------------------------------------------------
#  FUNCTION [7] PRINT MENU
# ------------------------------------------------------------
def print_dict_as_menu(my_dict):
    """Prints a dictionary as a menu with 4 evenly spaced columns."""
    keys = list(my_dict.keys())
    values = list(my_dict.values())
    # -----------------------------------
    # Calculate the maximum length of a key for padding
    # -----------------------------------
    max_key_length = max(len(str(key)) for key in keys)
    max_value_length = max(len(str(value)) for value in my_dict.values())
    # -----------------------------------
    # Calculate the number of rows needed
    # -----------------------------------
    num_rows = (len(keys) + 3) // 4  # Ceiling division
    for row in range(num_rows):
        for col in range(4):
            index = row + col * num_rows
            if index < len(keys):
                key = keys[index]
                value = values[index]
                print(
                    f"{key:<{max_key_length + 1}}> {value:<{max_value_length +2}}\t",
                    end="\t")
        print()


# ------------------------------------------------------------
#  FUNCTION [8] ENTER INT
# ------------------------------------------------------------
def get_integer(prompt):
    """ GET INTEGER """
    while True:
        try:
            number = int(input(prompt))
            return number
        except ValueError:
            print("Invalid input. Please enter a number from the menu.")


# ------------------------------------------------------------
#  FUNCTION [8] MAIN
# ------------------------------------------------------------
def main():
    """ MAIN: ORCHESTRATE AND CALL FUNCTIONS """
    # -----------------------------------
    # START LOGGER
    # -----------------------------------
    start_logging = init_logger()
    if start_logging:
        logging.info('Script is starting')
    # -----------------------------------
    # CHECK TERMINAL SIZE
    # -----------------------------------
    if check_terminal_size():
        logging.info("Terminal size is sufficient: > or = 210x50.")
    else:
        logging.info("The terminal is too small. Please resize it to 210x50.")
        sys.exit(1)
    # -----------------------------------
    # GET VERSION & PRINT
    # -----------------------------------
    ver_cmd = "show card"
    ver_info = ssh_execute_cmd(ver_cmd, device_netmiko)
    banner_1 = ('=' * 80 + '\n')
    banner_2 = ('\n' + '=' * 80 + '\n')
    parsed_t0, parsed_dict0 = parse_fsm(template=SHOWCARDTMP, output=ver_info)
    #print(f'{banner_1} hostname = {ip_addr} {banner_2}')
    logging.info(f"Checking the AXOS version for {ip_addr}")
    print(banner(parsed_t0, width=130))
    # -----------------------------------
    # GET HIERARCHY
    # -----------------------------------
    logging.info('Use login info to ssh and determine AXOS hierarchy')
    hier_info = ssh_expect(device_paramiko)
    # -----------------------------------
    # PARSE HIERARCHY
    # -----------------------------------
    logging.info('Generate release specific AXOS hierarchy')
    hier_stanzas = create_hierarchy(hier_info)
    # -----------------------------------
    # MAKE HIERARCHY MENU_DICT
    # -----------------------------------
    logging.info('Use cli info to generate menu')
    hier_menu = dict(enumerate(hier_stanzas))
    # -----------------------------------
    # PRINT HIERARCHY MENU_DICT
    # -----------------------------------
    logging.info('Printing target menu')
    print("\n" + "=" * 205)
    print_dict_as_menu(hier_menu)
    print("=" * 205 + "\n")
    # -----------------------------------
    # INPUT CODE HIERARCHY
    # -----------------------------------
    logging.info('Input selection from menu')
    print('\n' + "=" * 80)
    hier_val = get_integer("Enter AXOS hierarchy number to check: ")
    confirm_val = hier_menu[hier_val]
    print(
        f'Your choice is {hier_val}, meaning a {confirm_val} hierarchy config check.'
    )
    print("=" * 80 + "\n")
    # -----------------------------------
    # CONFIRM CHOICE
    # -----------------------------------
    if confirm_choice(confirm_val):
        logging.info('Choice confirmed - continuing')
        print("\n" + "=" * 80 + "\n")
    else:
        print("Aborting the program...")
        sys.exit(1)
    # -----------------------------------
    # CRAFT INFO TO GEN
    # -----------------------------------
    templ_dir = "/home/ttt/J2/E9"
    dir_sep = "/"
    yml_data = (f'{templ_dir}{dir_sep}{confirm_val}{dir_sep}{confirm_val}' +
                "_config" + ".yaml")
    jj2_data = (f'{templ_dir}{dir_sep}{confirm_val}{dir_sep}{confirm_val}' +
                "_config" + ".j2")
    # -----------------------------------
    # GENERATE REFERENCE
    # -----------------------------------
    logging.info('Generate reference configuration using Jinja2/YAML')
    ref_cfg = gen_template_config(yml_data, jj2_data)
    # -----------------------------------
    # GET EXISTING CONFIG
    # -----------------------------------
    cli_cmd = (f'show running-config {confirm_val} | nomore')
    logging.info('Use ssh to get existing configuration')
    rtr_cfg = ssh_execute_cmd(cli_cmd, device_netmiko)
    # -----------------------------------
    #  DIFFPLUS FORMATTING
    # -----------------------------------
    logging.info('Use diffplus lib to format REF and RTR responses.')
    Config_A = IndentedConfig(ref_cfg,
                              comment_char='!',
                              indent_char=' ',
                              sanitize=True)
    Config_B = IndentedConfig(rtr_cfg,
                              comment_char='!',
                              indent_char=' ',
                              sanitize=True)
    # -----------------------------------
    # USE DIFFLIB SEQUENCER
    # -----------------------------------
    logging.info('Use difflib SequenceMatcher to determine % match ratio')
    seq_match = SequenceMatcher(None, ref_cfg, rtr_cfg)
    ratio = seq_match.ratio()
    #print(ratio)  # Check the similarity of the two strings
    #diff = unified_diff(ref_cfg.splitlines(), rtr_cfg.splitlines(), lineterm='')
    #print('\n'.join(list(diff)))
    #config_change = conf_diff.ConfDiff(ref_config, rtr_config)
    #print(config_change.diff())
    # -----------------------------------
    # DECISION TREE IF/THEN
    # -----------------------------------
    logging.info('Logic test: if >0.99 match "good" else "bad"')
    logging.info('Perform diff if needed (use Incremental Diff) and print\n')
    if ratio < 0.988:
        print("\n" + "=" * 80)
        print(" " * 15 + "--- THE CONFIGURATION DIFFERS FROM REF ---")
        print("=" * 80 + "\n")
        #diff = DeepDiff(Config_B.to_dict(), Config_A.to_dict())
        diff = IncrementalDiff(Config_A, Config_B, merge=False, colored=True)
        #for item_added in diff['dictionary_item_added']:
        #    print(item_added)
        print(diff)
        #diff = difflib.ndiff(ref_config, rtr_config)
        #print(''.join(diff),)
    else:
        print("=" * 80)
        print(" " * 15 + "--- THE CONFIGURATION IS EQUAL TO REF ---")
        print("=" * 80 + "\n")


# ------------------------------------------------------------
#  FUNCTION [9] INVOKE MAIN
# ------------------------------------------------------------
if __name__ == "__main__":
    main()
