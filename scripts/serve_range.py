#!/usr/bin/env python3
"""Simple HTTP server with support for Range requests.

Serves files from a given root directory and implements partial content (206)
so that IGV.js can request slices of BAM files.

Usage:
  python scripts/serve_range.py --root data/output --port 8002
"""
import http.server
import socketserver
import argparse
import os
from urllib.parse import unquote


class RangeRequestHandler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return http.server.SimpleHTTPRequestHandler.send_head(self)

        if not os.path.exists(path):
            self.send_error(404, 'File not found')
            return None

        ctype = self.guess_type(path)
        fs = os.stat(path)
        size = fs.st_size

        range_header = self.headers.get('Range')
        if range_header:
            # e.g. bytes=0-1023
            start, end = 0, size - 1
            try:
                units, rng = range_header.split('=')
                if units.strip() == 'bytes':
                    if '-' in rng:
                        s, e = rng.split('-')
                        if s.strip():
                            start = int(s)
                        if e.strip():
                            end = int(e)
            except Exception:
                start, end = 0, size - 1

            if start > end or start >= size:
                self.send_error(416, 'Requested Range Not Satisfiable')
                return None

            self.send_response(206)
            self.send_header('Content-type', ctype)
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.send_header('Content-Length', str(end - start + 1))
            self.end_headers()
            self.range = (start, end)
            return open(path, 'rb')
        else:
            self.send_response(200)
            self.send_header('Content-type', ctype)
            self.send_header('Content-Length', str(size))
            self.end_headers()
            self.range = None
            return open(path, 'rb')

    def copyfile(self, source, outputfile):
        # if range present, copy only the requested bytes
        if getattr(self, 'range', None):
            start, end = self.range
            source.seek(start)
            remaining = end - start + 1
            bufsize = 64 * 1024
            while remaining > 0:
                read_len = min(bufsize, remaining)
                data = source.read(read_len)
                if not data:
                    break
                outputfile.write(data)
                remaining -= len(data)
        else:
            http.server.SimpleHTTPRequestHandler.copyfile(self, source, outputfile)


def run(port, root, host='127.0.0.1'):
    os.chdir(root)
    handler = RangeRequestHandler
    # Allow reusing address to reduce "Address already in use" issues when
    # restarting the server quickly (TIME_WAIT sockets on macOS/Unix).
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    bind_addr = (host, port)
    with socketserver.ThreadingTCPServer(bind_addr, handler) as httpd:
        print(f'Serving {root} at http://{host}:{port} (range-capable)')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\nShutting down')
            httpd.server_close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=8002)
    p.add_argument('--root', default='data/output')
    p.add_argument('--host', default='127.0.0.1', help='Host/IP to bind to (default: 127.0.0.1)')
    args = p.parse_args()
    run(args.port, args.root, args.host)


if __name__ == '__main__':
    main()
