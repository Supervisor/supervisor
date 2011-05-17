# -*- Mode: Python -*-

import pprint

def main (env, stdin, stdout):

    stdout.write (
            '<html><body><h1>Test CGI Module</h1>\r\n'
            '<br>The Environment:<pre>\r\n'
            )
    pprint.pprint (env, stdout)
    stdout.write ('</pre></body></html>\r\n')
