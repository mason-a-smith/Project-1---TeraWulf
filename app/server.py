"""Local-only workbench. python app/server.py; visit http://127.0.0.1:8765."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import workbench

class Handler(BaseHTTPRequestHandler):
    def respond(self,obj,status=200):
        body=json.dumps(obj,allow_nan=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path=='/api/config':
            self.respond(dict(controls=workbench.CONTROLS,base=workbench.evaluate(),analysis=workbench.all_results()))
        elif self.path in ('/','/index.html'):
            body=Path(__file__).with_name('analysis.html').read_bytes()
            self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers(); self.wfile.write(body)
        elif self.path=='/assumptions':
            body=(Path(__file__).resolve().parents[1]/'evidence'/'ASSUMPTION_CHALLENGE_RECORD.md').read_bytes()
            self.send_response(200); self.send_header('Content-Type','text/plain; charset=utf-8'); self.end_headers(); self.wfile.write(body)
        else:
            self.send_error(404)
    def do_POST(self):
        if self.path!='/api/evaluate': self.send_error(404); return
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<10000: raise ValueError('Invalid request size')
            self.respond(workbench.evaluate(json.loads(self.rfile.read(n))))
        except (ValueError,TypeError,AssertionError,ArithmeticError) as e:
            self.respond({'error':str(e)},400)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765)
    port=parser.parse_args().port
    print(f'TeraWulf workbench: http://127.0.0.1:{port} - Ctrl+C to stop',flush=True)
    HTTPServer(('127.0.0.1',port),Handler).serve_forever()
