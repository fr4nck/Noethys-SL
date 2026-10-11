import ast
import ssl
import types
import unittest
from pathlib import Path

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "noethys/Utils/UTILS_Portail_synchro.py"
)

def tree():
    return ast.parse(SOURCE.read_text(encoding="utf-8"))

def helpers(urlopen):
    nodes = [
        node for node in tree().body
        if isinstance(node, ast.FunctionDef)
        and node.name in ("ContexteSSLConnecthys", "UrlopenConnecthys")
    ]
    if len(nodes) != 2:
        raise AssertionError("Fonctions TLS manquantes")
    namespace = {"urlopen": urlopen}
    exec(compile(ast.Module(body=nodes, type_ignores=[]),
                 str(SOURCE), "exec"), namespace)
    return namespace

class TLSIsolationTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def fake_urlopen(*args, **kwargs):
            self.calls.append((args, kwargs))
            return "OK"

        self.functions = helpers(fake_urlopen)

    def test_default_uses_verified_tls(self):
        get_context = self.functions["ContexteSSLConnecthys"]
        self.assertIsNone(get_context())
        self.assertIsNone(get_context({}))
        self.assertIsNone(get_context({"accept_all_cert": False}))

    def test_permissive_context_does_not_change_global_tls(self):
        before = ssl._create_default_https_context
        get_context = self.functions["ContexteSSLConnecthys"]
        context = get_context({"accept_all_cert": True})
        self.assertEqual(context.verify_mode, ssl.CERT_NONE)
        self.assertFalse(context.check_hostname)
        self.assertIs(ssl._create_default_https_context, before)

    def test_request_without_option_keeps_original_signature(self):
        result = self.functions["UrlopenConnecthys"]("REQ", None)
        self.assertEqual(result, "OK")
        self.assertEqual(self.calls, [(("REQ",), {})])

    def test_request_with_option_receives_local_context(self):
        context = object()
        result = self.functions["UrlopenConnecthys"]("REQ", context)
        self.assertEqual(result, "OK")
        self.assertEqual(
            self.calls, [(("REQ",), {"context": context})]
        )

    def test_synchro_initialization_preserves_global_tls(self):
        cls = next(
            node for node in tree().body
            if isinstance(node, ast.ClassDef) and node.name == "Synchro"
        )
        init = next(
            node for node in cls.body
            if isinstance(node, ast.FunctionDef) and node.name == "__init__"
        )
        namespace = {
            "ContexteSSLConnecthys":
                self.functions["ContexteSSLConnecthys"]
        }
        exec(compile(ast.Module(body=[init], type_ignores=[]),
                     str(SOURCE), "exec"), namespace)

        before = ssl._create_default_https_context
        instance = types.SimpleNamespace()
        namespace["__init__"](
            instance, dict_parametres={"accept_all_cert": True}
        )
        self.assertIs(ssl._create_default_https_context, before)
        self.assertEqual(instance.contexte_ssl.verify_mode, ssl.CERT_NONE)

        content = SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("ssl._create_default_https_context =", content)
        self.assertEqual(
            content.count(
                "reponse = UrlopenConnecthys(req, self.contexte_ssl)"
            ),
            6,
        )

if __name__ == "__main__":
    unittest.main()
