import importlib, sys, traceback
print("PY version", sys.version)
for mod in ["dana", "dana.lang", "dana.lang.dana", "dana.lang.integrations.python.to_dana"]:
    try:
        m = importlib.import_module(mod); print("import ok:", mod, [n for n in dir(m) if not n.startswith('_')][:20])
    except Exception as e:
        print("import FAIL:", mod, e)
try:
    from dana.lang.dana import dana
    dana.enable_module_imports()
    import p6_module
    print("BRIDGE call:", p6_module.solve("xe chay xang"))
except Exception:
    traceback.print_exc()
