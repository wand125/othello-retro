"""Entry for the true-unbounded four-environment benchmark."""
import time
STARTED=time.monotonic()
import unbounded_engine
unbounded_engine.SCRIPT_STARTED=STARTED
if __name__=='__main__':unbounded_engine.main()
