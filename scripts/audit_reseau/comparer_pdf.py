"""Compare deux PDF après normalisation de leurs dates et de leur identifiant.

Usage : python3 -I comparer_pdf.py a.pdf b.pdf [libellé]   (code retour 0 si identiques)"""
import re, sys, hashlib
def norm(path):
    b = open(path, "rb").read()
    b = re.sub(rb"D:\d{14}[+\-Z][^)]*", b"D:X", b)
    b = re.sub(rb"/ID\s*\[\s*<[0-9a-fA-F]+>\s*<[0-9a-fA-F]+>\s*\]", b"/ID[X]", b)
    b = re.sub(rb"/ID\s*\[\s*\([^)]*\)\s*\([^)]*\)\s*\]", b"/ID[X]", b)
    return b
a, b = norm(sys.argv[1]), norm(sys.argv[2])
diff = sum(1 for x, y in zip(a, b) if x != y) + abs(len(a) - len(b))
print("%s  octets_differents_apres_normalisation=%d  (%d vs %d octets)  %s" % (
    "IDENTIQUES" if diff == 0 else "DIFFÉRENTS", diff, len(a), len(b), sys.argv[3] if len(sys.argv) > 3 else ""))
sys.exit(0 if diff == 0 else 1)
