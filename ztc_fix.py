#!/usr/bin/env python3


"""
Zabbix vulnerability assessment plugin.

Script will fix vulnerabilities.
ztc_fix.py {HOST.HOST} {TRIGGER.ID} {EVENT.ID}
"""


__author__ = 'samosvat'
__version__ = '0.3.2'


import logging
import subprocess
import sys

from pyzabbix import ZabbixAPI

import ztc_config as c


logging.basicConfig(
    # level=logging.DEBUG,
    level=logging.INFO,
    filename=c.log_file,
    format='%(asctime)s  %(process)d  %(levelname)s  %(message)s  [%(filename)s:%(lineno)d]')


def shell(command):
    proc = subprocess.Popen(command, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, shell=True)
    out = proc.communicate()[0].decode('utf8')
    return out


def do_fix(vname, fix_cmd):
    try:
        h = zapi.host.get(filter={'name': vname}, output=['hostid'])
        if len(h) == 0:
            logging.warning('Can\'t find host {} in Zabbix. Skip fixing vulnerabilities on this host.'.format(vname))
            return False

        h_if = zapi.hostinterface.get(hostids=h[0]['hostid'],
                                      filter={'main': '1', 'type': '1'},
                                      output=['dns', 'ip', 'useip'])[0]
        if h_if['useip'] == '1':
            h_conn = h_if['ip']
        else:
            h_conn = h_if['dns']

        if c.use_zbx_agent_to_fix:
            cmd = 'zabbix_get -s {} -k "system.run[{},nowait]"'.format(h_conn, fix_cmd)
        else:
            cmd = 'ssh {} -l {} "{}"'.format(h_conn, c.ssh_user, fix_cmd)

        logging.info(cmd)
        out = shell(cmd)
        logging.info(out)
        return True
    except Exception as e:
        logging.info('Exception: {}'.format(e))
        return False


triggered_host = sys.argv[1]
trigger_id = sys.argv[2]
event_id = sys.argv[3]


logging.info('Getting Started with the event: {}/tr_events.php?triggerid={}&eventid={}'
             .format(c.zbx_url, trigger_id, event_id))


try:
    zapi = ZabbixAPI(c.zbx_url, timeout=10)
    zapi.session.verify = c.zbx_verify_ssl_certs
    zapi.login(c.zbx_user, c.zbx_pass)
    logging.info('Connected to Zabbix API v.{}'.format(zapi.api_version()))
except Exception as e:
    logging.info('Error: Can\'t connect to Zabbix API. Exception: {}'.format(e))
    exit(1)


try:
    ack = zapi.event.get(eventids=event_id, select_acknowledges=['alias', 'message'], output=['alias', 'message'])
    ack_alias = ack[0]['acknowledges'][0]['alias']
    if ack_alias != c.acknowledge_user:
        logging.info('Not trusted user in acknowledge: {}.\nSkipping this request to fix.'.format(ack_alias))
        exit(0)
    tg = zapi.trigger.get(triggerids=trigger_id, output='extend')[0]
except Exception as e:
    logging.error('Error. Exception: {}'.format(e))
    exit(1)


tg_desc = tg['description']
tg_comm = tg['comments']


if triggered_host == c.zbx_h_hosts:
    h_name = tg_desc[tg_desc.rfind(' = ') + 3:]
    fix = tg_comm[tg_comm.rfind('\r\n\r\n') + 4:]
    do_fix(h_name, fix)
elif triggered_host == c.zbx_h_pkgs:
    pkg_name = tg_desc[tg_desc.rfind(' = ') + 3:].split()[0]
    tg_comm_tmp = tg_comm[tg_comm.rfind('\r\n\r\n') + 4:].split('\r\n----\r\n')
    hosts = tg_comm_tmp[0].splitlines()
    fix = tg_comm_tmp[1]
    current_h = 0
    total_h = len(hosts)
    for h_name in hosts:
        current_h += 1
        logging.info('[{current_h} in {total_h}] {h_name}'.format(current_h=current_h, total_h=total_h, h_name=h_name))
        do_fix(h_name, fix)
else:
    logging.info('Host {} that triggered the trigger does not match the required: {} or {}'
                 .format(triggered_host, c.zbx_h_pkgs, c.zbx_h_hosts))

# todo: Добавить в акновледж к событию информацию с результатом выполнения команды (успех/неуспех)

logging.info('End')
