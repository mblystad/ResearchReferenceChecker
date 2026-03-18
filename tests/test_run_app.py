import os

import run_app


def test_configure_streamlit_runtime_disables_development_mode():
    argv = run_app._configure_streamlit_runtime(32123)

    assert os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] == "false"
    assert os.environ["STREAMLIT_SERVER_PORT"] == "32123"
    assert "--global.developmentMode=false" in argv
    assert "--server.port=32123" in argv
