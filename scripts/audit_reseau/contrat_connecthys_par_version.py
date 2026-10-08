"""Analyse mécanique du contrat Connecthys sur toutes les versions publiées.

Usage : python3 -I contrat_connecthys_par_version.py <clone de Noethys/Connecthys> <sortie.json>
Lecture seule (git show) ; ne contacte aucun serveur."""
import subprocess, sys, re, json, itertools
REPO = sys.argv[1]
def git(*a):
    r = subprocess.run(["git", "-C", REPO] + list(a), capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None
tags = git("tag", "--sort=creatordate").split()
tags.append("master")
def show(tag, path):
    return git("show", "%s:connecthys/%s" % (tag, path))
def verdict(tag):
    v, imp, exp_, crypt, models = (show(tag, p) for p in ("application/views.py", "application/importation.py",
                                   "application/exportation.py", "application/cryptage.py", "application/models.py"))
    d = {}
    d["views"] = v is not None
    d["route_syncup"] = bool(v and "/syncup/<int:secret>" in v)
    d["route_syncdown"] = bool(v and re.search(r"/syncdown/<int:secret>/<int:last>", v))
    d["route_get_version"] = bool(v and "@app.route('/get_version')" in v)
    d["syncup_retourne_str"] = bool(v and "return str(resultat)" in v)
    d["jeton_date_plus_chiffres"] = bool(exp_ and 'strftime("%Y%m%d")' in exp_ and 'caract in "0123456789"' in exp_)
    # syncup : actions existantes -> UPDATE (etat, traitement_date, reponse) par ref_unique
    d["syncup_update_etat_par_ref_unique"] = bool(imp and "u.where(table_actions_destination.c.ref_unique == action.ref_unique)" in imp
                                                   and '"etat" : action.etat' in imp.replace("'", '"'))
    d["syncup_actions_non_droppees"] = bool(imp and '"actions"' in imp and 'tables.append("actions")' in imp)
    # syncdown : filtre
    d["syncdown_etat_attente"] = bool(exp_ and 'models.Action.etat == "attente"' in exp_)
    d["syncdown_last_ref_unique"] = bool(exp_ and "models.Action.ref_unique == last" in exp_)
    d["syncdown_last0_tout"] = bool(exp_ and 'if last == 0' in exp_)
    d["action_ref_unique"] = bool(models and "ref_unique = Column" in models)
    d["action_colonnes_etat_reponse"] = bool(models and "etat = Column" in models and "reponse = Column" in models)
    # chiffrement
    d["sv2_ecrit"] = bool(crypt and 'b"SV2"' in crypt and "def cryptFile2" in crypt)
    d["pickle_dans_dechiffrement_serveur"] = bool(crypt and "pickle.load" in crypt)
    d["pieces_chiffrees_serveur"] = bool(v and "CrypterFichier(chemin_fichier" in v)
    d["pieces_route"] = bool(v and "@app.route('/pieces'" in v)
    d["models_py"] = models is not None
    d["models_parametre_Action"] = bool(models and "class Action(Base)" in models)
    return d
res = {t: verdict(t) for t in tags}
json.dump(res, open(sys.argv[2], "w"), indent=1)
keys = list(res["master"].keys())
print("%d versions analysées" % len(tags))
for k in keys:
    vals = [res[t][k] for t in tags]
    # intervalles contigus
    runs = []
    for val, grp in itertools.groupby(zip(tags, vals), key=lambda x: x[1]):
        g = list(grp); runs.append((val, g[0][0], g[-1][0], len(g)))
    print("%-38s %s" % (k, " | ".join("%s %s→%s (%d)" % ("OUI" if r[0] else "NON", r[1], r[2], r[3]) for r in runs)))
