#!/usr/bin/python
# -*- coding: utf-8 -*-

import requests
import sys
import os

from Queue import Queue
from threading import Thread

# Last used proxy for round-robin.
last_proxy = -1

# Proxy check result constants.
check_result_ok = 0
check_result_failed = 1
check_result_banned = 2
check_result_wrong = 3
check_result_timeout = 4
check_result_exception = 5
check_result_empty = 6
check_result_max = 6  # Should be equal to maximal return code.


def append_file(filename, text):
    path = './'
    if os.path.exists(path+filename):
        f = open(path + filename, 'a+b')
    else:
        f = open(path + filename, 'w+b')

    f.write("%s\n" % text)

    f.close()


def append_file_no_nl(filename, text):
    path = './'
    if os.path.exists(path+filename):
        f = open(path + filename, 'a+b')
    else:
        f = open(path + filename, 'w+b')

    f.write("%s" % text)

    f.close()


# Simple function to do a call to Niantic's system for
# testing proxy connectivity.
def check_proxy(proxy_queue, timeout, proxies, check_results):
    # Url for proxy testing.
    proxy_test_url = 'https://pgorelease.nianticlabs.com/plfe/rpc'
    proxy = proxy_queue.get()

    check_result = check_result_ok

    if proxy and proxy[1]:

        print 'Checking proxy: ' + proxy[1] + ''

        try:
            proxy_response = requests.post(proxy_test_url, '',
                                           proxies={'http': 'http://'+proxy[1],
                                                    'https': 'http://'+proxy[1]},
                                           timeout=timeout)

            if proxy_response.status_code == 200:
                print 'Proxy ', proxy[1], ' is ok.'
                proxy_queue.task_done()
                proxies.append(proxy[1])
                append_file_no_nl("ok.txt", "'"+proxy[1]+"',")
                check_results[check_result_ok] += 1
                return True

            elif proxy_response.status_code == 403:
                proxy_error = 'Proxy ' + proxy[1] + ' is banned - got status code: ' + str(proxy_response.status_code) + ''
                append_file("banned.txt", proxy[1]+','+proxy_error)
                check_result = check_result_banned

            else:
                proxy_error = 'Wrong status code - ' + str(proxy_response.status_code) + ''
                append_file("wrong_status.txt", proxy[1]+','+proxy_error)
                check_result = check_result_wrong

        except requests.ConnectTimeout:
            proxy_error = 'Connection timeout (' + str(timeout) + ' second(s) ) via proxy ' + proxy[1] + ''
            append_file("timeout.txt", proxy[1] + ',' + proxy_error)
            check_result = check_result_timeout

        except requests.ConnectionError:
            proxy_error = 'Failed to connect to proxy ' + proxy[1] + ''
            append_file("failed_connection.txt", proxy[1] + ',' + proxy_error)
            check_result = check_result_failed

        except Exception as e:
            proxy_error = e
            check_result = check_result_exception

    else:
        proxy_error = 'Empty proxy server.'
        check_result = check_result_empty

    print proxy_error

    proxy_queue.task_done()

    check_results[check_result] += 1
    return False


# Check all proxies and return a working list with proxies.
def check_proxies():
    source_proxies = []

    check_results = [0] * (check_result_max + 1)

    # Load proxies from the file. Override args.proxy if specified.

    print 'Loading proxies from file.'

    with open('./proxy.txt') as f:
        for line in f:
            # Ignore blank lines and comment lines.
            if len(line.strip()) == 0 or line.startswith('#'):
                continue
            source_proxies.append(line.strip())

    print'Loaded ', len(source_proxies), ' proxies.'

    if len(source_proxies) == 0:
        print('Proxy file was configured but ' +
              'no proxies were loaded. Aborting.')
        sys.exit(1)

    proxy_queue = Queue()
    total_proxies = len(source_proxies)

    print 'Checking ', total_proxies, ' proxies...'

    proxies = []

    for proxy in enumerate(source_proxies):
        proxy_queue.put(proxy)

        t = Thread(target=check_proxy,
                   name='check_proxy',
                   args=(proxy_queue, 60, proxies,
                         check_results))
        t.daemon = True
        t.start()

    # This is painful but we need to wait here until proxy_queue is
    # completed so we have a working list of proxies.
    proxy_queue.join()

    working_proxies = len(proxies)

    if working_proxies == 0:
        print'Proxy was configured but no working proxies were found. Aborting.'
        sys.exit(1)
    else:
        other_fails = (check_results[check_result_failed] +
                       check_results[check_result_wrong] +
                       check_results[check_result_exception] +
                       check_results[check_result_empty])
        print'Proxy check completed. Working:', working_proxies, 'banned:', check_results[check_result_banned], \
            'timeout:', check_results[check_result_timeout], 'other fails:', \
            other_fails, ' of total ', total_proxies, ' configured. '
        return proxies


check_proxies()
