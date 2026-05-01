import py_compile
import sys
path = 'tender_dashboard_reflex/tender_dashboard_reflex/state.py'
try:
    py_compile.compile(path, doraise=True)
    print('OK')
except Exception as e:
    import traceback
    print('ERROR')
    traceback.print_exc()
    sys.exit(1)
