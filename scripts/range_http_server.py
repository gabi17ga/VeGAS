#!/usr/bin/env python3
"""Simple HTTP server that supports Range requests (for BAM/BAI seeking).
Usage: python3 scripts/range_http_server.py --dir data/output --host 127.0.0.1 --port 8000

This is a small drop-in replacement for python -m http.server with Range support
so tools like IGV can fetch byte ranges from BAM files.
"""
import argparse
import http.server
import os
import posixpath
import shutil
import sys
from http import HTTPStatus

class RangeRequestHandler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        ctype = self.guess_type(path)
        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None

        fs = os.fstat(f.fileno())
        size = fs.st_size

        # check for Range header first
        range_header = self.headers.get('Range')
        if range_header:
            try:
                unit, rng = range_header.strip().split('=', 1)
                if unit != 'bytes':
                    raise ValueError('Unsupported unit')
                start_s, end_s = rng.split('-', 1)
                start = int(start_s) if start_s else 0
                end = int(end_s) if end_s else size - 1
                if start > end:
                    raise ValueError('Invalid range')
                if end >= size:
                    end = size - 1
            except Exception:
                # Malformed range; fall back to full content
                start = None

            if start is not None:
                length = end - start + 1
                self.send_response(HTTPStatus.PARTIAL_CONTENT)
                self.send_header('Content-type', ctype)
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                self.send_header('Content-Length', str(length))
                self.send_header('Last-Modified', self.date_time_string(fs.st_mtime))
                self.end_headers()
                f.seek(start)
                return http.server.BufferedReader(f)

        # No valid Range header -> return full file
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-type', ctype)
        self.send_header('Content-Length', str(size))
        self.send_header('Last-Modified', self.date_time_string(fs.st_mtime))
        self.send_header('Accept-Ranges', 'bytes')
        self.end_headers()
        return f

    # override log_message to be a bit cleaner
    def log_message(self, format, *args):
        sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), format%args))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dir', default='data/output', help='Directory to serve')
    p.add_argument('--host', default='127.0.0.1', help='Host to bind')
    p.add_argument('--port', default=8000, type=int, help='Port to bind')
    args = p.parse_args()

    if not os.path.isdir(args.dir):
        print('Directory not found:', args.dir, file=sys.stderr)
        sys.exit(1)

    os.chdir(args.dir)
    server = http.server.ThreadingHTTPServer((args.host, args.port), RangeRequestHandler)
    print(f"Serving {os.getcwd()} on http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down')
        server.shutdown()

if __name__ == '__main__':
    main()
