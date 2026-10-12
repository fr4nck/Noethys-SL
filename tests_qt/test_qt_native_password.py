import base64
import unittest

from noethys_qt.activities_native import _decode_network_password


class DecodageMotDePasseReseauTests(unittest.TestCase):
    def test_decode_network_password_accepts_historical_noethys_format(self):
        plain = "mot-de-passe-test"
        encoded = "#64#" + base64.b64encode(plain.encode("utf-8")).decode("ascii")
        self.assertEqual(_decode_network_password(encoded), plain)

    def test_decode_network_password_keeps_plain_value(self):
        self.assertEqual(_decode_network_password("plain-test"), "plain-test")


if __name__ == "__main__":
    unittest.main()
