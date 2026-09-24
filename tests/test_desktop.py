import unittest
from urllib.request import urlopen

from desktop import start_local_server


class DesktopServerTests(unittest.TestCase):
    def test_starts_on_a_free_local_port_and_serves_the_app(self):
        server, thread, url = start_local_server()
        try:
            self.assertEqual(server.server_address[0], "127.0.0.1")
            with urlopen(url, timeout=2) as response:
                body = response.read().decode("utf-8")
            self.assertIn("Equivalencias", body)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
