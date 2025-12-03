#!/usr/bin/env python3
"""
Container Name Exporter for Prometheus
Exports Docker container ID to name mappings as Prometheus metrics
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import docker
import time

PORT = 9104

def get_container_mappings():
    """Get Docker container ID to name mappings"""
    try:
        client = docker.DockerClient(base_url='unix://var/run/docker.sock')
        containers = client.containers.list()

        mappings = {}
        for container in containers:
            # Get full container ID (64 characters)
            container_id = container.id
            # Get container name
            name = container.name
            mappings[container_id] = name

        return mappings
    except Exception as e:
        print(f"Error getting container mappings: {e}")
        return {}

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            mappings = get_container_mappings()

            metrics = ['# HELP container_name_info Container ID to name mapping',
                      '# TYPE container_name_info gauge']

            for container_id, name in mappings.items():
                # Create metric with container_id in the systemd scope format
                systemd_id = f"/system.slice/docker-{container_id}.scope"
                metrics.append(
                    f'container_name_info{{container_id="{container_id}",systemd_id="{systemd_id}",container_name="{name}"}} 1'
                )

            response = '\n'.join(metrics) + '\n'

            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(response.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress default logging
        pass

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), MetricsHandler)
    print(f"Container Name Exporter listening on port {PORT}")
    server.serve_forever()
